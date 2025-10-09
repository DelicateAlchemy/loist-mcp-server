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

if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run()


