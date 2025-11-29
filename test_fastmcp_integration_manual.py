#!/usr/bin/env python3
"""
Manual integration test for FastMCP exception serialization.
Run this directly to avoid pytest dependency issues.
"""
import sys
import json
import datetime
from pathlib import Path
from unittest.mock import MagicMock

# Add the src directory to Python path
parent_dir = Path(__file__).parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

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


def test_fastmcp_tool_exception_serialization():
    """Test exception serialization in FastMCP tool execution contexts."""
    print("Testing FastMCP tool exception serialization...")

    # Register test tools that raise exceptions
    @mcp.tool()
    def test_validation_tool(input_data: dict) -> str:
        """Test tool that validates input and raises ValidationError."""
        from src.error_utils import handle_tool_error

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
            error_response = handle_tool_error(e, "test_validation_tool", {"input_data": input_data})
            return json.dumps(error_response)

    @mcp.tool()
    def test_storage_tool(file_path: str) -> str:
        """Test tool that simulates GCS storage operations."""
        from src.error_utils import handle_tool_error

        details = {
            "operation": "upload",
            "bucket": "loist-mvp-audio-files",
            "file_path": file_path,
            "file_size": 1024,
            "gcs_client": MagicMock(),
            "upload_stream": MagicMock(),
            "retry_count": 3,
            "last_error": "Connection timeout",
            "connection_pool": MagicMock(),
            "credentials": {"type": "service_account", "project_id": "test-project"}
        }

        try:
            raise StorageError("GCS upload failed after 3 retries", details=details)
        except Exception as e:
            error_response = handle_tool_error(e, "test_storage_tool", {"file_path": file_path})
            return json.dumps(error_response)

    @mcp.tool()
    def test_database_tool(query: str) -> str:
        """Test tool that simulates database operations."""
        from src.error_utils import handle_tool_error

        details = {
            "operation": "SELECT",
            "table": "audio_tracks",
            "query": query,
            "connection_string": "postgresql://user:pass@host:5432/db",
            "connection": MagicMock(),
            "cursor": MagicMock(),
            "pool": MagicMock(),
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

    # Test the tools
    test_cases = [
        ("test_validation_tool", {"url": "invalid-url"}),
        ("test_storage_tool", "/tmp/test.mp3"),
        ("test_database_tool", "SELECT * FROM audio_tracks"),
    ]

    results = []
    for tool_name, args in test_cases:
        try:
            # Find the tool
            tool = None
            for t in mcp._tools:
                if t.name == tool_name:
                    tool = t
                    break

            if not tool:
                results.append((tool_name, False, f"Tool {tool_name} not found"))
                continue

            # Call the tool
            if tool_name == "test_validation_tool":
                result = tool.func(args)
            else:
                result = tool.func(args)

            # Parse the JSON result
            parsed = json.loads(result)

            # Validate the response structure
            assert isinstance(parsed, dict)
            assert parsed["success"] is False
            assert "error" in parsed
            assert "message" in parsed
            assert "exception_type" in parsed
            assert "exception_module" in parsed

            # Verify complex details were sanitized
            if "details" in parsed:
                details = parsed["details"]
                # Ensure no non-serializable objects remain (this would raise an exception)
                json.dumps(details)

            results.append((tool_name, True, "Success"))

        except Exception as e:
            results.append((tool_name, False, str(e)))

    # Report results
    for tool_name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{tool_name}: {status} - {message}")

    return all(success for _, success, _ in results)


def test_exception_details_preservation():
    """Test that important serializable details are preserved while non-serializable are sanitized."""
    print("\nTesting exception details preservation...")

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

    print("✅ Exception details preservation test passed")
    return True


def test_backwards_compatibility():
    """Test that existing error handling code continues to work."""
    print("\nTesting backwards compatibility...")

    from src.error_utils import create_error_response

    # Test with traditional exception (no details)
    exc = ValueError("Simple error")
    response = create_error_response(exc)

    # Should have all expected fields
    assert response["success"] is False
    assert response["error"] == "UNKNOWN_ERROR"
    assert response["message"] == "Simple error"
    assert response["exception_type"] == "ValueError"
    assert response["exception_module"] == "builtins"

    # Should be JSON serializable
    json_str = json.dumps(response)
    parsed = json.loads(json_str)
    assert parsed["message"] == "Simple error"

    print("✅ Backwards compatibility test passed")
    return True


if __name__ == "__main__":
    print("FastMCP Exception Serialization Integration Test")
    print("=" * 60)

    tests = [
        ("FastMCP Tool Exception Serialization", test_fastmcp_tool_exception_serialization),
        ("Exception Details Preservation", test_exception_details_preservation),
        ("Backwards Compatibility", test_backwards_compatibility),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            import traceback
            print(f"❌ {test_name}: Test crashed with {e}")
            print(f"Traceback: {traceback.format_exc()}")
            results.append((test_name, False))

    print("\n" + "=" * 60)
    print("SUMMARY:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n🎉 All FastMCP integration tests passed!")
        print("✅ Exception serialization works correctly in tool execution contexts!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed.")
        sys.exit(1)
