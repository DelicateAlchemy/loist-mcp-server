#!/usr/bin/env python3
"""
Simple test script to check FastMCP exception serialization issues.
"""
import sys
import json
from pathlib import Path

# Add the parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import exceptions
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

def test_basic_serialization():
    """Test basic exception serialization."""
    print("Testing basic exception serialization...")

    test_exceptions = [
        MusicLibraryError("Test error"),
        AudioProcessingError("Audio processing failed"),
        ValidationError("Validation failed"),
        StorageError("Storage failed"),
        ResourceNotFoundError("Resource not found"),
        TimeoutError("Timeout occurred"),
        AuthenticationError("Authentication failed"),
        RateLimitError("Rate limit exceeded"),
        ExternalServiceError("External service error"),
        DatabaseOperationError("Database operation error"),
    ]

    for exc in test_exceptions:
        try:
            # Simulate what FastMCP's ErrorHandlingMiddleware does
            error_data = {
                'type': type(exc).__name__,
                'message': str(exc),
                'module': type(exc).__module__,
            }

            # Try to serialize to JSON
            json_str = json.dumps(error_data)
            parsed = json.loads(json_str)

            print(f"✅ {type(exc).__name__}: Serialization successful")

        except Exception as e:
            print(f"❌ {type(exc).__name__}: Serialization failed - {e}")
            return False

    return True

def test_exception_details_serialization():
    """Test exception serialization with details."""
    print("\nTesting exception serialization with details...")

    # Test with complex details that might cause issues
    details_scenarios = [
        {"simple": "string"},
        {"nested": {"key": "value"}},
        {"list": [1, 2, 3]},
        {"mixed": {"string": "value", "number": 42, "bool": True}},
    ]

    for i, details in enumerate(details_scenarios):
        try:
            exc = MusicLibraryError("Test with details", details=details)

            error_data = {
                'type': type(exc).__name__,
                'message': str(exc),
                'module': type(exc).__module__,
                'details': exc.details,
            }

            json_str = json.dumps(error_data)
            parsed = json.loads(json_str)

            print(f"✅ Details scenario {i+1}: Serialization successful")

        except Exception as e:
            print(f"❌ Details scenario {i+1}: Serialization failed - {e}")
            return False

    return True

def test_globals_access():
    """Test that exceptions are accessible via globals lookup."""
    print("\nTesting globals access (like server.py does)...")

    # Simulate the globals() approach from server.py
    exception_classes = {
        'MusicLibraryError': MusicLibraryError,
        'AudioProcessingError': AudioProcessingError,
        'StorageError': StorageError,
        'ValidationError': ValidationError,
        'ResourceNotFoundError': ResourceNotFoundError,
        'TimeoutError': TimeoutError,
        'AuthenticationError': AuthenticationError,
        'RateLimitError': RateLimitError,
        'ExternalServiceError': ExternalServiceError,
        'DatabaseOperationError': DatabaseOperationError,
    }

    # Test globals lookup
    test_globals = {}
    test_globals.update(exception_classes)

    for name, expected_class in exception_classes.items():
        try:
            looked_up = test_globals.get(name)
            if looked_up is None:
                raise NameError(f"{name} not found in globals")

            if looked_up != expected_class:
                raise ValueError(f"Wrong class returned for {name}")

            print(f"✅ {name}: Globals access successful")

        except Exception as e:
            print(f"❌ {name}: Globals access failed - {e}")
            return False

    return True

