"""
Comprehensive tests for the Unified Exception Handling Framework.

Tests cover:
- ExceptionHandler core functionality
- ExceptionContext system
- Recovery strategies
- FastMCP integration
- Error response standardization
- Configuration options
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.exceptions import MusicLibraryError
from src.exceptions_new import (
    ExceptionHandler,
    ExceptionConfig,
    ExceptionContext,
    RecoveryStrategy,
    DatabaseRecoveryStrategy,
    FastMCPExceptionMiddleware,
)
from src.exceptions_new.handler import ErrorResponse
from src.exceptions_new.context import OperationType
from src.exceptions import MusicLibraryError, ValidationError


class TestExceptionContext:
    """Test ExceptionContext functionality."""

    def test_basic_context_creation(self):
        """Test creating a basic exception context."""
        context = ExceptionContext(
            operation="database_query",
            component="database.operations"
        )

        assert context.operation == "database_query"
        assert context.component == "database.operations"
        assert context.retry_count == 0
        assert context.can_retry() is True

    def test_context_with_metadata(self):
        """Test context with additional metadata."""
        context = ExceptionContext(
            operation="file_upload",
            component="storage.gcs",
            user_id="user123",
            request_id="req456"
        )

        context.add_metadata("file_size", 1024)
        context.add_metadata("content_type", "audio/mp3")

        assert context.user_id == "user123"
        assert context.request_id == "req456"
        assert context.get_metadata("file_size") == 1024
        assert context.get_metadata("content_type") == "audio/mp3"
        assert context.get_metadata("nonexistent", "default") == "default"

    def test_retry_logic(self):
        """Test retry count and limits."""
        context = ExceptionContext(
            operation="api_call",
            component="external.service",
            max_retries=2
        )

        assert context.can_retry() is True
        assert context.retry_count == 0

        context.increment_retry()
        assert context.retry_count == 1
        assert context.can_retry() is True

        context.increment_retry()
        assert context.retry_count == 2
        assert context.can_retry() is False

    def test_context_to_dict(self):
        """Test context serialization."""
        context = ExceptionContext(
            operation="search",
            component="database.search",
            user_id="user123",
            operation_type=OperationType.SEARCH_OPERATION
        )
        context.add_metadata("query", "test query")

        data = context.to_dict()

        assert data["operation"] == "search"
        assert data["component"] == "database.search"
        assert data["user_id"] == "user123"
        assert data["operation_type"] == "search_operation"
        assert data["metadata"]["query"] == "test query"


class TestExceptionConfig:
    """Test ExceptionConfig functionality."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExceptionConfig()

        assert config.enable_detailed_errors is True
        assert config.include_stack_traces is False
        assert config.mask_sensitive_data is True
        assert config.log_level == "ERROR"
        assert config.enable_recovery is True
        assert config.max_retry_attempts == 3

    def test_production_config(self):
        """Test production-optimized configuration."""
        config = ExceptionConfig().for_production()

        assert config.enable_detailed_errors is True
        assert config.include_stack_traces is False
        assert config.mask_sensitive_data is True
        assert config.log_level == "WARNING"
        assert config.enable_recovery is True

    def test_development_config(self):
        """Test development-optimized configuration."""
        config = ExceptionConfig().for_development()

        assert config.enable_detailed_errors is True
        assert config.include_stack_traces is True
        assert config.mask_sensitive_data is False
        assert config.log_level == "DEBUG"

    def test_testing_config(self):
        """Test testing-optimized configuration."""
        config = ExceptionConfig().for_testing()

        assert config.enable_recovery is False  # Disabled for predictability
        assert config.fastmcp_integration is False


class TestErrorResponse:
    """Test ErrorResponse functionality."""

    def test_basic_error_response(self):
        """Test creating a basic error response."""
        response = ErrorResponse(
            success=False,
            error_code="VALIDATION_ERROR",
            message="Invalid input"
        )

        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Invalid input"
        assert response.details == {}
        assert response.context == {}
        assert response.recovery == {}

    def test_error_response_with_details(self):
        """Test error response with full details."""
        response = ErrorResponse(
            success=False,
            error_code="DATABASE_ERROR",
            message="Connection failed",
            details={"host": "localhost", "port": 5432},
            context={"operation": "query", "component": "database"},
            recovery={"retryable": True, "suggested_action": "retry"}
        )

        data = response.to_dict()

        assert data["success"] is False
        assert data["error"]["code"] == "DATABASE_ERROR"
        assert data["error"]["message"] == "Connection failed"
        assert data["error"]["details"]["host"] == "localhost"
        assert data["error"]["context"]["operation"] == "query"
        assert data["error"]["recovery"]["retryable"] is True


