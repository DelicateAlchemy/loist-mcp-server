"""
Music Library MCP Server
FastMCP-based server for audio ingestion and embedding
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to Python path for imports (needed for Docker)
# When running from /app/src/server.py, this ensures /app is on the path
app_dir = Path(__file__).parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastmcp import FastMCP
from starlette.responses import HTMLResponse, JSONResponse
from starlette.templating import Jinja2Templates

from auth import SimpleBearerAuth
from config import config

# Import exceptions (clean and simple - no complex loading needed)
from src.exceptions import (
    AudioProcessingError,
    AuthenticationError,
    DatabaseOperationError,
    ExternalServiceError,
    MusicLibraryError,
    RateLimitError,
    ResourceNotFoundError,
    StorageError,
    TimeoutError,
    ValidationError,
)
from src.fastmcp_setup import (
    create_fastmcp_server,
    log_server_startup_info,
    setup_jinja_templates,
    validate_server_setup,
)

# ============================================================================
# Centralized Exception Import Strategy
# ============================================================================
# Clean FastMCP Setup - No more workarounds or globals manipulation



# Configure logging
config.configure_logging()
logger = logging.getLogger(__name__)

# Validate server setup before proceeding
validation = validate_server_setup()
if not validation["valid"]:
    logger.error("❌ Server setup validation failed - cannot proceed")
    for error in validation["errors"]:
        logger.error(f"  - {error}")
    raise RuntimeError("Server setup validation failed")

logger.info("✅ Server setup validation passed")

# Initialize FastMCP server cleanly
mcp = create_fastmcp_server()

# Register task handlers for async processing
from src.tasks.handler import register_task_handlers
register_task_handlers(mcp)

# Configure Jinja2 templates
templates = setup_jinja_templates()


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


# Log startup information for debugging
log_server_startup_info()

# ============================================================================
# Health Check Caching for Cost Optimization
# ============================================================================

# Global cache for database health status to reduce Cloud SQL queries
_last_db_check = {"time": 0, "result": None}
_db_check_cache_ttl = 5  # seconds

def check_database_availability_cached():
    """
    Cached version of database availability check.

    Reduces Cloud SQL queries by caching health status for short periods.
    This significantly reduces database load from health checks.
    """
    global _last_db_check

    now = time.time()
    if now - _last_db_check["time"] < _db_check_cache_ttl:
        return _last_db_check["result"]

    # Fresh check
    from database import check_database_availability
    result = check_database_availability()
    _last_db_check = {"time": now, "result": result}
    return result


@mcp.tool()
def health_check() -> dict:
    """
    Health check endpoint to verify server is running

    Returns:
        dict: Server status information including version and configuration

    Raises:
        Exception: If health check fails (demonstrates error handling)
    """
    from src.error_utils import handle_tool_error
    from src.exceptions import MusicLibraryError, ResourceNotFoundError
    from database import check_database_availability
    from src.storage.gcs_client import check_gcs_health
    from src.tasks.queue import check_cloud_tasks_health

    try:
        logger.debug("Health check requested")

        # Check all dependencies
        db_status = check_database_availability()
        gcs_status = check_gcs_health()
        tasks_status = check_cloud_tasks_health()

        # Determine overall health status
        all_healthy = all([
            db_status["available"],
            gcs_status["available"],
            tasks_status["available"]
        ])

        # Verify server is operational
        response = {
            "status": "healthy" if all_healthy else "degraded",
            "service": config.server_name,
            "version": config.server_version,
            "transport": config.server_transport,
            "log_level": config.log_level,
            "authentication": "enabled" if config.auth_enabled else "disabled",
            "database": {
                "available": db_status["available"],
                "connection_type": db_status["connection_type"],
                "response_time_ms": db_status["response_time_ms"],
                "error": db_status["error"]
            },
            "gcs": {
                "available": gcs_status["available"],
                "configured": gcs_status["configured"],
                "bucket_name": gcs_status["bucket_name"],
                "response_time_ms": gcs_status["response_time_ms"],
                "error": gcs_status["error"]
            },
            "cloud_tasks": {
                "available": tasks_status["available"],
                "configured": tasks_status["configured"],
                "queue_name": tasks_status["queue_name"],
                "location": tasks_status["location"],
                "response_time_ms": tasks_status["response_time_ms"],
                "error": tasks_status["error"]
            }
        }

        # Include connection pool stats if database is available
        if db_status["available"]:
            try:
                from database import get_connection_pool
                pool = get_connection_pool()
                pool_stats = pool.get_stats()
                response["database"]["pool_stats"] = {
                    "connections_created": pool_stats.get("connections_created", 0),
                    "queries_executed": pool_stats.get("queries_executed", 0),
                    "last_health_check": pool_stats.get("last_health_check")
                }
            except Exception as e:
                logger.debug(f"Could not get pool stats: {e}")
                response["database"]["pool_stats_error"] = str(e)

        logger.info("Health check passed")
        return response

    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "health_check")
        logger.error(f"Health check failed: {error_response}")
        return error_response


@mcp.custom_route("/health/database", methods=["GET"])
def database_health_endpoint(request):
    """
    Dedicated database health check endpoint.

    Returns detailed database connectivity and performance information.
    Useful for monitoring systems and load balancers.
    """
    from datetime import datetime

    try:
        from database import check_database_availability, get_connection_pool

        # Check database availability
        db_status = check_database_availability()

        response = {
            "status": "healthy" if db_status["available"] else "unhealthy",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "database": {
                "available": db_status["available"],
                "connection_type": db_status["connection_type"],
                "response_time_ms": db_status["response_time_ms"],
                "error": db_status["error"]
            }
        }

        # Add detailed pool information if available
        if db_status["available"]:
            try:
                pool = get_connection_pool()
                health = pool.health_check()
                pool_stats = pool.get_stats()

                response["database"].update({
                    "version": health.get("database_version"),
                    "pool_size": health.get("max_connections"),
                    "pool_stats": {
                        "connections_created": pool_stats.get("connections_created", 0),
                        "connections_closed": pool_stats.get("connections_closed", 0),
                        "connections_failed": pool_stats.get("connections_failed", 0),
                        "queries_executed": pool_stats.get("queries_executed", 0),
                        "last_health_check": pool_stats.get("last_health_check")
                    }
                })
            except Exception as e:
                response["database"]["pool_error"] = str(e)

        # Set HTTP status code based on availability
        status_code = 200 if db_status["available"] else 503

        return JSONResponse(content=response, status_code=status_code)

    except Exception as e:
        logger.error(f"Database health endpoint error: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "database": {
                    "available": False,
                    "error": str(e)
                }
            },
            status_code=500
        )


@mcp.custom_route("/health/live", methods=["GET"])
def liveness_health_endpoint(request):
    """
    Liveness health check endpoint - NO DATABASE QUERIES.

    Checks if the application is running and can handle requests.
    This is a basic check that doesn't test external dependencies.

    Used by Cloud Run to determine if container should be restarted.
    Returns 200 if alive, 500 if not responding.
    """
    from datetime import datetime

    try:
        return JSONResponse(
            content={
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "service": config.server_name,
                "version": config.server_version,
                "check": "liveness"
            },
            status_code=200
        )

    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return JSONResponse(
            content={
                "status": "dead",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "error": str(e),
                "check": "liveness"
            },
            status_code=500
        )


@mcp.custom_route("/health/ready", methods=["GET"])
def readiness_health_endpoint(request):
    """
    Readiness health check endpoint - CONFIGURATION-BASED CHECK.

    Checks if the application is ready to serve traffic by verifying configuration.
    Only checks if dependencies are configured, not if they're actually available.
    This is used by load balancers and orchestrators to determine if the service
    should receive traffic.

    Uses cached database check to reduce Cloud SQL queries.
    Returns 200 if ready, 503 if not ready.
    """
    from datetime import datetime

    try:
        # Check configuration, not actual connectivity (cost optimization)
        # This avoids expensive database queries during health checks
        db_configured = config.is_database_configured
        gcs_configured = config.is_gcs_configured

        # Application is ready if critical dependencies are configured
        # Note: Cloud Tasks is optional for basic functionality
        is_ready = db_configured and gcs_configured

        # Use cached database check for detailed status (if configured)
        db_status = {"available": False, "connection_type": "unknown"}
        if db_configured:
            try:
                # Use cached check to reduce database load
                cached_result = check_database_availability_cached()
                if cached_result:
                    db_status = {
                        "available": cached_result["available"],
                        "connection_type": cached_result["connection_type"]
                    }
            except Exception as e:
                logger.debug(f"Database availability check failed: {e}")
                # Continue with configuration-based check

        response = {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "service": config.server_name,
            "version": config.server_version,
            "check": "readiness",
            "dependencies": {
                "database": {
                    "configured": db_configured,
                    "available": db_status["available"],
                    "connection_type": db_status["connection_type"]
                },
                "gcs": {
                    "configured": gcs_configured
                }
            }
        }

        status_code = 200 if is_ready else 503
        return JSONResponse(content=response, status_code=status_code)

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "service": config.server_name,
                "check": "readiness",
                "error": str(e)
            },
            status_code=503
        )


# ============================================================================
# Task 7: Audio Processing Tool
# ============================================================================


@mcp.tool()
async def process_audio_complete(source: dict, options: dict = None) -> dict:
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
    from src.error_utils import handle_tool_error
    from src.tools import process_audio_complete as process_audio_func

    try:
        # All custom exceptions are already in global scope from centralized import
        # FastMCP can now serialize them correctly since they're available in module namespace

        # Build input data
        input_data = {"source": source, "options": options or {}}

        # Call the async processing function
        # Exceptions raised here will be serialized by FastMCP using the
        # exception classes already loaded in global scope
        return await process_audio_func(input_data)
    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "process_audio_complete")
        logger.error(f"Process audio complete failed: {error_response}")
        return error_response


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
    from src.error_utils import handle_tool_error
    from src.tools.query_tools import get_audio_metadata as get_metadata_func

    try:
        # Call the async function
        return await get_metadata_func({"audioId": audioId})
    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "get_audio_metadata")
        logger.error(f"Get audio metadata failed for {audioId}: {error_response}")
        return error_response


@mcp.tool()
async def search_library(
    query: str,
    filters: dict = None,
    limit: int = 20,
    offset: int = 0,
    sortBy: str = "relevance",
    sortOrder: str = "desc",
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
    from src.error_utils import handle_tool_error
    from src.tools.query_tools import search_library as search_func

    try:
        # Build input data
        input_data = {
            "query": query,
            "filters": filters,
            "limit": limit,
            "offset": offset,
            "sortBy": sortBy,
            "sortOrder": sortOrder,
        }

        # Call the async function
        return await search_func(input_data)
    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "search_library")
        logger.error(f"Search library failed for query '{query}': {error_response}")
        return error_response


# ============================================================================
# Task 8: Delete Audio Tool
# ============================================================================


@mcp.tool()
async def delete_audio(audioId: str) -> dict:
    """
    Delete a previously processed audio track.

    This tool permanently removes an audio track from the database.
    GCS files are left in place for lifecycle management.

    Args:
        audioId: UUID of the audio track to delete

    Returns:
        dict: Success response with deletion confirmation,
              or error response if track not found or deletion fails

    Example:
        >>> result = await delete_audio(audioId="550e8400-e29b-41d4-a716-446655440000")
        >>> print(result["deleted"])
        True
    """
    from src.error_utils import handle_tool_error
    from src.tools.query_tools import delete_audio as delete_func

    try:
        # Call the async function
        return await delete_func({"audioId": audioId})
    except Exception as e:
        # Log and return error response
        error_response = handle_tool_error(e, "delete_audio")
        logger.error(f"Delete audio failed for ID '{audioId}': {error_response}")
        return error_response


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
    from src.resources.audio_stream import get_audio_stream_resource

    uri = f"music-library://audio/{audioId}/stream"
    return await get_audio_stream_resource(uri)


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
    from src.resources.metadata import get_metadata_resource

    uri = f"music-library://audio/{audioId}/metadata"
    return await get_metadata_resource(uri)


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
    from src.resources.thumbnail import get_thumbnail_resource

    uri = f"music-library://audio/{audioId}/thumbnail"
    return await get_thumbnail_resource(uri)


# ============================================================================
# Device Detection Utilities
# ============================================================================

def detect_device_type(request) -> str:
    """
    Detect device type from request for template optimization.

    Priority:
    1. Query parameter ?device=mobile|desktop (explicit override)
    2. User-Agent header parsing
    3. Default to 'desktop'

    Args:
        request: Starlette Request object

    Returns:
        str: 'mobile' or 'desktop'
    """
    # Check for explicit device override in query parameters
    device_param = request.query_params.get('device', '').lower()
    if device_param in ['mobile', 'desktop']:
        logger.debug(f"Device detection: explicit override to '{device_param}'")
        return device_param

    # Parse User-Agent header for device detection
    user_agent = request.headers.get('user-agent', '').lower()

    # Mobile device patterns
    mobile_patterns = [
        'mobile', 'android', 'iphone', 'ipad', 'ipod',
        'blackberry', 'windows phone', 'opera mini',
        'iemobile', 'webos', 'palm'
    ]

    # Tablet-specific patterns (still considered mobile for our purposes)
    tablet_patterns = [
        'tablet', 'ipad', 'kindle', 'playbook', 'silk'
    ]

    # Check for mobile/tablet indicators
    if any(pattern in user_agent for pattern in mobile_patterns + tablet_patterns):
        logger.debug(f"Device detection: mobile (User-Agent: {user_agent[:50]}...)")
        return 'mobile'

    # Default to desktop
    logger.debug(f"Device detection: desktop (User-Agent: {user_agent[:50]}...)")
    return 'desktop'


async def get_waveform_context(audio_id: str) -> dict:
    """
    Get waveform context for audio track (used by waveform embed endpoints).

    Retrieves waveform metadata and generates signed URL if available.

    Args:
        audio_id: UUID of the audio track

    Returns:
        dict: Waveform context with keys:
            - waveform_url: Signed URL to waveform SVG (or None)
            - waveform_available: Boolean indicating if waveform exists
            - waveform_generated_at: ISO timestamp when waveform was generated (or None)
    """
    try:
        # Import required functions
        from database.operations import get_waveform_metadata
        from src.storage.waveform_storage import get_waveform_signed_url

        # Get waveform metadata
        metadata = get_waveform_metadata(audio_id)

        if metadata and metadata.get('waveform_gcs_path'):
            try:
                # Generate signed URL for waveform
                waveform_url = get_waveform_signed_url(audio_id)
                logger.debug(f"Waveform URL generated for audio_id: {audio_id}")
                return {
                    'waveform_url': waveform_url,
                    'waveform_available': True,
                    'waveform_generated_at': metadata.get('waveform_generated_at')
                }
            except Exception as e:
                logger.warning(f"Failed to generate waveform signed URL for {audio_id}: {e}")
                # Continue with waveform_available=False

    except Exception as e:
        logger.warning(f"Error retrieving waveform context for {audio_id}: {e}")

    # Return empty context if waveform unavailable
    return {
        'waveform_url': None,
        'waveform_available': False,
        'waveform_generated_at': None
    }


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

    from database import get_audio_metadata_by_id
    from src.resources.cache import get_cache

    # Extract audioId from path parameters
    audioId = request.path_params["audioId"]
    logger.info(f"[EMBED_TEST] Embed endpoint called for audioId: {audioId}")
    logger.info(f"Embed page requested for audio ID: {audioId}")

    # Check for template query parameter
    template = request.query_params.get('template', 'standard')
    logger.info(f"Requested template: {template}")

    try:
        # Get metadata from database
        metadata = get_audio_metadata_by_id(audioId)
    except ValidationError as e:
        logger.warning(f"Invalid audio ID format for embed: {audioId} - {e}")
        return HTMLResponse(
            content="<h1>Invalid Audio ID</h1><p>The audio ID format is invalid.</p>",
            status_code=400,
        )

    if not metadata:
        logger.warning(f"Audio track not found: {audioId}")
        return HTMLResponse(
            content="<h1>Audio Not Found</h1><p>The requested audio track could not be found.</p>",
            status_code=404,
        )

    logger.info("Metadata retrieved successfully, getting GCS paths")

    # Get GCS paths
    audio_path = metadata.get("audio_gcs_path")
    thumbnail_path = metadata.get("thumbnail_gcs_path")
    logger.info(f"Audio path from database: {audio_path}")

    # Fix for staging environment: correct bucket name if database contains old paths
    try:
        from src.config import config
        logger.info(f"[EMBED_FIX] Config imported successfully")
    except Exception as config_error:
        logger.error(f"[EMBED_FIX] Failed to import config: {config_error}")
        # Continue without config-based fixes
        config = None

    logger.info(f"[EMBED_FIX] Checking audio path: {audio_path}")
    if audio_path and 'loist-music-library-staging-audio' in audio_path:
        corrected_path = audio_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging')
        logger.warning(f"[EMBED_FIX] Correcting audio path from {audio_path} to {corrected_path}")
        audio_path = corrected_path
    else:
        logger.info(f"[EMBED_FIX] Audio path does not need correction: {audio_path}")

    if thumbnail_path and 'loist-music-library-staging-audio' in thumbnail_path:
        corrected_path = thumbnail_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging')
        logger.warning(f"[EMBED_FIX] Correcting thumbnail path from {thumbnail_path} to {corrected_path}")
        thumbnail_path = corrected_path
    else:
        logger.info(f"[EMBED_FIX] Thumbnail path does not need correction: {thumbnail_path}")

    if not audio_path:
        logger.error(f"No audio path for {audioId}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Audio file not available.</p>", status_code=500
        )

    # Generate signed URLs using cache
    cache = get_cache()

    # Debug logging for bucket configuration
    from src.config import config
    logger.info(f"[EMBED_DEBUG] GCS bucket name from config: {config.gcs_bucket_name}")
    logger.info(f"[EMBED_DEBUG] GCS_BUCKET_NAME env var: {os.getenv('GCS_BUCKET_NAME')}")
    logger.info(f"[EMBED_DEBUG] Audio GCS path: {audio_path}")

    try:
        stream_url = cache.get(audio_path, url_expiration_minutes=15)
        logger.info(f"[EMBED_DEBUG] Successfully generated signed URL")
    except Exception as e:
        logger.error(f"[EMBED_DEBUG] Failed to generate signed URL for audio: {e}")
        logger.error(f"[EMBED_DEBUG] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"[EMBED_DEBUG] Full traceback: {traceback.format_exc()}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Failed to generate audio stream. [EMBED_FIX_ACTIVE]</p>", status_code=500
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
        },
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
    try:
        # Create a mock request object for Jinja2Templates
        from starlette.datastructures import URL, Headers
        from starlette.requests import Request

        # Create minimal request object
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "query_string": b"",
        }
        mock_request = Request(scope)

        if template == 'waveform':
            # Get waveform context for waveform template
            # Note: get_waveform_context handles exceptions gracefully and returns default context
            logger.info("Getting waveform context for template rendering")
            waveform_context = await get_waveform_context(audioId)
            logger.info(f"Waveform context retrieved: available={waveform_context.get('waveform_available', False)}")
            
            # Always use waveform template when requested, even if waveform data isn't available yet
            # The template will handle missing waveform data gracefully
            device_type = detect_device_type(request)
            interactive_mode = device_type == 'desktop'

            logger.info(f"Using waveform template with device_type: {device_type}, interactive_mode: {interactive_mode}")

            response = templates.TemplateResponse(
                "embed-waveform.html",
                {
                    "request": mock_request,
                    "audio_id": audioId,
                    "metadata": template_metadata,
                    "stream_url": stream_url,
                    "thumbnail_url": thumbnail_url,
                    "mime_type": mime_type,
                    "duration_formatted": duration_formatted,
                    "embed_base_url": config.embed_base_url,
                    "device_type": device_type,
                    "is_mobile": device_type == 'mobile',
                    "is_desktop": device_type == 'desktop',
                    "interactive_mode": interactive_mode,
                    **waveform_context
                },
            )
        else:
            # Use standard template
            response = templates.TemplateResponse(
                "embed.html",
                {
                    "request": mock_request,
                    "audio_id": audioId,
                    "metadata": template_metadata,
                    "stream_url": stream_url,
                    "thumbnail_url": thumbnail_url,
                    "mime_type": mime_type,
                    "duration_formatted": duration_formatted,
                    "embed_base_url": config.embed_base_url,
                },
            )

        # Add security headers for iframe embedding
        # Use Content-Security-Policy (modern standard) instead of X-Frame-Options
        # CSP frame-ancestors * allows embedding from any origin
        response.headers["Content-Security-Policy"] = "frame-ancestors *"

        return response

    except Exception as e:
        logger.exception(f"Error rendering embed page: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>An unexpected error occurred: {str(e)}</p>", status_code=500
        )


# ============================================================================
# Waveform Player Embed Endpoints
# ============================================================================

@mcp.custom_route("/embed/{audioId}/waveform/mobile", methods=["GET"])
async def embed_waveform_mobile(request):
    """
    Serve waveform player embed page optimized for mobile devices.

    This endpoint provides a waveform-based audio player with:
    - Waveform visualization (static display)
    - Mobile-optimized UI and controls
    - Touch-friendly interactions
    - Standard progress bar for seeking

    Args:
        request: Starlette Request object with path parameters

    Returns:
        HTMLResponse: Rendered waveform player page for mobile
    """
    from starlette.requests import Request

    from database import get_audio_metadata_by_id
    from src.resources.cache import get_cache

    # Extract audioId from path parameters
    audioId = request.path_params["audioId"]
    logger.info(f"Waveform mobile embed requested for audio ID: {audioId}")

    try:
        # Get metadata from database
        metadata = get_audio_metadata_by_id(audioId)
    except ValidationError as e:
        logger.warning(f"Invalid audio ID format for waveform mobile embed: {audioId} - {e}")
        return HTMLResponse(
            content="<h1>Invalid Audio ID</h1><p>The audio ID format is invalid.</p>",
            status_code=400,
        )

    if not metadata:
        logger.warning(f"Audio track not found for waveform mobile embed: {audioId}")
        return HTMLResponse(
            content="<h1>Audio Not Found</h1><p>The requested audio track could not be found.</p>",
            status_code=404,
        )

    # Get waveform context
    waveform_context = await get_waveform_context(audioId)

    # Get GCS paths
    audio_path = metadata.get("audio_gcs_path")
    thumbnail_path = metadata.get("thumbnail_gcs_path")

    if not audio_path:
        logger.error(f"No audio path for waveform mobile embed {audioId}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Audio file not available.</p>", status_code=500
        )

    # Generate signed URLs using cache
    cache = get_cache()

    try:
        stream_url = cache.get(audio_path, url_expiration_minutes=15)
    except Exception as e:
        logger.error(f"Failed to generate signed URL for audio in waveform mobile embed: {e}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Failed to generate audio stream.</p>", status_code=500
        )

    # Generate thumbnail URL if available
    thumbnail_url = None
    if thumbnail_path:
        try:
            thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
        except Exception as e:
            logger.warning(f"Failed to generate signed URL for thumbnail: {e}")

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
        },
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

    logger.info(f"Rendering waveform mobile embed for: {template_metadata['Product']['Title']}")

    # Create mock request for template rendering
    from starlette.datastructures import URL, Headers

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [],
        "query_string": b"",
    }
    mock_request = Request(scope)

    try:
        response = templates.TemplateResponse(
            "embed-waveform.html",
            {
                "request": mock_request,
                "audio_id": audioId,
                "metadata": template_metadata,
                "stream_url": stream_url,
                "thumbnail_url": thumbnail_url,
                "mime_type": mime_type,
                "duration_formatted": duration_formatted,
                "embed_base_url": config.embed_base_url,
                "device_type": "mobile",
                "is_mobile": True,
                "is_desktop": False,
                "interactive_mode": False,  # Static mode for mobile
                **waveform_context,
            },
        )

        # Add security headers for iframe embedding
        # Use Content-Security-Policy (modern standard) instead of X-Frame-Options
        # CSP frame-ancestors * allows embedding from any origin
        response.headers["Content-Security-Policy"] = "frame-ancestors *"

        return response

    except Exception as e:
        logger.exception(f"Error rendering waveform mobile embed: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>An unexpected error occurred: {str(e)}</p>", status_code=500
        )


@mcp.custom_route("/embed/{audioId}/waveform/desktop", methods=["GET"])
async def embed_waveform_desktop(request):
    """
    Serve waveform player embed page optimized for desktop devices.

    This endpoint provides a waveform-based audio player with:
    - Interactive waveform visualization (click-to-seek)
    - Desktop-optimized UI with hover effects
    - Full keyboard and mouse controls
    - Visual progress overlay on waveform

    Args:
        request: Starlette Request object with path parameters

    Returns:
        HTMLResponse: Rendered waveform player page for desktop
    """
    from starlette.requests import Request

    from database import get_audio_metadata_by_id
    from src.resources.cache import get_cache

    # Extract audioId from path parameters
    audioId = request.path_params["audioId"]
    logger.info(f"Waveform desktop embed requested for audio ID: {audioId}")

    try:
        # Get metadata from database
        metadata = get_audio_metadata_by_id(audioId)
    except ValidationError as e:
        logger.warning(f"Invalid audio ID format for waveform desktop embed: {audioId} - {e}")
        return HTMLResponse(
            content="<h1>Invalid Audio ID</h1><p>The audio ID format is invalid.</p>",
            status_code=400,
        )

    if not metadata:
        logger.warning(f"Audio track not found for waveform desktop embed: {audioId}")
        return HTMLResponse(
            content="<h1>Audio Not Found</h1><p>The requested audio track could not be found.</p>",
            status_code=404,
        )

    # Get waveform context
    waveform_context = await get_waveform_context(audioId)

    # Get GCS paths
    audio_path = metadata.get("audio_gcs_path")
    thumbnail_path = metadata.get("thumbnail_gcs_path")

    if not audio_path:
        logger.error(f"No audio path for waveform desktop embed {audioId}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Audio file not available.</p>", status_code=500
        )

    # Generate signed URLs using cache
    cache = get_cache()

    try:
        stream_url = cache.get(audio_path, url_expiration_minutes=15)
    except Exception as e:
        logger.error(f"Failed to generate signed URL for audio in waveform desktop embed: {e}")
        return HTMLResponse(
            content="<h1>Error</h1><p>Failed to generate audio stream.</p>", status_code=500
        )

    # Generate thumbnail URL if available
    thumbnail_url = None
    if thumbnail_path:
        try:
            thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
        except Exception as e:
            logger.warning(f"Failed to generate signed URL for thumbnail: {e}")

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
        },
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

    logger.info(f"Rendering waveform desktop embed for: {template_metadata['Product']['Title']}")

    # Create mock request for template rendering
    from starlette.datastructures import URL, Headers

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [],
        "query_string": b"",
    }
    mock_request = Request(scope)

    try:
        response = templates.TemplateResponse(
            "embed-waveform.html",
            {
                "request": mock_request,
                "audio_id": audioId,
                "metadata": template_metadata,
                "stream_url": stream_url,
                "thumbnail_url": thumbnail_url,
                "mime_type": mime_type,
                "duration_formatted": duration_formatted,
                "embed_base_url": config.embed_base_url,
                "device_type": "desktop",
                "is_mobile": False,
                "is_desktop": True,
                "interactive_mode": True,  # Interactive mode for desktop
                **waveform_context,
            },
        )

        # Add security headers for iframe embedding
        # Use Content-Security-Policy (modern standard) instead of X-Frame-Options
        # CSP frame-ancestors * allows embedding from any origin
        response.headers["Content-Security-Policy"] = "frame-ancestors *"

        return response

    except Exception as e:
        logger.exception(f"Error rendering waveform desktop embed: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>An unexpected error occurred: {str(e)}</p>", status_code=500
        )


@mcp.custom_route("/embed/{audioId}/waveform", methods=["GET"])
async def embed_waveform_auto(request):
    """
    Serve waveform player embed page with automatic device detection.

    This endpoint auto-detects the device type and serves the appropriate
    waveform player (mobile or desktop optimized).

    Args:
        request: Starlette Request object with path parameters

    Returns:
        HTMLResponse: Rendered waveform player page (mobile or desktop)
    """
    # Detect device type
    device_type = detect_device_type(request)

    # Extract audioId
    audioId = request.path_params["audioId"]
    logger.info(f"Waveform auto embed requested for audio ID: {audioId} (detected device: {device_type})")

    # Route to appropriate endpoint based on device type
    if device_type == "mobile":
        # Call mobile endpoint logic
        return await embed_waveform_mobile(request)
    else:
        # Call desktop endpoint logic (default)
        return await embed_waveform_desktop(request)


# ============================================================================
# MCP Tools for Embed Management
# ============================================================================

@mcp.tool()
async def get_embed_url(audioId: str, template: str = "standard", device: Optional[str] = None) -> dict:
    """
    Generate embed URL for audio track with template selection.

    Returns embed URL with template and device-specific endpoint selection.

    Args:
        audioId: UUID of the audio track
        template: Template type ("standard" or "waveform")
        device: Device type override ("mobile", "desktop", or None for auto-detection)

    Returns:
        dict: Embed information including URL, template type, and device detection

    Example:
        >>> result = await get_embed_url("550e8400-e29b-41d4-a716-446655440000", "waveform")
        >>> print(result["embedUrl"])
        "https://example.com/embed/550e8400-e29b-41d4-a716-446655440000/waveform"
    """
    try:
        # Validate audioId exists
        from database import get_audio_metadata_by_id
        metadata = get_audio_metadata_by_id(audioId)
        if not metadata:
            return {
                "success": False,
                "error": "RESOURCE_NOT_FOUND",
                "message": f"Audio track with ID '{audioId}' was not found",
                "audioId": audioId
            }

        # Build base embed URL
        base_url = f"{config.embed_base_url}/embed/{audioId}"

        # Determine template endpoint
        if template == "waveform":
            embed_url = f"{base_url}/waveform"
            # Add device-specific endpoint if specified
            if device == "mobile":
                embed_url = f"{base_url}/waveform/mobile"
            elif device == "desktop":
                embed_url = f"{base_url}/waveform/desktop"
        else:
            embed_url = base_url

        # Check waveform availability (for waveform template)
        waveform_available = False
        if template == "waveform":
            try:
                waveform_context = await get_waveform_context(audioId)
                waveform_available = waveform_context.get("waveform_available", False)
            except Exception as e:
                logger.warning(f"Error checking waveform availability: {e}")

        return {
            "success": True,
            "audioId": audioId,
            "embedUrl": embed_url,
            "template": template,
            "device": device or "auto",
            "waveformAvailable": waveform_available,
            "metadata": {
                "title": metadata.get("title", "Untitled"),
                "artist": metadata.get("artist", "Unknown Artist"),
                "duration": metadata.get("duration", 0),
                "format": metadata.get("format", "MP3")
            }
        }

    except ValidationError as e:
        return {
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": f"Invalid audio ID format: {str(e)}",
            "audioId": audioId
        }
    except Exception as e:
        logger.error(f"Error generating embed URL for {audioId}: {e}")
        return {
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Failed to generate embed URL",
            "audioId": audioId
        }


@mcp.tool()
async def list_embed_templates() -> dict:
    """
    List available embed player templates and their capabilities.

    Returns information about all available embed templates including
    their features, device support, and endpoint information.

    Returns:
        dict: Template information with capabilities and endpoints

    Example:
        >>> templates = await list_embed_templates()
        >>> print(templates["templates"][0]["name"])
        "Standard Player"
    """
    try:
        return {
            "success": True,
            "templates": [
                {
                    "id": "standard",
                    "name": "Standard Player",
                    "description": "Basic audio player with progress bar and standard controls",
                    "endpoint": "/embed/{audioId}",
                    "features": ["progress-bar", "volume-control", "keyboard-shortcuts"],
                    "deviceSupport": ["mobile", "desktop"],
                    "interactive": True
                },
                {
                    "id": "waveform",
                    "name": "Waveform Player",
                    "description": "Interactive waveform visualization with click-to-seek",
                    "endpoint": "/embed/{audioId}/waveform",
                    "features": ["waveform-visualization", "click-to-seek", "progress-overlay", "volume-control", "keyboard-shortcuts"],
                    "deviceSupport": ["mobile", "desktop"],
                    "interactive": True,
                    "deviceVariants": [
                        {
                            "device": "mobile",
                            "endpoint": "/embed/{audioId}/waveform/mobile",
                            "description": "Mobile-optimized waveform player (static display)",
                            "interactive": False
                        },
                        {
                            "device": "desktop",
                            "endpoint": "/embed/{audioId}/waveform/desktop",
                            "description": "Desktop-optimized waveform player (interactive)",
                            "interactive": True
                        }
                    ]
                }
            ],
            "baseUrl": config.embed_base_url,
            "supportedFormats": ["MP3", "FLAC", "WAV", "M4A", "OGG", "AAC"]
        }

    except Exception as e:
        logger.error(f"Error listing embed templates: {e}")
        return {
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Failed to retrieve template information"
        }


@mcp.tool()
async def check_waveform_availability(audioId: str) -> dict:
    """
    Check if waveform is available for an audio track.

    Verifies waveform generation status and provides access information
    if the waveform exists.

    Args:
        audioId: UUID of the audio track

    Returns:
        dict: Waveform availability and access information

    Example:
        >>> result = await check_waveform_availability("550e8400-e29b-41d4-a716-446655440000")
        >>> if result["waveformAvailable"]:
        ...     print(f"Waveform generated at: {result['generatedAt']}")
    """
    try:
        # Get waveform context
        waveform_context = await get_waveform_context(audioId)

        # Validate audioId exists
        from database import get_audio_metadata_by_id
        metadata = get_audio_metadata_by_id(audioId)
        if not metadata:
            return {
                "success": False,
                "error": "RESOURCE_NOT_FOUND",
                "message": f"Audio track with ID '{audioId}' was not found",
                "audioId": audioId
            }

        return {
            "success": True,
            "audioId": audioId,
            "waveformAvailable": waveform_context.get("waveform_available", False),
            "waveformUrl": waveform_context.get("waveform_url"),
            "generatedAt": waveform_context.get("waveform_generated_at"),
            "metadata": {
                "title": metadata.get("title", "Untitled"),
                "artist": metadata.get("artist", "Unknown Artist"),
                "duration": metadata.get("duration", 0),
                "format": metadata.get("format", "MP3")
            }
        }

    except ValidationError as e:
        return {
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": f"Invalid audio ID format: {str(e)}",
            "audioId": audioId
        }
    except Exception as e:
        logger.error(f"Error checking waveform availability for {audioId}: {e}")
        return {
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Failed to check waveform availability",
            "audioId": audioId
        }


@mcp.custom_route("/oembed", methods=["GET"])
async def oembed_endpoint(request):
    """
    oEmbed endpoint for rich media previews.

    Implements the oEmbed specification for embedding audio player
    in platforms like Notion, WordPress, and other oEmbed consumers.

    Args:
        request: Starlette Request object with query parameters:
            - url (required): The embed URL to generate oEmbed data for
            - format (optional): Response format, 'json' or 'xml' (default: 'json')
            - maxwidth (optional): Maximum width for embed (default: 600)
            - maxheight (optional): Maximum height for embed (default: 240)

    Returns:
        JSONResponse: oEmbed JSON response according to spec

    Example:
        GET /oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000
        Returns: JSON with oEmbed metadata
    """
    from urllib.parse import unquote

    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from database import get_audio_metadata_by_id
    from src.resources.cache import get_cache

    try:
        # Extract query parameters
        url_param = request.query_params.get("url")
        format_param = request.query_params.get("format", "json")
        # Default dimensions optimized for horizontal audio player layout
        # Aspect ratio ~2.5:1 (width:height) for better fit
        maxwidth = int(request.query_params.get("maxwidth", 600))
        maxheight = int(request.query_params.get("maxheight", 240))

        # Validate URL parameter
        if not url_param:
            logger.warning("oEmbed request missing url parameter")
            return JSONResponse({"error": "Missing required parameter: url"}, status_code=400)

        # Decode URL-encoded parameter
        url = unquote(url_param)
        logger.info(f"oEmbed request for URL: {url}")

        # Validate URL format
        from config import config

        expected_prefix = f"{config.embed_base_url}/embed/"
        if not url.startswith(expected_prefix):
            logger.warning(f"Invalid oEmbed URL: {url}")
            return JSONResponse(
                {"error": f"Invalid URL. Must start with {config.embed_base_url}/embed/"},
                status_code=400,
            )

        # Extract audio ID from URL
        audio_id = url.replace(expected_prefix, "").strip()
        if not audio_id:
            logger.warning("oEmbed request with empty audio ID")
            return JSONResponse({"error": "Invalid URL format. Missing audio ID."}, status_code=400)

        # Get metadata from database
        try:
            metadata = get_audio_metadata_by_id(audio_id)
        except ValidationError as e:
            logger.warning(f"Invalid audio ID format for oEmbed: {audio_id} - {e}")
            return JSONResponse({"error": "Invalid audio ID format"}, status_code=400)

        if not metadata:
            logger.warning(f"Audio track not found for oEmbed: {audio_id}")
            return JSONResponse({"error": "Audio track not found"}, status_code=404)

        # Get thumbnail path for preview
        thumbnail_path = metadata.get("thumbnail_gcs_path")
        thumbnail_url = None

        if thumbnail_path:
            try:
                cache = get_cache()
                thumbnail_url = cache.get(thumbnail_path, url_expiration_minutes=15)
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail URL for oEmbed: {e}")
                # Continue without thumbnail

        # Build embed URL (full URL to player page)
        embed_url = f"{config.embed_base_url}/embed/{audio_id}"

        # Format metadata
        title = metadata.get("title", "Untitled")
        artist = metadata.get("artist", "Unknown Artist")
        album = metadata.get("album")

        # Build description
        description = f"{artist}"
        if album:
            description += f" - {album}"

        # Build oEmbed response according to spec
        # Include proper allow attributes for Notion iframe embedding
        # allow="autoplay; encrypted-media; fullscreen" enables media playback in sandboxed iframes
        iframe_html = (
            f'<iframe src="{embed_url}?compact=true" '
            f'width="{maxwidth}" height="{maxheight}" '
            f'frameborder="0" '
            f'allow="autoplay; encrypted-media; fullscreen" '
            f'style="border-radius: 12px; border: none;" '
            f'scrolling="no"></iframe>'
        )
        
        oembed_response = {
            "version": "1.0",
            "type": "rich",
            "provider_name": "Loist Music Library",
            "provider_url": config.embed_base_url,
            "title": title,
            "author_name": artist,
            "html": iframe_html,
            "width": maxwidth,
            "height": maxheight,
            "cache_age": 3600,  # Cache for 1 hour
        }

        # Add thumbnail if available
        if thumbnail_url:
            oembed_response["thumbnail_url"] = thumbnail_url
            oembed_response["thumbnail_width"] = 500
            oembed_response["thumbnail_height"] = 500

        logger.info(f"Generated oEmbed response for {audio_id}: {title}")

        return JSONResponse(oembed_response)

    except ValueError as e:
        logger.error(f"Invalid oEmbed request parameter: {e}")
        return JSONResponse({"error": f"Invalid parameter: {str(e)}"}, status_code=400)
    except Exception as e:
        logger.exception(f"Error generating oEmbed response: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@mcp.custom_route("/.well-known/oembed.json", methods=["GET"])
async def oembed_discovery(request):
    """
    oEmbed provider discovery endpoint.

    Returns provider information for oEmbed consumers to discover
    available endpoints and capabilities.

    Args:
        request: Starlette Request object

    Returns:
        JSONResponse: oEmbed provider discovery information
    """
    from starlette.responses import JSONResponse

    discovery_response = {
        "provider_name": "Loist Music Library",
        "provider_url": config.embed_base_url,
        "endpoints": [
            {"url": f"{config.embed_base_url}/oembed", "formats": ["json"], "discovery": True}
        ],
    }

    logger.info("oEmbed discovery endpoint accessed")
    return JSONResponse(discovery_response)


# ============================================================================
# HTTP API Routes
# ============================================================================


@mcp.custom_route("/api/tracks/{audioId}", methods=["DELETE"])
async def delete_track(request):
    """
    Delete a track via HTTP API.

    This endpoint provides HTTP access to the delete_audio MCP tool.

    Args:
        request: Starlette Request object with path parameters

    Returns:
        JSONResponse: Success (204) or error response
    """
    from starlette.responses import JSONResponse
    from src.tools.query_tools import delete_audio as delete_func

    # Extract audioId from path parameters
    audioId = request.path_params["audioId"]
    logger.info(f"DELETE /api/tracks/{audioId} - Delete track request")

    try:
        # Call the delete function
        result = await delete_func({"audioId": audioId})

        # Check if it was successful
        if result.get("success"):
            logger.info(f"Successfully deleted track: {audioId}")
            # Return 204 No Content for successful deletion
            return JSONResponse({}, status_code=204)
        else:
            # Return error with appropriate status code
            error_code = result.get("error", "UNKNOWN_ERROR")
            if error_code == "RESOURCE_NOT_FOUND":
                status_code = 404
            elif error_code == "INVALID_QUERY":
                status_code = 400
            else:
                status_code = 500

            logger.warning(f"Delete failed for track {audioId}: {result.get('message', 'Unknown error')}")
            return JSONResponse(result, status_code=status_code)

    except Exception as e:
        logger.exception(f"Unexpected error deleting track {audioId}: {e}")
        error_response = {
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Internal server error during deletion",
            "details": {"exception_type": type(e).__name__}
        }
        return JSONResponse(error_response, status_code=500)


def create_mcp_tools():
    """
    Create and register MCP tools.

    This function ensures all MCP tools are properly registered.
    Tools are registered via @mcp.tool() decorators, so this function
    primarily serves as a validation hook for tests.
    """
    # Tools are registered via decorators, no additional setup needed
    logger.info("MCP tools validated and ready")
    return True


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
    mcp_app = mcp.http_app(path="/mcp")

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
        mcp.run(transport="http", host=config.server_host, port=config.server_port)
    elif config.server_transport == "sse":
        logger.info(f"📡 Starting SSE server on {config.server_host}:{config.server_port}")
        mcp.run(transport="sse", host=config.server_host, port=config.server_port)
    elif config.server_transport == "dual":
        # Run both HTTP web server and MCP stdio for Cursor
        logger.info(f"🔄 Starting dual mode: HTTP server + MCP stdio")
        import asyncio
        import threading

        # Function to run MCP in stdio mode in a separate thread
        def run_mcp_stdio():
            logger.info("📡 Starting MCP stdio server in background thread")
            mcp.run()

        # Start MCP stdio in background thread
        mcp_thread = threading.Thread(target=run_mcp_stdio, daemon=True)
        mcp_thread.start()

        # Run HTTP server in main thread
        logger.info(f"🌐 Starting HTTP server on {config.server_host}:{config.server_port}")
        mcp.run(transport="http", host=config.server_host, port=config.server_port)
    else:
        # Default to stdio for MCP clients
        logger.info("📡 Starting STDIO server for MCP client communication")
        mcp.run()
