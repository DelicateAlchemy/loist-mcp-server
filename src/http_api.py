"""
HTTP REST API wrappers for MCP tools and resources.

This module provides HTTP REST endpoints that wrap existing MCP tools and resources,
enabling frontend applications to access the music library functionality via standard
HTTP requests instead of the MCP JSON-RPC protocol.

All endpoints return JSON responses and handle errors appropriately for web clients.
"""

import logging
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, AsyncGenerator

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
    convert_audio,
    ConversionError,
    ConversionTimeoutError,
    SUPPORTED_FORMATS,
    get_preset_config,
    get_mime_type,
    get_file_extension,
    validate_format,
    validate_preset,
    get_default_preset,
)
from src.storage import download_audio_file, generate_signed_url
from src.resources.audio_stream import parse_gcs_path

# Import database for track lookup
import sys
sys.path.append(str(Path(__file__).parent.parent))
from database import get_audio_metadata_by_id

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

    @mcp.custom_route("/api/tracks/{audioId}/download", methods=["GET"])
    async def download_audio(request: Request) -> Response:
        """
        Download audio file with optional format conversion.

        GET /api/tracks/{audioId}/download?format={format}&preset={preset}

        Query parameters:
        - format: Target format (mp3, wav, flac, aac, ogg) - REQUIRED
        - preset: Quality preset (format-specific, defaults to 'high')

        Returns:
        - StreamingResponse with converted audio file
        - OR RedirectResponse to signed URL if no conversion needed
        - OR JSONResponse with error details

        Args:
            request: Starlette Request object with audioId path parameter

        Returns:
            Response: Streaming audio file or redirect/error response
        """
        audio_id = request.path_params.get("audioId")

        if not audio_id:
            return JSONResponse(
                {"success": False, "message": "Audio ID is required", "error": "MISSING_AUDIO_ID"},
                status_code=400
            )

        # Validate UUID format
        try:
            uuid.UUID(audio_id)
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "Invalid audio ID format", "error": "INVALID_AUDIO_ID"},
                status_code=400
            )

        # Get format parameter (required)
        target_format = request.query_params.get("format")
        if not target_format:
            return JSONResponse(
                {
                    "success": False,
                    "message": "Format parameter is required",
                    "error": "MISSING_FORMAT",
                    "supportedFormats": list(SUPPORTED_FORMATS),
                },
                status_code=400
            )

        target_format = target_format.lower()

        # Validate format
        if not validate_format(target_format):
            return JSONResponse(
                {
                    "success": False,
                    "message": f"Unsupported format: {target_format}",
                    "error": "INVALID_FORMAT",
                    "supportedFormats": list(SUPPORTED_FORMATS),
                },
                status_code=400
            )

        # Get preset parameter (optional, defaults to format-specific high)
        preset = request.query_params.get("preset")
        if preset:
            preset = preset.lower()
            if not validate_preset(target_format, preset):
                try:
                    preset_config = get_preset_config(target_format)
                    # Get valid presets for error message
                    from src.converter.presets import FORMAT_PRESETS
                    valid_presets = list(FORMAT_PRESETS[target_format].keys())
                except Exception:
                    valid_presets = []
                
                return JSONResponse(
                    {
                        "success": False,
                        "message": f"Invalid preset '{preset}' for format '{target_format}'",
                        "error": "INVALID_PRESET",
                        "validPresets": valid_presets,
                    },
                    status_code=400
                )
        else:
            preset = get_default_preset(target_format)

        try:
            # Get track metadata from database
            metadata = get_audio_metadata_by_id(audio_id)

            if not metadata:
                return JSONResponse(
                    {"success": False, "message": f"Track not found: {audio_id}", "error": "TRACK_NOT_FOUND"},
                    status_code=404
                )

            # Get GCS audio path
            audio_gcs_path = metadata.get("audio_gcs_path")
            if not audio_gcs_path:
                return JSONResponse(
                    {"success": False, "message": "Audio file path not found", "error": "SOURCE_FILE_MISSING"},
                    status_code=500
                )

            # Get source format from path extension
            source_ext = Path(audio_gcs_path).suffix.lower().lstrip(".")
            source_format = _normalize_format(source_ext)

            # Short-circuit: if source format matches target and using default preset,
            # redirect to signed URL (no conversion needed)
            if source_format == target_format and preset == get_default_preset(target_format):
                logger.info(f"Short-circuit: redirecting to original file for {audio_id}")
                try:
                    # Parse GCS path and generate signed URL
                    bucket_name, blob_name = parse_gcs_path(audio_gcs_path)
                    signed_url = generate_signed_url(blob_name, expiration_minutes=15)
                    return RedirectResponse(url=signed_url, status_code=302)
                except Exception as e:
                    logger.warning(f"Short-circuit redirect failed, falling back to conversion: {e}")
                    # Fall through to conversion

            # Conversion is needed
            logger.info(
                f"Converting {audio_id} from {source_format} to {target_format} (preset: {preset})"
            )

            # Create temp directory for this conversion
            temp_dir = tempfile.mkdtemp(prefix="loist_download_")
            source_path = None
            output_path = None

            try:
                # Parse GCS path
                bucket_name, blob_name = parse_gcs_path(audio_gcs_path)

                # Download source file from GCS
                source_filename = f"source_{audio_id}{Path(audio_gcs_path).suffix}"
                source_path = Path(temp_dir) / source_filename

                logger.info(f"Downloading source from GCS: {blob_name}")
                download_audio_file(
                    blob_name=blob_name,
                    destination_path=source_path,
                    timeout=120,
                )

                # Prepare output path
                output_ext = get_file_extension(target_format)
                output_filename = f"converted_{audio_id}{output_ext}"
                output_path = Path(temp_dir) / output_filename

                # Convert audio
                conversion_result = convert_audio(
                    source_path=source_path,
                    output_path=output_path,
                    target_format=target_format,
                    preset_name=preset,
                    timeout_seconds=300,
                )

                if not conversion_result.success:
                    raise ConversionError(conversion_result.error_message or "Conversion failed")

                # Generate download filename from metadata
                download_filename = _generate_download_filename(metadata, target_format)

                # Get MIME type
                mime_type = get_mime_type(target_format)

                # Read converted file and prepare for streaming
                # We read the file into memory here since we need to clean up temp files
                # For very large files, we'd want a different approach
                file_size = output_path.stat().st_size

                async def file_iterator() -> AsyncGenerator[bytes, None]:
                    """Stream file contents in chunks."""
                    chunk_size = 64 * 1024  # 64KB chunks
                    with open(output_path, "rb") as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk

                # Cleanup function for temp files
                def cleanup_temp_files():
                    """Remove temporary files after response is sent."""
                    try:
                        if source_path and source_path.exists():
                            source_path.unlink()
                            logger.debug(f"Cleaned up source file: {source_path}")
                        if output_path and output_path.exists():
                            output_path.unlink()
                            logger.debug(f"Cleaned up output file: {output_path}")
                        if temp_dir and Path(temp_dir).exists():
                            Path(temp_dir).rmdir()
                            logger.debug(f"Cleaned up temp dir: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temp files: {e}")

                # Return streaming response with cleanup background task
                response = StreamingResponse(
                    file_iterator(),
                    media_type=mime_type,
                    background=BackgroundTask(cleanup_temp_files),
                )
                response.headers["Content-Disposition"] = f'attachment; filename="{download_filename}"'
                response.headers["Content-Length"] = str(file_size)
                response.headers["X-Conversion-Time"] = str(conversion_result.processing_time_seconds)

                logger.info(
                    f"Download prepared: {download_filename} "
                    f"({file_size / 1024 / 1024:.2f}MB, {conversion_result.processing_time_seconds}s)"
                )

                return response

            except Exception as e:
                # Cleanup on error
                try:
                    if source_path and source_path.exists():
                        source_path.unlink()
                    if output_path and output_path.exists():
                        output_path.unlink()
                    if temp_dir and Path(temp_dir).exists():
                        Path(temp_dir).rmdir()
                except Exception as cleanup_error:
                    logger.warning(f"Cleanup on error failed: {cleanup_error}")
                raise

        except ConversionTimeoutError as e:
            logger.error(f"Conversion timeout for {audio_id}: {e}")
            return JSONResponse(
                {"success": False, "message": "Conversion timed out", "error": "CONVERSION_TIMEOUT"},
                status_code=504
            )

        except ConversionError as e:
            logger.error(f"Conversion error for {audio_id}: {e}")
            return JSONResponse(
                {"success": False, "message": f"Conversion failed: {str(e)}", "error": "CONVERSION_FAILED"},
                status_code=500
            )

        except ResourceNotFoundError as e:
            logger.error(f"Resource not found: {e}")
            return JSONResponse(
                {"success": False, "message": str(e), "error": "TRACK_NOT_FOUND"},
                status_code=404
            )

        except Exception as e:
            logger.exception(f"Download failed for {audio_id}: {e}")
            return JSONResponse(
                {"success": False, "message": f"Download failed: {str(e)}", "error": "DOWNLOAD_FAILED"},
                status_code=500
            )


