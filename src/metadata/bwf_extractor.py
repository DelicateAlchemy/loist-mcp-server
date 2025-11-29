"""
BWF (Broadcast Wave Format) metadata extraction using PyExifTool.

Provides extraction of BWF metadata from WAV files, with special focus on
professional audio files that contain rich BWF metadata from recording studios,
audio interfaces, and production tools.

Supports BWF fields like Originator, OriginatorReference, Description,
OriginationDate, OriginationTime, and embedded iXML metadata.
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


class BWFExtractionError(Exception):
    """Exception raised when BWF extraction fails."""
    pass


class BWFExtractor:
    """
    Extract BWF (Broadcast Wave Format) metadata from WAV files using PyExifTool.

    Focuses on professional WAV files that commonly contain rich BWF metadata
    from recording studios, audio interfaces, and production tools.
    """

    # Supported formats for BWF extraction
    SUPPORTED_FORMATS = {".wav", ".bwf"}

    # BWF field mappings for music metadata
    # Maps ExifTool field names to internal field names
    # Includes both standard metadata fields and BWF-specific fields
    BWF_FIELD_MAPPINGS = {
        # Standard music metadata fields (found in BWF WAV files)
        # PyExifTool prefixes WAV fields with RIFF:
        'RIFF:Artist': 'artist',
        'RIFF:Title': 'title',
        'RIFF:Album': 'album',
        'RIFF:Genre': 'genre',
        'RIFF:Copyright': 'copyright',
        'RIFF:DateCreated': 'year',  # Maps to year field

        # Also include non-prefixed versions for compatibility
        'Artist': 'artist',
        'Title': 'title',
        'Album': 'album',
        'Genre': 'genre',
        'Copyright': 'copyright',
        'DateCreated': 'year',  # Maps to year field

        # Standard BWF fields
        'Originator': 'originator',
        'OriginatorReference': 'originator_reference',
        'Description': 'description',
        'OriginationDate': 'origination_date',
        'OriginationTime': 'origination_time',
        'BWFVersion': 'bwf_version',
        'UMID': 'umid',
        'CodingHistory': 'coding_history',

        # iXML fields (common in WAV files from audio interfaces)
        'IXMLVersion': 'ixml_version',
        'Scene': 'scene',
        'Take': 'take',
        'Note': 'note',
        'FileUID': 'file_uid',

        # Music-specific BWF/iXML fields
        'Product': 'album',  # Maps to album field

        # User-defined fields in iXML
        'UserCategory': 'genre',  # Often contains genre info
        'UserTrackTitle': 'title',
        'UserCdDescription': 'album',
        'UserSource': 'source',
        'UserDuration': 'duration_string',
    }

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if BWF extraction is available.

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
        Determine if BWF extraction is worth attempting.

        Args:
            file_path: Path to the audio file
            existing_metadata: Metadata already extracted by other methods

        Returns:
            True if BWF extraction should be attempted
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
        # This indicates the file might benefit from BWF enhancement
        return present_essential < 2

    @classmethod
    @contextmanager
    def get_exiftool_instance(cls):
        """
        Context manager for ExifTool instance.

        Ensures proper cleanup and error handling.
        """
        if not cls.is_available():
            raise BWFExtractionError("PyExifTool not available")

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
    def extract_bwf_metadata(cls, file_path: Path | str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Extract BWF metadata from a WAV file.

        Args:
            file_path: Path to the audio file
            timeout: Timeout in seconds for the extraction

        Returns:
            Dictionary of extracted BWF metadata, or None if extraction fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.debug(f"File not found for BWF extraction: {file_path}")
            return None

        if not cls.is_available():
            logger.debug("PyExifTool not available for BWF extraction")
            return None

        try:
            with cls.get_exiftool_instance() as et:
                # Extract all metadata (including BWF fields)
                metadata_list = et.execute_json(str(file_path))

                if not metadata_list or len(metadata_list) == 0:
                    logger.debug(f"No metadata found in {file_path.name}")
                    return None

                metadata = metadata_list[0]  # Get first result

                # Extract BWF fields
                bwf_data = cls._extract_bwf_fields(metadata)

                if bwf_data:
                    logger.info(f"Extracted BWF metadata from {file_path.name}: {list(bwf_data.keys())}")
                    return bwf_data
                else:
                    logger.debug(f"No BWF data found in {file_path.name}")
                    return None

        except Exception as e:
            logger.debug(f"BWF extraction failed for {file_path.name}: {e}")
            return None

    @classmethod
    def _extract_bwf_fields(cls, exiftool_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize BWF fields from ExifTool metadata.

        Args:
            exiftool_metadata: Raw metadata from ExifTool

        Returns:
            Normalized BWF metadata dictionary
        """
        bwf_data = {}

        # Extract mapped BWF fields
        for exif_key, internal_key in cls.BWF_FIELD_MAPPINGS.items():
            if exif_key in exiftool_metadata:
                value = exiftool_metadata[exif_key]
                if value and str(value).strip():  # Only non-empty values
                    normalized_value = cls._normalize_field_value(internal_key, value)
                    if normalized_value is not None:
                        bwf_data[internal_key] = normalized_value

        # Extract BWF XML fields (prefixed with Bwfxml:)
        for key, value in exiftool_metadata.items():
            if key.startswith('Bwfxml:') and key not in cls.BWF_FIELD_MAPPINGS:
                # Store BWF XML fields with a special prefix
                if value and str(value).strip():
                    # Convert to snake_case and prefix
                    field_name = key.replace('Bwfxml:', '').lower().replace(' ', '_')
                    bwf_data[f'bwf_{field_name}'] = str(value).strip()

        return bwf_data if bwf_data else {}

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

        elif field_name in ['artist', 'title', 'album', 'originator', 'description', 'copyright', 'genre']:
            # Text fields - ensure reasonable length
            if len(str_value) > 500:
                return str_value[:500]  # Truncate very long values
            return str_value

        elif field_name == 'duration_string':
            # Keep duration strings as-is for now
            return str_value

        elif field_name == 'bwf_version':
            # Convert to float if possible
            try:
                return float(value)
            except (ValueError, TypeError):
                return str_value

        else:
            # Default: return as string
            return str_value

    @classmethod
    def enhance_metadata_with_bwf(cls, file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance existing metadata with BWF data.

        BWF data takes priority over existing metadata for fields that are present.
        Implements smart copyright mapping to publisher/record_label fields with moderate tolerance
        for edge cases (case/whitespace normalization, exact string matching).

        Args:
            file_path: Path to the audio file
            existing_metadata: Existing metadata dictionary

        Returns:
            Enhanced metadata dictionary
        """
        # Create a copy to avoid modifying the original
        enhanced_metadata = existing_metadata.copy()

        # Attempt BWF extraction
        bwf_data = cls.extract_bwf_metadata(file_path)

        if bwf_data:
            # Handle smart copyright mapping
            copyright_value = bwf_data.get('copyright')
            if copyright_value:
                cls._map_copyright_to_rights_holder(enhanced_metadata, copyright_value, existing_metadata)

            # Remove copyright from bwf_data since we've mapped it
            bwf_data = {k: v for k, v in bwf_data.items() if k != 'copyright'}

            # BWF data takes priority - overwrite existing fields
            enhanced_metadata.update(bwf_data)

            # Log what was enhanced
            enhanced_fields = list(bwf_data.keys())
            logger.info(f"Enhanced metadata with BWF data: {enhanced_fields}")

            # Add BWF extraction flag
            enhanced_metadata['_bwf_enhanced'] = True
            enhanced_metadata['_bwf_fields'] = enhanced_fields
        else:
            enhanced_metadata['_bwf_enhanced'] = False

        return enhanced_metadata

    @classmethod
    def _map_copyright_to_rights_holder(cls, enhanced_metadata: Dict[str, Any], copyright_value: str, original_metadata: Dict[str, Any]):
        """
        Map copyright information to the most appropriate rights holder field.

        Edge Case Tolerance: Moderate - exact string matching after normalization
        - ✅ Case insensitive: "WEST ONE" matches "west one"
        - ✅ Whitespace normalized: "  Artist  " matches "Artist"
        - ❌ No partial matching: "Artist Ltd" ≠ "Artist"
        - ❌ No fuzzy matching: "Artist (ASCAP)" ≠ "Artist"

        Logic:
        1. If copyright equals artist name (after normalization) → map to publisher (edge case)
        2. If no publisher exists → map copyright to record_label
        3. If record_label already exists → map copyright to publisher

        Args:
            enhanced_metadata: The metadata dict being enhanced
            copyright_value: The copyright string to map
            original_metadata: Original metadata before enhancement
        """
        # Edge case: copyright matches artist name (moderate tolerance)
        # Handles case differences and whitespace, but requires exact string match
        artist_name = original_metadata.get('artist') or enhanced_metadata.get('artist')
        if artist_name and copyright_value.lower().strip() == artist_name.lower().strip():
            enhanced_metadata['publisher'] = copyright_value
            logger.debug(f"Mapped copyright to publisher (artist match): {copyright_value}")
            return

        # Check if publisher already exists (from any source)
        existing_publisher = original_metadata.get('publisher') or enhanced_metadata.get('publisher')
        if not existing_publisher:
            # No publisher - map copyright to record_label
            enhanced_metadata['record_label'] = copyright_value
            logger.debug(f"Mapped copyright to record_label (no publisher): {copyright_value}")
        else:
            # Publisher exists - map copyright to publisher
            # This handles the case where record_label already exists
            enhanced_metadata['publisher'] = copyright_value
            logger.debug(f"Mapped copyright to publisher (record_label exists): {copyright_value}")


# Convenience functions for external use

def extract_bwf_metadata(file_path: Path | str, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Extract BWF metadata from a WAV file.

    Args:
        file_path: Path to the audio file
        timeout: Timeout in seconds

    Returns:
        Dictionary of BWF metadata, or None
    """
    return BWFExtractor.extract_bwf_metadata(file_path, timeout)


def enhance_metadata_with_bwf(file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance existing metadata with BWF data.

    Args:
        file_path: Path to the audio file
        existing_metadata: Existing metadata to enhance

    Returns:
        Enhanced metadata dictionary
    """
    return BWFExtractor.enhance_metadata_with_bwf(file_path, existing_metadata)


def is_bwf_available() -> bool:
    """
    Check if BWF extraction is available.

    Returns:
        True if BWF extraction can be performed
    """
    return BWFExtractor.is_available()


def should_attempt_bwf_extraction(file_path: Path | str, existing_metadata: Dict[str, Any]) -> bool:
    """
    Determine if BWF extraction should be attempted.

    Args:
        file_path: Path to the audio file
        existing_metadata: Existing metadata

    Returns:
        True if BWF extraction should be attempted
    """
    return BWFExtractor.should_attempt_extraction(file_path, existing_metadata)
