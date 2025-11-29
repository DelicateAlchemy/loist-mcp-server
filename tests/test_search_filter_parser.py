"""
Tests for RSQL filter parser and cursor utilities.
"""

import pytest
from src.tools.search_filter_parser import (
    parse_rsql_filter,
    encode_cursor,
    decode_cursor,
    parse_field_selection,
    apply_field_selection,
    RSQLParseError,
    FilterOperator,
    FilterField,
)


class TestRSQLParsing:
    """Test RSQL filter parsing functionality"""

    def test_parse_simple_equality(self):
        """Test parsing simple equality filter"""
        result = parse_rsql_filter("genre==Rock")
        assert result == {"genre_filter": "Rock"}

    def test_parse_year_range(self):
        """Test parsing year range filters"""
        result = parse_rsql_filter("year>=1960,year<=1980")
        assert result == {"year_min": 1960, "year_max": 1980}

    def test_parse_combined_filters(self):
        """Test parsing combined AND filters"""
        result = parse_rsql_filter("genre==Rock;year>=1960,year<=1980")
        assert result == {
            "genre_filter": "Rock",
            "year_min": 1960,
            "year_max": 1980
        }

    def test_parse_format_filter(self):
        """Test parsing format filter"""
        result = parse_rsql_filter("format==MP3")
        assert result == {"format_filter": "MP3"}

    def test_parse_complex_filter(self):
        """Test parsing complex multi-clause filter"""
        result = parse_rsql_filter("genre==Rock;year>=1960,year<=1980;format==MP3")
        expected = {
            "genre_filter": "Rock",
            "year_min": 1960,
            "year_max": 1980,
            "format_filter": "MP3"
        }
        assert result == expected

    def test_parse_empty_filter(self):
        """Test parsing empty filter"""
        result = parse_rsql_filter("")
        assert result == {}

    def test_parse_none_filter(self):
        """Test parsing None filter"""
        result = parse_rsql_filter(None)
        assert result == {}

    def test_parse_invalid_operator(self):
        """Test parsing filter with invalid operator"""
        with pytest.raises(RSQLParseError):
            parse_rsql_filter("genre=Rock")  # Missing second =

    def test_parse_invalid_field(self):
        """Test parsing filter with invalid field"""
        with pytest.raises(RSQLParseError):
            parse_rsql_filter("invalid_field==value")

    def test_parse_invalid_year_value(self):
        """Test parsing filter with invalid year value"""
        with pytest.raises(RSQLParseError):
            parse_rsql_filter("year==not_a_number")


class TestCursorEncoding:
    """Test cursor encoding/decoding functionality"""

    def test_encode_decode_cursor(self):
        """Test round-trip cursor encoding/decoding"""
        score = 0.95
        created_at = "2024-01-01T12:00:00Z"
        track_id = "550e8400-e29b-41d4-a716-446655440000"

        # Encode
        cursor = encode_cursor(score, created_at, track_id)
        assert isinstance(cursor, str)

        # Decode
        decoded_score, decoded_created_at, decoded_id = decode_cursor(cursor)
        assert decoded_score == score
        assert decoded_created_at == created_at
        assert decoded_id == track_id

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor"""
        with pytest.raises(ValueError):
            decode_cursor("invalid-cursor-string")

    def test_decode_malformed_cursor(self):
        """Test decoding malformed cursor data"""
        with pytest.raises(ValueError):
            decode_cursor("eyJpbnZhbGlkX2pzb24iOnRydWV9")  # Invalid JSON structure


class TestFieldSelection:
    """Test field selection functionality"""

    def test_parse_field_selection(self):
        """Test parsing comma-separated field list"""
        fields = parse_field_selection("id,title,score,artist")
        assert fields == ["id", "title", "score", "artist"]

    def test_parse_empty_field_selection(self):
        """Test parsing empty field selection"""
        fields = parse_field_selection("")
        assert fields == []

    def test_parse_none_field_selection(self):
        """Test parsing None field selection"""
        fields = parse_field_selection(None)
        assert fields == []

    def test_apply_field_selection(self):
        """Test applying field selection to result data"""
        full_data = {
            "audioId": "123",
            "metadata": {"title": "Song", "artist": "Artist"},
            "score": 0.9,
            "extra_field": "should be removed"
        }

        filtered = apply_field_selection(full_data, ["audioId", "score"])
        expected = {
            "audioId": "123",
            "score": 0.9
        }
        assert filtered == expected

    def test_apply_empty_field_selection(self):
        """Test applying empty field selection"""
        full_data = {"audioId": "123", "score": 0.9}
        filtered = apply_field_selection(full_data, [])
        assert filtered == full_data


class TestFilterValidation:
    """Test filter validation logic"""

    def test_supported_fields(self):
        """Test that supported fields are recognized"""
        # These should not raise exceptions
        parse_rsql_filter("genre==Rock")
        parse_rsql_filter("year>=1960")
        parse_rsql_filter("duration>=180")
        parse_rsql_filter("format==MP3")
        parse_rsql_filter("artist=like=*beatles*")
        parse_rsql_filter("album=like=*white*")

    def test_like_operator(self):
        """Test LIKE operator parsing"""
        result = parse_rsql_filter("artist=like=*beatles*")
        assert result == {"artist_like": "*beatles*"}

    def test_greater_less_operators(self):
        """Test > and < operators"""
        result = parse_rsql_filter("year>1960,year<1980")
        assert result == {"year_min": 1960, "year_max": 1980}

    def test_greater_equal_less_equal_operators(self):
        """Test >= and <= operators"""
        result = parse_rsql_filter("duration>=180,duration<=300")
        assert result == {"duration_min": 180, "duration_max": 300}
