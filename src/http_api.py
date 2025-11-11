"""
HTTP REST API wrappers for MCP tools and resources.

This module provides HTTP REST endpoints that wrap existing MCP tools and resources,
enabling frontend applications to access the music library functionality via standard
HTTP requests instead of the MCP JSON-RPC protocol.

All endpoints return JSON responses and handle errors appropriately for web clients.
"""

import logging
from typing import Optional, Dict, Any
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request

from src.exceptions import ValidationError, ResourceNotFoundError
from src.error_utils import handle_tool_error

# Import the MCP tools and resources we'll be wrapping
from src.tools.query_tools import get_audio_metadata as get_metadata_func
from src.tools.query_tools import search_library as search_func
from src.resources.audio_stream import get_audio_stream_resource
from src.resources.thumbnail import get_thumbnail_resource

logger = logging.getLogger(__name__)


def register_http_api_routes(mcp: FastMCP) -> None:
    """
    Register all HTTP API routes with the FastMCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.custom_route("/api/tracks/{audioId}", methods=["GET"])
    async def get_track(request: Request) -> JSONResponse:
        """
        Get metadata for a specific audio track.

        GET /api/tracks/{audioId}

        Returns JSON metadata for the specified track, or 404 if not found.

        Args:
            request: Starlette Request object with audioId path parameter

        Returns:
            JSONResponse: Track metadata or error response
        """
        audio_id = request.path_params.get("audioId")

        if not audio_id:
            return JSONResponse(
                {"success": False, "message": "Audio ID is required", "error": "MISSING_AUDIO_ID"},
                status_code=400
            )

        try:
            # Call the existing MCP tool function
            result = await get_metadata_func({"audioId": audio_id})

            if not result.get("success", False):
                # Tool returned an error - convert to appropriate HTTP status
                error_msg = result.get("message", "Track not found")
                status_code = 404 if "not found" in error_msg.lower() else 500

                return JSONResponse(
                    {
                        "success": False,
                        "message": error_msg,
                        "error": result.get("error", "UNKNOWN_ERROR")
                    },
                    status_code=status_code
                )

            # Return successful response
            return JSONResponse(result, status_code=200)

        except ValidationError as e:
            logger.warning(f"Invalid audio ID format: {audio_id}")
            return JSONResponse(
                {"success": False, "message": "Invalid audio ID format", "error": "INVALID_AUDIO_ID"},
                status_code=400
            )
        except Exception as e:
            error_response = handle_tool_error(e, "get_audio_metadata")
            logger.error(f"Get audio metadata failed for {audio_id}: {error_response}")
            return JSONResponse(error_response, status_code=500)

    @mcp.custom_route("/api/search", methods=["GET"])
    async def search_tracks(request: Request) -> JSONResponse:
        """
        Search for audio tracks.

        GET /api/search?q=<query>&genre=<genre>&limit=<limit>&offset=<offset>&sortBy=<field>&sortOrder=<asc|desc>

        Required query params:
        - q: Search query string

        Optional query params:
        - genre: Filter by genre
        - limit: Maximum results (default: 20, max: 100)
        - offset: Results offset (default: 0)
        - sortBy: Sort field (default: relevance)
        - sortOrder: Sort order (default: desc)

        Returns JSON search results with pagination.
        """
        try:
            # Extract query parameters
            query = request.query_params.get("q")
            if not query or not query.strip():
                return JSONResponse(
                    {"success": False, "message": "Search query (q) is required", "error": "MISSING_QUERY"},
                    status_code=400
                )

            genre = request.query_params.get("genre")
            limit_str = request.query_params.get("limit", "20")
            offset_str = request.query_params.get("offset", "0")
            sort_by = request.query_params.get("sortBy", "relevance")
            sort_order = request.query_params.get("sortOrder", "desc")

            # Validate and convert parameters
            try:
                limit = int(limit_str)
                if limit < 1 or limit > 100:
                    limit = 20
            except ValueError:
                limit = 20

            try:
                offset = int(offset_str)
                if offset < 0:
                    offset = 0
            except ValueError:
                offset = 0

            # Build filters
            filters = {}
            if genre and genre.strip():
                filters["genre"] = [genre.strip()]

            # Build input data for the MCP tool
            input_data = {
                "query": query.strip(),
                "filters": filters if filters else None,
                "limit": limit,
                "offset": offset,
                "sortBy": sort_by,
                "sortOrder": sort_order,
            }

            # Call the existing MCP tool function
            result = await search_func(input_data)

            if not result.get("success", False):
                error_msg = result.get("message", "Search failed")
                return JSONResponse(
                    {
                        "success": False,
                        "message": error_msg,
                        "error": result.get("error", "SEARCH_FAILED")
                    },
                    status_code=500
                )

            # Return successful response
            return JSONResponse(result, status_code=200)

        except Exception as e:
            error_response = handle_tool_error(e, "search_library")
            logger.error(f"Search library failed for query '{query}': {error_response}")
            return JSONResponse(error_response, status_code=500)

    @mcp.custom_route("/api/tracks/{audioId}/stream", methods=["GET"])
    async def get_track_stream(request: Request) -> JSONResponse:
        """
        Get signed streaming URL for an audio track.

        GET /api/tracks/{audioId}/stream

        Returns JSON with signed GCS URL for audio streaming, or 404 if not found.

        Args:
            request: Starlette Request object with audioId path parameter

        Returns:
            JSONResponse: Stream URL or error response
        """
        audio_id = request.path_params.get("audioId")

        if not audio_id:
            return JSONResponse(
                {"success": False, "message": "Audio ID is required", "error": "MISSING_AUDIO_ID"},
                status_code=400
            )

        try:
            # Call the existing MCP resource function
            uri = f"music-library://audio/{audio_id}/stream"
            result = await get_audio_stream_resource(uri)

            if not result.get("success", False):
                error_msg = result.get("message", "Stream not available")
                status_code = 404 if "not found" in error_msg.lower() else 500

                return JSONResponse(
                    {
                        "success": False,
                        "message": error_msg,
                        "error": result.get("error", "STREAM_UNAVAILABLE")
                    },
                    status_code=status_code
                )

            # Return successful response
            return JSONResponse(result, status_code=200)

        except ValidationError as e:
            logger.warning(f"Invalid audio ID format: {audio_id}")
            return JSONResponse(
                {"success": False, "message": "Invalid audio ID format", "error": "INVALID_AUDIO_ID"},
                status_code=400
            )
        except Exception as e:
            error_response = handle_tool_error(e, "get_audio_stream")
            logger.error(f"Get audio stream failed for {audio_id}: {error_response}")
            return JSONResponse(error_response, status_code=500)

    @mcp.custom_route("/api/tracks/{audioId}/thumbnail", methods=["GET"])
    async def get_track_thumbnail(request: Request) -> JSONResponse:
        """
        Get signed URL for track thumbnail/artwork.

        GET /api/tracks/{audioId}/thumbnail

        Returns JSON with signed GCS URL for thumbnail, or 404 if not found.
        Handles missing thumbnails gracefully by returning success=false.

        Args:
            request: Starlette Request object with audioId path parameter

        Returns:
            JSONResponse: Thumbnail URL or error response
        """
        audio_id = request.path_params.get("audioId")

        if not audio_id:
            return JSONResponse(
                {"success": False, "message": "Audio ID is required", "error": "MISSING_AUDIO_ID"},
                status_code=400
            )

        try:
            # Call the existing MCP resource function
            uri = f"music-library://audio/{audio_id}/thumbnail"
            result = await get_thumbnail_resource(uri)

            if not result.get("success", False):
                error_msg = result.get("message", "Thumbnail not available")
                # Check if this is a "not found" error vs other errors
                if "not found" in error_msg.lower():
                    status_code = 404
                elif "no artwork" in error_msg.lower() or "no thumbnail" in error_msg.lower():
                    # Missing artwork is not an error - return success=false gracefully
                    return JSONResponse(
                        {
                            "success": False,
                            "message": "No thumbnail available for this track",
                            "error": "NO_THUMBNAIL"
                        },
                        status_code=200  # 200 OK with success=false
                    )
                else:
                    status_code = 500

                return JSONResponse(
                    {
                        "success": False,
                        "message": error_msg,
                        "error": result.get("error", "THUMBNAIL_UNAVAILABLE")
                    },
                    status_code=status_code
                )

            # Return successful response
            return JSONResponse(result, status_code=200)

        except ValidationError as e:
            logger.warning(f"Invalid audio ID format: {audio_id}")
            return JSONResponse(
                {"success": False, "message": "Invalid audio ID format", "error": "INVALID_AUDIO_ID"},
                status_code=400
            )
        except Exception as e:
            error_response = handle_tool_error(e, "get_thumbnail")
            logger.error(f"Get thumbnail failed for {audio_id}: {error_response}")
            return JSONResponse(error_response, status_code=500)


# Export the registration function for use in server.py
__all__ = ["register_http_api_routes"]
