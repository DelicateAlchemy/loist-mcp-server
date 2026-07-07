"""
Service layer for the browser upload & ingestion flow (LOI-45).

Cloud Run caps request bodies at 32 MiB, so uploads go around the server:

1. create_upload()      -> tracking row + GCS V4 signed PUT URL (staging prefix)
2. (browser PUTs the file directly to GCS)
3. start_processing()   -> re-validates the staged object, dispatches a job
4. get_job()            -> poll status until complete/failed

Processing reuses the existing transport-agnostic pipeline
(src/business/audio_processor.py) by signing a GET URL for the staged
object and feeding it through the http_url path unchanged.

Dispatch prefers the Cloud Tasks machinery (src/tasks/) targeting
POST /tasks/process-upload; when Cloud Tasks is not configured (local
dev, docker-compose) it falls back to an in-process asyncio task.
"""

import asyncio
import logging
import posixpath
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.config import config
from src.exceptions import ResourceNotFoundError, ValidationError
from src.repositories.upload_repository import get_upload_repository

logger = logging.getLogger(__name__)

# Staging prefix inside the bucket. Should carry a 24h delete lifecycle rule
# (scripts/setup-upload-staging-lifecycle.sh) so abandoned uploads get cleaned.
UPLOAD_STAGING_PREFIX = "uploads"

# Declared MIME types accepted at signing time. The pipeline re-validates the
# actual bytes at process time (validate_format=True), so this is a first
# gate, not the security boundary.
ALLOWED_CONTENT_TYPES = frozenset({
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/aac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/vorbis",
    "audio/aiff",
    "audio/x-aiff",
})

# Signed PUT URLs need enough headroom for a 100 MB upload on a slow link.
UPLOAD_URL_EXPIRATION_MINUTES = 60
# Signed GET URL handed to the processing pipeline.
PROCESS_URL_EXPIRATION_MINUTES = 60

_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    """Reduce a client filename to a safe GCS object-name component."""
    base = posixpath.basename(filename.replace("\\", "/")).strip()
    safe = _FILENAME_SANITIZE_RE.sub("_", base).strip("._")
    return safe[:200] or "upload"


def _get_gcs_client():
    """Create a GCS client (separate function so tests can patch it)."""
    from src.storage import create_gcs_client

    return create_gcs_client()


