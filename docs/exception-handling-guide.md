# Exception Handling Guide

## Overview

The Music Library MCP Server implements a unified exception handling framework that provides consistent error responses, automatic recovery strategies, and comprehensive debugging capabilities across all components.

## Core Concepts

### Exception Hierarchy

All custom exceptions inherit from `MusicLibraryError`, which provides standardized error codes and context:

```python
from src.exceptions import MusicLibraryError, ValidationError, DatabaseOperationError

# Base exception with context
class MusicLibraryError(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
```

### Exception Types

| Exception Type | Use Case | HTTP Status |
|----------------|----------|-------------|
| `ValidationError` | Invalid input data | 400 |
| `ResourceNotFoundError` | Missing resources | 404 |
| `AuthenticationError` | Auth failures | 401 |
| `DatabaseOperationError` | Database issues | 500 |
| `StorageError` | GCS operations | 500 |
| `AudioProcessingError` | Audio processing failures | 500 |
| `TimeoutError` | Operation timeouts | 504 |
| `RateLimitError` | Rate limiting | 429 |
| `ExternalServiceError` | Third-party service issues | 502 |

## Exception Handler Usage

### Basic Exception Handling

```python
from src.exceptions import ExceptionHandler, ExceptionContext, ExceptionConfig

# Create handler with default configuration
config = ExceptionConfig()
handler = ExceptionHandler(config)

# Create context for the operation
context = ExceptionContext(
    operation="process_audio",
    component="tools.process_audio",
    user_id="user123",
    request_id="req456"
)

try:
    # Your business logic here
    result = process_audio_file(audio_data)
except Exception as e:
    # Handle exception with full context
    error_response = handler.handle_exception(e, context)
    return error_response.to_dict()
```

### HTTP Response Handling

```python
try:
    metadata = repository.get_metadata_by_id(audio_id)
    if not metadata:
        raise ResourceNotFoundError(f"Audio track {audio_id} not found")
except Exception as e:
    # Automatic HTTP response generation
    response_dict, status_code = handler.handle_for_http(e, context)
    return JSONResponse(response_dict, status_code=status_code)
```

### Exception Raising with Context

```python
def validate_audio_format(format_str: str):
    """Validate audio format with proper error context."""
    from src.exceptions import ValidationError, ExceptionContext
    from src.exceptions.fastmcp_integration import get_global_exception_handler

    handler = get_global_exception_handler()
    context = ExceptionContext(
        operation="validate_format",
        component="audio_processing"
    )

    if format_str not in ['MP3', 'FLAC', 'WAV', 'AAC']:
        error = ValidationError(f"Unsupported audio format: {format_str}")
        handler.handle_and_raise(error, context)
```

## Recovery Strategies

### Automatic Retry Logic

The framework includes built-in recovery strategies for transient failures:

```python
from src.exceptions.recovery import DatabaseRecoveryStrategy

# Add recovery strategy to handler
handler.add_recovery_strategy(DatabaseRecoveryStrategy(
    max_retries=3,
    base_delay=0.1  # Base delay in seconds
))

# The handler will automatically retry database operations
# that fail due to transient connection issues
```

### Circuit Breaker Pattern

```python
from src.exceptions.recovery import CircuitBreakerRecoveryStrategy

# Add circuit breaker for external services
circuit_breaker = CircuitBreakerRecoveryStrategy(
    failure_threshold=5,     # Open after 5 failures
    recovery_timeout=60      # Try again after 60 seconds
)
handler.add_recovery_strategy(circuit_breaker)
```

### Custom Recovery Strategies

```python
from src.exceptions.recovery import RecoveryStrategy

class CustomRecoveryStrategy(RecoveryStrategy):
    def can_recover(self, exception, context):
        # Check if this exception can be recovered
        return isinstance(exception, TimeoutError) and context.can_retry()

    def recover(self, exception, context):
        # Implement custom recovery logic
        logger.info(f"Retrying operation after timeout: {context.operation}")
        context.increment_retry()

        # Custom recovery logic here
        # e.g., switch to different service endpoint

        raise exception  # Re-raise to trigger retry
```

