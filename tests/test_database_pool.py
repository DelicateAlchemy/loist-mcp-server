"""
Tests for database connection pooling.

Tests verify:
- Connection pool initialization
- Connection acquisition and release
- Health checks and validation
- Connection retry logic
- Pool statistics
- Thread safety
"""

import pytest
import os
from uuid import uuid4
from unittest.mock import patch, MagicMock

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


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

