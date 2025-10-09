"""
Audio metadata extraction using Mutagen.

Provides extraction of ID3 tags and audio metadata from various formats:
- MP3 (ID3v1, ID3v2.3, ID3v2.4)
- FLAC (Vorbis comments)
- M4A/AAC (MP4 tags)
- OGG (Vorbis comments)
- WAV (RIFF INFO)
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

logger = logging.getLogger(__name__)


class MetadataExtractionError(Exception):
    """Exception raised when metadata extraction fails."""
    pass


class MetadataExtractor:
    """
    Extract metadata from audio files.
    
    Supports multiple audio formats and handles missing/incomplete metadata gracefully.
    """
    
    # Supported audio formats
    SUPPORTED_FORMATS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}
    
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
    def extract(file_path: Path | str) -> Dict[str, Any]:
        """
        Extract all available metadata from an audio file.
        
        Automatically detects format and uses appropriate extraction method.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary containing all extracted metadata
        
        Raises:
            MetadataExtractionError: If extraction fails
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
            
            # If title is missing, use filename
            if not metadata['title']:
                metadata['title'] = file_path.stem
                logger.debug(f"Using filename as title: {metadata['title']}")
            
            logger.info(f"Successfully extracted metadata from {file_path.name}")
            return metadata
            
        except MetadataExtractionError:
            raise
        except Exception as e:
            raise MetadataExtractionError(f"Metadata extraction failed: {e}")


# Convenience functions

def extract_metadata(file_path: Path | str) -> Dict[str, Any]:
    """
    Extract all metadata from an audio file.
    
    Convenience function that uses MetadataExtractor.
    
    Args:
        file_path: Path to audio file
    
    Returns:
        Dictionary of metadata
    
    Example:
        >>> from src.metadata import extract_metadata
        >>> metadata = extract_metadata("song.mp3")
        >>> print(f"{metadata['artist']} - {metadata['title']}")
    """
    return MetadataExtractor.extract(file_path)


def extract_id3_tags(file_path: Path | str) -> Dict[str, Any]:
    """
    Extract only ID3 tags from MP3 file.
    
    Args:
        file_path: Path to MP3 file
    
    Returns:
        Dictionary of ID3 tag metadata
    """
    return MetadataExtractor.extract_id3_tags(file_path)