## Configuration Options

### Exception Handler Configuration

```python
from src.exceptions import ExceptionConfig

# Production configuration
prod_config = ExceptionConfig(
    enable_detailed_errors=True,
    include_stack_traces=False,      # Never in production
    mask_sensitive_data=True,
    log_level="WARNING",
    enable_recovery=True,
    max_retry_attempts=3
)

# Development configuration
dev_config = ExceptionConfig().for_development()

# Testing configuration
test_config = ExceptionConfig().for_testing()
```

### Environment-Specific Settings

```python
# Automatic configuration based on environment
import os

if os.getenv("ENVIRONMENT") == "production":
    config = ExceptionConfig().for_production()
elif os.getenv("ENVIRONMENT") == "testing":
    config = ExceptionConfig().for_testing()
else:
    config = ExceptionConfig().for_development()
```

## Error Response Format

### Standardized Response Structure

All errors follow a consistent JSON response format:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "audio_url",
      "value": "invalid-url",
      "reason": "must be valid http/https URL"
    },
    "context": {
      "operation": "process_audio",
      "component": "tools.process_audio",
      "request_id": "req-12345",
      "timestamp": "2025-11-04T17:42:07Z",
      "user_id": "user123"
    },
    "recovery": {
      "suggested_action": "provide_valid_url",
      "retryable": false,
      "max_retries": 3,
      "current_attempt": 1
    }
  }
}
```

### Error Codes

| Code | Description | Category |
|------|-------------|----------|
| `VALIDATION_ERROR` | Input validation failures | Client Error |
| `RESOURCE_NOT_FOUND_ERROR` | Missing resources | Client Error |
| `AUTHENTICATION_ERROR` | Authentication failures | Client Error |
| `DATABASE_ERROR` | Database operation failures | Server Error |
| `STORAGE_ERROR` | GCS operation failures | Server Error |
| `TIMEOUT_ERROR` | Operation timeouts | Server Error |
| `RATE_LIMIT_ERROR` | Rate limiting exceeded | Client Error |
| `EXTERNAL_SERVICE_ERROR` | Third-party service failures | Server Error |
| `UNKNOWN_ERROR` | Unexpected errors | Server Error |

## Logging and Monitoring

### Structured Logging

The framework automatically provides structured logging with context:

```python
# Automatic logging on exception
try:
    result = database_operation()
except Exception as e:
    # Logs include: exception_type, operation, component, user_id, request_id, etc.
    handler.handle_exception(e, context)
```

### Custom Log Context

```python
# Add custom metadata to context
context.add_metadata("file_size", 1024)
context.add_metadata("processing_time", 45.2)
context.add_metadata("retry_reason", "connection_timeout")

try:
    result = process_large_file(file_data)
except Exception as e:
    # Custom metadata included in logs and error responses
    handler.handle_exception(e, context)
```

## FastMCP Integration

### Automatic Exception Handling

The framework integrates seamlessly with FastMCP without manual workarounds:

```python
# In server initialization
from src.exceptions.fastmcp_integration import initialize_exception_framework

# Initialize unified exception handling
handler = initialize_exception_framework()

# All MCP tools and resources automatically use unified error handling
# No manual exception handling required in tool implementations
```

### Tool Exception Handling

```python
@mcp.tool()
async def process_audio(audio_url: str) -> dict:
    """Process audio file from URL."""
    # No manual exception handling needed
    # Framework automatically handles and formats errors
    return await process_audio_file(audio_url)
```

## Testing Exception Handling

### Unit Testing Exceptions

```python
import pytest
from src.exceptions import ValidationError, ExceptionHandler, ExceptionContext

