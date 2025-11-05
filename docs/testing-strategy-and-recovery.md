# Testing Strategy and Recovery Mechanisms

## Overview

This document outlines the comprehensive testing strategy implemented for the Music Library MCP Server, including automated testing frameworks, recovery mechanisms, and best practices for maintaining code quality.

## Testing Architecture

### Test Categories

The testing strategy employs multiple layers of testing to ensure comprehensive coverage:

#### 1. Unit Tests
- **Framework**: pytest with fixtures and mocking
- **Coverage**: Individual functions, classes, and modules
- **Isolation**: Full dependency injection and mocking
- **Location**: `tests/test_*.py`

#### 2. Integration Tests
- **Framework**: pytest with database fixtures
- **Coverage**: Component interactions and data flow
- **Environment**: Isolated test database with Docker
- **Location**: `tests/test_*_integration.py`

#### 3. End-to-End Tests
- **Framework**: pytest with full application startup
- **Coverage**: Complete user workflows and API interactions
- **Environment**: Staging environment simulation
- **Location**: `tests/test_*_e2e.py` (planned)

#### 4. Static Analysis & Code Quality
- **Framework**: mypy, flake8, pylint, black, isort, bandit, safety
- **Coverage**: Type checking, code style, security scanning, formatting
- **Automation**: Pre-commit hooks for continuous quality assurance
- **Configuration**: Strict settings with CI/CD integration

### Test Environment Setup

#### Docker-Based Testing Infrastructure

```yaml
# docker-compose.yml test services
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: music_library_test
    POSTGRES_USER: loist_user
    POSTGRES_PASSWORD: dev_password
  ports:
    - "5432:5432"
```

#### Test Database Management

- **Automatic Setup**: Docker container with pre-configured schema
- **Migration Application**: Automatic schema and index setup
- **Isolation**: Fresh database for each test session
- **Cleanup**: Automatic teardown and connection closure

#### Environment Configuration

```python
# tests/conftest.py
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configure test environment variables."""
    test_env = {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'music_library_test',
        'DB_USER': 'loist_user',
        'DB_PASSWORD': 'dev_password',
        'LOG_LEVEL': 'WARNING',
        'AUTH_ENABLED': 'false',
    }
    os.environ.update(test_env)
```

## Repository Pattern Testing

### Mock Implementation Strategy

#### Dependency Injection

```python
# src/repositories/audio_repository.py
def get_audio_repository() -> AudioRepositoryInterface:
    """Factory function with test mode detection."""
    if os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TEST_MODE') == 'true':
        from tests.conftest import MockAudioRepository
        return MockAudioRepository()
    return PostgresAudioRepository()
```

#### Mock Repository Features

```python
# tests/conftest.py
class MockAudioRepository(AudioRepositoryInterface):
    """Complete mock implementation for testing."""

    def __init__(self):
        self.metadata_store = {}
        self.search_results = []
        self.batch_results = {'inserted_count': 0}

    def save_metadata(self, metadata, audio_gcs_path, thumbnail_gcs_path=None, track_id=None):
        # Mock implementation with validation
        track_id = track_id or metadata.get('id') or f"mock-{len(self.metadata_store)}"
        self.metadata_store[track_id] = {
            'id': track_id,
            **metadata,
            'audio_path': audio_gcs_path,
            'thumbnail_path': thumbnail_gcs_path,
            'status': 'COMPLETED'
        }
        return self.metadata_store[track_id]
```

### Test Data Management

#### Fixture-Based Test Data

```python
@pytest.fixture
def sample_audio_metadata():
    """Standardized test data fixture."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "artist": "Test Artist",
        "title": "Test Track",
        "album": "Test Album",
        "genre": "Rock",
        "year": 2023,
        "duration": 245.5,
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 320000,
        "format": "MP3",
        "status": "COMPLETED"
    }
```

#### State Reset Between Tests

