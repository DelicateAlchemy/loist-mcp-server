# Testing Setup Guide

Complete guide for setting up and running tests in the Loist MCP Server project.

## Quick Start

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Python 3.11+** installed locally
3. **pip** package manager

### Setup Steps

1. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start database service**:
   ```bash
   docker-compose up -d postgres
   ```

3. **Verify database connection** (optional):
   ```bash
   docker-compose exec postgres psql -U loist_user -d loist_mvp -c "SELECT 1"
   ```

4. **Run tests**:
   ```bash
   pytest tests/ -v
   ```

## Test Execution Options

### Option 1: Local Testing (Recommended for Development)

**When to use**: Daily development, debugging, quick iteration

**Setup**:
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Start database service
docker-compose up -d postgres

# Set environment variables (optional, defaults work)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=loist_mvp
export DB_USER=loist_user
export DB_PASSWORD=dev_password
```

**Run tests**:
```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest -m unit -v

# Integration tests
pytest -m integration -v

# With coverage
pytest --cov=src --cov-report=html tests/
```

**Advantages**:
- Fast iteration
- Easy debugging
- Direct access to test output
- No container overhead

### Option 2: Docker Testing (For CI/CD Parity)

**When to use**: Testing in isolated environment, CI/CD debugging

**Setup**:
```bash
# Start all services
docker-compose up -d

# Note: pytest is NOT installed in mcp-server container
# You would need to add a test service (see docker-compose.yml recommendations)
```

**Run tests** (if test service added):
```bash
docker-compose run --rm test-runner pytest tests/ -v
```

**Advantages**:
- Isolated environment
- Matches CI/CD setup
- No local Python dependencies

## Test Categories

### Unit Tests

**Definition**: Fast, isolated tests with no external dependencies

**Run**:
```bash
pytest -m unit -v
```

**Characteristics**:
- No database required
- No GCS required
- Use mocks for external dependencies
- Should complete in <1 second each

**Location**: `tests/unit/test_*.py` or `tests/test_*.py` (auto-marked)

### Integration Tests

**Definition**: Tests component interactions and external services

**Run**:
```bash
pytest -m integration -v
```

**Characteristics**:
- May require database
- May require GCS
- Test real component interactions
- Slower than unit tests

**Location**: `tests/integration/test_*.py` or `tests/test_*_integration.py`

### Database Tests

**Definition**: Tests requiring PostgreSQL database

**Run**:
```bash
# Ensure PostgreSQL is running
docker-compose up -d postgres

# Run database tests
pytest -m requires_db -v
```

**Characteristics**:
- Require PostgreSQL service running
- Use `db_pool` fixture
- Auto-marked based on file patterns

**Location**: `tests/test_database_*.py`, `tests/test_*_integration.py`

### GCS Tests

**Definition**: Tests requiring Google Cloud Storage

**Run**:
```bash
# Set GCS credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Run GCS tests
pytest -m requires_gcs -v
```

**Characteristics**:
- Require GCS credentials
- May use real GCS or mocks
- Auto-marked based on function names

## Environment Variables

### Database Configuration

Tests automatically detect database configuration from environment variables:

```bash
export DB_HOST=localhost          # Default: localhost
export DB_PORT=5432               # Default: 5432
export DB_NAME=loist_mvp          # Default: loist_mvp
export DB_USER=loist_user         # Default: loist_user
export DB_PASSWORD=dev_password   # Default: dev_password
```

**Or use connection string**:
```bash
export DATABASE_URL=postgresql://loist_user:dev_password@localhost:5432/loist_mvp
```

### GCS Configuration

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
export GCS_BUCKET_NAME=loist-mvp-audio-files
export GCS_PROJECT_ID=loist-mvp-dev
```

### Server Configuration

```bash
export SERVER_TRANSPORT=stdio
export AUTH_ENABLED=false
export LOG_LEVEL=WARNING
```