def test_validation_error():
    """Test validation error handling."""
    handler = ExceptionHandler(ExceptionConfig().for_testing())
    context = ExceptionContext(operation="validate", component="test")

    exception = ValidationError("Invalid format")
    response = handler.handle_exception(exception, context)

    assert response.success is False
    assert response.error_code == "VALIDATION_ERROR"
    assert "Invalid format" in response.message
```

### Mocking Exception Handler

```python
from unittest.mock import Mock

def test_tool_with_exception_handling(mock_repository):
    """Test tool with mocked exception handling."""
    # Mock the repository to raise an exception
    mock_repository.get_metadata_by_id.side_effect = ResourceNotFoundError("Track not found")

    # Override global exception handler for testing
    from src.exceptions.fastmcp_integration import set_global_exception_handler
    mock_handler = Mock()
    mock_handler.handle_for_http.return_value = ({"error": "test"}, 404)
    set_global_exception_handler(mock_handler)

    # Test your tool
    # Exception handling is automatically applied
```

### Integration Testing

```python
def test_end_to_end_exception_handling():
    """Test complete exception handling flow."""
    # Initialize framework
    handler = initialize_exception_framework()

    # Test various exception scenarios
    exceptions_to_test = [
        ValidationError("test validation"),
        ResourceNotFoundError("test not found"),
        DatabaseOperationError("test database error"),
    ]

    for exception in exceptions_to_test:
        context = ExceptionContext(operation="test", component="test")
        response = handler.handle_exception(exception, context)

        # Verify consistent response format
        assert response.success is False
        assert response.error_code in response.message
        assert response.context["operation"] == "test"
```

## Migration Guide

### From Legacy Exception Handling

#### Before (Multiple Approaches)
```python
# Old approach 1: Custom error utils
from src.error_utils import create_error_response
try:
    result = operation()
except Exception as e:
    return create_error_response(e, "Custom message")

# Old approach 2: Direct exception serialization
from src.exception_serializer import exception_serializer
try:
    result = operation()
except Exception as e:
    serialized = exception_serializer.serialize_exception(e)
    return {"error": serialized}

# Old approach 3: MCP-specific workarounds
try:
    result = operation()
except Exception as e:
    # Complex workaround logic
    return handle_tool_error(e, "tool_name")
```

#### After (Unified Framework)
```python
# New unified approach
from src.exceptions import ExceptionContext
from src.exceptions.fastmcp_integration import get_global_exception_handler

handler = get_global_exception_handler()
context = ExceptionContext(operation="operation_name", component="component_name")

try:
    result = operation()
except Exception as e:
    return handler.handle_exception(e, context).to_dict()
```

### Gradual Migration Strategy

1. **Phase 1: Framework Installation**
   - Add exception framework to project
   - Initialize global exception handler
   - Keep existing code unchanged

2. **Phase 2: Component Migration**
   - Migrate one component at a time
   - Update imports and error handling
   - Test each component thoroughly

3. **Phase 3: Cleanup**
   - Remove old exception handling code
   - Update documentation
   - Train team on new patterns

### Common Migration Patterns

#### Tool Migration
```python
# Before
@mcp.tool()
async def process_audio(url: str):
    try:
        return await process_audio_impl(url)
    except Exception as e:
        return handle_tool_error(e, "process_audio")

# After
@mcp.tool()
async def process_audio(url: str):
    # Exception handling automatic via framework
    return await process_audio_impl(url)
```

#### Resource Migration
```python
# Before
async def get_metadata_resource(uri: str):
    try:
        metadata = get_audio_metadata_by_id(audio_id)
        return {"text": json.dumps(metadata)}
    except Exception as e:
        return {"error": str(e)}

# After
async def get_metadata_resource(uri: str):
    # Exception handling automatic via framework
    metadata = repository.get_metadata_by_id(audio_id)
    return {"text": json.dumps(metadata)}
