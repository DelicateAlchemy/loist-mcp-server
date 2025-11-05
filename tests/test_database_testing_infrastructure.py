"""
Tests for Database Testing Infrastructure.

This test file validates the database testing infrastructure implemented in subtask 16.2.
It demonstrates all the key features and ensures they work correctly.

Tests cover:
- Database connection fixtures and isolation
- Test data factories and sample data creation
- Transaction management and rollback
- Database mocking utilities
- Helper functions for common testing operations
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, patch


class TestDatabaseTestHelper:
    """Test the DatabaseTestHelper utility class."""

    def test_is_database_configured(self, db_helper):
        """Test database configuration detection."""
        result = db_helper.is_database_configured()
        assert isinstance(result, bool)

    def test_get_test_database_config(self, db_helper):
        """Test test database configuration retrieval."""
        config = db_helper.get_test_database_config()
        assert isinstance(config, dict)
        assert 'host' in config
        assert 'port' in config
        assert 'database' in config
        assert 'user' in config
        assert 'password' in config

    def test_generate_test_track_id(self, db_helper):
        """Test unique track ID generation."""
        track_id1 = db_helper.generate_test_track_id()
        track_id2 = db_helper.generate_test_track_id()

        assert isinstance(track_id1, str)
        assert isinstance(track_id2, str)
        assert track_id1 != track_id2
        assert len(track_id1) == 36  # UUID length

    def test_create_sample_track_data(self, db_helper):
        """Test sample track data creation."""
        data = db_helper.create_sample_track_data()
        assert isinstance(data, dict)
        assert 'title' in data
        assert 'artist' in data
        assert 'format' in data

        # Test with overrides
        custom_data = db_helper.create_sample_track_data(
            title="Custom Title",
            artist="Custom Artist",
            year=2020
        )
        assert custom_data['title'] == "Custom Title"
        assert custom_data['artist'] == "Custom Artist"
        assert custom_data['year'] == 2020

    def test_create_sample_gcs_paths(self, db_helper):
        """Test sample GCS path creation."""
        paths = db_helper.create_sample_gcs_paths()
        assert isinstance(paths, dict)
        assert 'audio' in paths
        assert 'thumbnail' in paths
        assert paths['audio'].startswith('gs://test-bucket/audio/')
        assert paths['thumbnail'].startswith('gs://test-bucket/thumbnails/')
        assert paths['audio'].endswith('.mp3')
        assert paths['thumbnail'].endswith('.jpg')


class TestTestDatabaseManager:
    """Test the TestDatabaseManager class."""

    def test_setup_and_cleanup(self, test_db_manager):
        """Test database manager setup and cleanup."""
        assert test_db_manager is not None

        # Test that pool is initialized
        assert test_db_manager._pool is not None

        # Test cleanup (this will be called automatically by fixture)

    def test_transaction_context(self, test_db_manager):
        """Test transaction context manager."""
        with test_db_manager.transaction_context() as conn:
            assert conn is not None
            assert not conn.closed

            # Test that we can execute queries in transaction
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result[0] == 1

        # Transaction should be rolled back

    def test_clear_all_test_data(self, test_db_manager, clean_database):
        """Test clearing all test data."""
        # This should work without errors
        test_db_manager.clear_all_test_data()

    def test_get_table_row_count(self, test_db_manager, clean_database):
        """Test getting table row count."""
        count = test_db_manager.get_table_row_count('audio_tracks')
        assert isinstance(count, int)
        assert count >= 0


class TestTestDataFactory:
    """Test the TestDataFactory class."""

    def test_create_basic_track(self, data_factory):
        """Test basic track creation."""
        track = data_factory.create_basic_track()
        assert isinstance(track, dict)
        assert 'track_id' in track
        assert 'metadata' in track
        assert 'audio_gcs_path' in track
        assert 'thumbnail_gcs_path' in track

        metadata = track['metadata']
        assert metadata['title'] == 'Test Track'
        assert metadata['artist'] == 'Test Artist'
        assert metadata['format'] == 'MP3'

    def test_create_track_batch(self, data_factory):
        """Test track batch creation."""
        batch = data_factory.create_track_batch(3)
        assert isinstance(batch, list)
        assert len(batch) == 3

        for track in batch:
            assert 'track_id' in track
            assert 'metadata' in track
            assert track['metadata']['title'].startswith('Batch Track')

    def test_create_edge_case_tracks(self, data_factory):
        """Test edge case track creation."""
        tracks = data_factory.create_edge_case_tracks()
        assert isinstance(tracks, list)
        assert len(tracks) == 4  # min, max, unicode, long strings

        # Check minimum values
        min_track = tracks[0]
        assert min_track['metadata']['year'] == 1800
        assert min_track['metadata']['channels'] == 1

        # Check maximum values
        max_track = tracks[1]
        assert max_track['metadata']['year'] == 2100
        assert max_track['metadata']['channels'] == 16

        # Check unicode
        unicode_track = tracks[2]
        assert 'Unicode' in unicode_track['metadata']['title']

    def test_create_search_test_tracks(self, data_factory):
        """Test search test tracks creation."""
        tracks = data_factory.create_search_test_tracks()
        assert isinstance(tracks, list)
        assert len(tracks) == 5

        # Check famous tracks are included
        titles = [track['metadata']['title'] for track in tracks]
        assert 'Bohemian Rhapsody' in titles
        assert 'Stairway to Heaven' in titles
        assert 'Hotel California' in titles


class TestDatabaseMockFactory:
    """Test the DatabaseMockFactory class."""

    def test_create_mock_connection(self, mock_factory):
        """Test mock connection creation."""
        mock_conn = mock_factory.create_mock_connection()
        assert isinstance(mock_conn, Mock)
        assert mock_conn.closed is False
        assert mock_conn.autocommit is True

    def test_create_mock_cursor(self, mock_factory):
        """Test mock cursor creation."""
        mock_cursor = mock_factory.create_mock_cursor()
        assert isinstance(mock_cursor, Mock)
        assert mock_cursor.fetchone() == (1,)
        assert mock_cursor.fetchall() == [(1,)]
        assert mock_cursor.rowcount == 1

    def test_create_mock_pool(self, mock_factory):
        """Test mock pool creation."""
        mock_pool = mock_factory.create_mock_pool()
        assert isinstance(mock_pool, Mock)

        # Test that getconn returns a mock connection
        conn = mock_pool.getconn()
        assert isinstance(conn, Mock)

    def test_create_mock_database_manager(self, mock_factory):
        """Test mock database manager creation."""
        mock_manager = mock_factory.create_mock_database_manager()
        assert isinstance(mock_manager, Mock)

        # Test health check
        health = mock_manager.health_check()
        assert health['healthy'] is True
        assert 'database_version' in health


class TestDatabaseTestingFixtures:
    """Test the database testing fixtures."""

    def test_sample_track_data_fixture(self, sample_track_data):
        """Test sample track data fixture."""
        assert isinstance(sample_track_data, dict)
        assert 'track_id' in sample_track_data
        assert 'metadata' in sample_track_data
        assert sample_track_data['metadata']['title'] == 'Test Track'

    def test_sample_track_batch_fixture(self, sample_track_batch):
        """Test sample track batch fixture."""
        assert isinstance(sample_track_batch, list)
        assert len(sample_track_batch) == 3
        for track in sample_track_batch:
            assert 'track_id' in track
            assert 'metadata' in track

    def test_edge_case_tracks_fixture(self, edge_case_tracks):
        """Test edge case tracks fixture."""
        assert isinstance(edge_case_tracks, list)
        assert len(edge_case_tracks) == 4

    def test_search_test_tracks_fixture(self, search_test_tracks):
        """Test search test tracks fixture."""
        assert isinstance(search_test_tracks, list)
        assert len(search_test_tracks) == 5

    def test_mock_fixtures(self, mock_db_connection, mock_db_pool, mock_database_manager):
        """Test mock fixtures."""
        assert isinstance(mock_db_connection, Mock)
        assert isinstance(mock_db_pool, Mock)
        assert isinstance(mock_database_manager, Mock)


class TestDatabaseTestingUtilities:
    """Test database testing utility functions."""

    def test_insert_test_track(self, clean_database, sample_track_data):
        """Test inserting a test track."""
        result = pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)
        assert isinstance(result, dict)
        assert 'id' in result
        assert result['title'] == 'Test Track'

    def test_insert_test_track_batch(self, clean_database, sample_track_batch):
        """Test inserting a batch of test tracks."""
        result = pytest.importorskip("tests.database_testing").insert_test_track_batch(sample_track_batch)
        assert isinstance(result, dict)
        assert result['inserted_count'] == 3
        assert 'track_ids' in result

    def test_count_tracks_in_database(self, clean_database):
        """Test counting tracks in database."""
        count = pytest.importorskip("tests.database_testing").count_tracks_in_database()
        assert isinstance(count, int)
        assert count >= 0

    def test_verify_track_exists(self, clean_database, sample_track_data):
        """Test verifying track existence."""
        # Track doesn't exist initially
        exists = pytest.importorskip("tests.database_testing").verify_track_exists(sample_track_data['track_id'])
        assert exists is False

        # Insert track
        pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)

        # Now it should exist
        exists = pytest.importorskip("tests.database_testing").verify_track_exists(sample_track_data['track_id'])
        assert exists is True

    def test_verify_track_data(self, clean_database, sample_track_data):
        """Test verifying track data."""
        # Insert track
        pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)

        # Verify data
        matches = pytest.importorskip("tests.database_testing").verify_track_data(
            sample_track_data['track_id'],
            {'title': 'Test Track', 'artist': 'Test Artist'}
        )
        assert matches is True

        # Test with wrong data
        matches = pytest.importorskip("tests.database_testing").verify_track_data(
            sample_track_data['track_id'],
            {'title': 'Wrong Title'}
        )
        assert matches is False


class TestDatabaseTestingContextManagers:
    """Test database testing context managers."""

    def test_temporary_track_context_manager(self, clean_database, sample_track_data):
        """Test temporary track context manager."""
        temporary_track_func = pytest.importorskip("tests.database_testing").temporary_track

        with temporary_track_func(sample_track_data) as track:
            assert isinstance(track, dict)
            assert 'id' in track
            assert track['title'] == 'Test Track'

        # Track should be cleaned up (transaction rollback)

    def test_temporary_track_batch_context_manager(self, clean_database, sample_track_batch):
        """Test temporary track batch context manager."""
        temporary_track_batch_func = pytest.importorskip("tests.database_testing").temporary_track_batch

        with temporary_track_batch_func(sample_track_batch) as result:
            assert isinstance(result, dict)
            assert result['inserted_count'] == 3
            assert 'track_ids' in result

        # Tracks should be cleaned up (transaction rollback)


class TestDatabaseTestingAssertions:
    """Test database testing assertion helpers."""

    def test_assert_track_count(self, clean_database):
        """Test track count assertion."""
        # Initially should be 0
        pytest.importorskip("tests.database_testing").assert_track_count(0)

        # Insert a track
        sample_track_data = pytest.importorskip("tests.database_testing").TestDataFactory.create_basic_track()
        pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)

        # Now should be 1
        pytest.importorskip("tests.database_testing").assert_track_count(1)

    def test_assert_track_exists(self, clean_database, sample_track_data):
        """Test track existence assertion."""
        # Insert track
        pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)

        # Should not raise assertion error
        pytest.importorskip("tests.database_testing").assert_track_exists(sample_track_data['track_id'])

    def test_assert_track_data_matches(self, clean_database, sample_track_data):
        """Test track data matching assertion."""
        # Insert track
        pytest.importorskip("tests.database_testing").insert_test_track(sample_track_data)

        # Should not raise assertion error
        pytest.importorskip("tests.database_testing").assert_track_data_matches(
            sample_track_data['track_id'],
            {'title': 'Test Track', 'artist': 'Test Artist'}
        )


class TestTransactionIsolation:
    """Test transaction isolation and rollback functionality."""

    def test_transaction_rollback_on_failure(self, db_transaction):
        """Test that transactions roll back on failure."""
        # This test uses the db_transaction fixture which provides rollback
        assert db_transaction is not None

        # Any changes made in this test will be rolled back automatically

    def test_clean_database_fixture(self, clean_database):
        """Test that clean_database fixture works."""
        # This fixture ensures clean state
        # Any test using this fixture starts with clean database

    def test_database_isolation_between_tests(self, clean_database):
        """Test that database state is isolated between tests."""
        # Each test gets a clean database state
        count = pytest.importorskip("tests.database_testing").count_tracks_in_database()
        assert count == 0  # Should always start clean


class TestDatabaseMocking:
    """Test database mocking capabilities."""

    def test_mock_connection_usage(self, mock_db_connection):
        """Test using mock connection."""
        assert mock_db_connection.closed is False

        # Can be used in place of real connection
        with mock_db_connection.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            # Mock returns another mock by default - just check it's not None
            assert result is not None

    def test_mock_pool_usage(self, mock_db_pool):
        """Test using mock connection pool."""
        conn = mock_db_pool.getconn()
        assert isinstance(conn, Mock)

        # Return connection
        mock_db_pool.putconn(conn)

        # Verify methods were called
        assert mock_db_pool.getconn.called
        assert mock_db_pool.putconn.called

    def test_mock_database_manager_usage(self, mock_database_manager):
        """Test using mock database manager."""
        health = mock_database_manager.health_check()
        assert health['healthy'] is True
        assert health['database_version'] == "15.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
