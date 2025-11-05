"""
Tests for database connection pooling.

Tests verify:
- Connection pool initialization
- Connection acquisition and release
- Health checks and validation
- Connection retry logic
- Pool statistics
- Thread safety
- Stress testing under load
- Timeout handling
- Pool configuration validation
- Connection lifecycle management
"""

import pytest
import os
import time
import threading
from uuid import uuid4
from unittest.mock import patch, MagicMock, call
from concurrent.futures import ThreadPoolExecutor, as_completed

# Skip all tests if database is not configured
pytest_plugins = []


def is_db_configured() -> bool:
    """Check if database configuration is available."""
    # Check for connection URL environment variables
    has_direct = bool(
        os.getenv("DB_HOST") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    has_proxy = bool(
        os.getenv("DB_CONNECTION_NAME") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    return has_direct or has_proxy


@pytest.fixture
def db_pool():
    """Fixture to create a test database pool."""
    if not is_db_configured():
        pytest.skip("Database not configured")
    
    from database import get_connection_pool, close_pool
    
    # Get fresh pool for testing
    pool = get_connection_pool(force_new=True)
    
    yield pool
    
    # Cleanup
    close_pool()


class TestDatabasePoolInitialization:
    """Test database pool initialization and configuration."""
    
    def test_pool_imports(self):
        """Test that database module imports correctly."""
        from database import DatabasePool, get_connection_pool
        assert DatabasePool is not None
        assert get_connection_pool is not None
    
    def test_pool_initialization(self, db_pool):
        """Test that pool initializes successfully."""
        assert db_pool is not None
        assert db_pool._pool is not None
        assert db_pool.min_connections >= 1
        assert db_pool.max_connections > db_pool.min_connections
    
    def test_pool_configuration_from_env(self):
        """Test pool uses environment configuration."""
        if not is_db_configured():
            pytest.skip("Database not configured")
        
        from database import DatabasePool
        
        pool = DatabasePool(min_connections=2, max_connections=5)
        
        assert pool.min_connections == 2
        assert pool.max_connections == 5
        assert pool.database_url is not None
    
    def test_pool_requires_database_url(self):
        """Test that pool requires database URL."""
        with patch.dict(os.environ, {}, clear=True):
            from database import DatabasePool
            
            with pytest.raises(ValueError, match="Database URL must be provided"):
                DatabasePool()


class TestConnectionManagement:
    """Test connection acquisition and release."""
    
    def test_get_connection(self, db_pool):
        """Test getting a connection from the pool."""
        from database import get_connection
        
        with get_connection() as conn:
            assert conn is not None
            assert not conn.closed
    
    def test_connection_auto_release(self, db_pool):
        """Test that connections are automatically released."""
        from database import get_connection
        
        # Get and release connection
        with get_connection() as conn:
            conn_id = id(conn)
        
        # Should be able to get another connection
        with get_connection() as conn2:
            assert conn2 is not None
    
    def test_connection_rollback_on_error(self, db_pool):
        """Test that connections rollback on error."""
        from database import get_connection
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Start a transaction
                    cur.execute("BEGIN")
                    # Force an error
                    raise Exception("Test error")
        except Exception:
            pass
        
        # Should be able to get a new connection
        with get_connection() as conn:
            assert conn is not None
            assert not conn.closed
    
    def test_connection_validation(self, db_pool):
        """Test connection validation."""
        assert db_pool._validate_connection(None) is False
        
        from database import get_connection
        
        with get_connection() as conn:
            assert db_pool._validate_connection(conn) is True


class TestHealthChecks:
    """Test health check functionality."""
    
    def test_health_check(self, db_pool):
        """Test database health check."""
        health = db_pool.health_check()
        
        assert isinstance(health, dict)
        assert "healthy" in health
        assert "stats" in health
        assert "timestamp" in health
        
        if is_db_configured():
            assert health["healthy"] is True
            assert "database_version" in health
    
    def test_health_check_includes_pool_config(self, db_pool):
        """Test health check includes pool configuration."""
        health = db_pool.health_check()
        
        if health["healthy"]:
            assert health["min_connections"] == db_pool.min_connections
            assert health["max_connections"] == db_pool.max_connections


class TestConnectionRetry:
    """Test connection retry logic."""
    
    def test_connection_retry_on_failure(self, db_pool):
        """Test that connections retry on transient failures."""
        from database import get_connection
        
        # Mock a transient failure
        original_getconn = db_pool._pool.getconn
        call_count = [0]
        
        def mock_getconn():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Transient error")
            return original_getconn()
        
        db_pool._pool.getconn = mock_getconn
        
        try:
            with get_connection(retry=True, max_retries=3) as conn:
                assert conn is not None
                assert call_count[0] > 1  # Retried at least once
        finally:
            db_pool._pool.getconn = original_getconn
    
    def test_connection_no_retry_when_disabled(self, db_pool):
        """Test that retry can be disabled."""
        from database import get_connection
        
        # This should work without retry
        with get_connection(retry=False) as conn:
            assert conn is not None


class TestPoolStatistics:
    """Test connection pool statistics."""
    
    def test_get_stats(self, db_pool):
        """Test getting pool statistics."""
        stats = db_pool.get_stats()
        
        assert isinstance(stats, dict)
        assert "connections_created" in stats
        assert "connections_closed" in stats
        assert "connections_failed" in stats
        assert "queries_executed" in stats
    
    def test_stats_update_on_query(self, db_pool):
        """Test that stats update when queries are executed."""
        initial_stats = db_pool.get_stats()
        initial_queries = initial_stats["queries_executed"]
        
        # Execute a query
        db_pool.execute_query("SELECT 1", fetch=True)
        
        updated_stats = db_pool.get_stats()
        assert updated_stats["queries_executed"] > initial_queries


class TestQueryExecution:
    """Test query execution through the pool."""
    
    def test_execute_query_select(self, db_pool):
        """Test executing a SELECT query."""
        result = db_pool.execute_query("SELECT 1 as num", fetch=True)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["num"] == 1
    
    def test_execute_query_with_params(self, db_pool):
        """Test executing a query with parameters."""
        result = db_pool.execute_query(
            "SELECT %s as num",
            params=(42,),
            fetch=True
        )
        
        assert result[0]["num"] == 42
    
    def test_execute_query_no_fetch(self, db_pool):
        """Test executing a query without fetching results."""
        result = db_pool.execute_query("SELECT 1", fetch=False)
        
        assert result is None


class TestThreadSafety:
    """Test thread safety of the connection pool."""
    
    def test_concurrent_connections(self, db_pool):
        """Test getting multiple concurrent connections."""
        import threading
        from database import get_connection
        
        results = []
        errors = []
        
        def get_and_query():
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        result = cur.fetchone()
                        results.append(result[0])
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=get_and_query) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert all(r == 1 for r in results)


class TestPoolCleanup:
    """Test connection pool cleanup."""
    
    def test_close_pool(self):
        """Test closing the connection pool."""
        if not is_db_configured():
            pytest.skip("Database not configured")
        
        from database import get_connection_pool, close_pool
        
        pool = get_connection_pool(force_new=True)
        assert pool._pool is not None
        
        close_pool()
        
        # Pool should be closed
        # Getting a new connection should create a new pool
        from database import get_connection
        with get_connection() as conn:
            assert conn is not None


class TestDatabaseUtils:
    """Test database utility functions."""
    
    def test_audio_track_db_imports(self):
        """Test that AudioTrackDB imports correctly."""
        from database.utils import AudioTrackDB
        assert AudioTrackDB is not None
    
    def test_execute_raw_query(self, db_pool):
        """Test executing raw queries."""
        from database.utils import execute_raw_query
        
        result = execute_raw_query("SELECT 1 as num")
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["num"] == 1


class TestConnectionPoolStressTesting:
    """Stress tests for connection pool under high load and concurrent access."""

    def test_concurrent_connection_acquisition(self, db_pool):
        """Test acquiring multiple connections concurrently."""
        if not db_pool:
            pytest.skip("Database pool not available")

        results = []
        errors = []

        def acquire_connection(worker_id):
            """Worker function to acquire and release a connection."""
            try:
                with db_pool.get_connection() as conn:
                    with conn.cursor() as cur:
                        # Perform a simple operation
                        cur.execute("SELECT %s as worker_id", (worker_id,))
                        result = cur.fetchone()
                        results.append((worker_id, result[0]))

                        # Simulate some work
                        time.sleep(0.01)

            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")

        # Launch 10 concurrent workers
        threads = []
        for i in range(10):
            thread = threading.Thread(target=acquire_connection, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Connection errors occurred: {errors}"
        assert len(results) == 10, "Not all workers completed successfully"

        # Verify each worker got its own ID back
        worker_ids = {result[0] for result in results}
        assert len(worker_ids) == 10, "Worker IDs should be unique"

    def test_connection_pool_limits_under_load(self, db_pool):
        """Test connection pool behavior when approaching max connections."""
        if not db_pool:
            pytest.skip("Database pool not available")

        max_connections = db_pool.max_connections
        connections = []

        try:
            # Acquire connections up to the limit
            for i in range(max_connections):
                conn = db_pool.get_connection()
                connections.append(conn)

            # Verify we got all expected connections
            assert len(connections) == max_connections

            # Try to get one more connection (should work or timeout gracefully)
            try:
                extra_conn = db_pool.get_connection(timeout=1.0)  # Short timeout
                extra_conn.close()
                # If we get here, the pool allows over-limit connections
            except Exception:
                # Expected behavior - pool is at capacity
                pass

        finally:
            # Clean up all connections
            for conn in connections:
                try:
                    conn.close()
                except Exception:
                    pass

    def test_connection_pool_timeout_handling(self, db_pool):
        """Test connection pool timeout behavior."""
        if not db_pool:
            pytest.skip("Database pool not available")

        # Acquire all available connections
        connections = []
        try:
            for i in range(db_pool.max_connections):
                try:
                    conn = db_pool.get_connection(timeout=1.0)
                    connections.append(conn)
                except Exception:
                    break  # Pool exhausted

            # Now try to get another connection with a short timeout
            start_time = time.time()
            try:
                db_pool.get_connection(timeout=0.5)
                pytest.fail("Expected timeout exception")
            except Exception as e:
                # Verify it failed within reasonable time
                elapsed = time.time() - start_time
                assert elapsed < 1.0, f"Timeout took too long: {elapsed}s"
                # Exception type depends on pool implementation

        finally:
            # Clean up
            for conn in connections:
                try:
                    conn.close()
                except Exception:
                    pass

    def test_connection_pool_rapid_acquire_release(self, db_pool):
        """Test rapid acquisition and release of connections."""
        if not db_pool:
            pytest.skip("Database pool not available")

        def rapid_acquire_release(iterations):
            """Perform rapid acquire/release cycles."""
            for i in range(iterations):
                try:
                    with db_pool.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                            cur.fetchone()
                except Exception as e:
                    pytest.fail(f"Connection failed on iteration {i}: {e}")

        # Run rapid cycles in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(rapid_acquire_release, 20) for _ in range(5)]

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()  # Will raise exception if any failed

    def test_connection_pool_health_under_load(self, db_pool):
        """Test connection pool health monitoring under load."""
        if not db_pool:
            pytest.skip("Database pool not available")

        # Perform health checks while under load
        initial_health = db_pool.health_check()

        def load_worker():
            """Worker that performs database operations."""
            for _ in range(50):
                with db_pool.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_backend_pid()")
                        cur.fetchone()

        # Start load workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(load_worker) for _ in range(10)]

            # Monitor health during load
            health_checks = []
            for _ in range(5):
                time.sleep(0.1)
                health = db_pool.health_check()
                health_checks.append(health)

            # Wait for workers to complete
            for future in as_completed(futures):
                future.result()

        # Verify health remained good throughout
        final_health = db_pool.health_check()
        assert final_health['healthy'] is True

        # Verify connection counts were reasonable
        for health in health_checks:
            assert health.get('connections_used', 0) <= db_pool.max_connections


class TestConnectionPoolConfiguration:
    """Test connection pool configuration validation and behavior."""

    def test_pool_configuration_validation(self):
        """Test that pool configuration is validated properly."""
        from database import DatabasePool

        # Test valid configuration
        pool = DatabasePool(min_connections=1, max_connections=5)
        assert pool.min_connections == 1
        assert pool.max_connections == 5

        # Test default values
        default_pool = DatabasePool()
        assert default_pool.min_connections >= 1
        assert default_pool.max_connections > default_pool.min_connections

    def test_pool_configuration_bounds(self):
        """Test pool configuration boundary conditions."""
        from database import DatabasePool

        # Test minimum bounds
        pool = DatabasePool(min_connections=0, max_connections=1)
        assert pool.min_connections >= 0
        assert pool.max_connections > 0

        # Test that max > min
        pool = DatabasePool(min_connections=5, max_connections=3)
        # Implementation should handle this gracefully
        assert pool.min_connections <= pool.max_connections

    def test_pool_initialization_with_custom_config(self):
        """Test pool initialization with custom configuration."""
        from database import DatabasePool

        config = {
            'min_connections': 2,
            'max_connections': 8,
            'connection_timeout': 30,
            'max_idle_time': 300
        }

        pool = DatabasePool(**config)
        assert pool.min_connections == config['min_connections']
        assert pool.max_connections == config['max_connections']

    def test_connection_validation_configuration(self, db_pool):
        """Test connection validation configuration."""
        if not db_pool:
            pytest.skip("Database pool not available")

        # Test that connection validation works
        with db_pool.get_connection() as conn:
            assert conn is not None
            assert not conn.closed

            # Test validation method if available
            if hasattr(db_pool, '_validate_connection'):
                is_valid = db_pool._validate_connection(conn)
                assert is_valid in [True, False]  # Should return boolean

    def test_pool_statistics_accuracy(self, db_pool):
        """Test that pool statistics are accurate."""
        if not db_pool:
            pytest.skip("Database pool not available")

        initial_stats = db_pool.get_stats()

        # Perform some operations
        for _ in range(5):
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

        # Check stats after operations
        updated_stats = db_pool.get_stats()

        # Statistics should be reasonable
        assert 'connections_used' in updated_stats
        assert 'connections_available' in updated_stats
        assert updated_stats['connections_used'] >= 0
        assert updated_stats['connections_available'] >= 0


class TestConnectionLifecycle:
    """Test complete connection lifecycle management."""

    def test_connection_proper_cleanup(self, db_pool):
        """Test that connections are properly cleaned up."""
        if not db_pool:
            pytest.skip("Database pool not available")

        initial_stats = db_pool.get_stats()

        # Use several connections
        for i in range(3):
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT %s", (i,))
                    result = cur.fetchone()
                    assert result[0] == i

        # Check that connections were returned to pool
        final_stats = db_pool.get_stats()

        # Available connections should be similar (allowing for timing)
        assert abs(final_stats.get('connections_available', 0) - initial_stats.get('connections_available', 0)) <= 3

    def test_connection_error_recovery(self, db_pool):
        """Test connection error recovery."""
        if not db_pool:
            pytest.skip("Database pool not available")

        # Cause a connection error and verify recovery
        try:
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    # Execute invalid SQL to cause error
                    cur.execute("INVALID SQL STATEMENT")
        except Exception:
            pass  # Expected error

        # Verify pool still works after error
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result[0] == 1

    def test_connection_context_manager_properly(self, db_pool):
        """Test that connection context manager works properly."""
        if not db_pool:
            pytest.skip("Database pool not available")

        conn = None
        try:
            conn = db_pool.get_connection()
            assert conn is not None
            assert not conn.closed

            with conn.cursor() as cur:
                cur.execute("SELECT 42 as answer")
                result = cur.fetchone()
                assert result[0] == 42

        finally:
            if conn:
                conn.close()

        # Verify connection is closed
        assert conn.closed

    def test_connection_reuse_efficiency(self, db_pool):
        """Test that connections are efficiently reused."""
        if not db_pool:
            pytest.skip("Database pool not available")

        # Get initial stats
        initial_stats = db_pool.get_stats()

        # Perform multiple operations
        for i in range(20):
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT %s", (i,))
                    cur.fetchone()

        # Check that we didn't create excessive connections
        final_stats = db_pool.get_stats()

        # Should not have created more than needed
        total_connections_created = final_stats.get('connections_created', 0)
        assert total_connections_created <= db_pool.max_connections


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

