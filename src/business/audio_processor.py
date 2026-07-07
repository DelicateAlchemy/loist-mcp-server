"""
Shared Audio Processing Business Logic (Transport-Agnostic)

This module contains the core audio processing orchestration that can be
called by both MCP tools and A2A handlers. It follows the same 6-stage
pipeline as the original MCP implementation but with no transport dependencies.

Design principles:
- Transport-agnostic (no FastMCP or A2A SDK types)
- Canonical snake_case naming for all fields
- Stable error codes matching MCP ErrorCode enum
- Optional dependency injection for testing
- Support for deterministic audio_id (for "identical results")
"""

import logging
import time
import uuid
import os
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Import existing schemas and error codes
from src.tools.schemas import ErrorCode
from src.schemas.metadata import (
    ProductMetadata,
    FormatMetadata,
    AudioMetadata,
    AudioResources,
)

# Import existing service modules
from src.downloader import (
    download_from_url,
    validate_url,
    validate_ssrf,
    DownloadError,
    DownloadTimeoutError,
    DownloadSizeError,
    URLValidationError,
    SSRFProtectionError,
)
from src.metadata import (
    extract_metadata_with_fallback,
    extract_artwork,
    validate_audio_format,
    parse_filename_metadata,
    enhance_metadata_with_xmp,
    should_attempt_xmp_extraction,
    enhance_metadata_with_bwf,
    should_attempt_bwf_extraction,
    MetadataExtractionError,
    FormatValidationError,
)
from src.metadata.fallback import apply_artist_composer_fallback
from src.storage import upload_audio_file
from database import (
    save_audio_metadata,
    mark_as_processing,
    mark_as_completed,
    mark_as_failed,
)
from src.exceptions import StorageError, DatabaseOperationError

logger = logging.getLogger(__name__)


# ============================================================================
# Shared Request/Result/Error Types (Canonical snake_case)
# ============================================================================

class AudioProcessingRequest(BaseModel):
    """
    Transport-neutral request for audio processing.
    
    Fields use canonical snake_case naming matching existing Pydantic schemas.
    """
    url: str = Field(description="HTTP/HTTPS URL to audio file")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Optional HTTP headers")
    filename: Optional[str] = Field(default=None, description="Optional filename override")
    mime_type: Optional[str] = Field(default=None, description="Optional MIME type hint")
    
    # Processing options (with defaults matching MCP tool)
    max_size_mb: float = Field(default=100.0, description="Maximum file size in MB")
    timeout: int = Field(default=300, description="Download timeout in seconds")
    validate_format: bool = Field(default=True, description="Whether to validate audio format")
    
    # Optional: provide audio_id for deterministic results (same input → same ID)
    audio_id: Optional[str] = Field(default=None, description="Optional audio ID for deterministic processing")

    # Optional: A2A task ID for linking audio tracks to A2A tasks
    a2a_task_id: Optional[str] = Field(default=None, description="A2A task ID for linking audio track to A2A task")

    @field_validator('a2a_task_id')
    @classmethod
    def validate_a2a_task_id(cls, v):
        """Validate that a2a_task_id is a valid UUID format if provided."""
        if v is not None:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError(f"Invalid UUID format for a2a_task_id: {v}")
        return v


class AudioProcessingResult(BaseModel):
    """
    Transport-neutral result from audio processing.
    
    Mirrors the structure of ProcessAudioOutput (snake_case) so both MCP
    and A2A can reuse this data shape end-to-end.
    """
    success: bool = Field(default=True, description="Processing success indicator")
    audio_id: str = Field(description="Unique audio track ID (UUID)")
    metadata: AudioMetadata = Field(description="Complete audio metadata")
    resources: AudioResources = Field(description="Resource URIs")
    processing_time: float = Field(description="Processing time in seconds")


class AudioProcessingError(Exception):
    """
    Shared exception type for audio processing errors.
    
    Uses stable error codes matching MCP's ErrorCode enum and provides
    structured error payload for both MCP and A2A adapters.
    """
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


# ============================================================================
# Resource Management (extracted from process_audio.py)
# ============================================================================

