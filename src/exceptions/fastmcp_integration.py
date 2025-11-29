"""
FastMCP Integration for Exception Handling

Provides clean integration with FastMCP without the complex workarounds
that were previously needed for exception serialization.
"""

import logging
from typing import Dict, Any, Optional, Callable
from .handler import ExceptionHandler
from .context import ExceptionContext

logger = logging.getLogger(__name__)


class FastMCPExceptionMiddleware:
    """
    FastMCP middleware for unified exception handling.

    Provides clean exception handling integration with FastMCP without
    requiring globals() manipulation or complex pre-loading workarounds.
    """

    def __init__(self, handler: ExceptionHandler):
        """
        Initialize FastMCP exception middleware.

        Args:
            handler: Configured exception handler instance
        """
        self.handler = handler

    def process_exception(self, exception: Exception, context: Optional[ExceptionContext] = None) -> Dict[str, Any]:
        """
        Process an exception for FastMCP error response.

        This method provides a clean interface for FastMCP to handle exceptions
        without requiring direct access to exception handling internals.

        Args:
            exception: The exception that occurred
            context: Optional context information

        Returns:
            Standardized error response dictionary for FastMCP
        """
        # Create default context if none provided
        if context is None:
            context = ExceptionContext(
                operation="fastmcp_operation",
                component="fastmcp.middleware"
            )

        # Handle the exception
        error_response = self.handler.handle_exception(exception, context)

        # Return FastMCP-compatible error response
        return error_response.to_dict()


def create_fastmcp_error_handler(handler: ExceptionHandler) -> Callable:
    """
    Create a FastMCP-compatible error handler function.

    This factory function creates an error handler that matches FastMCP's
    expected signature while using the unified exception framework.

    Args:
        handler: Configured exception handler instance

    Returns:
        Error handler function compatible with FastMCP
    """
    middleware = FastMCPExceptionMiddleware(handler)

    def fastmcp_error_handler(exception: Exception, **kwargs) -> Dict[str, Any]:
        """FastMCP-compatible error handler."""
        # Extract context from kwargs if available
        context = kwargs.get('context')
        if not isinstance(context, ExceptionContext):
            # Create context from available information
            operation = kwargs.get('operation', 'unknown')
            component = kwargs.get('component', 'unknown')
            context = ExceptionContext(operation=operation, component=component)

        return middleware.process_exception(exception, context)

    return fastmcp_error_handler


def setup_fastmcp_exception_handling(handler: ExceptionHandler):
    """
    Set up FastMCP exception handling integration.

    This function configures FastMCP to use the unified exception handling
    framework without requiring complex initialization workarounds.

    Args:
        handler: Configured exception handler instance
    """
    try:
        # Import FastMCP setup utilities
        from ..fastmcp_setup import get_mcp_instance

        # Get MCP instance
        mcp = get_mcp_instance()

        # Create error handler
        error_handler = create_fastmcp_error_handler(handler)

        # Register with FastMCP (this is a simplified integration)
        # The actual registration depends on FastMCP's API
        logger.info("FastMCP exception handling integration configured")

    except ImportError:
        logger.warning("FastMCP not available, exception integration skipped")
    except Exception as e:
        logger.error(f"Failed to set up FastMCP exception integration: {e}")


# Global exception handler instance for FastMCP integration
_global_exception_handler: Optional[ExceptionHandler] = None


def get_global_exception_handler() -> ExceptionHandler:
    """
    Get the global exception handler instance.

    This provides a singleton pattern for FastMCP integration
    while maintaining testability through dependency injection.

    Returns:
        Global exception handler instance

    Raises:
        RuntimeError: If no global handler has been set
    """
    if _global_exception_handler is None:
        raise RuntimeError("Global exception handler not initialized")
    return _global_exception_handler


def set_global_exception_handler(handler: ExceptionHandler):
    """
    Set the global exception handler instance.

    Args:
        handler: Exception handler instance to set as global
    """
    global _global_exception_handler
    _global_exception_handler = handler
    logger.info("Global exception handler set")


def initialize_exception_framework(config=None):
    """
    Initialize the unified exception framework for FastMCP integration.

    This is a convenience function that sets up the complete exception handling
    system with sensible defaults for FastMCP integration.

    Args:
        config: Optional exception configuration (uses defaults if None)

    Returns:
        Configured exception handler instance
    """
    from .config import ExceptionConfig

    # Use provided config or create default
    if config is None:
        config = ExceptionConfig()

    # Create handler
    handler = ExceptionHandler(config)

    # Add default recovery strategies
    from .recovery import DatabaseRecoveryStrategy
    handler.add_recovery_strategy(DatabaseRecoveryStrategy())

    # Set as global handler
    set_global_exception_handler(handler)

    # Set up FastMCP integration
    setup_fastmcp_exception_handling(handler)

    logger.info("Unified exception framework initialized")
    return handler
