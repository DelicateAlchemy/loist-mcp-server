"""
Music Library MCP Server
FastMCP-based server for audio ingestion and embedding
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path
from fastmcp import FastMCP
from starlette.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from config import config
from auth import SimpleBearerAuth

# Configure logging
config.configure_logging()
logger = logging.getLogger(__name__)

# Configure Jinja2 templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@asynccontextmanager
async def lifespan(app):
    """
    Server lifespan management - handles startup and shutdown
    """
    # Startup
    logger.info(f"🚀 Starting {config.server_name} v{config.server_version}")
    logger.info(f"📡 Transport: {config.server_transport}")
    logger.info(f"🔧 Log Level: {config.log_level}")
    logger.info(f"🔐 Authentication: {'enabled' if config.auth_enabled else 'disabled'}")
    logger.info(f"✅ Health check enabled: {config.enable_healthcheck}")
    
    yield
    
    # Shutdown
    logger.info(f"🛑 Shutting down {config.server_name}")


# Initialize authentication if enabled
auth: Optional[SimpleBearerAuth] = None
if config.auth_enabled and config.bearer_token:
    auth = SimpleBearerAuth(token=config.bearer_token, enabled=True)
    logger.info("🔒 Bearer token authentication configured")
elif config.auth_enabled:
    logger.warning("⚠️  Authentication enabled but no bearer token configured!")
else:
    logger.info("🔓 Running without authentication (development mode)")


# Initialize FastMCP server with advanced configuration
mcp = FastMCP(
    name=config.server_name,
    instructions=config.server_instructions,
    lifespan=lifespan,
    auth=auth,
    on_duplicate_tools=config.on_duplicate_tools,
    on_duplicate_resources=config.on_duplicate_resources,
    on_duplicate_prompts=config.on_duplicate_prompts,
    include_fastmcp_meta=config.include_fastmcp_meta
)


@mcp.tool()
def health_check() -> dict:
    """
    Health check endpoint to verify server is running
    
    Returns:
        dict: Server status information including version and configuration
        
    Raises:
        Exception: If health check fails (demonstrates error handling)
    """
    from exceptions import MusicLibraryError
    from error_utils import handle_tool_error
    
    try:
        logger.debug("Health check requested")
        
        # Verify server is operational
        response = {
            "status": "healthy",
            "service": config.server_name,
            "version": config.server_version,
            "transport": config.server_transport,
            "log_level": config.log_level,
            "authentication": "enabled" if config.auth_enabled else "disabled"
        }
        
        logger.info("Health check passed")
        return response
        
    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "health_check")
        logger.error(f"Health check failed: {error_response}")
        return error_response


# ============================================================================
# Task 7: Audio Processing Tool
# ============================================================================

@mcp.tool()
async def process_audio_complete(
    source: dict,
    options: dict = None
) -> dict:
    """
    Process audio from HTTP URL and return complete metadata.
    
    This tool orchestrates the complete audio processing pipeline:
    1. Download audio from HTTP/HTTPS URL
    2. Extract metadata (artist, title, album, etc.) and artwork
    3. Upload to Google Cloud Storage
    4. Save metadata to PostgreSQL database
    5. Return complete metadata and resource URIs
    
    Args:
        source: Audio source specification
            - type: Source type ("http_url")
            - url: HTTP/HTTPS URL to audio file
            - headers: Optional HTTP headers (e.g., authentication)
            - filename: Optional filename override
            - mimeType: Optional MIME type
        options: Processing options (optional)
            - maxSizeMB: Maximum file size in MB (default: 100)
            - timeout: Download timeout in seconds (default: 300)
            - validateFormat: Whether to validate audio format (default: true)
    
    Returns:
        dict: Success response with audioId, metadata, and resource URIs, or error response
        
    Example:
        >>> result = await process_audio_complete(
        ...     source={"type": "http_url", "url": "https://example.com/song.mp3"},
        ...     options={"maxSizeMB": 100}
        ... )
        >>> print(result["audioId"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    from tools import process_audio_complete as process_audio_func
    
    # Build input data
    input_data = {
        "source": source,
        "options": options or {}
    }
    
    # Call the async processing function
    return await process_audio_func(input_data)


# ============================================================================
# Task 8: Query/Retrieval Tools
# ============================================================================

@mcp.tool()
async def get_audio_metadata(audioId: str) -> dict:
    """
    Retrieve metadata for a previously processed audio track.
    
    This tool fetches complete metadata for an audio track that has been
    previously processed and stored in the system.
    
    Args:
        audioId: UUID of the audio track to retrieve
        
    Returns:
        dict: Success response with complete metadata and resource URIs,
              or error response if track not found
        
    Example:
        >>> result = await get_audio_metadata(audioId="550e8400-e29b-41d4-a716-446655440000")
        >>> print(result["metadata"]["Product"]["Title"])
        "Hey Jude"
    """
    from tools.query_tools import get_audio_metadata as get_metadata_func
    
    # Call the async function
    return await get_metadata_func({"audioId": audioId})


@mcp.tool()
async def search_library(
    query: str,
    filters: dict = None,
    limit: int = 20,
    offset: int = 0,
    sortBy: str = "relevance",
    sortOrder: str = "desc"
) -> dict:
    """
    Search across all processed audio in the library.
    
    Performs full-text search across audio metadata (title, artist, album, genre)
    with optional advanced filters.
    
    Args:
        query: Search query string (1-500 characters)
        filters: Optional filters (genre, year, duration, format, artist, album)
            Example: {"genre": ["Rock"], "year": {"min": 1960, "max": 1970}}
        limit: Maximum results to return (1-100, default: 20)
        offset: Number of results to skip (default: 0, max: 10000)
        sortBy: Field to sort by (relevance, title, artist, year, duration, created_at)
        sortOrder: Sort order (asc or desc, default: desc)
        
    Returns:
        dict: Success response with search results, relevance scores, and pagination info,
              or error response if search fails
        
    Example:
        >>> result = await search_library(
        ...     query="beatles",
        ...     filters={"genre": ["Rock"], "year": {"min": 1960, "max": 1970}},
        ...     limit=20
        ... )
        >>> print(f"Found {result['total']} results")
        Found 150 results
    """
    from tools.query_tools import search_library as search_func
    
    # Build input data
    input_data = {
        "query": query,
        "filters": filters,
        "limit": limit,
        "offset": offset,
        "sortBy": sortBy,
        "sortOrder": sortOrder
    }
    
    # Call the async function
    return await search_func(input_data)


# ============================================================================
# Task 9: MCP Resources
# ============================================================================

@mcp.resource("music-library://audio/{audioId}/stream")
async def audio_stream_resource(uri: str) -> str:
    """
    MCP resource for streaming audio files.
    
    Returns a signed GCS URL for secure audio streaming with support for:
    - HTTP Range requests (seeking)
    - Proper Content-Type headers
    - Caching for performance
    
    URI Format: music-library://audio/{audioId}/stream
    
    Args:
        uri: Resource URI containing audioId
        
    Returns:
        str: MCP resource response with signed streaming URL
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream
        Returns: Signed GCS URL for audio file
    """
    from resources.audio_stream import get_audio_stream_resource
    return await get_audio_stream_resource(uri)


@mcp.resource("music-library://audio/{audioId}/metadata")
async def metadata_resource(uri: str) -> str:
    """
    MCP resource for audio metadata.
    
    Returns complete metadata as JSON including Product and Format information.
    
    URI Format: music-library://audio/{audioId}/metadata
    
    Args:
        uri: Resource URI containing audioId
        
    Returns:
        str: MCP resource response with JSON metadata
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata
        Returns: JSON with complete track metadata
    """
    from resources.metadata import get_metadata_resource
    return await get_metadata_resource(uri)


@mcp.resource("music-library://audio/{audioId}/thumbnail")
async def thumbnail_resource(uri: str) -> str:
    """
    MCP resource for audio thumbnails/artwork.
    
    Returns a signed GCS URL for thumbnail image with caching.
    
    URI Format: music-library://audio/{audioId}/thumbnail
    
    Args:
        uri: Resource URI containing audioId
        
    Returns:
        str: MCP resource response with signed image URL
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail
        Returns: Signed GCS URL for thumbnail image
    """
    from resources.thumbnail import get_thumbnail_resource
    return await get_thumbnail_resource(uri)


# ============================================================================
# Task 10: HTML5 Audio Player Embed Page
# ============================================================================

@mcp.get("/embed/{audioId}")
async def embed_page(audioId: str):
    """
    Serve HTML5 audio player embed page.
    
    This route provides a standalone audio player page that can be embedded
    in iframes or accessed directly. It includes:
    - Custom audio player UI
    - Metadata display
    - Open Graph and Twitter Card tags
    - oEmbed discovery
    - Keyboard shortcuts
    - Responsive design
    
    Args:
        audioId: UUID of the audio track
        
    Returns:
        HTMLResponse: Rendered HTML page with audio player
        
    Example:
        GET /embed/550e8400-e29b-41d4-a716-446655440000
        Returns: HTML page with embedded audio player
    """
    from starlette.requests import Request
    from database import get_audio_metadata_by_id
    from resources.cache import get_cache
    
    logger.info(f"Embed page requested for audio ID: {audioId}")
    
    try:
        # Get metadata from database
        metadata = get_audio_metadata_by_id(audioId)
        
        if not metadata:
            logger.warning(f"Audio track not found: {audioId}")
            return HTMLResponse(
                content="<h1>Audio Not Found</h1><p>The requested audio track could not be found.</p>",
                status_code=404
            )
        
        # Get GCS paths
        audio_path = metadata.get("audio_path")
        thumbnail_path = metadata.get("thumbnail_path")
        
        if not audio_path:
            logger.error(f"No audio path for {audioId}")
            return HTMLResponse(
                content="<h1>Error</h1><p>Audio file not available.</p>",
                status_code=500
            )
        
        # Generate signed URLs using cache
        cache = get_cache()
        
        try:
            stream_url = cache.get(audio_path, url_expiration_minutes=15)
        except Exception as e:
            logger.error(f"Failed to generate signed URL for audio: {e}")
            return HTMLResponse(
                content="<h1>Error</h1><p>Failed to generate audio stream.</p>",
                status_code=500
            )
        
        # Generate thumbnail URL if available
        thumbnail_url = None
        if thumbnail_path:
            try:
                thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
            except Exception as e:
                logger.warning(f"Failed to generate signed URL for thumbnail: {e}")
                # Continue without thumbnail
        
        # Format metadata for template
        template_metadata = {
            "Product": {
                "Title": metadata.get("title", "Untitled"),
                "Artist": metadata.get("artist", "Unknown Artist"),
                "Album": metadata.get("album"),
                "Year": metadata.get("year"),
            },
            "Format": {
                "Duration": metadata.get("duration", 0.0),
                "Channels": metadata.get("channels", 2),
                "SampleRate": metadata.get("sample_rate", 44100),
                "Bitrate": metadata.get("bitrate", 0),
                "Format": metadata.get("format", "MP3"),
            }
        }
        
        # Format duration for display
        duration_seconds = metadata.get("duration", 0)
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        duration_formatted = f"{minutes}:{seconds:02d}"
        
        # Determine MIME type
        audio_format = metadata.get("format", "MP3").upper()
        mime_types = {
            "MP3": "audio/mpeg",
            "FLAC": "audio/flac",
            "M4A": "audio/mp4",
            "OGG": "audio/ogg",
            "WAV": "audio/wav",
            "AAC": "audio/aac",
        }
        mime_type = mime_types.get(audio_format, "audio/mpeg")
        
        logger.info(f"Rendering embed page for: {template_metadata['Product']['Title']}")
        
        # Render template
        # Create a mock request object for Jinja2Templates
        from starlette.requests import Request
        from starlette.datastructures import Headers, URL
        
        # Create minimal request object
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        
        response = templates.TemplateResponse("embed.html", {
            "request": request,
            "audio_id": audioId,
            "metadata": template_metadata,
            "stream_url": stream_url,
            "thumbnail_url": thumbnail_url,
            "mime_type": mime_type,
            "duration_formatted": duration_formatted
        })
        
        # Add security headers for iframe embedding
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = "frame-ancestors *"
        
        return response
        
    except Exception as e:
        logger.exception(f"Error rendering embed page: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>An unexpected error occurred: {str(e)}</p>",
            status_code=500
        )


def create_http_app():
    """
    Create HTTP application with CORS middleware for iframe embedding
    Only used when transport is HTTP or SSE
    """
    from starlette.middleware.cors import CORSMiddleware
    
    if not config.enable_cors:
        logger.info("CORS disabled, returning plain MCP app")
        return None
    
    # Get the FastMCP HTTP app
    mcp_app = mcp.http_app(path='/mcp')
    
    # Add CORS middleware
    mcp_app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins_list,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods_list,
        allow_headers=config.cors_allow_headers_list,
        expose_headers=config.cors_expose_headers_list,
    )
    
    logger.info(f"🌐 CORS enabled for origins: {config.cors_origins_list}")
    return mcp_app


if __name__ == "__main__":
    # Run the FastMCP server
    # CORS is automatically applied when using HTTP/SSE transport
    mcp.run()
