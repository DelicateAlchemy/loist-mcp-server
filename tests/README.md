# Loist Music Library MCP Server - Testing Guide

This directory contains the comprehensive test suite for the Loist Music Library MCP Server. The project uses `pytest` as its primary testing framework and follows a structured approach to ensure code quality, reliability, and maintainability.

## 🧪 Testing Philosophy

The testing strategy is built on a multi-layered approach to cover everything from individual functions to complete user workflows:

- **Unit Tests**: For fast, isolated validation of individual components.
- **Integration Tests**: To ensure that different parts of the system work together correctly.
- **Functional Tests**: For end-to-end validation of user-facing features.
- **Static Analysis & Security**: To maintain code quality and prevent common vulnerabilities.

## 🗂️ Directory Structure

The `tests/` directory is organized to reflect the different types of testing:

- **`/tests/unit`**: Contains unit tests that are self-contained and do not require external services like databases or network access. They are fast and should be run frequently during development.
- **`/tests/integration`**: Houses integration tests that verify the interaction between different components, such as the application logic and the database. These tests may require a running database instance.
- **`/tests/functional`**: For end-to-end tests that simulate real user scenarios. These are the slowest and most comprehensive tests.
- **`/tests/conftest.py`**: The main test fixtures file, used for defining project-wide fixtures and test helpers.
- **`pyproject.toml`**: Contains pytest configuration including markers and test options.
- **`/tests/database_testing.py`**: A dedicated module for database-related test infrastructure, providing tools for schema isolation, transaction management, and test data generation.

## ▶️ How to Run Tests

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Start the development environment**:
   ```bash
   docker-compose up -d
   ```

> ⚠️ **IMPORTANT**: Always run tests inside Docker. The local venv is outdated and has incorrect dependencies.

### Running All Tests

To run the entire test suite, use the following command from the project root:

```bash
docker-compose exec mcp-server pytest tests/ -v
```

### Running Specific Tests

You can run tests in a specific directory or file:

```bash
# Run all unit tests
docker-compose exec mcp-server pytest tests/unit/ -v

# Run a specific test file
docker-compose exec mcp-server pytest tests/integration/test_database_operations_integration.py -v

# Run a specific test function by name
docker-compose exec mcp-server pytest tests/ -k "test_search_library" -v
```

### Test Coverage

To measure code coverage:

```bash
# Run tests and generate a coverage report
docker-compose exec mcp-server pytest tests/ --cov=src --cov=database

# For a more detailed terminal report:
docker-compose exec mcp-server pytest tests/ --cov=src --cov=database --cov-report=term-missing
```

### Running Tests by Environment

The test suite uses pytest markers to categorize tests based on their external dependencies. This allows you to run only the tests appropriate for your development environment.

#### Local Development (Docker)

For local development in Docker Compose (no database/GCS access), run only unit tests:

```bash
# Run tests that don't require external services
docker-compose exec mcp-server python -m pytest tests/ \
  -m "not (requires_db or requires_gcs or requires_tools)"

# Expected: ~629 tests collected (209 deselected)
```

#### With Database Access

When you have database access available:

```bash
# Run tests that require database
docker-compose exec mcp-server python -m pytest tests/ -m "requires_db"

# Or run all tests including database tests
docker-compose exec mcp-server python -m pytest tests/ \
  -m "not (requires_gcs or requires_tools)"
```

#### With Full Environment

When all services are available (database, GCS, tools):

```bash
# Run all tests
docker-compose exec mcp-server python -m pytest tests/

# Expected: 838 tests collected
```

### Test Markers

The following pytest markers are used to categorize tests by their dependencies:

| Marker | Description | When to Use |
|--------|-------------|-------------|
| `unit` | Fast, isolated unit tests with no external dependencies | Always run locally |
| `integration` | Tests that verify component interactions | Run with database |
| `functional` | End-to-end tests simulating user scenarios | Run with full environment |
| `slow` | Tests that take >5 seconds to run | Skip for quick feedback |
| `requires_db` | Tests requiring PostgreSQL database connection | Skip without database |
| `requires_gcs` | Tests requiring Google Cloud Storage access | Skip without GCS |
| `requires_tools` | Tests requiring static analysis tools (black, isort, mypy, etc.) | Skip without tools |
| `regression` | Tests for previously fixed bugs | Run to prevent regressions |
| `tasks_13_14` | Tests related to specific tasks 13 and 14 | Run for targeted testing |

### Expected Test Behavior

| Environment | Tests Run | Expected Failures | Notes |
|-------------|-----------|-------------------|-------|
| Local Docker | 629 tests | 0 | No external dependencies |
| With Database | 729 tests | 0 | Database tests included |
| With GCS | 732 tests | 0 | GCS tests included |
| Full Environment | 838 tests | 0 | All tests should pass |

**Important**: Tests with missing dependencies will either be skipped (if properly marked) or fail. The goal is 0 failures in all environments when dependencies are available.

## 🛠️ Testing Tools & Fixtures

- **`pytest`**: The core testing framework.
- **`pytest-asyncio`**: For testing `async` code.
- **`pytest-cov`**: For measuring test coverage.
- **`Mocking`**: `unittest.mock` is used extensively to isolate components.
- **Custom Fixtures**: `conftest.py` and other test modules define custom fixtures for setting up test data, mock objects, and test clients.

## CI/CD Integration

All tests are automatically run on every push and pull request via **Google Cloud Build**. The pipeline is configured in `cloudbuild.yaml` and `cloudbuild-staging.yaml` and includes:

- Running unit, integration, and functional tests.
- Performing static analysis (`mypy`, `flake8`, `black`).
- Security scanning (`bandit`).
- Enforcing code coverage minimums.

For more details on the CI/CD pipeline and testing practices, please refer to the main project documentation:

- **[Testing Practices Guide](../docs/testing-practices-guide.md)**
- **[Pre-PR Testing Guide](../docs/pre-pr-testing-guide.md)**