```

## Best Practices

### Exception Context Guidelines

```python
# ✅ Good: Rich context
context = ExceptionContext(
    operation="process_audio",
    component="tools.process_audio",
    user_id=request.user_id,
    request_id=request.id,
    operation_type=OperationType.AUDIO_PROCESSING
)

# ❌ Bad: Minimal context
context = ExceptionContext("process", "tools")
```

### Error Message Standards

```python
# ✅ Good: User-friendly messages
raise ValidationError("Audio URL must be a valid HTTP or HTTPS URL")

# ❌ Bad: Technical jargon
raise ValidationError("Invalid URL scheme - only http/https supported")
```

### Recovery Strategy Selection

```python
# ✅ Good: Appropriate recovery for the operation
database_operations = ExceptionHandler(ExceptionConfig())
database_operations.add_recovery_strategy(DatabaseRecoveryStrategy())

external_api_calls = ExceptionHandler(ExceptionConfig())
external_api_calls.add_recovery_strategy(CircuitBreakerRecoveryStrategy())

# ❌ Bad: Wrong recovery strategy
# Don't use circuit breaker for database operations
# Don't use database recovery for external APIs
```

### Testing Coverage

```python
# ✅ Good: Test exception scenarios
def test_invalid_audio_format():
    with pytest.raises(ValidationError, match="Unsupported format"):
        validate_audio_format("INVALID")

def test_missing_audio_file():
    with pytest.raises(ResourceNotFoundError):
        get_audio_stream("nonexistent-id")

# ❌ Bad: Missing exception testing
def test_successful_operation():
    # Only tests happy path, ignores error cases
    result = process_audio("valid-url")
    assert result is not None
```

## Troubleshooting

### Common Issues

#### Exception Not Being Caught
```python
# Issue: Exception handler not initialized
# Solution: Ensure framework is initialized
from src.exceptions.fastmcp_integration import initialize_exception_framework
handler = initialize_exception_framework()
```

#### Recovery Strategy Not Working
```python
# Issue: Recovery strategy not added to handler
# Solution: Add strategies explicitly
handler.add_recovery_strategy(DatabaseRecoveryStrategy())
```

#### Context Missing Information
```python
# Issue: Insufficient context for debugging
# Solution: Always provide operation and component
context = ExceptionContext(
    operation="descriptive_operation_name",
    component="module.submodule"
)
```

### Debugging Tools

#### Enable Debug Logging
```python
import logging
logging.getLogger('src.exceptions').setLevel(logging.DEBUG)
```

#### Inspect Exception Context
```python
try:
    operation()
except Exception as e:
    # Log full context
    print(f"Operation: {context.operation}")
    print(f"Component: {context.component}")
    print(f"Retry count: {context.retry_count}")
    print(f"Metadata: {context.metadata}")
    raise
```

#### Test Exception Serialization
```python
from src.exception_serializer import SafeExceptionSerializer

serializer = SafeExceptionSerializer()
exception = ValidationError("test error")
serialized = serializer.serialize_exception(exception)

print(json.dumps(serialized, indent=2))
```

## Performance Considerations

### Exception Handling Overhead

- **Minimal Overhead**: Framework designed for performance
- **Lazy Evaluation**: Context and serialization only when needed
- **Efficient Recovery**: Strategies avoid unnecessary work

### Monitoring and Metrics

```python
# Track exception rates
exception_count = 0
recovery_success_count = 0

def handle_with_metrics(exception, context):
    global exception_count, recovery_success_count

    exception_count += 1

    try:
        result = handler.handle_exception(exception, context)
        recovery_success_count += 1
        return result
    finally:
        # Report metrics
        success_rate = recovery_success_count / exception_count
        metrics.gauge("exception_recovery_rate", success_rate)
```

---

This guide provides comprehensive coverage of the unified exception handling framework. For additional examples and advanced usage patterns, refer to the test files in `tests/test_exception_framework.py`.
