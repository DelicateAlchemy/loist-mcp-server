"""
Error handling utilities for Music Library MCP Server
Provides consistent error responses and logging
"""
import logging
from typing import Any, Optional
from exceptions import MusicLibraryError, get_error_code

logger = logging.getLogger(__name__)


def create_error_response(
    error: Exception,
    message: Optional[str] = None,
    include_details: bool = True
) -> dict:
    """
    Create a standardized error response for MCP protocol
    
    Args:
        error: The exception that occurred
        message: Optional custom error message (defaults to exception message)
        include_details: Whether to include detailed error information
        
    Returns:
        dict: Standardized error response
    """
    error_code = get_error_code(error)
    error_message = message or str(error)
    
    response = {
        "success": False,
        "error": error_code,
        "message": error_message
    }
    
    # Include additional details for MusicLibraryError exceptions
    if include_details and isinstance(error, MusicLibraryError):
        if error.details:
            response["details"] = error.details
    
    return response


def log_error(
    error: Exception,
    context: Optional[dict] = None,
    level: str = "error"
) -> None:
    """
    Log an error with structured context
    
    Args:
        error: The exception to log
        context: Additional context information
        level: Log level (error, warning, critical)
    """
    error_code = get_error_code(error)
    error_type = type(error).__name__
    
    log_data = {
        "error_type": error_type,
        "error_code": error_code,
        "error_message": str(error),  # Use error_message to avoid logging conflict
    }
    
    if context:
        log_data["context"] = context
    
    if isinstance(error, MusicLibraryError) and error.details:
        log_data["details"] = error.details
    
    # Log at appropriate level
    log_method = getattr(logger, level.lower(), logger.error)
    log_method(
        f"{error_code}: {str(error)}",
        extra=log_data,
        exc_info=True
    )


def handle_tool_error(
    error: Exception,
    tool_name: str,
    arguments: Optional[dict] = None
) -> dict:
    """
    Handle errors from MCP tool execution
    
    Args:
        error: The exception that occurred
        tool_name: Name of the tool that failed
        arguments: Tool arguments (for logging context)
        
    Returns:
        dict: Error response formatted for MCP protocol
    """
    # Log the error with context
    context = {
        "tool": tool_name,
        "arguments": arguments or {}
    }
    log_error(error, context=context)
    
    # Create error response
    error_response = create_error_response(error)
    
    return error_response


def handle_resource_error(
    error: Exception,
    resource_uri: str
) -> dict:
    """
    Handle errors from MCP resource access
    
    Args:
        error: The exception that occurred
        resource_uri: URI of the resource that failed
        
    Returns:
        dict: Error response formatted for MCP protocol
    """
    # Log the error with context
    context = {"resource_uri": resource_uri}
    log_error(error, context=context)
    
    # Create error response
    error_response = create_error_response(error)
    
    return error_response


def safe_execute(func, *args, **kwargs) -> tuple[Any, Optional[Exception]]:
    """
    Execute a function and return result or error
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        tuple: (result, error) - one will be None
    """
    try:
        result = func(*args, **kwargs)
        return result, None
    except Exception as e:
        return None, e

