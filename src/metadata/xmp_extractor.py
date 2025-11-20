"""
XMP metadata extraction using PyExifTool.

Provides extraction of XMP metadata from audio files, with special focus on
WAV and BWF (Broadcast Wave Format) files that may contain rich music metadata.

Supports custom XMP schemas and arbitrary fields while maintaining a flat
structure for music-related metadata (composer, publisher, record_label, isrc).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

try:
    import exiftool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False
    exiftool = None

logger = logging.getLogger(__name__)


class XMPExtractionError(Exception):
    """Exception raised when XMP extraction fails."""
    pass


class XMPExtractor:
    """
    Extract XMP metadata from audio files using PyExifTool.

    Focuses on WAV and BWF files which commonly contain rich XMP metadata
    from professional music production tools (Adobe Audition, Pro Tools, etc.).
    """

    # Supported formats for XMP extraction
    SUPPORTED_FORMATS = {".wav", ".bwf", ".aif", ".aiff"}

    # XMP field mappings for music metadata
    # Maps XMP field names to internal field names
    MUSIC_FIELD_MAPPINGS = {
        # Standard XMP fields
        'XMP:Artist': 'artist',
        'XMP:Title': 'title',
        'XMP:Album': 'album',
        'XMP:Genre': 'genre',
        'XMP:ReleaseDate': 'year',
        'XMP:CreateDate': 'year',
        'XMP:ModifyDate': 'year',

        # Music-specific XMP fields
        'XMP:Composer': 'composer',
        'XMP:Publisher': 'publisher',
        'XMP:Label': 'record_label',
        'XMP:RecordLabel': 'record_label',
        'XMP:ISRC': 'isrc',
        'XMP:Copyright': 'copyright',
        'XMP:Rights': 'copyright',
        'XMP:Comment': 'comment',
        'XMP:Description': 'comment',

        # BWF (Broadcast Wave Format) specific fields
        'XMP:BWF:Originator': 'originator',
        'XMP:BWF:OriginatorReference': 'originator_reference',
        'XMP:BWF:Description': 'description',
        'XMP:BWF:OriginationDate': 'origination_date',
        'XMP:BWF:OriginationTime': 'origination_time',

        # iXML fields (common in WAV files from audio interfaces)
        'XMP:IXML:Scene': 'scene',
        'XMP:IXML:Take': 'take',
        'XMP:IXML:Note': 'note',
    }

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if XMP extraction is available.

        Returns:
            True if PyExifTool and exiftool binary are available.
        """
        if not EXIFTOOL_AVAILABLE:
            return False

        try:
            # Test exiftool availability
            with exiftool.ExifTool() as et:
                return True
        except Exception:
            return False

    @classmethod
    def should_attempt_extraction(cls, file_path: Path | str, existing_metadata: Dict[str, Any]) -> bool:
        """
        Determine if XMP extraction is worth attempting.

        Args:
            file_path: Path to the audio file
            existing_metadata: Metadata already extracted by other methods

        Returns:
            True if XMP extraction should be attempted
        """
        file_path = Path(file_path)

        # Only attempt for supported formats
        if file_path.suffix.lower() not in cls.SUPPORTED_FORMATS:
            return False

        # Check if we have minimal existing metadata (indicating potential for enhancement)
        essential_fields = ['artist', 'title', 'album']
        present_essential = sum(1 for field in essential_fields
                              if existing_metadata.get(field))

        # Attempt if we have less than 2 essential fields
        # This indicates the file might benefit from XMP enhancement
        return present_essential < 2

    @classmethod
    @contextmanager
    def get_exiftool_instance(cls):
        """
        Context manager for ExifTool instance.

        Ensures proper cleanup and error handling.
        """
        if not cls.is_available():
            raise XMPExtractionError("PyExifTool not available")

        et = None
        try:
            et = exiftool.ExifTool()
            et.run()  # Start the ExifTool process
            yield et
        finally:
            if et:
                try:
                    et.terminate()
                except Exception:
                    pass  # Best effort cleanup

    @classmethod
    def extract_xmp_metadata(cls, file_path: Path | str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Extract XMP metadata from an audio file.

        Args:
            file_path: Path to the audio file
            timeout: Timeout in seconds for the extraction

        Returns:
            Dictionary of extracted XMP metadata, or None if extraction fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.debug(f"File not found for XMP extraction: {file_path}")
            return None

        if not cls.is_available():
            logger.debug("PyExifTool not available for XMP extraction")
            return None

        try:
            with cls.get_exiftool_instance() as et:
                # Extract metadata with XMP focus using execute_json
                metadata_list = et.execute_json('-xmp:all', str(file_path))

                if not metadata_list or len(metadata_list) == 0:
                    logger.debug(f"No metadata found in {file_path.name}")
                    return None

                metadata = metadata_list[0]  # Get first result

                # Extract XMP fields
                xmp_data = cls._extract_xmp_fields(metadata)

                if xmp_data:
                    logger.info(f"Extracted XMP metadata from {file_path.name}: {list(xmp_data.keys())}")
                    return xmp_data
                else:
                    logger.debug(f"No XMP data found in {file_path.name}")
                    return None

        except Exception as e:
            logger.debug(f"XMP extraction failed for {file_path.name}: {e}")
            return None

    @classmethod
    def _extract_xmp_fields(cls, exiftool_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize XMP fields from ExifTool metadata.

        Args:
            exiftool_metadata: Raw metadata from ExifTool

        Returns:
            Normalized XMP metadata dictionary
        """
        xmp_data = {}

        # Extract mapped fields
        for exif_key, internal_key in cls.MUSIC_FIELD_MAPPINGS.items():
            if exif_key in exiftool_metadata:
                value = exiftool_metadata[exif_key]
                if value and str(value).strip():  # Only non-empty values
                    normalized_value = cls._normalize_field_value(internal_key, value)
                    if normalized_value is not None:
                        xmp_data[internal_key] = normalized_value

        # Extract arbitrary XMP fields (prefixed with XMP:)
        for key, value in exiftool_metadata.items():
            if key.startswith('XMP:') and key not in cls.MUSIC_FIELD_MAPPINGS:
                # Store arbitrary XMP fields with a special prefix
                if value and str(value).strip():
                    # Convert to snake_case and prefix
                    field_name = key.replace('XMP:', '').lower().replace(' ', '_')
                    xmp_data[f'xmp_{field_name}'] = str(value).strip()

        return xmp_data if xmp_data else {}

    @classmethod
    def _normalize_field_value(cls, field_name: str, value: Any) -> Any:
        """
        Normalize a field value based on its type.

        Args:
            field_name: Name of the field
            value: Raw value from ExifTool

        Returns:
            Normalized value
        """
        if not value:
            return None

        # Convert to string and strip whitespace
        str_value = str(value).strip()
        if not str_value:
            return None

        # Field-specific normalization
        if field_name == 'year':
            # Extract year from date strings
            if isinstance(value, str):
                # Handle various date formats
                import re
                year_match = re.search(r'(\d{4})', value)
                if year_match:
                    try:
                        return int(year_match.group(1))
                    except ValueError:
                        pass
            return None

        elif field_name in ['artist', 'title', 'album', 'composer', 'publisher', 'record_label', 'copyright']:
            # Text fields - ensure reasonable length
            if len(str_value) > 500:
                return str_value[:500]  # Truncate very long values
            return str_value

        elif field_name == 'isrc':
            # ISRC codes are typically 12 characters
            # Format: CC-XXX-YY-NNNNN (Country-Code-Year-Number)
            str_value = str_value.upper().replace('-', '').replace(' ', '')
            if len(str_value) == 12 and str_value.isalnum():
                # Reformat as CC-XXX-YY-NNNNN
                return f"{str_value[:2]}-{str_value[2:5]}-{str_value[5:7]}-{str_value[7:]}"
            return str_value

        else:
            # Default: return as string
            return str_value

    @classmethod
    def enhance_metadata_with_xmp(cls, file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance existing metadata with XMP data.

        XMP data takes priority over existing metadata for fields that are present.

        Args:
            file_path: Path to the audio file
            existing_metadata: Existing metadata dictionary

        Returns:
            Enhanced metadata dictionary
        """
        # Create a copy to avoid modifying the original
        enhanced_metadata = existing_metadata.copy()

        # Attempt XMP extraction
        xmp_data = cls.extract_xmp_metadata(file_path)

        if xmp_data:
            # XMP data takes priority - overwrite existing fields
            enhanced_metadata.update(xmp_data)

            # Log what was enhanced
            enhanced_fields = list(xmp_data.keys())
            logger.info(f"Enhanced metadata with XMP data: {enhanced_fields}")

            # Add XMP extraction flag
            enhanced_metadata['_xmp_enhanced'] = True
            enhanced_metadata['_xmp_fields'] = enhanced_fields
        else:
            enhanced_metadata['_xmp_enhanced'] = False

        return enhanced_metadata


# Convenience functions for external use

def extract_xmp_metadata(file_path: Path | str, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Extract XMP metadata from an audio file.

    Args:
        file_path: Path to the audio file
        timeout: Timeout in seconds

    Returns:
        Dictionary of XMP metadata, or None
    """
    return XMPExtractor.extract_xmp_metadata(file_path, timeout)


def enhance_metadata_with_xmp(file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance existing metadata with XMP data.

    Args:
        file_path: Path to the audio file
        existing_metadata: Existing metadata to enhance

    Returns:
        Enhanced metadata dictionary
    """
    return XMPExtractor.enhance_metadata_with_xmp(file_path, existing_metadata)


def is_xmp_available() -> bool:
    """
    Check if XMP extraction is available.

    Returns:
        True if XMP extraction can be performed
    """
    return XMPExtractor.is_available()


def should_attempt_xmp_extraction(file_path: Path | str, existing_metadata: Dict[str, Any]) -> bool:
    """
    Determine if XMP extraction should be attempted.

    Args:
        file_path: Path to the audio file
        existing_metadata: Existing metadata

    Returns:
        True if XMP extraction should be attempted
    """
    return XMPExtractor.should_attempt_extraction(file_path, existing_metadata)
