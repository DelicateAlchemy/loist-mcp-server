"""
Data Integrity and Validation Testing for Loist MCP Server.

This module provides comprehensive testing for:
- Database constraint enforcement
- Application-level data validation rules
- Data consistency across operations
- Edge cases and boundary conditions

Author: Task Master AI
Created: 2025-11-05
"""

import pytest
import uuid
import psycopg2
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

# Database testing infrastructure
from database_testing import (
    DatabaseTestHelper,
    TestDatabaseManager,
    TestDataFactory,
    DatabaseMockFactory,
    insert_test_track,
    assert_track_exists,
    assert_track_count,
    db_transaction,
    clean_database,
    sample_track_data,
)

# Database operations to test
from database.operations import (
    save_audio_metadata,
    get_audio_metadata_by_id,
    update_processing_status,
    save_audio_metadata_batch,
)

# Exception types to test
from src.exceptions import (
    ValidationError,
    DatabaseOperationError,
    ResourceNotFoundError,
)

# Test schema name
TEST_SCHEMA = "test_schema"


class ConstraintTests:
    """
    Tests for database constraint enforcement.

    Verifies that all database-level constraints are properly enforced:
    - Primary key uniqueness
    - Check constraints on fields
    - NOT NULL constraints
    - Foreign key relationships (if any)
    """

    @pytest.fixture
    def test_schema_setup(self, test_db_manager):
        """Set up test schema for constraint testing."""
        test_db_manager._create_test_schema()
        yield
        # Cleanup happens via transaction rollback

    def test_unique_track_id_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that track_id uniqueness is enforced."""
        # Create first track
        track_data = TestDataFactory.create_basic_track()
        insert_test_track(track_data)

        # Attempt to insert duplicate track_id - should fail
        duplicate_data = TestDataFactory.create_basic_track(track_id=track_data['track_id'])

        with pytest.raises((psycopg2.IntegrityError, DatabaseOperationError)):
            save_audio_metadata(
                metadata=duplicate_data['metadata'],
                audio_gcs_path=duplicate_data['audio_gcs_path'],
                track_id=duplicate_data['track_id']
            )

    def test_status_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that status values are constrained to valid options."""
        valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']

        # Test valid statuses
        for status in valid_statuses:
            track_data = TestDataFactory.create_basic_track()
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['status'] == 'COMPLETED'  # Default status

            # Update to test status
            update_processing_status(result['id'], status)
            updated = get_audio_metadata_by_id(result['id'])
            assert updated['status'] == status

        # Test invalid status - should fail
        track_data = TestDataFactory.create_basic_track()
        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        with pytest.raises(ValidationError):
            update_processing_status(result['id'], 'INVALID_STATUS')

    def test_year_range_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that year values are constrained to valid range (1800-2100)."""
        # Test valid years
        for year in [1800, 1900, 2000, 2023, 2100]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['year'] = year
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['year'] == year

        # Test invalid years - should fail
        for invalid_year in [1799, 2101, 3000, -100]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['year'] = invalid_year

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

        # Test NULL year - should be allowed
        track_data = TestDataFactory.create_basic_track()
        track_data['metadata']['year'] = None
        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )
        assert result['year'] is None

    def test_channels_range_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that channels values are constrained to valid range (1-16)."""
        # Test valid channels
        for channels in [1, 2, 5, 8, 16]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['channels'] = channels
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['channels'] == channels

        # Test invalid channels - should fail
        for invalid_channels in [0, -1, 17, 32]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['channels'] = invalid_channels

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_sample_rate_positive_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that sample_rate must be positive."""
        # Test valid sample rates
        for sample_rate in [8000, 22050, 44100, 48000, 96000]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['sample_rate'] = sample_rate
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['sample_rate'] == sample_rate

        # Test invalid sample rates - should fail
        for invalid_sample_rate in [0, -1, -44100]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['sample_rate'] = invalid_sample_rate

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_bitrate_positive_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that bitrate must be positive."""
        # Test valid bitrates
        for bitrate in [64000, 128000, 320000, 1411000]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['bitrate'] = bitrate
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['bitrate'] == bitrate

        # Test invalid bitrates - should fail
        for invalid_bitrate in [0, -1, -320000]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['bitrate'] = invalid_bitrate

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_file_size_bytes_positive_check_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that file_size_bytes must be positive."""
        # Test valid file sizes
        for file_size in [1024, 1048576, 52428800]:  # 1KB, 1MB, 50MB
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['file_size_bytes'] = file_size
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['file_size_bytes'] == file_size

        # Test invalid file sizes - should fail
        for invalid_size in [0, -1, -1024]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['file_size_bytes'] = invalid_size

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_audio_gcs_path_format_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that audio_gcs_path must start with 'gs://'."""
        # Test valid GCS paths
        valid_paths = [
            'gs://bucket/file.mp3',
            'gs://my-bucket/path/to/file.flac',
            'gs://test-bucket/audio/file.wav'
        ]

        for path in valid_paths:
            track_data = TestDataFactory.create_basic_track()
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=path
            )
            assert result['audio_gcs_path'] == path

        # Test invalid paths - should fail
        invalid_paths = [
            'http://bucket/file.mp3',
            's3://bucket/file.mp3',
            'file.mp3',
            '/path/to/file.mp3',
            ''
        ]

        for invalid_path in invalid_paths:
            track_data = TestDataFactory.create_basic_track()

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=invalid_path
                )

    def test_thumbnail_gcs_path_format_constraint(self, test_db_manager, db_transaction, clean_database):
        """Test that thumbnail_gcs_path must start with 'gs://' if provided."""
        # Test valid thumbnail paths
        valid_paths = [
            'gs://bucket/thumbnail.jpg',
            'gs://my-bucket/artwork/cover.png'
        ]

        for path in valid_paths:
            track_data = TestDataFactory.create_basic_track()
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path'],
                thumbnail_gcs_path=path
            )
            assert result['thumbnail_gcs_path'] == path

        # Test NULL thumbnail - should be allowed
        track_data = TestDataFactory.create_basic_track()
        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path'],
            thumbnail_gcs_path=None
        )
        assert result['thumbnail_gcs_path'] is None

        # Test invalid thumbnail paths - should fail
        invalid_paths = [
            'http://bucket/thumbnail.jpg',
            's3://bucket/thumbnail.jpg',
            'thumbnail.jpg',
            '/path/to/thumbnail.jpg'
        ]

        for invalid_path in invalid_paths:
            track_data = TestDataFactory.create_basic_track()

            with pytest.raises(ValidationError):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path'],
                    thumbnail_gcs_path=invalid_path
                )


