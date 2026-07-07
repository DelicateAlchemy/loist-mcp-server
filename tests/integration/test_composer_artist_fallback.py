"""
Integration tests for composer→artist fallback in the full processing pipeline.

Tests the complete flow from file processing to API response with fallback verification.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import asyncio

from src.tools.process_audio import process_audio_complete
from src.tools.schemas import ProcessAudioInput
from database.operations import get_audio_metadata_by_id


class TestComposerArtistFallbackIntegration:
    """Integration tests for composer→artist fallback in full pipeline.

    The pipeline logic now lives in src/business/audio_processor.py
    (process_audio_complete is a thin MCP adapter over process_audio_shared),
    so mocks patch the audio_processor namespace.
    """

    @patch('src.business.audio_processor.mark_as_completed')
    @patch('src.business.audio_processor.mark_as_processing')
    @patch('src.business.audio_processor.save_audio_metadata')
    @patch('src.business.audio_processor.upload_audio_file')
    @patch('src.business.audio_processor.extract_artwork')
    @patch('src.business.audio_processor.parse_filename_metadata')
    @patch('src.business.audio_processor.should_attempt_bwf_extraction')
    @patch('src.business.audio_processor.enhance_metadata_with_xmp')
    @patch('src.business.audio_processor.should_attempt_xmp_extraction')
    @patch('src.business.audio_processor.extract_metadata_with_fallback')
    @patch('src.business.audio_processor.download_from_url')
    @patch('src.business.audio_processor.validate_ssrf')
    @pytest.mark.asyncio
    async def test_fallback_applied_in_pipeline(
        self,
        mock_validate_ssrf,
        mock_download,
        mock_extract_metadata,
        mock_should_attempt_xmp,
        mock_enhance_xmp,
        mock_should_attempt_bwf,
        mock_parse_filename,
        mock_extract_artwork,
        mock_upload_audio,
        mock_save_metadata,
        mock_mark_processing,
        mock_mark_completed,
    ):
        """Test that fallback is applied during processing pipeline."""
        # Create fake downloaded audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(b"fake wav data")
            tmp_path = Path(tmp.name)

        mock_validate_ssrf.return_value = None
        mock_download.return_value = str(tmp_path)

        # Mock basic metadata extraction (no artist, composer arrives via XMP)
        mock_extract_metadata.return_value = ({
            "artist": "",  # Empty artist
            "title": "Test Track",
            "album": "Test Album",
            "duration": 180.0,
            "format": "wav"
        }, False)

        # Mock XMP enhancement to add composer
        def mock_xmp_enhancement(path, metadata):
            enhanced = metadata.copy()
            enhanced["composer"] = "Bach"  # Add composer via XMP
            enhanced["_xmp_enhanced"] = True
            enhanced["_xmp_fields"] = ["composer"]
            return enhanced

        mock_enhance_xmp.side_effect = mock_xmp_enhancement
        mock_should_attempt_xmp.return_value = True
        mock_should_attempt_bwf.return_value = False
        mock_parse_filename.return_value = None

        # Mock other pipeline components
        mock_extract_artwork.return_value = None
        mock_blob = MagicMock()
        mock_blob.bucket.name = "test-bucket"
        mock_blob.name = "audio/test/test.wav"
        mock_upload_audio.return_value = mock_blob

        # Mock database operations
        mock_save_metadata.return_value = {"id": "test-uuid", "status": "COMPLETED"}

        try:
            # Process audio
            result = await process_audio_complete({
                "source": {
                    "type": "http_url",
                    "url": "https://example.com/test.wav",
                    "filename": "test.wav"
                },
                "options": {"validate_format": False}
            })

            # Verify result
            assert result["success"] is True
            assert result["audio_id"]  # Generated UUID

            # Check that fallback was applied in response
            metadata = result["metadata"]
            product = metadata["product"]
            assert product["artist"] == "Bach"  # Should show composer name
            assert product["title"] == "Test Track"

            # Verify database save was called with fallback-applied artist
            call_args = mock_save_metadata.call_args
            db_metadata = call_args[1]["metadata"]
            assert db_metadata["artist"] == "Bach"  # Fallback applied
            assert db_metadata["composer"] == "Bach"  # Composer preserved

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    @patch('src.resources.metadata.get_audio_metadata_by_id')
    async def test_mcp_resource_uses_fallback(self, mock_get_metadata):
        """Test that MCP resource endpoint returns fallback-applied artist."""
        # URI parser requires a hex/dash audio id
        audio_id = "550e8400-e29b-41d4-a716-446655440000"

        # Mock database to return record with fallback-applied artist
        mock_get_metadata.return_value = {
            "id": audio_id,
            "artist": "Bach",  # Fallback applied in database
            "composer": "Bach",  # Original preserved
            "title": "Test Track",
            "album": "Test Album",
            "genre": "Classical",
            "year": 2025,
            "duration_seconds": 180.0,
            "channels": 2,
            "sample_rate": 44100,
            "bitrate": 0,
            "format": "wav",
            "thumbnail_path": None
        }

        # Test MCP resource retrieval
        from src.resources.metadata import get_metadata_resource

        result = await get_metadata_resource(f"music-library://audio/{audio_id}/metadata")

        # Resource returns an MCP envelope with JSON payload in "text"
        import json
        assert result["mimeType"] == "application/json"
        payload = json.loads(result["text"])

        assert payload["id"] == audio_id
        assert payload["Product"]["Artist"] == "Bach"  # Shows fallback artist
        assert payload["Product"]["Title"] == "Test Track"

    def test_no_fallback_when_artist_exists(self):
        """Test no fallback when artist already exists."""
        from src.metadata.fallback import apply_artist_composer_fallback

        # Test metadata with existing artist
        metadata = {
            "artist": "Berlin Philharmonic",
            "composer": "Bach"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Berlin Philharmonic"  # Artist preserved
        assert result["composer"] == "Bach"

    def test_fallback_edge_cases(self):
        """Test fallback with various edge cases."""
        from src.metadata.fallback import apply_artist_composer_fallback

        test_cases = [
            # (input_artist, input_composer, expected_artist)
            ("", "Bach", "Bach"),                    # Basic fallback
            ("   ", "Beethoven", "Beethoven"),       # Whitespace artist
            (None, "Mozart", "Mozart"),              # None artist
            ("Artist", "Composer", "Artist"),        # No fallback needed
            ("", "", ""),                            # Both empty
            ("", None, ""),                          # No composer
            ("", "   ", ""),                         # Whitespace composer
        ]

        for artist, composer, expected in test_cases:
            metadata = {"artist": artist, "composer": composer}
            result = apply_artist_composer_fallback(metadata)
            assert result["artist"] == expected, f"Failed for artist={artist!r}, composer={composer!r}"
