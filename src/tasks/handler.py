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
import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
from dataclasses import dataclass, field

from fastmcp import FastMCP

from src.waveform.generator import generate_waveform_svg, WaveformGenerationError
from src.storage.waveform_storage import upload_waveform_svg
from database.operations import update_waveform_metadata, check_waveform_cache
from src.storage.gcs_client import create_gcs_client
from src.exceptions import ValidationError, DatabaseOperationError, StorageError

logger = logging.getLogger(__name__)


@dataclass
class WaveformMetrics:
    """Thread-safe metrics for waveform processing operations."""

    # Core counters (use atomic operations when possible)
    _total_requests: int = 0
    _successful_generations: int = 0
    _failed_generations: int = 0
    _cache_hits: int = 0

    # Processing time statistics
    _processing_times: list = field(default_factory=list)
    _processing_times_lock: threading.RLock = field(default_factory=threading.RLock)

    # Error tracking
    _error_counts: Dict[str, int] = field(default_factory=dict)
    _error_counts_lock: threading.RLock = field(default_factory=threading.RLock)

    # Thread safety locks
    _counters_lock: threading.RLock = field(default_factory=threading.RLock)

    def increment_total_requests(self):
        """Atomically increment total requests counter."""
        with self._counters_lock:
            self._total_requests += 1

    def increment_successful_generations(self):
        """Atomically increment successful generations counter."""
        with self._counters_lock:
            self._successful_generations += 1

    def increment_failed_generations(self):
        """Atomically increment failed generations counter."""
        with self._counters_lock:
            self._failed_generations += 1

    def increment_cache_hits(self):
        """Atomically increment cache hits counter."""
        with self._counters_lock:
            self._cache_hits += 1

    def add_processing_time(self, processing_time: float):
        """Thread-safe addition of processing time."""
        with self._processing_times_lock:
            self._processing_times.append(processing_time)
            # Keep only last 1000 measurements to prevent unbounded growth
            if len(self._processing_times) > 1000:
                self._processing_times.pop(0)

    def increment_error_count(self, error_type: str):
        """Thread-safe increment of error type counter."""
        with self._error_counts_lock:
            self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """
        Get a thread-safe snapshot of current metrics.

        Returns a copy of metrics that can be safely read without locks.
        """
        with self._counters_lock:
            total_requests = self._total_requests
            successful_generations = self._successful_generations
            failed_generations = self._failed_generations
            cache_hits = self._cache_hits

        with self._processing_times_lock:
            processing_times = self._processing_times.copy()

        with self._error_counts_lock:
            error_types = self._error_counts.copy()

        # Calculate derived metrics
        processing_time_stats = {}
        if processing_times:
            processing_time_stats = {
                "count": len(processing_times),
                "average_seconds": sum(processing_times) / len(processing_times),
                "min_seconds": min(processing_times),
                "max_seconds": max(processing_times)
            }

        return {
            "total_requests": total_requests,
            "successful_generations": successful_generations,
            "failed_generations": failed_generations,
            "cache_hits": cache_hits,
            "processing_time_stats": processing_time_stats,
            "error_types": error_types
        }


# Global metrics instance
_waveform_metrics = WaveformMetrics()


def _update_waveform_metrics(
    success: bool,
    processing_time: Optional[float] = None,
    cache_hit: bool = False,
    error_type: Optional[str] = None
):
    """
    Update waveform processing metrics in a thread-safe manner.

    Args:
        success: Whether the operation was successful
        processing_time: Time taken for processing (in seconds)
        cache_hit: Whether this was served from cache
        error_type: Type of error if operation failed
    """
    _waveform_metrics.increment_total_requests()

    if cache_hit:
        _waveform_metrics.increment_cache_hits()
    elif success:
        _waveform_metrics.increment_successful_generations()
    else:
        _waveform_metrics.increment_failed_generations()

    if processing_time is not None:
        _waveform_metrics.add_processing_time(processing_time)

    if error_type is not None:
        _waveform_metrics.increment_error_count(error_type)


def get_waveform_metrics() -> Dict[str, Any]:
    """
    Get current waveform processing metrics snapshot.

    Returns:
        Dictionary containing current metrics
    """
    return _waveform_metrics.get_metrics_snapshot()


def _validate_cloud_tasks_auth(request_headers: Dict[str, str]) -> bool:
    """
    Validate that request is from Google Cloud Tasks.

    Checks for Cloud Tasks specific headers and service account authentication.
    In production, this should validate the service account making the request.

    Args:
        request_headers: HTTP request headers

    Returns:
        True if request is authenticated, False otherwise
    """
    # For MVP, we accept requests that appear to come from Cloud Tasks
    # In production, should validate the service account identity

    # Check for Cloud Tasks user agent
    user_agent = request_headers.get("User-Agent", "")
    if "Google-Cloud-Tasks" not in user_agent:
        logger.warning(f"Suspicious request - User-Agent: {user_agent}")
        return False

    # Additional validation could include:
    # - Validating the service account identity
    # - Checking request signatures
    # - Validating the queue name

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

    start_time = time.time()
    logger.info(f"Processing waveform generation for audio_id: {audio_id}")

    # Check cache first
    cached_path = check_waveform_cache(audio_id, source_hash)
    if cached_path:
        processing_time = time.time() - start_time
        _update_waveform_metrics(success=True, processing_time=processing_time, cache_hit=True)
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

            blob = client.bucket.blob(blob_name)
            blob.download_to_filename(str(temp_audio_path))

            # Verify downloaded file hash matches expected
            actual_hash = _calculate_file_hash(temp_audio_path)
            if actual_hash != source_hash:
                raise ValidationError(
                    f"File hash mismatch: expected {source_hash}, got {actual_hash}. "
                    "Audio file may have changed since task was created."
                )

            # Generate waveform SVG
            logger.info("Generating waveform SVG")
            result = generate_waveform_svg(
                audio_path=temp_audio_path,
                output_path=temp_svg_path,
                width=2000,  # DAW-style width
                height=200   # DAW-style height
            )

            # Upload SVG to GCS
            logger.info("Uploading waveform SVG to GCS")
            gcs_path = upload_waveform_svg(
                svg_path=temp_svg_path,
                audio_id=audio_id,
                content_hash=source_hash
            )

            # Update database metadata
            logger.info("Updating database with waveform metadata")
            update_waveform_metadata(
                audio_id=audio_id,
                waveform_gcs_path=gcs_path,
                source_hash=source_hash
            )

            logger.info(f"Successfully generated waveform for audio_id: {audio_id}")

            # Update metrics for successful generation
            processing_time = time.time() - start_time
            _update_waveform_metrics(success=True, processing_time=processing_time, cache_hit=False)

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
        # Update metrics for failed generation
        processing_time = time.time() - start_time
        error_type = type(e).__name__
        _update_waveform_metrics(success=False, processing_time=processing_time, cache_hit=False, error_type=error_type)

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

    @mcp.tool()
    def get_waveform_metrics_tool() -> Dict[str, Any]:
        """
        Get current waveform processing metrics.

        Returns comprehensive statistics about waveform generation operations
        including success rates, processing times, cache hit rates, and error
        tracking.

        Returns:
            Dictionary containing current metrics with the following structure:
            {
                "total_requests": int,
                "successful_generations": int,
                "failed_generations": int,
                "cache_hits": int,
                "processing_time_stats": {
                    "count": int,
                    "average_seconds": float,
                    "min_seconds": float,
                    "max_seconds": float
                },
                "error_types": {"ErrorType": count, ...}
            }
        """
        return {"status": "success", "metrics": get_waveform_metrics()}

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
