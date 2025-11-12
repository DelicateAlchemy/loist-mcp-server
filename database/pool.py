"""
Database connection pooling for PostgreSQL.

Provides thread-safe connection pooling with automatic connection
management, health checks, and retry logic.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any
from psycopg2 import pool, extensions, OperationalError, DatabaseError
import psycopg2.extras

# Try to import config, fallback to environment
try:
    from src.config import config as app_config
    HAS_APP_CONFIG = True
except ImportError:
    HAS_APP_CONFIG = False
    import os

# Try to import circuit breaker for fault tolerance
try:
    from src.exceptions.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
    HAS_CIRCUIT_BREAKER = True
except ImportError:
    HAS_CIRCUIT_BREAKER = False

# Try to import retry utilities for enhanced error handling
try:
    from src.exceptions.retry import retry_call, DATABASE_RETRY_CONFIG, RetryExhaustedException
    HAS_RETRY = True
except ImportError:
    HAS_RETRY = False

logger = logging.getLogger(__name__)


class DatabasePool:
    """
    Thread-safe database connection pool manager.
    
    Uses psycopg2's ThreadedConnectionPool for efficient connection management.
    Provides context managers for safe connection handling and automatic cleanup.
    """
    
    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
        database_url: Optional[str] = None,
        **connection_kwargs
    ):
        """
        Initialize database connection pool.
        
        Args:
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            database_url: PostgreSQL connection URL (defaults to config)
            **connection_kwargs: Additional psycopg2 connection parameters
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._connection_kwargs = connection_kwargs
        
        # Get database URL from config or parameter
        if database_url:
            self.database_url = database_url
        elif HAS_APP_CONFIG and app_config.database_url:
            self.database_url = app_config.database_url
        else:
            # Fallback to environment variables
            self.database_url = self._build_url_from_env()
        
        if not self.database_url:
            raise ValueError(
                "Database URL must be provided via parameter, config, or environment variables"
            )
        
        # Connection statistics
        self._stats = {
            "connections_created": 0,
            "connections_closed": 0,
            "connections_failed": 0,
            "queries_executed": 0,
            "last_health_check": None,
        }
        
        logger.info(
            f"Initialized database pool: min={min_connections}, max={max_connections}"
        )
    
    def _build_url_from_env(self) -> Optional[str]:
        """Build database URL from environment variables."""
        import os
        
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_connection_name = os.getenv("DB_CONNECTION_NAME")
        
        if db_connection_name and db_connection_name.strip() and db_name and db_user and db_password:
            # Cloud SQL Proxy connection
            return f"postgresql://{db_user}:{db_password}@/{db_name}?host=/cloudsql/{db_connection_name}"
        elif db_host and db_name and db_user and db_password:
            # Direct connection
            return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        return None
    
    def initialize(self) -> None:
        """
        Initialize the connection pool.
        
        Creates the actual connection pool and tests initial connectivity.
        """
        if self._pool is not None:
            logger.warning("Pool already initialized")
            return
        
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                dsn=self.database_url,
                **self._connection_kwargs
            )
            
            self._stats["connections_created"] = self.min_connections
            
            # Test connectivity
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result[0] != 1:
                        raise DatabaseError("Health check failed")
            
            logger.info("Database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            self._stats["connections_failed"] += 1
            raise
    
    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is None:
            return
        
        try:
            self._pool.closeall()
            logger.info("Database connection pool closed")
            self._stats["connections_closed"] += self.min_connections
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            self._pool = None
    
    @contextmanager
    def get_connection(self, retry: bool = True, max_retries: int = 3):
        """
        Get a connection from the pool with automatic cleanup and circuit breaker protection.

        Args:
            retry: Whether to retry on connection failures
            max_retries: Maximum number of retry attempts

        Yields:
            Database connection

        Example:
            with pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM audio_tracks")
        """
        if self._pool is None:
            self.initialize()

        # Get circuit breaker for database operations
        db_circuit_breaker = None
        if HAS_CIRCUIT_BREAKER:
            db_circuit_breaker = get_circuit_breaker(
                "database",
                CircuitBreakerConfig(
                    name="database",
                    failure_threshold=3,  # Fail after 3 consecutive failures
                    recovery_timeout=30.0,  # Wait 30s before trying again
                    success_threshold=2,  # Need 2 successes to close
                    timeout=10.0  # 10s timeout for operations
                )
            )

        def _get_connection_with_retry():
            """Get connection with circuit breaker and retry logic."""
            def _single_connection_attempt():
                """Single connection attempt."""
                conn = self._pool.getconn()

                # Validate connection
                if not self._validate_connection(conn):
                    self._pool.putconn(conn, close=True)
                    raise OperationalError("Connection validation failed")

                return conn

            # Apply retry logic first, then circuit breaker
            if HAS_RETRY and retry:
                retry_config = DATABASE_RETRY_CONFIG
                retry_config.max_attempts = max_retries

                def _retryable_connection_attempt():
                    return retry_call(_single_connection_attempt, retry_config)

                if db_circuit_breaker:
                    return db_circuit_breaker.call(_retryable_connection_attempt)
                else:
                    return _retryable_connection_attempt()
            else:
                # Fallback to original logic
                if db_circuit_breaker:
                    return db_circuit_breaker.call(_single_connection_attempt)
                else:
                    return _single_connection_attempt()

        conn = None
        try:
            conn = _get_connection_with_retry()
        except Exception as e:
            self._stats["connections_failed"] += 1
            if HAS_RETRY and isinstance(e, RetryExhaustedException):
                logger.error(f"Database connection failed after {e.attempts} retry attempts. Last error: {e.last_exception}")
                raise e.last_exception from e
            raise

        try:
            yield conn
        except Exception as e:
            # Rollback on error
            if conn and not conn.closed:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            # Return connection to pool
            if conn and self._pool:
                try:
                    self._pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
    
    def _validate_connection(self, conn) -> bool:
        """
        Validate that a connection is still alive and usable.

        Simplified validation for reliability:
        - Basic connection state checks
        - Lightweight database query only when needed

        Args:
            conn: Database connection to validate

        Returns:
            True if connection is valid, False otherwise
        """
        if conn is None or conn.closed:
            logger.debug("Connection is None or closed")
            return False

        try:
            # Perform basic validation with database query
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()

                if result and result[0] == 1:
                    logger.debug("Connection validation successful")
                    return True
                else:
                    logger.warning("Connection validation query returned unexpected result")
                    return False

        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the connection pool.
        
        Returns:
            Dictionary with health status and statistics
        """
        status = {
            "healthy": False,
            "error": None,
            "stats": self._stats.copy(),
            "timestamp": time.time(),
        }
        
        try:
            with self.get_connection(retry=False) as conn:
                with conn.cursor() as cur:
                    # Test query
                    cur.execute("SELECT version()")
                    version = cur.fetchone()[0]
                    
                    # Check pool status
                    status["healthy"] = True
                    status["database_version"] = version
                    status["min_connections"] = self.min_connections
                    status["max_connections"] = self.max_connections
            
            self._stats["last_health_check"] = status["timestamp"]
            
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return status
    
    def execute_query(
        self,
        query: str,
        params: tuple = None,
        fetch: bool = True,
        commit: bool = False
    ):
        """
        Execute a query using a connection from the pool.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            fetch: Whether to fetch results
            commit: Whether to commit the transaction
        
        Returns:
            Query results if fetch=True, otherwise None
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                self._stats["queries_executed"] += 1
                
                result = None
                if fetch:
                    result = cur.fetchall()
                
                if commit:
                    conn.commit()
                
                return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return self._stats.copy()


# Global pool instance
_pool: Optional[DatabasePool] = None


def get_connection_pool(
    min_connections: int = None,
    max_connections: int = None,
    force_new: bool = False
) -> DatabasePool:
    """
    Get or create the global connection pool instance.
    
    Args:
        min_connections: Minimum connections (defaults to config)
        max_connections: Maximum connections (defaults to config)
        force_new: Force creation of new pool
    
    Returns:
        DatabasePool instance
    """
    global _pool
    
    if _pool is None or force_new:
        # Get defaults from config if available
        if HAS_APP_CONFIG:
            min_conn = min_connections or app_config.db_min_connections
            max_conn = max_connections or app_config.db_max_connections
        else:
            min_conn = min_connections or 2
            max_conn = max_connections or 10
        
        if _pool is not None:
            _pool.close()
        
        _pool = DatabasePool(
            min_connections=min_conn,
            max_connections=max_conn
        )
        _pool.initialize()
    
    return _pool


@contextmanager
def get_connection(retry: bool = True, max_retries: int = 3):
    """
    Convenience function to get a database connection.
    
    Args:
        retry: Whether to retry on connection failures
        max_retries: Maximum number of retry attempts
    
    Yields:
        Database connection
    
    Example:
        from database import get_connection
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM audio_tracks")
                tracks = cur.fetchall()
    """
    pool = get_connection_pool()
    with pool.get_connection(retry=retry, max_retries=max_retries) as conn:
        yield conn


def close_pool() -> None:
    """Close the global connection pool."""
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Global connection pool closed")


def check_database_availability() -> Dict[str, Any]:
    """
    Check database availability without throwing exceptions.

    Performs a quick connectivity test to determine if the database is available.
    Works for both Cloud SQL Proxy and direct connections.

    Returns:
        Dict with availability status and error details:
        {
            "available": bool,
            "error": str | None,
            "connection_type": "proxy" | "direct" | "unknown",
            "response_time_ms": float | None
        }
    """
    import time

    result = {
        "available": False,
        "error": None,
        "connection_type": "unknown",
        "response_time_ms": None
    }

    start_time = time.time()

    try:
        # Get pool (creates if needed)
        pool = get_connection_pool()

        # Determine connection type
        config = None
        if HAS_APP_CONFIG and hasattr(app_config, 'db_connection_name') and app_config.db_connection_name:
            result["connection_type"] = "proxy"
        else:
            result["connection_type"] = "direct"

        # Test connectivity with short timeout
        with pool.get_connection(retry=False, max_retries=1) as conn:
            with conn.cursor() as cur:
                # Simple query to test connectivity
                cur.execute("SELECT 1 as test")
                row = cur.fetchone()

                if row and row[0] == 1:
                    result["available"] = True
                    result["response_time_ms"] = (time.time() - start_time) * 1000
                    logger.debug(".1f")
                else:
                    result["error"] = "Unexpected query result"
                    logger.warning("Database availability check failed: unexpected query result")

    except Exception as e:
        result["error"] = str(e)
        result["response_time_ms"] = (time.time() - start_time) * 1000

        # Log different error types for debugging
        if "cloudsql" in str(e).lower():
            logger.debug("Cloud SQL Proxy not available: %s", e)
        elif "connection refused" in str(e).lower():
            logger.debug("Database connection refused: %s", e)
        elif "timeout" in str(e).lower():
            logger.debug("Database connection timeout: %s", e)
        else:
            logger.debug("Database availability check failed: %s", e)

    return result

