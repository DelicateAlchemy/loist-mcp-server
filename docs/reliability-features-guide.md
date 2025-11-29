# Reliability Features Guide

**Circuit Breaker and Retry Logic Configuration**

This guide explains how to configure and use the circuit breaker and retry logic features for improved fault tolerance and reliability.

## Overview

The system includes two key reliability features:

1. **Circuit Breaker**: Prevents cascading failures by automatically opening when services fail repeatedly
2. **Retry Logic**: Automatically retries transient failures with exponential backoff and jitter

Both features are integrated into:
- Database connection pool (`database/pool.py`)
- Google Cloud Storage client (`src/storage/gcs_client.py`)
- Task handlers (`src/tasks/handler.py`)

## Circuit Breaker

### What is a Circuit Breaker?

A circuit breaker is a design pattern that prevents repeated calls to a failing service. It has three states:

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Service is failing, requests fail fast without calling the service
- **HALF_OPEN**: Testing if service has recovered, limited requests allowed

### Configuration

Circuit breakers are configured using `CircuitBreakerConfig`:

```python
from src.exceptions.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker

config = CircuitBreakerConfig(
    name="database-pool",           # Unique name for this circuit breaker
    failure_threshold=5,            # Failures before opening circuit
    recovery_timeout=60.0,          # Seconds to wait before trying half-open
    success_threshold=3,            # Successes needed to close from half-open
    timeout=30.0                    # Request timeout in seconds
)

breaker = get_circuit_breaker("database-pool", config=config)
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | `"default"` | Unique identifier for the circuit breaker |
| `failure_threshold` | `5` | Number of consecutive failures before opening circuit |
| `recovery_timeout` | `60.0` | Seconds to wait before attempting recovery (half-open state) |
| `success_threshold` | `3` | Number of consecutive successes needed to close circuit from half-open |
| `timeout` | `30.0` | Maximum time (seconds) for a request before timing out |

### Usage Examples

#### Basic Usage

```python
from src.exceptions.circuit_breaker import get_circuit_breaker

# Get or create a circuit breaker (uses defaults if not configured)
breaker = get_circuit_breaker("my-service")

# Execute a function through the circuit breaker
try:
    result = breaker.call(my_function, arg1, arg2)
except CircuitBreakerOpenException:
    # Circuit is open - service is down
    handle_service_unavailable()
```

#### Async Usage

```python
# For async functions
result = await breaker.call_async(my_async_function, arg1, arg2)
```

#### Custom Configuration

```python
from src.exceptions.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker

# Create custom configuration
config = CircuitBreakerConfig(
    name="gcs-upload",
    failure_threshold=3,      # Open after 3 failures
    recovery_timeout=30.0,     # Try recovery after 30 seconds
    success_threshold=2,       # Close after 2 successes
    timeout=60.0              # 60 second timeout
)

breaker = get_circuit_breaker("gcs-upload", config=config)
```

### Monitoring Circuit Breakers

Get status of all circuit breakers:

```python
from src.exceptions.circuit_breaker import get_all_circuit_breakers

breakers = get_all_circuit_breakers()
for name, breaker in breakers.items():
    stats = breaker.stats
    print(f"{name}: {breaker.state.value}")
    print(f"  Total requests: {stats.total_requests}")
    print(f"  Failed: {stats.failed_requests}")
    print(f"  Consecutive failures: {stats.consecutive_failures}")
```

Or use the MCP tool:

```python
# Via MCP tool
result = mcp.call_tool("get_circuit_breaker_status")
```

### Resetting Circuit Breakers

Manually reset a circuit breaker:

```python
from src.exceptions.circuit_breaker import reset_circuit_breaker

reset_circuit_breaker("database-pool")
```

### Integration Points

Circuit breakers are automatically integrated into:

1. **Database Pool** (`database/pool.py`):
   - Wraps connection acquisition and query execution
   - Prevents database connection exhaustion during outages

2. **GCS Client** (`src/storage/gcs_client.py`):
   - Wraps GCS upload/download operations
   - Prevents cascading failures when GCS is unavailable

3. **Task Handlers** (`src/tasks/handler.py`):
   - Monitors waveform generation task execution
   - Provides circuit breaker status via MCP tool

## Retry Logic

### What is Retry Logic?

Retry logic automatically retries failed operations that are likely to succeed on retry (transient failures). It uses exponential backoff with jitter to avoid thundering herd problems.

### Configuration

Retry logic is configured using `RetryConfig`:

```python
from src.exceptions.retry import RetryConfig, retry_call