```python
@pytest.fixture(autouse=True)
def reset_mocks(mock_repository):
    """Reset mock state between tests."""
    mock_repository.metadata_store.clear()
    mock_repository.search_results.clear()
    mock_repository.batch_results = {'inserted_count': 0}
```

## Exception Framework Testing

### Unified Exception Handler Testing

#### Framework Architecture

```python
# src/exceptions_new/handler.py
class ExceptionHandler:
    """Unified exception handling with recovery strategies."""

    def __init__(self, config: ExceptionConfig):
        self.config = config
        self.serializer = SafeExceptionSerializer()
        self.recovery_strategies: list[RecoveryStrategy] = []

    def handle_exception(self, exception, context, include_recovery=True):
        """Main exception handling entry point."""
        self._log_exception(exception, context)
        # Recovery logic...
        return self._create_error_response(exception, context)
```

#### Comprehensive Test Coverage

```python
class TestExceptionHandler:
    def test_handle_exception_basic(self, handler, context):
        exception = ValueError("test error")
        response = handler.handle_exception(exception, context)
        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"

    def test_error_code_mapping(self, handler, context):
        test_cases = [
            (ValueError("test"), "VALIDATION_ERROR"),
            (ConnectionError("test"), "CONNECTION_ERROR"),
            (MusicLibraryError("test"), "MUSIC_LIBRARY_ERROR"),
        ]
        for exception, expected_code in test_cases:
            response = handler.handle_exception(exception, context)
            assert response.error_code == expected_code
```

### Recovery Strategy Testing

#### Strategy Pattern Implementation

```python
# src/exceptions_new/recovery.py
class RecoveryStrategy(ABC):
    @abstractmethod
    def can_recover(self, exception, context):
        pass

    @abstractmethod
    def recover(self, exception, context):
        pass

class DatabaseRecoveryStrategy(RecoveryStrategy):
    def can_recover(self, exception, context):
        if not isinstance(exception, OperationalError):
            return False
        return context.can_retry()
```

#### Test Coverage for Recovery

```python
def test_database_recovery_strategy():
    strategy = DatabaseRecoveryStrategy(max_retries=2)

    context = ExceptionContext(operation="db_query", component="database")
    op_error = OperationalError("connection failed")

    assert strategy.can_recover(op_error, context)

    # Test recovery (should raise to trigger retry)
    with pytest.raises(OperationalError):
        strategy.recover(op_error, context)
    assert context.retry_count == 1
```

## Database Integration Testing

### Performance Benchmarking

#### Batch vs Individual Operations

```python
def test_batch_vs_individual_performance(self, db_pool):
    """Compare batch vs individual insert performance."""

    # Test individual inserts
    individual_start = time.time()
    for i in range(5):
        save_audio_metadata(metadata, audio_path, thumbnail_path)
    individual_time = time.time() - individual_start

    # Test batch insert
    batch_data = [{...}] * 5
    batch_start = time.time()
    batch_result = save_audio_metadata_batch(batch_data)
    batch_time = time.time() - batch_start

    # Assert performance improvement
    improvement_ratio = individual_time / batch_time
    assert improvement_ratio > 2.0
```

#### Connection Pool Validation

```python
def test_connection_pool_health(self, db_pool):
    """Test connection pool health monitoring."""
    health = db_pool.health_check()
    assert health['healthy'] is True
    assert 'database_version' in health
    assert health['min_connections'] == db_pool.min_connections
```

### Transaction Testing

#### Rollback on Error

```python
def test_transaction_rollback_on_error(self, db_pool):
    """Test that transactions roll back on errors."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO audio_tracks (id, title) VALUES (%s, %s)",
                       ('test-id', 'Test Track'))
            # Force error
            raise Exception("Test error")

    # Verify rollback
    result = get_audio_metadata_by_id('test-id')
    assert result is None
```

#### Commit on Success

```python
def test_transaction_commit_on_success(self, db_pool):
    """Test that transactions commit on success."""
    result = save_audio_metadata(metadata, audio_path)

    # Verify commit
    retrieved = get_audio_metadata_by_id(result['id'])
    assert retrieved is not None
    assert retrieved['title'] == metadata['title']
```

