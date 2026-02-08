"""
HTTP REST API wrappers for MCP tools and resources.

This module provides HTTP REST endpoints that wrap existing MCP tools and resources,
enabling frontend applications to access the music library functionality via standard
HTTP requests instead of the MCP JSON-RPC protocol.

All endpoints return JSON responses and handle errors appropriately for web clients.
"""

import logging
import uuid
from typing import AsyncGenerator
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import JSONResponse, StreamingResponse, RedirectResponse, Response
from starlette.requests import Request
from starlette.background import BackgroundTask

from src.exceptions import ValidationError, ResourceNotFoundError
from src.error_utils import handle_tool_error

# Import HTTP API schemas for parameter validation
from src.schemas.http_api import (
    validate_search_params,
    validate_uuid_path,
    validate_download_params,
    ErrorCode,
)

# Import the MCP tools and resources we'll be wrapping
from src.services import audio_service
from src.services import streaming_service

# Import converter and storage modules for download endpoint
from src.converter import (
    ConversionError,
    ConversionTimeoutError,
    SUPPORTED_FORMATS,
    validate_format,
    validate_preset,
    get_default_preset,
)
from src.services import download_service

logger = logging.getLogger(__name__)


def register_http_api_routes(mcp: FastMCP) -> None:
    """
    Register all HTTP API routes with the FastMCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.custom_route("/api/tracks/{audioId}", methods=["GET"])
    async def get_track(request: Request) -> Response:
        """
        Get metadata for a specific audio track.
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
            import hashlib
            etag = hashlib.md5(response.body).hexdigest()
            response.headers["ETag"] = f'"{etag}"'
            
            # Cache for 1 hour, but require re-validation
            response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"

            # Check for If-None-Match header from client
            if request.headers.get("if-none-match") == f'"{etag}"':
                return Response(status_code=304)

            return response

        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Unexpected error getting track {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/search", methods=["GET"])
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
            # Handle validation errors with consistent error response format
            return JSONResponse({
                "success": False,
                "error": ErrorCode.INVALID_QUERY,
                "message": str(e)
            }, status_code=400)

        except Exception as e:
            logger.exception(f"Search failed for query '{request.query_params.get('q', 'unknown')}': {e}")
            return JSONResponse({
                "success": False,
                "error": ErrorCode.SEARCH_FAILED,
                "message": "An internal error occurred during search."
            }, status_code=500)


    @mcp.custom_route("/api/tracks/{audioId}/stream", methods=["GET"])
    async def get_track_stream(request: Request) -> Response:
        """
        Get signed streaming URL for an audio track.
        Redirects the client to a signed GCS URL for efficient streaming.
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
            details = await streaming_service.get_audio_stream_details(audio_id)
            # Redirect to the signed URL. The client's browser/player will handle the stream.
            # GCS correctly handles HTTP Range requests on signed URLs.
            return RedirectResponse(url=details["signed_url"], status_code=302)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get stream URL for {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/tracks/{audioId}/thumbnail", methods=["GET"])
    async def get_track_thumbnail(request: Request) -> Response:
        """
        Get signed URL for track thumbnail/artwork.
        Redirects the client to a signed GCS URL.
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
            details = await streaming_service.get_thumbnail_details(audio_id)
            return RedirectResponse(url=details["signed_url"], status_code=302)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get thumbnail URL for {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


    @mcp.custom_route("/api/tracks/{audioId}/download", methods=["GET"])
    async def download_audio(request: Request) -> Response:
        """
        Download audio file with optional format conversion. Refactored to use download_service.
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

        target_format = request.query_params.get("format")
        preset = request.query_params.get("preset")

        try:
            target_format, preset = validate_download_params(target_format, preset)
            # Apply default preset if not provided
            if preset is None:
                preset = get_default_preset(target_format)
        except ValidationError as e:
            return JSONResponse({
                "success": False,
                "error": ErrorCode.VALIDATION_ERROR,
                "message": str(e)
            }, status_code=400)

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
            return JSONResponse({"success": False, "message": "Unknown service action"}, status_code=500)

        except (ConversionTimeoutError, ConversionError, ResourceNotFoundError) as e:
            error_map = {
                ConversionTimeoutError: (504, "CONVERSION_TIMEOUT", "Conversion timed out"),
                ConversionError: (500, "CONVERSION_FAILED", f"Conversion failed: {e}"),
                ResourceNotFoundError: (404, "TRACK_NOT_FOUND", str(e)),
            }
            status, code, msg = error_map.get(type(e), (500, "DOWNLOAD_FAILED", str(e)))
            logger.error(f"Download failed for {audio_id}: {msg}")
            return JSONResponse({"success": False, "message": msg, "error": code}, status_code=status)
        except Exception as e:
            logger.exception(f"Unexpected download failure for {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Unexpected download error"}, status_code=500)


    @mcp.custom_route("/api/tracks/{audioId}", methods=["DELETE"])
    async def delete_track(request: Request) -> Response:
        """
        Delete a track via HTTP API.
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
            await audio_service.delete_audio_track_and_files(audio_id)
            return Response(status_code=204)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to delete track {audio_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    # ========================================================================
    # Album HTTP API Routes
    # ========================================================================

    @mcp.custom_route("/api/albums", methods=["POST"])
    async def create_album_route(request: Request) -> Response:
        """Create a new album."""
        from src.services import album_service

        try:
            body = await request.json()
            result = await album_service.create_album(body)
            return JSONResponse({"success": True, "album": result}, status_code=201)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to create album: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums", methods=["GET"])
    async def search_albums_route(request: Request) -> Response:
        """Search/list albums."""
        from src.services import album_service

        try:
            query = request.query_params.get("q", "")
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
            status = request.query_params.get("status")

            if not query:
                return JSONResponse(
                    {"success": False, "message": "Query parameter 'q' is required"},
                    status_code=400,
                )

            result = await album_service.search_albums(
                query, limit=limit, offset=offset, status=status
            )
            return JSONResponse({"success": True, **result})
        except ValueError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Album search failed: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}", methods=["GET"])
    async def get_album_route(request: Request) -> Response:
        """Get album with tracks."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        try:
            album_id = validate_uuid_path(album_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            result = await album_service.get_album(album_id)
            return JSONResponse({"success": True, "album": result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get album {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}", methods=["PUT"])
    async def update_album_route(request: Request) -> Response:
        """Update album metadata."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        try:
            album_id = validate_uuid_path(album_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            result = await album_service.update_album(album_id, body)
            return JSONResponse({"success": True, "album": result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to update album {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}", methods=["DELETE"])
    async def delete_album_route(request: Request) -> Response:
        """Delete an album."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        try:
            album_id = validate_uuid_path(album_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            await album_service.delete_album(album_id)
            return Response(status_code=204)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to delete album {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}/tracks", methods=["POST"])
    async def add_album_track_route(request: Request) -> Response:
        """Add a track to an album."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        try:
            album_id = validate_uuid_path(album_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            audio_track_id = body.get("audio_track_id")
            if not audio_track_id:
                return JSONResponse(
                    {"success": False, "message": "audio_track_id is required"},
                    status_code=400,
                )
            position = body.get("position")
            disc_number = body.get("disc_number", 1)
            result = await album_service.add_track_to_album(
                album_id, audio_track_id, position, disc_number
            )
            return JSONResponse({"success": True, "track": result}, status_code=201)
        except Exception as e:
            logger.exception(f"Failed to add track to album {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}/tracks/{audioId}", methods=["DELETE"])
    async def remove_album_track_route(request: Request) -> Response:
        """Remove a track from an album."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        audio_id = request.path_params.get("audioId")
        try:
            album_id = validate_uuid_path(album_id)
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            await album_service.remove_track_from_album(album_id, audio_id)
            return Response(status_code=204)
        except Exception as e:
            logger.exception(f"Failed to remove track from album {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/albums/{albumId}/tracks/order", methods=["PUT"])
    async def reorder_album_tracks_route(request: Request) -> Response:
        """Reorder tracks in an album."""
        from src.services import album_service

        album_id = request.path_params.get("albumId")
        try:
            album_id = validate_uuid_path(album_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            track_order = body.get("track_order", [])
            if not track_order:
                return JSONResponse(
                    {"success": False, "message": "track_order is required"},
                    status_code=400,
                )
            result = await album_service.reorder_album_tracks(album_id, track_order)
            return JSONResponse({"success": True, **result})
        except Exception as e:
            logger.exception(f"Failed to reorder album tracks {album_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    # ========================================================================
    # Playlist HTTP API Routes
    # ========================================================================

    @mcp.custom_route("/api/playlists", methods=["POST"])
    async def create_playlist_route(request: Request) -> Response:
        """Create a new playlist."""
        from src.services import playlist_service

        try:
            body = await request.json()
            result = await playlist_service.create_playlist(body)
            return JSONResponse({"success": True, "playlist": result}, status_code=201)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to create playlist: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists", methods=["GET"])
    async def search_playlists_route(request: Request) -> Response:
        """Search/list playlists."""
        from src.services import playlist_service

        try:
            query = request.query_params.get("q", "")
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))

            if not query:
                return JSONResponse(
                    {"success": False, "message": "Query parameter 'q' is required"},
                    status_code=400,
                )

            result = await playlist_service.search_playlists(
                query, limit=limit, offset=offset
            )
            return JSONResponse({"success": True, **result})
        except ValueError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Playlist search failed: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}", methods=["GET"])
    async def get_playlist_route(request: Request) -> Response:
        """Get playlist with tracks and collaborators."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            result = await playlist_service.get_playlist(playlist_id)
            return JSONResponse({"success": True, "playlist": result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to get playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}", methods=["PUT"])
    async def update_playlist_route(request: Request) -> Response:
        """Update playlist metadata."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            result = await playlist_service.update_playlist(playlist_id, body)
            return JSONResponse({"success": True, "playlist": result})
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)
        except Exception as e:
            logger.exception(f"Failed to update playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}", methods=["DELETE"])
    async def delete_playlist_route(request: Request) -> Response:
        """Delete a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            await playlist_service.delete_playlist(playlist_id)
            return Response(status_code=204)
        except ResourceNotFoundError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=404)
        except Exception as e:
            logger.exception(f"Failed to delete playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}/tracks", methods=["POST"])
    async def add_playlist_track_route(request: Request) -> Response:
        """Add a track to a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            audio_track_id = body.get("audio_track_id")
            if not audio_track_id:
                return JSONResponse(
                    {"success": False, "message": "audio_track_id is required"},
                    status_code=400,
                )
            position = body.get("position")
            added_by = body.get("added_by")
            result = await playlist_service.add_track_to_playlist(
                playlist_id, audio_track_id, position, added_by
            )
            return JSONResponse({"success": True, "track": result}, status_code=201)
        except Exception as e:
            logger.exception(f"Failed to add track to playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}/tracks/{audioId}", methods=["DELETE"])
    async def remove_playlist_track_route(request: Request) -> Response:
        """Remove a track from a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        audio_id = request.path_params.get("audioId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
            audio_id = validate_uuid_path(audio_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            await playlist_service.remove_track_from_playlist(playlist_id, audio_id)
            return Response(status_code=204)
        except Exception as e:
            logger.exception(f"Failed to remove track from playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}/tracks/order", methods=["PUT"])
    async def reorder_playlist_tracks_route(request: Request) -> Response:
        """Reorder tracks in a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            track_order = body.get("track_order", [])
            if not track_order:
                return JSONResponse(
                    {"success": False, "message": "track_order is required"},
                    status_code=400,
                )
            result = await playlist_service.reorder_playlist_tracks(playlist_id, track_order)
            return JSONResponse({"success": True, **result})
        except Exception as e:
            logger.exception(f"Failed to reorder playlist tracks {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}/collaborators", methods=["POST"])
    async def add_playlist_collaborator_route(request: Request) -> Response:
        """Add a collaborator to a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            body = await request.json()
            user_id = body.get("user_id")
            if not user_id:
                return JSONResponse(
                    {"success": False, "message": "user_id is required"},
                    status_code=400,
                )
            role = body.get("role", "viewer")
            result = await playlist_service.add_collaborator(playlist_id, user_id, role)
            return JSONResponse({"success": True, "collaborator": result}, status_code=201)
        except Exception as e:
            logger.exception(f"Failed to add collaborator to playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/playlists/{playlistId}/collaborators/{userId}", methods=["DELETE"])
    async def remove_playlist_collaborator_route(request: Request) -> Response:
        """Remove a collaborator from a playlist."""
        from src.services import playlist_service

        playlist_id = request.path_params.get("playlistId")
        user_id = request.path_params.get("userId")
        try:
            playlist_id = validate_uuid_path(playlist_id)
            user_id = validate_uuid_path(user_id)
        except ValidationError as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=400)

        try:
            await playlist_service.remove_collaborator(playlist_id, user_id)
            return Response(status_code=204)
        except Exception as e:
            logger.exception(f"Failed to remove collaborator from playlist {playlist_id}: {e}")
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


__all__ = ["register_http_api_routes"]