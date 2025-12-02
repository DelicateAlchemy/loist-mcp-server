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

# Import the MCP tools and resources we'll be wrapping
from src.tools.query_tools import get_audio_metadata as get_metadata_func
from src.tools.query_tools import search_library as search_func
from src.resources.audio_stream import get_audio_stream_resource
from src.resources.thumbnail import get_thumbnail_resource

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
    async def get_track(request: Request) -> JSONResponse:
        """
        Get metadata for a specific audio track.
        """
        audio_id = request.path_params.get("audioId")
        if not audio_id:
            return JSONResponse({"success": False, "message": "Audio ID is required"}, status_code=400)
        try:
            result = await get_metadata_func({"audio_id": audio_id})
            if not result.get("success", False):
                status_code = 404 if "not found" in result.get("message", "").lower() else 500
                return JSONResponse(result, status_code=status_code)
            return JSONResponse(result, status_code=200)
        except Exception as e:
            return JSONResponse(handle_tool_error(e, "get_audio_metadata"), status_code=500)

    @mcp.custom_route("/api/search", methods=["GET"])
    async def search_tracks(request: Request) -> JSONResponse:
        """
        Search for audio tracks.
        """
        query = request.query_params.get("q")
        if not query or not query.strip():
            return JSONResponse({"success": False, "message": "Search query (q) is required"}, status_code=400)
        try:
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
            input_data = {
                "query": query.strip(),
                "filters": {"genre": [request.query_params.get("genre")]} if request.query_params.get("genre") else None,
                "limit": max(1, min(limit, 100)),
                "offset": max(0, offset),
                "sortBy": request.query_params.get("sortBy", "relevance"),
                "sortOrder": request.query_params.get("sortOrder", "desc"),
            }
            result = await search_func(input_data)
            if not result.get("success", False):
                return JSONResponse(result, status_code=500)
            return JSONResponse(result, status_code=200)
        except Exception as e:
            return JSONResponse(handle_tool_error(e, "search_library"), status_code=500)

    @mcp.custom_route("/api/tracks/{audioId}/stream", methods=["GET"])
    async def get_track_stream(request: Request) -> JSONResponse:
        """
        Get signed streaming URL for an audio track.
        """
        audio_id = request.path_params.get("audioId")
        if not audio_id:
            return JSONResponse({"success": False, "message": "Audio ID is required"}, status_code=400)
        try:
            uri = f"music-library://audio/{audio_id}/stream"
            result = await get_audio_stream_resource(uri)
            # This logic is flawed and will be fixed in the next refactoring phase
            if not result.get("uri"):
                 return JSONResponse({"success": False, "message": "Stream not available"}, status_code=404)
            return JSONResponse({"success": True, "url": result["uri"], "mimeType": result["mimeType"]}, status_code=200)
        except Exception as e:
            return JSONResponse(handle_tool_error(e, "get_audio_stream"), status_code=500)

    @mcp.custom_route("/api/tracks/{audioId}/thumbnail", methods=["GET"])
    async def get_track_thumbnail(request: Request) -> JSONResponse:
        """
        Get signed URL for track thumbnail/artwork.
        """
        audio_id = request.path_params.get("audioId")
        if not audio_id:
            return JSONResponse({"success": False, "message": "Audio ID is required"}, status_code=400)
        try:
            uri = f"music-library://audio/{audio_id}/thumbnail"
            result = await get_thumbnail_resource(uri)
            # This logic is flawed and will be fixed in the next refactoring phase
            if not result.get("uri"):
                 return JSONResponse({"success": False, "message": "Thumbnail not available"}, status_code=404)
            return JSONResponse({"success": True, "url": result["uri"], "mimeType": result["mimeType"]}, status_code=200)
        except Exception as e:
            return JSONResponse(handle_tool_error(e, "get_thumbnail"), status_code=500)

    @mcp.custom_route("/api/tracks/{audioId}/download", methods=["GET"])
    async def download_audio(request: Request) -> Response:
        """
        Download audio file with optional format conversion. Refactored to use download_service.
        """
        audio_id = request.path_params.get("audioId")
        try:
            uuid.UUID(audio_id)
        except (ValueError, AttributeError):
            return JSONResponse({"success": False, "message": "Invalid audio ID format"}, status_code=400)

        target_format = request.query_params.get("format")
        if not target_format:
            return JSONResponse({"success": False, "message": "Format parameter is required"}, status_code=400)
        
        target_format = target_format.lower()
        if not validate_format(target_format):
            return JSONResponse({"success": False, "message": f"Unsupported format: {target_format}"}, status_code=400)

        preset = request.query_params.get("preset", get_default_preset(target_format)).lower()
        if not validate_preset(target_format, preset):
            return JSONResponse({"success": False, "message": f"Invalid preset '{preset}' for format '{target_format}'"}, status_code=400)

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


__all__ = ["register_http_api_routes"]