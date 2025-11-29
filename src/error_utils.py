"""
Error handling utilities for Music Library MCP Server
Provides consistent error responses and logging with safe exception serialization
"""
import logging
from typing import Any, Optional
from src.exceptions import MusicLibraryError, get_error_code
from src.exception_serializer import exception_serializer

logger = logging.getLogger(__name__)


def create_error_response(
    error: Exception,
    message: Optional[str] = None,
    include_details: bool = True
) -> dict:
    """
    Create a standardized error response for MCP protocol with safe serialization

    Args:
        error: The exception that occurred
        message: Optional custom error message (defaults to exception message)
        include_details: Whether to include detailed error information

    Returns:
        dict: Standardized error response with safely serialized exception details
    """
    # Use the safe exception serializer to handle complex exception details
    serialized_exception = exception_serializer.serialize_exception(error)

    error_code = serialized_exception.get("error_code", get_error_code(error))
    error_message = message or serialized_exception["message"]

    response = {
        "success": False,
        "error": error_code,
        "message": error_message
    }

    # Include safely serialized details if requested and available
    if include_details and serialized_exception.get("details"):
        response["details"] = serialized_exception["details"]

    # Include additional exception context for debugging
    response["exception_type"] = serialized_exception["type"]
    response["exception_module"] = serialized_exception["module"]

    return response


def log_error(
    error: Exception,
    context: Optional[dict] = None,
    level: str = "error"
) -> None:
    """
    Log an error with structured context using safe exception serialization

    Args:
        error: The exception to log
        context: Additional context information
        level: Log level (error, warning, critical)
    """
    # Use safe serializer to get structured exception information
    serialized_exception = exception_serializer.serialize_exception(error)

    log_data = {
        "error_type": serialized_exception["type"],
        "error_module": serialized_exception["module"],
        "error_code": serialized_exception.get("error_code", get_error_code(error)),
        "error_message": serialized_exception["message"],
    }

    # Include safely serialized details
    if serialized_exception.get("details"):
        log_data["details"] = serialized_exception["details"]

    # Include additional context if provided
    if context:
        log_data["context"] = context

    # Log at appropriate level with full exception info
    log_method = getattr(logger, level.lower(), logger.error)
    log_method(
        f"{log_data['error_code']}: {log_data['error_message']}",
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

