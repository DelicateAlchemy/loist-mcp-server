"""
Unit tests for download filename generation and sanitization.

Tests the core filename logic used in download operations, including:
- Original filename preservation
- Fallback to metadata-based names
- Filename sanitization and safety
"""

import pytest
from src.tools.download_tool import _sanitize_filename_component, _generate_download_filename


class TestSanitizeFilenameComponent:
    """Test filename component sanitization."""

    def test_normal_filename(self):
        """Test sanitization of normal filenames."""
        result = _sanitize_filename_component("normal_filename.mp3")
        assert result == "normal_filename.mp3"

    def test_unsafe_characters(self):
        """Test replacement of unsafe characters."""
        result = _sanitize_filename_component('file:with<>colons"and|symbols?.mp3')
        assert result == "file_with__colons_and_symbols_.mp3"

    def test_backslashes(self):
        """Test backslash replacement."""
        result = _sanitize_filename_component(r"file\with\backslashes.mp3")
        assert result == "file_with_backslashes.mp3"

    def test_length_limiting(self):
        """Test length truncation."""
        long_name = "a" * 150
        result = _sanitize_filename_component(long_name)
        assert len(result) == 100
        assert result == "a" * 100

    def test_custom_length_limit(self):
        """Test custom length limits."""
        result = _sanitize_filename_component("very_long_filename_" + "x" * 50, max_length=20)
        assert len(result) == 20
        assert result == "very_long_filename_x"  # Truncated to 20 chars

    def test_empty_input(self):
        """Test handling of empty/whitespace input."""
        assert _sanitize_filename_component("") is None
        assert _sanitize_filename_component("   ") is None
        assert _sanitize_filename_component(None) is None

    def test_preserve_unicode(self):
        """Test that Unicode characters are preserved."""
        result = _sanitize_filename_component("file_ñáéíóú.mp3")
        assert result == "file_ñáéíóú.mp3"

    def test_trailing_unsafe_chars(self):
        """Test handling of unsafe chars at string boundaries."""
        result = _sanitize_filename_component("<start>middle?end>")
        assert result == "_start_middle_end_"


class TestGenerateDownloadFilename:
    """Test download filename generation with priority logic."""

    def test_original_filename_priority(self):
        """Test that original_filename takes priority over metadata."""
        metadata = {
            'title': 'Ignored Title',
            'artist': 'Ignored Artist',
            'original_filename': 'my-song.mp3'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'my-song.mp3'

    def test_original_filename_with_format_conversion(self):
        """Test original_filename with format conversion changes extension."""
        metadata = {
            'original_filename': 'song.wav'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'song.mp3'

    def test_original_filename_aac_to_m4a(self):
        """Test AAC format conversion to m4a extension."""
        metadata = {
            'original_filename': 'song.wav'
        }
        result = _generate_download_filename(metadata, 'aac')
        assert result == 'song.m4a'

    def test_original_filename_sanitization(self):
        """Test that original_filename gets sanitized."""
        metadata = {
            'original_filename': 'unsafe<file>name?.wav'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'unsafe_file_name_.mp3'

    def test_original_filename_empty_fallback(self):
        """Test fallback when original_filename is empty."""
        metadata = {
            'title': 'Test Title',
            'artist': 'Test Artist',
            'original_filename': ''
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'Test Title - Test Artist.mp3'

    def test_original_filename_none_fallback(self):
        """Test fallback when original_filename is None."""
        metadata = {
            'title': 'Test Title',
            'artist': 'Test Artist',
            'original_filename': None
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'Test Title - Test Artist.mp3'

    def test_metadata_fallback_basic(self):
        """Test basic metadata fallback."""
        metadata = {
            'title': 'My Song',
            'artist': 'My Artist'
        }
        result = _generate_download_filename(metadata, 'flac')
        assert result == 'My Song - My Artist.flac'

    def test_metadata_fallback_missing_artist(self):
        """Test fallback with missing artist."""
        metadata = {
            'title': 'My Song'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'My Song - Unknown Artist.mp3'

    def test_metadata_fallback_missing_title(self):
        """Test fallback with missing title."""
        metadata = {
            'artist': 'My Artist'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'Unknown - My Artist.mp3'

    def test_metadata_fallback_empty_fields(self):
        """Test fallback with empty title/artist."""
        metadata = {
            'title': '',
            'artist': ''
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'Unknown - Unknown Artist.mp3'

    def test_metadata_sanitization(self):
        """Test that metadata fields get sanitized."""
        metadata = {
            'title': 'Song:with<>symbols?',
            'artist': 'Artist|with"bad<chars'
        }
        result = _generate_download_filename(metadata, 'mp3')
        assert result == 'Song_with__symbols_ - Artist_with_bad_chars.mp3'

    def test_metadata_length_limits(self):
        """Test length limits on metadata fields."""
        metadata = {
            'title': 'a' * 150,  # Should be truncated to 100
            'artist': 'b' * 100  # Should be truncated to 50
        }
        result = _generate_download_filename(metadata, 'mp3')
        title_part, artist_part = result.split(' - ')
        assert len(title_part) == 100
        assert len(artist_part) == 50 + 4  # + '.mp3'

    def test_none_metadata(self):
        """Test handling of None metadata."""
        result = _generate_download_filename(None, 'mp3')
        assert result == 'Unknown_Unknown_Artist.unknown'

    def test_original_filename_stem_extraction(self):
        """Test that only the stem is used from original_filename."""
        metadata = {
            'original_filename': 'path/to/song.mp3'
        }
        result = _generate_download_filename(metadata, 'flac')
        assert result == 'song.flac'

    def test_original_filename_with_unsafe_chars(self):
        """Test original filename with unsafe characters gets sanitized."""
        metadata = {
            'title': 'Fallback Title',
            'artist': 'Fallback Artist',
            'original_filename': 'song<>with?bad:chars.mp3'
        }
        result = _generate_download_filename(metadata, 'flac')
        assert result == 'song__with_bad_chars.flac'
