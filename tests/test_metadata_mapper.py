"""
Unit tests for metadata mapper module.

Tests verify:
- Database field to FFmpeg metadata mapping
- Format-specific metadata handling
- UTF-8 encoding and special character escaping
- Artwork embedding argument generation
- Metadata validation for different formats
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.converter.metadata_mapper import (
    map_metadata_to_ffmpeg_args,
    _escape_metadata_value,
    _get_artwork_ffmpeg_args,
    _get_format_specific_flags,
    get_supported_artwork_formats,
    validate_metadata_for_format,
)


class TestMetadataMapping:
    """Test metadata field mapping to FFmpeg arguments."""

    def test_basic_metadata_mapping(self):
        """Test mapping of basic metadata fields."""
        metadata = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'genre': 'Rock',
            'year': 2024,
        }

        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')

        # Should contain metadata arguments
        assert '-metadata' in args
        assert 'title=Test Song' in args
        assert 'artist=Test Artist' in args
        assert 'album=Test Album' in args
        assert 'genre=Rock' in args
        assert 'date=2024' in args

    def test_empty_metadata_filtering(self):
        """Test that empty metadata fields are filtered out."""
        metadata = {
            'title': 'Test Song',
            'artist': '',  # Empty string
            'album': None,  # None value
            'genre': 'Rock',
        }

        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')

        # Should only include non-empty fields
        assert 'title=Test Song' in args
        assert 'genre=Rock' in args
        # Should not include empty fields
        assert not any('artist=' in arg for arg in args if arg != '-metadata')

    def test_track_number_formatting(self):
        """Test track number formatting."""
        # Test with track number only
        metadata = {'title': 'Song', 'track_number': 5}
        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')
        assert 'track=5' in args

        # Test with track number and total
        metadata = {'title': 'Song', 'track_number': 5, 'total_tracks': 12}
        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')
        assert 'track=5/12' in args

    def test_format_specific_metadata(self):
        """Test format-specific metadata handling."""
        metadata = {
            'title': 'Song',
            'album_artist': 'Album Artist',
        }

        # MP3 should include album_artist
        mp3_args = map_metadata_to_ffmpeg_args(metadata, 'mp3')
        assert 'album_artist=Album Artist' in mp3_args

        # WAV should not include album_artist (not supported in RIFF INFO)
        wav_args = map_metadata_to_ffmpeg_args(metadata, 'wav')
        assert not any('album_artist=' in arg for arg in wav_args)

    def test_utf8_encoding(self):
        """Test UTF-8 character handling."""
        metadata = {
            'title': '歌曲标题',  # Chinese characters
            'artist': 'José García',  # Accented characters
        }

        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')

        # Should preserve UTF-8 characters
        assert 'title=歌曲标题' in args
        assert 'artist=José García' in args

    def test_special_character_escaping(self):
        """Test special character escaping."""
        metadata = {
            'title': 'Song "with" quotes',
            'artist': 'Artist\\with\\backslashes',
        }

        args = map_metadata_to_ffmpeg_args(metadata, 'mp3')

        # Should escape special characters
        assert 'title=Song \\"with\\" quotes' in args
        assert 'artist=Artist\\\\with\\\\backslashes' in args


class TestArtworkEmbedding:
    """Test artwork embedding argument generation."""

    def test_mp3_artwork_args(self):
        """Test MP3 artwork embedding arguments."""
        artwork_path = Path('/tmp/cover.jpg')
        args = _get_artwork_ffmpeg_args('mp3', artwork_path)

        assert '-i' in args
        assert str(artwork_path) in args
        assert '-map' in args
        assert '0:a' in args  # Audio stream
        assert '1:v' in args  # Video stream (artwork)
        assert '-codec:v' in args
        assert 'mjpeg' in args

    def test_aac_artwork_args(self):
        """Test AAC artwork embedding arguments."""
        artwork_path = Path('/tmp/cover.jpg')
        args = _get_artwork_ffmpeg_args('aac', artwork_path)

        assert '-i' in args
        assert str(artwork_path) in args
        assert '-map' in args
        assert '-codec:v' in args
        assert 'mjpeg' in args
        assert '-disposition:v' in args
        assert 'attached_pic' in args

    def test_flac_artwork_args(self):
        """Test FLAC artwork embedding arguments."""
        artwork_path = Path('/tmp/cover.jpg')
        args = _get_artwork_ffmpeg_args('flac', artwork_path)

        assert '-i' in args
        assert str(artwork_path) in args
        assert '-map' in args
        assert '-codec:v' in args
        assert 'mjpeg' in args
        assert '-disposition:v' in args
        assert 'attached_pic' in args

    def test_wav_no_artwork(self):
        """Test that WAV format doesn't get artwork arguments."""
        artwork_path = Path('/tmp/cover.jpg')
        args = _get_artwork_ffmpeg_args('wav', artwork_path)

        # Should return empty list for WAV
        assert args == []

    def test_ogg_artwork_args(self):
        """Test OGG artwork embedding arguments."""
        artwork_path = Path('/tmp/cover.jpg')
        args = _get_artwork_ffmpeg_args('ogg', artwork_path)

        assert '-i' in args
        assert str(artwork_path) in args
        assert '-map' in args
        assert '-codec:v' in args
        assert 'mjpeg' in args
        assert '-disposition:v' in args
        assert 'attached_pic' in args


