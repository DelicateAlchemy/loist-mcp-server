"""
Unit tests for the browser upload & ingestion flow (LOI-45).

Covers src/services/upload_service.py with a fake in-memory repository and a
mocked GCS client, plus an end-to-end flow test (create -> staged -> process
-> poll) with the ingestion pipeline mocked.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import ResourceNotFoundError, ValidationError
from src.repositories.upload_repository import (
    UploadRepositoryInterface,
    set_upload_repository,
)
from src.services import upload_service


class InMemoryUploadRepository(UploadRepositoryInterface):
    """Simple in-memory stand-in for the Postgres repository."""

    def __init__(self):
        self.rows: Dict[str, Dict[str, Any]] = {}

    def create(self, upload_data: Dict[str, Any]) -> Dict[str, Any]:
        row = {
            "id": upload_data.get("id") or str(uuid.uuid4()),
            "filename": upload_data["filename"],
            "content_type": upload_data["content_type"],
            "size_bytes": upload_data["size_bytes"],
            "gcs_object_name": upload_data["gcs_object_name"],
            "status": "awaiting_upload",
            "audio_id": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.rows[row["id"]] = row
        return dict(row)

    def get_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        row = self.rows.get(upload_id)
        return dict(row) if row else None

    def update_status(self, upload_id, status, audio_id=None, error_message=None):
        row = self.rows.get(upload_id)
        if not row:
            raise ResourceNotFoundError(f"Upload with ID '{upload_id}' was not found")
        row["status"] = status
        if audio_id is not None:
            row["audio_id"] = audio_id
        row["error_message"] = error_message
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


@pytest.fixture
def repo():
    repository = InMemoryUploadRepository()
    set_upload_repository(repository)
    yield repository
    set_upload_repository(None)


@pytest.fixture
def gcs_client():
    """Mock GCS client with a controllable staged blob."""
    client = MagicMock()
    client.generate_signed_url.return_value = "https://storage.googleapis.com/signed"
    blob = client.bucket.blob.return_value
    blob.exists.return_value = True
    blob.size = 1024
    blob.content_type = "audio/mpeg"
    with patch.object(upload_service, "_get_gcs_client", return_value=client):
        yield client


VALID_REQUEST = {"filename": "song.mp3", "content_type": "audio/mpeg", "size_bytes": 1024}


# ============================================================================
# create_upload
# ============================================================================

async def test_create_upload_success(repo, gcs_client):
    result = await upload_service.create_upload(dict(VALID_REQUEST))

    assert result["signed_put_url"] == "https://storage.googleapis.com/signed"
    assert result["required_headers"] == {"Content-Type": "audio/mpeg"}
    assert result["gcs_object_name"].startswith(f"uploads/{result['upload_id']}/")
    assert result["gcs_object_name"].endswith("song.mp3")

    row = repo.rows[result["upload_id"]]
    assert row["status"] == "awaiting_upload"

    # PUT signature must bake in the declared content type
    kwargs = gcs_client.generate_signed_url.call_args.kwargs
    assert kwargs["method"] == "PUT"
    assert kwargs["content_type"] == "audio/mpeg"


async def test_create_upload_sanitizes_filename(repo, gcs_client):
    request = dict(VALID_REQUEST, filename="../../etc/pass wd?.mp3")
    result = await upload_service.create_upload(request)
    object_component = result["gcs_object_name"].rsplit("/", 1)[-1]
    assert "/" not in object_component
    assert ".." not in object_component
    assert " " not in object_component
    # Original filename is preserved on the record for the pipeline hint
    assert repo.rows[result["upload_id"]]["filename"] == "../../etc/pass wd?.mp3"


@pytest.mark.parametrize("field", ["filename", "content_type", "size_bytes"])
async def test_create_upload_missing_field(repo, gcs_client, field):
    request = dict(VALID_REQUEST)
    del request[field]
    with pytest.raises(ValidationError):
        await upload_service.create_upload(request)


async def test_create_upload_rejects_non_audio_content_type(repo, gcs_client):
    with pytest.raises(ValidationError, match="Unsupported content_type"):
        await upload_service.create_upload(dict(VALID_REQUEST, content_type="video/mp4"))


@pytest.mark.parametrize("size", [0, -5, "1024", 10.5, True])
async def test_create_upload_rejects_bad_sizes(repo, gcs_client, size):
    with pytest.raises(ValidationError):
        await upload_service.create_upload(dict(VALID_REQUEST, size_bytes=size))


async def test_create_upload_rejects_oversize(repo, gcs_client):
    from src.config import config
    with pytest.raises(ValidationError, match="too large"):
        await upload_service.create_upload(
            dict(VALID_REQUEST, size_bytes=config.max_file_size + 1)
        )


# ============================================================================
# start_processing
# ============================================================================

async def _staged_upload(repo, gcs_client) -> str:
    result = await upload_service.create_upload(dict(VALID_REQUEST))
    return result["upload_id"]


async def test_start_processing_unknown_upload(repo, gcs_client):
    with pytest.raises(ResourceNotFoundError):
        await upload_service.start_processing(str(uuid.uuid4()))


async def test_start_processing_before_put(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    gcs_client.bucket.blob.return_value.exists.return_value = False
    with pytest.raises(ValidationError, match="PUT the file"):
        await upload_service.start_processing(upload_id)
    assert repo.rows[upload_id]["status"] == "awaiting_upload"


async def test_start_processing_rejects_empty_object(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    gcs_client.bucket.blob.return_value.size = 0
    with pytest.raises(ValidationError, match="empty"):
        await upload_service.start_processing(upload_id)


async def test_start_processing_rejects_oversize_object(repo, gcs_client):
    from src.config import config
    upload_id = await _staged_upload(repo, gcs_client)
    gcs_client.bucket.blob.return_value.size = config.max_file_size + 1
    with pytest.raises(ValidationError, match="too large"):
        await upload_service.start_processing(upload_id)


async def test_start_processing_rejects_bad_staged_content_type(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    gcs_client.bucket.blob.return_value.content_type = "application/x-msdownload"
    with pytest.raises(ValidationError, match="unsupported content type"):
        await upload_service.start_processing(upload_id)


async def test_start_processing_dispatches_and_sets_pending(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    with patch.object(upload_service, "_dispatch_processing") as dispatch:
        result = await upload_service.start_processing(upload_id)
    dispatch.assert_called_once_with(upload_id)
    assert result == {"job_id": upload_id, "status": "pending"}
    assert repo.rows[upload_id]["status"] == "pending"


async def test_start_processing_rejects_in_flight_or_done(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    for status in ("pending", "processing", "complete"):
        repo.rows[upload_id]["status"] = status
        with pytest.raises(ValidationError):
            await upload_service.start_processing(upload_id)


async def test_start_processing_allows_retry_after_failure(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    repo.rows[upload_id]["status"] = "failed"
    with patch.object(upload_service, "_dispatch_processing"):
        result = await upload_service.start_processing(upload_id)
    assert result["status"] == "pending"


# ============================================================================
# process_upload (worker)
# ============================================================================

async def test_process_upload_success(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    repo.rows[upload_id]["status"] = "pending"
    audio_id = str(uuid.uuid4())

    pipeline_result = MagicMock(audio_id=audio_id)
    with patch("src.business.process_audio_shared", return_value=pipeline_result) as pipeline:
        record = await upload_service.process_upload(upload_id)

    assert record["status"] == "complete"
    assert record["audio_id"] == audio_id

    # Pipeline was fed a signed GET URL for the staged object
    request = pipeline.call_args.args[0]
    assert request.url == "https://storage.googleapis.com/signed"
    assert request.filename == "song.mp3"
    assert request.mime_type == "audio/mpeg"
    get_call = gcs_client.generate_signed_url.call_args
    assert get_call.kwargs["method"] == "GET"

    # Staging object cleaned up on success
    gcs_client.bucket.blob.return_value.delete.assert_called_once()


async def test_process_upload_failure_marks_failed(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)
    repo.rows[upload_id]["status"] = "pending"

    with patch("src.business.process_audio_shared", side_effect=RuntimeError("corrupt header")):
        record = await upload_service.process_upload(upload_id)

    assert record["status"] == "failed"
    assert "corrupt header" in record["error_message"]
    gcs_client.bucket.blob.return_value.delete.assert_not_called()


async def test_process_upload_unknown_upload(repo, gcs_client):
    with pytest.raises(ResourceNotFoundError):
        await upload_service.process_upload(str(uuid.uuid4()))


# ============================================================================
# get_job
# ============================================================================

async def test_get_job_unknown(repo, gcs_client):
    with pytest.raises(ResourceNotFoundError):
        await upload_service.get_job(str(uuid.uuid4()))


async def test_get_job_shapes(repo, gcs_client):
    upload_id = await _staged_upload(repo, gcs_client)

    job = await upload_service.get_job(upload_id)
    assert job["job_id"] == upload_id
    assert job["status"] == "awaiting_upload"
    assert "audio_id" not in job and "error" not in job

    audio_id = str(uuid.uuid4())
    repo.rows[upload_id].update(status="complete", audio_id=audio_id)
    job = await upload_service.get_job(upload_id)
    assert job["audio_id"] == audio_id

    repo.rows[upload_id].update(status="failed", error_message="boom")
    job = await upload_service.get_job(upload_id)
    assert job["error"] == "boom"


# ============================================================================
# End-to-end flow (mocked GCS + pipeline)
# ============================================================================

async def test_full_upload_flow(repo, gcs_client):
    """create -> (browser PUT simulated) -> process -> poll -> audio_id."""
    created = await upload_service.create_upload(
        {"filename": "album track.flac", "content_type": "audio/flac", "size_bytes": 50 * 1024 * 1024}
    )
    upload_id = created["upload_id"]

    # Simulate the browser PUT: the staged blob now exists with real facts
    blob = gcs_client.bucket.blob.return_value
    blob.exists.return_value = True
    blob.size = 50 * 1024 * 1024
    blob.content_type = "audio/flac"

    audio_id = str(uuid.uuid4())
    # Dispatch runs the worker inline (the local-dev fallback path, awaited)
    async def inline_dispatch(uid):
        with patch("src.business.process_audio_shared", return_value=MagicMock(audio_id=audio_id)):
            await upload_service.process_upload(uid)

    with patch.object(upload_service, "_dispatch_processing") as dispatch:
        result = await upload_service.start_processing(upload_id)
        assert result["status"] == "pending"
        await inline_dispatch(dispatch.call_args.args[0])

    job = await upload_service.get_job(upload_id)
    assert job["status"] == "complete"
    assert job["audio_id"] == audio_id


# ============================================================================
# HTTP routes (envelope + status codes)
# ============================================================================

@pytest.fixture
def api_client():
    from starlette.testclient import TestClient
    from src.server import mcp

    with TestClient(mcp.http_app()) as client:
        yield client


def test_route_create_upload_201(api_client, repo, gcs_client):
    response = api_client.post("/api/v1/uploads", json=dict(VALID_REQUEST))
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["signed_put_url"]
    assert body["upload_id"]


def test_route_create_upload_rejects_bad_body(api_client, repo, gcs_client):
    response = api_client.post(
        "/api/v1/uploads",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "VALIDATION_ERROR"


def test_route_create_upload_rejects_bad_type(api_client, repo, gcs_client):
    response = api_client.post(
        "/api/v1/uploads", json=dict(VALID_REQUEST, content_type="text/html")
    )
    assert response.status_code == 400
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_route_process_202_and_validation(api_client, repo, gcs_client):
    created = api_client.post("/api/v1/uploads", json=dict(VALID_REQUEST)).json()
    upload_id = created["upload_id"]

    with patch.object(upload_service, "_dispatch_processing"):
        response = api_client.post(f"/api/v1/uploads/{upload_id}/process")
    assert response.status_code == 202
    assert response.json()["job_id"] == upload_id

    # Second trigger while pending -> 400
    response = api_client.post(f"/api/v1/uploads/{upload_id}/process")
    assert response.status_code == 400


def test_route_process_unknown_404(api_client, repo, gcs_client):
    response = api_client.post(f"/api/v1/uploads/{uuid.uuid4()}/process")
    assert response.status_code == 404
    assert response.json()["error"] == "RESOURCE_NOT_FOUND"


def test_route_job_polling(api_client, repo, gcs_client):
    created = api_client.post("/api/v1/uploads", json=dict(VALID_REQUEST)).json()
    upload_id = created["upload_id"]

    response = api_client.get(f"/api/v1/jobs/{upload_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_upload"

    response = api_client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404

    response = api_client.get("/api/v1/jobs/not-a-uuid")
    assert response.status_code == 400
