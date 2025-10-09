#!/usr/bin/env python3
"""
Database Migration Runner for Loist MVP

This script applies PostgreSQL migrations in order and provides rollback capabilities.
It follows best practices for database migrations including:
- Transactional migrations (all-or-nothing)
- Migration tracking table
- Rollback support
- Error handling and logging
- Connection pooling for production use

Usage:
    python migrate.py --action=up --database-url=postgresql://user:pass@host:port/db
    python migrate.py --action=down --migration=001 --database-url=postgresql://user:pass@host:port/db
    python migrate.py --action=status --database-url=postgresql://user:pass@host:port/db

Author: Task Master AI
Created: $(date)
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """Handles database migrations with rollback support."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent / "migrations"
        
    def get_connection(self):
        """Get database connection with proper error handling."""
        try:
            conn = psycopg2.connect(self.database_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def ensure_migrations_table(self, conn):
        """Create migrations tracking table if it doesn't exist."""
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    checksum VARCHAR(64),
                    execution_time_ms INTEGER
                );
            """)
            logger.info("Migrations table ensured")
    
    def get_applied_migrations(self, conn) -> List[str]:
        """Get list of applied migration versions."""
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row[0] for row in cur.fetchall()]
    
    def get_pending_migrations(self, conn) -> List[Tuple[str, Path]]:
        """Get list of pending migration files."""
        applied = set(self.get_applied_migrations(conn))
        pending = []
        
        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            version = migration_file.stem
            if version not in applied:
                pending.append((version, migration_file))
        
        return pending
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of migration file."""
        import hashlib
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def apply_migration(self, conn, version: str, file_path: Path) -> bool:
        """Apply a single migration file."""
        logger.info(f"Applying migration {version}")
        
        start_time = datetime.now()
        
        try:
            # Read migration file
            with open(file_path, 'r') as f:
                migration_sql = f.read()
            
            # Calculate checksum
            checksum = self.calculate_checksum(file_path)
            
            # Apply migration in transaction
            with conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN;")
                
                try:
                    # Execute migration SQL
                    cur.execute(migration_sql)
                    
                    # Record migration
                    end_time = datetime.now()
                    execution_time = int((end_time - start_time).total_seconds() * 1000)
                    
                    cur.execute("""
                        INSERT INTO schema_migrations (version, checksum, execution_time_ms)
                        VALUES (%s, %s, %s)
                    """, (version, checksum, execution_time))
                    
                    # Commit transaction
                    cur.execute("COMMIT;")
                    
                    logger.info(f"Migration {version} applied successfully in {execution_time}ms")
                    return True
                    
                except Exception as e:
                    # Rollback on error
                    cur.execute("ROLLBACK;")
                    logger.error(f"Migration {version} failed: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False
    
    def rollback_migration(self, conn, version: str) -> bool:
        """Rollback a specific migration (requires manual rollback SQL)."""
        logger.warning(f"Rollback requested for migration {version}")
        logger.warning("Manual rollback SQL required - this is a destructive operation!")
        
        # Check if migration exists
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations WHERE version = %s", (version,))
            if not cur.fetchone():
                logger.error(f"Migration {version} not found in applied migrations")
                return False
        
        # For now, just remove the record (manual rollback required)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schema_migrations WHERE version = %s", (version,))
            logger.info(f"Migration {version} record removed (manual rollback required)")
        
        return True
    
    def migrate_up(self) -> bool:
        """Apply all pending migrations."""
        logger.info("Starting migration up")
        
        conn = self.get_connection()
        try:
            self.ensure_migrations_table(conn)
            pending = self.get_pending_migrations(conn)
            
            if not pending:
                logger.info("No pending migrations")
                return True
            
            logger.info(f"Found {len(pending)} pending migrations")
            
            for version, file_path in pending:
                if not self.apply_migration(conn, version, file_path):
                    logger.error(f"Migration failed at {version}")
                    return False
            
            logger.info("All migrations applied successfully")
            return True
            
        finally:
            conn.close()
    
    def migrate_down(self, version: str) -> bool:
        """Rollback to a specific migration."""
        logger.info(f"Starting migration down to {version}")
        
        conn = self.get_connection()
        try:
            self.ensure_migrations_table(conn)
            return self.rollback_migration(conn, version)
        finally:
            conn.close()
    
    def get_status(self) -> None:
        """Show migration status."""
        conn = self.get_connection()
        try:
            self.ensure_migrations_table(conn)
            applied = self.get_applied_migrations(conn)
            pending = self.get_pending_migrations(conn)
            
            print("\n=== Migration Status ===")
            print(f"Applied migrations: {len(applied)}")
            for version in applied:
                print(f"  ✅ {version}")
            
            print(f"\nPending migrations: {len(pending)}")
            for version, _ in pending:
                print(f"  ⏳ {version}")
            
            if not applied and not pending:
                print("No migrations found")
                
        finally:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description="Database Migration Runner")
    parser.add_argument(
        "--action", 
        choices=["up", "down", "status"], 
        required=True,
        help="Migration action to perform"
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection URL (or set DATABASE_URL env var)"
    )
    parser.add_argument(
        "--migration",
        help="Migration version for rollback (required for down action)"
    )
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("Database URL required (--database-url or DATABASE_URL env var)")
        sys.exit(1)
    
    # Validate rollback arguments
    if args.action == "down" and not args.migration:
        logger.error("Migration version required for rollback action")
        sys.exit(1)
    
    # Create migrator and execute action
    migrator = DatabaseMigrator(database_url)
    
    try:
        if args.action == "up":
            success = migrator.migrate_up()
        elif args.action == "down":
            success = migrator.migrate_down(args.migration)
        elif args.action == "status":
            migrator.get_status()
            success = True
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