class TestFormatSpecificFlags:
    """Test format-specific FFmpeg flag generation."""

    def test_mp3_flags(self):
        """Test MP3 format-specific flags."""
        flags = _get_format_specific_flags('mp3')

        assert '-id3v2_version' in flags
        assert '3' in flags
        assert '-write_id3v1' in flags
        assert '1' in flags

    def test_wav_flags(self):
        """Test WAV format-specific flags."""
        flags = _get_format_specific_flags('wav')

        assert '-write_bext' in flags
        assert '1' in flags

    def test_other_formats_flags(self):
        """Test format-specific flags for other formats."""
        # FLAC and OGG don't have special flags
        assert _get_format_specific_flags('flac') == []
        assert _get_format_specific_flags('ogg') == []

        # AAC uses iPod container format
        aac_flags = _get_format_specific_flags('aac')
        assert '-f' in aac_flags
        assert 'ipod' in aac_flags


class TestArtworkFormatSupport:
    """Test artwork format support checking."""

    def test_supported_formats(self):
        """Test formats that support artwork."""
        assert get_supported_artwork_formats('mp3') == True
        assert get_supported_artwork_formats('aac') == True
        assert get_supported_artwork_formats('m4a') == True
        assert get_supported_artwork_formats('flac') == True
        assert get_supported_artwork_formats('ogg') == True

    def test_unsupported_formats(self):
        """Test formats that don't support artwork."""
        assert get_supported_artwork_formats('wav') == False
        assert get_supported_artwork_formats('invalid') == False


class TestMetadataValidation:
    """Test metadata validation for different formats."""

    def test_valid_metadata(self):
        """Test validation of valid metadata."""
        metadata = {
            'title': 'Valid Song',
            'artist': 'Valid Artist',
        }

        warnings = validate_metadata_for_format(metadata, 'mp3')
        assert len(warnings) == 0

    def test_missing_title(self):
        """Test validation with missing title."""
        metadata = {
            'artist': 'Artist',
        }

        warnings = validate_metadata_for_format(metadata, 'mp3')
        assert len(warnings) > 0
        assert any('title' in w.lower() for w in warnings)

    def test_mp3_artist_recommendation(self):
        """Test MP3-specific validation recommendations."""
        metadata = {
            'title': 'Song',
            # No artist or album_artist
        }

        warnings = validate_metadata_for_format(metadata, 'mp3')
        assert len(warnings) > 0

    def test_wav_artist_recommendation(self):
        """Test WAV-specific validation recommendations."""
        metadata = {
            'title': 'Song',
            # No artist
        }

        warnings = validate_metadata_for_format(metadata, 'wav')
        assert len(warnings) > 0


class TestErrorHandling:
    """Test error handling in metadata mapping."""

    def test_missing_title_error(self):
        """Test error when title is missing."""
        metadata = {
            'artist': 'Artist',
            # No title
        }

        with pytest.raises(ValueError, match="Title is required"):
            map_metadata_to_ffmpeg_args(metadata, 'mp3')

    def test_none_metadata_error(self):
        """Test error when metadata is None and no artwork."""
        with pytest.raises(ValueError, match="Metadata dictionary or artwork path is required"):
            map_metadata_to_ffmpeg_args(None, 'mp3')


class TestCharacterEscaping:
    """Test character escaping utilities."""

    def test_escape_quotes(self):
        """Test quote escaping."""
        result = _escape_metadata_value('Song "Title"')
        assert result == 'Song \\"Title\\"'

    def test_escape_backslashes(self):
        """Test backslash escaping."""
        result = _escape_metadata_value('Path\\to\\file')
        assert result == 'Path\\\\to\\\\file'

    def test_escape_mixed_characters(self):
        """Test mixed character escaping."""
        result = _escape_metadata_value('Test "with" \\quotes\\ and \'single\'')
        expected = 'Test \\"with\\" \\\\quotes\\\\ and \\\'single\\\''
        assert result == expected

    def test_no_escaping_needed(self):
        """Test strings that don't need escaping."""
        result = _escape_metadata_value('Simple Song Title')
        assert result == 'Simple Song Title'
