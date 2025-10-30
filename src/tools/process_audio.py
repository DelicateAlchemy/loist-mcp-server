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
    extract_metadata,
    extract_artwork,
    validate_audio_format,
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
    ResourceNotFoundError,
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
        
        # Note: Removed premature database record creation to avoid constraint violations
        # The record will be created later with all required fields after GCS upload
        # This fixes the "Premature Status Updates" architectural issue
        logger.debug(f"Processing audio with ID: {pipeline.audio_id}")
        
        # ====================================================================
        # Stage 2: HTTP Download (Subtask 7.2)
        # ====================================================================
        logger.info(f"Downloading audio from: {source.url}")
        logger.debug(f"Download options: max_size_mb={options.maxSizeMB}, timeout={options.timeout}")
        
        try:
            # Validate URL scheme (http/https only)
            logger.debug("Validating URL scheme...")
            validate_url(str(source.url))
            logger.debug("URL scheme validation passed")
            
            # SSRF protection check
            logger.debug("Performing SSRF protection check...")
            validate_ssrf(str(source.url))
            logger.debug("SSRF protection check passed")
            
            # Download to temporary file
            logger.debug(f"Starting download with max_size_mb={options.maxSizeMB}, timeout_seconds={options.timeout}")
            pipeline.temp_audio_path = download_from_url(
                url=str(source.url),
                headers=source.headers,
                max_size_mb=options.maxSizeMB,
                timeout_seconds=options.timeout
            )
            
            logger.info(f"Downloaded audio to: {pipeline.temp_audio_path}")
            logger.debug(f"Download successful, file size: {Path(pipeline.temp_audio_path).stat().st_size if pipeline.temp_audio_path else 'N/A'} bytes")
            
        except URLValidationError as e:
            import traceback
            logger.error(f"URL validation failed: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
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
            import traceback
            logger.error(f"Download failed: {e}")
            logger.error(f"DownloadError type: {type(e).__name__}")
            logger.error(f"DownloadError traceback:\n{traceback.format_exc()}")
            raise ProcessAudioException(
                error_code=ErrorCode.FETCH_FAILED,
                message=f"Failed to download audio: {str(e)}",
                details={"download_error_type": type(e).__name__, "traceback": traceback.format_exc()}
            )
        except Exception as download_exc:
            # Catch any other unexpected exceptions during download
            import traceback
            logger.error(f"Unexpected exception during download phase: {download_exc}")
            logger.error(f"Exception type: {type(download_exc).__name__}")
            logger.error(f"Exception module: {type(download_exc).__module__ if hasattr(type(download_exc), '__module__') else 'N/A'}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Check if this is the NameError about ResourceNotFoundError
            if isinstance(download_exc, NameError) and "ResourceNotFoundError" in str(download_exc):
                logger.error("⚠️ NameError about ResourceNotFoundError detected in DOWNLOAD phase!")
                logger.error(f"  This suggests ResourceNotFoundError is referenced during download operations")
            
            raise ProcessAudioException(
                error_code=ErrorCode.FETCH_FAILED,
                message=f"Unexpected error during download: {str(download_exc)}",
                details={
                    "exception_type": type(download_exc).__name__,
                    "exception_message": str(download_exc),
                    "occurred_in": "download_phase"
                }
            )
        
        # ====================================================================
        # Stage 3: Metadata Extraction (Subtask 7.3)
        # ====================================================================
        logger.info("Extracting metadata and artwork")
        
        try:
            # Validate audio format if enabled
            if options.validateFormat:
                validate_audio_format(pipeline.temp_audio_path)
            
            # Extract metadata
            metadata_dict = extract_metadata(pipeline.temp_audio_path)
            logger.debug(f"Extracted metadata: {metadata_dict}")
            
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
            audio_blob = upload_audio_file(
                source_path=pipeline.temp_audio_path,
                destination_blob_name=f"audio/{pipeline.audio_id}/{filename}"
            )
            # Construct full GCS path (gs://bucket/path) for database storage
            pipeline.gcs_audio_path = f"gs://{audio_blob.bucket.name}/{audio_blob.name}"
            logger.info(f"Uploaded audio to GCS: {pipeline.gcs_audio_path}")
            
            # Upload artwork if present
            if pipeline.temp_artwork_path:
                artwork_blob = upload_audio_file(
                    source_path=pipeline.temp_artwork_path,
                    destination_blob_name=f"audio/{pipeline.audio_id}/artwork.jpg"
                )
                # Construct full GCS path (gs://bucket/path) for database storage
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
            # Prepare database metadata (separate from GCS paths)
            db_metadata = {
                "artist": metadata_dict.get("artist", ""),
                "title": metadata_dict.get("title", "Untitled"),
                "album": metadata_dict.get("album", ""),
                "genre": metadata_dict.get("genre"),
                "year": metadata_dict.get("year"),
                "duration_seconds": metadata_dict.get("duration", 0),
                "channels": metadata_dict.get("channels", 2),
                "sample_rate": metadata_dict.get("sample_rate", 44100),
                "bitrate": metadata_dict.get("bitrate", 0),
                "format": metadata_dict.get("format", ""),
            }
            
            # Save to database using correct function signature
            saved_record = save_audio_metadata(
                metadata=db_metadata,
                audio_gcs_path=pipeline.gcs_audio_path,
                thumbnail_gcs_path=pipeline.gcs_artwork_path,
                track_id=pipeline.audio_id
            )
            pipeline.db_committed = True
            
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
        from config import config
        embed_url = f"{config.embed_base_url}/embed/{pipeline.audio_id}"
        
        # Build response using Pydantic models for validation
        response = ProcessAudioOutput(
            success=True,
            audioId=pipeline.audio_id,
            metadata=AudioMetadata(
                Product=ProductMetadata(
                    Artist=metadata_dict.get("artist", ""),
                    Title=metadata_dict.get("title", "Untitled"),
                    Album=metadata_dict.get("album", ""),
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
        import traceback
        logger.error(f"Processing failed: {e.message}")
        logger.error(f"Error code: {e.error_code}")
        logger.error(f"Error details: {e.details}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Mark as failed in database if we have an ID
        if pipeline.audio_id:
            try:
                mark_as_failed(
                    track_id=pipeline.audio_id,
                    error_message=e.message
                )
                logger.debug(f"Marked {pipeline.audio_id} as FAILED")
            except Exception as db_error:
                logger.error(f"Failed to update status to FAILED: {db_error}")
                logger.error(f"Database exception traceback:\n{traceback.format_exc()}")
        
        # Cleanup temporary files (error path)
        pipeline.cleanup()
        
        # Return error response
        error_response = e.to_error_response()
        return error_response.model_dump()
        
    except Exception as e:
        # Catch-all for unexpected errors
        # Log comprehensive exception details for debugging
        import traceback
        exc_type = type(e).__name__
        exc_message = str(e)
        exc_traceback = traceback.format_exc()
        
        logger.error(f"Unexpected error during processing:")
        logger.error(f"  Exception Type: {exc_type}")
        logger.error(f"  Exception Message: {exc_message}")
        logger.error(f"  Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
        logger.error(f"  Exception Module: {type(e).__module__ if hasattr(type(e), '__module__') else 'N/A'}")
        logger.error(f"  Full Traceback:\n{exc_traceback}")
        
        # Enhanced debugging for NameError issues
        if exc_type == "NameError" and "ResourceNotFoundError" in exc_message:
            logger.error("⚠️ DETECTED: NameError referencing ResourceNotFoundError!")
            logger.error(f"  This suggests ResourceNotFoundError is not in scope where it's being referenced")
            logger.error(f"  Exception occurred in: {exc_traceback.split('File')[-1].split(',')[0] if 'File' in exc_traceback else 'Unknown location'}")
            
            # Check if this is related to FastMCP serialization
            if "fastmcp" in exc_traceback.lower() or "json" in exc_traceback.lower():
                logger.error("  ⚠️ This appears to be a FastMCP serialization issue!")
                logger.error("  FastMCP may be trying to serialize exception class information in a different context")
            
            # Check module namespace
            import sys
            current_module = sys.modules.get(__name__, None)
            if current_module:
                logger.error(f"  ResourceNotFoundError in module namespace: {hasattr(current_module, 'ResourceNotFoundError')}")
                logger.error(f"  Available exception classes: {[name for name in dir(current_module) if 'Error' in name]}")
        
        # Mark as failed if we have an ID
        if pipeline.audio_id:
            try:
                mark_as_failed(
                    track_id=pipeline.audio_id,
                    error_message=f"Unexpected error: {str(e)}"
                )
            except Exception as db_exc:
                logger.error(f"Failed to mark as failed in database: {db_exc}")
                logger.error(f"Database exception traceback:\n{traceback.format_exc()}")
        
        # Cleanup
        pipeline.cleanup()
        
        # Return generic error with enhanced details
        error_response = ProcessAudioError(
            success=False,
            error=ErrorCode.FETCH_FAILED,
            message=f"Unexpected error: {str(e)}",
            details={
                "exception_type": exc_type,
                "exception_message": exc_message,
                "traceback_preview": exc_traceback.split('\n')[-5:] if exc_traceback else None,
            }
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

