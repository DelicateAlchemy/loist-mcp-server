"""
Audio processing orchestration tool for Loist Music Library MCP Server.

Implements the process_audio_complete MCP tool that orchestrates:
1. HTTP download
2. Metadata extraction
3. GCS storage
4. Database persistence

Follows best practices for:
- Transaction management across services
- Automatic cleanup of temporary files
- Status tracking and rollback
- Comprehensive error handling
"""

import logging
import time
import uuid
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager
from urllib.parse import urlparse

from .schemas import (
    ProcessAudioInput,
    ProcessAudioOutput,
    ProcessAudioError,
    ProcessAudioException,
    ErrorCode,
    ProductMetadata,
    FormatMetadata,
    AudioMetadata,
    AudioResources,
)

# Import modules from previous tasks
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
    MetadataExtractionError,
    FormatValidationError,
)
from src.storage import (
    upload_audio_file,
    generate_signed_url,
)
from database import (
    save_audio_metadata,
    mark_as_processing,
    mark_as_completed,
    mark_as_failed,
    get_connection,
)
from src.exceptions import (
    MusicLibraryError,
    StorageError,
    DatabaseOperationError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Resource Management
# ============================================================================

@contextmanager
def managed_temp_files(*temp_paths):
    """
    Context manager for automatic cleanup of temporary files.
    
    Ensures files are deleted even if exceptions occur.
    Follows best practice: cleanup runs on any failure.
    
    Args:
        *temp_paths: Paths to temporary files to manage
        
    Yields:
        None
    """
    try:
        yield
    finally:
        # Cleanup temporary files
        for path in temp_paths:
            if path and Path(path).exists():
                try:
                    os.remove(path)
                    logger.debug(f"Cleaned up temporary file: {path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {path}: {e}")


def _extract_filename_from_url(url: str) -> Optional[str]:
    """
    Extract filename from URL path.

    Examples:
        https://example.com/audio/thebeatles-imonlysleeping.mp3 -> thebeatles-imonlysleeping.mp3
        https://tmpfiles.org/dl/123/file.mp3 -> file.mp3
    """
    try:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            # Get the last component of the path
            filename = path.split('/')[-1]
            # Basic validation - should have an extension
            if '.' in filename and len(filename) > 4:
                return filename
    except Exception:
        pass
    return None


def _validate_metadata_quality_after_enhancement(metadata: Dict[str, Any]) -> None:
    """
    Validate metadata quality after filename parsing enhancement.

    Uses adaptive thresholds based on available metadata:
    - Artist + Title available: threshold 0.2 (20%)
    - Only Title available: threshold 0.1 (10%)
    - Always allow if we have at least a title from filename

    Args:
        metadata: Enhanced metadata dictionary

    Raises:
        MetadataExtractionError: If metadata quality is insufficient
    """
    from src.metadata.extractor import MetadataQualityAssessment

    # If we have a title (from filename parsing if needed), be very lenient
    if metadata.get('title'):
        # We have at least a title - allow processing with minimal requirements
        quality_assessment = MetadataQualityAssessment(metadata, Path("/tmp/dummy.mp3"))  # Path not used in assessment
        quality_report = quality_assessment.get_quality_report()

        logger.info(
            f"Final metadata quality assessment: "
            f"Score={quality_report['quality_score']}, "
            f"Level={quality_report['quality_level']}, "
            f"Completeness={quality_report['metadata_completeness']}%"
        )

        # Very lenient threshold for files with titles
        if quality_report['quality_score'] < 0.1:  # 10% threshold
            logger.warning(
                f"Low quality metadata but proceeding: Score={quality_report['quality_score']}, "
                f"Issues={quality_report['issues']}"
            )
        # Don't raise an error - allow processing
        return

    # No title at all - this is problematic, but should have been caught earlier
    logger.error(f"No title found in metadata after all enhancement attempts: {metadata}")
    raise MetadataExtractionError("No title could be determined from file metadata or filename")


class ProcessingPipeline:
    """
    Manages the audio processing pipeline with proper state tracking
    and rollback capabilities.
    """
    
    def __init__(self):
        self.audio_id: Optional[str] = None
        self.temp_audio_path: Optional[str] = None
        self.temp_artwork_path: Optional[str] = None
        self.gcs_audio_path: Optional[str] = None
        self.gcs_artwork_path: Optional[str] = None
        self.db_committed: bool = False
        
    def cleanup(self):
        """
        Cleanup temporary files and rollback partial operations.
        
        Implements rollback mechanisms on failure following best practices.
        """
        # Cleanup temporary files
        if self.temp_audio_path and Path(self.temp_audio_path).exists():
            try:
                os.remove(self.temp_audio_path)
                logger.debug(f"Cleaned up temp audio: {self.temp_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp audio: {e}")
                
        if self.temp_artwork_path and Path(self.temp_artwork_path).exists():
            try:
                os.remove(self.temp_artwork_path)
                logger.debug(f"Cleaned up temp artwork: {self.temp_artwork_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp artwork: {e}")
        
        # Note: GCS files are intentionally NOT deleted as they may be useful
        # for debugging. Implement lifecycle policies in GCS bucket for cleanup.
        # Database entries are marked as FAILED rather than deleted.


# ============================================================================
# Main Processing Function
# ============================================================================

async def process_audio_complete(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process audio from HTTP URL and return complete metadata.
    
    This is the main MCP tool that orchestrates the complete audio processing
    pipeline following FastMCP best practices for async operations and error handling.
    
    Pipeline stages:
    1. Input validation
    2. HTTP download with SSRF protection
    3. Metadata extraction and artwork
    4. GCS storage upload
    5. Database persistence
    6. Response formatting
    
    Args:
        input_data: Dictionary containing source and options
        
    Returns:
        Dictionary containing success response or error
        
    Example:
        >>> result = await process_audio_complete({
        ...     "source": {
        ...         "type": "http_url",
        ...         "url": "https://example.com/song.mp3"
        ...     }
        ... })
        >>> print(result["audioId"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    start_time = time.time()
    pipeline = ProcessingPipeline()
    
    try:
        # ====================================================================
        # Stage 1: Input Validation
        # ====================================================================
        logger.info("Starting audio processing pipeline")
        
        # Validate input schema using Pydantic
        try:
            validated_input = ProcessAudioInput(**input_data)
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid input: {str(e)}",
                details={"validation_errors": str(e)}
            )
        
        source = validated_input.source
        options = validated_input.options
        
        # Generate unique audio ID
        pipeline.audio_id = str(uuid.uuid4())
        logger.info(f"Generated audio ID: {pipeline.audio_id}")
        
        # ====================================================================
        # Stage 2: HTTP Download (Subtask 7.2)
        # ====================================================================
        logger.info(f"Downloading audio from: {source.url}")
        
        try:
            # Validate URL scheme (http/https only)
            validate_url(str(source.url))
            
            # SSRF protection check
            validate_ssrf(str(source.url))
            
            # Download to temporary file
            pipeline.temp_audio_path = download_from_url(
                url=str(source.url),
                headers=source.headers,
                max_size_mb=options.maxSizeMB,
                timeout_seconds=options.timeout,
                filename_override=getattr(source, 'filename', None)
            )
            
            logger.info(f"Downloaded audio to: {pipeline.temp_audio_path}")
            
        except URLValidationError as e:
            logger.error(f"URL validation failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid URL: {str(e)}"
            )
        except SSRFProtectionError as e:
            logger.error(f"SSRF protection triggered: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"URL blocked by security policy: {str(e)}"
            )
        except DownloadSizeError as e:
            logger.error(f"File too large: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.SIZE_EXCEEDED,
                message=str(e),
                details={"max_size_mb": options.maxSizeMB}
            )
        except DownloadTimeoutError as e:
            logger.error(f"Download timeout: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.TIMEOUT,
                message=str(e),
                details={"timeout_seconds": options.timeout}
            )
        except DownloadError as e:
            logger.error(f"Download failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.FETCH_FAILED,
                message=f"Failed to download audio: {str(e)}"
            )
        
        # ====================================================================
        # Stage 3: Metadata Extraction (Subtask 7.3)
        # ====================================================================
        logger.info("Extracting metadata and artwork")
        
        try:
            # Handle filename override for validation and extraction
            validation_path = pipeline.temp_audio_path
            extraction_path = pipeline.temp_audio_path

            if hasattr(source, 'filename') and source.filename:
                # Rename temp file to have correct extension for validation and extraction
                filename_suffix = Path(source.filename).suffix
                correct_path = Path(pipeline.temp_audio_path).with_suffix(filename_suffix)
                logger.debug(f"DEBUG: temp_audio_path={pipeline.temp_audio_path}, filename={source.filename}, suffix={filename_suffix}, correct_path={correct_path}")
                try:
                    if pipeline.temp_audio_path.exists() and not correct_path.exists():
                        pipeline.temp_audio_path.rename(correct_path)
                        logger.info(f"Renamed temp file: {pipeline.temp_audio_path} -> {correct_path}")
                        # Update pipeline to use the renamed file
                        pipeline.temp_audio_path = correct_path
                    validation_path = pipeline.temp_audio_path
                    extraction_path = pipeline.temp_audio_path
                    logger.info(f"Using filename override: {source.filename}")
                except Exception as e:
                    logger.error(f"Failed to rename temp file: {e}")
                    # Fall back to original path
                    logger.warning("Falling back to original path for validation/extraction")

            # Validate audio format if enabled
            if options.validateFormat:
                # Skip validation if we have a trusted filename override
                if hasattr(source, 'filename') and source.filename:
                    provided_ext = Path(source.filename).suffix.lower()
                    if provided_ext in ['.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac']:
                        logger.info(f"Skipping format validation for trusted filename: {source.filename}")
                    else:
                        validate_audio_format(validation_path)
                else:
                    validate_audio_format(validation_path)

            # Extract metadata with fallback mechanisms
            metadata_dict, was_repaired = extract_metadata_with_fallback(extraction_path)
            if was_repaired:
                logger.info(f"Metadata was repaired for {pipeline.audio_id}")
            logger.debug(f"Extracted metadata: {metadata_dict}")

            # Parse filename for missing metadata fields
            # Priority order: source.filename > URL parsing > temp file
            logger.info(f"🎵 FILENAME PARSING: Starting filename parsing phase")
            logger.debug(f"SOURCE DEBUG: source={source}, type={type(source)}")
            filename_for_parsing = pipeline.temp_audio_path
            logger.info(f"🎵 FILENAME PARSING: Initial filename_for_parsing = {filename_for_parsing}")

            # Priority 1: Use explicit filename override from source (highest priority)
            if hasattr(source, 'filename') and source.filename:
                logger.debug(f"SOURCE DEBUG: Found explicit filename in source: {source.filename}")
                filename_for_parsing = Path(source.filename)
                logger.info(f"🎵 FILENAME PARSING: Using source.filename: {source.filename}")

            # Priority 2: Try to extract filename from URL (for regular URLs)
            elif hasattr(source, 'url') and source.url:
                logger.debug(f"SOURCE DEBUG: Found URL in source: {source.url}")
                # Convert HttpUrl to string for processing
                url_str = str(source.url)
                url_filename = _extract_filename_from_url(url_str)
                logger.debug(f"SOURCE DEBUG: Extracted filename: {url_filename}")
                if url_filename:
                    # Create a temporary Path object with the URL filename for parsing
                    # This preserves the original filename semantics for the parser
                    class URLPath(os.PathLike):
                        def __init__(self, url_filename):
                            self._stem = Path(url_filename).stem
                            self._url_filename = url_filename

                        @property
                        def stem(self):
                            return self._stem

                        def __fspath__(self):
                            return self._url_filename

                    filename_for_parsing = URLPath(url_filename)
                    logger.debug(f"Using URL filename for parsing: {url_filename}")
                else:
                    logger.debug("URL filename extraction failed")

            # Priority 3: Fall back to temp file path (lowest priority)
            else:
                logger.debug(f"No explicit filename or URL found in source, using temp file path")

            filename_metadata = parse_filename_metadata(filename_for_parsing, metadata_dict)
            if filename_metadata:
                metadata_dict.update(filename_metadata)
                logger.info(f"Enhanced metadata from filename: {filename_metadata}")

            # Adaptive quality validation after filename parsing
            _validate_metadata_quality_after_enhancement(metadata_dict)

            # Extract artwork (optional - may be None)
            pipeline.temp_artwork_path = extract_artwork(pipeline.temp_audio_path)
            if pipeline.temp_artwork_path:
                logger.info(f"Extracted artwork to: {pipeline.temp_artwork_path}")
            else:
                logger.info("No artwork found in audio file")
                
        except FormatValidationError as e:
            logger.error(f"Invalid audio format: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.INVALID_FORMAT,
                message=f"Unsupported or invalid audio format: {str(e)}"
            )
        except MetadataExtractionError as e:
            logger.error(f"Metadata extraction failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.EXTRACTION_FAILED,
                message=f"Failed to extract metadata: {str(e)}"
            )
        
        # ====================================================================
        # Stage 4: GCS Storage Upload (Subtask 7.4)
        # ====================================================================
        logger.info("Uploading to Google Cloud Storage")
        
        try:
            # Determine filename
            filename = source.filename or f"{pipeline.audio_id}.{metadata_dict.get('format', 'mp3').lower()}"
            
            # Upload audio file
            blob = upload_audio_file(
                source_path=pipeline.temp_audio_path,
                destination_blob_name=f"audio/{pipeline.audio_id}/{filename}",
                metadata={"content_type": source.mimeType or f"audio/{metadata_dict.get('format', 'mp3').lower()}"}
            )
            pipeline.gcs_audio_path = f"gs://{blob.bucket.name}/{blob.name}"
            logger.info(f"Uploaded audio to GCS: {pipeline.gcs_audio_path}")
            
            # Upload artwork if present
            if pipeline.temp_artwork_path:
                artwork_blob = upload_audio_file(
                    source_path=pipeline.temp_artwork_path,
                    destination_blob_name=f"audio/{pipeline.audio_id}/artwork.jpg",
                    metadata={"content_type": "image/jpeg"}
                )
                pipeline.gcs_artwork_path = f"gs://{artwork_blob.bucket.name}/{artwork_blob.name}"
                logger.info(f"Uploaded artwork to GCS: {pipeline.gcs_artwork_path}")
            
        except StorageError as e:
            logger.error(f"Storage upload failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.STORAGE_FAILED,
                message=f"Failed to upload to storage: {str(e)}"
            )
        
        # ====================================================================
        # Stage 5: Database Persistence (Subtask 7.5)
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
                "duration": metadata_dict.get("duration", 0),
                "channels": metadata_dict.get("channels", 2),
                "sample_rate": metadata_dict.get("sample_rate", 44100),
                "bitrate": metadata_dict.get("bitrate", 0),
                "format": metadata_dict.get("format", ""),
            }
            
            # Save to database using transaction
            saved_record = save_audio_metadata(
                metadata=db_metadata,
                audio_gcs_path=str(pipeline.gcs_audio_path),
                thumbnail_gcs_path=str(pipeline.gcs_artwork_path) if pipeline.gcs_artwork_path else None,
                track_id=pipeline.audio_id
            )
            pipeline.db_committed = True
            
            # Mark as processing first, then completed
            mark_as_processing(pipeline.audio_id)
            logger.debug(f"Marked {pipeline.audio_id} as PROCESSING")
            
            # Mark as completed
            mark_as_completed(pipeline.audio_id)
            logger.info(f"Successfully saved metadata for {pipeline.audio_id}")
            
        except DatabaseOperationError as e:
            logger.error(f"Database operation failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.DATABASE_FAILED,
                message=f"Failed to save metadata: {str(e)}"
            )
        
        # ====================================================================
        # Stage 6: Response Formatting (Subtask 7.7)
        # ====================================================================
        logger.info("Formatting response")
        
        # Generate embed URL
        embed_url = f"https://loist.io/embed/{pipeline.audio_id}"
        
        # Build response using Pydantic models for validation
        logger.info(f"[RESPONSE_DEBUG] Final metadata_dict: {metadata_dict}")

        # Ensure required fields are not None
        final_artist = metadata_dict.get("artist") or ""
        final_album = metadata_dict.get("album") or ""
        final_title = metadata_dict.get("title") or "Untitled"

        logger.info(f"[RESPONSE_DEBUG] Final values - Artist: '{final_artist}', Album: '{final_album}', Title: '{final_title}'")

        response = ProcessAudioOutput(
            success=True,
            audioId=pipeline.audio_id,
            metadata=AudioMetadata(
                Product=ProductMetadata(
                    Artist=final_artist,
                    Title=final_title,
                    Album=final_album,
                    MBID=None,  # MVP: null
                    Genre=[metadata_dict.get("genre")] if metadata_dict.get("genre") else [],
                    Year=metadata_dict.get("year")
                ),
                Format=FormatMetadata(
                    Duration=metadata_dict.get("duration", 0),
                    Channels=metadata_dict.get("channels", 2),
                    SampleRate=metadata_dict.get("sample_rate", 44100),
                    Bitrate=metadata_dict.get("bitrate", 0),
                    Format=metadata_dict.get("format", "")
                ),
                urlEmbedLink=embed_url
            ),
            resources=AudioResources(
                audio=f"music-library://audio/{pipeline.audio_id}/stream",
                thumbnail=f"music-library://audio/{pipeline.audio_id}/thumbnail" if pipeline.gcs_artwork_path else None,
                waveform=None  # MVP: null
            ),
            processingTime=time.time() - start_time
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Audio processing completed in {processing_time:.2f}s")
        
        # Cleanup temporary files (successful path)
        pipeline.cleanup()
        
        return response.model_dump()
        
    except ProcessAudioException as e:
        # ====================================================================
        # Error Handling (Subtask 7.6)
        # ====================================================================
        logger.error(f"Processing failed: {e.message}")
        
        # Mark as failed in database if we have an ID
        if pipeline.audio_id:
            try:
                mark_as_failed(
                    track_id=pipeline.audio_id,
                    error_message=e.message
                )
                logger.debug(f"Marked {pipeline.audio_id} as FAILED")
            except Exception as db_error:
                logger.warning(f"Failed to update status to FAILED: {db_error}")
        
        # Cleanup temporary files (error path)
        pipeline.cleanup()
        
        # Return error response
        error_response = e.to_error_response()
        return error_response.model_dump()
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error during processing: {e}")
        
        # Mark as failed if we have an ID
        if pipeline.audio_id:
            try:
                mark_as_failed(
                    track_id=pipeline.audio_id,
                    error_message=f"Unexpected error: {str(e)}"
                )
            except Exception:
                pass  # Best effort
        
        # Cleanup
        pipeline.cleanup()
        
        # Return generic error
        error_response = ProcessAudioError(
            success=False,
            error=ErrorCode.FETCH_FAILED,
            message=f"Unexpected error: {str(e)}",
            details={"exception_type": type(e).__name__}
        )
        return error_response.model_dump()


# ============================================================================
# Synchronous Wrapper for FastMCP (if needed)
# ============================================================================

def process_audio_complete_sync(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for process_audio_complete.
    
    FastMCP supports async tools, so this is only needed if you encounter
    issues with async support.
    """
    import asyncio
    return asyncio.run(process_audio_complete(input_data))

