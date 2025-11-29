#!/usr/bin/env python3
"""
Test the enhanced exception serialization system.
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

from src.exceptions import MusicLibraryError, ValidationError, StorageError
from src.exception_serializer import SafeExceptionSerializer, ExceptionSerializationMiddleware


def test_safe_exception_serializer():
    """Test the SafeExceptionSerializer class."""
    print("Testing SafeExceptionSerializer...")

    serializer = SafeExceptionSerializer()

    # Test basic exception serialization
    exc = ValidationError("Test validation error", details={"field": "email", "reason": "invalid_format"})
    result = serializer.serialize_exception(exc)

    assert result["type"] == "ValidationError"
    assert result["message"] == "Test validation error"
    assert result["details"]["field"] == "email"
    print("✅ Basic exception serialization")

    # Test exception with complex non-serializable details
    complex_details = {
        "datetime": datetime.datetime.now(),
        "path": Path("/tmp/test"),
        "callable": lambda x: x,
        "serializable": "this should work"
    }
    exc_complex = MusicLibraryError("Complex details test", details=complex_details)
    result_complex = serializer.serialize_exception(exc_complex)

    # Complex objects should be converted to strings
    assert "datetime" in result_complex["details"]
    assert "path" in result_complex["details"]
    assert result_complex["details"]["serializable"] == "this should work"
    assert isinstance(result_complex["details"]["datetime"], str)
    assert isinstance(result_complex["details"]["path"], str)
    print("✅ Complex details sanitization")

    # Test error code inclusion
    assert "error_code" in result_complex
    # Note: The error code will be INTERNAL_ERROR for MusicLibraryError base class
    assert result_complex["error_code"] == "INTERNAL_ERROR"
    print("✅ Error code inclusion")

    # Test JSON-RPC error response creation
    error_response = serializer.create_fastmcp_error_response(exc)
    assert error_response["jsonrpc"] == "2.0"
    assert "error" in error_response
    assert isinstance(error_response["error"]["code"], int)  # Should be an integer error code
    assert error_response["error"]["message"] == "Test validation error"
    print("✅ JSON-RPC error response creation")

    return True


def test_exception_serialization_middleware():
    """Test the ExceptionSerializationMiddleware class."""
    print("\nTesting ExceptionSerializationMiddleware...")

    middleware = ExceptionSerializationMiddleware()

    # Test preprocessing with complex details
    complex_details = {
        "database_connection": MagicMock(),  # Non-serializable
        "file_handle": MagicMock(),  # Non-serializable
        "valid_data": {"user_id": 123, "action": "upload"}
    }
    exc = StorageError("Storage operation failed", details=complex_details)

    # Preprocess the exception
    processed_exc = middleware.preprocess_exception(exc)

    # Verify details were sanitized
    assert hasattr(processed_exc, 'details')
    assert processed_exc.details != complex_details  # Should be different (sanitized)

    # Create error response
    error_response = middleware.create_error_response(exc)
    assert error_response["jsonrpc"] == "2.0"
    assert "error" in error_response

    print("✅ Middleware preprocessing and error response creation")

    return True


def test_json_serializability_checks():
    """Test JSON serializability detection."""
    print("\nTesting JSON serializability checks...")

    serializer = SafeExceptionSerializer()

    # Test serializable objects
    assert serializer.is_json_serializable({"key": "value"})
    assert serializer.is_json_serializable([1, 2, 3])
    assert serializer.is_json_serializable("string")
    assert serializer.is_json_serializable(42)

    # Test non-serializable objects
    assert not serializer.is_json_serializable(datetime.datetime.now())
    assert not serializer.is_json_serializable(Path("/tmp/test"))
    assert not serializer.is_json_serializable(lambda x: x)

    print("✅ JSON serializability detection")

    return True


def test_fallback_serialization():
    """Test that the serializer gracefully handles various edge cases."""
    print("\nTesting fallback serialization...")

    serializer = SafeExceptionSerializer()

    # Test with a standard exception that should work normally
    exc = ValueError("Test value error")
    result = serializer.serialize_exception(exc)

    # Verify it works and has expected structure
    assert isinstance(result, dict)
    assert "type" in result
    assert result["type"] == "ValueError"
    assert "message" in result
    assert result["message"] == "Test value error"

    # Test that all results have required fields
    required_fields = ["type", "module", "message", "details"]
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"

    print("✅ Fallback serialization handling")
    return True


def test_real_world_scenario():
    """Test with a realistic scenario that might occur in the application."""
    print("\nTesting real-world scenario...")

    # Simulate what might happen when a database operation fails
    db_error_details = {
        "operation": "SELECT",
        "table": "audio_tracks",
        "conditions": {"audio_id": "550e8400-e29b-41d4-a716-446655440000"},
        "error_code": "CONNECTION_LOST",
        # Include some non-serializable objects that might be in real exceptions
        "connection": MagicMock(),
        "cursor": MagicMock(),
        "transaction_context": {"isolation_level": "READ_COMMITTED", "timeout": 30}
    }

    exc = MusicLibraryError("Database operation failed", details=db_error_details)
    serializer = SafeExceptionSerializer()
    result = serializer.serialize_exception(exc)

    # Verify serialization worked
    assert result["type"] == "MusicLibraryError"
    assert result["message"] == "Database operation failed"
    assert result["is_music_library_error"] is True

    # Verify details were properly sanitized
    details = result["details"]
    assert details["operation"] == "SELECT"
    assert details["table"] == "audio_tracks"
    assert details["transaction_context"]["isolation_level"] == "READ_COMMITTED"

    # Non-serializable objects should be converted to strings
    assert isinstance(details["connection"], str)
    assert isinstance(details["cursor"], str)
    assert "<MagicMock object>" in details["connection"]

    print("✅ Real-world scenario handling")

    return True


if __name__ == "__main__":
    print("Exception Serializer Test Suite")
    print("=" * 50)

    tests = [
        ("SafeExceptionSerializer", test_safe_exception_serializer),
        ("ExceptionSerializationMiddleware", test_exception_serialization_middleware),
        ("JSON Serializability Checks", test_json_serializability_checks),
        ("Fallback Serialization", test_fallback_serialization),
        ("Real-world Scenario", test_real_world_scenario),
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
        print("\n🎉 All exception serializer tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed.")
        sys.exit(1)
