"""
Database Testing Infrastructure for Loist MCP Server.

This module provides comprehensive database testing capabilities including:
- Test database initialization and cleanup
- Transaction management for test isolation
- Test data fixtures and factories
- Database mocking utilities for unit tests
- Helper functions for common database testing operations

Author: Task Master AI
Created: 2025-11-05
"""

import os
import uuid
import logging
import pytest
from typing import Dict, Any, List, Optional, Generator, Callable
from contextlib import contextmanager
from unittest.mock import Mock, MagicMock

# Database imports
try:
    from database import get_connection_pool, close_pool, get_connection
    from database.operations import (
        save_audio_metadata,
        save_audio_metadata_batch,
        get_audio_metadata_by_id,
        get_all_audio_metadata,
        update_processing_status,
        search_audio_tracks
    )
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DatabaseTestHelper:
    """
    Helper class for database testing operations.

    Provides utilities for test database management, data fixtures,
    and common testing patterns.
    """

    @staticmethod
    def is_database_configured() -> bool:
        """Check if database configuration is available for testing."""
        return DATABASE_AVAILABLE and bool(
            os.getenv("DB_HOST") and
            os.getenv("DB_NAME") and
            os.getenv("DB_USER") and
            os.getenv("DB_PASSWORD")
        )

    @staticmethod
    def get_test_database_config() -> Dict[str, Any]:
        """Get test database configuration."""
        return {
            'host': os.getenv("DB_HOST", "localhost"),
            'port': int(os.getenv("DB_PORT", "5432")),
            'database': os.getenv("DB_NAME", "music_library_test"),
            'user': os.getenv("DB_USER", "loist_user"),
            'password': os.getenv("DB_PASSWORD", "dev_password")
        }

    @staticmethod
    def generate_test_track_id() -> str:
        """Generate a unique test track ID."""
        return str(uuid.uuid4())

    @staticmethod
    def create_sample_track_data(**overrides) -> Dict[str, Any]:
        """Create sample track metadata for testing."""
        base_data = {
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'genre': 'Rock',
            'year': 2023,
            'duration_seconds': 245.5,
            'channels': 2,
            'sample_rate': 44100,
            'bitrate': 320000,
            'format': 'MP3',
            'file_size_bytes': 10240000,
        }

        base_data.update(overrides)
        return base_data

    @staticmethod
    def create_sample_gcs_paths(track_id: Optional[str] = None) -> Dict[str, str]:
        """Create sample GCS paths for testing."""
        if track_id is None:
            track_id = DatabaseTestHelper.generate_test_track_id()

        return {
            'audio': f'gs://test-bucket/audio/{track_id}.mp3',
            'thumbnail': f'gs://test-bucket/thumbnails/{track_id}.jpg'
        }


