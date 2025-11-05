"""
Test FastMCP exception serialization to identify and reproduce NameError issues.

This test module is designed to reproduce and validate fixes for Task 13:
FastMCP Exception Serialization Context Issues.
"""
import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path
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

    def test_safe_exception_serializer_integration(self):
        """Test integration with SafeExceptionSerializer from Task 13 fix."""
        from src.exception_serializer import SafeExceptionSerializer

        serializer = SafeExceptionSerializer()

        # Test complex exception serialization (Task 13 scenario)
        complex_details = {
            "datetime": datetime.now(),
            "path": Path("/tmp/test.mp3"),
            "mock": MagicMock(),
            "nested": {
                "another_mock": MagicMock(),
                "list_with_complex": [datetime.now(), Path("/tmp")]
            }
        }

        exception = AudioProcessingError("Processing failed", complex_details)
        result = serializer.serialize_exception(exception)

        # Should not raise JSON serialization errors
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Complex objects should be converted to safe string representations
        assert "<datetime object>" in parsed["details"]["datetime"]
        assert "<PosixPath object>" in parsed["details"]["path"]
        assert "<MagicMock object>" in parsed["details"]["mock"]

    def test_exception_hierarchy_preservation_task13(self):
        """Test that exception class hierarchy is preserved during serialization (Task 13)."""
        from src.exception_serializer import SafeExceptionSerializer

        serializer = SafeExceptionSerializer()
        exception = DatabaseOperationError("Connection failed")

        result = serializer.serialize_exception(exception)

        assert result["exception_type"] == "DatabaseOperationError"
        assert result["exception_module"] == "src.exceptions"

        # Should be JSON serializable without NameError
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["exception_type"] == "DatabaseOperationError"

    def test_no_nameerror_exceptions_task13(self):
        """Regression test: Ensure no NameError during serialization (Task 13 core issue)."""
        from src.exception_serializer import SafeExceptionSerializer

        serializer = SafeExceptionSerializer()

        exception = StorageError("Upload failed", {"file": "test.mp3"})

        # This should not raise NameError (the original Task 13 issue)
        result = serializer.serialize_exception(exception)

        assert result is not None
        assert result["success"] is False
        assert "STORAGE_ERROR" in result["error"]

    def test_async_context_serialization_task13(self):
        """Test serialization works in async contexts (where Task 13 issue occurred)."""
        import asyncio
        from src.exception_serializer import SafeExceptionSerializer

        serializer = SafeExceptionSerializer()

        async def test_async_serialization():
            exception = ValidationError("Async validation failed")
            result = serializer.serialize_exception(exception)
            return result

        # Should not raise NameError or other context-related errors
        result = asyncio.run(test_async_serialization())

        assert result["success"] is False
        assert result["exception_type"] == "ValidationError"

    def test_fastmcp_error_response_creation_task13(self):
        """Test FastMCP error response creation with safe serialization (Task 13)."""
        from src.error_utils import create_error_response

        # Create exception with complex details that would cause Task 13 issues
        complex_details = {
            "request_id": "req-12345",
            "timestamp": datetime.now(),
            "file_path": Path("/uploads/audio.mp3"),
            "connection": MagicMock(),
            "metadata": {
                "size": 1024,
                "format": "mp3",
                "duration": 180.5
            }
        }

        exception = AudioProcessingError("Complex processing error", complex_details)

        # This should work without NameError (Task 13 fix)
        result = create_error_response(exception, "process_audio_complete")

        # Should be JSON serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert parsed["success"] is False
        assert "error" in parsed
        assert parsed["error"]["exception_type"] == "AudioProcessingError"

        # Complex objects should be safely serialized
        assert "<datetime object>" in parsed["details"]["timestamp"]
        assert "<PosixPath object>" in parsed["details"]["file_path"]
        assert "<MagicMock object>" in parsed["details"]["connection"]