config = RetryConfig(
    max_attempts=3,            # Maximum number of retry attempts
    initial_delay=0.1,         # Initial delay in seconds
    max_delay=30.0,            # Maximum delay between retries
    backoff_factor=2.0,        # Exponential backoff multiplier
    jitter=True,               # Add random jitter to delay
    jitter_factor=0.1          # Jitter factor (±10% of delay)
)

result = retry_call(my_function, config=config, arg1, arg2)
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_attempts` | `3` | Maximum number of attempts (including initial attempt) |
| `initial_delay` | `0.1` | Initial delay in seconds before first retry |
| `max_delay` | `30.0` | Maximum delay between retries (caps exponential growth) |
| `backoff_factor` | `2.0` | Multiplier for exponential backoff (delay = initial * factor^attempt) |
| `jitter` | `True` | Whether to add random jitter to delays |
| `jitter_factor` | `0.1` | Jitter range as fraction of delay (±10% = ±0.1) |
| `retryable_exceptions` | `[ConnectionError, TimeoutError, ...]` | List of exception types that trigger retries |

### Pre-configured Retry Configs

The system provides pre-configured retry configs for common use cases:

#### Database Operations

```python
from src.exceptions.retry import DATABASE_RETRY_CONFIG, retry_call

# Uses conservative settings for database operations
result = retry_call(database_query, config=DATABASE_RETRY_CONFIG)
```

**Settings:**
- `max_attempts=3`
- `initial_delay=0.1s`
- `max_delay=5.0s`
- `backoff_factor=2.0`
- Retries: `ConnectionError`, `TimeoutError`, `psycopg2.OperationalError`

#### GCS Operations

```python
from src.exceptions.retry import GCS_RETRY_CONFIG, retry_call

# Optimized for GCS API calls
result = retry_call(gcs_upload, config=GCS_RETRY_CONFIG)
```

**Settings:**
- `max_attempts=3`
- `initial_delay=0.2s`
- `max_delay=10.0s`
- `backoff_factor=2.0`
- Retries: Google Cloud API exceptions, network errors

#### HTTP Operations

```python
from src.exceptions.retry import HTTP_RETRY_CONFIG, retry_call

# More aggressive retries for HTTP calls
result = retry_call(http_request, config=HTTP_RETRY_CONFIG)
```

**Settings:**
- `max_attempts=5`
- `initial_delay=0.5s`
- `max_delay=30.0s`
- `backoff_factor=1.5`
- Retries: `ConnectionError`, `TimeoutError`, network errors

### Usage Examples

#### Decorator Pattern

```python
from src.exceptions.retry import retry_with_backoff

@retry_with_backoff(max_attempts=5, initial_delay=0.5)
def unreliable_operation():
    # This function will be automatically retried on failure
    return make_api_call()
```

#### Function Call Pattern

```python
from src.exceptions.retry import retry_call, RetryConfig

config = RetryConfig(max_attempts=3, initial_delay=0.1)
result = retry_call(my_function, config=config, arg1="value")
```

#### Custom Retryable Exceptions

```python
from src.exceptions.retry import RetryConfig, retry_call

class MyCustomError(Exception):
    pass

config = RetryConfig(
    max_attempts=3,
    retryable_exceptions=[MyCustomError, ConnectionError]
)

