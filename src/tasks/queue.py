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
) -> str:
    """
    Enqueue a waveform generation task.

    Creates a Cloud Task to generate a DAW-style SVG waveform for the given audio file.
    Task will be processed asynchronously by the waveform handler endpoint.

    Args:
        audio_id: UUID of the audio track
        audio_gcs_path: GCS path to the source audio file
        source_hash: SHA-256 hash of the source audio file
        project_id: GCP project ID (auto-detected if not provided)
        location: GCP region (default: us-central1)
        queue_name: Cloud Tasks queue name (default: audio-processing-queue)
        target_url: HTTP endpoint URL to call (auto-configured if not provided)

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
        logger.info(f"Enqueuing waveform generation task for audio_id: {audio_id}")
        response = client.create_task(parent=queue_path, task=task)

        task_name = response.name
        logger.info(f"Successfully enqueued task: {task_name}")

        # Extract just the task ID from the full path
        task_id = task_name.split('/')[-1]
        return task_id

    except google_exceptions.GoogleAPICallError as e:
        logger.error(f"Cloud Tasks API error enqueuing waveform task for {audio_id}: {e}")
        raise TaskQueueError(f"Failed to enqueue waveform task: {e}") from e

    except Exception as e:
        logger.error(f"Unexpected error enqueuing waveform task for {audio_id}: {e}")
        raise TaskQueueError(f"Failed to enqueue waveform task: {e}") from e


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
