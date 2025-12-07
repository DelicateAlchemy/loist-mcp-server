"""
Integration tests for MCP resource database connectivity.

These tests verify that MCP resource handlers (audio stream, metadata, thumbnail)
can correctly interact with the database using real connections and data.
They use the database testing infrastructure to ensure test isolation and
proper cleanup.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.resources.audio_stream import get_audio_stream_resource
from src.resources.metadata import get_metadata_resource
from src.resources.thumbnail import get_thumbnail_resource
from src.exceptions import ResourceNotFoundError, ValidationError

# Import test utilities for database interaction
from tests.database_testing import (
    TestDataFactory,
    insert_test_track,
    assert_track_exists
)

# ============================================================================
# Integration Tests for MCP Resources
# These tests verify actual database interaction.
# They require the 'test_db_manager' and 'db_transaction' fixtures from
# tests/database_testing.py, which are automatically provided via conftest.py
# ============================================================================

@pytest.mark.asyncio
async def test_metadata_resource_with_db_connection(db_transaction, clean_database):
    """
    Test metadata resource handler with a real database connection.
    Verifies that it can retrieve metadata for an existing audio track.
    """
    # 1. Setup: Insert a sample track into the clean test database
    track_data = TestDataFactory.create_basic_track(
        title="DB Test Song",
        artist="DB Test Artist",
        album="DB Test Album"
    )
    inserted_track = insert_test_track(track_data)
    track_id = inserted_track['track_id']
    
    # Verify track exists in DB
    assert_track_exists(track_id)

    # 2. Action: Call the metadata resource handler
    uri = f"music-library://audio/{track_id}/metadata"
    response = await get_metadata_resource(uri)

    # 3. Assert: Verify the response contains the correct metadata
    assert response is not None
    assert response["mimeType"] == "application/json"
    
    import json
    response_data = json.loads(response["text"])
    assert response_data["id"] == track_id
    assert response_data["Product"]["Title"] == "DB Test Song"
    assert response_data["Product"]["Artist"] == "DB Test Artist"
    assert response_data["Product"]["Album"] == "DB Test Album"
    assert response_data["Format"]["Format"] == "MP3"
    assert response_data["resources"]["audio"] == f"music-library://audio/{track_id}/stream"
    
    # db_transaction fixture will automatically roll back changes

@pytest.mark.asyncio
async def test_audio_stream_resource_with_db_connection(db_transaction, clean_database):
    """
    Test audio stream resource handler with a real database connection.
    Verifies that it can generate a signed URL for an existing audio track.
    """
    # 1. Setup: Insert a sample track into the clean test database
    track_data = TestDataFactory.create_basic_track(
        title="Stream Test Song",
        audio_gcs_path="gs://test-bucket/stream/test_audio.mp3"
    )
    inserted_track = insert_test_track(track_data)
    track_id = inserted_track['track_id']
    
    # Verify track exists in DB
    assert_track_exists(track_id)

    # Mock GCS signed URL generation, as this is outside DB scope
    with patch('src.storage.gcs_client.generate_signed_url', return_value="http://mock-signed-url/stream/test_audio.mp3"):
        # 2. Action: Call the audio stream resource handler
        uri = f"music-library://audio/{track_id}/stream"
        response = await get_audio_stream_resource(uri)

        # 3. Assert: Verify the response contains a signed URL and correct MIME type
        assert response is not None
        assert response["uri"] == "http://mock-signed-url/stream/test_audio.mp3"
        assert response["mimeType"] == "audio/mpeg"
    
    # db_transaction fixture will automatically roll back changes

@pytest.mark.asyncio
async def test_thumbnail_resource_with_db_connection(db_transaction, clean_database):
    """
    Test thumbnail resource handler with a real database connection.
    Verifies that it can generate a signed URL for an existing audio track's thumbnail.
    """
    # 1. Setup: Insert a sample track into the clean test database
    track_data = TestDataFactory.create_basic_track(
        title="Thumbnail Test Song",
        thumbnail_gcs_path="gs://test-bucket/thumbnails/test_thumb.jpg"
    )
    inserted_track = insert_test_track(track_data)
    track_id = inserted_track['track_id']
    
    # Verify track exists in DB
    assert_track_exists(track_id)

    # Mock GCS signed URL generation
    with patch('src.storage.gcs_client.generate_signed_url', return_value="http://mock-signed-url/thumbnails/test_thumb.jpg"):
        # 2. Action: Call the thumbnail resource handler
        uri = f"music-library://audio/{track_id}/thumbnail"
        response = await get_thumbnail_resource(uri)

        # 3. Assert: Verify the response contains a signed URL and correct MIME type
        assert response is not None
        assert response["uri"] == "http://mock-signed-url/thumbnails/test_thumb.jpg"
        assert response["mimeType"] == "image/jpeg"
    
    # db_transaction fixture will automatically roll back changes

@pytest.mark.asyncio
async def test_metadata_resource_invalid_audio_id(db_transaction, clean_database):
    """
    Test metadata resource handler with an invalid (non-existent) audio ID.
    Verifies that it raises ResourceNotFoundError.
    """
    non_existent_id = "550e8400-e29b-41d4-a716-invalid-id-not-found"
    uri = f"music-library://audio/{non_existent_id}/metadata"
    
    with pytest.raises(ResourceNotFoundError):
        await get_metadata_resource(uri)

@pytest.mark.asyncio
async def test_audio_stream_resource_invalid_audio_id(db_transaction, clean_database):
    """
    Test audio stream resource handler with an invalid (non-existent) audio ID.
    Verifies that it raises ResourceNotFoundError.
    """
    non_existent_id = "550e8400-e29b-41d4-a716-invalid-id-not-found"
    uri = f"music-library://audio/{non_existent_id}/stream"
    
    with pytest.raises(ResourceNotFoundError):
        await get_audio_stream_resource(uri)

@pytest.mark.asyncio
async def test_thumbnail_resource_invalid_audio_id(db_transaction, clean_database):
    """
    Test thumbnail resource handler with an invalid (non-existent) audio ID.
    Verifies that it raises ResourceNotFoundError.
    """
    non_existent_id = "550e8400-e29b-41d4-a716-invalid-id-not-found"
    uri = f"music-library://audio/{non_existent_id}/thumbnail"
    
    with pytest.raises(ResourceNotFoundError):
        await get_thumbnail_resource(uri)