result = retry_call(my_function, config=config)
```

### Retry Behavior

#### Exponential Backoff Calculation

Delay for attempt `n` (0-based):
```
delay = initial_delay * (backoff_factor ^ n)
delay = min(delay, max_delay)  # Cap at max_delay
```

**Example** (initial_delay=0.1, backoff_factor=2.0, max_delay=10.0):
- Attempt 0: 0.1s
- Attempt 1: 0.2s
- Attempt 2: 0.4s
- Attempt 3: 0.8s
- Attempt 4: 1.6s
- Attempt 5: 3.2s
- Attempt 6: 6.4s
- Attempt 7: 10.0s (capped)

#### Jitter

When jitter is enabled, a random value is added to each delay:
```
jitter_range = delay * jitter_factor
jitter = random.uniform(-jitter_range, jitter_range)
final_delay = delay + jitter
```

This prevents multiple clients from retrying simultaneously (thundering herd problem).

### Non-Retryable Exceptions

Some exceptions are **never retried**:
- `ValueError`, `TypeError`, `KeyError` (programming errors)
- `AuthenticationError` (won't succeed on retry)
- Any exception not in `retryable_exceptions` list

### Integration Points

Retry logic is automatically integrated into:

1. **Database Pool** (`database/pool.py`):
   - Retries connection acquisition
   - Uses `CONSERVATIVE_CONFIG` for reliable database operations

2. **GCS Client** (`src/storage/gcs_client.py`):
   - Retries upload/download operations
   - Uses `CONSERVATIVE_CONFIG` for cloud storage reliability

3. **Storage Manager** (`src/storage/manager.py`):
   - Configurable retry behavior for all storage operations
   - Defaults to `CONSERVATIVE_CONFIG`, accepts custom configurations

## Best Practices

### Circuit Breaker Configuration

1. **Failure Threshold**: Set based on expected failure rate
   - Low threshold (3-5): For critical services that must be highly available
   - Higher threshold (10+): For services that can tolerate occasional failures

2. **Recovery Timeout**: Should match expected recovery time
   - Short timeout (30s): For services that recover quickly
   - Longer timeout (60-120s): For services that need more time to recover

3. **Success Threshold**: Number of test requests in half-open state
   - Lower (2-3): Faster recovery but more test requests
   - Higher (5+): Slower recovery but more confidence

### Retry Configuration

1. **Max Attempts**: Balance between reliability and latency
   - Fewer attempts (2-3): Lower latency, less reliability
   - More attempts (5+): Higher latency, more reliability

2. **Initial Delay**: Start small to catch quick recoveries
   - Very small (0.1s): For fast-recovering services
   - Larger (0.5-1s): For slower services

3. **Max Delay**: Cap exponential growth
   - Lower (5-10s): For time-sensitive operations
   - Higher (30-60s): For background operations

4. **Jitter**: Always enable for distributed systems
   - Prevents thundering herd problems
   - Recommended: `jitter=True`, `jitter_factor=0.1`

### Monitoring

Monitor both circuit breakers and retry logic:

```python
# Circuit breaker stats
breakers = get_all_circuit_breakers()
for name, breaker in breakers.items():
    stats = breaker.stats
    if stats.failed_requests > 0:
        failure_rate = stats.failed_requests / stats.total_requests
        logger.warning(f"{name} failure rate: {failure_rate:.2%}")

# Retry metrics (via waveform metrics or custom tracking)
# Track: retry attempts, retry success rate, average retry delay
```

## Environment Configuration

### Circuit Breaker Settings

Circuit breaker configuration can be done programmatically or via environment variables. Environment variables provide global defaults that can be overridden per instance.

#### Environment Variables

```bash
# Global circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5      # Failures before opening (default: 5)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60.0   # Seconds to wait before recovery (default: 60.0)
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3     # Successes needed to close from half-open (default: 3)
CIRCUIT_BREAKER_TIMEOUT=30.0            # Request timeout in seconds (default: 30.0)
```

#### Programmatic Configuration

```python
from src.exceptions.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker

# Using environment variable defaults
config = CircuitBreakerConfig(name="database-pool")
breaker = get_circuit_breaker("database-pool", config)

