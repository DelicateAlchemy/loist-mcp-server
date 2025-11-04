"""
FastMCP Server Setup and Configuration

This module provides clean FastMCP initialization without workarounds.
Handles exception loading, server configuration, and middleware setup.

Author: Task Master AI
Created: $(date)
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from starlette.templating import Jinja2Templates
from pathlib import Path

from src.config import config
from src.exceptions import MusicLibraryError

logger = logging.getLogger(__name__)


def create_fastmcp_server() -> FastMCP:
    """
    Create and configure FastMCP server with clean initialization.

    Returns:
        FastMCP: Configured FastMCP server instance
    """
    logger.info("Initializing FastMCP server...")

    # Create FastMCP server with configuration
    mcp = FastMCP(
        name=config.server_name,
        version=config.server_version,
        instructions=config.server_instructions,
        modelPreferences={
            "temperature": 0.1,
            "maxTokens": 4096,
        }
    )

    logger.info(f"✅ FastMCP server initialized: {config.server_name} v{config.server_version}")
    return mcp


def setup_jinja_templates() -> Jinja2Templates:
    """
    Configure Jinja2 templates for the application.

    Returns:
        Jinja2Templates: Configured template engine
    """
    template_dir = Path(__file__).parent.parent / "templates"
    templates = Jinja2Templates(directory=str(template_dir))
    logger.info(f"✅ Jinja2 templates configured: {template_dir}")
    return templates


def get_server_config() -> Dict[str, Any]:
    """
    Get server configuration for FastMCP.

    Returns:
        Dict containing server configuration
    """
    return {
        "name": config.server_name,
        "version": config.server_version,
        "host": config.server_host,
        "port": config.server_port,
        "transport": config.server_transport,
        "auth_enabled": config.auth_enabled,
        "cors_enabled": config.enable_cors,
        "metrics_enabled": config.enable_metrics,
        "healthcheck_enabled": config.enable_healthcheck,
    }


def validate_server_setup() -> Dict[str, Any]:
    """
    Validate that server setup is complete and functional.

    Returns:
        Dict containing validation results
    """
    validation_results = {
        "fastmcp_initialized": False,
        "templates_configured": False,
        "configuration_valid": False,
        "errors": []
    }

    try:
        # Test FastMCP server creation
        mcp = create_fastmcp_server()
        validation_results["fastmcp_initialized"] = True
        logger.info("✅ FastMCP server validation passed")

    except Exception as e:
        validation_results["errors"].append(f"FastMCP initialization failed: {e}")
        logger.error(f"❌ FastMCP server validation failed: {e}")

    try:
        # Test template configuration
        templates = setup_jinja_templates()
        validation_results["templates_configured"] = True
        logger.info("✅ Template configuration validation passed")

    except Exception as e:
        validation_results["errors"].append(f"Template configuration failed: {e}")
        logger.error(f"❌ Template configuration validation failed: {e}")

    # Validate configuration
    try:
        server_config = get_server_config()
        required_fields = ["name", "version", "host", "port"]
        missing_fields = [field for field in required_fields if field not in server_config]

        if missing_fields:
            validation_results["errors"].append(f"Missing configuration fields: {missing_fields}")
            logger.error(f"❌ Configuration validation failed: missing fields {missing_fields}")
        else:
            validation_results["configuration_valid"] = True
            logger.info("✅ Server configuration validation passed")

    except Exception as e:
        validation_results["errors"].append(f"Configuration validation failed: {e}")
        logger.error(f"❌ Configuration validation failed: {e}")

    # Overall validation status
    validation_results["valid"] = (
        validation_results["fastmcp_initialized"] and
        validation_results["templates_configured"] and
        validation_results["configuration_valid"]
    )

    if validation_results["valid"]:
        logger.info("✅ Server setup validation completed successfully")
    else:
        logger.error(f"❌ Server setup validation failed with {len(validation_results['errors'])} errors")

    return validation_results


def log_server_startup_info() -> None:
    """
    Log comprehensive server startup information for debugging.
    """
    logger.info("=" * 60)
    logger.info("Loist Music Library MCP Server Starting Up")
    logger.info("=" * 60)

    server_config = get_server_config()
    logger.info("Server Configuration:")
    for key, value in server_config.items():
        logger.info(f"  {key}: {value}")

    logger.info("")
    logger.info("Environment:")
    logger.info(f"  Python path: {Path(__file__).parent}")
    logger.info(f"  Template directory: {Path(__file__).parent.parent / 'templates'}")
    logger.info(f"  Log level: {config.log_level}")

    logger.info("")
    logger.info("Services Status:")
    logger.info(f"  Database configured: {config.is_database_configured}")
    logger.info(f"  GCS configured: {config.is_gcs_configured}")

    validation = validate_server_setup()
    if validation["valid"]:
        logger.info("✅ All validations passed - server ready to start")
    else:
        logger.error(f"❌ Validation failed with {len(validation['errors'])} errors:")
        for error in validation["errors"]:
            logger.error(f"  - {error}")

    logger.info("=" * 60)
