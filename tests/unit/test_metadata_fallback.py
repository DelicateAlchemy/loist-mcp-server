"""
Unit tests for metadata fallback logic.

Tests the composer→artist fallback functionality in various scenarios.
"""

import pytest
from src.metadata.fallback import apply_artist_composer_fallback


class TestArtistComposerFallback:
    """Test cases for composer→artist fallback logic."""

    def test_composer_fallback_to_artist(self):
        """Test basic composer→artist fallback when artist is empty."""
        metadata = {
            "artist": "",
            "composer": "Bach"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Bach"
        assert result["composer"] == "Bach"
        assert metadata["artist"] == ""  # Original dict unchanged

    def test_artist_takes_priority(self):
        """Test that artist field takes priority when both are present."""
        metadata = {
            "artist": "Berlin Philharmonic",
            "composer": "Bach"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Berlin Philharmonic"  # Artist preserved
        assert result["composer"] == "Bach"

    def test_no_fallback_when_artist_present(self):
        """Test no fallback when artist is already populated."""
        metadata = {
            "artist": "Mozart",
            "composer": ""
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Mozart"  # Artist preserved
        assert result["composer"] == ""

    def test_both_fields_present_different(self):
        """Test no fallback when both artist and composer exist and are different."""
        metadata = {
            "artist": "Artist Name",
            "composer": "Composer Name"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Artist Name"  # Artist preserved
        assert result["composer"] == "Composer Name"

    def test_whitespace_artist_fallback(self):
        """Test fallback when artist is whitespace-only."""
        metadata = {
            "artist": "   ",
            "composer": "Beethoven"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Beethoven"
        assert result["composer"] == "Beethoven"

    def test_none_artist_fallback(self):
        """Test fallback when artist is None."""
        metadata = {
            "artist": None,
            "composer": "Mozart"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Mozart"
        assert result["composer"] == "Mozart"

    def test_empty_composer_no_fallback(self):
        """Test no fallback when composer is empty."""
        metadata = {
            "artist": "",
            "composer": ""
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == ""  # No change
        assert result["composer"] == ""

    def test_whitespace_composer_no_fallback(self):
        """Test no fallback when composer is whitespace-only."""
        metadata = {
            "artist": "",
            "composer": "   "
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == ""  # No change
        assert result["composer"] == "   "

    def test_none_composer_no_fallback(self):
        """Test no fallback when composer is None."""
        metadata = {
            "artist": "",
            "composer": None
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == ""  # No change
        assert result["composer"] is None

    def test_immutable_input_dict(self):
        """Test that input dictionary is not mutated."""
        original_metadata = {
            "artist": "",
            "composer": "Bach"
        }
        original_artist = original_metadata["artist"]

        result = apply_artist_composer_fallback(original_metadata)

        assert original_metadata["artist"] == original_artist  # Unchanged
        assert result["artist"] == "Bach"  # New dict has fallback

    def test_composer_preserved_after_fallback(self):
        """Test that composer field is preserved after fallback."""
        metadata = {
            "artist": "",
            "composer": "Bach"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Bach"
        assert result["composer"] == "Bach"  # Original preserved

    def test_strip_composer_whitespace(self):
        """Test that composer whitespace is stripped when applied to artist."""
        metadata = {
            "artist": "",
            "composer": "  Bach  "
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Bach"  # Stripped
        assert result["composer"] == "  Bach  "  # Original preserved

    def test_other_fields_unchanged(self):
        """Test that other metadata fields are unchanged."""
        metadata = {
            "artist": "",
            "composer": "Bach",
            "title": "Brandenburg Concerto",
            "album": "Classical Collection",
            "genre": "Classical"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Bach"
        assert result["title"] == "Brandenburg Concerto"
        assert result["album"] == "Classical Collection"
        assert result["genre"] == "Classical"

    def test_empty_metadata_dict(self):
        """Test handling of empty metadata dictionary."""
        metadata = {}
        result = apply_artist_composer_fallback(metadata)

        assert result == {}  # No change

    def test_missing_artist_field(self):
        """Test handling when artist field is missing."""
        metadata = {
            "composer": "Bach"
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == "Bach"
        assert result["composer"] == "Bach"

    def test_missing_composer_field(self):
        """Test handling when composer field is missing."""
        metadata = {
            "artist": ""
        }
        result = apply_artist_composer_fallback(metadata)

        assert result["artist"] == ""  # No change
        assert "composer" not in result
