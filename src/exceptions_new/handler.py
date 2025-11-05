"""
Unified Exception Handler

Core exception handling system that consolidates all error handling approaches
into a single, consistent framework with dependency injection support.
"""

import logging
import traceback
from typing import Any, Dict, Optional, Union
from .config import ExceptionConfig
from .context import ExceptionContext
from .recovery import RecoveryStrategy
# Import MusicLibraryError - will be imported locally to avoid circular dependency
from ..exception_serializer import SafeExceptionSerializer

logger = logging.getLogger(__name__)


class ErrorResponse:
    """
    Standardized error response format.

    Provides consistent error response structure across all endpoints
    with configurable detail levels and safe serialization.
    """

    def __init__(
        self,
        success: bool = False,
        error_code: str = "UNKNOWN_ERROR",
        message: str = "An unknown error occurred",
        details: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        recovery: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.context = context or {}
        self.recovery = recovery or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
                "context": self.context,
                "recovery": self.recovery,
            }
        }


class ExceptionHandler:
    """
    Unified exception handler for the Music Library MCP Server.

    Consolidates all exception handling approaches into a single framework
    with consistent error responses, recovery strategies, and testing support.
    """

    def __init__(self, config: ExceptionConfig):
        """
        Initialize the exception handler.

        Args:
            config: Configuration for exception handling behavior
        """
        self.config = config
        self.serializer = SafeExceptionSerializer()
        self.recovery_strategies: list[RecoveryStrategy] = []
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging based on configuration."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }
        level = level_map.get(self.config.log_level.upper(), logging.ERROR)
        logger.setLevel(level)

    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """Add a recovery strategy to the handler."""
        self.recovery_strategies.append(strategy)

    def handle_exception(
        self,
        exception: Exception,
        context: ExceptionContext,
        include_recovery: bool = True
    ) -> ErrorResponse:
        """
        Handle an exception with full context and recovery logic.

        This is the main entry point for exception handling throughout the application.

        Args:
            exception: The exception that occurred
            context: Context information about the operation
            include_recovery: Whether to include recovery information in response

        Returns:
            Standardized error response
        """
        # Log the exception with context
        self._log_exception(exception, context)

        # Try recovery strategies first
        if self.config.enable_recovery and include_recovery:
            for strategy in self.recovery_strategies:
                if strategy.can_recover(exception, context):
                    try:
                        logger.info(f"Attempting recovery with {strategy.__class__.__name__}")
                        result = strategy.recover(exception, context)
                        logger.info("Recovery successful")
                        # If recovery succeeds, this shouldn't be reached
                        # (strategy should raise exception to trigger retry)
                        break
                    except Exception as recovery_error:
                        logger.warning(f"Recovery failed: {recovery_error}")
                        continue

        # Create error response
        return self._create_error_response(exception, context, include_recovery)

    def handle_and_raise(
        self,
        exception: Exception,
        context: ExceptionContext,
        include_recovery: bool = True
    ) -> None:
        """
        Handle an exception and then re-raise it.

        Useful for logging and context enrichment while preserving original exception flow.

        Args:
            exception: The exception to handle and re-raise
            context: Context information about the operation
            include_recovery: Whether to include recovery information

        Raises:
            Exception: The original exception after handling
        """
        self._log_exception(exception, context)

        # Try recovery if applicable
        if self.config.enable_recovery and include_recovery:
            for strategy in self.recovery_strategies:
                if strategy.can_recover(exception, context):
                    try:
                        strategy.recover(exception, context)
                        break  # Recovery successful
                    except Exception:
                        continue  # Try next strategy

        # Re-raise the original exception
        raise exception

    def handle_for_http(
        self,
        exception: Exception,
        context: ExceptionContext,
        include_recovery: bool = True
    ) -> tuple:
        """
        Handle exception and return HTTP response tuple.

        Args:
            exception: The exception that occurred
            context: Context information about the operation
            include_recovery: Whether to include recovery information

        Returns:
            Tuple of (response_dict, status_code)
        """
        error_response = self.handle_exception(exception, context, include_recovery)

        # Determine HTTP status code
        status_code = self._get_http_status_code(exception)

        return error_response.to_dict(), status_code

    def _log_exception(self, exception: Exception, context: ExceptionContext):
        """Log exception with structured context."""
        if self.config.enable_structured_logging:
            log_data = {
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'operation': context.operation,
                'component': context.component,
                'retry_count': context.retry_count,
                'user_id': context.user_id,
                'request_id': context.request_id,
            }

            if self.config.include_stack_traces:
                log_data['stack_trace'] = traceback.format_exc()

            logger.error("Exception occurred", extra=log_data)
        else:
            logger.error(f"Exception in {context.component}.{context.operation}: {exception}")

    def _create_error_response(
        self,
        exception: Exception,
        context: ExceptionContext,
        include_recovery: bool = True
    ) -> ErrorResponse:
        """Create standardized error response."""
        # Serialize exception safely
        serialized = self.serializer.serialize_exception(exception)

        # Build error response
        error_code = self._get_error_code(exception, serialized)
        message = self._get_error_message(exception, serialized)

        # Include details based on configuration
        details = {}
        if self.config.enable_detailed_errors:
            details = serialized.get('details', {})

        # Add context information
        context_dict = context.to_dict() if context else {}

        # Add recovery information
        recovery = {}
        if include_recovery and self.config.enable_recovery:
            recovery = self._get_recovery_info(exception, context)

        return ErrorResponse(
            success=False,
            error_code=error_code,
            message=message,
            details=details,
            context=context_dict,
            recovery=recovery
        )

    def _get_error_code(self, exception: Exception, serialized: Dict[str, Any]) -> str:
        """Get standardized error code for exception."""
        # Import locally to avoid circular dependency
        from ..exceptions import MusicLibraryError

        # Use exception type mapping (prioritize over serialized error_code)
        error_code_map = {
            MusicLibraryError: 'MUSIC_LIBRARY_ERROR',
            ValueError: 'VALIDATION_ERROR',
            KeyError: 'MISSING_KEY_ERROR',
            TypeError: 'TYPE_ERROR',
            ConnectionError: 'CONNECTION_ERROR',
            TimeoutError: 'TIMEOUT_ERROR',
            PermissionError: 'PERMISSION_ERROR',
            FileNotFoundError: 'FILE_NOT_FOUND_ERROR',
            OSError: 'OS_ERROR',
        }

        for exc_type, code in error_code_map.items():
            if isinstance(exception, exc_type):
                return code

        # Fallback to serialized error_code if no type mapping found
        if 'error_code' in serialized:
            return serialized['error_code']

        return 'UNKNOWN_ERROR'

    def _get_error_message(self, exception: Exception, serialized: Dict[str, Any]) -> str:
        """Get user-friendly error message."""
        # Use serialized message if available
        if 'message' in serialized:
            message = serialized['message']
        else:
            message = str(exception)

        # Mask sensitive data if configured
        if self.config.mask_sensitive_data:
            message = self._mask_sensitive_data(message)

        return message

    def _mask_sensitive_data(self, message: str) -> str:
        """Mask sensitive information in error messages."""
        # Simple masking patterns - can be extended
        import re

        # Mask API keys
        message = re.sub(r'key=[a-zA-Z0-9_-]+', 'key=***', message)
        message = re.sub(r'password=[^&\s]+', 'password=***', message)
        message = re.sub(r'token=[a-zA-Z0-9_-]+', 'token=***', message)

        return message

    def _get_http_status_code(self, exception: Exception) -> int:
        """Map exception to HTTP status code."""
        # Import locally to avoid circular dependency
        from ..exceptions import MusicLibraryError

        status_map = {
            MusicLibraryError: 400,  # Bad Request
            ValueError: 400,         # Bad Request
            KeyError: 400,           # Bad Request
            TypeError: 400,          # Bad Request
            ConnectionError: 503,    # Service Unavailable
            TimeoutError: 504,       # Gateway Timeout
            PermissionError: 403,    # Forbidden
            FileNotFoundError: 404,  # Not Found
            OSError: 500,            # Internal Server Error
        }

        for exc_type, status in status_map.items():
            if isinstance(exception, exc_type):
                return status

        return 500  # Internal Server Error

    def _get_recovery_info(self, exception: Exception, context: ExceptionContext) -> Dict[str, Any]:
        """Get recovery information for the exception."""
        recovery = {
            'retryable': False,
            'suggested_action': 'contact_support'
        }

        # Check if any recovery strategy can handle this
        for strategy in self.recovery_strategies:
            if strategy.can_recover(exception, context):
                recovery.update({
                    'retryable': True,
                    'suggested_action': 'retry_operation',
                    'max_retries': context.max_retries,
                    'current_attempt': context.retry_count + 1
                })
                break

        # Add specific recovery suggestions based on exception type
        if isinstance(exception, ConnectionError):
            recovery['suggested_action'] = 'check_network_connectivity'
        elif isinstance(exception, TimeoutError):
            recovery['suggested_action'] = 'increase_timeout'
        elif isinstance(exception, PermissionError):
            recovery['suggested_action'] = 'check_permissions'

        return recovery
