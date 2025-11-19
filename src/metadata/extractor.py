"""
Audio metadata extraction using Mutagen.

Provides extraction of ID3 tags and audio metadata from various formats:
- MP3 (ID3v1, ID3v2.3, ID3v2.4)
- FLAC (Vorbis comments)
- M4A/AAC (MP4 tags)
- OGG (Vorbis comments)
- WAV (RIFF INFO)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
import tempfile
import re

logger = logging.getLogger(__name__)


class MetadataExtractionError(Exception):
    """Exception raised when metadata extraction fails."""
    pass


class MetadataQualityError(Exception):
    """Exception raised when metadata quality issues are detected."""
    def __init__(self, message: str, quality_score: float, issues: List[str]):
        super().__init__(message)
        self.quality_score = quality_score
        self.issues = issues


class MetadataQualityAssessment:
    """Assessment of metadata quality and completeness."""
    
    def __init__(self, metadata: Dict[str, Any], file_path: Path):
        self.metadata = metadata
        self.file_path = file_path
        self.issues: List[str] = []
        self.quality_score = 1.0
        self._assess_quality()
    
    def _assess_quality(self):
        """Assess metadata quality and identify issues."""
        # Essential fields for quality assessment
        essential_fields = ['artist', 'title', 'album']
        optional_fields = ['genre', 'year', 'duration', 'channels', 'sample_rate']
        
        # Check for missing essential fields
        missing_essential = []
        for field in essential_fields:
            if not self.metadata.get(field):
                missing_essential.append(field)
        
        if missing_essential:
            self.issues.append(f"Missing essential fields: {', '.join(missing_essential)}")
            self.quality_score -= 0.3 * len(missing_essential)
        
        # Check for missing optional fields
        missing_optional = []
        for field in optional_fields:
            if not self.metadata.get(field):
                missing_optional.append(field)
        
        if missing_optional:
            self.issues.append(f"Missing optional fields: {', '.join(missing_optional)}")
            self.quality_score -= 0.1 * len(missing_optional)
        
        # Check for corrupt or invalid data
        self._check_corrupt_data()
        
        # Ensure quality score doesn't go below 0
        self.quality_score = max(0.0, self.quality_score)
    
    def _check_corrupt_data(self):
        """Check for corrupt or invalid metadata values."""
        # Check year validity
        year = self.metadata.get('year')
        if year is not None:
            if not isinstance(year, int) or year < 1900 or year > 2030:
                self.issues.append(f"Invalid year: {year}")
                self.quality_score -= 0.2
        
        # Check duration validity
        duration = self.metadata.get('duration')
        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0 or duration > 86400:  # Max 24 hours
                self.issues.append(f"Invalid duration: {duration}")
                self.quality_score -= 0.1
        
        # Check sample rate validity
        sample_rate = self.metadata.get('sample_rate')
        if sample_rate is not None:
            if not isinstance(sample_rate, int) or sample_rate <= 0 or sample_rate > 192000:
                self.issues.append(f"Invalid sample rate: {sample_rate}")
                self.quality_score -= 0.1
        
        # Check channels validity
        channels = self.metadata.get('channels')
        if channels is not None:
            if not isinstance(channels, int) or channels <= 0 or channels > 8:
                self.issues.append(f"Invalid channel count: {channels}")
                self.quality_score -= 0.1
        
        # Check for suspiciously long or empty strings
        text_fields = ['artist', 'title', 'album', 'genre']
        for field in text_fields:
            value = self.metadata.get(field)
            if value:
                if len(str(value)) > 500:  # Suspiciously long
                    self.issues.append(f"Suspiciously long {field}: {len(str(value))} characters")
                    self.quality_score -= 0.05
                elif len(str(value).strip()) == 0:  # Empty after stripping
                    self.issues.append(f"Empty {field} field")
                    self.quality_score -= 0.1
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive quality report."""
        return {
            'file_path': str(self.file_path),
            'quality_score': round(self.quality_score, 2),
            'quality_level': self._get_quality_level(),
            'issues': self.issues,
            'has_issues': len(self.issues) > 0,
            'metadata_completeness': self._calculate_completeness()
        }
    
    def _get_quality_level(self) -> str:
        """Get human-readable quality level."""
        if self.quality_score >= 0.9:
            return "Excellent"
        elif self.quality_score >= 0.7:
            return "Good"
        elif self.quality_score >= 0.5:
            return "Fair"
        elif self.quality_score >= 0.3:
            return "Poor"
        else:
            return "Very Poor"
    
    def _calculate_completeness(self) -> float:
        """Calculate metadata completeness percentage."""
        total_fields = 11  # All metadata fields
        present_fields = sum(1 for value in self.metadata.values() if value is not None)
        return round((present_fields / total_fields) * 100, 1)


