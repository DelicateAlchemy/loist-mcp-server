"""
Audio format validation using file signatures (magic numbers).

Provides validation beyond file extensions to ensure files are actually
the claimed format and not corrupted or malicious.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class FormatValidationError(Exception):
    """Exception raised when format validation fails."""
    pass


# File magic numbers (signatures) for audio formats
# Format: (offset, signature_bytes, format_name)
AUDIO_SIGNATURES = {
    ".mp3": [
        (0, b'ID3', "MP3 with ID3v2"),  # ID3v2 tag
        (0, b'\xff\xfb', "MP3 (MPEG-1 Layer 3)"),  # MPEG-1 Layer 3
        (0, b'\xff\xf3', "MP3 (MPEG-1 Layer 3)"),  # MPEG-1 Layer 3
        (0, b'\xff\xf2', "MP3 (MPEG-1 Layer 3)"),  # MPEG-1 Layer 3
    ],
    ".flac": [
        (0, b'fLaC', "FLAC"),  # FLAC signature
    ],
    ".wav": [
        (0, b'RIFF', "WAV"),  # RIFF header
        (8, b'WAVE', "WAV"),  # WAVE format
    ],
    ".aif": [
        (0, b'FORM', "AIF"),  # FORM header
        (8, b'AIFF', "AIF"),  # AIFF format
    ],
    ".aiff": [
        (0, b'FORM', "AIFF"),  # FORM header
        (8, b'AIFF', "AIFF"),  # AIFF format
    ],
    ".ogg": [
        (0, b'OggS', "OGG"),  # OGG container
    ],
    ".m4a": [
        (4, b'ftyp', "M4A/MP4"),  # MP4 file type box
    ],
    ".aac": [
        (0, b'\xff\xf1', "AAC (ADTS)"),  # AAC ADTS
        (0, b'\xff\xf9', "AAC (ADTS)"),  # AAC ADTS
    ],
}


class FormatValidator:
    """
    Audio format validator using magic numbers and structure checks.
    
    Validates files beyond extension to detect:
    - Incorrect file extensions
    - Corrupted files
    - Malicious files disguised as audio
    """
    
    @staticmethod
    def read_file_signature(file_path: Path, max_bytes: int = 12) -> bytes:
        """
        Read file signature (magic numbers).
        
        Args:
            file_path: Path to file
            max_bytes: Maximum bytes to read
        
        Returns:
            File signature bytes
        """
        try:
            with open(file_path, 'rb') as f:
                return f.read(max_bytes)
        except Exception as e:
            raise FormatValidationError(f"Could not read file signature: {e}")
    
    @staticmethod
    def validate_signature(file_path: Path | str, expected_format: Optional[str] = None) -> str:
        """
        Validate file signature matches expected audio format.
        
        Args:
            file_path: Path to file
            expected_format: Expected format (e.g., ".mp3"), or None to detect
        
        Returns:
            Detected format extension
        
        Raises:
            FormatValidationError: If signature doesn't match or is invalid
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FormatValidationError(f"File not found: {file_path}")
        
        # Read file signature
        signature = FormatValidator.read_file_signature(file_path)
        
        # If expected format provided, validate against it
        if expected_format:
            expected_format = expected_format if expected_format.startswith('.') else f'.{expected_format}'
            
            if expected_format not in AUDIO_SIGNATURES:
                raise FormatValidationError(f"Unsupported format: {expected_format}")
            
            # Check signatures for expected format
            for offset, sig_bytes, description in AUDIO_SIGNATURES[expected_format]:
                if len(signature) > offset and signature[offset:offset+len(sig_bytes)] == sig_bytes:
                    logger.debug(f"File signature validated: {description}")
                    return expected_format
            
            raise FormatValidationError(
                f"File signature does not match {expected_format} format. "
                f"File may be corrupted or have incorrect extension."
            )
        
        # Auto-detect format from signature
        for ext, signatures in AUDIO_SIGNATURES.items():
            for offset, sig_bytes, description in signatures:
                if len(signature) > offset and signature[offset:offset+len(sig_bytes)] == sig_bytes:
                    logger.info(f"Detected format: {description} ({ext})")
                    return ext
        
        raise FormatValidationError(
            f"Unknown or unsupported audio format. "
            f"File signature: {signature[:8].hex()}"
        )
    
    @staticmethod
    def validate_file(file_path: Path | str) -> Dict[str, any]:
        """
        Comprehensive file validation.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary with validation results
        
        Raises:
            FormatValidationError: If validation fails
        """
        file_path = Path(file_path)
        
        # Check file exists
        if not file_path.exists():
            raise FormatValidationError(f"File not found: {file_path}")
        
        # Check file size (should be > 0)
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise FormatValidationError("File is empty")
        
        # Check file extension
        extension = file_path.suffix.lower()
        if extension not in AUDIO_SIGNATURES:
            raise FormatValidationError(
                f"Unsupported file extension: {extension}. "
                f"Supported: {', '.join(AUDIO_SIGNATURES.keys())}"
            )
        
        # Validate signature
        detected_format = FormatValidator.validate_signature(file_path, extension)
        
        return {
            "valid": True,
            "extension": extension,
            "detected_format": detected_format,
            "file_size": file_size,
            "matches_extension": detected_format == extension,
        }
    
    @staticmethod
    def is_supported_format(file_path: Path | str) -> bool:
        """
        Check if file format is supported (extension-based).
        
        Args:
            file_path: Path to file
        
        Returns:
            True if format is supported
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        return extension in AUDIO_SIGNATURES
    
    @staticmethod
    def detect_format(file_path: Path | str) -> Optional[str]:
        """
        Detect audio format from file signature.
        
        Args:
            file_path: Path to file
        
        Returns:
            Detected format extension or None
        """
        try:
            return FormatValidator.validate_signature(file_path)
        except FormatValidationError:
            return None


def validate_audio_format(file_path: Path | str) -> Dict[str, any]:
    """
    Validate audio file format.
    
    Convenience function for format validation.
    
    Args:
        file_path: Path to audio file
    
    Returns:
        Validation results dictionary
    
    Raises:
        FormatValidationError: If validation fails
    
    Example:
        >>> from src.metadata.format_validator import validate_audio_format
        >>> result = validate_audio_format("song.mp3")
        >>> print(f"Valid: {result['valid']}, Format: {result['detected_format']}")
    """
    return FormatValidator.validate_file(file_path)

