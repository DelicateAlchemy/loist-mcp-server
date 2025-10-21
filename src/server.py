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
from src.config import config
from src.auth import SimpleBearerAuth

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
async def audio_stream_resource(audioId: str) -> str:
    """
    MCP resource for streaming audio files.
    
    Returns a signed GCS URL for secure audio streaming with support for:
    - HTTP Range requests (seeking)
    - Proper Content-Type headers
    - Caching for performance
    
    URI Format: music-library://audio/{audioId}/stream
    
    Args:
        audioId: Audio file identifier
        
    Returns:
        str: MCP resource response with signed streaming URL
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream
        Returns: Signed GCS URL for audio file
    """
    from resources.audio_stream import get_audio_stream_resource
    return await get_audio_stream_resource(f"music-library://audio/{audioId}/stream")


@mcp.resource("music-library://audio/{audioId}/metadata")
async def metadata_resource(audioId: str) -> str:
    """
    MCP resource for audio metadata.
    
    Returns complete metadata as JSON including Product and Format information.
    
    URI Format: music-library://audio/{audioId}/metadata
    
    Args:
        audioId: Audio file identifier
        
    Returns:
        str: MCP resource response with JSON metadata
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata
        Returns: JSON with complete track metadata
    """
    from resources.metadata import get_metadata_resource
    return await get_metadata_resource(f"music-library://audio/{audioId}/metadata")


@mcp.resource("music-library://audio/{audioId}/thumbnail")
async def thumbnail_resource(audioId: str) -> str:
    """
    MCP resource for audio thumbnails/artwork.
    
    Returns a signed GCS URL for thumbnail image with caching.
    
    URI Format: music-library://audio/{audioId}/thumbnail
    
    Args:
        audioId: Audio file identifier
        
    Returns:
        str: MCP resource response with signed image URL
        
    Example:
        URI: music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail
        Returns: Signed GCS URL for thumbnail image
    """
    from resources.thumbnail import get_thumbnail_resource
    return await get_thumbnail_resource(f"music-library://audio/{audioId}/thumbnail")


# ============================================================================
# Task 11: oEmbed and Open Graph Integration
# ============================================================================

@mcp.custom_route("/oembed", methods=["GET"])
async def oembed_endpoint(request):
    """
    oEmbed endpoint for platform embedding.
    
    Provides oEmbed-compliant JSON responses for audio content embedding.
    Supports maxwidth and maxheight parameters for responsive embedding.
    
    Args:
        request: Starlette Request object with query parameters
        
    Returns:
        JSONResponse: oEmbed-compliant response or error response
        
    Example:
        GET /oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000&maxwidth=500
        Returns: oEmbed JSON response with iframe HTML
    """
    from starlette.responses import JSONResponse
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from database import get_audio_metadata_by_id
    from resources.cache import get_cache
    
    # Get URL parameter
    url = request.query_params.get('url')
    if not url or not url.startswith('https://loist.io/embed/'):
        logger.warning(f"Invalid oEmbed URL parameter: {url}")
        return JSONResponse(
            {"error": "Invalid URL parameter. URL must start with https://loist.io/embed/"},
            status_code=400
        )
    
    # Extract UUID from URL
    try:
        uuid = url.split('/')[-1]
        if not uuid or len(uuid) != 36:  # Basic UUID validation
            raise ValueError("Invalid UUID format")
    except (IndexError, ValueError) as e:
        logger.warning(f"Failed to extract UUID from URL {url}: {e}")
        return JSONResponse(
            {"error": "Invalid URL format"},
            status_code=400
        )
    
    logger.info(f"oEmbed request for audio ID: {uuid}")
    
    try:
        # Get metadata from database
        metadata = get_audio_metadata_by_id(uuid)
        
        if not metadata:
            logger.warning(f"Audio track not found for oEmbed: {uuid}")
            return JSONResponse(
                {"error": "Audio not found"},
                status_code=404
            )
        
        # Get optional width/height parameters
        max_width = request.query_params.get('maxwidth', '500')
        max_height = request.query_params.get('maxheight', '200')
        
        try:
            max_width = int(max_width)
            max_height = int(max_height)
        except ValueError:
            max_width = 500
            max_height = 200
        
        # Adjust dimensions to respect maxwidth/maxheight
        width = min(500, max_width)
        height = min(200, max_height)
        
        # Generate thumbnail URL if available
        thumbnail_url = None
        thumbnail_path = metadata.get("thumbnail_path")
        if thumbnail_path:
            try:
                cache = get_cache()
                thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
            except Exception as e:
                logger.warning(f"Failed to generate signed URL for thumbnail: {e}")
                # Continue without thumbnail
        
        # Format oEmbed response
        response = {
            "version": "1.0",
            "type": "rich",
            "title": metadata.get("title", "Untitled"),
            "author_name": metadata.get("artist", ""),
            "provider_name": "Loist Music Library",
            "provider_url": "https://loist.io",
            "html": f'<iframe src="https://loist.io/embed/{uuid}" width="{width}" height="{height}" frameborder="0" allowfullscreen></iframe>',
            "width": width,
            "height": height
        }
        
        # Add thumbnail if available
        if thumbnail_url:
            response["thumbnail_url"] = thumbnail_url
            response["thumbnail_width"] = 600
            response["thumbnail_height"] = 600
        
        logger.info(f"oEmbed response generated for: {metadata.get('title', 'Untitled')}")
        return JSONResponse(response)
        
    except Exception as e:
        logger.exception(f"Error generating oEmbed response: {e}")
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500
        )