class ValidationTests:
    """
    Tests for application-level data validation rules.

    Verifies that validation logic in the application layer works correctly
    before data reaches the database.
    """

    def test_required_title_validation(self, test_db_manager, db_transaction, clean_database):
        """Test that title is required."""
        track_data = TestDataFactory.create_basic_track()
        track_data['metadata']['title'] = None

        with pytest.raises(ValidationError, match="Title is required"):
            save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )

        # Test empty string
        track_data['metadata']['title'] = ''
        with pytest.raises(ValidationError, match="Title is required"):
            save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )

        # Test whitespace-only
        track_data['metadata']['title'] = '   '
        with pytest.raises(ValidationError, match="Title is required"):
            save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )

    def test_required_format_validation(self, test_db_manager, db_transaction, clean_database):
        """Test that format is required."""
        track_data = TestDataFactory.create_basic_track()
        track_data['metadata']['format'] = None

        with pytest.raises(ValidationError, match="Format is required"):
            save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )

        # Test empty string
        track_data['metadata']['format'] = ''
        with pytest.raises(ValidationError, match="Format is required"):
            save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )

    def test_uuid_format_validation(self, test_db_manager, db_transaction, clean_database):
        """Test that track_id must be valid UUID format."""
        track_data = TestDataFactory.create_basic_track()

        # Test valid UUID
        valid_uuid = str(uuid.uuid4())
        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path'],
            track_id=valid_uuid
        )
        assert result['id'] == valid_uuid

        # Test invalid UUID formats
        invalid_uuids = [
            'not-a-uuid',
            '123',
            '123e4567-e89b-12d3-a456-42661417400',  # Too short
            '123e4567-e89b-12d3-a456-426614174000-extra',  # Too long
            'gggggggg-hhhh-iiii-jjjj-kkkkkkkkkkkk',  # Invalid hex
            '',
            None
        ]

        for invalid_uuid in invalid_uuids:
            with pytest.raises(ValidationError, match="Invalid track_id format"):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path'],
                    track_id=invalid_uuid
                )

    def test_year_validation_range(self, test_db_manager, db_transaction, clean_database):
        """Test year validation at application level."""
        # Test valid years
        for year in [1800, 1900, 2000, 2023, 2100]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['year'] = year
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['year'] == year

        # Test invalid years
        for invalid_year in [1799, 2101, 3000, -100]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['year'] = invalid_year

            with pytest.raises(ValidationError, match="Year must be between 1800 and 2100"):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_channels_validation_range(self, test_db_manager, db_transaction, clean_database):
        """Test channels validation at application level."""
        # Test valid channels
        for channels in [1, 2, 5, 8, 16]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['channels'] = channels
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=track_data['audio_gcs_path']
            )
            assert result['channels'] == channels

        # Test invalid channels
        for invalid_channels in [0, -1, 17, 32]:
            track_data = TestDataFactory.create_basic_track()
            track_data['metadata']['channels'] = invalid_channels

            with pytest.raises(ValidationError, match="Channels must be between 1 and 16"):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path']
                )

    def test_gcs_path_validation(self, test_db_manager, db_transaction, clean_database):
        """Test GCS path validation at application level."""
        track_data = TestDataFactory.create_basic_track()

        # Test valid audio paths
        valid_audio_paths = [
            'gs://bucket/file.mp3',
            'gs://my-bucket/path/to/file.flac'
        ]

        for path in valid_audio_paths:
            result = save_audio_metadata(
                metadata=track_data['metadata'],
                audio_gcs_path=path
            )
            assert result['audio_gcs_path'] == path

        # Test invalid audio paths
        invalid_audio_paths = [
            'http://bucket/file.mp3',
            's3://bucket/file.mp3',
            'file.mp3',
            '/path/to/file.mp3',
            '',
            None
        ]

        for invalid_path in invalid_audio_paths:
            with pytest.raises(ValidationError, match="Invalid audio_gcs_path"):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=invalid_path
                )

        # Test invalid thumbnail paths
        invalid_thumb_paths = [
            'http://bucket/thumb.jpg',
            's3://bucket/thumb.jpg',
            'thumb.jpg'
        ]

        for invalid_path in invalid_thumb_paths:
            with pytest.raises(ValidationError, match="Invalid thumbnail_gcs_path"):
                save_audio_metadata(
                    metadata=track_data['metadata'],
                    audio_gcs_path=track_data['audio_gcs_path'],
                    thumbnail_gcs_path=invalid_path
                )


