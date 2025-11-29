"""
Integration tests for FastMCP exception serialization in real tool execution scenarios.

This test suite verifies that the enhanced exception serialization works correctly
when FastMCP tools raise exceptions during actual execution, ensuring no NameError
exceptions occur during JSON-RPC serialization.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import datetime

# Import the actual server components
from src.server import mcp
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


class TestFastMCPToolExceptionSerialization:
    """Test exception serialization in actual FastMCP tool execution contexts."""

    def test_tool_with_validation_error(self):
        """Test a tool that raises ValidationError with complex details."""
        @mcp.tool()
        def test_validation_tool(input_data: dict) -> str:
            """Test tool that validates input and raises ValidationError."""
            from src.error_utils import handle_tool_error

            # Simulate validation failure with complex details
            details = {
                "field": "url",
                "provided_value": input_data.get("url"),
                "expected_format": "http or https URL",
                "timestamp": datetime.datetime.now(),
                "request_id": "test-12345",
                "user_agent": "TestClient/1.0",
                "validation_rules": ["must start with http:// or https://", "must be valid URL"]
            }

            try:
                raise ValidationError("Invalid URL format", details=details)
            except Exception as e:
                # This should use the safe serializer and not crash
                error_response = handle_tool_error(e, "test_validation_tool", {"input_data": input_data})
                return json.dumps(error_response)  # Simulate what FastMCP does

        # Verify the tool was registered
        assert "test_validation_tool" in [tool.name for tool in mcp._tools]

    def test_tool_with_storage_error_complex_details(self):
        """Test a tool that raises StorageError with database/file handle details."""
        @mcp.tool()
        def test_storage_tool(file_path: str) -> str:
            """Test tool that simulates GCS storage operations."""
            from src.error_utils import handle_tool_error

            # Simulate storage failure with complex non-serializable details
            details = {
                "operation": "upload",
                "bucket": "loist-mvp-audio-files",
                "file_path": file_path,
                "file_size": 1024,
                "gcs_client": MagicMock(),  # Non-serializable
                "upload_stream": MagicMock(),  # Non-serializable
                "retry_count": 3,
                "last_error": "Connection timeout",
                "connection_pool": MagicMock(),  # Non-serializable
                "credentials": {"type": "service_account", "project_id": "test-project"}
            }

            try:
                raise StorageError("GCS upload failed after 3 retries", details=details)
            except Exception as e:
                error_response = handle_tool_error(e, "test_storage_tool", {"file_path": file_path})
                return json.dumps(error_response)

        assert "test_storage_tool" in [tool.name for tool in mcp._tools]

    def test_tool_with_database_error(self):
        """Test a tool that raises DatabaseOperationError with connection details."""
        @mcp.tool()
        def test_database_tool(query: str) -> str:
            """Test tool that simulates database operations."""
            from src.error_utils import handle_tool_error

            # Simulate database error with complex details
            details = {
                "operation": "SELECT",
                "table": "audio_tracks",
                "query": query,
                "connection_string": "postgresql://user:pass@host:5432/db",
                "connection": MagicMock(),  # Non-serializable
                "cursor": MagicMock(),  # Non-serializable
                "pool": MagicMock(),  # Non-serializable
                "timeout": 30,
                "isolation_level": "READ_COMMITTED",
                "error_code": "CONNECTION_LOST",
                "retry_count": 2
            }

            try:
                raise DatabaseOperationError("Database connection lost during query execution", details=details)
            except Exception as e:
                error_response = handle_tool_error(e, "test_database_tool", {"query": query})
                return json.dumps(error_response)

        assert "test_database_tool" in [tool.name for tool in mcp._tools]

    def test_tool_with_nested_exceptions(self):
        """Test a tool that raises exceptions with nested complex objects."""
        @mcp.tool()
        def test_nested_error_tool(operation: str) -> str:
            """Test tool that raises exceptions with deeply nested complex objects."""
            from src.error_utils import handle_tool_error

            # Create deeply nested complex details
            details = {
                "operation": operation,
                "context": {
                    "user": {"id": 123, "session": MagicMock()},
                    "request": {
                        "headers": {"Authorization": "Bearer token", "User-Agent": "Test/1.0"},
                        "params": {"format": "mp3", "quality": "high"},
                        "files": [MagicMock(), MagicMock()]  # Non-serializable file objects
                    },
                    "system": {
                        "timestamp": datetime.datetime.now(),
                        "version": "1.0.0",
                        "config": {
                            "database": {"pool_size": 10, "connection": MagicMock()},
                            "storage": {"bucket": "test-bucket", "client": MagicMock()},
                            "cache": {"redis_client": MagicMock(), "ttl": 3600}
                        }
                    }
                },
                "stack_trace": [
                    "frame1: function_call()",
                    "frame2: another_call()",
                    MagicMock()  # Non-serializable frame object
                ]
            }

            try:
                raise ExternalServiceError("Multiple external service failures occurred", details=details)
            except Exception as e:
                error_response = handle_tool_error(e, "test_nested_error_tool", {"operation": operation})
                return json.dumps(error_response)

        assert "test_nested_error_tool" in [tool.name for tool in mcp._tools]

    def test_tool_with_music_library_base_error(self):
        """Test a tool that raises the base MusicLibraryError class."""
        @mcp.tool()
        def test_base_error_tool(component: str) -> str:
            """Test tool that raises base MusicLibraryError."""
            from src.error_utils import handle_tool_error

            details = {
                "component": component,
                "error_category": "general_failure",
                "severity": "high",
                "requires_immediate_attention": True,
                "support_ticket": "TICKET-12345",
                "logs": ["Log entry 1", "Log entry 2", MagicMock()],  # Mixed content
                "metrics": {
                    "cpu_usage": 85.5,
                    "memory_usage": 1024,
                    "active_connections": 150,
                    "error_rate": 0.05
                }
            }

            try:
                raise MusicLibraryError(f"Critical failure in {component}", details=details)
            except Exception as e:
                error_response = handle_tool_error(e, "test_base_error_tool", {"component": component})
                return json.dumps(error_response)

        assert "test_base_error_tool" in [tool.name for tool in mcp._tools]

    @pytest.mark.asyncio
    async def test_async_tool_exception_handling(self):
        """Test exception handling in async tools (common in the codebase)."""
        @mcp.tool()
        async def test_async_tool(url: str) -> str:
            """Async test tool that raises exceptions."""
            from src.error_utils import handle_tool_error

            # Simulate async operation failure with complex details
            details = {
                "url": url,
                "http_method": "GET",
                "timeout": 30,
                "retry_count": 3,
                "aiohttp_session": MagicMock(),  # Non-serializable async session
                "response": MagicMock(),  # Non-serializable response object
                "ssl_context": MagicMock(),  # Non-serializable SSL context
                "dns_cache": {"example.com": "1.2.3.4"},
                "connection_pool": MagicMock(),  # Non-serializable pool
            }

            try:
                raise TimeoutError("HTTP request timed out after 30 seconds", details=details)
            except Exception as e:
                error_response = handle_tool_error(e, "test_async_tool", {"url": url})
                return json.dumps(error_response)

        assert "test_async_tool" in [tool.name for tool in mcp._tools]

    def test_error_response_json_serializability(self):
        """Test that all error responses from tools are valid JSON."""
        # Get all the test tools we registered
        test_tools = [tool for tool in mcp._tools if tool.name.startswith("test_")]

        for tool in test_tools:
            # Call each tool with appropriate test data
            if tool.name == "test_validation_tool":
                result = tool.func({"url": "invalid-url"})
            elif tool.name == "test_storage_tool":
                result = tool.func("/tmp/test.mp3")
            elif tool.name == "test_database_tool":
                result = tool.func("SELECT * FROM audio_tracks")
            elif tool.name == "test_nested_error_tool":
                result = tool.func("complex_operation")
            elif tool.name == "test_base_error_tool":
                result = tool.func("audio_processor")

            # Each tool returns a JSON string - verify it's valid JSON
            try:
                parsed = json.loads(result)
                assert isinstance(parsed, dict)
                assert parsed["success"] is False
                assert "error" in parsed
                assert "message" in parsed
                assert "exception_type" in parsed
                assert "exception_module" in parsed

                # Verify complex details were sanitized
                if "details" in parsed:
                    details = parsed["details"]
                    # Ensure no non-serializable objects remain
                    json.dumps(details)  # This should not raise an exception

            except json.JSONDecodeError as e:
                pytest.fail(f"Tool {tool.name} returned invalid JSON: {e}")
            except Exception as e:
                pytest.fail(f"Tool {tool.name} error response validation failed: {e}")

    def test_exception_details_preservation(self):
        """Test that important serializable details are preserved while non-serializable are sanitized."""
        from src.exception_serializer import SafeExceptionSerializer

        serializer = SafeExceptionSerializer()

        # Test with a mix of serializable and non-serializable details
        mixed_details = {
            "serializable_string": "this should work",
            "serializable_number": 42,
            "serializable_list": [1, 2, "three"],
            "serializable_dict": {"nested": "value"},
            "non_serializable_datetime": datetime.datetime.now(),
            "non_serializable_path": Path("/tmp/file"),
            "non_serializable_mock": MagicMock(),
            "mixed_list": ["string", 123, MagicMock(), datetime.datetime.now()]
        }

        exc = AudioProcessingError("Processing failed", details=mixed_details)
        result = serializer.serialize_exception(exc)

        details = result["details"]

        # Serializable items should be preserved exactly
        assert details["serializable_string"] == "this should work"
        assert details["serializable_number"] == 42
        assert details["serializable_list"] == [1, 2, "three"]
        assert details["serializable_dict"] == {"nested": "value"}

        # Non-serializable items should be converted to strings
        assert isinstance(details["non_serializable_datetime"], str)
        assert isinstance(details["non_serializable_path"], str)
        assert isinstance(details["non_serializable_mock"], str)

        # Mixed list should have non-serializable items converted
        mixed_list = details["mixed_list"]
        assert mixed_list[0] == "string"  # String preserved
        assert mixed_list[1] == 123      # Number preserved
        assert isinstance(mixed_list[2], str)  # Mock converted to string
        assert isinstance(mixed_list[3], str)  # Datetime converted to string

    def test_backwards_compatibility(self):
        """Test that existing error handling code continues to work."""
        from src.error_utils import create_error_response

        # Test with traditional exception (no details)
        exc = ValueError("Simple error")
        response = create_error_response(exc)

        # Should have all expected fields
        assert response["success"] is False
        assert response["error"] == "UNKNOWN_ERROR"  # Since ValueError doesn't have specific mapping
        assert response["message"] == "Simple error"
        assert response["exception_type"] == "ValueError"
        assert response["exception_module"] == "builtins"

        # Should be JSON serializable
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        assert parsed["message"] == "Simple error"
