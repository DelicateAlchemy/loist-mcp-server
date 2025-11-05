"""
Test configuration and fixtures for the MCP server tests.

Provides:
- Test database configuration and setup
- Repository mocks for dependency injection
- Environment variable management
- Common test utilities and fixtures
- Application initialization and configuration
- Logging setup for tests
"""

import os
import pytest
import logging
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, Generator

# Import configuration and logging utilities
try:
    from src.config import Config
    from src.fastmcp_setup import create_app
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

try:
    from src.repositories.audio_repository import AudioRepositoryInterface
    REPOSITORIES_AVAILABLE = True
except ImportError:
    REPOSITORIES_AVAILABLE = False


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables and configuration."""
    # Store original environment
    original_env = dict(os.environ)

    # Set test database configuration
    test_env = {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'music_library_test',
        'DB_USER': 'loist_user',
        'DB_PASSWORD': 'dev_password',
        'LOG_LEVEL': 'WARNING',  # Reduce log noise during tests
        'AUTH_ENABLED': 'false',
    }

    # Update environment
    os.environ.update(test_env)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="session")
def test_db_config():
    """Test database configuration."""
    return {
        'host': 'localhost',
        'port': 5432,
        'database': 'music_library_test',
        'user': 'loist_user',
        'password': 'dev_password'
    }


class MockAudioRepository:
    """Mock implementation of AudioRepositoryInterface for testing."""

    def __init__(self):
        self.metadata_store = {}
        self.search_results = []
        self.batch_results = {'inserted_count': 0}

    def save_metadata(self, metadata: Dict[str, Any], audio_gcs_path: str,
                     thumbnail_gcs_path: str = None, track_id: str = None) -> Dict[str, Any]:
        """Mock save single metadata."""
        track_id = track_id or metadata.get('id') or f"mock-{len(self.metadata_store)}"
        self.metadata_store[track_id] = {
            'id': track_id,
            **metadata,  # Flatten metadata into top level
            'audio_path': audio_gcs_path,
            'thumbnail_path': thumbnail_gcs_path,
            'status': 'COMPLETED'
        }
        return self.metadata_store[track_id]

    def save_metadata_batch(self, metadata_list: list) -> Dict[str, Any]:
        """Mock save batch metadata."""
        inserted_count = len(metadata_list)
        self.batch_results = {
            'inserted_count': inserted_count,
            'tracks': [
                {'id': f'mock-{i}', 'status': 'COMPLETED'}
                for i in range(inserted_count)
            ]
        }
        return self.batch_results

    def get_metadata_by_id(self, track_id: str) -> Dict[str, Any]:
        """Mock get metadata by ID."""
        return self.metadata_store.get(track_id)

    def get_metadata_by_ids(self, track_ids: list) -> Dict[str, Any]:
        """Mock get metadata by multiple IDs."""
        results = {}
        for track_id in track_ids:
            if track_id in self.metadata_store:
                results[track_id] = self.metadata_store[track_id]
        return results

    def get_all_metadata(self, limit: int = 20, offset: int = 0,
                        status_filter: str = None, order_by: str = "created_at",
                        order_direction: str = "DESC") -> Dict[str, Any]:
        """Mock get all metadata."""
        tracks = list(self.metadata_store.values())
        total = len(tracks)

        # Apply status filter if provided
        if status_filter:
            tracks = [t for t in tracks if t.get('status') == status_filter]

        # Apply pagination
        start_idx = offset
        end_idx = offset + limit
        paginated_tracks = tracks[start_idx:end_idx]

        return {
            'tracks': paginated_tracks,
            'total': total,
            'limit': limit,
            'offset': offset
        }

    def search_tracks(self, query: str, limit: int = 20, offset: int = 0,
                     min_rank: float = 0.0) -> list:
        """Mock search tracks."""
        return self.search_results[:limit]

    def search_tracks_advanced(self, query: str, limit: int = 20, offset: int = 0,
                             status_filter: str = None, year_min: int = None,
                             year_max: int = None, format_filter: str = None,
                             min_rank: float = 0.0, rank_normalization: int = 1) -> Dict[str, Any]:
        """Mock advanced search."""
        return {
            'tracks': self.search_results[:limit],
            'total_matches': len(self.search_results),
            'query': query,
            'limit': limit,
            'offset': offset
        }

    def update_status(self, track_id: str, status: str,
                     error_message: str = None, increment_retry: bool = False) -> Dict[str, Any]:
        """Mock update status."""
        if track_id in self.metadata_store:
            self.metadata_store[track_id]['status'] = status
            if error_message:
                self.metadata_store[track_id]['error_message'] = error_message
            return self.metadata_store[track_id]
        return {'error': 'Track not found'}

    def mark_processing(self, track_id: str) -> Dict[str, Any]:
        """Mock mark as processing."""
        return self.update_status(track_id, 'PROCESSING')

    def mark_completed(self, track_id: str) -> Dict[str, Any]:
        """Mock mark as completed."""
        return self.update_status(track_id, 'COMPLETED')

    def mark_failed(self, track_id: str, error_message: str, increment_retry: bool = True) -> Dict[str, Any]:
        """Mock mark as failed."""
        return self.update_status(track_id, 'FAILED', error_message)


@pytest.fixture
def mock_repository():
    """Fixture providing a mock audio repository."""
    if REPOSITORIES_AVAILABLE:
        # If interface is available, ensure our mock implements it
        repo = MockAudioRepository()
        # Add any missing methods if needed
        return repo
    else:
        # Fallback to basic mock
        return MockAudioRepository()


@pytest.fixture
def sample_audio_metadata():
    """Sample audio metadata for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "artist": "Test Artist",
        "title": "Test Track",
        "album": "Test Album",
        "genre": "Rock",
        "year": 2023,
        "duration": 245.5,
        "channels": 2,
        "sample_rate": 44100,
        "bitrate": 320000,
        "format": "MP3",
        "audio_path": "gs://test-bucket/audio/test-track.mp3",
        "thumbnail_path": "gs://test-bucket/thumbnails/test-thumb.jpg",
        "status": "COMPLETED"
    }