class MetadataExtractor:
    """
    Extract metadata from audio files.
    
    Supports multiple audio formats and handles missing/incomplete metadata gracefully.
    """
    
    # Supported audio formats
    SUPPORTED_FORMATS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}
    
    # Picture type priorities (APIC/Picture type field)
    # 3 = Front cover (preferred)
    # 0 = Other
    # 1 = 32x32 file icon
    # 2 = Other file icon
    # 4 = Back cover
    PICTURE_TYPE_PRIORITY = [3, 0, 4, 2, 1]
    
    @staticmethod
    def extract_id3_tags(file_path: Path | str) -> Dict[str, Any]:
        """
        Extract ID3 tags from MP3 file.
        
        Supports ID3v1, ID3v2.3, and ID3v2.4 tags.
        
        Args:
            file_path: Path to MP3 file
        
        Returns:
            Dictionary of metadata
        
        Raises:
            MetadataExtractionError: If extraction fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise MetadataExtractionError(f"File not found: {file_path}")
        
        metadata = {
            "artist": None,
            "title": None,
            "album": None,
            "genre": None,
            "year": None,
        }
        
        try:
            # Try to load ID3 tags
            try:
                audio = ID3(str(file_path))
            except ID3NoHeaderError:
                # Try as MP3 file (may have ID3v1 tags)
                audio = MP3(str(file_path))
                if not hasattr(audio, 'tags') or audio.tags is None:
                    logger.warning(f"No ID3 tags found in {file_path}")
                    return metadata
                audio = audio.tags
            
            # Extract common ID3v2 tags
            # TPE1 = Artist
            if 'TPE1' in audio:
                metadata['artist'] = str(audio['TPE1'].text[0]) if audio['TPE1'].text else None
            
            # TIT2 = Title
            if 'TIT2' in audio:
                metadata['title'] = str(audio['TIT2'].text[0]) if audio['TIT2'].text else None
            
            # TALB = Album
            if 'TALB' in audio:
                metadata['album'] = str(audio['TALB'].text[0]) if audio['TALB'].text else None
            
            # TCON = Genre
            if 'TCON' in audio:
                metadata['genre'] = str(audio['TCON'].text[0]) if audio['TCON'].text else None
            
            # TDRC = Recording Date (ID3v2.4) or TYER = Year (ID3v2.3)
            if 'TDRC' in audio:
                try:
                    year_str = str(audio['TDRC'].text[0])
                    # Extract year from date (format: YYYY-MM-DD or YYYY)
                    metadata['year'] = int(year_str.split('-')[0])
                except (ValueError, IndexError, AttributeError):
                    pass
            elif 'TYER' in audio:
                try:
                    metadata['year'] = int(str(audio['TYER'].text[0]))
                except (ValueError, AttributeError):
                    pass
            
            logger.info(f"Extracted ID3 tags from {file_path.name}")
            return metadata
            
        except Exception as e:
            raise MetadataExtractionError(f"Failed to extract ID3 tags: {e}")
    
    @staticmethod
    def extract_vorbis_comments(file_path: Path | str) -> Dict[str, Any]:
        """
        Extract Vorbis comments from FLAC/OGG files.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary of metadata
        """
        file_path = Path(file_path)
        
        metadata = {
            "artist": None,
            "title": None,
            "album": None,
            "genre": None,
            "year": None,
        }
        
        try:
            # Detect file type
            if file_path.suffix.lower() == '.flac':
                audio = FLAC(str(file_path))
            elif file_path.suffix.lower() == '.ogg':
                audio = OggVorbis(str(file_path))
            else:
                raise MetadataExtractionError(f"Unsupported format for Vorbis comments: {file_path.suffix}")
            
            if not audio.tags:
                logger.warning(f"No Vorbis comments found in {file_path}")
                return metadata
            
            # Extract Vorbis comment fields (lowercase keys)
            metadata['artist'] = audio.tags.get('artist', [None])[0]
            metadata['title'] = audio.tags.get('title', [None])[0]
            metadata['album'] = audio.tags.get('album', [None])[0]
            metadata['genre'] = audio.tags.get('genre', [None])[0]
            
            # Date can be in various formats
            date = audio.tags.get('date', [None])[0]
            if date:
                try:
                    metadata['year'] = int(str(date).split('-')[0])
                except (ValueError, AttributeError):
                    pass
            
            logger.info(f"Extracted Vorbis comments from {file_path.name}")
            return metadata
            
        except Exception as e:
            raise MetadataExtractionError(f"Failed to extract Vorbis comments: {e}")
    
    @staticmethod
    def extract_mp4_tags(file_path: Path | str) -> Dict[str, Any]:
        """
        Extract tags from MP4/M4A/AAC files.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary of metadata
        """
        file_path = Path(file_path)
        
        metadata = {
            "artist": None,
            "title": None,
            "album": None,
            "genre": None,
            "year": None,
        }
        
        try:
            audio = MP4(str(file_path))
            
            if not audio.tags:
                logger.warning(f"No MP4 tags found in {file_path}")
                return metadata
            
            # Extract MP4 tag fields
            # \xa9ART = Artist
            if '\xa9ART' in audio.tags:
                metadata['artist'] = audio.tags['\xa9ART'][0]
            
            # \xa9nam = Title
            if '\xa9nam' in audio.tags:
                metadata['title'] = audio.tags['\xa9nam'][0]
            
            # \xa9alb = Album
            if '\xa9alb' in audio.tags:
                metadata['album'] = audio.tags['\xa9alb'][0]
            
            # \xa9gen = Genre
            if '\xa9gen' in audio.tags:
                metadata['genre'] = audio.tags['\xa9gen'][0]
            
            # \xa9day = Date/Year
            if '\xa9day' in audio.tags:
                try:
                    year_str = audio.tags['\xa9day'][0]
                    metadata['year'] = int(str(year_str).split('-')[0])
                except (ValueError, AttributeError):
                    pass
            
            logger.info(f"Extracted MP4 tags from {file_path.name}")
            return metadata
            
        except Exception as e:
            raise MetadataExtractionError(f"Failed to extract MP4 tags: {e}")
    
    @staticmethod
    def extract(file_path: Path | str, validate_quality: bool = True, quality_threshold: float = 0.3) -> Dict[str, Any]:
        """
        Extract all available metadata from an audio file.
        
        Automatically detects format and uses appropriate extraction method.
        
        Args:
            file_path: Path to audio file
            validate_quality: Whether to validate metadata quality
            quality_threshold: Minimum quality score threshold (0.0-1.0)
        
        Returns:
            Dictionary containing all extracted metadata
        
        Raises:
            MetadataExtractionError: If extraction fails
            MetadataQualityError: If quality validation fails and threshold not met
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise MetadataExtractionError(f"File not found: {file_path}")
        
        # Check format
        suffix = file_path.suffix.lower()
        if suffix not in MetadataExtractor.SUPPORTED_FORMATS:
            raise MetadataExtractionError(
                f"Unsupported audio format: {suffix}. "
                f"Supported formats: {', '.join(MetadataExtractor.SUPPORTED_FORMATS)}"
            )
        
        # Initialize result
        metadata = {
            "artist": None,
            "title": None,
            "album": None,
            "genre": None,
            "year": None,
            "duration": None,
            "channels": None,
            "sample_rate": None,
            "bitrate": None,
            "bit_depth": None,
            "format": suffix.lstrip('.').upper(),
        }
        
        try:
            # Load file with Mutagen
            audio = MutagenFile(str(file_path))
            
            if audio is None:
                raise MetadataExtractionError(f"Could not load audio file: {file_path}")
            
            # Extract format-specific tags
            if suffix == '.mp3':
                tags = MetadataExtractor.extract_id3_tags(file_path)
                metadata.update(tags)
            elif suffix in {'.flac', '.ogg'}:
                tags = MetadataExtractor.extract_vorbis_comments(file_path)
                metadata.update(tags)
            elif suffix in {'.m4a', '.aac'}:
                tags = MetadataExtractor.extract_mp4_tags(file_path)
                metadata.update(tags)
            elif suffix == '.wav':
                # WAV files may have INFO chunks
                if hasattr(audio, 'tags') and audio.tags:
                    metadata['artist'] = audio.tags.get('artist', [None])[0]
                    metadata['title'] = audio.tags.get('title', [None])[0]
                    metadata['album'] = audio.tags.get('album', [None])[0]
            
            # Extract technical specifications (available for most formats)
            if hasattr(audio.info, 'length'):
                metadata['duration'] = round(audio.info.length, 3)  # seconds
            
            if hasattr(audio.info, 'channels'):
                metadata['channels'] = audio.info.channels
            
            if hasattr(audio.info, 'sample_rate'):
                metadata['sample_rate'] = audio.info.sample_rate
            
            if hasattr(audio.info, 'bitrate'):
                metadata['bitrate'] = audio.info.bitrate // 1000  # Convert to kbps
            
            # Bit depth (bits per sample) - available for some formats
            if hasattr(audio.info, 'bits_per_sample'):
                metadata['bit_depth'] = audio.info.bits_per_sample
            elif hasattr(audio.info, 'sample_width'):
                # For WAV files, sample_width is in bytes
                metadata['bit_depth'] = audio.info.sample_width * 8
            
            # If title is missing, use filename
            if not metadata['title']:
                metadata['title'] = file_path.stem
                logger.debug(f"Using filename as title: {metadata['title']}")
            
            # Validate metadata quality if requested
            if validate_quality:
                quality_assessment = MetadataQualityAssessment(metadata, file_path)
                quality_report = quality_assessment.get_quality_report()
                
                # Log quality assessment
                logger.info(
                    f"Metadata quality assessment for {file_path.name}: "
                    f"Score={quality_report['quality_score']}, "
                    f"Level={quality_report['quality_level']}, "
                    f"Completeness={quality_report['metadata_completeness']}%"
                )
                
                # Log issues if any
                if quality_report['has_issues']:
                    logger.warning(f"Metadata quality issues in {file_path.name}: {quality_report['issues']}")
                
                # Check if quality meets threshold
                if quality_report['quality_score'] < quality_threshold:
                    raise MetadataQualityError(
                        f"Metadata quality below threshold ({quality_threshold}): "
                        f"Score={quality_report['quality_score']}, "
                        f"Issues={quality_report['issues']}",
                        quality_report['quality_score'],
                        quality_report['issues']
                    )
                
                # Add quality report to metadata
                metadata['_quality_report'] = quality_report
            
            logger.info(f"Successfully extracted metadata from {file_path.name}")
            return metadata
            
        except MetadataExtractionError:
            raise
        except MetadataQualityError:
            raise
        except Exception as e:
            raise MetadataExtractionError(f"Metadata extraction failed: {e}")
    
    @staticmethod
    def validate_and_repair_metadata(metadata: Dict[str, Any], file_path: Path) -> Dict[str, Any]:
        """
        Validate and repair corrupted metadata.
        
        Args:
            metadata: Metadata dictionary to validate
            file_path: Path to the audio file
        
        Returns:
            Repaired metadata dictionary
        """
        repaired_metadata = metadata.copy()
        
        # Repair invalid year
        if repaired_metadata.get('year') is not None:
            year = repaired_metadata['year']
            if not isinstance(year, int) or year < 1900 or year > 2030:
                logger.warning(f"Repairing invalid year {year} in {file_path.name}")
                repaired_metadata['year'] = None
        
        # Repair invalid duration
        if repaired_metadata.get('duration') is not None:
            duration = repaired_metadata['duration']
            if not isinstance(duration, (int, float)) or duration <= 0 or duration > 86400:
                logger.warning(f"Repairing invalid duration {duration} in {file_path.name}")
                repaired_metadata['duration'] = None
        
        # Repair invalid sample rate
        if repaired_metadata.get('sample_rate') is not None:
            sample_rate = repaired_metadata['sample_rate']
            if not isinstance(sample_rate, int) or sample_rate <= 0 or sample_rate > 192000:
                logger.warning(f"Repairing invalid sample rate {sample_rate} in {file_path.name}")
                repaired_metadata['sample_rate'] = None
        
        # Repair invalid channels
        if repaired_metadata.get('channels') is not None:
            channels = repaired_metadata['channels']
            if not isinstance(channels, int) or channels <= 0 or channels > 8:
                logger.warning(f"Repairing invalid channel count {channels} in {file_path.name}")
                repaired_metadata['channels'] = None
        
        # Repair empty or suspiciously long text fields
        text_fields = ['artist', 'title', 'album', 'genre']
        for field in text_fields:
            value = repaired_metadata.get(field)
            if value:
                str_value = str(value).strip()
                if len(str_value) == 0:
                    logger.warning(f"Repairing empty {field} field in {file_path.name}")
                    repaired_metadata[field] = None
                elif len(str_value) > 500:
                    logger.warning(f"Truncating suspiciously long {field} field in {file_path.name}")
                    repaired_metadata[field] = str_value[:500]
        
        return repaired_metadata
    
    @staticmethod
    def extract_with_fallback(file_path: Path | str) -> Tuple[Dict[str, Any], bool]:
        """
        Extract metadata with fallback mechanisms for corrupt data.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Tuple of (metadata, was_repaired) where was_repaired indicates if repairs were made
        """
        file_path = Path(file_path)
        
        try:
            # Try normal extraction with quality validation
            metadata = MetadataExtractor.extract(file_path, validate_quality=True)
            return metadata, False
            
        except MetadataQualityError as e:
            logger.warning(f"Metadata quality issues detected in {file_path.name}: {e.issues}")
            
            # Try extraction without quality validation
            try:
                metadata = MetadataExtractor.extract(file_path, validate_quality=False)
                
                # Attempt to repair the metadata
                repaired_metadata = MetadataExtractor.validate_and_repair_metadata(metadata, file_path)
                
                # Re-assess quality after repair
                quality_assessment = MetadataQualityAssessment(repaired_metadata, file_path)
                quality_report = quality_assessment.get_quality_report()
                
                logger.info(
                    f"Metadata repaired for {file_path.name}: "
                    f"Score={quality_report['quality_score']}, "
                    f"Level={quality_report['quality_level']}"
                )
                
                # Add quality report
                repaired_metadata['_quality_report'] = quality_report
                
                return repaired_metadata, True
                
            except Exception as repair_error:
                logger.error(f"Failed to repair metadata for {file_path.name}: {repair_error}")
                raise MetadataExtractionError(f"Metadata extraction and repair failed: {repair_error}")
        
        except Exception as e:
            raise MetadataExtractionError(f"Metadata extraction failed: {e}")
    
    @staticmethod
    def extract_artwork(
        file_path: Path | str,
        destination: Optional[Path | str] = None,
        prefer_front_cover: bool = True
    ) -> Optional[Path]:
        """
        Extract embedded artwork from audio file.
        
        Args:
            file_path: Path to audio file
            destination: Destination path for artwork (temp file if None)
            prefer_front_cover: Prefer front cover artwork (type 3)
        
        Returns:
            Path to extracted artwork or None if no artwork found
        
        Raises:
            MetadataExtractionError: If extraction fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise MetadataExtractionError(f"File not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        # Extract artwork based on format
        if suffix == '.mp3':
            return MetadataExtractor._extract_artwork_mp3(file_path, destination, prefer_front_cover)
        elif suffix == '.flac':
            return MetadataExtractor._extract_artwork_flac(file_path, destination, prefer_front_cover)
        elif suffix in {'.m4a', '.aac'}:
            return MetadataExtractor._extract_artwork_mp4(file_path, destination, prefer_front_cover)
        elif suffix == '.ogg':
            return MetadataExtractor._extract_artwork_ogg(file_path, destination, prefer_front_cover)
        else:
            logger.debug(f"Artwork extraction not supported for {suffix}")
            return None
    
    @staticmethod
    def _extract_artwork_mp3(
        file_path: Path,
        destination: Optional[Path | str],
        prefer_front_cover: bool
    ) -> Optional[Path]:
        """Extract artwork from MP3 file (APIC frames)."""
        try:
            audio = MP3(str(file_path))
            
            if not audio.tags:
                logger.debug(f"No tags found in {file_path}")
                return None
            
            # Find APIC frames (artwork)
            apic_frames = [tag for tag in audio.tags.values() if isinstance(tag, APIC)]
            
            if not apic_frames:
                logger.debug(f"No artwork found in {file_path}")
                return None
            
            # Select artwork based on priority
            selected_artwork = None
            
            if prefer_front_cover:
                # Try to find front cover (type 3)
                for priority_type in MetadataExtractor.PICTURE_TYPE_PRIORITY:
                    for frame in apic_frames:
                        if frame.type == priority_type:
                            selected_artwork = frame
                            break
                    if selected_artwork:
                        break
            
            # If no prioritized artwork found, use first one
            if not selected_artwork:
                selected_artwork = apic_frames[0]
            
            # Determine file extension from MIME type
            mime_type = selected_artwork.mime
            extension = MetadataExtractor._mime_to_extension(mime_type)
            
            # Create destination path
            if destination:
                dest_path = Path(destination)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=extension
                )
                dest_path = Path(temp_file.name)
                temp_file.close()
            
            # Save artwork
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(selected_artwork.data)
            
            logger.info(
                f"Extracted artwork from {file_path.name} ({len(selected_artwork.data)} bytes) "
                f"to {dest_path}"
            )
            return dest_path
            
        except Exception as e:
            logger.error(f"Failed to extract artwork from MP3: {e}")
            return None
    
    @staticmethod
    def _extract_artwork_flac(
        file_path: Path,
        destination: Optional[Path | str],
        prefer_front_cover: bool
    ) -> Optional[Path]:
        """Extract artwork from FLAC file (Picture blocks)."""
        try:
            audio = FLAC(str(file_path))
            
            if not audio.pictures:
                logger.debug(f"No artwork found in {file_path}")
                return None
            
            # Select picture based on priority
            selected_picture = None
            
            if prefer_front_cover:
                # Try to find front cover (type 3)
                for priority_type in MetadataExtractor.PICTURE_TYPE_PRIORITY:
                    for picture in audio.pictures:
                        if picture.type == priority_type:
                            selected_picture = picture
                            break
                    if selected_picture:
                        break
            
            # If no prioritized picture found, use first one
            if not selected_picture:
                selected_picture = audio.pictures[0]
            
            # Determine file extension from MIME type
            mime_type = selected_picture.mime
            extension = MetadataExtractor._mime_to_extension(mime_type)
            
            # Create destination path
            if destination:
                dest_path = Path(destination)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=extension
                )
                dest_path = Path(temp_file.name)
                temp_file.close()
            
            # Save artwork
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(selected_picture.data)
            
            logger.info(
                f"Extracted artwork from {file_path.name} ({len(selected_picture.data)} bytes) "
                f"to {dest_path}"
            )
            return dest_path
            
        except Exception as e:
            logger.error(f"Failed to extract artwork from FLAC: {e}")
            return None
    
    @staticmethod
    def _extract_artwork_mp4(
        file_path: Path,
        destination: Optional[Path | str],
        prefer_front_cover: bool
    ) -> Optional[Path]:
        """Extract artwork from MP4/M4A file (covr atom)."""
        try:
            audio = MP4(str(file_path))
            
            if not audio.tags or 'covr' not in audio.tags:
                logger.debug(f"No artwork found in {file_path}")
                return None
            
            # Get cover artwork
            covers = audio.tags['covr']
            
            if not covers:
                return None
            
            # Use first cover (MP4 doesn't have type priorities like ID3)
            cover = covers[0]
            
            # Determine file extension (MP4 cover can be JPEG or PNG)
            # Check for PNG signature
            if cover[:8] == b'\x89PNG\r\n\x1a\n':
                extension = '.png'
            else:
                extension = '.jpg'  # Default to JPEG
            
            # Create destination path
            if destination:
                dest_path = Path(destination)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=extension
                )
                dest_path = Path(temp_file.name)
                temp_file.close()
            
            # Save artwork
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(cover)
            
            logger.info(
                f"Extracted artwork from {file_path.name} ({len(cover)} bytes) "
                f"to {dest_path}"
            )
            return dest_path
            
        except Exception as e:
            logger.error(f"Failed to extract artwork from MP4: {e}")
            return None
    
    @staticmethod
    def _extract_artwork_ogg(
        file_path: Path,
        destination: Optional[Path | str],
        prefer_front_cover: bool
    ) -> Optional[Path]:
        """Extract artwork from OGG file (METADATA_BLOCK_PICTURE)."""
        try:
            audio = OggVorbis(str(file_path))
            
            # OGG Vorbis can have METADATA_BLOCK_PICTURE in comments
            if not audio.tags:
                return None
            
            # Look for picture data in Vorbis comments
            metadata_block = audio.tags.get('metadata_block_picture')
            
            if not metadata_block:
                logger.debug(f"No artwork found in {file_path}")
                return None
            
            # Decode picture data (base64 encoded FLAC picture block)
            import base64
            picture_data = base64.b64decode(metadata_block[0])
            
            # Parse FLAC picture block
            # For simplicity, we'll extract the raw image data
            # (Full FLAC picture parsing would require more complex logic)
            
            # Create destination path
            if destination:
                dest_path = Path(destination)
            else:
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix='.jpg'  # Default to JPEG
                )
                dest_path = Path(temp_file.name)
                temp_file.close()
            
            # Save picture data
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(picture_data)
            
            logger.info(f"Extracted artwork from {file_path.name} to {dest_path}")
            return dest_path
            
        except Exception as e:
            logger.debug(f"No artwork in OGG file or extraction failed: {e}")
            return None
    
    @staticmethod
    def _mime_to_extension(mime_type: str) -> str:
        """
        Convert MIME type to file extension.
        
        Args:
            mime_type: MIME type string
        
        Returns:
            File extension with dot (e.g., ".jpg")
        """
        mime_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/webp': '.webp',
        }
        
        return mime_map.get(mime_type.lower(), '.jpg')


def extract_id3_tags(file_path: Path | str) -> Dict[str, Any]:
    """
    Extract only ID3 tags from MP3 file.
    
    Args:
        file_path: Path to MP3 file
    
    Returns:
        Dictionary of ID3 tag metadata
    """
    return MetadataExtractor.extract_id3_tags(file_path)


def extract_artwork(
    file_path: Path | str,
    destination: Optional[Path | str] = None,
    prefer_front_cover: bool = True
) -> Optional[Path]:
    """
    Extract artwork from audio file.
    
    Args:
        file_path: Path to audio file
        destination: Destination path for artwork (temp file if None)
        prefer_front_cover: Prefer front cover artwork
    
    Returns:
        Path to extracted artwork or None if no artwork found
    
    Example:
        >>> from src.metadata import extract_artwork
        >>> artwork_path = extract_artwork("song.mp3")
        >>> if artwork_path:
        ...     print(f"Artwork saved to: {artwork_path}")
    """
    return MetadataExtractor.extract_artwork(file_path, destination, prefer_front_cover)

def extract_metadata(file_path: Path | str, validate_quality: bool = True, quality_threshold: float = 0.3) -> Dict[str, Any]:
    """
    Extract all metadata from an audio file.
    
    Convenience function that uses MetadataExtractor.
    
    Args:
        file_path: Path to audio file
        validate_quality: Whether to validate metadata quality
        quality_threshold: Minimum quality score threshold (0.0-1.0)
    
    Returns:
        Dictionary of metadata
    
    Example:
        >>> from src.metadata import extract_metadata
        >>> metadata = extract_metadata("song.mp3")
        >>> print(f"{metadata['artist']} - {metadata['title']}")
    """
    return MetadataExtractor.extract(file_path, validate_quality, quality_threshold)


def extract_metadata_with_fallback(file_path: Path | str) -> Tuple[Dict[str, Any], bool]:
    """
    Extract metadata with fallback mechanisms for corrupt data.
    
    Convenience function that uses MetadataExtractor.extract_with_fallback.
    
    Args:
        file_path: Path to audio file
    
    Returns:
        Tuple of (metadata, was_repaired) where was_repaired indicates if repairs were made
    
    Example:
        >>> from src.metadata import extract_metadata_with_fallback
        >>> metadata, was_repaired = extract_metadata_with_fallback("song.mp3")
        >>> if was_repaired:
        ...     print("Metadata was repaired")
    """
    return MetadataExtractor.extract_with_fallback(file_path)


def assess_metadata_quality(metadata: Dict[str, Any], file_path: Path | str) -> Dict[str, Any]:
    """
    Assess metadata quality and completeness.
    
    Args:
        metadata: Metadata dictionary to assess
        file_path: Path to the audio file
    
    Returns:
        Quality assessment report
    
    Example:
        >>> from src.metadata import assess_metadata_quality
        >>> report = assess_metadata_quality(metadata, "song.mp3")
        >>> print(f"Quality: {report['quality_level']} ({report['quality_score']})")
    """
    return MetadataQualityAssessment(metadata, Path(file_path)).get_quality_report()


def extract_id3_tags(file_path: Path | str) -> Dict[str, Any]:
    """
    Extract only ID3 tags from MP3 file.
    
    Args:
        file_path: Path to MP3 file
    
    Returns:
        Dictionary of ID3 tag metadata
    """
    return MetadataExtractor.extract_id3_tags(file_path)


def extract_artwork(
    file_path: Path | str,
    destination: Optional[Path | str] = None,
    prefer_front_cover: bool = True
) -> Optional[Path]:
    """
    Extract artwork from audio file.
    
    Args:
        file_path: Path to audio file
        destination: Destination path for artwork (temp file if None)
        prefer_front_cover: Prefer front cover artwork
    
    Returns:
        Path to extracted artwork or None if no artwork found
    
    Example:
        >>> from src.metadata import extract_artwork
        >>> artwork_path = extract_artwork("song.mp3")
        >>> if artwork_path:
        ...     print(f"Artwork saved to: {artwork_path}")
    """
    return MetadataExtractor.extract_artwork(file_path, destination, prefer_front_cover)



def parse_filename_metadata(file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse metadata from filename patterns.

    Handles common filename patterns and preprocesses to handle inconsistent formats:
    - Removes leading track numbers (01., 1-, etc.)
    - Handles year patterns (YYYY, (YYYY))
    - Multiple parsing attempts for complex patterns
    - Can override temp filenames (tmpXXXXXX patterns) with proper metadata

    Common patterns after preprocessing:
    - "Artist - Title.mp3"
    - "Artist - Title (Album).mp3"
    - "Artist - Album - Title.mp3"
    - "Title.mp3" (no artist)
    - "Track01.mp3" (minimal info)

    Args:
        file_path: Path to audio file
        existing_metadata: Already extracted metadata (won't overwrite except temp filenames)

    Returns:
        Dictionary with parsed metadata (fills missing fields, can override temp filenames)
    """
    file_path = Path(file_path)
    filename = file_path.stem  # Without extension
    parsed = {}

    # Preprocessing: Clean up common prefixes and patterns
    cleaned_filename = _preprocess_filename(filename)

    # Try multiple parsing strategies in order of specificity (most specific first)
    strategies = [
        _parse_artist_album_title_pattern,  # 3 parts: Artist - Album - Title
        _parse_artist_title_pattern,        # 2 parts: Artist - Title
        _parse_title_only_pattern           # 1 part: Title only
    ]

    for strategy in strategies:
        result = strategy(cleaned_filename)
        if result:
            parsed.update(result)
            break  # Take first successful parse

    # Fill in missing fields or override temp filenames
    result = {}
    for key, value in parsed.items():
        existing_value = existing_metadata.get(key)

        # Allow override if existing value is a temp filename pattern
        should_override = (
            not existing_value or  # No existing value
            _is_temp_filename(existing_value)  # Existing value is a temp filename
        )

        if should_override and value:
            result[key] = value

    if result:
        logger.debug(f"Parsed metadata from filename '{filename}': {result}")

    return result