class TestDatabaseManager:
    """
    Manages test database state and provides test isolation.

    Handles database setup, cleanup, and transaction management
    for comprehensive test isolation.
    """

    def __init__(self):
        self._pool = None
        self._original_pool = None

    def setup_test_database(self) -> None:
        """Set up test database with fresh state."""
        if not DatabaseTestHelper.is_database_configured():
            pytest.skip("Database not configured for testing")

        # Store original pool if exists
        try:
            from database import _pool as original_pool
            self._original_pool = original_pool
        except ImportError:
            pass

        # Create fresh pool for testing
        self._pool = get_connection_pool(force_new=True)

        # Create a dedicated test schema to isolate tests from production data
        self._create_test_schema()

        logger.info("Test database pool initialized")

    def _create_test_schema(self) -> None:
        """Create a dedicated test schema for database isolation."""
        if not self._pool:
            return

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Create test schema if it doesn't exist
                cur.execute("""
                    CREATE SCHEMA IF NOT EXISTS test_schema;
                    SET search_path TO test_schema, public;
                """)

                # Create test tables that mirror production but in test schema
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS test_schema.audio_tracks (
                        id SERIAL PRIMARY KEY,
                        track_id VARCHAR(36) UNIQUE NOT NULL,
                        title VARCHAR(500) NOT NULL,
                        artist VARCHAR(500),
                        album VARCHAR(500),
                        genre VARCHAR(100),
                        year INTEGER,
                        duration_seconds DECIMAL(10,3),
                        channels INTEGER,
                        sample_rate INTEGER,
                        bitrate INTEGER,
                        format VARCHAR(10),
                        file_size_bytes BIGINT,
                        audio_gcs_path TEXT NOT NULL,
                        thumbnail_gcs_path TEXT,
                        processing_status VARCHAR(20) DEFAULT 'PENDING',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    -- Create indexes for test schema
                    CREATE INDEX IF NOT EXISTS idx_test_tracks_track_id ON test_schema.audio_tracks(track_id);
                    CREATE INDEX IF NOT EXISTS idx_test_tracks_status ON test_schema.audio_tracks(processing_status);
                    CREATE INDEX IF NOT EXISTS idx_test_tracks_created ON test_schema.audio_tracks(created_at);
                """)

                # Create full-text search index for test schema
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_test_tracks_fts ON test_schema.audio_tracks
                    USING gin (to_tsvector('english',
                        coalesce(title, '') || ' ' ||
                        coalesce(artist, '') || ' ' ||
                        coalesce(album, '') || ' ' ||
                        coalesce(genre, '')
                    ));
                """)

            conn.commit()

    def cleanup_test_database(self) -> None:
        """Clean up test database and restore original state."""
        if self._pool:
            close_pool()

        # Restore original pool if it existed
        if self._original_pool:
            try:
                from database import _pool
                _pool = self._original_pool
            except ImportError:
                pass

        self._pool = None
        logger.info("Test database pool cleaned up")

    @contextmanager
    def transaction_context(self):
        """
        Context manager for database transactions in tests.

        Automatically rolls back changes after test completion.
        Uses a dedicated connection for transaction management.
        """
        if not self._pool:
            raise RuntimeError("Test database not initialized")

        # Get a connection directly from the pool (not using get_connection context manager)
        # to have full control over transaction management
        conn = None
        try:
            conn = self._pool._pool.getconn()

            # Set up transaction mode
            conn.autocommit = False

            try:
                yield conn
                # Always rollback to ensure test isolation
                conn.rollback()
            except Exception:
                if conn and not conn.closed:
                    conn.rollback()
                raise
            finally:
                if conn and not conn.closed:
                    conn.autocommit = True
        finally:
            # Return connection to pool
            if conn and self._pool and self._pool._pool:
                try:
                    self._pool._pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")

    def clear_all_test_data(self) -> None:
        """Clear all test data from database."""
        if not self._pool:
            return

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Clear all test data from test schema
                cur.execute("DELETE FROM test_schema.audio_tracks")
                # Reset sequences
                cur.execute("ALTER SEQUENCE test_schema.audio_tracks_id_seq RESTART WITH 1")
                conn.commit()

    def get_table_row_count(self, table_name: str = 'test_schema.audio_tracks') -> int:
        """Get row count for a table."""
        if not self._pool:
            return 0

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                result = cur.fetchone()
                return result[0] if result else 0