def _normalize_format(extension: str) -> str:
    """
    Normalize file extension to standard format name.
    
    Args:
        extension: File extension (without dot)
        
    Returns:
        Normalized format name
    """
    extension = extension.lower()
    format_map = {
        "mp3": "mp3",
        "wav": "wav",
        "wave": "wav",
        "flac": "flac",
        "m4a": "aac",
        "aac": "aac",
        "ogg": "ogg",
        "oga": "ogg",
        "opus": "ogg",
    }
    return format_map.get(extension, extension)


def _generate_download_filename(metadata: Dict[str, Any], target_format: str) -> str:
    """
    Generate a safe filename for download from track metadata.
    
    Args:
        metadata: Track metadata dictionary
        target_format: Target format for extension
        
    Returns:
        Safe filename string
    """
    title = metadata.get("title") or "Unknown"
    artist = metadata.get("artist") or "Unknown Artist"
    
    # Sanitize for filename use
    def sanitize(s: str) -> str:
        # Remove/replace unsafe characters
        s = re.sub(r'[<>:"/\\|?*]', '', s)
        s = s.strip('. ')
        return s[:100]  # Limit length
    
    title = sanitize(title)
    artist = sanitize(artist)
    
    extension = get_file_extension(target_format)
    
    return f"{title} - {artist}{extension}"


# Export the registration function for use in server.py
__all__ = ["register_http_api_routes"]
