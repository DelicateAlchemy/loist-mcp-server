# Testing Practices Guide

This guide provides comprehensive documentation for the testing infrastructure and practices implemented in Task 16 of the Loist Music Library MCP Server project.

## Overview

The project implements a multi-layered testing strategy with automated CI/CD integration through Google Cloud Build. The testing infrastructure includes:

- **Pytest Framework**: Comprehensive test execution with coverage analysis
- **Static Analysis**: Code quality checks with mypy, flake8, black, and isort
- **Security Scanning**: Automated vulnerability detection with Bandit
- **Database Testing**: Isolated test environments with transaction rollback
- **CI/CD Integration**: Automated testing in Cloud Build pipelines

## Testing Infrastructure Components

### 1. Pytest Framework Setup

#### Configuration (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --disable-warnings
    --tb=short
    --cov=.
    --cov-report=html:coverage-reports/htmlcov
    --cov-report=xml:coverage-reports/coverage.xml
    --cov-fail-under=80
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, may need external services)
    functional: End-to-end functional tests
    regression: Regression tests for bug fixes
    fastmcp: FastMCP-specific tests
```

#### Test Directory Structure
```
tests/
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_exceptions.py
│   ├── test_validation.py
│   └── test_utils.py
├── integration/            # Integration tests
│   ├── test_database_operations.py
│   ├── test_fastmcp_tools.py
│   └── test_api_endpoints.py
├── functional/             # End-to-end tests
│   ├── test_audio_processing_workflow.py
│   └── test_user_journeys.py
├── conftest.py             # Shared fixtures and configuration
└── test_*.py              # General test files
```

### 2. Database Testing Infrastructure (Task 17)

The database testing infrastructure provides comprehensive testing capabilities for database operations, migrations, connection pooling, transactions, full-text search, and data integrity validation.

#### Core Components

##### TestDatabaseManager
Provides isolated database testing with automatic cleanup and schema isolation:

```python
from tests.database_testing import TestDatabaseManager

def test_database_operations():
    """Test database operations with automatic isolation."""
    db_manager = TestDatabaseManager()
    db_manager.setup_test_database()

    try:
        # All database operations happen in test schema
        # Tests are completely isolated from production data
        with db_manager.transaction_context() as conn:
            # Database operations here
            # Changes automatically rolled back after test
            pass
    finally:
        db_manager.cleanup_test_database()
```

##### MigrationTestRunner
Comprehensive migration testing with schema isolation and validation:

```python
from tests.database_testing import MigrationTestRunner

def test_migration_application():
    """Test migration application and validation."""
    runner = MigrationTestRunner()
    runner.setup_test_migration_schema()

    try:
        # Get migration file
        migration_file = Path("database/migrations/001_initial_schema.sql")

        # Apply migration
        result = runner.apply_migration_to_test_schema(migration_file)
        assert result['success'] is True

        # Verify schema changes
        expected_changes = {
            'tables': ['audio_tracks'],
            'columns': {
                'audio_tracks': ['id', 'title', 'artist', 'album']
            }
        }
        verification = runner.verify_migration_schema_changes(migration_file, expected_changes)
        assert verification['all_passed'] is True

        # Test idempotency (safe to run multiple times)
        assert runner.test_migration_idempotency(migration_file)

    finally:
        runner.cleanup_test_migration_schema()
```

#### Test Data Management

##### TestDataFactory
Generates diverse test data scenarios:

```python
from tests.database_testing import TestDataFactory

def test_with_various_data_scenarios():
    """Test with different data scenarios."""
    factory = TestDataFactory()

    # Basic track data
    basic_track = factory.create_basic_track()

    # Batch data for performance testing
    track_batch = factory.create_track_batch(100)

    # Edge cases (empty strings, max lengths, unicode)
    edge_cases = factory.create_edge_case_tracks()

    # Search-specific test data
    search_tracks = factory.create_search_test_tracks()
```

##### DatabaseMockFactory
Provides mock objects for unit testing without database dependencies:

```python
from tests.database_testing import DatabaseMockFactory

def test_business_logic_without_database():
    """Unit test business logic with mocked database."""
    mock_connection = DatabaseMockFactory.create_mock_connection()
    mock_pool = DatabaseMockFactory.create_mock_pool()

    # Test logic that interacts with database
    # All database calls are mocked
    result = business_function(mock_connection)
    assert result is not None
