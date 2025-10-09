"""
Database Configuration for Loist MVP

This module provides database connection configuration and utilities
for the PostgreSQL database used by the Loist audio metadata service.

Features:
- Connection pooling for production use
- Environment-based configuration
- Connection health checks
- Query optimization settings
- Error handling and logging

Author: Task Master AI
Created: $(date)
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import psycopg2
from psycopg2 import pool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    
    # Connection settings
    host: str = "localhost"
    port: int = 5432
    database: str = "loist_mvp"
    username: str = "loist_user"
    password: str = ""
    
    # Connection pool settings
    min_connections: int = 5
    max_connections: int = 20
    
    # Query settings
    statement_timeout: int = 30000  # 30 seconds in milliseconds
    idle_in_transaction_session_timeout: int = 60000  # 60 seconds
    
    # Performance settings
    work_mem: str = "256MB"
    shared_buffers: str = "256MB"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "loist_mvp"),
            username=os.getenv("DB_USER", "loist_user"),
            password=os.getenv("DB_PASSWORD", ""),
            min_connections=int(os.getenv("DB_MIN_CONNECTIONS", "5")),
            max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "20")),
            statement_timeout=int(os.getenv("DB_STATEMENT_TIMEOUT", "30000")),
            idle_in_transaction_session_timeout=int(os.getenv("DB_IDLE_TIMEOUT", "60000")),
            work_mem=os.getenv("DB_WORK_MEM", "256MB"),
            shared_buffers=os.getenv("DB_SHARED_BUFFERS", "256MB"),
        )
    
    @property
    def connection_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def dsn(self) -> str:
        """Get PostgreSQL DSN string."""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.username} password={self.password}"

class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
    
    def initialize_pool(self) -> None:
        """Initialize connection pool."""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                dsn=self.config.dsn,
                options=f"-c statement_timeout={self.config.statement_timeout} "
                       f"-c idle_in_transaction_session_timeout={self.config.idle_in_transaction_session_timeout}"
            )
            logger.info(f"Database connection pool initialized: {self.config.min_connections}-{self.config.max_connections} connections")
        except psycopg2.Error as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    def get_connection(self):
        """Get connection from pool."""
        if not self._pool:
            self.initialize_pool()
        
        try:
            return self._pool.getconn()
        except psycopg2.Error as e:
            logger.error(f"Failed to get connection from pool: {e}")
            raise
    
    def return_connection(self, conn) -> None:
        """Return connection to pool."""
        if self._pool:
            self._pool.putconn(conn)
    
    def close_pool(self) -> None:
        """Close connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Database connection pool closed")
    
    def health_check(self) -> bool:
        """Check database connectivity and health."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Simple query to test connectivity
                cur.execute("SELECT 1")
                result = cur.fetchone()
                
                # Check if search extensions are available
                cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pg_trgm')")
                extensions = [row[0] for row in cur.fetchall()]
                
                if 'uuid-ossp' not in extensions:
                    logger.warning("uuid-ossp extension not found")
                    return False
                
                if 'pg_trgm' not in extensions:
                    logger.warning("pg_trgm extension not found")
                    return False
                
                logger.info("Database health check passed")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database health check failed: {e}")
            return False
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query and return results."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                # Handle different query types
                if query.strip().upper().startswith('SELECT'):
                    return cur.fetchall()
                elif query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()
                    return cur.rowcount
                else:
                    conn.commit()
                    return None
                    
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def get_table_stats(self) -> Dict[str, Any]:
        """Get database table statistics."""
        query = """
            SELECT 
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE tablename = 'audio_tracks'
        """
        
        try:
            results = self.execute_query(query)
            if results:
                return {
                    'table_stats': results[0],
                    'timestamp': 'now()'
                }
            return {}
        except psycopg2.Error as e:
            logger.error(f"Failed to get table stats: {e}")
            return {}
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get database index statistics."""
        query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_tup_read,
                idx_tup_fetch,
                idx_scan,
                idx_tup_read / GREATEST(idx_scan, 1) as avg_tuples_per_scan
            FROM pg_stat_user_indexes
            WHERE tablename = 'audio_tracks'
            ORDER BY idx_tup_read DESC
        """
        
        try:
            results = self.execute_query(query)
            return {
                'index_stats': results,
                'timestamp': 'now()'
            }
        except psycopg2.Error as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}

# Global database manager instance
_db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        config = DatabaseConfig.from_env()
        _db_manager = DatabaseManager(config)
    return _db_manager

def initialize_database() -> DatabaseManager:
    """Initialize database connection pool."""
    db_manager = get_db_manager()
    db_manager.initialize_pool()
    return db_manager

def close_database() -> None:
    """Close database connection pool."""
    global _db_manager
    if _db_manager:
        _db_manager.close_pool()
        _db_manager = None
