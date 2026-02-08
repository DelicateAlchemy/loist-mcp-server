#!/usr/bin/env python3
"""
Test the integration of safe exception serialization with error_utils.py
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock

# Add the parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from src.exceptions import ValidationError, StorageError, MusicLibraryError
from src.error_utils import create_error_response, log_error, handle_tool_error


def test_create_error_response_with_safe_serializer():
    """Test that create_error_response uses safe serialization."""
    print("Testing create_error_response with safe serializer...")

    # Test with simple exception
    exc = ValidationError("Test validation error")
    response = create_error_response(exc)

    assert response["success"] is False
    assert "error" in response
    assert "message" in response
    assert response["exception_type"] == "ValidationError"
    assert response["exception_module"] == "src.exceptions"
    print("✅ Basic error response creation")

    # Test with exception containing complex details
    import datetime
    complex_details = {
        "timestamp": datetime.datetime.now(),
        "connection": MagicMock(),
        "serializable_data": {"user_id": 123}
    }
    exc_complex = StorageError("Storage operation failed", details=complex_details)
    response_complex = create_error_response(exc_complex)

    # Verify complex objects were sanitized
    assert response_complex["success"] is False
    assert "details" in response_complex
    details = response_complex["details"]

    # Serializable data should be preserved
    assert details["serializable_data"]["user_id"] == 123

    # Non-serializable objects should be converted to strings
    assert isinstance(details["timestamp"], str)
    assert isinstance(details["connection"], str)
    assert "<MagicMock object>" in details["connection"]
    print("✅ Complex details sanitization in error response")

    return True


def test_log_error_with_safe_serializer():
    """Test that log_error uses safe serialization (without actually logging)."""
    print("\nTesting log_error with safe serializer...")

    # Test with exception containing complex details
    complex_details = {
        "file_handle": MagicMock(),
        "database_cursor": MagicMock(),
        "operation": "upload",
        "user_id": 456
    }
    exc = MusicLibraryError("Database operation failed", details=complex_details)

    # This should not raise any exceptions and should handle complex details safely
    try:
        # We can't easily test the actual logging without mocking the logger
        # But we can verify the function doesn't crash
        log_error(exc, context={"tool": "test_tool"}, level="debug")
        print("✅ Log error handling with complex details")
        return True
    except Exception as e:
        print(f"❌ Log error failed: {e}")
        return False


def test_handle_tool_error_integration():
    """Test handle_tool_error with the new safe serialization."""
    print("\nTesting handle_tool_error integration...")

    # Test with exception containing non-serializable objects
    complex_details = {
        "gcs_client": MagicMock(),
        "upload_stream": MagicMock(),
        "file_path": Path("/tmp/test.mp3"),
        "metadata": {"title": "Test Song", "artist": "Test Artist"}
    }
    exc = StorageError("GCS upload failed", details=complex_details)

    # This should work without raising serialization errors
    try:
        error_response = handle_tool_error(exc, "process_audio_complete", {"source": {"type": "http_url"}})

        # Verify the response structure
        assert isinstance(error_response, dict)
        assert error_response["success"] is False
        assert "error" in error_response
        assert "message" in error_response
        assert "exception_type" in error_response
        assert error_response["exception_type"] == "StorageError"

        # Verify details were safely serialized
        if "details" in error_response:
            details = error_response["details"]
            # Serializable metadata should be preserved
            assert details["metadata"]["title"] == "Test Song"
            # Non-serializable objects should be strings
            assert isinstance(details["gcs_client"], str)
            assert isinstance(details["upload_stream"], str)
            assert isinstance(details["file_path"], str)

        print("✅ Handle tool error integration with complex objects")
        return True

    except Exception as e:
        print(f"❌ Handle tool error integration failed: {e}")
        return False


def test_backward_compatibility():
    """Test that the changes maintain backward compatibility."""
    print("\nTesting backward compatibility...")

    # Test that the response structure is still compatible
    exc = ValidationError("Simple error")
    response = create_error_response(exc)

    # Should have the expected fields
    required_fields = ["success", "error", "message", "exception_type", "exception_module"]
    for field in required_fields:
        assert field in response, f"Missing required field: {field}"

    # Success should be False
    assert response["success"] is False

    # Error should be a string
    assert isinstance(response["error"], str)

    print("✅ Backward compatibility maintained")
    return True


def test_json_serialization_of_responses():
    """Test that error responses can be JSON serialized (critical for FastMCP)."""
    print("\nTesting JSON serialization of error responses...")

    test_cases = [
        ValidationError("Simple validation error"),
        StorageError("Storage failed", details={"path": "/tmp/file.mp3"}),
        MusicLibraryError("Complex error", details={
            "connection": MagicMock(),
            "timestamp": "2025-01-01T00:00:00Z",
            "nested": {"data": [1, 2, {"key": "value"}]}
        })
    ]

    for i, exc in enumerate(test_cases):
        try:
            response = create_error_response(exc)

            # This is the critical test - can the response be JSON serialized?
            json_str = json.dumps(response)

            # Verify we can parse it back
            parsed = json.loads(json_str)

            # Verify key fields are preserved
            assert parsed["success"] is False
            assert "error" in parsed
            assert "message" in parsed

            print(f"✅ Error response JSON serialization - case {i+1}")

        except Exception as e:
            print(f"❌ Error response JSON serialization failed for case {i+1}: {e}")
            return False

    return True


if __name__ == "__main__":
    print("Error Utils Integration Test Suite")
    print("=" * 50)

    tests = [
        ("Create Error Response with Safe Serializer", test_create_error_response_with_safe_serializer),
        ("Log Error with Safe Serializer", test_log_error_with_safe_serializer),
        ("Handle Tool Error Integration", test_handle_tool_error_integration),
        ("Backward Compatibility", test_backward_compatibility),
        ("JSON Serialization of Responses", test_json_serialization_of_responses),
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

    print("\n" + "=" * 50)
    print("SUMMARY:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n🎉 All error utils integration tests passed!")
        print("✅ Safe exception serialization is properly integrated!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed.")
        sys.exit(1)
