# Testing Setup Guide

Complete guide for setting up and running tests in the Loist MCP Server project.

## Quick Start

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Git** for version control

### Setup Steps

1. **Start services**:
   ```bash
   docker-compose up -d
   ```

2. **Verify services are healthy**:
   ```bash
   docker-compose ps
   ```

3. **Run tests**:
   ```bash
   docker-compose exec mcp-server pytest tests/ -v
   ```

## Test Execution (ALWAYS Use Docker)

**All tests MUST be run inside the Docker container**. The local venv is outdated and has incorrect dependencies.

### Basic Commands

```bash
# All tests
docker-compose exec mcp-server pytest tests/ -v

# Unit tests only
docker-compose exec mcp-server pytest tests/ -m unit -v

# Integration tests
docker-compose exec mcp-server pytest tests/ -m integration -v

# Database tests
docker-compose exec mcp-server pytest tests/ -m requires_db -v

# Specific test file
docker-compose exec mcp-server pytest tests/test_exceptions.py -v

# With coverage
docker-compose exec mcp-server pytest tests/ --cov=src --cov-report=term-missing -v

# Collect only (verify imports work)
docker-compose exec mcp-server pytest tests/ --collect-only
```

### Why Docker?

| Aspect | Docker (✅ Use This) | Local venv (❌ Avoid) |
|--------|---------------------|----------------------|
| Dependencies | Current, correct | Outdated, incorrect |
| PYTHONPATH | Properly configured | Inconsistent |
| Environment | Matches production | May differ |
| Database | Integrated | Requires manual setup |

## Test File Organization

### Where to Put Tests

**ALL tests go in the `tests/` directory**:

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── unit/                 # Unit tests (fast, isolated)
│   └── test_*.py
├── integration/          # Integration tests
│   └── test_*.py
├── a2a/                  # A2A-specific tests
│   └── test_*.py
└── test_*.py             # General tests
```

**NEVER put tests in**:
- Project root (e.g., `test_my_feature.py`)
- `src/` directory (e.g., `src/test_my_feature.py`)

### Import Style

**ALWAYS use standard imports from the `src` package**:

```python
# ✅ CORRECT: Standard imports
from src.exceptions import MusicLibraryError, ValidationError
from src.server import mcp
from src.config import Config
from src.services.metadata_service import MetadataService

# ❌ WRONG: sys.path manipulation
import sys
sys.path.insert(0, 'src')  # NEVER DO THIS
from server import mcp     # Will break

# ❌ WRONG: Direct imports without src prefix
from exceptions import ValidationError  # Will break
```

## Test Categories

### Unit Tests

**Definition**: Fast, isolated tests with no external dependencies

**Run**:
```bash
docker-compose exec mcp-server pytest tests/ -m unit -v
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
docker-compose exec mcp-server pytest tests/ -m integration -v
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
# Database is automatically available in Docker
docker-compose exec mcp-server pytest tests/ -m requires_db -v
```

**Characteristics**:
- PostgreSQL service runs alongside mcp-server
- Use `db_pool` fixture
- Auto-marked based on file patterns

**Location**: `tests/test_database_*.py`, `tests/test_*_integration.py`

## Configuration

### Single Source of Truth: `pyproject.toml`

All pytest configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
pythonpath = ["."]
addopts = "-v --tb=short --strict-markers --disable-warnings --import-mode=importlib"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

**Key settings**:
- `pythonpath = ["."]` - Array format required for `--import-mode=importlib`
- `testpaths = ["tests"]` - Tests only from tests/ directory
- `--import-mode=importlib` - Modern import mode (PEP 451)

**Note**: There is NO `pytest.ini` file. All configuration is in `pyproject.toml`.

### Docker Environment

The Docker container sets `PYTHONPATH=/app`:
- The `src` directory is a package, accessed as `from src.module import ...`
- This matches the pytest `pythonpath = ["."]` setting

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
docker-compose exec mcp-server pytest tests/ -m unit -v

# Integration tests
docker-compose exec mcp-server pytest tests/ -m integration -v

# Exclude slow tests
docker-compose exec mcp-server pytest tests/ -m "not slow" -v

# Database tests
docker-compose exec mcp-server pytest tests/ -m requires_db -v

# Multiple markers
docker-compose exec mcp-server pytest tests/ -m "unit and not slow" -v
```

## Coverage

### Running with Coverage

```bash
# Basic coverage
docker-compose exec mcp-server pytest tests/ --cov=src

# Terminal report with missing lines
docker-compose exec mcp-server pytest tests/ --cov=src --cov-report=term-missing

# HTML report
docker-compose exec mcp-server pytest tests/ --cov=src --cov-report=html
# Reports saved in container - copy out if needed
```

### Coverage Requirements

- **Production**: 75% minimum coverage
- **Staging**: 60% minimum coverage
- **New code**: 90% coverage recommended

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