## FastMCP Integration Testing

### Middleware Testing

```python
class TestFastMCPIntegration:
    def test_middleware_process_exception(self, middleware):
        context = ExceptionContext(operation="mcp_call", component="tools.test")
        exception = ValidationError("invalid MCP call")

        response = middleware.process_exception(exception, context)

        assert response["success"] is False
        assert response["error"]["code"] == "VALIDATION_ERROR"
```

### Global Handler Management

```python
def test_global_handler_management(self, handler):
    from src.exceptions.fastmcp_integration import (
        set_global_exception_handler,
        get_global_exception_handler
    )

    # Initially should raise
    with pytest.raises(RuntimeError):
        get_global_exception_handler()

    # Set handler
    set_global_exception_handler(handler)
    retrieved = get_global_exception_handler()
    assert retrieved is handler
```

## Test Execution and Reporting

### Automated Test Pipeline

#### GitHub Actions Integration

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: music_library_test
          POSTGRES_USER: loist_user
          POSTGRES_PASSWORD: dev_password

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: pytest --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Coverage Requirements

#### Minimum Coverage Targets

- **Unit Tests**: 90% coverage for core modules
- **Integration Tests**: 85% coverage for database operations
- **Exception Framework**: 95% coverage for error handling

#### Coverage Configuration

```ini
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/venv/*",
    "src/fastmcp_setup.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

## Recovery Mechanisms

### Exception Recovery Strategies

#### Automatic Retry Logic

```python
class DatabaseRecoveryStrategy(RecoveryStrategy):
    def __init__(self, max_retries=3, base_delay=0.1):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def recover(self, exception, context):
        if not self.can_recover(exception, context):
            raise exception

        # Exponential backoff
        delay = self.base_delay * (2 ** context.retry_count)
        time.sleep(delay)
        context.increment_retry()

        # Re-raise to trigger retry at caller level
        raise exception
```

#### Circuit Breaker Pattern

```python
class CircuitBreakerRecoveryStrategy(RecoveryStrategy):
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"

    def can_recover(self, exception, context):
        if self.state == "open":
            # Check recovery timeout
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        return True
```

### Database Connection Recovery

#### Pool Management

```python
class DatabasePool:
    def get_connection(self, retry=True, max_retries=3):
        """Get connection with automatic retry and validation."""
        conn = None
        attempts = 0

        while attempts < max_retries:
            try:
                conn = self._pool.getconn()

                # Validate connection
                if not self._validate_connection(conn):
                    self._pool.putconn(conn, close=True)
                    conn = None
                    attempts += 1
                    continue

                return conn

            except Exception as e:
                attempts += 1
                if attempts >= max_retries:
                    raise
```

#### Health Monitoring

```python
def health_check(self):
    """Comprehensive health check."""
    try:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        version() as database_version,
                        COUNT(*) as connection_count
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                result = cur.fetchone()

                return {
                    "healthy": True,
                    "database_version": result["database_version"],
                    "active_connections": result["connection_count"],
                    "pool_stats": self.get_stats(),
                    "timestamp": time.time()
                }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": time.time()
        }
```

## Best Practices

### Test Organization

#### File Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_exception_framework.py    # Exception framework tests
├── test_resources.py         # Resource handler tests
├── test_database_pool.py     # Connection pool tests
├── test_database_operations_integration.py  # DB integration tests
└── test_*.py                # Additional test files
```

#### Naming Conventions

```python
# Test files: test_*.py
# Test classes: Test*
# Test methods: test_*
# Fixtures: snake_case
# Mock objects: mock_*

class TestExceptionHandler:
    def test_handle_exception_basic(self, handler, context):
        pass

@pytest.fixture
def mock_repository():
    return MockAudioRepository()
```

### Mock Strategy

#### Repository Pattern Benefits