class TestRecoveryStrategies:
    """Test recovery strategy functionality."""

    def test_database_recovery_strategy(self):
        """Test database recovery strategy."""
        strategy = DatabaseRecoveryStrategy(max_retries=2, base_delay=0.01)

        context = ExceptionContext(
            operation="db_query",
            component="database",
            max_retries=2
        )

        # Test with non-recoverable exception
        assert not strategy.can_recover(ValueError("test"), context)

        # Test with recoverable exception
        from psycopg2 import OperationalError
        op_error = OperationalError("connection failed")

        assert strategy.can_recover(op_error, context)

        # Test recovery (should raise to trigger retry)
        with pytest.raises(OperationalError):
            strategy.recover(op_error, context)

        assert context.retry_count == 1

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery strategy."""
        from src.exceptions.recovery import CircuitBreakerRecoveryStrategy
        strategy = CircuitBreakerRecoveryStrategy(failure_threshold=2, recovery_timeout=1)

        context = ExceptionContext(operation="api_call", component="external.api")

        # Initially closed
        assert strategy.can_recover(Exception("test"), context)

        # Record failures to open circuit
        strategy._record_failure()
        strategy._record_failure()

        # Should be open now
        assert not strategy.can_recover(Exception("test"), context)

    def test_fallback_recovery(self):
        """Test fallback recovery strategy."""
        from src.exceptions.recovery import FallbackRecoveryStrategy

        def fallback_func(exception, context):
            return "fallback_result"

        strategy = FallbackRecoveryStrategy(fallback_func)

        context = ExceptionContext(operation="operation", component="component")

        assert strategy.can_recover(Exception("test"), context)

        result = strategy.recover(Exception("test"), context)
        assert result == "fallback_result"

    def test_composite_recovery(self):
        """Test composite recovery strategy."""
        from src.exceptions.recovery import CompositeRecoveryStrategy, FallbackRecoveryStrategy

        # Create strategies
        fallback_strategy = FallbackRecoveryStrategy(lambda e, c: "recovered")
        strategies = [DatabaseRecoveryStrategy(), fallback_strategy]

        composite = CompositeRecoveryStrategy(strategies)

        context = ExceptionContext(operation="test", component="test")

        # Should be able to recover with fallback
        assert composite.can_recover(Exception("test"), context)

        # Recovery should work
        result = composite.recover(Exception("test"), context)
        assert result == "recovered"


class TestExceptionHandler:
    """Test ExceptionHandler core functionality."""

    @pytest.fixture
    def handler(self):
        """Create a test exception handler."""
        config = ExceptionConfig().for_testing()
        return ExceptionHandler(config)

    @pytest.fixture
    def context(self):
        """Create a test exception context."""
        return ExceptionContext(
            operation="test_operation",
            component="test.component"
        )

    def test_handler_initialization(self, handler):
        """Test handler initializes correctly."""
        assert handler.config is not None
        assert handler.serializer is not None
        assert handler.recovery_strategies == []

    def test_handle_exception_basic(self, handler, context):
        """Test basic exception handling."""
        exception = ValueError("test error")

        response = handler.handle_exception(exception, context)

        assert isinstance(response, ErrorResponse)
        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert "test error" in response.message

    def test_handle_exception_with_recovery(self, handler, context):
        """Test exception handling with recovery strategy."""
        from src.exceptions.recovery import FallbackRecoveryStrategy

        # Add fallback recovery
        def fallback_func(e, c):
            return "recovered"

        recovery = FallbackRecoveryStrategy(fallback_func)
        handler.add_recovery_strategy(recovery)

        exception = Exception("test error")

        response = handler.handle_exception(exception, context)

        # Should still get error response since fallback doesn't prevent error response
        assert response.success is False

    def test_handle_and_raise(self, handler, context):
        """Test handle and raise functionality."""
        exception = ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            handler.handle_and_raise(exception, context)

    def test_handle_for_http(self, handler, context):
        """Test HTTP response generation."""
        exception = ValidationError("invalid input")

        response_dict, status_code = handler.handle_for_http(exception, context)

        assert response_dict["success"] is False
        assert status_code == 400  # Bad Request for ValidationError

    def test_error_code_mapping(self, handler, context):
        """Test error code mapping for different exception types."""
        test_cases = [
            (ValueError("test"), "VALIDATION_ERROR"),
            (KeyError("test"), "MISSING_KEY_ERROR"),
            (TypeError("test"), "TYPE_ERROR"),
            (ConnectionError("test"), "CONNECTION_ERROR"),
            (TimeoutError("test"), "TIMEOUT_ERROR"),
            (MusicLibraryError("test"), "MUSIC_LIBRARY_ERROR"),
        ]

        for exception, expected_code in test_cases:
            response = handler.handle_exception(exception, context)
            assert response.error_code == expected_code

    def test_sensitive_data_masking(self):
        """Test sensitive data masking in error messages."""
        config = ExceptionConfig(mask_sensitive_data=True)
        handler = ExceptionHandler(config)
        context = ExceptionContext(operation="test", component="test")

        # Test with sensitive data in message
        exception = Exception("API key=abc123 password=secret token=xyz789")

        response = handler.handle_exception(exception, context)

        assert "key=***" in response.message
        assert "password=***" in response.message
        assert "token=***" in response.message
        assert "abc123" not in response.message

    def test_http_status_code_mapping(self, handler, context):
        """Test HTTP status code mapping."""
        test_cases = [
            (ValidationError("test"), 400),
            (ValueError("test"), 400),
            (ConnectionError("test"), 503),
            (TimeoutError("test"), 504),
            (PermissionError("test"), 403),
            (FileNotFoundError("test"), 404),
            (Exception("test"), 500),
        ]

        for exception, expected_status in test_cases:
            _, status_code = handler.handle_for_http(exception, context)
            assert status_code == expected_status

    @patch('src.exceptions_new.handler.logger')
    def test_structured_logging(self, mock_logger, context):
        """Test structured logging functionality."""
        config = ExceptionConfig(enable_structured_logging=True, include_stack_traces=False)
        handler = ExceptionHandler(config)

        exception = ValueError("test error")

        handler.handle_exception(exception, context)

        # Verify structured logging was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "extra" in call_args.kwargs
        extra = call_args.kwargs["extra"]
        assert extra["exception_type"] == "ValueError"
        assert extra["operation"] == "test_operation"
        assert extra["component"] == "test.component"


class TestFastMCPIntegration:
    """Test FastMCP integration functionality."""

    @pytest.fixture
    def handler(self):
        """Create a test exception handler."""
        config = ExceptionConfig().for_testing()
        return ExceptionHandler(config)

    @pytest.fixture
    def middleware(self, handler):
        """Create FastMCP middleware."""
        return FastMCPExceptionMiddleware(handler)

    def test_middleware_creation(self, middleware):
        """Test middleware initializes correctly."""
        assert middleware.handler is not None

    def test_middleware_process_exception(self, middleware):
        """Test middleware exception processing."""
        context = ExceptionContext(
            operation="mcp_call",
            component="tools.test"
        )

        exception = ValidationError("invalid MCP call")

        response = middleware.process_exception(exception, context)

        assert response["success"] is False
        assert response["error"]["code"] == "VALIDATION_ERROR"

    def test_middleware_without_context(self, middleware):
        """Test middleware with default context."""
        exception = ValueError("test error")

        response = middleware.process_exception(exception)

        assert response["success"] is False
        assert response["error"]["context"]["operation"] == "fastmcp_operation"

    def test_create_fastmcp_error_handler(self, handler):
        """Test FastMCP error handler creation."""
        from src.exceptions_new.fastmcp_integration import create_fastmcp_error_handler

        error_handler = create_fastmcp_error_handler(handler)

        exception = Exception("test")

        response = error_handler(exception, operation="test_op", component="test.comp")

        assert response["success"] is False

    @patch('src.exceptions_new.fastmcp_integration.get_mcp_instance')
    def test_setup_fastmcp_integration(self, mock_get_mcp, handler):
        """Test FastMCP integration setup."""
        from src.exceptions_new.fastmcp_integration import setup_fastmcp_exception_handling

        mock_mcp = Mock()
        mock_get_mcp.return_value = mock_mcp

        # Should not raise exception
        setup_fastmcp_exception_handling(handler)

    def test_global_handler_management(self, handler):
        """Test global exception handler management."""
        from src.exceptions_new.fastmcp_integration import (
            set_global_exception_handler,
            get_global_exception_handler
        )

        # Initially should raise
        with pytest.raises(RuntimeError):
            get_global_exception_handler()

        # Set handler
        set_global_exception_handler(handler)

        # Now should return handler
        retrieved = get_global_exception_handler()
        assert retrieved is handler

    def test_initialize_exception_framework(self):
        """Test complete framework initialization."""
        from src.exceptions_new.fastmcp_integration import initialize_exception_framework

        handler = initialize_exception_framework()

        assert isinstance(handler, ExceptionHandler)
        assert len(handler.recovery_strategies) > 0  # Should have default strategies


class TestExceptionFrameworkIntegration:
    """Integration tests for the complete exception framework."""

    def test_end_to_end_exception_handling(self):
        """Test complete exception handling flow."""
        # Initialize framework
        from src.exceptions_new.fastmcp_integration import initialize_exception_framework

        handler = initialize_exception_framework()

        # Create context
        context = ExceptionContext(
            operation="process_audio",
            component="tools.process_audio",
            user_id="test_user",
            request_id="test_request"
        )

        # Handle exception
        exception = ValidationError("Invalid audio file format")
        response = handler.handle_exception(exception, context)

        # Verify response structure
        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.context["operation"] == "process_audio"
        assert response.context["user_id"] == "test_user"

        # Test HTTP response
        http_response, status_code = handler.handle_for_http(exception, context)
        assert status_code == 400
        assert http_response["success"] is False

    def test_recovery_integration(self):
        """Test recovery strategies in complete flow."""
        from src.exceptions.recovery import FallbackRecoveryStrategy

        config = ExceptionConfig().for_testing()
        handler = ExceptionHandler(config)

        # Add recovery strategy
        def fallback_func(e, c):
            return {"recovered": True, "data": "fallback_data"}

        recovery = FallbackRecoveryStrategy(fallback_func)
        handler.add_recovery_strategy(recovery)

        context = ExceptionContext(
            operation="external_api_call",
            component="external.service"
        )

        # Exception should be recoverable
        exception = ConnectionError("API unavailable")

        # This should attempt recovery but still return error response
        response = handler.handle_exception(exception, context)

        assert response.success is False
        assert response.recovery["retryable"] is True

    def test_configuration_integration(self):
        """Test different configurations work end-to-end."""
        configs = [
            ExceptionConfig().for_production(),
            ExceptionConfig().for_development(),
            ExceptionConfig().for_testing(),
        ]

        context = ExceptionContext(operation="test", component="test")

        for config in configs:
            handler = ExceptionHandler(config)
            exception = ValueError("test error")

            response = handler.handle_exception(exception, context)

            # All should produce valid responses
            assert isinstance(response, ErrorResponse)
            assert response.success is False
            assert response.error_code == "VALIDATION_ERROR"

    def test_json_serialization(self):
        """Test that all responses can be JSON serialized."""
        handler = ExceptionHandler(ExceptionConfig().for_testing())
        context = ExceptionContext(operation="test", component="test")

        # Test various exception types
        exceptions = [
            ValueError("test"),
            MusicLibraryError("test"),
            ValidationError("test"),
            ConnectionError("test"),
        ]

        for exception in exceptions:
            response = handler.handle_exception(exception, context)

            # Should be JSON serializable
            json_str = json.dumps(response.to_dict())
            parsed = json.loads(json_str)

            assert parsed["success"] is False
            assert "error" in parsed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
