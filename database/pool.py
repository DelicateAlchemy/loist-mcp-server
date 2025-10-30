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
        
        # TEMPORARY DEBUG: Force local PostgreSQL connection
        logger.info("DEBUG: Forcing local PostgreSQL connection")
        return "postgresql://loist_user:dev_password@postgres:5432/loist_mvp"
        
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
        Get a connection from the pool with automatic cleanup.
        
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
                    if not retry:
                        raise OperationalError("Connection validation failed")
                    continue
                
                # Connection is valid
                break
                
            except Exception as e:
                attempts += 1
                logger.warning(f"Connection attempt {attempts} failed: {e}")
                
                if attempts >= max_retries:
                    self._stats["connections_failed"] += 1
                    raise
                
                if not retry:
                    raise
                
                # Brief backoff
                time.sleep(0.1 * attempts)
        
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
        
        Args:
            conn: Database connection to validate
        
        Returns:
            True if connection is valid, False otherwise
        """
        if conn is None or conn.closed:
            return False
        
        try:
            # Test the connection with a simple query
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                return result[0] == 1
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
    logger.info(f"DEBUG get_connection: Using database URL: {pool.database_url}")
    with pool.get_connection(retry=retry, max_retries=max_retries) as conn:
        yield conn


def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Global connection pool closed")