def _is_temp_filename(value: str) -> bool:
    """
    Check if a string looks like a temporary filename that should be overridden.

    Patterns that indicate temp filenames:
    - tmp followed by digits (tmp123456, tmpabcdef)
    - Random alphanumeric strings (8+ chars, no spaces, mixed case)
    - Common temp prefixes (temp_, tmp_, cache_)
    """
    if not isinstance(value, str):
        return False

    value_lower = value.lower()

    # Check for common temp patterns
    import re

    # tmp followed by digits/letters
    if re.match(r'^tmp[a-z0-9]{6,}$', value_lower):
        return True

    # temp_ or tmp_ prefix
    if value_lower.startswith(('temp_', 'tmp_', 'cache_')):
        return True

    # Very long random-looking strings that look like temp files
    # Only flag if 10+ chars AND contains digits AND looks computer-generated
    if (len(value) >= 10 and
        re.search(r'\d', value_lower) and  # Contains digits
        re.match(r'^[a-z0-9]+$', value_lower) and  # Alphanumeric only
        not re.search(r'[aeiou]{2}', value_lower)):  # No vowel clusters (real words have vowels)
        return True

    return False


def _preprocess_filename(filename: str) -> str:
    """
    Preprocess filename to remove common prefixes and normalize patterns.
    
    Handles:
    - Leading track numbers: "01. ", "1-", "(01) "
    - Year patterns: " (2020)", " - 2020"
    - Extra spaces and separators
    """
    # Remove leading track numbers (with various separators)
    patterns = [
        r'^\d+\.\s*',  # "01. "
        r'^\d+-\s*',   # "01-"
        r'^\(\d+\)\s*', # "(01) "
        r'^\[\d+\]\s*', # "[01] "
        r'^\d+\s*-\s*', # "01 - "
    ]
    
    cleaned = filename
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove trailing year patterns (but keep them for potential album year)
    # This is tricky - we'll handle years in the parsing logic instead
    # cleaned = re.sub(r'\s*\(\d{4}\)$', '', cleaned)  # Remove (2020) at end
    # cleaned = re.sub(r'\s*-\s*\d{4}$', '', cleaned)  # Remove - 2020 at end
    
    return cleaned.strip()