class TestDataFactory:
    """
    Factory for creating test data with various scenarios.

    Provides methods to create consistent test data for different
    test scenarios and edge cases.
    """

    @staticmethod
    def create_basic_track(track_id: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """Create a basic track for testing."""
        if track_id is None:
            track_id = DatabaseTestHelper.generate_test_track_id()

        data = DatabaseTestHelper.create_sample_track_data(**overrides)
        gcs_paths = DatabaseTestHelper.create_sample_gcs_paths(track_id)

        return {
            'track_id': track_id,
            'metadata': data,
            'audio_gcs_path': gcs_paths['audio'],
            'thumbnail_gcs_path': gcs_paths['thumbnail']
        }

    @staticmethod
    def create_track_batch(count: int = 5, **shared_overrides) -> List[Dict[str, Any]]:
        """Create a batch of tracks with shared properties."""
        tracks = []
        for i in range(count):
            overrides = shared_overrides.copy()
            overrides['title'] = f"{overrides.get('title', 'Batch Track')} {i+1}"
            tracks.append(TestDataFactory.create_basic_track(**overrides))
        return tracks

    @staticmethod
    def create_edge_case_tracks() -> List[Dict[str, Any]]:
        """Create tracks with edge case data."""
        return [
            # Minimum valid data
            TestDataFactory.create_basic_track(
                title="Min Track",
                year=1800,
                duration_seconds=0.1,
                channels=1
            ),
            # Maximum valid data
            TestDataFactory.create_basic_track(
                title="Max Track",
                year=2100,
                duration_seconds=36000,  # 10 hours
                channels=16
            ),
            # Unicode characters
            TestDataFactory.create_basic_track(
                title="Unicode 歌曲",
                artist="Unicode 艺术家",
                album="Unicode 专辑"
            ),
            # Very long strings
            TestDataFactory.create_basic_track(
                title="A" * 500,  # Long title
                artist="B" * 500,  # Long artist
                album="C" * 500   # Long album
            ),
        ]

    @staticmethod
    def create_search_test_tracks() -> List[Dict[str, Any]]:
        """Create tracks specifically for search testing."""
        return [
            TestDataFactory.create_basic_track(
                title="Bohemian Rhapsody",
                artist="Queen",
                album="A Night at the Opera",
                genre="Rock",
                year=1975
            ),
            TestDataFactory.create_basic_track(
                title="Stairway to Heaven",
                artist="Led Zeppelin",
                album="Led Zeppelin IV",
                genre="Rock",
                year=1971
            ),
            TestDataFactory.create_basic_track(
                title="Hotel California",
                artist="Eagles",
                album="Hotel California",
                genre="Rock",
                year=1976
            ),
            TestDataFactory.create_basic_track(
                title="Imagine",
                artist="John Lennon",
                album="Imagine",
                genre="Pop",
                year=1971
            ),
            TestDataFactory.create_basic_track(
                title="Hey Jude",
                artist="The Beatles",
                album="Hey Jude",
                genre="Pop",
                year=1968
            ),
        ]


class DatabaseMockFactory:
    """
    Factory for creating database mocks for unit testing.

    Provides mock implementations that don't require actual database connections.
    """

    @staticmethod
    def create_mock_connection() -> Mock:
        """Create a mock database connection."""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_conn.autocommit = True
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_conn.cursor.return_value)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        return mock_conn

    @staticmethod
    def create_mock_cursor() -> Mock:
        """Create a mock database cursor."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [(1,)]
        mock_cursor.rowcount = 1
        return mock_cursor

    @staticmethod
    def create_mock_pool() -> Mock:
        """Create a mock database connection pool."""
        mock_pool = Mock()
        mock_pool.getconn.return_value = DatabaseMockFactory.create_mock_connection()
        mock_pool.putconn = Mock()
        mock_pool.closeall = Mock()
        return mock_pool

    @staticmethod
    def create_mock_database_manager() -> Mock:
        """Create a mock database manager."""
        mock_manager = Mock()
        mock_manager.get_connection.return_value.__enter__ = Mock(return_value=DatabaseMockFactory.create_mock_connection())
        mock_manager.get_connection.return_value.__exit__ = Mock(return_value=None)
        mock_manager.health_check.return_value = {"healthy": True, "database_version": "15.0"}
        return mock_manager


# Global test database manager instance
_test_db_manager = TestDatabaseManager()


# Pytest fixtures for database testing
@pytest.fixture(scope="session")
def test_db_manager():
    """Session-scoped database manager for tests."""
    if not DatabaseTestHelper.is_database_configured():
        pytest.skip("Database not configured")

    _test_db_manager.setup_test_database()
    yield _test_db_manager
    _test_db_manager.cleanup_test_database()


@pytest.fixture
def db_transaction(test_db_manager):
    """Transaction fixture that rolls back changes after each test."""
    with test_db_manager.transaction_context() as conn:
        yield conn


@pytest.fixture
def clean_database(test_db_manager):
    """Fixture that ensures clean database state for each test."""
    test_db_manager.clear_all_test_data()
    yield
    # Cleanup happens automatically via transaction rollback


@pytest.fixture
def sample_track_data():
    """Fixture providing sample track data."""
    return TestDataFactory.create_basic_track()


@pytest.fixture
def sample_track_batch():
    """Fixture providing a batch of sample tracks."""
    return TestDataFactory.create_track_batch(3)


@pytest.fixture
def mock_db_connection():
    """Fixture providing a mock database connection."""
    return DatabaseMockFactory.create_mock_connection()


@pytest.fixture
def mock_db_pool():
    """Fixture providing a mock database connection pool."""
    return DatabaseMockFactory.create_mock_pool()


@pytest.fixture
def mock_database_manager():
    """Fixture providing a mock database manager."""
    return DatabaseMockFactory.create_mock_database_manager()


# Utility functions for test data management
def insert_test_track(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a test track into the test schema database.

    Args:
        track_data: Track data from TestDataFactory

    Returns:
        Inserted track data
    """
    # Use test schema for insertion
    with get_connection() as conn:
        with conn.cursor() as cur:
            metadata = track_data['metadata']
            cur.execute("""
                INSERT INTO test_schema.audio_tracks (
                    track_id, title, artist, album, genre, year, duration_seconds,
                    channels, sample_rate, bitrate, format, file_size_bytes,
                    audio_gcs_path, thumbnail_gcs_path, processing_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, track_id, title, artist, album, genre, year,
                         duration_seconds, channels, sample_rate, bitrate, format,
                         file_size_bytes, audio_gcs_path, thumbnail_gcs_path, processing_status
            """, (
                track_data['track_id'],
                metadata['title'],
                metadata.get('artist'),
                metadata.get('album'),
                metadata.get('genre'),
                metadata.get('year'),
                metadata.get('duration_seconds'),
                metadata.get('channels'),
                metadata.get('sample_rate'),
                metadata.get('bitrate'),
                metadata.get('format'),
                metadata.get('file_size_bytes'),
                track_data['audio_gcs_path'],
                track_data.get('thumbnail_gcs_path'),
                'COMPLETED'  # Default status for test tracks
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                return {
                    'id': result[0],
                    'track_id': result[1],
                    'title': result[2],
                    'artist': result[3],
                    'album': result[4],
                    'genre': result[5],
                    'year': result[6],
                    'duration_seconds': result[7],
                    'channels': result[8],
                    'sample_rate': result[9],
                    'bitrate': result[10],
                    'format': result[11],
                    'file_size_bytes': result[12],
                    'audio_gcs_path': result[13],
                    'thumbnail_gcs_path': result[14],
                    'processing_status': result[15]
                }

    return {}


def insert_test_track_batch(track_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Insert a batch of test tracks into the test schema database.

    Args:
        track_batch: List of track data from TestDataFactory

    Returns:
        Batch insertion results
    """
    # Use test schema for batch insertion
    with get_connection() as conn:
        with conn.cursor() as cur:
            track_ids = []

            for track_data in track_batch:
                metadata = track_data['metadata']
                cur.execute("""
                    INSERT INTO test_schema.audio_tracks (
                        track_id, title, artist, album, genre, year, duration_seconds,
                        channels, sample_rate, bitrate, format, file_size_bytes,
                        audio_gcs_path, thumbnail_gcs_path, processing_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    track_data['track_id'],
                    metadata['title'],
                    metadata.get('artist'),
                    metadata.get('album'),
                    metadata.get('genre'),
                    metadata.get('year'),
                    metadata.get('duration_seconds'),
                    metadata.get('channels'),
                    metadata.get('sample_rate'),
                    metadata.get('bitrate'),
                    metadata.get('format'),
                    metadata.get('file_size_bytes'),
                    track_data['audio_gcs_path'],
                    track_data.get('thumbnail_gcs_path'),
                    'COMPLETED'  # Default status for test tracks
                ))
                track_ids.append(track_data['track_id'])

            conn.commit()

            return {
                'inserted_count': len(track_batch),
                'track_ids': track_ids
            }


def count_tracks_in_database(status_filter: Optional[str] = None) -> int:
    """
    Count tracks in database with optional status filter.

    Args:
        status_filter: Optional status to filter by

    Returns:
        Number of tracks matching criteria
    """
    # Use test schema for counting
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status_filter:
                cur.execute(
                    "SELECT COUNT(*) FROM test_schema.audio_tracks WHERE processing_status = %s",
                    (status_filter,)
                )
            else:
                cur.execute("SELECT COUNT(*) FROM test_schema.audio_tracks")

            result = cur.fetchone()
            return result[0] if result else 0


def verify_track_exists(track_id: str) -> bool:
    """
    Verify a track exists in the database.

    Args:
        track_id: Track ID to check

    Returns:
        True if track exists, False otherwise
    """
    # Use test schema for verification
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM test_schema.audio_tracks WHERE track_id = %s",
                (track_id,)
            )
            result = cur.fetchone()
            return result is not None


def verify_track_data(track_id: str, expected_data: Dict[str, Any]) -> bool:
    """
    Verify track data matches expected values.

    Args:
        track_id: Track ID to check
        expected_data: Expected track data

    Returns:
        True if data matches, False otherwise
    """
    # Use test schema for verification
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, artist FROM test_schema.audio_tracks WHERE track_id = %s",
                (track_id,)
            )
            result = cur.fetchone()
            if not result:
                return False

            actual_title, actual_artist = result
            expected_title = expected_data.get('title')
            expected_artist = expected_data.get('artist')

            return (actual_title == expected_title and
                    actual_artist == expected_artist)

    return True


