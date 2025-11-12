"""
HTTP endpoint handlers for async audio processing tasks.

Provides HTTP endpoints that are called by Google Cloud Tasks for background
processing of audio files, including waveform generation.

Features:
- Cloud Tasks authentication validation
- Extensible task routing by type
- Error handling and logging
- Integration with waveform generation pipeline
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile

from fastmcp import FastMCP

from src.waveform.generator import generate_waveform_svg, WaveformGenerationError
from src.storage.waveform_storage import upload_waveform_svg
from database.operations import update_waveform_metadata, check_waveform_cache
from src.storage.gcs_client import create_gcs_client
from src.exceptions import ValidationError, DatabaseOperationError, StorageError

logger = logging.getLogger(__name__)


def _validate_cloud_tasks_auth(request_headers: Dict[str, str]) -> bool:
    """
    Validate that request is from Google Cloud Tasks.

    Performs comprehensive authentication validation including:
    - Cloud Tasks User-Agent validation
    - Queue name validation against configured allowed queues
    - Service account identity validation (configurable strictness)
    - Request signature validation (future enhancement)

    Args:
        request_headers: HTTP request headers

    Returns:
        True if request is authenticated, False otherwise
    """
    # Import config for validation settings
    try:
        from src.config import config
        allowed_queues = config.allowed_task_queues_list
        strict_auth = config.cloud_tasks_strict_auth
    except ImportError:
        # Fallback if config not available
        allowed_queues = ["audio-processing-queue"]
        strict_auth = True

    # Check for Cloud Tasks user agent
    user_agent = request_headers.get("User-Agent", "")
    if "Google-Cloud-Tasks" not in user_agent:
        logger.warning(f"Invalid User-Agent for Cloud Tasks request: {user_agent}")
        return False

    # Validate queue name header
    queue_name = request_headers.get("X-CloudTasks-QueueName", "")
    if not queue_name:
        logger.warning("Missing X-CloudTasks-QueueName header")
        return False

    # Validate against configured allowed queues
    if queue_name not in allowed_queues:
        logger.warning(f"Unexpected queue name: {queue_name}. Allowed: {allowed_queues}")
        return False

    # Service account validation based on strictness setting
    service_account = request_headers.get("X-CloudTasks-ServiceAccount", "")
    if service_account:
        # Validate service account format
        if not service_account.endswith("@developer.gserviceaccount.com"):
            logger.warning(f"Invalid service account format: {service_account}")
            return False

        # Additional validation could include:
        # - Checking against expected service accounts
        # - Validating project ID in service account email
        logger.debug(f"Validated service account: {service_account}")
    else:
        # Check if we're in production (Cloud Run)
        import os
        is_production = bool(os.getenv("K_SERVICE"))

        if is_production and strict_auth:
            logger.warning("Missing service account identity in production environment with strict auth enabled")
            return False
        elif is_production:
            logger.debug("Allowing request without service account in production (strict auth disabled)")
        else:
            logger.debug("Allowing request without service account in development")

    # Future enhancements could include:
    # - Request signature validation using HMAC
    # - Timestamp validation to prevent replay attacks
    # - IP address validation for Cloud Tasks ranges

    logger.debug(f"Cloud Tasks authentication successful for queue: {queue_name}")
    return True


def _calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA-256 hash string
    """
    hash_sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