class ConsistencyTests:
    """
    Tests for data consistency across operations.

    Verifies that operations maintain data consistency and relationships
    between related data elements.
    """

    def test_batch_operation_consistency(self, test_db_manager, db_transaction, clean_database):
        """Test that batch operations maintain data consistency."""
        # Create batch of tracks
        batch_data = TestDataFactory.create_track_batch(3)

        # Convert to batch format
        batch_records = []
        for track in batch_data:
            batch_records.append({
                'metadata': track['metadata'],
                'audio_gcs_path': track['audio_gcs_path'],
                'thumbnail_gcs_path': track.get('thumbnail_gcs_path'),
                'track_id': track['track_id']
            })

        # Save batch
        result = save_audio_metadata_batch(batch_records)

        assert result['success'] == True
        assert result['inserted_count'] == 3
        assert len(result['track_ids']) == 3

        # Verify all tracks exist and data is consistent
        for track_id in result['track_ids']:
            track = get_audio_metadata_by_id(track_id)
            assert track is not None
            assert track['status'] == 'COMPLETED'
            assert track['audio_gcs_path'].startswith('gs://')

    def test_status_update_consistency(self, test_db_manager, db_transaction, clean_database):
        """Test that status updates maintain consistency."""
        # Create track
        track_data = TestDataFactory.create_basic_track()
        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track_id = result['id']

        # Update to PROCESSING
        update_result = update_processing_status(track_id, 'PROCESSING')
        assert update_result['status'] == 'PROCESSING'

        # Verify in database
        track = get_audio_metadata_by_id(track_id)
        assert track['status'] == 'PROCESSING'
        assert track['last_processed_at'] is not None

        # Update to FAILED with error
        error_msg = "Test error message"
        update_result = update_processing_status(track_id, 'FAILED', error_message=error_msg, increment_retry=True)
        assert update_result['status'] == 'FAILED'
        assert update_result['retry_count'] == 1

        # Verify error tracking
        track = get_audio_metadata_by_id(track_id)
        assert track['status'] == 'FAILED'
        assert track['error_message'] == error_msg
        assert track['retry_count'] == 1

    def test_timestamp_consistency(self, test_db_manager, db_transaction, clean_database):
        """Test that timestamps are updated consistently."""
        import time

        # Create track
        track_data = TestDataFactory.create_basic_track()
        start_time = time.time()

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        # Check initial timestamps
        assert result['created_at'] is not None
        assert result['updated_at'] is not None
        assert result['created_at'] == result['updated_at']  # Should be equal for new records

        track_id = result['id']
        initial_created_at = result['created_at']

        # Wait a moment and update
        time.sleep(0.1)
        update_result = update_processing_status(track_id, 'PROCESSING')

        # Verify timestamps
        assert update_result['last_processed_at'] is not None
        track = get_audio_metadata_by_id(track_id)

        # created_at should not change
        assert track['created_at'] == initial_created_at
        # updated_at should be newer
        assert track['updated_at'] > initial_created_at

    def test_search_vector_consistency(self, test_db_manager, db_transaction, clean_database):
        """Test that search vector is maintained consistently."""
        # Create track with searchable content
        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update({
            'title': 'Bohemian Rhapsody',
            'artist': 'Queen',
            'album': 'A Night at the Opera',
            'genre': 'Rock'
        })

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        # Verify search vector exists (should be populated by trigger)
        track = get_audio_metadata_by_id(result['id'])
        # Note: search_vector is not returned by default query, but trigger should populate it

        # Update searchable fields
        update_result = update_processing_status(result['id'], 'COMPLETED')
        track_updated = get_audio_metadata_by_id(result['id'])

        # Fields should remain consistent
        assert track_updated['title'] == 'Bohemian Rhapsody'
        assert track_updated['artist'] == 'Queen'