from src.exceptions import ValidationError


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
from src.services.metadata_service import MetadataService


def test_integration_with_database(db_pool):
    """Integration test with real database."""
    if not is_db_configured():
        pytest.skip("Database not configured")
    
    # Arrange
    test_data = {"title": "Test Track", "artist": "Test Artist"}
    
    # Act
    with db_pool.get_connection() as conn:
        result = save_metadata(conn, test_data)
    
    # Assert
    assert result["id"] is not None
```

### Async Test Pattern

```python
import pytest

from src.services.async_service import async_function


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
1. Verify you're running in Docker:
   ```bash
   docker-compose exec mcp-server pytest tests/ -v
   ```
2. Check container is healthy:
   ```bash
   docker-compose ps
   ```
3. Rebuild container if needed:
   ```bash
   docker-compose up -d --build
   ```
4. Verify imports work:
   ```bash
   docker-compose exec mcp-server python -c "from src.server import mcp; print('OK')"
   ```

### Circular Import Errors

**Problem**: `ImportError: cannot import name 'X' from partially initialized module`

**Cause**: Usually a module name conflict (e.g., having both `src/exceptions.py` AND `src/exceptions/`)

**Solutions**:
1. Check for file/package name conflicts in `src/`
2. Ensure no `sys.path` manipulation in the failing module
3. The `--import-mode=importlib` setting helps prevent this

### Container Issues

**Problem**: Container restarting or tests not running

**Solutions**:
1. Check logs:
   ```bash
   docker-compose logs mcp-server
   ```
2. Verify healthcheck:
   ```bash
   docker-compose exec mcp-server python -c "from src.server import mcp; print('OK')"
   ```
3. Full rebuild:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

### Tests Not Collected

**Problem**: `pytest tests/ --collect-only` shows 0 items

**Solutions**:
1. Check test files are in `tests/` directory (not root or src/)
2. Check test file names match `test_*.py`
3. Check test function names match `test_*`
4. Verify tests directory is mounted:
   ```bash
   docker-compose exec mcp-server ls tests/
   ```

## CI/CD Testing

### Cloud Build Pipeline

Tests run in Cloud Build using:
- `python:3.11-slim` container
- Dependencies installed: `pip install -r requirements.txt` + test dependencies
- PYTHONPATH: `/workspace`
- Command: `python -m pytest tests/ -m "not (requires_db or requires_gcs or slow or requires_tools)"`

### Local vs CI/CD Differences

| Aspect | Local (Docker) | CI/CD (Cloud Build) |
|--------|----------------|---------------------|
| Container | docker-compose | Cloud Build step |
| PYTHONPATH | `/app` | `/workspace` |
| Database | Docker Compose PostgreSQL | Excluded by marker |
| Test Execution | `docker-compose exec ... pytest` | `python -m pytest` |

## Best Practices

### Test Organization

1. **One concept per test**: Each test should verify one specific behavior
2. **Descriptive names**: Test names should explain what they're testing
3. **Independent tests**: Tests should not depend on each other
4. **Fast execution**: Keep tests fast to encourage frequent running

### Import Best Practices

1. **Always use `from src.*` imports** - never manipulate sys.path
2. **Put tests in `tests/`** - never in src/ or project root
3. **Use fixtures** - don't duplicate setup code
4. **Mock external dependencies** - keep unit tests fast and reliable

### Test Maintenance

1. **Regular review**: Review and update tests as code changes
2. **Remove flaky tests**: Fix or remove tests that fail intermittently
3. **Update on refactor**: Update tests when refactoring code
4. **Document complex tests**: Add comments for complex test scenarios

## Quick Reference

```bash
# Start services
docker-compose up -d

# Run all tests
docker-compose exec mcp-server pytest tests/ -v

# Run unit tests only
docker-compose exec mcp-server pytest tests/ -m unit -v

# Run integration tests
docker-compose exec mcp-server pytest tests/ -m integration -v

# Run database tests
docker-compose exec mcp-server pytest tests/ -m requires_db -v

# Run with coverage
docker-compose exec mcp-server pytest tests/ --cov=src --cov-report=term-missing

# Run specific test
docker-compose exec mcp-server pytest tests/test_exceptions.py::TestExceptionHandling::test_validation_error -v

# Debug failing test
docker-compose exec mcp-server pytest tests/test_failing.py -v -s

# Show slow tests
docker-compose exec mcp-server pytest tests/ --durations=10

# Verify imports
docker-compose exec mcp-server python -c "from src.server import mcp; print('OK')"

# Rebuild after changes
docker-compose up -d --build
```

---

**See Also**:
- [Testing Practices Guide](testing-practices-guide.md) - Comprehensive testing documentation
- [Testing Strategy and Recovery](testing-strategy-and-recovery.md) - Testing architecture overview
- [Cursor Testing Rules](../.cursor/rules/testing-workflow.mdc) - Agentic workflow rules
