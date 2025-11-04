"""
Enhanced exception serialization for FastMCP compatibility.

This module provides safe exception serialization that prevents NameError and other
serialization issues when FastMCP attempts to convert exceptions to JSON-RPC responses.
"""
import json
import logging
from typing import Any, Dict, Optional, Union
from src.exceptions import MusicLibraryError

logger = logging.getLogger(__name__)


class SafeExceptionSerializer:
    """
    Safe exception serializer that handles complex objects and execution context issues.

    This serializer ensures that exceptions can be safely converted to JSON-RPC error
    responses without causing NameError or other serialization failures in FastMCP.
    """

    @staticmethod
    def is_json_serializable(obj: Any) -> bool:
        """
        Check if an object can be safely serialized to JSON.

        Args:
            obj: Object to check for JSON serializability

        Returns:
            bool: True if object can be JSON serialized, False otherwise
        """
        try:
            json.dumps(obj)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def sanitize_exception_details(details: Any) -> Any:
        """
        Sanitize exception details to ensure JSON serializability.

        This method recursively processes exception details, converting non-serializable
        objects to string representations or removing them entirely.

        Args:
            details: Raw exception details (can be any type)

        Returns:
            Any: Sanitized details safe for JSON serialization
        """
        if details is None:
            return {}

        # If it's a dict, sanitize each value recursively
        if isinstance(details, dict):
            sanitized = {}
            for key, value in details.items():
                try:
                    sanitized[key] = SafeExceptionSerializer.sanitize_exception_details(value)
                except Exception as e:
                    logger.warning(f"Failed to sanitize detail '{key}': {e}")
                    sanitized[key] = f"<non-serializable: {type(value).__name__}>"
            return sanitized

        # If it's a list/tuple, sanitize each item
        if isinstance(details, (list, tuple)):
            sanitized = []
            for item in details:
                try:
                    sanitized.append(SafeExceptionSerializer.sanitize_exception_details(item))
                except Exception as e:
                    logger.warning(f"Failed to sanitize list item: {e}")
                    sanitized.append(f"<non-serializable: {type(item).__name__}>")
            return sanitized

        # Check if the object is JSON serializable
        if SafeExceptionSerializer.is_json_serializable(details):
            return details

        # For any other non-serializable object, convert to string
        return SafeExceptionSerializer._object_to_string(details)

    @staticmethod
    def _object_to_string(obj: Any) -> str:
        """
        Convert a non-serializable object to a meaningful string representation.

        Args:
            obj: Object to convert to string

        Returns:
            str: String representation of the object
        """
        try:
            # Try to get a meaningful string representation
            if hasattr(obj, '__name__'):
                return f"<{type(obj).__name__} {getattr(obj, '__name__', '')}>"
            elif hasattr(obj, '__class__'):
                return f"<{obj.__class__.__name__} object>"
            else:
                return f"<{type(obj).__name__} object>"
        except Exception:
            # Fallback if even basic introspection fails
            return "<non-serializable object>"

    @classmethod
    def serialize_exception(cls, exception: Exception) -> Dict[str, Any]:
        """
        Safely serialize an exception for FastMCP JSON-RPC responses.

        This method ensures that all exception information is safely serializable
        and includes proper error context while preventing NameError exceptions.

        Args:
            exception: The exception to serialize

        Returns:
            Dict containing safely serializable exception information
        """
        try:
            # Get basic exception information safely
            exc_type = type(exception)
            exc_module = getattr(exc_type, '__module__', 'unknown')
            exc_name = getattr(exc_type, '__name__', 'UnknownException')

            # Ensure exception class information is accessible
            # This prevents NameError when FastMCP tries to access __class__
            try:
                # Verify we can access the exception class
                _ = exception.__class__
                _ = exception.__class__.__name__
                _ = exception.__class__.__module__
            except AttributeError as e:
                logger.warning(f"Exception class access failed: {e}")
                # Use fallback values
                exc_name = "UnknownException"
                exc_module = "unknown"

            # Sanitize exception details
            raw_details = getattr(exception, 'details', None)
            safe_details = cls.sanitize_exception_details(raw_details)

            # Build safe exception representation
            serialized = {
                "type": exc_name,
                "module": exc_module,
                "message": str(exception),
                "details": safe_details,
            }

            # Add additional context for MusicLibraryError subclasses
            if isinstance(exception, MusicLibraryError):
                serialized["is_music_library_error"] = True
                # Ensure error code is accessible
                try:
                    from src.exceptions import get_error_code
                    serialized["error_code"] = get_error_code(exception)
                except Exception as e:
                    logger.warning(f"Failed to get error code: {e}")
                    serialized["error_code"] = "UNKNOWN_ERROR"

            return serialized

        except Exception as e:
            # Ultimate fallback - return a generic error representation
            logger.error(f"Exception serialization failed completely: {e}")
            return {
                "type": "SerializationError",
                "module": "unknown",
                "message": "Exception serialization failed",
                "details": {"original_error": str(e)},
                "serialization_failed": True,
            }

    @classmethod
    def create_fastmcp_error_response(cls, exception: Exception, request_id: Any = None) -> Dict[str, Any]:
        """
        Create a complete FastMCP JSON-RPC error response from an exception.

        Args:
            exception: The exception to convert to an error response
            request_id: The JSON-RPC request ID (if available)

        Returns:
            Dict containing complete JSON-RPC error response
        """
        # Serialize the exception safely
        serialized_exception = cls.serialize_exception(exception)

        # Determine appropriate JSON-RPC error code
        error_code = -32603  # Internal error (default)

        # Use specific error codes for known exception types
        if isinstance(exception, MusicLibraryError):
            # Map MusicLibraryError subclasses to appropriate codes
            error_code_map = {
                "VALIDATION_ERROR": -32602,  # Invalid params
                "RESOURCE_NOT_FOUND": -32602,  # Invalid params (resource not found)
                "AUTHENTICATION_FAILED": -32600,  # Invalid request (auth)
            }
            exception_error_code = serialized_exception.get("error_code")
            if exception_error_code in error_code_map:
                error_code = error_code_map[exception_error_code]

        # Build JSON-RPC error response
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": error_code,
                "message": serialized_exception["message"],
                "data": {
                    "exception": serialized_exception
                }
            }
        }

        # Include request ID if provided
        if request_id is not None:
            error_response["id"] = request_id

        return error_response


