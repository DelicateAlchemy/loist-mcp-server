"""
Music Library MCP Server
FastMCP-based server for audio ingestion and embedding
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastmcp import FastMCP
from config import config
from auth import SimpleBearerAuth

# Configure logging
config.configure_logging()
logger = logging.getLogger(__name__)


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