async def handle_waveform_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a waveform generation task.

    Processes the waveform generation request: downloads audio, generates SVG,
    uploads to GCS, and updates database metadata.

    Args:
        payload: Task payload with waveform generation parameters

    Returns:
        Dict with processing results

    Raises:
        ValidationError: If payload is invalid
        WaveformGenerationError: If waveform generation fails
        StorageError: If GCS operations fail
        DatabaseOperationError: If database operations fail
    """
    # Extract and validate payload
    audio_id = payload.get("audioId")
    audio_gcs_path = payload.get("audioGcsPath")
    source_hash = payload.get("sourceHash")

    if not audio_id or not audio_gcs_path or not source_hash:
        raise ValidationError("Missing required payload fields: audioId, audioGcsPath, sourceHash")

    logger.info(f"Processing waveform generation for audio_id: {audio_id}")

    # Check cache first
    cached_path = check_waveform_cache(audio_id, source_hash)
    if cached_path:
        logger.info(f"Cache hit for audio_id {audio_id} - waveform already exists")
        return {
            "status": "cache_hit",
            "audioId": audio_id,
            "waveformGcsPath": cached_path,
            "message": "Waveform already exists in cache"
        }

    # Download audio file to temp location
    temp_audio_path = None
    temp_svg_path = None

    try:
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_audio_path = Path(temp_dir) / f"{audio_id}_audio.mp3"
            temp_svg_path = Path(temp_dir) / f"{audio_id}_waveform.svg"

            # Download audio from GCS
            logger.info(f"Downloading audio from {audio_gcs_path}")
            client = create_gcs_client()

            # Extract blob name from gs:// URL
            if not audio_gcs_path.startswith('gs://'):
                raise ValidationError(f"Invalid GCS path format: {audio_gcs_path}")

            path_part = audio_gcs_path[5:]  # Remove 'gs://'
            slash_index = path_part.find('/')
            if slash_index == -1:
                raise ValidationError(f"Invalid GCS path format: {audio_gcs_path}")

            blob_name = path_part[slash_index + 1:]  # Everything after bucket/

            try:
                blob = client.bucket.blob(blob_name)
                blob.download_to_filename(str(temp_audio_path))
            except Exception as e:
                if "403" in str(e) or "forbidden" in str(e).lower():
                    raise StorageError(f"GCS access denied for {audio_gcs_path}. Check service account permissions: {e}") from e
                elif "404" in str(e) or "not found" in str(e).lower():
                    raise StorageError(f"Audio file not found in GCS: {audio_gcs_path}. File may have been deleted: {e}") from e
                elif "network" in str(e).lower() or "timeout" in str(e).lower():
                    raise StorageError(f"Network error downloading from GCS: {audio_gcs_path}. Check connectivity: {e}") from e
                else:
                    raise StorageError(f"Unexpected GCS download error for {audio_gcs_path}: {e}") from e

            # Verify downloaded file hash matches expected
            actual_hash = _calculate_file_hash(temp_audio_path)
            if actual_hash != source_hash:
                raise ValidationError(
                    f"File hash mismatch: expected {source_hash}, got {actual_hash}. "
                    "Audio file may have changed since task was created."
                )

            # Generate waveform SVG
            logger.info("Generating waveform SVG")
            try:
                result = generate_waveform_svg(
                    audio_path=temp_audio_path,
                    output_path=temp_svg_path,
                    width=2000,  # DAW-style width
                    height=200   # DAW-style height
                )
            except WaveformGenerationError as e:
                if "ffmpeg" in str(e).lower():
                    raise WaveformGenerationError(f"FFmpeg processing failed for {audio_id}. Ensure FFmpeg is installed and accessible: {e}") from e
                elif "format" in str(e).lower() or "codec" in str(e).lower():
                    raise WaveformGenerationError(f"Audio format not supported for {audio_id}. Supported formats: MP3, WAV, FLAC, M4A: {e}") from e
                elif "corrupt" in str(e).lower() or "invalid" in str(e).lower():
                    raise WaveformGenerationError(f"Audio file appears corrupted for {audio_id}. File may be truncated or invalid: {e}") from e
                else:
                    raise WaveformGenerationError(f"Waveform generation failed for {audio_id}: {e}") from e

            # Upload SVG to GCS
            logger.info("Uploading waveform SVG to GCS")
            try:
                gcs_path = upload_waveform_svg(
                    svg_path=temp_svg_path,
                    audio_id=audio_id,
                    content_hash=source_hash
                )
            except StorageError as e:
                if "403" in str(e) or "forbidden" in str(e).lower():
                    raise StorageError(f"GCS upload access denied for {audio_id}. Check service account permissions for waveform bucket: {e}") from e
                elif "quota" in str(e).lower() or "exceeded" in str(e).lower():
                    raise StorageError(f"GCS storage quota exceeded for {audio_id}. Free up space or increase quota: {e}") from e
                elif "network" in str(e).lower() or "timeout" in str(e).lower():
                    raise StorageError(f"Network error uploading waveform for {audio_id}. Check connectivity: {e}") from e
                else:
                    raise StorageError(f"GCS upload failed for {audio_id}: {e}") from e

            # Update database metadata
            logger.info("Updating database with waveform metadata")
            try:
                update_waveform_metadata(
                    audio_id=audio_id,
                    waveform_gcs_path=gcs_path,
                    source_hash=source_hash
                )
            except DatabaseOperationError as e:
                if "connection" in str(e).lower() or "cloudsql" in str(e).lower():
                    raise DatabaseOperationError(f"Database connection failed for {audio_id}. Check Cloud SQL Proxy or direct connection: {e}") from e
                elif "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    raise DatabaseOperationError(f"Waveform metadata already exists for {audio_id}. This may indicate a duplicate task: {e}") from e
                elif "timeout" in str(e).lower():
                    raise DatabaseOperationError(f"Database operation timed out for {audio_id}. Database may be overloaded: {e}") from e
                else:
                    raise DatabaseOperationError(f"Database update failed for {audio_id}: {e}") from e

            logger.info(f"Successfully generated waveform for audio_id: {audio_id}")

            return {
                "status": "completed",
                "audioId": audio_id,
                "waveformGcsPath": gcs_path,
                "processingTimeSeconds": result["processing_time_seconds"],
                "fileSizeBytes": result["file_size_bytes"],
                "sampleCount": result["sample_count"],
                "message": "Waveform generation completed successfully"
            }

    except Exception as e:
        logger.error(f"Failed to process waveform task for {audio_id}: {e}")

        # Re-raise with appropriate error type
        if isinstance(e, (ValidationError, WaveformGenerationError, StorageError, DatabaseOperationError)):
            raise

        # Wrap unexpected errors
        raise WaveformGenerationError(f"Unexpected error processing waveform task: {e}") from e

    finally:
        # Cleanup is handled by TemporaryDirectory context manager
        pass


def register_task_handlers(mcp: FastMCP) -> None:
    """
    Register task handler endpoints with the FastMCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.custom_route("/tasks/waveform", methods=["POST"])
    async def waveform_task_handler(request):
        """
        Handle waveform generation tasks from Cloud Tasks.

        This endpoint is called by Google Cloud Tasks to process waveform
        generation requests asynchronously.

        Authentication: Validates Cloud Tasks service account
        Payload: JSON with task details (audioId, audioGcsPath, sourceHash)
        Response: JSON with processing results or error details
        """
        try:
            # Get request data
            body = await request.body()
            headers = dict(request.headers)

            # Validate Cloud Tasks authentication
            if not _validate_cloud_tasks_auth(headers):
                logger.warning("Unauthorized request to waveform task handler")
                return {
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Request not from authorized Cloud Tasks service"
                }

            # Parse payload
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON payload: {e}")
                return {
                    "success": False,
                    "error": "INVALID_PAYLOAD",
                    "message": f"Invalid JSON payload: {e}"
                }

            # Process the task
            logger.info("Processing waveform generation task")
            result = await handle_waveform_task(payload)

            return {
                "success": True,
                "result": result
            }

        except ValidationError as e:
            logger.error(f"Validation error in waveform task: {e}")
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }

        except WaveformGenerationError as e:
            logger.error(f"Waveform generation error: {e}")
            return {
                "success": False,
                "error": "WAVEFORM_GENERATION_FAILED",
                "message": str(e)
            }

        except StorageError as e:
            logger.error(f"Storage error in waveform task: {e}")
            return {
                "success": False,
                "error": "STORAGE_ERROR",
                "message": str(e)
            }

        except DatabaseOperationError as e:
            logger.error(f"Database error in waveform task: {e}")
            return {
                "success": False,
                "error": "DATABASE_ERROR",
                "message": str(e)
            }

        except Exception as e:
            logger.error(f"Unexpected error in waveform task handler: {e}")
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": f"Internal server error: {str(e)}"
            }


# ============================================================================
# Future Task Handlers (Commented/Stubs)
# ============================================================================

async def handle_musicbrainz_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    FUTURE: Handle MusicBrainz lookup tasks.

    Would query MusicBrainz API for metadata using audio fingerprint.
    """
    # TODO: Implement MusicBrainz task processing
    raise NotImplementedError("MusicBrainz task handling not yet implemented")


async def handle_music_ai_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    FUTURE: Handle music AI analysis tasks.

    Would send audio to music.ai API for advanced analysis.
    """
    # TODO: Implement music AI task processing
    raise NotImplementedError("Music AI task handling not yet implemented")
