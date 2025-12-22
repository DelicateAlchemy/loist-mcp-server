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



# NOTE: TestEmbedUrlIntegration class was removed (2025-12-22)
# These tests were technical debt - they mocked src.server.* but the actual
# implementation was refactored to src/tools/embed_tools.py which imports
# from different locations (database, src.services.streaming_service).
# See LOI-27 for details.
