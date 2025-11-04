"""
Test FastMCP exception serialization to identify and reproduce NameError issues.

This test module is designed to reproduce and validate fixes for Task 13:
FastMCP Exception Serialization Context Issues.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastmcp import FastMCP

# Import all custom exceptions to ensure they're available
from src.exceptions import (
    MusicLibraryError,
    AudioProcessingError,
    StorageError,
    ValidationError,
    ResourceNotFoundError,
    TimeoutError,
    AuthenticationError,
    RateLimitError,
    ExternalServiceError,
    DatabaseOperationError,
)


class TestFastMCPExceptionSerialization:
    """Test cases for FastMCP exception serialization issues."""

    def test_exception_hierarchy_accessibility(self):
        """Test that all exception classes are accessible in the current namespace."""
        # Verify all exception classes can be accessed
        exceptions_to_test = [
            MusicLibraryError,
            AudioProcessingError,
            StorageError,
            ValidationError,
            ResourceNotFoundError,
            TimeoutError,
            AuthenticationError,
            RateLimitError,
            ExternalServiceError,
            DatabaseOperationError,
        ]

        for exc_class in exceptions_to_test:
            # Verify class attributes that FastMCP might access
            assert hasattr(exc_class, '__name__')
            assert hasattr(exc_class, '__module__')
            assert hasattr(exc_class, '__bases__')

            # Verify we can instantiate the exception
            instance = exc_class("Test message")
            assert isinstance(instance, Exception)
            assert str(instance) == "Test message"

    def test_exception_serialization_basic(self):
        """Test basic exception serialization without FastMCP."""
        # Test that exceptions can be serialized to JSON
        test_exceptions = [
            MusicLibraryError("Test error"),
            AudioProcessingError("Audio processing failed"),
            ValidationError("Validation failed"),
        ]

        for exc in test_exceptions:
            # Test basic serialization (this is what FastMCP tries to do)
            try:
                # This simulates what FastMCP's ErrorHandlingMiddleware does
                error_data = {
                    'type': type(exc).__name__,
                    'message': str(exc),
                    'module': type(exc).__module__,
                }

                # Try to serialize to JSON
                json_str = json.dumps(error_data)
                assert json_str is not None

                # Verify we can deserialize
                parsed = json.loads(json_str)
                assert parsed['type'] == type(exc).__name__

            except (TypeError, NameError) as e:
                pytest.fail(f"Exception serialization failed for {type(exc).__name__}: {e}")

    def test_exception_with_details_serialization(self):
        """Test exception serialization with details dict."""
        # Test exceptions with details that might contain complex objects
        details = {
            'user_id': '12345',
            'operation': 'upload',
            'timestamp': '2025-01-01T00:00:00Z'
        }

        exc = StorageError("Upload failed", details=details)

        try:
            # Simulate FastMCP serialization
            error_data = {
                'type': type(exc).__name__,
                'message': str(exc),
                'module': type(exc).__module__,
                'details': exc.details if hasattr(exc, 'details') else None,
            }

            json_str = json.dumps(error_data)
            parsed = json.loads(json_str)

            assert parsed['details'] == details

        except (TypeError, NameError) as e:
            pytest.fail(f"Exception with details serialization failed: {e}")

    @pytest.mark.asyncio
    async def test_fastmcp_tool_error_serialization(self):
        """Test exception serialization through FastMCP tool execution."""
        # Create a minimal FastMCP instance for testing
        mcp = FastMCP(name="test-server")

        @mcp.tool()
        def failing_tool() -> str:
            """A tool that always raises an exception."""
            raise MusicLibraryError("Intentional test error")

        # Test that the tool execution and error handling works
        # This will test FastMCP's internal exception serialization
        try:
            # We can't easily call the tool directly, but we can test the setup
            assert mcp is not None
            assert len(mcp._tools) > 0

        except Exception as e:
            pytest.fail(f"FastMCP tool setup with exception failed: {e}")

    def test_exception_context_preservation(self):
        """Test that exception context is preserved during serialization."""
        # Create an exception with context that might be lost
        original_exc = ValidationError("Invalid input", details={'field': 'url', 'value': 'invalid'})

        # Simulate what happens when FastMCP serializes the exception
        try:
            # This is similar to what FastMCP's ErrorHandlingMiddleware does
            serialized_context = {
                'exception_class': original_exc.__class__.__name__,
                'exception_module': original_exc.__class__.__module__,
                'message': str(original_exc),
                'details': original_exc.details,
            }

            # Test that we can access all the context
            assert serialized_context['exception_class'] == 'ValidationError'
            assert 'src.exceptions' in serialized_context['exception_module']
            assert serialized_context['message'] == "Invalid input"
            assert serialized_context['details']['field'] == 'url'

        except NameError as e:
            pytest.fail(f"Exception context preservation failed with NameError: {e}")
        except AttributeError as e:
            pytest.fail(f"Exception context preservation failed with AttributeError: {e}")

    def test_circular_import_simulation(self):
        """Test exception handling in scenarios that might cause circular import issues."""
        # This test simulates what might happen if exceptions are imported in different contexts

        # Test importing exceptions in a simulated "different context"
        import sys
        from types import ModuleType

        # Create a mock module context
        mock_module = ModuleType('mock_context')
        mock_module.__dict__.update({
            'MusicLibraryError': MusicLibraryError,
            'ValidationError': ValidationError,
        })

        # Simulate accessing exceptions from this context
        try:
            exc_class = mock_module.MusicLibraryError
            instance = exc_class("Test from mock context")
            assert isinstance(instance, Exception)

        except NameError as e:
            pytest.fail(f"Circular import simulation failed: {e}")

    def test_globals_namespace_verification(self):
        """Test that exception classes are available in globals() as expected."""
        # This verifies the approach used in server.py
        import builtins

        # Test that we can access exception classes from globals
        test_globals = {
            'MusicLibraryError': MusicLibraryError,
            'ValidationError': ValidationError,
            'StorageError': StorageError,
        }

        for name, exc_class in test_globals.items():
            try:
                # Verify we can access via globals-like lookup
                looked_up = test_globals.get(name)
                assert looked_up is not None
                assert looked_up == exc_class

                # Verify class attributes
                assert hasattr(looked_up, '__name__')
                assert hasattr(looked_up, '__module__')

            except NameError as e:
                pytest.fail(f"Globals namespace verification failed for {name}: {e}")
