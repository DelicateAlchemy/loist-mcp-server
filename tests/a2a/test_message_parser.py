"""
Unit tests for A2A message parsing utilities.

Tests audio URL extraction from A2A Message objects, including:
- FilePart extraction with FileWithUri
- FilePart handling with FileWithBytes (should skip)
- TextPart extraction with various URL formats
- Priority handling (FilePart before TextPart)
- Security validation (SSRF protection)
"""

import pytest

# Try to import a2a types, skip tests if not available
try:
    from a2a.types import Message, TextPart, FilePart, FileWithUri, FileWithBytes
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    # Create dummy types for pytest collection
    Message = None
    TextPart = None
    FilePart = None
    FileWithUri = None
    FileWithBytes = None

from src.a2a_server.message_parser import (
    extract_audio_url,
    validate_audio_url,
    is_audio_url,
    AUDIO_URL_PATTERN,
)


@pytest.fixture(scope="module", autouse=True)
def check_a2a_available():
    """Skip all tests if A2A SDK is not available."""
    if not A2A_AVAILABLE:
        pytest.skip("A2A SDK not available (a2a-sdk package not installed)")


class TestExtractAudioUrl:
    """Tests for extract_audio_url() function."""

    def test_filepart_with_filewithuri_audio_mime(self):
        """Test FilePart with FileWithUri and audio MIME type."""
        file_with_uri = FileWithUri(
            uri="https://example.com/song.mp3",
            mime_type="audio/mpeg"
        )
        file_part = FilePart(file=file_with_uri)
        msg = Message(
            message_id="test-1",
            role="user",
            parts=[file_part]
        )

        result = extract_audio_url(msg)
        assert result == "https://example.com/song.mp3"

    def test_filepart_with_filewithuri_various_audio_mimes(self):
        """Test FilePart with various audio MIME types."""
        audio_mimes = [
            ("audio/mpeg", "https://example.com/song.mp3"),
            ("audio/wav", "https://example.com/song.wav"),
            ("audio/x-flac", "https://example.com/song.flac"),
            ("audio/mp4", "https://example.com/song.m4a"),
            ("audio/aac", "https://example.com/song.aac"),
            ("audio/ogg", "https://example.com/song.ogg"),
        ]

        for mime_type, uri in audio_mimes:
            file_with_uri = FileWithUri(uri=uri, mime_type=mime_type)
            file_part = FilePart(file=file_with_uri)
            msg = Message(
                message_id=f"test-{mime_type}",
                role="user",
                parts=[file_part]
            )

            result = extract_audio_url(msg)
            assert result == uri, f"Failed for MIME type: {mime_type}"

    def test_filepart_with_filewithbytes_skipped(self):
        """Test FilePart with FileWithBytes (inline data) is skipped."""
        file_with_bytes = FileWithBytes(
            bytes="base64encodeddata",
            mime_type="audio/mpeg"
        )
        file_part = FilePart(file=file_with_bytes)
        msg = Message(
            message_id="test-bytes",
            role="user",
            parts=[file_part]
        )

        result = extract_audio_url(msg)
        assert result is None, "FileWithBytes should be skipped (no URI)"

    def test_filepart_with_non_audio_mime_skipped(self):
        """Test FilePart with non-audio MIME type is skipped."""
        file_with_uri = FileWithUri(
            uri="https://example.com/document.pdf",
            mime_type="application/pdf"
        )
        file_part = FilePart(file=file_with_uri)
        msg = Message(
            message_id="test-pdf",
            role="user",
            parts=[file_part]
        )

        result = extract_audio_url(msg)
        assert result is None, "Non-audio MIME types should be skipped"

    def test_textpart_with_audio_url_extracted(self):
        """Test TextPart containing audio URL is extracted."""
        text_part = TextPart(text="Listen to this: https://example.com/song.wav")
        msg = Message(
            message_id="test-text",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result == "https://example.com/song.wav"

    def test_textpart_with_multiple_urls_returns_first(self):
        """Test TextPart with multiple URLs returns first match."""
        text_part = TextPart(
            text="Check these: https://example.com/first.mp3 and https://example.com/second.wav"
        )
        msg = Message(
            message_id="test-multiple",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result == "https://example.com/first.mp3"

    def test_textpart_with_non_audio_url_skipped(self):
        """Test TextPart with non-audio URL is skipped."""
        text_part = TextPart(text="See this document: https://example.com/doc.pdf")
        msg = Message(
            message_id="test-non-audio",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result is None

    def test_priority_filepart_before_textpart(self):
        """Test that FilePart URL is returned before TextPart URL."""
        file_with_uri = FileWithUri(
            uri="https://example.com/file-audio.mp3",
            mime_type="audio/mpeg"
        )
        file_part = FilePart(file=file_with_uri)
        text_part = TextPart(text="Also check: https://example.com/text-audio.wav")

        msg = Message(
            message_id="test-priority",
            role="user",
            parts=[file_part, text_part]
        )

        result = extract_audio_url(msg)
        assert result == "https://example.com/file-audio.mp3"

    def test_empty_message_parts_returns_none(self):
        """Test message with empty parts returns None."""
        msg = Message(
            message_id="test-empty",
            role="user",
            parts=[]
        )

        result = extract_audio_url(msg)
        assert result is None

    def test_no_audio_urls_returns_none(self):
        """Test message with no audio URLs returns None."""
        text_part = TextPart(text="Just some text without any URLs")
        msg = Message(
            message_id="test-no-urls",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result is None

    def test_textpart_url_with_query_params(self):
        """Test TextPart with URL containing query parameters."""
        text_part = TextPart(
            text="Download: https://example.com/audio.mp3?token=abc123&expires=2025"
        )
        msg = Message(
            message_id="test-query",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result is not None
        assert "example.com/audio.mp3" in result

    def test_textpart_url_with_fragment(self):
        """Test TextPart with URL containing fragment."""
        text_part = TextPart(
            text="Play from: https://example.com/audio.mp3#t=30"
        )
        msg = Message(
            message_id="test-fragment",
            role="user",
            parts=[text_part]
        )

        result = extract_audio_url(msg)
        assert result is not None
        assert "example.com/audio.mp3" in result


class TestValidateAudioUrl:
    """Tests for validate_audio_url() function."""

    def test_valid_https_url_passes(self):
        """Test valid HTTPS URL passes validation."""
        validate_audio_url("https://example.com/audio.mp3")
        # Should not raise

    def test_valid_http_url_passes(self):
        """Test valid HTTP URL passes validation."""
        validate_audio_url("http://example.com/audio.wav")
        # Should not raise

    def test_private_ip_raises_valueerror(self):
        """Test private IP addresses raise ValueError."""
        with pytest.raises(ValueError, match="private IP|blocked"):
            validate_audio_url("http://192.168.1.1/audio.mp3")

    def test_localhost_raises_valueerror(self):
        """Test localhost addresses raise ValueError."""
        with pytest.raises(ValueError, match="private IP|blocked|localhost"):
            validate_audio_url("http://127.0.0.1/audio.mp3")

    def test_file_scheme_raises_valueerror(self):
        """Test file:// scheme raises ValueError."""
        with pytest.raises(ValueError, match="Invalid or blocked|scheme"):
            validate_audio_url("file:///path/to/audio.mp3")

    def test_empty_url_raises_valueerror(self):
        """Test empty URL raises ValueError."""
        with pytest.raises(ValueError):
            validate_audio_url("")

    def test_invalid_url_format_raises_valueerror(self):
        """Test invalid URL format raises ValueError."""
        with pytest.raises(ValueError):
            validate_audio_url("not-a-valid-url")


class TestIsAudioUrl:
    """Tests for is_audio_url() helper function."""

    def test_mp3_url_returns_true(self):
        """Test MP3 URL returns True."""
        assert is_audio_url("https://example.com/song.mp3") is True

    def test_wav_url_returns_true(self):
        """Test WAV URL returns True."""
        assert is_audio_url("https://example.com/song.wav") is True

    def test_flac_url_returns_true(self):
        """Test FLAC URL returns True."""
        assert is_audio_url("https://example.com/song.flac") is True

    def test_pdf_url_returns_false(self):
        """Test PDF URL returns False."""
        assert is_audio_url("https://example.com/document.pdf") is False

    def test_url_without_extension_returns_false(self):
        """Test URL without extension returns False."""
        assert is_audio_url("https://example.com/file") is False

    def test_case_insensitive_extension(self):
        """Test case-insensitive extension matching."""
        assert is_audio_url("https://example.com/song.MP3") is True
        assert is_audio_url("https://example.com/song.WAV") is True


class TestAudioUrlPattern:
    """Tests for AUDIO_URL_PATTERN regex."""

    def test_pattern_matches_mp3_url(self):
        """Test pattern matches MP3 URL."""
        url = "https://example.com/song.mp3"
        match = AUDIO_URL_PATTERN.search(url)
        assert match is not None
        assert match.group(0) == url

    def test_pattern_matches_url_with_query_params(self):
        """Test pattern matches URL with query parameters."""
        url = "https://example.com/audio.mp3?token=abc&expires=2025"
        match = AUDIO_URL_PATTERN.search(url)
        assert match is not None
        assert "audio.mp3" in match.group(0)

    def test_pattern_matches_url_with_fragment(self):
        """Test pattern matches URL with fragment."""
        url = "https://example.com/audio.mp3#t=30"
        match = AUDIO_URL_PATTERN.search(url)
        assert match is not None
        assert "audio.mp3" in match.group(0)

    def test_pattern_does_not_match_pdf(self):
        """Test pattern does not match PDF URL."""
        url = "https://example.com/document.pdf"
        match = AUDIO_URL_PATTERN.search(url)
        assert match is None

    def test_pattern_case_insensitive(self):
        """Test pattern is case-insensitive."""
        url = "https://example.com/song.MP3"
        match = AUDIO_URL_PATTERN.search(url)
        assert match is not None