# Context managers for test scenarios
@contextmanager
def temporary_track(track_data: Optional[Dict[str, Any]] = None):
    """
    Context manager that creates a temporary track and cleans it up.

    Usage:
        with temporary_track() as track:
            # Use track in test
            assert track['id'] is not None
        # Track is automatically cleaned up
    """
    if track_data is None:
        track_data = TestDataFactory.create_basic_track()

    # Insert track
    inserted_track = insert_test_track(track_data)

    try:
        yield inserted_track
    finally:
        # Clean up (in real tests this would be handled by transaction rollback)
        pass


@contextmanager
def temporary_track_batch(track_batch: Optional[List[Dict[str, Any]]] = None):
    """
    Context manager that creates temporary tracks and cleans them up.

    Usage:
        with temporary_track_batch() as tracks:
            # Use tracks in test
            assert len(tracks) == 3
        # Tracks are automatically cleaned up
    """
    if track_batch is None:
        track_batch = TestDataFactory.create_track_batch(3)

    # Insert tracks
    result = insert_test_track_batch(track_batch)

    try:
        yield result
    finally:
        # Clean up (in real tests this would be handled by transaction rollback)
        pass


# Test assertion helpers
def assert_track_count(expected_count: int, status_filter: Optional[str] = None):
    """Assert that the database contains the expected number of tracks."""
    actual_count = count_tracks_in_database(status_filter)
    assert actual_count == expected_count, f"Expected {expected_count} tracks, found {actual_count}"


def assert_track_exists(track_id: str):
    """Assert that a track exists in the database."""
    assert verify_track_exists(track_id), f"Track {track_id} does not exist"


def assert_track_data_matches(track_id: str, expected_data: Dict[str, Any]):
    """Assert that track data matches expected values."""
    assert verify_track_data(track_id, expected_data), f"Track {track_id} data does not match expected"


# Export key classes and functions
__all__ = [
    'DatabaseTestHelper',
    'TestDatabaseManager',
    'TestDataFactory',
    'DatabaseMockFactory',
    'insert_test_track',
    'insert_test_track_batch',
    'count_tracks_in_database',
    'verify_track_exists',
    'verify_track_data',
    'temporary_track',
    'temporary_track_batch',
    'assert_track_count',
    'assert_track_exists',
    'assert_track_data_matches',
]
