"""
Loist REST API (v1).

This module implements the public HTTP REST API for frontend applications.
It is an independent interface, NOT a wrapper around MCP tools: both the REST
routes here and the MCP tools in src/server.py call the same shared service
layer (src/services/). The two interfaces evolve independently — changes to
MCP tool signatures do not affect REST contracts, and vice versa.

    Frontend / HTTP clients ──> REST API (this module, /api/v1/*) ──┐
                                                                    ├──> src/services/
    MCP clients (agents)    ──> MCP tools (src/server.py)  ─────────┘

All endpoints live under the /api/v1 prefix. Errors use a single envelope:

    {"success": false, "error": "<ERROR_CODE>", "message": "<human readable>"}

See docs/frontend-api-guide.md for the full API reference.
"""

import hashlib
import logging
from typing import AsyncGenerator

from fastmcp import FastMCP
from starlette.responses import JSONResponse, StreamingResponse, RedirectResponse, Response
from starlette.requests import Request
from starlette.background import BackgroundTask

from src.exceptions import ValidationError, ResourceNotFoundError

# Import HTTP API schemas for parameter validation
from src.schemas.http_api import (
    validate_search_params,
    validate_uuid_path,
    validate_download_params,
    ErrorCode,
)

from src.services import audio_service
from src.services import streaming_service
from src.services import download_service
from src.services import party_service
from src.services import work_service

from src.converter import (
    ConversionError,
    ConversionTimeoutError,
    get_default_preset,
)

logger = logging.getLogger(__name__)

# Single source of truth for the REST API version prefix.
API_V1_PREFIX = "/api/v1"


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """
    Build a standardized API error response.

    Every REST error — validation, not-found, auth, internal — must go through
    this helper so clients can rely on one shape:

        {"success": false, "error": "<ERROR_CODE>", "message": "..."}
    """
    return JSONResponse(
        {"success": False, "error": code, "message": message},
        status_code=status_code,
    )