@mcp.custom_route("/.well-known/oembed.json", methods=["GET"])
async def oembed_discovery(request):
    """
    oEmbed discovery endpoint.
    
    Provides oEmbed provider discovery information for automatic
    oEmbed client configuration.
    
    Args:
        request: Starlette Request object
        
    Returns:
        JSONResponse: oEmbed provider discovery information
        
    Example:
        GET /.well-known/oembed.json
        Returns: Provider discovery JSON
    """
    from starlette.responses import JSONResponse
    
    discovery_info = {
        "provider_name": "Loist Music Library",
        "provider_url": "https://loist.io",
        "endpoints": [
            {
                "url": "https://loist.io/oembed",
                "formats": ["json"],
                "discovery": True
            }
        ]
    }
    
    logger.info("oEmbed discovery endpoint accessed")
    return JSONResponse(discovery_info)


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request):
    """
    HTTP health check endpoint for Cloud Run probes.
    
    Provides a lightweight health check endpoint that Cloud Run can use
    for startup and liveness probes. This endpoint performs minimal checks
    to verify the application is running and ready to serve traffic.
    
    Args:
        request: Starlette Request object
        
    Returns:
        JSONResponse: Health status with HTTP status codes
        
    Example:
        GET /health
        Returns: {"status": "healthy", "service": "loist-mcp-server", ...}
    """
    from starlette.responses import JSONResponse
    
    try:
        logger.debug("Health check endpoint requested")
        
        # Perform basic health checks
        health_status = {
            "status": "healthy",
            "service": config.server_name,
            "version": config.server_version,
            "transport": config.server_transport,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        
        # Add database connectivity check if enabled (non-blocking)
        try:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent))
            from database.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    health_status["database"] = "connected"
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            health_status["database"] = "disconnected"
            # Don't degrade status for database issues in health check
        
        # Add GCS connectivity check if enabled (non-blocking)
        try:
            from storage.gcs_client import create_gcs_client
            client = create_gcs_client()
            # Simple bucket access test
            client.bucket.exists()
            health_status["storage"] = "connected"
        except Exception as e:
            logger.warning(f"Storage health check failed: {e}")
            health_status["storage"] = "disconnected"
            # Don't degrade status for storage issues in health check
        
        # Determine HTTP status code
        status_code = 200 if health_status["status"] == "healthy" else 503
        
        logger.info(f"Health check completed: {health_status['status']}")
        return JSONResponse(health_status, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Health check endpoint failed: {e}")
        error_response = {
            "status": "unhealthy",
            "service": config.server_name,
            "error": str(e),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        return JSONResponse(error_response, status_code=503)


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_endpoint(request):
    """
    HTTP readiness endpoint for Cloud Run startup probes.
    
    Provides a readiness check that verifies the application is fully
    initialized and ready to accept traffic. This is more comprehensive
    than the basic health check and includes dependency verification.
    
    Args:
        request: Starlette Request object
        
    Returns:
        JSONResponse: Readiness status with dependency checks
        
    Example:
        GET /ready
        Returns: {"status": "ready", "dependencies": {...}}
    """
    from starlette.responses import JSONResponse
    
    try:
        logger.debug("Readiness check requested")
        
        readiness_status = {
            "status": "ready",
            "service": config.server_name,
            "version": config.server_version,
            "dependencies": {}
        }
        
        # Check database readiness (non-blocking for startup)
        try:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent))
            from database.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    result = cursor.fetchone()
                    readiness_status["dependencies"]["database"] = {
                        "status": "ready",
                        "version": result[0] if result else "unknown"
                    }
        except Exception as e:
            logger.warning(f"Database readiness check failed: {e}")
            readiness_status["dependencies"]["database"] = {
                "status": "not_ready",
                "error": str(e)
            }
            # Don't fail readiness for database issues during startup
        
        # Check storage readiness (non-blocking for startup)
        try:
            from storage.gcs_client import create_gcs_client
            client = create_gcs_client()
            bucket = client.bucket
            if bucket.exists():
                readiness_status["dependencies"]["storage"] = {
                    "status": "ready",
                    "bucket": config.gcs_bucket_name
                }
            else:
                readiness_status["dependencies"]["storage"] = {
                    "status": "not_ready",
                    "error": f"Bucket {config.gcs_bucket_name} not found"
                }
                # Don't fail readiness for storage issues during startup
        except Exception as e:
            logger.warning(f"Storage readiness check failed: {e}")
            readiness_status["dependencies"]["storage"] = {
                "status": "not_ready",
                "error": str(e)
            }
            # Don't fail readiness for storage issues during startup
        
        # Determine HTTP status code
        status_code = 200 if readiness_status["status"] == "ready" else 503
        
        logger.info(f"Readiness check completed: {readiness_status['status']}")
        return JSONResponse(readiness_status, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Readiness check endpoint failed: {e}")
        error_response = {
            "status": "not_ready",
            "service": config.server_name,
            "error": str(e),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        return JSONResponse(error_response, status_code=503)


# ============================================================================
# Task 10: HTML5 Audio Player Embed Page
# ============================================================================

@mcp.custom_route("/embed/{audioId}", methods=["GET"])
async def embed_page(request):
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
        request: Starlette Request object with path parameters
        
    Returns:
        HTMLResponse: Rendered HTML page with audio player
        
    Example:
        GET /embed/550e8400-e29b-41d4-a716-446655440000
        Returns: HTML page with embedded audio player
    """
    from starlette.requests import Request
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from database import get_audio_metadata_by_id
    from resources.cache import get_cache
    
    # Extract audioId from path parameters
    audioId = request.path_params['audioId']
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
        audio_path = metadata.get("audio_gcs_path")
        thumbnail_path = metadata.get("thumbnail_gcs_path")
        
        if not audio_path:
            logger.error(f"No audio path for {audioId}")
            return HTMLResponse(
                content="<h1>Error</h1><p>Audio file not available.</p>",
                status_code=500
            )
        
        # Generate signed URLs using cache
        cache = get_cache()
        
        # TEMPORARY: Use mock URLs for testing Open Graph tags
        stream_url = f"https://storage.googleapis.com/loist-music-library-audio/audio/{audioId}/test.mp3"
        thumbnail_url = f"https://storage.googleapis.com/loist-music-library-audio/audio/{audioId}/artwork.jpg" if thumbnail_path else None
        
        logger.info(f"Using mock URLs for testing: stream={stream_url}, thumbnail={thumbnail_url}")
        
        # Original GCS code (commented out for testing):
        # try:
        #     stream_url = cache.get(audio_path, url_expiration_minutes=15)
        # except Exception as e:
        #     logger.error(f"Failed to generate signed URL for audio: {e}")
        #     return HTMLResponse(
        #         content="<h1>Error</h1><p>Failed to generate audio stream.</p>",
        #         status_code=500
        #     )
        # 
        # # Generate thumbnail URL if available
        # thumbnail_url = None
        # if thumbnail_path:
        #     try:
        #         thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
        #     except Exception as e:
        #         logger.warning(f"Failed to generate signed URL for thumbnail: {e}")
        #         # Continue without thumbnail
        
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
    
    # Check transport mode and run accordingly
    if config.server_transport == "http":
        logger.info(f"🌐 Starting HTTP server on {config.server_host}:{config.server_port}")
        mcp.run(
            transport="http",
            host=config.server_host,
            port=config.server_port
        )
    elif config.server_transport == "sse":
        logger.info(f"📡 Starting SSE server on {config.server_host}:{config.server_port}")
        mcp.run(
            transport="sse",
            host=config.server_host,
            port=config.server_port
        )
    else:
        # Default to stdio for MCP clients
        logger.info("📡 Starting STDIO server for MCP client communication")
        mcp.run()