## Test Markers

### Automatic Marker Assignment

The `conftest.py` file automatically assigns markers based on:

- **File paths**: Database tests (`test_database_*.py`), integration tests (`test_*_integration.py`)
- **Function names**: GCS tests (functions with `gcs` in name), slow tests (`performance`, `stress`, `load`)

**You don't need to manually add markers** - they're assigned automatically!

### Manual Markers

Use these markers when you need explicit categorization:

- `@pytest.mark.unit` - Unit test (fast, isolated)
- `@pytest.mark.integration` - Integration test
- `@pytest.mark.slow` - Slow test (>1 second)
- `@pytest.mark.requires_db` - Requires database (auto-assigned)
- `@pytest.mark.requires_gcs` - Requires GCS (auto-assigned)
- `@pytest.mark.requires_tools` - Requires static analysis tools

### Running Tests by Marker

```bash
# Unit tests only
pytest -m unit -v

# Integration tests
pytest -m integration -v

# Exclude slow tests
pytest -m "not slow" -v

# Database tests
pytest -m requires_db -v

# Multiple markers
pytest -m "unit and not slow" -v
```

## Coverage

### Running with Coverage

```bash
# Basic coverage
pytest --cov=src tests/

# HTML report
pytest --cov=src --cov-report=html tests/
# Open: reports/coverage_html/index.html

# Terminal report
pytest --cov=src --cov-report=term-missing tests/

# XML report (for CI/CD)
pytest --cov=src --cov-report=xml tests/
```

### Coverage Requirements

- **Production**: 75% minimum coverage
- **Staging**: 60% minimum coverage
- **New code**: 90% coverage recommended

### Coverage Configuration

Coverage is configured in `pytest.ini`:
- Source: `src/`
- Reports: HTML, XML, terminal
- Exclusions: tests, migrations, venv

## Test Fixtures

### Available Fixtures

**Database fixtures**:
- `db_pool` - Database connection pool
- `test_database_pool` - Test database pool (session-scoped)
- `test_database_transaction` - Isolated transaction (auto-rollback)

**Data fixtures**:
- `sample_audio_metadata` - Standardized test data
- `mock_repository` - Mock repository for unit tests

**Service fixtures**:
- `mock_storage_client` - Mock GCS client
- `test_config` - Test configuration

### Using Fixtures

```python
def test_with_database(db_pool):
    """Test using database fixture."""
    with db_pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            assert result[0] == 1

def test_with_sample_data(sample_audio_metadata):
    """Test using sample data fixture."""
    assert sample_audio_metadata["title"] is not None
    assert sample_audio_metadata["artist"] is not None
```

## Common Test Patterns

### Unit Test Pattern

```python
from unittest.mock import Mock, patch

def test_validation_logic():
    """Unit test with mocked dependencies."""
    # Arrange
    mock_repository = Mock()
    mock_repository.get_data.return_value = {"key": "value"}
    
    # Act
    result = function_under_test(mock_repository)
    
    # Assert
    assert result is not None
    mock_repository.get_data.assert_called_once()
```

### Integration Test Pattern

```python
def test_integration_with_database(db_pool):
    """Integration test with real database."""
    if not is_db_configured():
        pytest.skip("Database not configured")
    
    # Arrange
    test_data = {"title": "Test Track", "artist": "Test Artist"}
    
    # Act
    with db_pool.get_connection() as conn:
        # Perform database operations
        result = save_metadata(conn, test_data)
    
    # Assert
    assert result["id"] is not None
```

### Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality."""
    # Arrange
    input_data = "test"
    
    # Act
    result = await async_function(input_data)
    
    # Assert
    assert result is not None
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError` when running tests

**Solutions**:
1. Check you're in project root directory
2. Verify `src/` directory exists
3. Check `pytest.ini` configuration
4. Try: `export PYTHONPATH=$PWD/src:$PWD`

### Database Connection Errors

**Problem**: `OperationalError` or connection refused

**Solutions**:
1. Check PostgreSQL is running: `docker-compose ps postgres`
2. Start if needed: `docker-compose up -d postgres`
3. Wait a few seconds for database to initialize
4. Verify connection: `docker-compose exec postgres psql -U loist_user -d loist_mvp`
5. Check environment variables: `echo $DB_HOST`

### Pytest Not Found

**Problem**: `pytest: command not found`

**Solutions**:
1. Install dev dependencies: `pip install -r requirements-dev.txt`
2. Or install pytest directly: `pip install pytest`
3. Check Python path: `which python` and `which pytest`

### Coverage Not Working

**Problem**: Coverage reports empty or missing

**Solutions**:
1. Install coverage plugin: `pip install pytest-cov`
2. Run with coverage: `pytest --cov=src tests/`
3. Check coverage config in `pytest.ini`
4. Verify source directory: `ls src/`

### Tests Hang or Timeout

**Problem**: Tests hang indefinitely

**Solutions**:
1. Check database connection (may be waiting for DB)
2. Check for infinite loops in test code
3. Use `pytest -v -s` for verbose output
4. Check Docker container logs: `docker-compose logs postgres`

## CI/CD Testing

### Cloud Build Pipeline

Tests run in Cloud Build using:
- `python:3.11-slim` container (not Docker Compose)
- Dependencies installed: `pip install -r requirements.txt` + test dependencies
- PYTHONPATH: `/workspace/src:/workspace`
- Command: `python -m pytest -m "not (requires_db or requires_gcs or slow or requires_tools)"`

### Local vs CI/CD Differences

| Aspect | Local Development | CI/CD (Cloud Build) |
|--------|------------------|---------------------|
| Python | Local Python 3.11+ | `python:3.11-slim` container |
| Dependencies | `requirements-dev.txt` | `requirements.txt` + test deps |
| Database | Docker Compose PostgreSQL | TestContainers (for DB tests) |
| PYTHONPATH | Auto-handled | `/workspace/src:/workspace` |
| Test Execution | `pytest tests/` | `python -m pytest tests/` |

## Best Practices

### Test Organization

1. **One concept per test**: Each test should verify one specific behavior
2. **Descriptive names**: Test names should explain what they're testing
3. **Independent tests**: Tests should not depend on each other
4. **Fast execution**: Keep tests fast to encourage frequent running

### Test Maintenance

1. **Regular review**: Review and update tests as code changes
2. **Remove flaky tests**: Fix or remove tests that fail intermittently
3. **Update on refactor**: Update tests when refactoring code
4. **Document complex tests**: Add comments for complex test scenarios

### Performance

1. **Use fixtures efficiently**: Share fixtures across tests when possible
2. **Mock external services**: Mock GCS, external APIs for unit tests
3. **Run tests in parallel**: Use `pytest-xdist` for parallel execution
4. **Profile slow tests**: Use `pytest --durations=10` to find slow tests

## Quick Reference

```bash
# Setup
pip install -r requirements-dev.txt
docker-compose up -d postgres

# Run all tests
pytest tests/ -v

# Run unit tests only
pytest -m unit -v

# Run integration tests
pytest -m integration -v

# Run database tests
pytest -m requires_db -v

# Run with coverage
pytest --cov=src --cov-report=html tests/

# Run specific test
pytest tests/test_exceptions.py::TestExceptionHandling::test_validation_error -v

# Debug failing test
pytest -v -s tests/test_failing.py

# Show slow tests
pytest --durations=10 tests/
```

---

**See Also**:
- [Testing Practices Guide](testing-practices-guide.md) - Comprehensive testing documentation
- [Testing Strategy and Recovery](testing-strategy-and-recovery.md) - Testing architecture overview
- [Cursor Testing Rules](../.cursor/rules/testing-workflow.mdc) - Agentic workflow rules