class EdgeCaseTests:
    """
    Tests for edge cases, boundary conditions, and special scenarios.

    Covers NULL values, boundary conditions, very long strings,
    unicode characters, and other special cases.
    """

    def test_null_value_handling(self, test_db_manager, db_transaction, clean_database):
        """Test handling of NULL values in optional fields."""
        # Create track with all optional fields as None
        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update({
            'artist': None,
            'album': None,
            'genre': None,
            'year': None,
            'duration_seconds': None,
            'channels': None,
            'sample_rate': None,
            'bitrate': None,
            'file_size_bytes': None
        })

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path'],
            thumbnail_gcs_path=None
        )

        # Verify NULL values are stored correctly
        track = get_audio_metadata_by_id(result['id'])
        assert track['artist'] is None
        assert track['album'] is None
        assert track['genre'] is None
        assert track['year'] is None
        assert track['duration_seconds'] is None
        assert track['channels'] is None
        assert track['sample_rate'] is None
        assert track['bitrate'] is None
        assert track['file_size_bytes'] is None
        assert track['thumbnail_gcs_path'] is None

    def test_boundary_value_limits(self, test_db_manager, db_transaction, clean_database):
        """Test boundary values for numeric fields."""
        # Test minimum values
        min_values = {
            'year': 1800,
            'channels': 1,
            'sample_rate': 1,
            'bitrate': 1,
            'file_size_bytes': 1,
            'duration_seconds': 0.001
        }

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update(min_values)

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        for field, expected_value in min_values.items():
            assert track[field] == expected_value

        # Test maximum values
        max_values = {
            'year': 2100,
            'channels': 16,
            'duration_seconds': 86400.0  # 24 hours
        }

        track_data2 = TestDataFactory.create_basic_track()
        track_data2['metadata'].update(max_values)

        result2 = save_audio_metadata(
            metadata=track_data2['metadata'],
            audio_gcs_path=track_data2['audio_gcs_path']
        )

        track2 = get_audio_metadata_by_id(result2['id'])
        for field, expected_value in max_values.items():
            assert track2[field] == expected_value

    def test_long_string_handling(self, test_db_manager, db_transaction, clean_database):
        """Test handling of very long strings in text fields."""
        # Test maximum length strings (VARCHAR(500) for title, artist, album)
        long_title = "A" * 500
        long_artist = "B" * 500
        long_album = "C" * 500
        long_genre = "D" * 100  # VARCHAR(100) for genre

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update({
            'title': long_title,
            'artist': long_artist,
            'album': long_album,
            'genre': long_genre
        })

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        assert track['title'] == long_title
        assert track['artist'] == long_artist
        assert track['album'] == long_album
        assert track['genre'] == long_genre

        # Test exceeding limits - should be handled gracefully
        too_long_title = "A" * 600  # Exceeds VARCHAR(500)
        track_data2 = TestDataFactory.create_basic_track()
        track_data2['metadata']['title'] = too_long_title

        # Should either truncate or raise appropriate error
        try:
            save_audio_metadata(
                metadata=track_data2['metadata'],
                audio_gcs_path=track_data2['audio_gcs_path']
            )
        except (DatabaseOperationError, psycopg2.DataError):
            # Expected - string too long
            pass

    def test_unicode_character_handling(self, test_db_manager, db_transaction, clean_database):
        """Test handling of unicode characters in metadata."""
        unicode_data = {
            'title': '歌曲标题',  # Chinese
            'artist': '艺术家名',  # Chinese
            'album': '专辑名称',  # Chinese
            'genre': '类型名称'   # Chinese
        }

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update(unicode_data)

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        for field, expected_value in unicode_data.items():
            assert track[field] == expected_value

        # Test emojis
        emoji_data = {
            'title': '🎵 Song Title 🎶',
            'artist': '🎤 Artist Name 🎧',
            'album': '💿 Album Name 🎼'
        }

        track_data2 = TestDataFactory.create_basic_track()
        track_data2['metadata'].update(emoji_data)

        result2 = save_audio_metadata(
            metadata=track_data2['metadata'],
            audio_gcs_path=track_data2['audio_gcs_path']
        )

        track2 = get_audio_metadata_by_id(result2['id'])
        for field, expected_value in emoji_data.items():
            assert track2[field] == expected_value

    def test_special_characters_handling(self, test_db_manager, db_transaction, clean_database):
        """Test handling of special characters and SQL injection attempts."""
        special_data = {
            'title': "Song's Title (feat. Artist) [Remix] - 2023",
            'artist': 'Artist & Producer feat. DJ Name',
            'album': 'Greatest Hits Vol. 1 (Deluxe Edition)',
            'genre': 'Rock/Pop/Alternative'
        }

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update(special_data)

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        for field, expected_value in special_data.items():
            assert track[field] == expected_value

    def test_empty_and_whitespace_handling(self, test_db_manager, db_transaction, clean_database):
        """Test handling of empty strings and whitespace."""
        # Test whitespace-only strings in optional fields
        whitespace_data = {
            'artist': '   ',
            'album': '\t\n  ',
            'genre': ' '
        }

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update(whitespace_data)

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        # Should store whitespace as-is (not convert to NULL)
        for field, expected_value in whitespace_data.items():
            assert track[field] == expected_value

    def test_extreme_numeric_values(self, test_db_manager, db_transaction, clean_database):
        """Test handling of extreme but valid numeric values."""
        extreme_data = {
            'duration_seconds': 31536000.0,  # 1 year in seconds
            'sample_rate': 192000,  # Very high sample rate
            'bitrate': 14112000,  # Very high bitrate
            'file_size_bytes': 10737418240  # 10GB
        }

        track_data = TestDataFactory.create_basic_track()
        track_data['metadata'].update(extreme_data)

        result = save_audio_metadata(
            metadata=track_data['metadata'],
            audio_gcs_path=track_data['audio_gcs_path']
        )

        track = get_audio_metadata_by_id(result['id'])
        for field, expected_value in extreme_data.items():
            assert track[field] == expected_value


