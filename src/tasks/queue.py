"""
Generic task queue for async audio processing using Google Cloud Tasks.

Provides extensible task queuing for background processing of audio files,
with built-in retry logic, exponential backoff, and support for multiple
task types (waveform generation, MusicBrainz lookups, AI analysis).

Features:
- Cloud Tasks integration with automatic retries
- Extensible task types with type-based routing
- Configurable queue settings
- Error handling and logging
"""

import logging
import json
from typing import Dict, Any, Optional
from google.cloud import tasks
from google.protobuf import timestamp_pb2
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)


class TaskQueueError(Exception):
    """Raised when task queue operations fail."""
    pass


def _get_cloud_tasks_client() -> tasks.CloudTasksClient:
    """
    Get or create Cloud Tasks client.

    Returns:
        Configured Cloud Tasks client
    """
    try:
        return tasks.CloudTasksClient()
    except Exception as e:
        logger.error(f"Failed to create Cloud Tasks client: {e}")
        raise TaskQueueError(f"Cloud Tasks client creation failed: {e}") from e


def _get_queue_path(project_id: str, location: str, queue_name: str) -> str:
    """
    Get the full queue path for Cloud Tasks.

    Args:
        project_id: GCP project ID
        location: GCP region (e.g., 'us-central1')
        queue_name: Name of the queue

    Returns:
        Full queue path string
    """
    client = _get_cloud_tasks_client()
    return client.queue_path(project_id, location, queue_name)


def _create_task_payload(task_type: str, **kwargs) -> str:
    """
    Create JSON payload for a task.

    Args:
        task_type: Type of task (e.g., 'waveform', 'musicbrainz')
        **kwargs: Task-specific parameters

    Returns:
        JSON string payload
    """
    payload = {
        "type": task_type,
        **kwargs
    }
    return json.dumps(payload)