@pytest.fixture
def sample_gcs_paths():
    """Sample GCS paths for testing."""
    return {
        'audio': 'gs://test-bucket/audio/sample-track.mp3',
        'thumbnail': 'gs://test-bucket/thumbnails/sample-thumb.jpg'
    }


@pytest.fixture(autouse=True)
def reset_mocks(mock_repository):
    """Reset mock repository state between tests."""
    mock_repository.metadata_store.clear()
    mock_repository.search_results.clear()
    mock_repository.batch_results = {'inserted_count': 0}


# Application initialization fixtures
@pytest.fixture(scope="session")
def test_config():
    """Test configuration object."""
    if CONFIG_AVAILABLE:
        # Create a test configuration with test database settings
        config = Config()
        # Override database settings for testing
        config.db_host = 'localhost'
        config.db_port = 5432
        config.db_name = 'music_library_test'
        config.db_user = 'loist_user'
        config.db_password = 'dev_password'
        config.auth_enabled = False
        config.log_level = 'WARNING'
        return config
    else:
        # Fallback mock config
        return Mock(
            db_host='localhost',
            db_port=5432,
            db_name='music_library_test',
            db_user='loist_user',
            db_password='dev_password',
            auth_enabled=False,
            log_level='WARNING'
        )


@pytest.fixture(scope="session")
def test_app(test_config):
    """Test FastMCP application instance."""
    if CONFIG_AVAILABLE:
        app = create_app(config=test_config)
        return app
    else:
        return Mock()


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Set up logging configuration for tests."""
    # Configure test logging to reduce noise
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    # Suppress noisy loggers during tests
    logging.getLogger('httpx').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('google').setLevel(logging.ERROR)


@pytest.fixture
def app_context(test_app):
    """Application context for tests."""
    if hasattr(test_app, 'app') and hasattr(test_app.app, 'app_context'):
        with test_app.app.app_context():
            yield
    else:
        yield


# Environment management utilities
class TestEnv:
    """Context manager for temporary environment variable changes."""

    def __init__(self, **kwargs):
        self.new_env = kwargs
        self.original_env = {}

    def __enter__(self):
        for key, value in self.new_env.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = str(value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for key, original_value in self.original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


@pytest.fixture
def test_env():
    """Fixture providing TestEnv context manager."""
    return TestEnv