def _parse_artist_title_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns like "Artist - Title" or "Artist - Title (Album)".

    Special handling for year patterns: if the second part looks like a year,
    treat the first part as title and the second as year instead of artist-title.
    """
    # Pattern: "Artist - Title (Album)" - handle album in parentheses first
    match = re.match(r'^(.+?)\s*-\s*(.+?)\s*\(([^)]+)\)$', filename)
    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()
        album = match.group(3).strip()

        # Check if album looks like a year (4 digits)
        if re.match(r'^\d{4}$', album):
            return {
                'artist': artist,
                'title': title,
                'year': album
            }
        else:
            return {
                'artist': artist,
                'title': title,
                'album': album
            }

    # Pattern: "Artist/Title - Year" - check for year pattern first
    match = re.match(r'^(.+?)\s*-\s*(\d{4})$', filename)
    if match:
        potential_title = match.group(1).strip()
        year = match.group(2).strip()

        # If the first part is reasonable length and not just numbers, treat as title + year
        if len(potential_title) >= 2 and not re.match(r'^\d+$', potential_title):
            return {
                'title': potential_title,
                'year': year
            }

    # Pattern: "Artist - Title" (fallback for non-year patterns)
    match = re.match(r'^(.+?)\s*-\s*(.+)$', filename)
    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()

        # Skip if title is just a track number or very short
        if re.match(r'^\d{1,3}$', title) or len(title) < 2:
            return None

        # Additional check: if title looks like a year, don't treat as artist-title
        if re.match(r'^\d{4}$', title):
            return None

        return {
            'artist': artist,
            'title': title
        }

    return None


def _parse_artist_album_title_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns like "Artist - Album - Title".
    """
    match = re.match(r'^(.+?)\s*-\s*(.+?)\s*-\s*(.+)$', filename)
    if match:
        artist = match.group(1).strip()
        album = match.group(2).strip()
        title = match.group(3).strip()
        
        # Check if album looks like a year (4 digits)
        if re.match(r'^\d{4}$', album):
            return {
                'artist': artist,
                'title': title,
                'year': album
            }
        else:
            return {
                'artist': artist,
                'album': album,
                'title': title
            }
    
    return None


def _parse_title_only_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns that are just titles, possibly with years.
    """
    # Check if it's a reasonable title (not just numbers/symbols)
    if len(filename) < 2 or re.match(r'^[\d\s\-\(\)\[\]]+$', filename):
        return None
    
    # Pattern: "Title (Year)"
    match = re.match(r'^(.+?)\s*\((\d{4})\)$', filename)
    if match:
        title = match.group(1).strip()
        year = match.group(2).strip()
        return {
            'title': title,
            'year': year
        }
    
    # Pattern: "Title - Year"
    match = re.match(r'^(.+?)\s*-\s*(\d{4})$', filename)
    if match:
        title = match.group(1).strip()
        year = match.group(2).strip()
        return {
            'title': title,
            'year': year
        }
    
    # Just title
    return {
        'title': filename
    }
