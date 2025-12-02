"""
Unit tests for PlayerConfig consolidation functionality.

Tests the new PlayerConfig Pydantic models and the consolidated embed tool behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from src.tools.schemas import PlayerConfig, PlayerConfigUrls, PlayerConfigMetadata


class TestPlayerConfigModels:
    """Test PlayerConfig Pydantic models."""

    def test_player_config_urls_model(self):
        """Test PlayerConfigUrls model validation."""
        # Test complete URLs
        urls = PlayerConfigUrls(
            embed="https://loist.io/embed/123",
            waveform="https://loist.io/embed/123/waveform",
            artwork="https://storage.googleapis.com/artwork.jpg",
            waveform_svg="https://storage.googleapis.com/waveform.svg"
        )
        assert urls.embed == "https://loist.io/embed/123"
        assert urls.waveform == "https://loist.io/embed/123/waveform"
        assert urls.artwork == "https://storage.googleapis.com/artwork.jpg"
        assert urls.waveform_svg == "https://storage.googleapis.com/waveform.svg"

        # Test optional fields
        minimal_urls = PlayerConfigUrls(embed="https://loist.io/embed/123")
        assert minimal_urls.embed == "https://loist.io/embed/123"
        assert minimal_urls.waveform is None
        assert minimal_urls.artwork is None
        assert minimal_urls.waveform_svg is None

    def test_player_config_metadata_model(self):
        """Test PlayerConfigMetadata model validation."""
        # Test complete metadata
        metadata = PlayerConfigMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_seconds=180.5
        )
        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.duration_seconds == 180.5

        # Test optional fields
        minimal_metadata = PlayerConfigMetadata(
            title="Test Song",
            artist="Test Artist"
        )
        assert minimal_metadata.title == "Test Song"
        assert minimal_metadata.artist == "Test Artist"
        assert minimal_metadata.album is None
        assert minimal_metadata.duration_seconds is None

    def test_player_config_model(self):
        """Test complete PlayerConfig model validation."""
        urls = PlayerConfigUrls(embed="https://loist.io/embed/123")
        metadata = PlayerConfigMetadata(
            title="Test Song",
            artist="Test Artist"
        )

        config = PlayerConfig(
            audio_id="550e8400-e29b-41d4-a716-446655440000",
            mode="waveform",
            device="desktop",
            context="embed",
            waveform_available=True,
            urls=urls,
            metadata=metadata
        )

        assert config.audio_id == "550e8400-e29b-41d4-a716-446655440000"
        assert config.mode == "waveform"
        assert config.device == "desktop"
        assert config.context == "embed"
        assert config.waveform_available is True
        assert isinstance(config.urls, PlayerConfigUrls)
        assert isinstance(config.metadata, PlayerConfigMetadata)

    def test_player_config_model_dump(self):
        """Test PlayerConfig serialization."""
        urls = PlayerConfigUrls(
            embed="https://loist.io/embed/123",
            waveform="https://loist.io/embed/123/waveform"
        )
        metadata = PlayerConfigMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_seconds=180.5
        )

        config = PlayerConfig(
            audio_id="550e8400-e29b-41d4-a716-446655440000",
            mode="waveform",
            device="desktop",
            context="embed",
            waveform_available=True,
            urls=urls,
            metadata=metadata
        )

        dumped = config.model_dump()
        expected = {
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "mode": "waveform",
            "device": "desktop",
            "context": "embed",
            "waveform_available": True,
            "urls": {
                "embed": "https://loist.io/embed/123",
                "waveform": "https://loist.io/embed/123/waveform",
                "artwork": None,
                "waveform_svg": None
            },
            "metadata": {
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album",
                "duration_seconds": 180.5
            }
        }

        assert dumped == expected

    def test_player_config_validation(self):
        """Test PlayerConfig validation with invalid data."""
        urls = PlayerConfigUrls(embed="https://loist.io/embed/123")
        metadata = PlayerConfigMetadata(title="Test", artist="Artist")

        # Test invalid mode
        with pytest.raises(ValueError):
            PlayerConfig(
                audio_id="550e8400-e29b-41d4-a716-446655440000",
                mode="invalid_mode",  # Should be "simple" or "waveform"
                device="desktop",
                context="embed",
                waveform_available=True,
                urls=urls,
                metadata=metadata
            )

        # Test invalid device
        with pytest.raises(ValueError):
            PlayerConfig(
                audio_id="550e8400-e29b-41d4-a716-446655440000",
                mode="waveform",
                device="invalid_device",  # Should be "desktop", "mobile", or "auto"
                context="embed",
                waveform_available=True,
                urls=urls,
                metadata=metadata
            )

        # Test invalid context
        with pytest.raises(ValueError):
            PlayerConfig(
                audio_id="550e8400-e29b-41d4-a716-446655440000",
                mode="waveform",
                device="desktop",
                context="invalid_context",  # Should be "embed" or "direct"
                waveform_available=True,
                urls=urls,
                metadata=metadata
            )


class TestEmbedUrlIntegration:
    """Test get_embed_url PlayerConfig response integration."""

    @pytest.mark.asyncio
    @patch('src.server.get_waveform_context')
    @patch('src.server.get_audio_metadata_by_id')
    @patch('src.server.get_cache')
    @patch('src.storage.waveform_storage.get_waveform_signed_url')
    async def test_get_embed_url_waveform_mode(self, mock_get_waveform_url, mock_get_cache, mock_get_metadata, mock_get_waveform_context):
        """Test get_embed_url returns PlayerConfig shape for waveform template."""
        from src.server import get_embed_url

        # Mock dependencies
        mock_get_metadata.return_value = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.5,
            'format': 'MP3',
            'thumbnail_gcs_path': 'gs://bucket/artwork.jpg'
        }

        mock_get_waveform_context.return_value = {
            'waveform_available': True,
            'waveform_url': 'https://storage.googleapis.com/waveform.svg'
        }

        mock_cache = MagicMock()
        mock_cache.get.return_value = 'https://storage.googleapis.com/artwork.jpg?signed'
        mock_get_cache.return_value = mock_cache

        mock_get_waveform_url.return_value = 'https://storage.googleapis.com/waveform.svg?signed'

        # Call the function
        result = await get_embed_url(
            audio_id="550e8400-e29b-41d4-a716-446655440000",
            template="waveform",
            device="desktop"
        )

        # Verify success
        assert result['success'] is True

        # Verify PlayerConfig structure
        assert 'audio_id' in result
        assert 'mode' in result
        assert 'device' in result
        assert 'context' in result
        assert 'waveform_available' in result
        assert 'urls' in result
        assert 'metadata' in result

        # Verify specific values
        assert result['audio_id'] == "550e8400-e29b-41d4-a716-446655440000"
        assert result['mode'] == "waveform"
        assert result['device'] == "desktop"
        assert result['context'] == "embed"
        assert result['waveform_available'] is True

        # Verify URLs structure
        urls = result['urls']
        assert 'embed' in urls
        assert 'waveform' in urls
        assert 'artwork' in urls
        assert 'waveform_svg' in urls

        # Verify metadata structure
        metadata = result['metadata']
        assert metadata['title'] == 'Test Song'
        assert metadata['artist'] == 'Test Artist'
        assert metadata['album'] == 'Test Album'
        assert metadata['duration_seconds'] == 180.5

    @pytest.mark.asyncio
    @patch('src.server.get_waveform_context')
    @patch('src.server.get_audio_metadata_by_id')
    async def test_get_embed_url_simple_mode(self, mock_get_metadata, mock_get_waveform_context):
        """Test get_embed_url returns PlayerConfig shape for simple template."""
        from src.server import get_embed_url

        # Mock dependencies
        mock_get_metadata.return_value = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'duration': 120.0,
            'format': 'MP3'
        }

        mock_get_waveform_context.return_value = {
            'waveform_available': False
        }

        # Call the function
        result = await get_embed_url(
            audio_id="550e8400-e29b-41d4-a716-446655440000",
            template="standard",
            device="mobile"
        )

        # Verify success and structure
        assert result['success'] is True
        assert result['mode'] == "simple"
        assert result['device'] == "mobile"
        assert result['context'] == "embed"
        assert result['waveform_available'] is False

        # Verify URLs
        urls = result['urls']
        assert urls['waveform'] is None  # No waveform URL for simple mode


class TestCheckWaveformAvailabilityDeprecation:
    """Test check_waveform_availability deprecation behavior."""

    @pytest.mark.asyncio
    @patch('src.server.get_embed_url')
    async def test_check_waveform_availability_delegation(self, mock_get_embed_url):
        """Test check_waveform_availability delegates to get_embed_url."""
        from src.server import check_waveform_availability

        # Mock the delegated call
        mock_result = {
            'success': True,
            'audio_id': '550e8400-e29b-41d4-a716-446655440000',
            'mode': 'waveform',
            'device': 'auto',
            'context': 'embed',
            'waveform_available': True,
            'urls': {'embed': 'https://loist.io/embed/123'},
            'metadata': {'title': 'Test', 'artist': 'Artist'}
        }
        mock_get_embed_url.return_value = mock_result

        # Capture log messages
        with patch('src.server.logger') as mock_logger:
            result = await check_waveform_availability("550e8400-e29b-41d4-a716-446655440000")

            # Verify deprecation warning was logged
            mock_logger.warning.assert_called_once_with(
                "check_waveform_availability is deprecated. Use get_embed_url instead for audio_id: 550e8400-e29b-41d4-a716-446655440000"
            )

            # Verify delegation
            mock_get_embed_url.assert_called_once_with(
                "550e8400-e29b-41d4-a716-446655440000",
                template="waveform",
                device="auto"
            )

            # Verify result is returned unchanged
            assert result == mock_result