class ExceptionSerializationMiddleware:
    """
    Middleware to preprocess exceptions before FastMCP serialization.

    This middleware can be integrated with FastMCP to ensure all exceptions
    are properly sanitized before being passed to FastMCP's ErrorHandlingMiddleware.
    """

    def __init__(self):
        self.serializer = SafeExceptionSerializer()

    def preprocess_exception(self, exception: Exception) -> Exception:
        """
        Preprocess an exception to ensure it's safe for FastMCP serialization.

        Args:
            exception: Raw exception from application code

        Returns:
            Exception: Preprocessed exception safe for serialization
        """
        if isinstance(exception, MusicLibraryError):
            # For our custom exceptions, sanitize the details
            if hasattr(exception, 'details') and exception.details:
                safe_details = self.serializer.sanitize_exception_details(exception.details)
                # Create a new exception instance with sanitized details
                new_exception = type(exception)(exception.message, safe_details)
                return new_exception

        return exception

    def create_error_response(self, exception: Exception, request_id: Any = None) -> Dict[str, Any]:
        """
        Create a FastMCP-compatible error response from an exception.

        Args:
            exception: Exception to convert to error response
            request_id: JSON-RPC request ID

        Returns:
            Dict: JSON-RPC error response
        """
        # Preprocess the exception first
        safe_exception = self.preprocess_exception(exception)

        # Create the error response
        return self.serializer.create_fastmcp_error_response(safe_exception, request_id)


# Global instance for easy access
exception_serializer = SafeExceptionSerializer()
exception_middleware = ExceptionSerializationMiddleware()