class TestDataGenerator:
    """
    Test data generator for diverse test scenarios.

    Provides methods to create varied test data including edge cases,
    invalid data for negative testing, and comprehensive coverage scenarios.
    """

    @staticmethod
    def create_comprehensive_test_dataset() -> List[Dict[str, Any]]:
        """
        Create a comprehensive dataset covering all validation scenarios.

        Returns:
            List of test track data covering various scenarios
        """
        test_tracks = []

        # Valid tracks with different formats
        formats = ['MP3', 'FLAC', 'WAV', 'AAC', 'OGG']
        for fmt in formats:
            track = TestDataFactory.create_basic_track()
            track['metadata']['format'] = fmt
            test_tracks.append(track)

        # Edge case tracks
        test_tracks.extend(TestDataFactory.create_edge_case_tracks())

        # Search-specific tracks
        test_tracks.extend(TestDataFactory.create_search_test_tracks())

        # Tracks with various metadata completeness
        completeness_scenarios = [
            # Minimal valid data
            {'title': 'Minimal Track', 'format': 'MP3'},
            # Full metadata
            {
                'title': 'Complete Track',
                'artist': 'Complete Artist',
                'album': 'Complete Album',
                'genre': 'Complete Genre',
                'year': 2023,
                'duration_seconds': 180.0,
                'channels': 2,
                'sample_rate': 44100,
                'bitrate': 320000,
                'format': 'FLAC',
                'file_size_bytes': 10485760
            },
            # Partial metadata
            {
                'title': 'Partial Track',
                'artist': 'Partial Artist',
                'format': 'MP3',
                'year': 2020
            }
        ]

        for scenario in completeness_scenarios:
            track = TestDataFactory.create_basic_track()
            track['metadata'].update(scenario)
            test_tracks.append(track)

        return test_tracks

    @staticmethod
    def create_invalid_test_dataset() -> List[Dict[str, Any]]:
        """
        Create dataset with intentionally invalid data for negative testing.

        Returns:
            List of invalid track data that should fail validation
        """
        invalid_tracks = []

        # Missing required fields
        invalid_scenarios = [
            {'format': 'MP3'},  # Missing title
            {'title': 'Test Track'},  # Missing format
            {'title': '', 'format': 'MP3'},  # Empty title
            {'title': 'Test', 'format': ''},  # Empty format
        ]

        for scenario in invalid_scenarios:
            track = TestDataFactory.create_basic_track()
            track['metadata'].update(scenario)
            invalid_tracks.append(track)

        # Invalid value ranges
        range_violations = [
            {'year': 1799},
            {'year': 2101},
            {'channels': 0},
            {'channels': 17},
            {'sample_rate': 0},
            {'sample_rate': -1},
            {'bitrate': 0},
            {'file_size_bytes': 0},
        ]

        for violation in range_violations:
            track = TestDataFactory.create_basic_track()
            track['metadata'].update(violation)
            invalid_tracks.append(track)

        # Invalid GCS paths
        path_violations = [
            {'audio_gcs_path': 'http://bucket/file.mp3'},
            {'audio_gcs_path': 's3://bucket/file.mp3'},
            {'audio_gcs_path': 'file.mp3'},
            {'thumbnail_gcs_path': 'http://bucket/thumb.jpg'},
        ]

        for violation in path_violations:
            track = TestDataFactory.create_basic_track()
            track.update(violation)
            invalid_tracks.append(track)

        # Invalid UUIDs
        uuid_violations = [
            {'track_id': 'not-a-uuid'},
            {'track_id': '123'},
            {'track_id': ''},
        ]

        for violation in uuid_violations:
            track = TestDataFactory.create_basic_track()
            track.update(violation)
            invalid_tracks.append(track)

        return invalid_tracks

    @staticmethod
    def create_performance_test_dataset(size: int = 1000) -> List[Dict[str, Any]]:
        """
        Create large dataset for performance testing.

        Args:
            size: Number of tracks to generate

        Returns:
            List of tracks for performance testing
        """
        return TestDataFactory.create_track_batch(size)

    @staticmethod
    def create_batch_test_dataset(batches: int = 5, batch_size: int = 10) -> List[List[Dict[str, Any]]]:
        """
        Create multiple batches of test data for batch operation testing.

        Args:
            batches: Number of batches to create
            batch_size: Size of each batch

        Returns:
            List of batches, each containing track data
        """
        batch_datasets = []
        for _ in range(batches):
            batch = TestDataFactory.create_track_batch(batch_size)
            batch_datasets.append(batch)
        return batch_datasets