@contextmanager
def managed_temp_files(*temp_paths):
    """
    Context manager for automatic cleanup of temporary files.
    
    Ensures files are deleted even if exceptions occur.
    """
    try:
        yield
    finally:
        for path in temp_paths:
            if path and Path(path).exists():
                try:
                    os.remove(path)
                    logger.debug(f"Cleaned up temporary file: {path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {path}: {e}")


def _extract_filename_from_url(url: str) -> Optional[str]:
    """Extract filename from URL path."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = path.split('/')[-1]
            if '.' in filename and len(filename) > 4:
                return filename
    except Exception:
        pass
    return None


def _validate_metadata_quality_after_enhancement(metadata: Dict[str, Any]) -> None:
    """
    Validate metadata quality after filename parsing enhancement.
    
    Uses adaptive thresholds based on available metadata.
    """
    from src.metadata.extractor import MetadataQualityAssessment
    
    if metadata.get('title'):
        quality_assessment = MetadataQualityAssessment(metadata, Path("/tmp/dummy.mp3"))
        quality_report = quality_assessment.get_quality_report()
        
        logger.info(
            f"Final metadata quality assessment: "
            f"Score={quality_report['quality_score']}, "
            f"Level={quality_report['quality_level']}, "
            f"Completeness={quality_report['metadata_completeness']}%"
        )
        
        if quality_report['quality_score'] < 0.1:
            logger.warning(
                f"Low quality metadata but proceeding: Score={quality_report['quality_score']}, "
                f"Issues={quality_report['issues']}"
            )
        return
    
    logger.error(f"No title found in metadata after all enhancement attempts: {metadata}")
    raise MetadataExtractionError("No title could be determined from file metadata or filename")


class ProcessingPipeline:
    """Manages audio processing pipeline state tracking and cleanup."""
    
    def __init__(self):
        self.audio_id: Optional[str] = None
        self.temp_audio_path: Optional[Path] = None
        self.temp_artwork_path: Optional[Path] = None
        self.gcs_audio_path: Optional[str] = None
        self.gcs_artwork_path: Optional[str] = None
        self.db_committed: bool = False
        
    def cleanup(self):
        """Cleanup temporary files and rollback partial operations."""
        if self.temp_audio_path and self.temp_audio_path.exists():
            try:
                os.remove(self.temp_audio_path)
                logger.debug(f"Cleaned up temp audio: {self.temp_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp audio: {e}")
                
        if self.temp_artwork_path and self.temp_artwork_path.exists():
            try:
                os.remove(self.temp_artwork_path)
                logger.debug(f"Cleaned up temp artwork: {self.temp_artwork_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp artwork: {e}")


# ============================================================================
# Main Shared Processing Function
# ============================================================================

async def process_audio_shared(request: AudioProcessingRequest) -> AudioProcessingResult:
    """
    Shared audio processing orchestration (transport-agnostic).
    
    This function implements the complete 6-stage audio processing pipeline
    without any transport-specific dependencies. Both MCP tools and A2A handlers
    call this function with a standardized request.
    
    Pipeline stages:
    1. Input validation and audio ID generation
    2. HTTP download with SSRF protection
    3. Metadata extraction and artwork
    4. GCS storage upload
    5. Database persistence
    6. Response formatting
    
    Args:
        request: AudioProcessingRequest with URL and processing options
        
    Returns:
        AudioProcessingResult with audio_id, metadata, and resources
        
    Raises:
        AudioProcessingError: On any processing failure with structured error info
    """
    start_time = time.time()
    pipeline = ProcessingPipeline()
    
    try:
        # ====================================================================
        # Stage 1: Input Validation and ID Generation
        # ====================================================================
        logger.info("Starting shared audio processing pipeline")
        
        # Generate or use provided audio ID (for deterministic results)
        if request.audio_id:
            pipeline.audio_id = request.audio_id
            logger.info(f"Using provided audio ID: {pipeline.audio_id}")
        else:
            pipeline.audio_id = str(uuid.uuid4())
            logger.info(f"Generated new audio ID: {pipeline.audio_id}")
        
        # ====================================================================
        # Stage 2: HTTP Download
        # ====================================================================
        logger.info(f"Downloading audio from: {request.url}")
        
        try:
            # Validate URL scheme (http/https only)
            validate_url(request.url)
            
            # SSRF protection check
            validate_ssrf(request.url)
            
            # Download to temporary file
            pipeline.temp_audio_path = Path(download_from_url(
                url=request.url,
                headers=request.headers,
                max_size_mb=request.max_size_mb,
                timeout_seconds=request.timeout,
                filename_override=request.filename
            ))
            
            logger.info(f"Downloaded audio to: {pipeline.temp_audio_path}")
            
        except URLValidationError as e:
            logger.error(f"URL validation failed: {e}")
            raise AudioProcessingError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid URL: {str(e)}",
                retryable=False
            )
        except SSRFProtectionError as e:
            logger.error(f"SSRF protection triggered: {e}")
            raise AudioProcessingError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"URL blocked by security policy: {str(e)}",
                retryable=False
            )
        except DownloadSizeError as e:
            logger.error(f"File too large: {e}")
            raise AudioProcessingError(
                code=ErrorCode.SIZE_EXCEEDED,
                message=str(e),
                details={"max_size_mb": request.max_size_mb},
                retryable=False
            )
        except DownloadTimeoutError as e:
            logger.error(f"Download timeout: {e}")
            raise AudioProcessingError(
                code=ErrorCode.TIMEOUT,
                message=str(e),
                details={"timeout_seconds": request.timeout},
                retryable=True
            )
        except DownloadError as e:
            logger.error(f"Download failed: {e}")
            raise AudioProcessingError(
                code=ErrorCode.FETCH_FAILED,
                message=f"Failed to download audio: {str(e)}",
                retryable=True
            )
        
        # ====================================================================
        # Stage 3: Metadata Extraction
        # ====================================================================
        logger.info("Extracting metadata and artwork")
        
        try:
            # Handle filename override for validation and extraction
            if request.filename:
                filename_suffix = Path(request.filename).suffix
                correct_path = pipeline.temp_audio_path.with_suffix(filename_suffix)
                if pipeline.temp_audio_path.exists() and not correct_path.exists():
                    pipeline.temp_audio_path.rename(correct_path)
                    pipeline.temp_audio_path = correct_path
                    logger.info(f"Renamed temp file to: {correct_path}")
            
            # Validate audio format if enabled
            if request.validate_format:
                if request.filename:
                    provided_ext = Path(request.filename).suffix.lower()
                    if provided_ext not in ['.mp3', '.flac', '.wav', '.aif', '.aiff', '.ogg', '.m4a', '.aac']:
                        validate_audio_format(str(pipeline.temp_audio_path))
                else:
                    validate_audio_format(str(pipeline.temp_audio_path))
            
            # Extract metadata with fallback mechanisms
            metadata_dict, was_repaired = extract_metadata_with_fallback(str(pipeline.temp_audio_path))
            if was_repaired:
                logger.info(f"Metadata was repaired for {pipeline.audio_id}")
            
            # Attempt XMP enhancement for WAV/BWF/AIF files
            if should_attempt_xmp_extraction(str(pipeline.temp_audio_path), metadata_dict):
                logger.info(f"🎵 XMP EXTRACTION: Attempting XMP enhancement")
                try:
                    enhanced_metadata = enhance_metadata_with_xmp(str(pipeline.temp_audio_path), metadata_dict)
                    if enhanced_metadata.get('_xmp_enhanced'):
                        metadata_dict = enhanced_metadata
                        logger.info(f"🎵 XMP EXTRACTION: Enhanced with XMP fields: {enhanced_metadata.get('_xmp_fields', [])}")
                except Exception as e:
                    logger.warning(f"🎵 XMP EXTRACTION: Failed: {e}")
            
            # Attempt BWF enhancement for WAV files
            if should_attempt_bwf_extraction(str(pipeline.temp_audio_path), metadata_dict):
                logger.info(f"🎵 BWF EXTRACTION: Attempting BWF enhancement")
                try:
                    enhanced_metadata = enhance_metadata_with_bwf(str(pipeline.temp_audio_path), metadata_dict)
                    if enhanced_metadata.get('_bwf_enhanced'):
                        metadata_dict = enhanced_metadata
                        logger.info(f"🎵 BWF EXTRACTION: Enhanced with BWF fields: {enhanced_metadata.get('_bwf_fields', [])}")
                except Exception as e:
                    logger.warning(f"🎵 BWF EXTRACTION: Failed: {e}")
            
            # Apply composer→artist fallback if needed
            metadata_dict = apply_artist_composer_fallback(metadata_dict)
            
            # Parse filename for missing metadata fields
            filename_for_parsing = request.filename if request.filename else _extract_filename_from_url(request.url)
            if filename_for_parsing:
                filename_metadata = parse_filename_metadata(Path(filename_for_parsing), metadata_dict)
                if filename_metadata:
                    metadata_dict.update(filename_metadata)
                    logger.info(f"Enhanced metadata from filename: {filename_metadata}")
            
            # Capture original filename for download preservation
            original_filename = None
            if request.filename:
                original_filename = Path(request.filename).name
            elif filename_for_parsing:
                original_filename = Path(filename_for_parsing).name
            
            if original_filename:
                logger.info(f"🎵 FILENAME CAPTURE: Captured original_filename='{original_filename}'")
            
            # Adaptive quality validation
            _validate_metadata_quality_after_enhancement(metadata_dict)
            
            # Extract artwork (optional)
            pipeline.temp_artwork_path = extract_artwork(str(pipeline.temp_audio_path))
            if pipeline.temp_artwork_path:
                pipeline.temp_artwork_path = Path(pipeline.temp_artwork_path)
                logger.info(f"Extracted artwork to: {pipeline.temp_artwork_path}")
            
        except FormatValidationError as e:
            logger.error(f"Invalid audio format: {e}")
            raise AudioProcessingError(
                code=ErrorCode.INVALID_FORMAT,
                message=f"Unsupported or invalid audio format: {str(e)}",
                retryable=False
            )
        except MetadataExtractionError as e:
            logger.error(f"Metadata extraction failed: {e}")
            raise AudioProcessingError(
                code=ErrorCode.EXTRACTION_FAILED,
                message=f"Failed to extract metadata: {str(e)}",
                retryable=False
            )
        
        # ====================================================================
        # Stage 4: GCS Storage Upload
        # ====================================================================
        logger.info("Uploading to Google Cloud Storage")
        
        try:
            # Determine filename
            filename = request.filename or f"{pipeline.audio_id}.{metadata_dict.get('format', 'mp3').lower()}"
            
            # Upload audio file
            blob = upload_audio_file(
                source_path=str(pipeline.temp_audio_path),
                destination_blob_name=f"audio/{pipeline.audio_id}/{filename}",
                metadata={"content_type": request.mime_type or f"audio/{metadata_dict.get('format', 'mp3').lower()}"}
            )
            pipeline.gcs_audio_path = f"gs://{blob.bucket.name}/{blob.name}"
            logger.info(f"Uploaded audio to GCS: {pipeline.gcs_audio_path}")
            
            # Upload artwork if present
            if pipeline.temp_artwork_path:
                artwork_blob = upload_audio_file(
                    source_path=str(pipeline.temp_artwork_path),
                    destination_blob_name=f"audio/{pipeline.audio_id}/artwork.jpg",
                    metadata={"content_type": "image/jpeg"}
                )
                pipeline.gcs_artwork_path = f"gs://{artwork_blob.bucket.name}/{artwork_blob.name}"
                logger.info(f"Uploaded artwork to GCS: {pipeline.gcs_artwork_path}")
            
        except StorageError as e:
            logger.error(f"Storage upload failed: {e}")
            raise AudioProcessingError(
                code=ErrorCode.STORAGE_FAILED,
                message=f"Failed to upload to storage: {str(e)}",
                retryable=True
            )
        
        # ====================================================================
        # Stage 5: Database Persistence
        # ====================================================================
        logger.info("Saving metadata to database")
        
        try:
            # Prepare database record
            db_metadata = {
                "artist": metadata_dict.get("artist", ""),
                "title": metadata_dict.get("title", "Untitled"),
                "album": metadata_dict.get("album", ""),
                "genre": metadata_dict.get("genre"),
                "year": metadata_dict.get("year"),
                "duration_seconds": metadata_dict.get("duration"),
                "channels": metadata_dict.get("channels", 2),
                "sample_rate": metadata_dict.get("sample_rate", 44100),
                "bitrate": metadata_dict.get("bitrate", 0),
                "format": metadata_dict.get("format", ""),
                "composer": metadata_dict.get("composer"),
                "publisher": metadata_dict.get("publisher"),
                "record_label": metadata_dict.get("record_label"),
                "isrc": metadata_dict.get("isrc"),
                "original_filename": original_filename,
            }
            
            # Save to database
            saved_record = save_audio_metadata(
                metadata=db_metadata,
                audio_gcs_path=str(pipeline.gcs_audio_path),
                thumbnail_gcs_path=str(pipeline.gcs_artwork_path) if pipeline.gcs_artwork_path else None,
                track_id=pipeline.audio_id,
                a2a_task_id=request.a2a_task_id
            )
            pipeline.db_committed = True
            
            # Mark as processing first, then completed
            mark_as_processing(pipeline.audio_id)
            mark_as_completed(pipeline.audio_id)
            logger.info(f"Successfully saved metadata for {pipeline.audio_id}")
            
        except DatabaseOperationError as e:
            logger.error(f"Database operation failed: {e}")
            raise AudioProcessingError(
                code=ErrorCode.DATABASE_FAILED,
                message=f"Failed to save metadata: {str(e)}",
                retryable=True
            )
        
        # ====================================================================
        # Stage 6: Response Formatting
        # ====================================================================
        logger.info("Formatting shared response")
        
        # Generate embed URL
        embed_url = f"https://loist.io/embed/{pipeline.audio_id}"
        
        # Ensure required fields are not None
        final_artist = metadata_dict.get("artist") or ""
        final_album = metadata_dict.get("album") or ""
        final_title = metadata_dict.get("title") or "Untitled"
        
        # Build result using canonical snake_case structure
        result = AudioProcessingResult(
            success=True,
            audio_id=pipeline.audio_id,
            metadata=AudioMetadata(
                product=ProductMetadata(
                    artist=final_artist,
                    title=final_title,
                    album=final_album,
                    mbid=None,
                    genre=[metadata_dict.get("genre")] if metadata_dict.get("genre") else [],
                    year=metadata_dict.get("year"),
                    isrc=metadata_dict.get("isrc"),
                ),
                format=FormatMetadata(
                    duration=metadata_dict.get("duration"),
                    channels=metadata_dict.get("channels", 2),
                    sample_rate=metadata_dict.get("sample_rate", 44100),
                    bitrate=metadata_dict.get("bitrate", 0),
                    format=metadata_dict.get("format", "")
                ),
                url_embed_link=embed_url
            ),
            resources=AudioResources(
                audio_url=f"music-library://audio/{pipeline.audio_id}/stream",
                thumbnail_url=f"music-library://audio/{pipeline.audio_id}/thumbnail" if pipeline.gcs_artwork_path else None,
                waveform_url=None
            ),
            processing_time=time.time() - start_time
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Shared audio processing completed in {processing_time:.2f}s")
        
        # Cleanup temporary files (successful path)
        pipeline.cleanup()
        
        return result
        
    except AudioProcessingError:
        # Re-raise our own exceptions
        logger.error(f"Audio processing error in shared layer")
        
        # Mark as failed in database if we have an ID
        if pipeline.audio_id:
            try:
                mark_as_failed(track_id=pipeline.audio_id, error_message="Processing failed")
            except Exception:
                pass
        
        pipeline.cleanup()
        raise
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in shared audio processing: {e}")
        
        # Mark as failed
        if pipeline.audio_id:
            try:
                mark_as_failed(track_id=pipeline.audio_id, error_message=f"Unexpected error: {str(e)}")
            except Exception:
                pass
        
        pipeline.cleanup()
        
        # Wrap in AudioProcessingError
        raise AudioProcessingError(
            code=ErrorCode.FETCH_FAILED,
            message=f"Unexpected error: {str(e)}",
            details={"exception_type": type(e).__name__},
            retryable=False
        )

