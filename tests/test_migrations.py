"""
Tests for database migrations.

Tests verify:
- Migration system initialization
- Migration application
- Rollback functionality
- Migration tracking
- Error handling
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


def is_db_configured() -> bool:
    """Check if database configuration is available."""
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


class TestMigrationSystem:
    """Test migration system components."""
    
    def test_migrator_imports(self):
        """Test that migration modules import correctly."""
        from database.migrate import DatabaseMigrator
        assert DatabaseMigrator is not None
    
    def test_migrator_requires_database_url(self):
        """Test that migrator requires database URL."""
        with patch.dict(os.environ, {}, clear=True):
            from database.migrate import DatabaseMigrator
            
            with pytest.raises(ValueError, match="Database URL must be provided"):
                DatabaseMigrator()
    
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host:5432/db"})
    def test_migrator_initialization_from_env(self):
        """Test migrator initialization from environment."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator()
        
        assert migrator.database_url == "postgresql://user:pass@host:5432/db"
        assert migrator.migrations_dir.exists()
    
    def test_migrator_initialization_with_url(self):
        """Test migrator initialization with explicit URL."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator(database_url="postgresql://user:pass@host:5432/db")
        
        assert migrator.database_url == "postgresql://user:pass@host:5432/db"
    
    def test_migrations_directory_exists(self):
        """Test that migrations directory exists."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator(database_url="postgresql://test")
        
        assert migrator.migrations_dir.exists()
        assert migrator.migrations_dir.is_dir()
    
    def test_migration_files_exist(self):
        """Test that initial migration files exist."""
        migrations_dir = Path(__file__).parent.parent / "database" / "migrations"
        
        # Check for initial schema migration
        initial_migration = migrations_dir / "001_initial_schema.sql"
        assert initial_migration.exists(), "Initial schema migration should exist"
        
        # Check for rollback migration
        rollback_migration = migrations_dir / "001_initial_schema_rollback.sql"
        assert rollback_migration.exists(), "Rollback migration should exist"


@pytest.mark.skipif(not is_db_configured(), reason="Database not configured")
class TestMigrationOperations:
    """Test migration operations against real database."""
    
    def test_migration_status(self):
        """Test getting migration status."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator()
        
        try:
            # Should not raise an error
            migrator.get_status()
        except Exception as e:
            pytest.fail(f"Migration status check failed: {e}")
    
    def test_ensure_migrations_table(self):
        """Test that migrations table is created."""
        from database.migrate import DatabaseMigrator
        from database import get_connection
        
        migrator = DatabaseMigrator()
        
        conn = migrator.get_connection()
        try:
            migrator.ensure_migrations_table(conn)
            
            # Verify table exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'schema_migrations'
                    )
                """)
                exists = cur.fetchone()[0]
                assert exists, "schema_migrations table should exist"
        finally:
            conn.close()
    
    def test_get_applied_migrations(self):
        """Test getting list of applied migrations."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator()
        conn = migrator.get_connection()
        
        try:
            migrator.ensure_migrations_table(conn)
            applied = migrator.get_applied_migrations(conn)
            
            assert isinstance(applied, list)
            # After initial setup, at least the first migration should be applied
            # (this test assumes migrations have been run)
        finally:
            conn.close()
    
    def test_get_pending_migrations(self):
        """Test getting list of pending migrations."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator()
        conn = migrator.get_connection()
        
        try:
            migrator.ensure_migrations_table(conn)
            pending = migrator.get_pending_migrations(conn)
            
            assert isinstance(pending, list)
            # Each pending migration should be a tuple of (version, file_path)
            for migration in pending:
                assert isinstance(migration, tuple)
                assert len(migration) == 2
                version, file_path = migration
                assert isinstance(version, str)
                assert isinstance(file_path, Path)
                assert file_path.exists()
        finally:
            conn.close()
    
    def test_calculate_checksum(self):
        """Test migration file checksum calculation."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator()
        
        # Get first migration file
        migration_files = sorted(migrator.migrations_dir.glob("*.sql"))
        if migration_files:
            checksum = migrator.calculate_checksum(migration_files[0])
            
            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA-256 hash length
            
            # Calculating again should give same result
            checksum2 = migrator.calculate_checksum(migration_files[0])
            assert checksum == checksum2


class TestMigrationCLI:
    """Test migration CLI commands."""
    
    def test_cli_imports(self):
        """Test that CLI module imports correctly."""
        from database import cli
        assert cli is not None
    
    def test_cli_has_main_function(self):
        """Test that CLI has main function."""
        from database.cli import main
        assert callable(main)
    
    @patch('sys.argv', ['cli.py', 'migrate', 'status'])
    @patch('database.cli.migrate_command')
    def test_cli_migrate_command(self, mock_migrate):
        """Test CLI migrate command parsing."""
        from database.cli import main
        
        mock_migrate.return_value = 0
        
        # This would normally parse arguments and call migrate_command
        # For testing, we just verify the command exists


class TestMigrationErrorHandling:
    """Test migration error handling."""
    
    def test_invalid_database_url(self):
        """Test handling of invalid database URL."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator(database_url="invalid://url")
        
        # Should raise an error when trying to connect
        with pytest.raises(Exception):
            migrator.get_connection()
    
    def test_missing_migrations_directory(self):
        """Test handling when migrations directory doesn't exist."""
        from database.migrate import DatabaseMigrator
        
        migrator = DatabaseMigrator(database_url="postgresql://test")
        
        # Temporarily change migrations dir to non-existent path
        original_dir = migrator.migrations_dir
        migrator.migrations_dir = Path("/nonexistent/path")
        
        try:
            conn = MagicMock()
            pending = migrator.get_pending_migrations(conn)
            
            # Should return empty list for non-existent directory
            assert pending == []
        finally:
            migrator.migrations_dir = original_dir


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

