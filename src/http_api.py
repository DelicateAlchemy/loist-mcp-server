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


__all__ = ["register_http_api_routes", "error_response", "API_V1_PREFIX"]
