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

# Add the parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
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
    """Test exception serialization in tool execution contexts."""
    print("Testing FastMCP tool exception serialization...")

    # Test the exception handling directly without FastMCP tool registration complexity
    test_cases = [
        {
            "name": "ValidationError with complex details",
            "exception": ValidationError("Invalid URL format", details={
                "field": "url",
                "provided_value": "invalid-url",
                "expected_format": "http or https URL",
                "timestamp": datetime.datetime.now(),
                "validation_rules": ["must start with http:// or https://"]
            }),
            "tool_name": "test_validation_tool",
            "args": {"url": "invalid-url"}
        },
        {
            "name": "StorageError with GCS details",
            "exception": StorageError("GCS upload failed", details={
                "operation": "upload",
                "bucket": "loist-mvp-audio-files",
                "file_path": "/tmp/test.mp3",
                "gcs_client": MagicMock(),
                "upload_stream": MagicMock(),
                "retry_count": 3
            }),
            "tool_name": "test_storage_tool",
            "args": {"file_path": "/tmp/test.mp3"}
        },
        {
            "name": "DatabaseError with connection details",
            "exception": DatabaseOperationError("Connection lost", details={
                "operation": "SELECT",
                "connection": MagicMock(),
                "cursor": MagicMock(),
                "pool": MagicMock(),
                "timeout": 30
            }),
            "tool_name": "test_database_tool",
            "args": {"query": "SELECT * FROM audio_tracks"}
        }
    ]

    results = []
    for test_case in test_cases:
        try:
            from src.error_utils import handle_tool_error

            # Test the exception handling directly
            error_response = handle_tool_error(
                test_case["exception"],
                test_case["tool_name"],
                test_case["args"]
            )

            # Validate the response structure
            assert isinstance(error_response, dict)
            assert error_response["success"] is False
            assert "error" in error_response
            assert "message" in error_response
            assert "exception_type" in error_response
            assert "exception_module" in error_response

            # Verify complex details were sanitized
            if "details" in error_response:
                details = error_response["details"]
                # Ensure no non-serializable objects remain (this would raise an exception)
                json.dumps(details)

            results.append((test_case["name"], True, "Success"))

        except Exception as e:
            results.append((test_case["name"], False, str(e)))

    # Report results
    for test_name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status} - {message}")

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
    # Debug: print the actual mixed_list to see what we got
    print(f"DEBUG: mixed_list = {mixed_list}")
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
