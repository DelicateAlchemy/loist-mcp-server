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
- Idempotent migrations (handles "already exists" gracefully)

Usage:
    # Apply all pending migrations (in lexicographic filename order)
    python database/migrate.py --action=apply --database-url=postgresql://user:pass@host:port/db
    python database/migrate.py --action=apply --dry-run   # preview the plan, apply nothing

    # "up" is a long-standing alias for "apply", kept for backward compatibility with
    # existing Cloud Build deploy pipelines (cloudbuild*.yaml call --action=up).
    python database/migrate.py --action=up --database-url=postgresql://user:pass@host:port/db

    python database/migrate.py --action=down --migration=001 --database-url=postgresql://user:pass@host:port/db
    python database/migrate.py --action=status --database-url=postgresql://user:pass@host:port/db

    # Mark existing (hand-migrated) databases as up to date without running the SQL
    python database/migrate.py --action=baseline --database-url=postgresql://user:pass@host:port/db
    python database/migrate.py --action=baseline --up-to=006_optimize_search_vector

See database/migrations/README.md for full documentation, including the LOI-51
old->new filename mapping for the historical duplicate "002_" prefixed migrations.

Author: Task Master AI
Created: $(date)
"""

import argparse
import hashlib
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import connection as PgConnection

# Try to import application config and pool
try:
    from src.config import config as app_config

    HAS_APP_CONFIG = True
except ImportError:
    HAS_APP_CONFIG = False

try:
    from database.pool import get_connection  # noqa: F401  (kept for API discoverability)

    HAS_POOL = True
except ImportError:
    HAS_POOL = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles database migrations with rollback support."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        # Get database URL from parameter, config, or environment
        resolved_url: Optional[str]
        if database_url:
            resolved_url = database_url
        elif HAS_APP_CONFIG and app_config.database_url:
            resolved_url = app_config.database_url
        else:
            resolved_url = os.getenv("DATABASE_URL")

        if not resolved_url:
            raise ValueError(
                "Database URL must be provided via parameter, config, or DATABASE_URL env var"
            )

        self.database_url: str = resolved_url
        self.migrations_dir = Path(__file__).parent / "migrations"
        self.use_pool = False  # Use direct connection for migrations by default

    def get_connection(self) -> PgConnection:
        """Get database connection with proper error handling."""
        try:
            conn = psycopg2.connect(self.database_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def ensure_migrations_table(self, conn: PgConnection) -> None:
        """Create migrations tracking table if it doesn't exist."""
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    checksum VARCHAR(64),
                    execution_time_ms INTEGER
                );
                """
            )
            logger.info("Migrations table ensured")

    def get_applied_migrations(self, conn: PgConnection) -> List[str]:
        """Get list of applied migration versions."""
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row[0] for row in cur.fetchall()]

    def get_pending_migrations(self, conn: PgConnection) -> List[Tuple[str, Path]]:
        """Get list of pending migration files, in lexicographic filename order."""
        applied = set(self.get_applied_migrations(conn))
        pending = []

        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            version = migration_file.stem
            if version not in applied:
                pending.append((version, migration_file))

        return pending

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of migration file."""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    # Error messages that indicate the migration was already applied
    IDEMPOTENT_ERRORS = [
        "already exists",
        "duplicate key value violates unique constraint",
        "column .* of relation .* already exists",
        "relation .* already exists",
        "index .* already exists",
        "constraint .* already exists",
        "type .* already exists",
    ]

    def is_idempotent_error(self, error_message: str) -> bool:
        """Check if the error indicates the migration was already applied."""
        error_lower = str(error_message).lower()
        for pattern in self.IDEMPOTENT_ERRORS:
            if re.search(pattern, error_lower):
                return True
        return False

    def apply_migration(
        self,
        conn: PgConnection,
        version: str,
        file_path: Path,
        force_idempotent: bool = True,
    ) -> bool:
        """Apply a single migration file.

        Args:
            conn: Database connection
            version: Migration version string
            file_path: Path to migration SQL file
            force_idempotent: If True, treat "already exists" errors as success
        """
        logger.info(f"Applying migration {version}")

        start_time = datetime.now()

        try:
            # Read migration file
            with open(file_path, "r") as f:
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

                    cur.execute(
                        """
                        INSERT INTO schema_migrations (version, checksum, execution_time_ms)
                        VALUES (%s, %s, %s)
                        """,
                        (version, checksum, execution_time),
                    )

                    # Commit transaction
                    cur.execute("COMMIT;")

                    logger.info(f"Migration {version} applied successfully in {execution_time}ms")
                    return True

                except Exception as e:
                    # Rollback on error
                    cur.execute("ROLLBACK;")

                    # Check if this is an idempotent error (already applied)
                    if force_idempotent and self.is_idempotent_error(str(e)):
                        logger.warning(
                            f"Migration {version} appears already applied (idempotent): {e}"
                        )
                        # Mark as applied anyway
                        return self.mark_migration_applied(conn, version, checksum)

                    logger.error(f"Migration {version} failed: {e}")
                    raise

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False

    def mark_migration_applied(
        self, conn: PgConnection, version: str, checksum: Optional[str] = None
    ) -> bool:
        """Mark a migration as applied without running it."""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO schema_migrations (version, checksum, execution_time_ms)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version, checksum, 0),
                )
            logger.info(f"Migration {version} marked as applied")
            return True
        except Exception as e:
            logger.error(f"Failed to mark migration {version} as applied: {e}")
            return False

    def rollback_migration(self, conn: PgConnection, version: str) -> bool:
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

    def migrate_up(self, dry_run: bool = False) -> bool:
        """Apply all pending migrations, in lexicographic filename order.

        Args:
            dry_run: If True, only print the plan of pending migrations; apply nothing.
        """
        logger.info("Starting migration up" + (" (dry run)" if dry_run else ""))

        conn = self.get_connection()
        try:
            self.ensure_migrations_table(conn)
            pending = self.get_pending_migrations(conn)

            if not pending:
                logger.info("No pending migrations")
                return True

            logger.info(f"Found {len(pending)} pending migrations")

            if dry_run:
                print("\n=== Migration Plan (dry run, nothing applied) ===")
                for version, _ in pending:
                    print(f"  ⏳ {version}")
                return True

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

    def baseline(self, up_to_version: Optional[str] = None) -> bool:
        """Mark all migrations (or up to a specific version) as applied without running them.

        This is useful for existing databases where the schema was created manually
        or before migration tracking was enabled.

        Args:
            up_to_version: Optional. If provided, only baseline up to this version.
                          If None, baseline all migrations.
        """
        logger.info(
            f"Creating migration baseline{f' up to {up_to_version}' if up_to_version else ''}"
        )

        conn = self.get_connection()
        try:
            self.ensure_migrations_table(conn)

            # Get all migration files
            all_migrations = sorted(self.migrations_dir.glob("*.sql"))
            applied = set(self.get_applied_migrations(conn))

            baselined = 0
            for migration_file in all_migrations:
                version = migration_file.stem

                # Skip if already applied
                if version in applied:
                    logger.info(f"Migration {version} already tracked, skipping")
                    continue

                # Stop if we've reached the target version
                if up_to_version and version > up_to_version:
                    logger.info(f"Reached target version {up_to_version}, stopping baseline")
                    break

                # Calculate checksum and mark as applied
                checksum = self.calculate_checksum(migration_file)
                if self.mark_migration_applied(conn, version, checksum):
                    baselined += 1
                else:
                    logger.error(f"Failed to baseline migration {version}")
                    return False

            if baselined > 0:
                logger.info(f"✅ Baselined {baselined} migrations")
            else:
                logger.info("No migrations needed to be baselined")

            return True

        finally:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Database Migration Runner")
    parser.add_argument(
        "--action",
        choices=["apply", "up", "down", "status", "baseline"],
        required=True,
        help=(
            "Migration action to perform: apply/up (apply pending migrations - 'up' is a "
            "backward-compatible alias), down (rollback), status (show), "
            "baseline (mark as applied without running)"
        ),
    )
    parser.add_argument(
        "--database-url", help="PostgreSQL connection URL (or set DATABASE_URL env var)"
    )
    parser.add_argument(
        "--migration", help="Migration version for rollback (required for down action)"
    )
    parser.add_argument(
        "--up-to", help="For baseline action: only baseline up to this migration version"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For apply/up action: print the plan of pending migrations without applying them",
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
        success: bool
        if args.action in ("apply", "up"):
            success = migrator.migrate_up(dry_run=args.dry_run)
        elif args.action == "down":
            success = migrator.migrate_down(args.migration)
        elif args.action == "status":
            migrator.get_status()
            success = True
        elif args.action == "baseline":
            success = migrator.baseline(args.up_to)
        else:  # pragma: no cover - argparse choices already restrict this
            raise ValueError(f"Unknown action: {args.action}")

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