```

#### Database Testing Categories

##### Migration Testing
- **Schema Validation**: Verify migrations create expected tables, columns, indexes
- **Idempotency Testing**: Ensure migrations can be safely re-run
- **Dependency Analysis**: Validate migration ordering and dependencies
- **Checksum Verification**: Ensure migration files haven't been tampered with
- **Performance Tracking**: Monitor migration execution times

##### Connection Pool Testing
- **Connection Acquisition/Release**: Test proper connection lifecycle
- **Stress Testing**: Simulate high concurrent connection usage
- **Timeout Handling**: Verify timeout behavior under load
- **Pool Configuration**: Validate pool size limits and behavior
- **Health Monitoring**: Test connection health checks and recovery

##### Transaction Testing
- **Transaction Isolation**: Verify transaction boundaries and isolation levels
- **Commit/Rollback Scenarios**: Test successful commits and error rollbacks
- **Nested Transactions**: Validate nested transaction behavior
- **Timeout Handling**: Test transaction timeouts and deadlock detection
- **Concurrency Testing**: Verify transaction behavior under concurrent access

##### Full-Text Search Testing (Task 17.4)
The full-text search testing infrastructure provides comprehensive validation of PostgreSQL full-text search functionality with dedicated test classes for different aspects of search behavior.

**SearchIndexTests** - Validates search index creation and maintenance:
```python
from tests.test_full_text_search import SearchIndexTests

def test_search_index_creation(test_db_manager):
    """Test that full-text search indexes are properly created."""
    search_tests = SearchIndexTests(test_db_manager)
    search_tests.test_search_index_creation()
    search_tests.test_search_index_updates()
    search_tests.test_search_vector_composition()
```

**SearchQueryTests** - Tests various search query patterns and types:
```python
from tests.test_full_text_search import SearchQueryTests

def test_search_query_functionality(test_db_manager):
    """Test exact match, fuzzy search, and multi-word queries."""
    search_tests = SearchQueryTests(test_db_manager)
    search_tests.test_exact_match_search()
    search_tests.test_multi_word_search()
    search_tests.test_prefix_suffix_matching()
    search_tests.test_fuzzy_search_patterns()
    search_tests.test_search_ranking()
    search_tests.test_empty_and_invalid_queries()
```

**SearchPerformanceTests** - Benchmarks search performance across dataset sizes:
```python
from tests.test_full_text_search import SearchPerformanceTests

def test_search_performance(test_db_manager):
    """Test search performance with different dataset sizes."""
    perf_tests = SearchPerformanceTests(test_db_manager)
    perf_tests.test_small_dataset_performance()      # < 0.1s target
    perf_tests.test_medium_dataset_performance()     # < 0.2s target
    perf_tests.test_search_pagination_performance()
    perf_tests.test_search_with_filters_performance()
```

**SearchRelevanceTests** - Validates result ranking and relevance accuracy:
```python
from tests.test_full_text_search import SearchRelevanceTests

def test_search_relevance(test_db_manager):
    """Test search result relevance and ranking."""
    relevance_tests = SearchRelevanceTests(test_db_manager)
    relevance_tests.test_relevance_ranking_accuracy()
    relevance_tests.test_multiple_field_relevance()
    relevance_tests.test_relevance_score_distribution()
```

**Full-Text Search Testing Features**:
- **Index Creation**: Verify GIN indexes are built correctly in test schema
- **Query Accuracy**: Test exact matches, fuzzy search, prefix/suffix matching
- **Multi-Word Queries**: Validate AND operations for complex search terms
- **Performance Validation**: Monitor response times with configurable thresholds
- **Relevance Testing**: Validate search result ranking and score distribution
- **Index Updates**: Test automatic search vector updates after data changes
- **Edge Case Handling**: Validate behavior with empty/invalid queries
- **Dataset Scaling**: Test performance with small (25), medium (200), and large datasets
- **Pagination Testing**: Verify efficient result pagination
- **Advanced Filtering**: Test search with status, year, format, and rank filters

##### Data Integrity Testing
- **Constraint Enforcement**: Test foreign keys, unique constraints, check constraints
- **Data Validation**: Verify application-level validation rules
- **Consistency Checks**: Ensure data consistency across related tables
- **Edge Case Handling**: Test NULL values, boundary conditions, special characters
- **Bulk Operation Validation**: Test integrity during batch operations

#### Testing Patterns

##### Schema Isolation Pattern
```python
@pytest.fixture
def isolated_database():
    """Provide completely isolated database for testing."""
    db_manager = TestDatabaseManager()
    db_manager.setup_test_database()

    yield db_manager

    db_manager.cleanup_test_database()

def test_database_operation(isolated_database):
    """Test runs in completely isolated environment."""
    # No interference with production data
    # Automatic cleanup after test
    pass