def test_fastmcp_context_simulation():
    """Test exception handling in FastMCP-like context."""
    print("\nTesting FastMCP context simulation...")

    # This simulates what happens when FastMCP tries to serialize exceptions
    # during JSON-RPC response generation

    try:
        # Simulate an exception being raised in a tool
        raise ValidationError("Simulated validation error", details={"field": "url", "reason": "invalid_format"})

    except Exception as exc:
        try:
            # This is what FastMCP's error handling might try to do
            # Access exception class information
            exc_class = type(exc)
            exc_name = exc_class.__name__
            exc_module = exc_class.__module__

            # Try to serialize the error information
            error_info = {
                "error": {
                    "code": -32603,  # Internal error
                    "message": str(exc),
                    "data": {
                        "exception_type": exc_name,
                        "exception_module": exc_module,
                        "details": getattr(exc, 'details', None)
                    }
                },
                "jsonrpc": "2.0",
                "id": 1
            }

            # Serialize to JSON (this is where NameError would occur)
            json_response = json.dumps(error_info)

            print("✅ FastMCP context simulation: Serialization successful")
            return True

        except NameError as e:
            print(f"❌ FastMCP context simulation: NameError during serialization - {e}")
            return False
        except Exception as e:
            print(f"❌ FastMCP context simulation: Unexpected error - {e}")
            return False

def test_exception_context_isolation():
    """Test exception serialization in isolated execution contexts."""
    print("\nTesting exception context isolation...")

    # This simulates the issue where exceptions might be serialized
    # in a different execution context than where they were defined

    def simulate_tool_execution():
        """Simulate a tool function that raises an exception."""
        raise ResourceNotFoundError("Audio track not found", details={"audioId": "123"})

    def simulate_error_handler(exc):
        """Simulate FastMCP's error handler trying to serialize the exception."""
        try:
            # This is what might happen in FastMCP's serialization code
            # It tries to access exception class information
            exc_class_name = exc.__class__.__name__

            # But the class might not be available in this context
            # Simulate this by checking if we can import the class dynamically
            module_name = exc.__class__.__module__
            class_name = exc.__class__.__name__

            # Try to import the module and get the class
            __import__(module_name)
            module = sys.modules[module_name]
            resolved_class = getattr(module, class_name)

            # Verify it's the same class
            if resolved_class != exc.__class__:
                raise NameError(f"Resolved class {resolved_class} != original {exc.__class__}")

            return True

        except (ImportError, AttributeError, NameError) as e:
            print(f"❌ Exception context isolation: Failed to resolve exception class - {e}")
            return False

    try:
        simulate_tool_execution()
    except Exception as exc:
        return simulate_error_handler(exc)

def test_complex_details_serialization():
    """Test serialization with complex objects in details that might not be JSON serializable."""
    print("\nTesting complex details serialization...")

    # Test with objects that might not be JSON serializable
    import datetime
    from pathlib import Path

    complex_details_scenarios = [
        {"datetime": datetime.datetime.now(), "path": Path("/tmp/test")},
        {"set": {1, 2, 3}, "tuple": (1, 2, "three")},
        {"callable": lambda x: x, "module": sys.modules[__name__]},
    ]

    for i, details in enumerate(complex_details_scenarios):
        try:
            exc = MusicLibraryError("Test with complex details", details=details)

            # Try to serialize - this should fail for non-JSON-serializable objects
            error_data = {
                'type': type(exc).__name__,
                'message': str(exc),
                'module': type(exc).__module__,
                'details': exc.details,  # This contains non-serializable objects
            }

            # This should fail with TypeError
            json_str = json.dumps(error_data)
            print(f"❌ Complex details scenario {i+1}: Unexpectedly succeeded (should have failed)")
            return False

        except TypeError as e:
            # This is expected - complex objects can't be JSON serialized
            print(f"✅ Complex details scenario {i+1}: Correctly failed with TypeError - {str(e)[:50]}...")
        except Exception as e:
            print(f"❌ Complex details scenario {i+1}: Unexpected error - {e}")
            return False

    return True

if __name__ == "__main__":
    print("FastMCP Exception Serialization Test")
    print("=" * 50)

    results = []
    results.append(("Basic Serialization", test_basic_serialization()))
    results.append(("Details Serialization", test_exception_details_serialization()))
    results.append(("Globals Access", test_globals_access()))
    results.append(("FastMCP Context", test_fastmcp_context_simulation()))
    results.append(("Exception Context Isolation", test_exception_context_isolation()))
    results.append(("Complex Details Serialization", test_complex_details_serialization()))

    print("\n" + "=" * 50)
    print("SUMMARY:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n🎉 All tests passed! No serialization issues detected.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Exception serialization issues detected.")
        sys.exit(1)