# Overriding specific settings
config = CircuitBreakerConfig(
    name="api-client",
    failure_threshold=3,      # Override env var default
    recovery_timeout=30.0,    # Override env var default
    success_threshold=2,      # Override env var default
    timeout=10.0              # Override env var default
)
breaker = get_circuit_breaker("api-client", config)
```

#### Configuration Priority

1. **Instance-specific parameters** (highest priority)
2. **Environment variables** (global defaults)
3. **Built-in defaults** (lowest priority)

This allows fine-tuned configuration per service while maintaining sensible global defaults.

### Retry Settings

Retry configuration is done programmatically. Pre-configured configs are recommended for most use cases.

### Preset Retry Configurations

The system provides three preset retry configurations optimized for different scenarios:

#### CONSERVATIVE_CONFIG
```python
CONSERVATIVE_CONFIG = RetryConfig(
    max_attempts=3,      # Conservative number of retries
    initial_delay=1.0,   # Start with 1 second delay
    max_delay=16.0,      # Cap at 16 seconds
    exponential_base=2.0,# Standard exponential backoff
    jitter=True          # Add randomness to prevent thundering herd
)
```
**Use for**: Database operations, critical API calls, most cloud storage operations
**Rationale**: Balances reliability with reasonable latency. Suitable for most production workloads.

#### AGGRESSIVE_CONFIG
```python
AGGRESSIVE_CONFIG = RetryConfig(
    max_attempts=5,      # More retry attempts
    initial_delay=0.5,   # Shorter initial delay
    max_delay=8.0,       # Lower maximum delay
    exponential_base=1.5,# Gentler exponential growth
    jitter=True          # Add randomness
)
```
**Use for**: Fast-recovering services, time-sensitive operations, user-facing requests
**Rationale**: Prioritizes speed over maximum reliability. Good when quick recovery is more important than exhaustive retries.

#### PATIENT_CONFIG
```python
PATIENT_CONFIG = RetryConfig(
    max_attempts=4,      # Moderate retry attempts
    initial_delay=2.0,   # Longer initial delay
    max_delay=60.0,      # Much higher maximum delay
    exponential_base=2.5,# Steeper exponential growth
    jitter=True          # Add randomness
)
```
**Use for**: Large file uploads/downloads, background processing, operations with high variability
**Rationale**: Optimized for operations that may take longer to recover. Prevents overwhelming slow-recovering services.

### Choosing the Right Configuration

| Scenario | Recommended Config | Why |
|----------|-------------------|-----|
| Database queries | `CONSERVATIVE_CONFIG` | Reliable with reasonable timeouts |
| GCS operations | `CONSERVATIVE_CONFIG` | Good balance for cloud storage |
| User-facing APIs | `AGGRESSIVE_CONFIG` | Faster recovery for better UX |
| Large file uploads | `PATIENT_CONFIG` | Handles long recovery times |
| Background tasks | `PATIENT_CONFIG` | Can afford longer delays |
| Critical operations | `CONSERVATIVE_CONFIG` | High reliability needed |

### Custom Retry Configuration

For specialized needs, create custom `RetryConfig` instances:

```python
from src.storage.retry import RetryConfig

# Custom config for very fast operations
fast_config = RetryConfig(
    max_attempts=2,
    initial_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=True
)

# Custom config for extremely patient operations
ultra_patient = RetryConfig(
    max_attempts=6,
    initial_delay=5.0,
    max_delay=300.0,  # 5 minutes
    exponential_base=2.0,
    jitter=True
)
```

### Integration Examples

```python
from src.storage.retry import with_retry, CONSERVATIVE_CONFIG, AGGRESSIVE_CONFIG
from src.storage.manager import StorageManager

# Using decorator with preset config
@with_retry(CONSERVATIVE_CONFIG)
def upload_file(file_path):
    # Upload logic here
    pass

# Using storage manager with custom config
storage = StorageManager(retry_config=AGGRESSIVE_CONFIG)
storage.upload_file("path/to/file")

# Functional approach
from src.storage.retry import retry_operation
result = retry_operation(
    lambda: risky_operation(),
    config=CONSERVATIVE_CONFIG,
    operation_name="my-operation"
)
```

## Troubleshooting

### Circuit Breaker Always Open

**Symptoms**: Circuit breaker stays open even when service recovers

**Solutions**:
1. Check `recovery_timeout` - may be too long
2. Verify service is actually recovering
3. Manually reset: `reset_circuit_breaker("service-name")`

### Too Many Retries

**Symptoms**: Operations take too long due to excessive retries

**Solutions**:
1. Reduce `max_attempts`
2. Reduce `max_delay`
3. Review `retryable_exceptions` - may be retrying non-retryable errors

### Retries Not Happening

**Symptoms**: Failures occur immediately without retries

**Solutions**:
1. Check exception type is in `retryable_exceptions`
2. Verify `max_attempts > 1`
3. Check if exception is being caught elsewhere

## Testing

Test circuit breaker and retry logic:

```bash
# Test circuit breaker
bash scripts/test_circuit_breaker.sh

# Test retry logic
bash scripts/test_retry_logic.sh
```

## Related Documentation

- [Exception Handling Guide](exception-handling-guide.md)
- [Database Best Practices](database-best-practices.md)
- [Testing Strategy](testing-strategy-and-recovery.md)
- [Tech Debt Analysis](tech-debt-analysis.md)