```

##### Migration Validation Pattern
```python
def test_migration_creates_expected_schema():
    """Validate migration creates expected database structure."""
    runner = MigrationTestRunner()

    # Setup isolated schema
    runner.setup_test_migration_schema()

    try:
        # Apply migration
        migration_file = Path("database/migrations/001_initial_schema.sql")
        result = runner.apply_migration_to_test_schema(migration_file)

        # Verify success
        assert result['success'] is True

        # Verify schema state
        verification = runner.verify_migration_schema_changes(migration_file, {
            'tables': ['audio_tracks'],
            'columns': {'audio_tracks': ['id', 'title', 'artist', 'album', 'genre']}
        })
        assert verification['all_passed'] is True

    finally:
        runner.cleanup_test_migration_schema()
```

##### Performance Testing Pattern
```python
def test_operation_performance_under_load():
    """Test performance characteristics under various loads."""
    # Test with different data sizes
    for size in [10, 100, 1000]:
        data = TestDataFactory.create_track_batch(size)

        start_time = time.time()
        result = bulk_operation(data)
        duration = time.time() - start_time

        # Verify performance requirements
        assert duration < size * 0.01  # Linear performance requirement
        assert result['processed_count'] == size
```

#### Key Features

- **Complete Schema Isolation**: Tests run in dedicated `test_schema` preventing production data interference
- **Automatic Transaction Rollback**: All changes automatically rolled back after each test
- **Comprehensive Mocking**: Full mock support for unit testing without database dependencies
- **Migration Safety**: Idempotency, dependency, and checksum validation for migrations
- **Performance Monitoring**: Built-in timing and performance tracking for operations
- **Edge Case Coverage**: Extensive test data factories for boundary and edge case testing
- **Error Recovery**: Robust error handling and recovery testing capabilities

#### Connection Pool and Transaction Testing (Task 17.3)

Task 17.3 provides enterprise-grade testing for database connection pools and transaction management, including stress testing, concurrent operations, and failure scenario validation.

##### Connection Pool Testing Classes

**TestConnectionPoolStressTesting** - Validates pool behavior under extreme load:

```python
# Test concurrent connection acquisition
def test_concurrent_connection_acquisition(self, db_pool):
    """Test acquiring multiple connections concurrently."""
    results = []
    errors = []

    def acquire_connection(worker_id):
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Perform database operation
                cur.execute("SELECT %s as worker_id", (worker_id,))
                results.append(cur.fetchone()[0])

    # Launch 10 concurrent workers
    threads = [threading.Thread(target=acquire_connection, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 10  # All workers completed successfully
```

**TestConnectionPoolConfiguration** - Validates pool setup and configuration:

```python
def test_pool_configuration_validation(self):
    """Test that pool configuration is validated properly."""
    from database import DatabasePool

    # Test valid configuration
    pool = DatabasePool(min_connections=1, max_connections=5)
    assert pool.min_connections == 1
    assert pool.max_connections == 5

    # Test bounds checking
    pool = DatabasePool(min_connections=5, max_connections=3)
    assert pool.min_connections <= pool.max_connections
```

**TestConnectionLifecycle** - Tests complete connection lifecycle:

```python
def test_connection_proper_cleanup(self, db_pool):
    """Test that connections are properly cleaned up."""
    initial_stats = db_pool.get_stats()

    # Use several connections
    for i in range(3):
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT %s", (i,))

    # Verify connections returned to pool
    final_stats = db_pool.get_stats()
    assert abs(final_stats['connections_available'] - initial_stats['connections_available']) <= 3
```

##### Transaction Testing Classes

**TestTransactionCommitRollback** - Tests transaction commit and rollback scenarios:

```python
def test_successful_transaction_commit(self, test_schema_setup):
    """Test that successful transactions commit properly."""
    manager = test_schema_setup

    with manager.committing_transaction_context() as conn:
        with conn.cursor() as cur:
            # Insert test data
            cur.execute("""
                INSERT INTO test_schema.transaction_test (name, balance)
                VALUES (%s, %s) RETURNING id
            """, ("Commit Test", 100.50))

            inserted_id = cur.fetchone()[0]

    # Verify transaction was committed (data persists)
    with manager._pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM test_schema.transaction_test WHERE id = %s", (inserted_id,))
            result = cur.fetchone()
            assert result[0] == "Commit Test"
```

**TestTransactionIsolationLevels** - Tests different isolation levels:

```python
def test_read_committed_isolation(self, test_schema_setup):
    """Test READ COMMITTED isolation level."""
    manager = test_schema_setup

    # Insert initial data
    with manager.transaction_context() as conn:
        # Setup test data
        pass

    # Test concurrent read/write behavior
    results = []

    def transaction_worker(worker_id):
        with manager.transaction_context() as conn:
            # Perform operations and check isolation
            pass

    # Run concurrent transactions
    threads = [threading.Thread(target=transaction_worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
```

**TestTransactionTimeoutDeadlock** - Tests timeout and deadlock handling:

```python
def test_deadlock_detection_simulation(self, test_schema_setup):
    """Test deadlock detection and handling."""
    manager = test_schema_setup

    results = []

    def deadlock_worker(worker_id):
        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    if worker_id == 1:
                        # Lock record 1 then try to lock record 2
                        cur.execute("SELECT * FROM test_table WHERE id = 1 FOR UPDATE")
                        time.sleep(0.1)
                        cur.execute("SELECT * FROM test_table WHERE id = 2 FOR UPDATE")
                    else:
                        # Lock record 2 then try to lock record 1
                        cur.execute("SELECT * FROM test_table WHERE id = 2 FOR UPDATE")
                        time.sleep(0.1)
                        cur.execute("SELECT * FROM test_table WHERE id = 1 FOR UPDATE")
            results.append(f"worker_{worker_id}_success")
        except Exception as e:
            results.append(f"worker_{worker_id}_error: {str(e)[:50]}")

    # Run conflicting transactions
    threads = [threading.Thread(target=deadlock_worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Verify deadlock was detected and handled
    success_count = sum(1 for r in results if "success" in r)
    assert success_count >= 1  # At least one transaction should succeed
```

**TestConcurrentTransactions** - Tests concurrent transaction behavior:

```python
def test_concurrent_transaction_isolation(self, test_schema_setup):
    """Test that concurrent transactions are properly isolated."""
    manager = test_schema_setup

    results = []

    def concurrent_transaction_worker(worker_id, operation):
        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    if operation == "insert":
                        cur.execute("INSERT INTO test_table (data) VALUES (%s)", (worker_id,))
                    elif operation == "update":
                        cur.execute("UPDATE test_table SET data = data + 1")
                    elif operation == "select":
                        cur.execute("SELECT COUNT(*) FROM test_table")
                        count = cur.fetchone()[0]
                        results.append(("select", worker_id, count))
            results.append((operation, worker_id, "success"))
        except Exception as e:
            results.append((operation, worker_id, f"error: {str(e)[:50]}"))

    # Run concurrent operations
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(concurrent_transaction_worker, i, ["insert", "update", "select"][i % 3])
                  for i in range(5)]
        for future in futures:
            future.result()

    # Verify concurrent operations completed
    operations_completed = len([r for r in results if r[2] == "success"])
    assert operations_completed > 0
```

##### Transaction Context Managers

**committing_transaction_context()** - Commits successful transactions:

```python
# Unlike transaction_context() which always rolls back,
# committing_transaction_context() commits successful operations
def test_with_commit(self, test_schema_setup):
    manager = test_schema_setup

    with manager.committing_transaction_context() as conn:
        # Operations here will be committed if successful
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_table (data) VALUES (%s)", ("test",))

    # Data persists after context manager exits
    # Verify with separate connection
```

**transaction_context()** - Always rolls back for test isolation:

```python
def test_with_rollback(self, test_schema_setup):
    manager = test_schema_setup

    with manager.transaction_context() as conn:
        # Operations here will be rolled back
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_table (data) VALUES (%s)", ("test",))

    # Data does not persist - rolled back automatically
```

##### Test Fixtures for Connection Pool and Transaction Testing

```python
@pytest.fixture
def test_schema_setup(db_pool):
    """Set up test schema for transaction testing."""
    from tests.database_testing import TestDatabaseManager

    manager = TestDatabaseManager()
    manager.setup_test_database()

    # Create test tables for transaction testing
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_schema.transaction_test (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    balance DECIMAL(10,2) DEFAULT 0
                );
            """)
        conn.commit()

    yield manager
    manager.cleanup_test_database()
```

##### Connection Pool and Transaction Testing Patterns

**Stress Testing Pattern**:
```python
def test_connection_pool_under_load(db_pool):
    """Test pool behavior under concurrent load."""
    def load_worker():
        for _ in range(100):
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")

    # Run multiple workers concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(load_worker) for _ in range(10)]
        for future in futures:
            future.result()

    # Verify pool health
    health = db_pool.health_check()
    assert health['healthy'] is True
```

**Transaction Atomicity Pattern**:
```python
def test_transaction_atomicity(test_schema_setup):
    """Test that transactions maintain atomicity."""
    manager = test_schema_setup

    try:
        with manager.committing_transaction_context() as conn:
            with conn.cursor() as cur:
                # Multiple related operations
                cur.execute("INSERT INTO accounts (name) VALUES (%s)", ("Alice",))
                cur.execute("INSERT INTO accounts (name) VALUES (%s)", ("Bob",))
                # Simulate error - should rollback all
                raise Exception("Simulated failure")
    except Exception:
        pass

    # Verify atomicity - either all operations succeeded or none
    with manager._pool.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM accounts WHERE name IN (%s, %s)", ("Alice", "Bob"))
            count = cur.fetchone()[0]
            assert count in [0, 2]  # All or nothing
```

**Isolation Level Testing Pattern**:
```python
def test_isolation_level_behavior(test_schema_setup):
    """Test specific isolation level behavior."""
    manager = test_schema_setup

    # Test phenomena that should be prevented at certain isolation levels
    # (dirty reads, non-repeatable reads, phantom reads)

    results = []

    def reader():
        with manager.transaction_context() as conn:
            # Reader transaction
            pass

    def writer():
        with manager.transaction_context() as conn:
            # Writer transaction
            pass

    # Run concurrent reader/writer transactions
    # Verify isolation level prevents unwanted phenomena
```

##### Key Features of Connection Pool and Transaction Testing

- **Stress Testing**: Validates pool behavior under extreme concurrent load (10+ connections)
- **Timeout Handling**: Tests graceful timeout behavior and resource cleanup
- **Transaction Atomicity**: Ensures all-or-nothing transaction behavior
- **Isolation Validation**: Verifies proper transaction isolation levels and consistency
- **Deadlock Detection**: Tests deadlock prevention and resolution mechanisms
- **Concurrent Safety**: Validates thread-safe connection pool operations
- **Resource Management**: Ensures proper connection lifecycle and cleanup
- **Error Recovery**: Tests system resilience under failure conditions
- **Performance Monitoring**: Built-in timing and health monitoring during tests

### 3. Static Analysis Tools

#### MyPy Configuration (`.mypy.ini`)
```ini
[mypy]
python_version = 3.11
disallow_untyped_defs = True
warn_return_any = True
warn_unused_configs = True
disallow_incomplete_defs = True

# Module-specific overrides
[mypy-tests.*]
disallow_untyped_defs = False
[mypy-scripts.*]
disallow_untyped_defs = False
```

#### Code Quality Standards
- **Black**: Line length 100 characters
- **isort**: Black-compatible import sorting
- **flake8**: PEP 8 compliance with custom ignores
- **mypy**: Strict type checking with gradual adoption

### 4. Security Scanning

#### Bandit Configuration (`.bandit`)
```yaml
exclude_dirs:
  - tests
  - scripts
  - venv
skips:
  - B101  # Assert used (acceptable in tests)
  - B601  # Shell usage (needed for some operations)
```

## Testing Categories and Patterns

### Unit Tests

**Purpose**: Test individual functions and classes in isolation.

**Example**:
```python
import pytest
from src.validation import validate_audio_url

class TestAudioUrlValidation:
    """Test URL validation logic."""

    def test_valid_http_url(self):
        """Test valid HTTP URLs are accepted."""
        assert validate_audio_url("https://example.com/audio.mp3") is True

    def test_invalid_scheme(self):
        """Test invalid URL schemes are rejected."""
        with pytest.raises(ValidationError):
            validate_audio_url("ftp://example.com/audio.mp3")

    @pytest.mark.parametrize("invalid_url", [
        "not-a-url",
        "",
        "http://",  # Missing domain
        "https://",  # Missing domain
    ])
    def test_invalid_urls_rejected(self, invalid_url):
        """Test various invalid URLs are rejected."""
        with pytest.raises(ValidationError):
            validate_audio_url(invalid_url)
```

### Integration Tests

**Purpose**: Test component interactions and external service integrations.

**Example**:
```python
import pytest
from tests.conftest import get_test_database, get_test_repository

class TestAudioRepositoryIntegration:
    """Test repository layer with database integration."""

    def test_save_and_retrieve_metadata(self):
        """Test complete save and retrieve workflow."""
        with get_test_database() as db, get_test_repository(db) as repo:
            # Create test data
            metadata = AudioMetadata(
                title="Test Track",
                artist="Test Artist",
                duration=180.5
            )

            # Save through repository
            saved = repo.save_metadata(metadata)
            assert saved.id is not None

            # Retrieve and verify
            retrieved = repo.get_metadata_by_id(saved.id)
            assert retrieved.title == "Test Track"
            assert retrieved.artist == "Test Artist"
```

### Functional Tests

**Purpose**: Test complete user workflows end-to-end.

**Example**:
```python
import pytest
from tests.conftest import get_test_client

class TestAudioProcessingWorkflow:
    """Test complete audio processing workflow."""

    def test_process_audio_complete_workflow(self):
        """Test the complete audio processing workflow."""
        with get_test_client() as client:
            # Upload audio file
            response = client.post("/process-audio", json={
                "url": "https://example.com/test.mp3",
                "metadata": {"title": "Test Song"}
            })

            assert response.status_code == 200
            result = response.json()

            # Verify processing completed
            assert result["status"] == "completed"
            assert "audio_id" in result
            assert "metadata" in result

            # Verify audio is retrievable
            audio_id = result["audio_id"]
            get_response = client.get(f"/audio/{audio_id}")
            assert get_response.status_code == 200
```

### Regression Tests

**Purpose**: Ensure previously fixed bugs don't reoccur.

**Example**:
```python
import pytest
from src.exception_serializer import SafeExceptionSerializer
from src.exceptions import AudioProcessingError
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

class TestExceptionSerializationRegression:
    """Regression tests for Task 13: FastMCP Exception Serialization"""

    def test_complex_object_serialization(self):
        """Regression test: Complex objects in exceptions should serialize safely."""
        serializer = SafeExceptionSerializer()

        # This specific scenario caused NameError before Task 13 fix
        complex_details = {
            "datetime": datetime.now(),
            "path": Path("/tmp/test.mp3"),
            "mock": MagicMock(),
            "nested": {
                "another_mock": MagicMock(),
                "list_with_complex": [datetime.now(), Path("/tmp")]
            }
        }

        exception = AudioProcessingError("Processing failed", complex_details)
        result = serializer.serialize_exception(exception)

        # Should not raise JSON serialization errors
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Complex objects should be safely converted
        assert "<datetime object>" in parsed["details"]["datetime"]
        assert "<PosixPath object>" in parsed["details"]["path"]
        assert "<MagicMock object>" in parsed["details"]["mock"]
```

## Test Fixtures and Utilities

### Shared Fixtures (`tests/conftest.py`)

```python
import pytest
from unittest.mock import Mock
import asyncio
from tests.database_fixtures import get_test_database, get_test_pool
from tests.mcp_fixtures import get_test_mcp_client, get_test_tools

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "database_url": "postgresql://test:test@localhost:5433/test_db",
        "storage_bucket": "test-bucket",
        "log_level": "DEBUG"
    }

@pytest.fixture
def mock_storage_client():
    """Mock Google Cloud Storage client."""
    client = Mock()
    client.bucket.return_value = Mock()
    return client

@pytest.fixture
def sample_audio_metadata():
    """Provide sample audio metadata for testing."""
    return {
        "title": "Sample Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 180.5,
        "format": "mp3",
        "bitrate": 192,
        "size_bytes": 1024000
    }
```

### Database Testing Fixtures

```python
import pytest
from database.pool import DatabasePool
from database.operations import create_database_schema

@pytest.fixture(scope="session")
def test_database_pool():
    """Create test database pool for session."""
    pool = DatabasePool(
        host="localhost",
        port=5433,
        database="test_db",
        user="test_user",
        password="test_pass"
    )
    yield pool
    pool.close()

@pytest.fixture
def test_database_transaction(test_database_pool):
    """Provide isolated database transaction for each test."""
    with test_database_pool.get_connection() as conn:
        with conn.cursor() as cur:
            # Start transaction
            cur.execute("BEGIN")

            yield conn

            # Always rollback to maintain isolation
            cur.execute("ROLLBACK")
```

## CI/CD Integration

### Cloud Build Testing Pipeline

The CI/CD pipeline runs comprehensive tests before deployment:

#### Production Pipeline (`cloudbuild.yaml`)
```yaml
steps:
  # 1. Run Comprehensive Testing Suite
  - name: 'python:3.11-slim'
    id: 'run-tests'
    args: ['bash', '-c', '
      # Install dependencies and run tests
      pip install -r requirements.txt
      pip install pytest-cov pytest-xdist pytest-html

      # Run pytest with coverage (80% minimum)
      python -m pytest --cov=. --cov-fail-under=80 --cov-report=xml tests/

      # Fail build if tests fail
      if [ $? -ne 0 ]; then exit 1; fi
    ']

  # 2. Run Static Analysis
  - name: 'python:3.11-slim'
    id: 'static-analysis'
    args: ['bash', '-c', '
      # Install analysis tools
      pip install mypy flake8 black isort bandit

      # Run all checks
      python -m black --check src/ tests/
      python -m isort --check-only src/ tests/
      python -m mypy src/
      python -m flake8 src/ tests/
      python -m bandit -r src/
    ']

  # 3. Store Test Artifacts
  - name: 'gcr.io/cloud-builders/gsutil'
    args: ['cp', '-r', 'coverage-reports/', 'gs://$PROJECT_ID-build-artifacts/$COMMIT_SHA/']

  # 4. Build and Deploy (only if tests pass)
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/app:$COMMIT_SHA', '.']
    # ... deployment steps
```

#### Staging Pipeline (`cloudbuild-staging.yaml`)
- Same test suite but with relaxed coverage threshold (70%)
- Warnings don't block deployment
- Full deployment proceeds regardless of test results

### Quality Gates

**Production Deployment**:
- ✅ All tests must pass
- ✅ 80% minimum code coverage
- ✅ No static analysis errors
- ✅ Security scan clean
- ✅ Build fails if any gate fails

**Staging Deployment**:
- ⚠️ Tests run but failures don't block deployment
- ✅ 70% minimum code coverage recommended
- ⚠️ Static analysis warnings logged but allowed
- ✅ Security scan runs for visibility

## Running Tests

### Local Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m "not integration" # Exclude integration tests

# Run specific test file
pytest tests/test_exceptions.py

# Run single test
pytest tests/test_exceptions.py::TestExceptionHandling::test_validation_error

# Debug failing test
pytest -v -s tests/test_failing.py
```

### Static Analysis

```bash
# Type checking
mypy src/

# Code formatting check
black --check src/ tests/

# Import sorting check
isort --check-only src/ tests/

# Code quality
flake8 src/ tests/

# Security scanning
bandit -r src/
```

### CI/CD Testing

Tests run automatically on:
- **Push to `main`**: Full production pipeline
- **Push to `dev`**: Staging pipeline with relaxed requirements
- **Pull Requests**: Basic validation (can be configured)

## Test Writing Guidelines

### Test Structure

```python
import pytest
from src.module import ClassToTest, function_to_test

class TestClassToTest:
    """Test suite for ClassToTest."""

    def setup_method(self):
        """Set up test fixtures."""
        self.instance = ClassToTest()

    def teardown_method(self):
        """Clean up after tests."""
        pass

    def test_descriptive_test_name(self):
        """Test that specific behavior works correctly."""
        # Arrange
        input_data = "test input"
        expected = "expected output"

        # Act
        result = self.instance.method(input_data)

        # Assert
        assert result == expected

    @pytest.mark.parametrize("input_value,expected", [
        ("input1", "output1"),
        ("input2", "output2"),
        (None, ValueError),
    ])
    def test_parameterized_behavior(self, input_value, expected):
        """Test behavior with multiple input scenarios."""
        if expected == ValueError:
            with pytest.raises(ValueError):
                function_to_test(input_value)
        else:
            assert function_to_test(input_value) == expected
```

### Test Naming Conventions

- **Files**: `test_*.py`
- **Classes**: `Test*`
- **Methods**: `test_*`
- **Descriptive names**: `test_invalid_email_raises_validation_error`

### Assertions and Error Handling

```python
# Good: Specific assertions
assert result.status_code == 200
assert "error" not in result.json()
assert len(users) == expected_count

# Good: Test exceptions properly
with pytest.raises(ValueError, match="Invalid email"):
    validate_email("not-an-email")

# Good: Test async code
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### Mocking and Fixtures

```python
from unittest.mock import Mock, patch

def test_with_mocking():
    """Test using mocks for external dependencies."""
    # Create mock
    mock_service = Mock()
    mock_service.get_data.return_value = {"key": "value"}

    # Use in test
    with patch('src.module.external_service', mock_service):
        result = function_under_test()
        assert result["key"] == "value"

        # Verify interactions
        mock_service.get_data.assert_called_once()

@pytest.fixture
def authenticated_client():
    """Fixture providing authenticated test client."""
    client = TestClient(app)
    client.headers = {"Authorization": "Bearer test-token"}
    return client
```

## Coverage Requirements

### Coverage Targets

- **Production**: 80% minimum coverage
- **Staging**: 70% recommended minimum
- **New Code**: 90% coverage required

### Coverage Configuration

```ini
[coverage:run]
source = src
omit =
    */tests/*
    */venv/*
    */migrations/*
    setup.py

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class .*\bProtocol\):
    @(abc\.)?abstractmethod
```

### Improving Coverage

```python
# Exclude debug-only code
if settings.DEBUG:  # pragma: no cover
    logger.debug("Debug info")

# Test error conditions
def test_error_handling():
    with pytest.raises(ValueError):
        function_that_raises()

# Test edge cases
def test_empty_input():
    result = process_data([])
    assert result == []

# Use parametrize for comprehensive testing
@pytest.mark.parametrize("input_data,expected", [
    ([], []),
    ([1], [1]),
    ([1, 2, 3], [1, 2, 3]),
])
def test_process_data(input_data, expected):
    assert process_data(input_data) == expected
```

## Debugging Test Failures

### Common Issues

1. **Import Errors**: Check `PYTHONPATH` and virtual environment
2. **Database Connections**: Ensure test database is running
3. **Async Tests**: Use `@pytest.mark.asyncio` decorator
4. **Mock Issues**: Verify mock return values and side effects

### Debugging Tools

```bash
# Run tests with detailed output
pytest -v -s tests/test_failing.py

# Run specific test with debugging
pytest -k "test_name" --pdb

# Show coverage for specific file
pytest --cov=src.module --cov-report=html tests/

# Profile slow tests
pytest --durations=10 tests/
```

## Performance Testing

### Test Execution Time

```python
import time
import pytest

def test_operation_performance():
    """Test that operation completes within time limit."""
    start_time = time.time()

    result = perform_operation()

    duration = time.time() - start_time
    assert duration < 5.0  # Must complete within 5 seconds

    assert result is not None
```

### Load Testing

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test handling multiple concurrent operations."""
    # Create multiple concurrent tasks
    tasks = [async_operation(i) for i in range(10)]

    # Execute concurrently
    results = await asyncio.gather(*tasks)

    # Verify all succeeded
    assert all(result is not None for result in results)
```

## Security Testing

### Input Validation Testing

```python
def test_sql_injection_protection():
    """Test that SQL injection attempts are blocked."""
    malicious_input = "'; DROP TABLE users; --"

    with pytest.raises(ValidationError):
        process_user_input(malicious_input)

def test_xss_protection():
    """Test XSS attempts are sanitized."""
    xss_attempt = "<script>alert('xss')</script>"

    result = sanitize_html_input(xss_attempt)
    assert "<script>" not in result
    assert "alert" not in result
```

### Authentication Testing

```python
def test_unauthorized_access_blocked():
    """Test unauthorized requests are rejected."""
    client = TestClient(app)

    response = client.get("/protected-endpoint")
    assert response.status_code == 401

def test_invalid_token_rejected():
    """Test invalid tokens are rejected."""
    client = TestClient(app)
    client.headers = {"Authorization": "Bearer invalid-token"}

    response = client.get("/protected-endpoint")
    assert response.status_code == 401
```

## Best Practices

### Test Organization

1. **One Concept Per Test**: Each test should verify one specific behavior
2. **Descriptive Names**: Test names should explain what they're testing
3. **Independent Tests**: Tests should not depend on each other
4. **Fast Execution**: Keep tests fast to encourage frequent running

### Test Maintenance

1. **Regular Review**: Review and update tests as code changes
2. **Remove Flaky Tests**: Fix or remove tests that fail intermittently
3. **Update on Refactor**: Update tests when refactoring code
4. **Document Complex Tests**: Add comments for complex test scenarios

### CI/CD Integration

1. **Fail Fast**: Stop pipeline on first test failure in critical paths
2. **Parallel Execution**: Run tests in parallel for faster feedback
3. **Artifact Storage**: Store test results and coverage reports
4. **Notification**: Alert team on test failures

## Troubleshooting

### Common Issues

**Tests Pass Locally but Fail in CI/CD**:
- Check environment variables
- Verify database connections
- Check file paths and permissions
- Review Python version compatibility

**Slow Test Execution**:
- Use fixtures efficiently
- Mock external services
- Run tests in parallel
- Profile and optimize slow tests

**Flaky Tests**:
- Avoid time-dependent tests
- Use proper cleanup in fixtures
- Mock external dependencies
- Add retry logic for network operations

**Coverage Issues**:
- Review coverage configuration
- Add tests for uncovered code
- Use `# pragma: no cover` for unreachable code
- Check for missing `__init__.py` files

### Getting Help

1. **Check Existing Tests**: Look at similar tests for patterns
2. **Review Documentation**: Check this guide and related docs
3. **Debug Locally**: Run tests with detailed output
4. **Ask for Review**: Get feedback on test implementation

---

**Last Updated**: November 5, 2025
**Coverage Target**: 80% (Production), 70% (Staging)
**Test Categories**: Unit, Integration, Functional, Regression, Migration, Connection Pool Stress, Connection Pool Config, Connection Lifecycle, Transaction Commit/Rollback, Transaction Isolation, Transaction Timeout/Deadlock, Concurrent Transactions, Search Index, Search Query, Search Performance, Search Relevance, Data Integrity
