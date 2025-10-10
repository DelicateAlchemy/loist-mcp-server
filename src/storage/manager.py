"""
Audio Storage Manager - High-level interface for managing audio file uploads to GCS.

Provides functionality for:
- Unique filename generation using UUIDs
- Structured file organization in GCS
- Audio and thumbnail upload coordination
- Temporary file cleanup
- Retry logic for reliable uploads
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from src.storage.retry import with_retry, RetryConfig, CONSERVATIVE_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class StorageResult:
    """Result of a storage operation containing file metadata and paths."""
    audio_id: str
    audio_gcs_path: str
    thumbnail_gcs_path: Optional[str] = None
    audio_blob_name: str = ""
    thumbnail_blob_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FilenameGenerator:
    """
    Generates unique, collision-resistant filenames for cloud storage.
    
    Uses UUID v4 for unique identifiers, which provides:
    - 122 bits of randomness (extremely low collision probability)
    - No sequential patterns (prevents enumeration attacks)
    - Stateless generation (no coordination required)
    - URL-safe string representation
    
    Best practices implemented:
    - UUID v4 for strong randomness and security
    - Preserves file extensions for proper content-type handling
    - Organized folder structure for scalability
    - Collision detection capability (via GCS existence checks)
    """
    
    @staticmethod
    def generate_audio_id() -> str:
        """
        Generate a unique identifier for an audio file.
        
        Returns:
            UUID v4 string (e.g., "550e8400-e29b-41d4-a716-446655440000")
        
        Notes:
            - UUID v4 provides ~5.3×10^36 possible values
            - Collision probability is negligible for practical purposes
            - More secure than sequential IDs (prevents enumeration)
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_blob_name(
        audio_id: str,
        file_path: Path | str,
        file_type: str = "audio"
    ) -> str:
        """
        Generate a GCS blob name using the unique audio ID and file extension.
        
        Args:
            audio_id: Unique identifier for this audio file
            file_path: Path to the file (used to extract extension)
            file_type: Type of file ("audio" or "thumbnail")
        
        Returns:
            Blob name in format: "audio/{audio_id}/{file_type}.{ext}"
            
        Examples:
            >>> generate_blob_name("abc-123", "/tmp/song.mp3", "audio")
            "audio/abc-123/audio.mp3"
            
            >>> generate_blob_name("abc-123", "/tmp/cover.jpg", "thumbnail")
            "audio/abc-123/thumbnail.jpg"
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        # Extract extension (e.g., ".mp3", ".jpg")
        extension = file_path.suffix.lower()
        
        # Construct blob name with organized structure
        # Format: audio/{uuid}/{type}.{ext}
        blob_name = f"audio/{audio_id}/{file_type}{extension}"
        
        return blob_name
    
    @staticmethod
    def generate_thumbnail_blob_name(audio_id: str, extension: str = ".jpg") -> str:
        """
        Generate a blob name for a thumbnail/artwork image.
        
        Args:
            audio_id: Unique identifier for the parent audio file
            extension: Image file extension (default: ".jpg")
        
        Returns:
            Blob name for the thumbnail
            
        Example:
            >>> generate_thumbnail_blob_name("abc-123")
            "audio/abc-123/thumbnail.jpg"
        """
        # Ensure extension starts with a dot
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        return f"audio/{audio_id}/thumbnail{extension}"
    
    @staticmethod
    def parse_audio_id_from_blob_name(blob_name: str) -> Optional[str]:
        """
        Extract the audio ID from a blob name.
        
        Args:
            blob_name: GCS blob name (e.g., "audio/abc-123/audio.mp3")
        
        Returns:
            Audio ID if found, None otherwise
            
        Example:
            >>> parse_audio_id_from_blob_name("audio/abc-123/audio.mp3")
            "abc-123"
        """
        try:
            parts = blob_name.split('/')
            if len(parts) >= 2 and parts[0] == 'audio':
                return parts[1]
        except Exception as e:
            logger.warning(f"Failed to parse audio ID from blob name: {blob_name}, error: {e}")
        
        return None
    
    @staticmethod
    def validate_uuid(audio_id: str) -> bool:
        """
        Validate that a string is a valid UUID.
        
        Args:
            audio_id: String to validate
        
        Returns:
            True if valid UUID, False otherwise
        """
        try:
            uuid.UUID(audio_id)
            return True
        except (ValueError, AttributeError):
            return False


class FileOrganizer:
    """
    Manages the file organization structure in Google Cloud Storage.
    
    Organization strategy:
    - Root folder: "audio/"
    - Each upload gets a unique UUID folder: "audio/{uuid}/"
    - Audio file: "audio/{uuid}/audio.{ext}"
    - Thumbnail: "audio/{uuid}/thumbnail.{ext}"
    
    Benefits:
    - Easy to locate all files for a single audio upload
    - Simple cleanup (delete entire folder)
    - Scalable (no flat directory with millions of files)
    - Supports future additions (lyrics, waveforms, etc.)
    """
    
    AUDIO_ROOT = "audio"
    AUDIO_FILENAME = "audio"
    THUMBNAIL_FILENAME = "thumbnail"
    
    @classmethod
    def get_folder_structure(cls, audio_id: str) -> Dict[str, str]:
        """
        Get the folder structure paths for an audio ID.
        
        Args:
            audio_id: Unique identifier
        
        Returns:
            Dictionary with folder paths:
            - "root": Root audio folder
            - "audio_folder": Folder for this specific audio
            - "audio_prefix": Prefix for listing files
        """
        return {
            "root": cls.AUDIO_ROOT,
            "audio_folder": f"{cls.AUDIO_ROOT}/{audio_id}",
            "audio_prefix": f"{cls.AUDIO_ROOT}/{audio_id}/",
        }
    
    @classmethod
    def get_expected_files(cls, audio_id: str, audio_ext: str = ".mp3", has_thumbnail: bool = True) -> Dict[str, str]:
        """
        Get the expected file paths for an audio upload.
        
        Args:
            audio_id: Unique identifier
            audio_ext: Audio file extension
            has_thumbnail: Whether to include thumbnail path
        
        Returns:
            Dictionary with expected file paths
        """
        paths = {
            "audio": f"{cls.AUDIO_ROOT}/{audio_id}/{cls.AUDIO_FILENAME}{audio_ext}",
        }
        
        if has_thumbnail:
            paths["thumbnail"] = f"{cls.AUDIO_ROOT}/{audio_id}/{cls.THUMBNAIL_FILENAME}.jpg"
        
        return paths
    
    @classmethod
    def format_gcs_uri(cls, bucket_name: str, blob_name: str) -> str:
        """
        Format a GCS URI from bucket and blob name.
        
        Args:
            bucket_name: GCS bucket name
            blob_name: Blob path within bucket
        
        Returns:
            Full GCS URI (gs://bucket/path)
        """
        return f"gs://{bucket_name}/{blob_name}"


class AudioStorageManager:
    """
    High-level manager for audio file storage operations.
    
    Coordinates the complete upload workflow:
    1. Generate unique identifiers
    2. Upload audio files to GCS with proper organization
    3. Upload thumbnails/artwork
    4. Handle errors and retries
    5. Clean up temporary files
    6. Return structured results
    
    Usage:
        manager = AudioStorageManager(bucket_name="my-bucket")
        result = manager.upload_audio("/tmp/song.mp3", "/tmp/artwork.jpg")
        print(f"Audio uploaded: {result.audio_gcs_path}")
    """
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize the audio storage manager.
        
        Args:
            bucket_name: GCS bucket name (defaults to env var or config)
            project_id: GCP project ID
            credentials_path: Path to service account credentials
            retry_config: Custom retry configuration (uses CONSERVATIVE_CONFIG if not provided)
        """
        # Import here to avoid circular dependency
        from src.storage.gcs_client import GCSClient
        
        self.gcs_client = GCSClient(
            bucket_name=bucket_name,
            project_id=project_id,
            credentials_path=credentials_path,
        )
        
        self.filename_generator = FilenameGenerator()
        self.file_organizer = FileOrganizer()
        self.retry_config = retry_config or CONSERVATIVE_CONFIG
        
        logger.info(
            f"Initialized AudioStorageManager for bucket: {self.gcs_client.bucket_name} "
            f"with retry config (max_attempts={self.retry_config.max_attempts})"
        )
    
    def _upload_file_with_retry(
        self,
        source_path: Path,
        blob_name: str,
        content_type: str,
        metadata: Dict[str, str],
        operation_name: str,
    ):
        """
        Internal method to upload a file with retry logic.
        
        Args:
            source_path: Local file path
            blob_name: Destination blob name in GCS
            content_type: MIME type
            metadata: File metadata
            operation_name: Operation name for logging
        
        Returns:
            Uploaded blob object
        """
        # Create a wrapped upload function with retry logic
        @with_retry(config=self.retry_config, operation_name=operation_name)
        def _do_upload():
            return self.gcs_client.upload_file(
                source_path=source_path,
                destination_blob_name=blob_name,
                content_type=content_type,
                metadata=metadata,
            )
        
        return _do_upload()
    
    def _cleanup_file(self, file_path: Path, file_description: str = "file") -> bool:
        """
        Safely delete a file with error handling.
        
        Args:
            file_path: Path to file to delete
            file_description: Description for logging (e.g., "audio file", "thumbnail")
        
        Returns:
            True if deleted successfully, False if failed
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up temporary {file_description}: {file_path}")
                return True
            else:
                logger.debug(f"Temporary {file_description} already removed: {file_path}")
                return True
        except PermissionError as e:
            logger.warning(f"Permission denied when cleaning up {file_description} {file_path}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary {file_description} {file_path}: {e}")
            return False
    
    def upload_audio_file(
        self,
        source_path: Path | str,
        audio_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        cleanup: bool = False,
    ) -> StorageResult:
        """
        Upload an audio file to GCS with proper organization and error handling.
        
        Args:
            source_path: Path to the local audio file
            audio_id: Optional pre-generated audio ID (generates new UUID if not provided)
            metadata: Optional custom metadata to attach to the file
            cleanup: If True, delete the local file after successful upload
        
        Returns:
            StorageResult with upload details and GCS paths
        
        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If file format is not supported
            GoogleCloudError: If upload fails after retries
            
        Example:
            >>> manager = AudioStorageManager()
            >>> result = manager.upload_audio_file("/tmp/song.mp3")
            >>> print(result.audio_gcs_path)
            "gs://my-bucket/audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3"
        """
        source_path = Path(source_path) if isinstance(source_path, str) else source_path
        
        # Validate source file exists
        if not source_path.exists():
            raise FileNotFoundError(f"Audio file not found: {source_path}")
        
        # Validate file extension
        supported_extensions = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'}
        if source_path.suffix.lower() not in supported_extensions:
            raise ValueError(
                f"Unsupported audio format: {source_path.suffix}. "
                f"Supported formats: {', '.join(supported_extensions)}"
            )
        
        # Generate or use provided audio ID
        if audio_id is None:
            audio_id = self.filename_generator.generate_audio_id()
            logger.info(f"Generated new audio ID: {audio_id}")
        else:
            # Validate provided UUID
            if not self.filename_generator.validate_uuid(audio_id):
                raise ValueError(f"Invalid UUID format: {audio_id}")
            logger.info(f"Using provided audio ID: {audio_id}")
        
        # Generate blob name using organized structure
        blob_name = self.filename_generator.generate_blob_name(
            audio_id=audio_id,
            file_path=source_path,
            file_type="audio"
        )
        
        logger.info(f"Uploading audio: {source_path} -> {blob_name}")
        
        try:
            # Determine content type from extension
            content_type_map = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.flac': 'audio/flac',
                '.ogg': 'audio/ogg',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
            }
            content_type = content_type_map.get(source_path.suffix.lower(), 'audio/mpeg')
            
            # Add default metadata
            upload_metadata = {
                'audio_id': audio_id,
                'original_filename': source_path.name,
                'file_size': str(source_path.stat().st_size),
            }
            
            # Merge with custom metadata if provided
            if metadata:
                upload_metadata.update(metadata)
            
            # Upload file to GCS with retry logic
            blob = self._upload_file_with_retry(
                source_path=source_path,
                blob_name=blob_name,
                content_type=content_type,
                metadata=upload_metadata,
                operation_name=f"upload_audio_{audio_id}",
            )
            
            # Format GCS URI
            gcs_path = self.file_organizer.format_gcs_uri(
                bucket_name=self.gcs_client.bucket_name,
                blob_name=blob_name
            )
            
            logger.info(f"Successfully uploaded audio: {gcs_path}")
            
            # Cleanup temporary file if requested
            if cleanup:
                self._cleanup_file(source_path, "audio file")
            
            # Return structured result
            return StorageResult(
                audio_id=audio_id,
                audio_gcs_path=gcs_path,
                audio_blob_name=blob_name,
                metadata={
                    'size': blob.size,
                    'content_type': blob.content_type,
                    'md5_hash': blob.md5_hash,
                    'generation': blob.generation,
                }
            )
            
        except FileNotFoundError:
            logger.error(f"File disappeared during upload: {source_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to upload audio file {source_path}: {e}")
            raise
    
    def upload_thumbnail_file(
        self,
        source_path: Path | str,
        audio_id: str,
        metadata: Optional[Dict[str, str]] = None,
        cleanup: bool = False,
    ) -> StorageResult:
        """
        Upload a thumbnail/artwork image to GCS for an audio file.
        
        Args:
            source_path: Path to the local thumbnail/artwork image
            audio_id: Audio ID this thumbnail belongs to (must be valid UUID)
            metadata: Optional custom metadata to attach to the file
            cleanup: If True, delete the local file after successful upload
        
        Returns:
            StorageResult with upload details and GCS paths
        
        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If file format is not supported or audio_id is invalid
            GoogleCloudError: If upload fails after retries
            
        Example:
            >>> manager = AudioStorageManager()
            >>> result = manager.upload_thumbnail_file(
            ...     "/tmp/artwork.jpg",
            ...     "550e8400-e29b-41d4-a716-446655440000"
            ... )
            >>> print(result.thumbnail_gcs_path)
            "gs://my-bucket/audio/550e8400-e29b-41d4-a716-446655440000/thumbnail.jpg"
        """
        source_path = Path(source_path) if isinstance(source_path, str) else source_path
        
        # Validate source file exists
        if not source_path.exists():
            raise FileNotFoundError(f"Thumbnail file not found: {source_path}")
        
        # Validate audio_id is a valid UUID
        if not self.filename_generator.validate_uuid(audio_id):
            raise ValueError(f"Invalid UUID format for audio_id: {audio_id}")
        
        # Validate file extension
        supported_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        if source_path.suffix.lower() not in supported_extensions:
            raise ValueError(
                f"Unsupported image format: {source_path.suffix}. "
                f"Supported formats: {', '.join(supported_extensions)}"
            )
        
        # Generate blob name using thumbnail naming convention
        blob_name = self.filename_generator.generate_thumbnail_blob_name(
            audio_id=audio_id,
            extension=source_path.suffix.lower()
        )
        
        logger.info(f"Uploading thumbnail: {source_path} -> {blob_name}")
        
        try:
            # Determine content type from extension
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
            }
            content_type = content_type_map.get(source_path.suffix.lower(), 'image/jpeg')
            
            # Add default metadata
            upload_metadata = {
                'audio_id': audio_id,
                'original_filename': source_path.name,
                'file_size': str(source_path.stat().st_size),
                'file_type': 'thumbnail',
            }
            
            # Merge with custom metadata if provided
            if metadata:
                upload_metadata.update(metadata)
            
            # Upload file to GCS with retry logic
            blob = self._upload_file_with_retry(
                source_path=source_path,
                blob_name=blob_name,
                content_type=content_type,
                metadata=upload_metadata,
                operation_name=f"upload_thumbnail_{audio_id}",
            )
            
            # Format GCS URI
            gcs_path = self.file_organizer.format_gcs_uri(
                bucket_name=self.gcs_client.bucket_name,
                blob_name=blob_name
            )
            
            logger.info(f"Successfully uploaded thumbnail: {gcs_path}")
            
            # Cleanup temporary file if requested
            if cleanup:
                self._cleanup_file(source_path, "thumbnail file")
            
            # Return structured result
            return StorageResult(
                audio_id=audio_id,
                audio_gcs_path="",  # Not applicable for thumbnail-only upload
                thumbnail_gcs_path=gcs_path,
                thumbnail_blob_name=blob_name,
                metadata={
                    'size': blob.size,
                    'content_type': blob.content_type,
                    'md5_hash': blob.md5_hash,
                    'generation': blob.generation,
                }
            )
            
        except FileNotFoundError:
            logger.error(f"File disappeared during upload: {source_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to upload thumbnail file {source_path}: {e}")
            raise
    
    def upload_audio_with_thumbnail(
        self,
        audio_path: Path | str,
        thumbnail_path: Optional[Path | str] = None,
        audio_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        cleanup: bool = False,
    ) -> StorageResult:
        """
        Upload an audio file and optional thumbnail together.
        
        This is the recommended method for uploading a complete audio entry
        with its associated artwork in a single operation.
        
        Args:
            audio_path: Path to the local audio file
            thumbnail_path: Optional path to thumbnail/artwork image
            audio_id: Optional pre-generated audio ID (generates new UUID if not provided)
            metadata: Optional custom metadata to attach to both files
            cleanup: If True, delete local files after successful upload
        
        Returns:
            StorageResult with both audio and thumbnail paths
        
        Raises:
            FileNotFoundError: If source files don't exist
            ValueError: If file formats are not supported
            GoogleCloudError: If upload fails after retries
            
        Example:
            >>> manager = AudioStorageManager()
            >>> result = manager.upload_audio_with_thumbnail(
            ...     "/tmp/song.mp3",
            ...     "/tmp/artwork.jpg"
            ... )
            >>> print(f"Audio: {result.audio_gcs_path}")
            >>> print(f"Thumbnail: {result.thumbnail_gcs_path}")
        """
        # Upload audio first (this generates the audio_id if not provided)
        audio_result = self.upload_audio_file(
            source_path=audio_path,
            audio_id=audio_id,
            metadata=metadata,
            cleanup=cleanup,
        )
        
        # Upload thumbnail if provided
        if thumbnail_path:
            thumbnail_result = self.upload_thumbnail_file(
                source_path=thumbnail_path,
                audio_id=audio_result.audio_id,
                metadata=metadata,
                cleanup=cleanup,
            )
            
            # Combine results
            return StorageResult(
                audio_id=audio_result.audio_id,
                audio_gcs_path=audio_result.audio_gcs_path,
                audio_blob_name=audio_result.audio_blob_name,
                thumbnail_gcs_path=thumbnail_result.thumbnail_gcs_path,
                thumbnail_blob_name=thumbnail_result.thumbnail_blob_name,
                metadata={
                    **audio_result.metadata,
                    'has_thumbnail': True,
                }
            )
        else:
            # No thumbnail, return audio result only
            audio_result.metadata['has_thumbnail'] = False
            return audio_result


# For subtask 5.1, we've implemented:
# 1. FilenameGenerator class with UUID v4 generation
# 2. Collision-resistant unique ID generation
# 3. Blob name generation preserving file extensions
# 4. Security considerations (non-sequential IDs prevent enumeration)
# 5. Validation and parsing utilities

# For subtask 5.3, we've implemented:
# 1. AudioStorageManager class for coordinating uploads
# 2. upload_audio_file() method with comprehensive error handling
# 3. File validation (existence, supported formats)
# 4. UUID generation and validation
# 5. Metadata attachment to uploaded files
# 6. Structured result object (StorageResult)
# 7. Proper content-type detection from file extensions
# 8. Detailed logging for debugging and auditing

# For subtask 5.4, we've implemented:
# 1. upload_thumbnail_file() method for artwork/image uploads
# 2. Support for multiple image formats (.jpg, .jpeg, .png, .webp)
# 3. Validation of audio_id before thumbnail upload
# 4. Content-type detection for image formats
# 5. Metadata tagging (audio_id, file_type, etc.)
# 6. upload_audio_with_thumbnail() convenience method
# 7. Combined result with both audio and thumbnail paths
# 8. Proper handling of optional thumbnail uploads

# For subtask 5.6, we've implemented:
# 1. _cleanup_file() private method for safe file deletion
# 2. Error handling for cleanup (PermissionError, etc.)
# 3. Optional 'cleanup' parameter in all upload methods
# 4. Cleanup only happens after successful upload
# 5. Failed cleanup doesn't break the upload operation
# 6. Detailed logging of cleanup operations
# 7. Cleanup applies to both audio and thumbnail files
# 8. Cleanup in upload_audio_with_thumbnail() handles both files

# The implementation follows best practices:
# - UUID v4 for strong randomness (122 bits)
# - Preserves original file extensions
# - Clear, documented structure
# - Helper methods for validation and parsing
# - Comprehensive docstrings
# - Proper error handling with informative messages
# - Coordinated uploads for related files
# - Safe cleanup that doesn't interfere with upload success