async def create_upload(upload_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an upload record and a GCS V4 signed PUT URL for it.

    Args:
        upload_request: Dictionary with:
            - filename: str (required) - Original filename (used for the
              staging object name and as a pipeline hint)
            - content_type: str (required) - Declared MIME type; must be in
              ALLOWED_CONTENT_TYPES
            - size_bytes: int (required) - Declared size; must be within
              config.max_file_size

    Returns:
        Dictionary with upload_id, signed_put_url, expires_at, and
        gcs_object_name.

    Raises:
        ValidationError: If the declared file facts are unacceptable.
    """
    filename = (upload_request.get("filename") or "").strip()
    content_type = (upload_request.get("content_type") or "").strip().lower()
    size_bytes = upload_request.get("size_bytes")

    if not filename:
        raise ValidationError("Field 'filename' is required")
    if not content_type:
        raise ValidationError("Field 'content_type' is required")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported content_type '{content_type}'. "
            f"Supported: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
        raise ValidationError("Field 'size_bytes' must be a positive integer")
    if size_bytes > config.max_file_size:
        raise ValidationError(
            f"File too large: {size_bytes} bytes (max {config.max_file_size})"
        )

    upload_id = str(uuid.uuid4())
    gcs_object_name = f"{UPLOAD_STAGING_PREFIX}/{upload_id}/{_sanitize_filename(filename)}"

    record = get_upload_repository().create(
        {
            "id": upload_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "gcs_object_name": gcs_object_name,
        }
    )

    client = _get_gcs_client()
    signed_put_url = client.generate_signed_url(
        blob_name=gcs_object_name,
        expiration_minutes=UPLOAD_URL_EXPIRATION_MINUTES,
        method="PUT",
        content_type=content_type,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=UPLOAD_URL_EXPIRATION_MINUTES)

    logger.info(f"Created upload {upload_id} for '{filename}' ({size_bytes} bytes)")
    return {
        "upload_id": record["id"] if isinstance(record["id"], str) else str(record["id"]),
        "signed_put_url": signed_put_url,
        "expires_at": expires_at.isoformat(),
        "gcs_object_name": gcs_object_name,
        # The browser must send this exact Content-Type header on the PUT,
        # since it is baked into the signature.
        "required_headers": {"Content-Type": content_type},
    }


async def start_processing(upload_id: str) -> Dict[str, Any]:
    """
    Re-validate the staged object and dispatch a processing job.

    Args:
        upload_id: UUID of the upload (returned by create_upload).

    Returns:
        Dictionary with job_id (== upload_id) and status.

    Raises:
        ResourceNotFoundError: If the upload record does not exist.
        ValidationError: If the file was never uploaded, fails re-validation,
            or the upload is already being processed / processed.
    """
    repo = get_upload_repository()
    upload = repo.get_by_id(upload_id)
    if not upload:
        raise ResourceNotFoundError(f"Upload with ID '{upload_id}' was not found")

    status = upload["status"]
    if status in ("pending", "processing"):
        raise ValidationError(f"Upload {upload_id} is already {status}")
    if status == "complete":
        raise ValidationError(f"Upload {upload_id} has already been processed")

    # Server-side re-validation of the staged object: signed URLs constrain
    # Content-Type but cannot enforce the declared size.
    client = _get_gcs_client()
    blob = client.bucket.blob(upload["gcs_object_name"])
    if not blob.exists():
        raise ValidationError(
            f"No file found for upload {upload_id} — PUT the file to the signed URL first"
        )
    blob.reload()
    actual_size = blob.size or 0
    if actual_size <= 0:
        raise ValidationError(f"Staged object for upload {upload_id} is empty")
    if actual_size > config.max_file_size:
        raise ValidationError(
            f"Staged object is too large: {actual_size} bytes (max {config.max_file_size})"
        )
    actual_content_type = (blob.content_type or "").lower()
    if actual_content_type and actual_content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Staged object has unsupported content type '{actual_content_type}'"
        )

    repo.update_status(upload_id, "pending")
    _dispatch_processing(upload_id)

    logger.info(f"Dispatched processing for upload {upload_id}")
    return {"job_id": upload_id, "status": "pending"}


def _dispatch_processing(upload_id: str) -> None:
    """
    Dispatch the processing job: Cloud Tasks when available, otherwise an
    in-process asyncio task (local dev / docker-compose).
    """
    try:
        from src.tasks.queue import enqueue_upload_processing

        task_id = enqueue_upload_processing(upload_id)
        logger.info(f"Enqueued Cloud Task {task_id} for upload {upload_id}")
        return
    except Exception as e:
        logger.warning(
            f"Cloud Tasks dispatch unavailable for upload {upload_id} "
            f"({e}); falling back to in-process execution"
        )

    asyncio.get_event_loop().create_task(process_upload(upload_id))


async def process_upload(upload_id: str) -> Dict[str, Any]:
    """
    Worker: run the staged object through the existing ingestion pipeline.

    Signs a GET URL for the staging object and reuses the transport-agnostic
    http_url pipeline unchanged. Updates the upload row with the outcome and
    best-effort deletes the staging object on success.

    Returns:
        The final upload record.
    """
    repo = get_upload_repository()
    upload = repo.get_by_id(upload_id)
    if not upload:
        raise ResourceNotFoundError(f"Upload with ID '{upload_id}' was not found")

    repo.update_status(upload_id, "processing")

    try:
        from src.business import AudioProcessingRequest, process_audio_shared

        client = _get_gcs_client()
        source_url = client.generate_signed_url(
            blob_name=upload["gcs_object_name"],
            expiration_minutes=PROCESS_URL_EXPIRATION_MINUTES,
            method="GET",
        )

        request = AudioProcessingRequest(
            url=source_url,
            filename=upload["filename"],
            mime_type=upload["content_type"],
            max_size_mb=config.max_file_size / (1024 * 1024),
        )
        result = await process_audio_shared(request)

        record = repo.update_status(upload_id, "complete", audio_id=result.audio_id)
        logger.info(f"Upload {upload_id} processed -> audio_id {result.audio_id}")

        try:
            client.bucket.blob(upload["gcs_object_name"]).delete()
        except Exception as cleanup_error:
            logger.warning(
                f"Could not delete staging object for upload {upload_id}: {cleanup_error}"
            )

        return record

    except Exception as e:
        message = str(e)[:2000] or type(e).__name__
        logger.exception(f"Processing failed for upload {upload_id}: {e}")
        return repo.update_status(upload_id, "failed", error_message=message)


async def get_job(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a processing job (job_id == upload_id).

    Returns:
        Dictionary with job_id, status, and (when set) audio_id / error.

    Raises:
        ResourceNotFoundError: If no such upload/job exists.
    """
    upload = get_upload_repository().get_by_id(job_id)
    if not upload:
        raise ResourceNotFoundError(f"Job with ID '{job_id}' was not found")

    result: Dict[str, Any] = {
        "job_id": str(upload["id"]),
        "status": upload["status"],
        "filename": upload["filename"],
        "created_at": _isoformat(upload.get("created_at")),
        "updated_at": _isoformat(upload.get("updated_at")),
    }
    if upload.get("audio_id"):
        result["audio_id"] = str(upload["audio_id"])
    if upload.get("error_message"):
        result["error"] = upload["error_message"]
    return result


def _isoformat(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
