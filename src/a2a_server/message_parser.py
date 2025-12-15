"""
A2A Message Parsing Utilities

Provides utilities to extract audio URLs from A2A Message objects for the Loist Music Library.
Handles both TextPart content with URLs and FilePart references with audio MIME types.

Author: Task Master AI
Created: $(date)
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

# Try to import A2A types, provide fallbacks if not available
try:
    from a2a.types import Message, TextPart, FilePart
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    # Create dummy types for when A2A is not available
    class Message:
        def __init__(self, id=None, role=None, parts=None):
            self.id = id or "dummy"
            self.role = role or "user"
            self.parts = parts or []

    class TextPart:
        def __init__(self, text=""):
            self.text = text

    class FilePart:
        def __init__(self, file=None):
            self.file = file

# Import existing security utilities
from src.downloader.ssrf_protection import validate_ssrf, SSRFProtectionError
from src.downloader.validators import URLValidationError, validate_url

logger = logging.getLogger(__name__)


# URL pattern for audio files (supports common audio formats)
# Matches http/https URLs ending with audio extensions, allowing query params and fragments
AUDIO_URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:mp3|wav|flac|m4a|aac|ogg|wma|opus)(?:\?[^\s<>"{}|\\^`\[\]]*)?(?:#[^\s<>"{}|\\^`\[\]]*)?',
    re.IGNORECASE
)


def extract_audio_url(message: Message) -> Optional[str]:
    """
    Extract audio URL from A2A message parts.

    Checks message parts in order:
    1. FilePart with audio MIME type and URI -> returns the URI
    2. TextPart containing audio URL -> uses regex to extract

    Args:
        message: A2A Message object containing parts to search

    Returns:
        str or None: First valid audio URL found, or None if no URL found

    Note:
        - A2A SDK uses discriminated unions: `Message.parts` contains `Part` wrappers
        - Access actual part via `part.root`
        - `FilePart.file` can be `FileWithUri` (has `uri`) or `FileWithBytes` (has `bytes`)
        - Only `FileWithUri` is supported (inline bytes are skipped)

    Example:
        >>> from a2a.types import Message, TextPart, FilePart, FileWithUri
        >>> file_with_uri = FileWithUri(uri="https://example.com/audio.mp3", mime_type="audio/mpeg")
        >>> msg = Message(message_id="test", role="user", parts=[FilePart(file=file_with_uri)])
        >>> extract_audio_url(msg)
        'https://example.com/audio.mp3'
    """
    if not A2A_AVAILABLE:
        logger.warning("A2A SDK not available, cannot extract audio URL from message")
        return None

    if not message.parts:
        logger.debug("Message has no parts")
        return None

    logger.debug("🔍 Extracting audio URL from message with %d parts", len(message.parts))

    for part in message.parts:
        # A2A SDK uses discriminated unions - access the root object
        actual_part = part.root

        # Check for file parts with audio MIME type
        if isinstance(actual_part, FilePart):
            # FilePart has a 'file' field containing FileWithUri or FileWithBytes
            file_obj = actual_part.file
            
            # Check if this is FileWithUri (has URI) vs FileWithBytes (inline data)
            if not hasattr(file_obj, 'uri'):
                logger.debug("Skipping FilePart with inline bytes (FileWithBytes)")
                continue
            
            # Check MIME type and URI existence
            if file_obj.mime_type and file_obj.mime_type.startswith('audio/') and file_obj.uri:
                logger.info(f"📁 Found audio file: {file_obj.uri} (MIME: {file_obj.mime_type})")
                return file_obj.uri

        # Check text parts for URLs
        elif isinstance(actual_part, TextPart):
            match = AUDIO_URL_PATTERN.search(actual_part.text)
            if match:
                url = match.group(0)
                logger.info(f"📝 Found audio URL in text: {url}")
                return url

    logger.debug("❌ No audio URL found in message")
    return None


def validate_audio_url(url: str) -> None:
    """
    Validate URL is safe to process for audio downloading.

    Performs comprehensive validation:
    - URL format validation (HTTP/HTTPS only)
    - SSRF protection (blocks private IPs, localhost, cloud metadata)
    - Hostname validation

    Args:
        url: URL to validate

    Returns:
        None: Returns nothing if validation passes

    Raises:
        ValueError: If URL is invalid or blocked (with descriptive message)

    Example:
        >>> validate_audio_url("https://example.com/audio.mp3")  # Passes
        >>> validate_audio_url("http://192.168.1.1/audio.mp3")  # Raises ValueError
        ValueError: Invalid or blocked audio URL: Access to private IP address 192.168.1.1 is blocked...
    """
    try:
        # First validate URL format and scheme
        validated_url = validate_url(url, normalize=True)

        # Then check for SSRF vulnerabilities
        validate_ssrf(validated_url, check_dns=True)

        logger.info(f"✅ Audio URL validated: {validated_url}")

    except (URLValidationError, SSRFProtectionError) as e:
        logger.warning(f"❌ Audio URL validation failed: {e}")
        raise ValueError(f"Invalid or blocked audio URL: {e}") from e
    except Exception as e:
        logger.error(f"❌ Unexpected error validating audio URL: {e}")
        raise ValueError(f"Failed to validate audio URL: {e}") from e


def is_audio_url(url: str) -> bool:
    """
    Check if URL points to an audio file based on file extension.

    Args:
        url: URL to check

    Returns:
        bool: True if URL has audio file extension

    Example:
        >>> is_audio_url("https://example.com/song.mp3")
        True
        >>> is_audio_url("https://example.com/document.pdf")
        False
    """
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Check for audio file extensions
    audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.opus'}
    return any(path.endswith(ext) for ext in audio_extensions)