- **Isolation**: Tests don't require database connectivity
- **Speed**: In-memory operations are much faster
- **Reliability**: No external dependencies
- **Control**: Precise control over test data and behavior

#### Mock Implementation Guidelines

```python
class MockAudioRepository(AudioRepositoryInterface):
    """Complete mock with realistic behavior."""

    def __init__(self):
        self.store = {}
        self.call_history = []

    def save_metadata(self, *args, **kwargs):
        self.call_history.append(('save_metadata', args, kwargs))
        # Realistic implementation...
```

### Performance Testing

#### Benchmarking Setup

```python
import time
import statistics

def benchmark_operation(operation, iterations=100):
    """Benchmark operation performance."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        operation()
        end = time.perf_counter()
        times.append(end - start)

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times),
        'min': min(times),
        'max': max(times)
    }
```

### Continuous Integration

#### Quality Gates

- **Test Coverage**: >85% overall, >90% for critical modules
- **Performance Regression**: <5% degradation from baseline
- **Error Rates**: Zero test failures in CI pipeline
- **Security**: Automated vulnerability scanning (Bandit + Safety)
- **Code Quality**: Static analysis passing (mypy, flake8, pylint)
- **Formatting**: Consistent code style (black + isort)
- **Type Safety**: Strict type checking compliance

#### Static Analysis Integration

```python
# Pre-commit hooks automatically run quality checks
# .pre-commit-config.yaml defines all quality tools

# Manual quality verification
def run_quality_checks():
    """Run all static analysis tools."""
    tools = [
        "black --check --diff src/ tests/",
        "isort --check-only --diff src/ tests/",
        "flake8 src/ tests/",
        "mypy src/",
        "bandit -r src/",
        "safety check"
    ]
    return all(run_command(tool) for tool in tools)
```

#### Automated Reporting

```python
# Generate comprehensive test report
def generate_test_report(results):
    """Generate detailed test execution report."""
    return {
        'summary': {
            'total_tests': results.testsRun,
            'passed': results.testsRun - len(results.failures) - len(results.errors),
            'failed': len(results.failures),
            'errors': len(results.errors),
        },
        'performance': benchmark_results,
        'coverage': coverage_report,
        'recommendations': generate_recommendations(results)
    }
```

## Maintenance and Evolution

### Test Debt Management

#### Regular Review Process

- **Monthly**: Review test coverage and effectiveness
- **Quarterly**: Update test data and fixtures
- **Bi-annually**: Comprehensive test suite refactoring

#### Test Health Metrics

- **Flakiness Rate**: <1% of tests should be flaky
- **Execution Time**: <10 minutes for full test suite
- **Maintenance Burden**: <20% of development time

### Future Enhancements

#### Planned Improvements

1. **Property-Based Testing**: Use hypothesis for edge case exploration
2. **Load Testing**: Integration with k6 or Locust for performance testing
3. **Chaos Engineering**: Fault injection testing for resilience
4. **AI-Powered Test Generation**: Automated test case generation
5. **Visual Testing**: Screenshot comparison for UI components

#### Monitoring Integration

```python
# Integration with monitoring systems
def report_test_metrics(results):
    """Report test metrics to monitoring system."""
    metrics = {
        'test.success_rate': calculate_success_rate(results),
        'test.execution_time': results.timeTaken,
        'test.coverage': get_coverage_percentage(),
    }

    # Send to monitoring system (Datadog, Prometheus, etc.)
    monitoring_client.send_metrics(metrics)
```

---

## Summary

This testing strategy provides comprehensive coverage across all layers of the application:

- **Unit Testing**: Isolated component testing with mocking
- **Integration Testing**: Component interaction validation
- **Performance Testing**: Benchmarking and optimization validation
- **Recovery Mechanisms**: Automatic error handling and retry logic
- **CI/CD Integration**: Automated testing in deployment pipeline

The framework ensures high code quality, prevents regressions, and provides confidence in deployments while supporting rapid development cycles.
