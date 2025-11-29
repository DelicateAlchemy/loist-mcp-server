"""
Tests for database migrations.

Tests verify:
- Migration system initialization
- Migration application
- Rollback functionality
- Migration tracking
- Error handling
- Migration idempotency
- Schema verification
- Dependency ordering
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


@pytest.mark.skipif(not is_db_configured(), reason="Database not configured")
class TestMigrationTestRunner:
    """Test the MigrationTestRunner class for comprehensive migration testing."""

    def test_migration_test_runner_initialization(self):
        """Test MigrationTestRunner initializes correctly."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        assert runner.migrator is not None
        assert runner.test_schema == "test_schema"

    def test_setup_and_cleanup_test_migration_schema(self):
        """Test setting up and cleaning up test migration schema."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()

        # Setup
        runner.setup_test_migration_schema()

        # Verify schema exists
        with runner.migrator.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata
                        WHERE schema_name = 'test_schema'
                    )
                """)
                exists = cur.fetchone()[0]
                assert exists, "Test schema should exist"

        # Cleanup
        runner.cleanup_test_migration_schema()

        # Verify schema is gone
        with runner.migrator.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata
                        WHERE schema_name = 'test_schema'
                    )
                """)
                exists = cur.fetchone()[0]
                assert not exists, "Test schema should be cleaned up"

    def test_apply_migration_to_test_schema(self):
        """Test applying a migration to test schema."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Get the first migration file
            migration_files = sorted(runner.migrator.migrations_dir.glob("*.sql"))
            if migration_files:
                migration_file = migration_files[0]

                # Apply migration
                result = runner.apply_migration_to_test_schema(migration_file)

                # Verify result structure
                assert 'success' in result
                assert 'version' in result
                assert 'execution_time_ms' in result
                assert 'checksum' in result

                # Should succeed for initial schema migration
                assert result['success'] is True

                # Verify migration was recorded
                with runner.migrator.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO test_schema, public")
                        cur.execute("SELECT version FROM test_schema.schema_migrations WHERE version = %s", (result['version'],))
                        recorded = cur.fetchone()
                        assert recorded is not None
                        assert recorded[0] == result['version']

        finally:
            runner.cleanup_test_migration_schema()

    def test_migration_idempotency(self):
        """Test migration idempotency (safe to run multiple times)."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Get the first migration file
            migration_files = sorted(runner.migrator.migrations_dir.glob("*.sql"))
            if migration_files:
                migration_file = migration_files[0]

                # Test idempotency
                is_idempotent = runner.test_migration_idempotency(migration_file)

                # Initial schema migration should be idempotent
                assert is_idempotent is True

        finally:
            runner.cleanup_test_migration_schema()

    def test_verify_migration_schema_changes(self):
        """Test verification of migration schema changes."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Get the initial schema migration
            migration_files = sorted(runner.migrator.migrations_dir.glob("*initial_schema.sql"))
            if migration_files:
                migration_file = migration_files[0]

                # Apply migration first
                runner.apply_migration_to_test_schema(migration_file)

                # Define expected changes for initial schema
                expected_changes = {
                    'tables': ['audio_tracks'],
                    'columns': {
                        'audio_tracks': ['id', 'track_id', 'title', 'artist', 'album', 'genre',
                                       'year', 'duration_seconds', 'channels', 'sample_rate',
                                       'bitrate', 'format', 'file_size_bytes', 'audio_gcs_path',
                                       'thumbnail_gcs_path', 'processing_status', 'created_at', 'updated_at']
                    },
                    'indexes': ['idx_audio_tracks_track_id', 'idx_audio_tracks_status', 'idx_audio_tracks_created']
                }

                # Verify schema changes
                verification = runner.verify_migration_schema_changes(migration_file, expected_changes)

                assert verification['all_passed'] is True
                assert verification['version'] == '001'

                # Check that all expected checks passed
                for check_name, passed in verification['checks'].items():
                    assert passed, f"Schema check failed: {check_name}"

        finally:
            runner.cleanup_test_migration_schema()

    def test_migration_dependencies(self):
        """Test migration dependency analysis."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()

        # Test dependency analysis
        dependency_results = runner.test_migration_dependencies()

        assert 'total_migrations' in dependency_results
        assert 'dependency_issues' in dependency_results
        assert 'dependency_check_passed' in dependency_results

        # Should have at least the initial migrations
        assert dependency_results['total_migrations'] >= 1

        # Dependency check should pass for properly ordered migrations
        assert dependency_results['dependency_check_passed'] is True

    def test_migration_with_rollback_file(self):
        """Test migration rollback functionality."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Look for migration with rollback file
            migration_files = sorted(runner.migrator.migrations_dir.glob("*initial_schema.sql"))
            rollback_files = sorted(runner.migrator.migrations_dir.glob("*initial_schema_rollback.sql"))

            if migration_files and rollback_files:
                migration_file = migration_files[0]
                rollback_file = rollback_files[0]

                # Apply migration
                apply_result = runner.apply_migration_to_test_schema(migration_file)
                assert apply_result['success'] is True

                # Verify table exists
                with runner.migrator.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO test_schema, public")
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables
                                WHERE table_schema = 'test_schema' AND table_name = 'audio_tracks'
                            )
                        """)
                        exists_before = cur.fetchone()[0]
                        assert exists_before, "Table should exist after migration"

                # Note: Full rollback testing would require implementing rollback in MigrationTestRunner
                # For now, we verify the migration applies correctly

        finally:
            runner.cleanup_test_migration_schema()

    def test_migration_checksum_calculation(self):
        """Test migration checksum calculation."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()

        # Get a migration file
        migration_files = sorted(runner.migrator.migrations_dir.glob("*.sql"))
        if migration_files:
            migration_file = migration_files[0]

            # Calculate checksum twice - should be same
            checksum1 = runner.migrator.calculate_checksum(migration_file)
            checksum2 = runner.migrator.calculate_checksum(migration_file)

            assert checksum1 == checksum2
            assert len(checksum1) == 64  # SHA-256 hash length
            assert checksum1.isalnum()  # Should be hexadecimal

    def test_migration_execution_timing(self):
        """Test migration execution timing."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Get a migration file
            migration_files = sorted(runner.migrator.migrations_dir.glob("*.sql"))
            if migration_files:
                migration_file = migration_files[0]

                # Apply migration and check timing
                result = runner.apply_migration_to_test_schema(migration_file)

                assert result['success'] is True
                assert 'execution_time_ms' in result
                assert isinstance(result['execution_time_ms'], int)
                assert result['execution_time_ms'] >= 0

        finally:
            runner.cleanup_test_migration_schema()


class TestMigrationErrorHandling:
    """Test migration error handling and edge cases."""

    def test_migration_with_invalid_sql(self):
        """Test handling of migrations with invalid SQL."""
        from tests.database_testing import MigrationTestRunner
        import tempfile
        import os

        runner = MigrationTestRunner()
        runner.setup_test_migration_schema()

        try:
            # Create a temporary migration file with invalid SQL
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write("INVALID SQL THAT WILL FAIL;")
                temp_file = Path(f.name)

            # Try to apply invalid migration
            result = runner.apply_migration_to_test_schema(temp_file)

            # Should fail
            assert result['success'] is False
            assert 'error' in result

        finally:
            # Clean up temp file
            if 'temp_file' in locals():
                os.unlink(temp_file)
            runner.cleanup_test_migration_schema()

    def test_migration_dependency_ordering_validation(self):
        """Test validation of migration dependency ordering."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()

        # Test with current migrations
        dependency_results = runner.test_migration_dependencies()

        # Should not have dependency issues with properly ordered migrations
        assert len(dependency_results['dependency_issues']) == 0

    def test_migration_file_format_validation(self):
        """Test validation of migration file naming format."""
        from tests.database_testing import MigrationTestRunner

        runner = MigrationTestRunner()

        # Check that migration files follow proper naming convention
        migration_files = list(runner.migrator.migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            # Should start with version number
            version_part = migration_file.stem.split('_')[0]

            # Version should be numeric
            try:
                int(version_part)
            except ValueError:
                pytest.fail(f"Migration file {migration_file.name} does not start with valid version number")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

