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
- **`/tests/conftest.py`**: The main `pytest` configuration file, used for defining project-wide fixtures and test helpers.
- **`/tests/database_testing.py`**: A dedicated module for database-related test infrastructure, providing tools for schema isolation, transaction management, and test data generation.

## ▶️ How to Run Tests

### Prerequisites

Ensure you have all the development dependencies installed:

```bash
# Make sure you are in the project's root directory
# and have activated your virtual environment.
pip install -r requirements-dev.txt
```

### Running All Tests

To run the entire test suite, use the following command from the project root:

```bash
pytest
```

### Running Specific Tests

You can run tests in a specific directory or file:

```bash
# Run all unit tests
pytest tests/unit/

# Run a specific test file
pytest tests/integration/test_database_operations_integration.py

# Run a specific test function by name
pytest -k "test_search_library"
```

### Test Coverage

To measure code coverage, use the `pytest-cov` plugin (included in `requirements-dev.txt`):

```bash
# Run tests and generate a coverage report
pytest --cov=src --cov=database

# For a more detailed HTML report:
pytest --cov=src --cov=database --cov-report=html
# Then open `htmlcov/index.html` in your browser.
```

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