def enqueue_waveform_generation(
    audio_id: str,
    audio_gcs_path: str,
    source_hash: str,
    project_id: Optional[str] = None,
    location: str = "us-central1",
    queue_name: str = "audio-processing-queue",
    target_url: Optional[str] = None,
    task_queue_mode: Optional[str] = None,
) -> str:
    """
    Enqueue a waveform generation task.

    Supports both Cloud Tasks (production) and local queue (development) modes.
    In local mode, tasks are executed in-memory without requiring GCP infrastructure.

    Args:
        audio_id: UUID of the audio track
        audio_gcs_path: GCS path to the source audio file
        source_hash: SHA-256 hash of the source audio file
        project_id: GCP project ID (auto-detected if not provided, cloud mode only)
        location: GCP region (default: us-central1, cloud mode only)
        queue_name: Cloud Tasks queue name (default: audio-processing-queue, cloud mode only)
        target_url: HTTP endpoint URL to call (auto-configured if not provided, cloud mode only)
        task_queue_mode: Queue mode - "cloud" or "local" (auto-detected from config if not provided)

    Returns:
        Task name/ID string

    Raises:
        TaskQueueError: If task creation fails

    Example:
        >>> task_id = enqueue_waveform_generation(
        ...     '123e4567-e89b-12d3-a456-426614174000',
        ...     'gs://bucket/audio/123e4567.mp3',
        ...     'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'
        ... )
        >>> print(f"Enqueued task: {task_id}")
    """
    # Determine queue mode (auto-detect from config if not provided)
    if task_queue_mode is None:
        try:
            from src.config import config
            task_queue_mode = config.task_queue_mode
        except ImportError:
            task_queue_mode = "cloud"  # Default fallback

    # Use local queue mode
    if task_queue_mode == "local":
        try:
            from src.tasks.local_queue import enqueue_local_task

            # Create task payload
            payload = _create_task_payload(
                "waveform",
                audioId=audio_id,
                audioGcsPath=audio_gcs_path,
                sourceHash=source_hash,
            )

            # Parse payload for local handler
            task_payload = json.loads(payload)

            logger.info(f"Enqueuing local waveform generation task for audio_id: {audio_id}")
            task_id = enqueue_local_task(task_payload, target_url or "http://localhost:8080/tasks/waveform")

            logger.info(f"Successfully enqueued local task: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"Failed to enqueue local waveform task for {audio_id}: {e}")
            raise TaskQueueError(f"Failed to enqueue local waveform task: {e}") from e

    # Use Cloud Tasks mode (original implementation)
    else:
        # Auto-detect project ID if not provided
        if not project_id:
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                raise TaskQueueError("project_id not provided and GOOGLE_CLOUD_PROJECT env var not set")

        # Auto-configure target URL if not provided
        if not target_url:
            # Default to waveform handler endpoint on current service
            # In Cloud Run, this would be the URL of the waveform processing service
            import os
            service_url = os.getenv("WAVEFORM_SERVICE_URL")
            if service_url:
                target_url = f"{service_url}/tasks/waveform"
            else:
                # Fallback for local development
                target_url = "http://localhost:8080/tasks/waveform"

        client = _get_cloud_tasks_client()
        queue_path = _get_queue_path(project_id, location, queue_name)

        # Create task payload
        payload = _create_task_payload(
            "waveform",
            audioId=audio_id,
            audioGcsPath=audio_gcs_path,
            sourceHash=source_hash,
        )

        # Create task
        task = tasks.Task(
            http_request=tasks.HttpRequest(
                http_method=tasks.HttpMethod.POST,
                url=target_url,
                headers={"Content-Type": "application/json"},
                body=payload.encode(),
            ),
        )

        # Configure retry settings
        task.dispatch_deadline.CopyFrom(timestamp_pb2.Timestamp(seconds=1800))  # 30 minutes

        try:
            logger.info(f"Enqueuing Cloud Tasks waveform generation task for audio_id: {audio_id}")
            response = client.create_task(parent=queue_path, task=task)

            task_name = response.name
            logger.info(f"Successfully enqueued Cloud Tasks: {task_name}")

            # Extract just the task ID from the full path
            task_id = task_name.split('/')[-1]
            return task_id

        except google_exceptions.GoogleAPICallError as e:
            if "PERMISSION_DENIED" in str(e) or "403" in str(e):
                logger.error(f"Cloud Tasks permission denied for {audio_id}: {e}")
                raise TaskQueueError(f"Cloud Tasks access denied. Check service account permissions for 'roles/cloudtasks.enqueuer': {e}") from e
            elif "NOT_FOUND" in str(e) or "404" in str(e):
                logger.error(f"Cloud Tasks queue not found for {audio_id}: {e}")
                raise TaskQueueError(f"Cloud Tasks queue '{queue_name}' not found. Verify queue exists in region '{location}': {e}") from e
            elif "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                logger.error(f"Cloud Tasks quota exceeded for {audio_id}: {e}")
                raise TaskQueueError(f"Cloud Tasks quota exceeded. Check current usage limits: {e}") from e
            else:
                logger.error(f"Cloud Tasks API error enqueuing waveform task for {audio_id}: {e}")
                raise TaskQueueError(f"Cloud Tasks API error: {e}") from e

        except Exception as e:
            if "GOOGLE_CLOUD_PROJECT" in str(e) or "project_id" in str(e).lower():
                logger.error(f"Missing GCP project configuration for {audio_id}: {e}")
                raise TaskQueueError(f"GCP project not configured. Set GOOGLE_CLOUD_PROJECT environment variable: {e}") from e
            elif "credentials" in str(e).lower() or "authentication" in str(e).lower():
                logger.error(f"GCP authentication failed for {audio_id}: {e}")
                raise TaskQueueError(f"GCP authentication failed. Check service account credentials: {e}") from e
            else:
                logger.error(f"Unexpected error enqueuing waveform task for {audio_id}: {e}")
                raise TaskQueueError(f"Unexpected error enqueuing Cloud Tasks: {e}") from e


# ============================================================================
# Future Task Types (Commented/Stubs)
# ============================================================================

def enqueue_musicbrainz_query(
    audio_id: str,
    audio_fingerprint: str,
    project_id: Optional[str] = None,
    location: str = "us-central1",
    queue_name: str = "audio-processing-queue",
) -> str:
    """
    FUTURE: Enqueue a MusicBrainz lookup task.

    Would query MusicBrainz API for metadata using audio fingerprint.

    Args:
        audio_id: UUID of the audio track
        audio_fingerprint: AcoustID fingerprint of the audio
        project_id: GCP project ID
        location: GCP region
        queue_name: Cloud Tasks queue name

    Returns:
        Task name/ID string
    """
    # TODO: Implement MusicBrainz task enqueuing
    raise NotImplementedError("MusicBrainz task enqueuing not yet implemented")


def enqueue_music_ai_query(
    audio_id: str,
    audio_gcs_path: str,
    project_id: Optional[str] = None,
    location: str = "us-central1",
    queue_name: str = "audio-processing-queue",
) -> str:
    """
    FUTURE: Enqueue a music AI analysis task.

    Would send audio to music.ai API for advanced analysis.

    Args:
        audio_id: UUID of the audio track
        audio_gcs_path: GCS path to the audio file
        project_id: GCP project ID
        location: GCP region
        queue_name: Cloud Tasks queue name

    Returns:
        Task name/ID string
    """
    # TODO: Implement music.ai task enqueuing
    raise NotImplementedError("Music AI task enqueuing not yet implemented")


def check_cloud_tasks_health(
    project_id: Optional[str] = None,
    location: str = "us-central1",
    queue_name: str = "audio-processing-queue"
) -> Dict[str, Any]:
    """
    Check Cloud Tasks queue health and accessibility.

    Performs basic connectivity and permission tests for Cloud Tasks.

    Args:
        project_id: GCP project ID (auto-detected if not provided)
        location: GCP region
        queue_name: Cloud Tasks queue name

    Returns:
        Dict with health status and details:
        {
            "available": bool,
            "configured": bool,
            "error": str | None,
            "queue_name": str | None,
            "location": str | None,
            "response_time_ms": float | None
        }
    """
    import time

    result = {
        "available": False,
        "configured": False,
        "error": None,
        "queue_name": queue_name,
        "location": location,
        "response_time_ms": None
    }

    start_time = time.time()

    try:
        # Auto-detect project ID if not provided
        if not project_id:
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                result["error"] = "GCP project ID not configured"
                return result

        result["configured"] = True

        # Test Cloud Tasks client creation and basic connectivity
        try:
            client = _get_cloud_tasks_client()

            # Try to get queue path (tests authentication and basic connectivity)
            queue_path = client.queue_path(project_id, location, queue_name)

            # Try to get queue (tests permissions and queue existence)
            # This will throw if queue doesn't exist or permissions are insufficient
            queue = client.get_queue(name=queue_path)

            result["available"] = True
            result["response_time_ms"] = (time.time() - start_time) * 1000

        except Exception as e:
            result["error"] = f"Cloud Tasks health check failed: {str(e)}"
            result["response_time_ms"] = (time.time() - start_time) * 1000

            # Provide more specific error messages
            if "PERMISSION_DENIED" in str(e):
                result["error"] = "Cloud Tasks permission denied. Check service account has 'roles/cloudtasks.viewer' role"
            elif "NOT_FOUND" in str(e):
                result["error"] = f"Cloud Tasks queue '{queue_name}' not found in {location}"

    except Exception as e:
        result["error"] = f"Cloud Tasks health check setup failed: {str(e)}"
        result["response_time_ms"] = (time.time() - start_time) * 1000

    return result