def register_http_api_routes(mcp: FastMCP) -> None:
    """
    Register all v1 REST API routes with the FastMCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.custom_route(f"{API_V1_PREFIX}/tracks/{{audioId}}", methods=["GET"])
    async def get_track(request: Request) -> Response:
        """
        Get metadata for a specific audio track.
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        try:
            service_result = await audio_service.get_audio_metadata(audio_id)

            # The service returns a dict with Pydantic models, need to convert to JSON-serializable
            response_data = {
                "success": True,
                "audio_id": service_result["audio_id"],
                "metadata": service_result["metadata"].model_dump(),
                "resources": service_result["resources"].model_dump(),
            }

            # Create a JSON response to calculate ETag and then set headers
            response = JSONResponse(response_data)

            # ETag based on content hash
            etag = hashlib.md5(response.body).hexdigest()
            response.headers["ETag"] = f'"{etag}"'

            # Cache for 1 hour, but require re-validation
            response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"

            # Check for If-None-Match header from client
            if request.headers.get("if-none-match") == f'"{etag}"':
                return Response(status_code=304)

            return response

        except ResourceNotFoundError as e:
            return error_response(ErrorCode.TRACK_NOT_FOUND, str(e), 404)
        except Exception as e:
            logger.exception(f"Unexpected error getting track {audio_id}: {e}")
            return error_response(ErrorCode.INTERNAL_ERROR, "Internal server error", 500)


    @mcp.custom_route(f"{API_V1_PREFIX}/search", methods=["GET"])
    async def search_tracks(request: Request) -> Response:
        """
        Search for audio tracks.

        Uses strict parameter validation - invalid parameters return 400 Bad Request
        instead of being silently corrected.
        """
        try:
            # Validate query parameters using Pydantic schema
            query_params = dict(request.query_params)
            validated_params = validate_search_params(query_params)

            # Extract validated values
            query = validated_params.q
            limit = validated_params.limit
            offset = validated_params.offset

            # Build filters from validated parameters
            filters = {}
            if validated_params.genre:
                filters["genre"] = validated_params.genre.split(",")

            # Call service with validated parameters
            service_result = await audio_service.search_audio_library(
                query=query, limit=limit, offset=offset, filters=filters
            )

            # Convert Pydantic models to dicts for JSON response
            service_result['results'] = [r.model_dump() for r in service_result['results']]
            if service_result['facets']:
                service_result['facets'] = service_result['facets'].model_dump()

            response_data = {"success": True, **service_result}
            response = JSONResponse(response_data)

            # Add pagination headers
            response.headers['X-Total-Count'] = str(service_result['total'])

            # Build Link header
            base_url = str(request.url).split('?')[0] + f"?q={query}"
            links = []
            if service_result['has_more']:
                next_offset = offset + limit
                links.append(f'<{base_url}&limit={limit}&offset={next_offset}>; rel="next"')
            if offset > 0:
                prev_offset = max(0, offset - limit)
                links.append(f'<{base_url}&limit={limit}&offset={prev_offset}>; rel="prev"')
            if links:
                response.headers['Link'] = ", ".join(links)

            return response

        except ValidationError as e:
            return error_response(ErrorCode.INVALID_QUERY, str(e), 400)

        except Exception as e:
            logger.exception(f"Search failed for query '{request.query_params.get('q', 'unknown')}': {e}")
            return error_response(
                ErrorCode.SEARCH_FAILED, "An internal error occurred during search.", 500
            )


    @mcp.custom_route(f"{API_V1_PREFIX}/tracks/{{audioId}}/stream", methods=["GET"])
    async def get_track_stream(request: Request) -> Response:
        """
        Get signed streaming URL for an audio track.
        Redirects the client to a signed GCS URL for efficient streaming.
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        try:
            details = await streaming_service.get_audio_stream_details(audio_id)
            # Redirect to the signed URL. The client's browser/player will handle the stream.
            # GCS correctly handles HTTP Range requests on signed URLs.
            return RedirectResponse(url=details["signed_url"], status_code=302)
        except ResourceNotFoundError as e:
            return error_response(ErrorCode.TRACK_NOT_FOUND, str(e), 404)
        except Exception as e:
            logger.exception(f"Failed to get stream URL for {audio_id}: {e}")
            return error_response(ErrorCode.INTERNAL_ERROR, "Internal server error", 500)


    @mcp.custom_route(f"{API_V1_PREFIX}/tracks/{{audioId}}/thumbnail", methods=["GET"])
    async def get_track_thumbnail(request: Request) -> Response:
        """
        Get signed URL for track thumbnail/artwork.
        Redirects the client to a signed GCS URL.
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        try:
            details = await streaming_service.get_thumbnail_details(audio_id)
            return RedirectResponse(url=details["signed_url"], status_code=302)
        except ResourceNotFoundError as e:
            return error_response(ErrorCode.TRACK_NOT_FOUND, str(e), 404)
        except Exception as e:
            logger.exception(f"Failed to get thumbnail URL for {audio_id}: {e}")
            return error_response(ErrorCode.INTERNAL_ERROR, "Internal server error", 500)


    @mcp.custom_route(f"{API_V1_PREFIX}/tracks/{{audioId}}/download", methods=["GET"])
    async def download_audio(request: Request) -> Response:
        """
        Download audio file with optional format conversion. Refactored to use download_service.
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        target_format = request.query_params.get("format")
        preset = request.query_params.get("preset")

        try:
            target_format, preset = validate_download_params(target_format, preset)
            # Apply default preset if not provided
            if preset is None:
                preset = get_default_preset(target_format)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        try:
            action, data = await download_service.prepare_audio_download(audio_id, target_format, preset)

            if action == "redirect":
                return RedirectResponse(url=data["url"], status_code=302)

            if action == "stream":
                output_path = data["output_path"]

                async def file_iterator() -> AsyncGenerator[bytes, None]:
                    chunk_size = 64 * 1024
                    with open(output_path, "rb") as f:
                        while chunk := f.read(chunk_size):
                            yield chunk

                cleanup_task = BackgroundTask(download_service.cleanup_temp_directory, temp_dir=data["temp_dir"])

                return StreamingResponse(
                    file_iterator(),
                    media_type=data["mime_type"],
                    background=cleanup_task,
                    headers={
                        "Content-Disposition": f'attachment; filename="{data["download_filename"]}"',
                        "Content-Length": str(data["file_size"]),
                        "X-Conversion-Time": str(data["conversion_time"]),
                    },
                )

            # Should not be reached
            return error_response(ErrorCode.INTERNAL_ERROR, "Unknown service action", 500)

        except (ConversionTimeoutError, ConversionError, ResourceNotFoundError) as e:
            error_map = {
                ConversionTimeoutError: (504, ErrorCode.CONVERSION_TIMEOUT, "Conversion timed out"),
                ConversionError: (500, ErrorCode.CONVERSION_FAILED, f"Conversion failed: {e}"),
                ResourceNotFoundError: (404, ErrorCode.TRACK_NOT_FOUND, str(e)),
            }
            status, code, msg = error_map.get(type(e), (500, ErrorCode.DOWNLOAD_FAILED, str(e)))
            logger.error(f"Download failed for {audio_id}: {msg}")
            return error_response(code, msg, status)
        except Exception as e:
            logger.exception(f"Unexpected download failure for {audio_id}: {e}")
            return error_response(ErrorCode.INTERNAL_ERROR, "Unexpected download error", 500)


    @mcp.custom_route(f"{API_V1_PREFIX}/tracks/{{audioId}}", methods=["DELETE"])
    async def delete_track(request: Request) -> Response:
        """
        Delete a track via HTTP API.
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return error_response(ErrorCode.VALIDATION_ERROR, str(e), 400)

        try:
            await audio_service.delete_audio_track_and_files(audio_id)
            return Response(status_code=204)
        except ResourceNotFoundError as e:
            return error_response(ErrorCode.TRACK_NOT_FOUND, str(e), 404)
        except Exception as e:
            logger.exception(f"Failed to delete track {audio_id}: {e}")
            return error_response(ErrorCode.INTERNAL_ERROR, "Internal server error", 500)


    # ====================================================================
    # Song Publishing API Endpoints
    # ====================================================================

    @mcp.custom_route("/api/parties", methods=["POST"])
    async def create_party_endpoint(request: Request) -> Response:
        """
        Create a new party (person or organization).

        POST /api/parties
        Body: {"name": "...", "party_type": "person"|"organization", ...}
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Invalid JSON body"
            }, status_code=400)

        if not body.get("name"):
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Field 'name' is required"
            }, status_code=400)

        try:
            result = await party_service.create_party(body)
            return JSONResponse({"success": True, **result}, status_code=201)
        except ValidationError as e:
            return JSONResponse({"success": False, "error": ErrorCode.VALIDATION_ERROR, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to create party: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/parties/search", methods=["GET"])
    async def search_parties_endpoint(request: Request) -> Response:
        """
        Search parties by name.

        GET /api/parties/search?q=lennon&limit=20&offset=0
        """
        query = request.query_params.get("q", "").strip()
        if not query:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Query parameter 'q' is required"
            }, status_code=400)

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Parameters 'limit' and 'offset' must be integers"
            }, status_code=400)

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        try:
            result = await party_service.search_parties(query, limit=limit, offset=offset)
            return JSONResponse({"success": True, **result})
        except Exception as e:
            logger.exception(f"Party search failed for '{query}': {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/parties/{partyId}", methods=["GET"])
    async def get_party_endpoint(request: Request) -> Response:
        """
        Get party details with involvement summary.

        GET /api/parties/{partyId}
        """
        party_id = request.path_params.get("partyId")
        try:
            party_id = validate_uuid_path(party_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

        try:
            result = await party_service.get_party(party_id)
            return JSONResponse({"success": True, **result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get party {party_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/works/search", methods=["GET"])
    async def search_works_endpoint(request: Request) -> Response:
        """
        Search works by title.

        GET /api/works/search?q=imagine&limit=20&offset=0
        """
        query = request.query_params.get("q", "").strip()
        if not query:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Query parameter 'q' is required"
            }, status_code=400)

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Parameters 'limit' and 'offset' must be integers"
            }, status_code=400)

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        try:
            result = await work_service.search_works(query, limit=limit, offset=offset)
            return JSONResponse({"success": True, **result})
        except Exception as e:
            logger.exception(f"Work search failed for '{query}': {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/works/{workId}", methods=["GET"])
    async def get_work_endpoint(request: Request) -> Response:
        """
        Get work details with writers, publishers, recordings, and split warnings.

        GET /api/works/{workId}
        """
        work_id = request.path_params.get("workId")
        try:
            work_id = validate_uuid_path(work_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

        try:
            result = await work_service.get_work(work_id)
            return JSONResponse({"success": True, **result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get work {work_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/works/{workId}/writers", methods=["PUT"])
    async def update_work_writers_endpoint(request: Request) -> Response:
        """
        Replace all writers on a work (batch update).

        PUT /api/works/{workId}/writers
        Body: {"writers": [{"party_id": "...", "split_percentage": 50.0, "split_status": "confirmed"}, ...]}
        """
        work_id = request.path_params.get("workId")
        try:
            work_id = validate_uuid_path(work_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Invalid JSON body"
            }, status_code=400)

        writers = body.get("writers")
        if writers is None or not isinstance(writers, list):
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Field 'writers' is required and must be an array"
            }, status_code=400)

        try:
            result = await work_service.update_work_writers(work_id, writers)
            return JSONResponse({"success": True, **result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except ValidationError as e:
            return JSONResponse({"success": False, "error": ErrorCode.VALIDATION_ERROR, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to update writers for work {work_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/works/{workId}/publishers", methods=["PUT"])
    async def update_work_publishers_endpoint(request: Request) -> Response:
        """
        Replace all publishers on a work (batch update).

        PUT /api/works/{workId}/publishers
        Body: {"publishers": [{"party_id": "...", "split_percentage": 100.0, "split_status": "confirmed"}, ...]}
        """
        work_id = request.path_params.get("workId")
        try:
            work_id = validate_uuid_path(work_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Invalid JSON body"
            }, status_code=400)

        publishers = body.get("publishers")
        if publishers is None or not isinstance(publishers, list):
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Field 'publishers' is required and must be an array"
            }, status_code=400)

        try:
            result = await work_service.update_work_publishers(work_id, publishers)
            return JSONResponse({"success": True, **result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except ValidationError as e:
            return JSONResponse({"success": False, "error": ErrorCode.VALIDATION_ERROR, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to update publishers for work {work_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/tracks/{audioId}/artists", methods=["POST"])
    async def link_artist_endpoint(request: Request) -> Response:
        """
        Link a party as an artist on a recording.

        POST /api/tracks/{audioId}/artists
        Body: {"party_id": "...", "is_primary": true, "notes": "..."}
        """
        audio_id = request.path_params.get("audioId")
        try:
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Invalid JSON body"
            }, status_code=400)

        party_id = body.get("party_id")
        if not party_id:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": "Field 'party_id' is required"
            }, status_code=400)

        try:
            party_id = validate_uuid_path(party_id)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": f"Invalid party_id: {e}"
            }, status_code=400)

        is_primary = body.get("is_primary", True)
        notes = body.get("notes")

        try:
            from src.repositories import get_audio_repository
            repo = get_audio_repository()
            result = repo.link_artist_to_recording(
                audio_track_id=audio_id,
                party_id=party_id,
                is_primary=is_primary,
                notes=notes,
            )
            return JSONResponse({"success": True, **result}, status_code=201)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except ValidationError as e:
            return JSONResponse({"success": False, "error": ErrorCode.VALIDATION_ERROR, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to link artist to track {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


__all__ = ["register_http_api_routes", "error_response", "API_V1_PREFIX"]
