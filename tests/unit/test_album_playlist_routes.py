"""
Route-level tests for the album & playlist REST API (LOI-47).

These tests exercise the HTTP layer only: paths under /api/v1, the standard
error envelope ({"success": false, "error": "<CODE>", "message": "..."}),
and status codes. The service layer is mocked, so no database is required.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.exceptions import ResourceNotFoundError
from src.services import album_service, playlist_service

ALBUM_ID = str(uuid.uuid4())
PLAYLIST_ID = str(uuid.uuid4())
TRACK_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())

SAMPLE_ALBUM = {
    "id": ALBUM_ID,
    "name": "Test Album",
    "description": None,
    "status": "project",
    "cover_art_gcs_path": None,
    "owner_id": None,
    "track_count": 0,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "tracks": [],
}

SAMPLE_PLAYLIST = {
    "id": PLAYLIST_ID,
    "name": "Test Playlist",
    "description": None,
    "is_public": False,
    "owner_id": None,
    "track_count": 0,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "tracks": [],
    "collaborators": [],
}


@pytest.fixture
def api_client():
    from starlette.testclient import TestClient

    from src.server import mcp

    with TestClient(mcp.http_app()) as client:
        yield client


# ============================================================================
# Album routes
# ============================================================================


def test_route_create_album_201(api_client):
    with patch.object(album_service, "create_album", AsyncMock(return_value=SAMPLE_ALBUM)):
        response = api_client.post("/api/v1/albums", json={"name": "Test Album"})
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["album"]["id"] == ALBUM_ID


def test_route_get_album_200(api_client):
    with patch.object(album_service, "get_album", AsyncMock(return_value=SAMPLE_ALBUM)):
        response = api_client.get(f"/api/v1/albums/{ALBUM_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["album"]["name"] == "Test Album"


def test_route_get_album_bad_uuid_400_envelope(api_client):
    response = api_client.get("/api/v1/albums/not-a-uuid")
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "VALIDATION_ERROR"
    assert body["message"]


def test_route_get_album_404_envelope(api_client):
    with patch.object(
        album_service,
        "get_album",
        AsyncMock(side_effect=ResourceNotFoundError("Album not found")),
    ):
        response = api_client.get(f"/api/v1/albums/{ALBUM_ID}")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "RESOURCE_NOT_FOUND"


def test_route_search_albums_200(api_client):
    result = {"albums": [SAMPLE_ALBUM], "total": 1, "limit": 20, "offset": 0}
    with patch.object(album_service, "search_albums", AsyncMock(return_value=result)):
        response = api_client.get("/api/v1/albums", params={"q": "test"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_route_search_albums_missing_query_400(api_client):
    response = api_client.get("/api/v1/albums")
    assert response.status_code == 400
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_route_delete_album_204(api_client):
    with patch.object(album_service, "delete_album", AsyncMock(return_value=True)):
        response = api_client.delete(f"/api/v1/albums/{ALBUM_ID}")
    assert response.status_code == 204


def test_route_add_album_track_requires_track_id(api_client):
    response = api_client.post(f"/api/v1/albums/{ALBUM_ID}/tracks", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_route_add_album_track_201(api_client):
    track = {"audio_track_id": TRACK_ID, "position": 1, "disc_number": 1}
    with patch.object(album_service, "add_track_to_album", AsyncMock(return_value=track)):
        response = api_client.post(
            f"/api/v1/albums/{ALBUM_ID}/tracks", json={"audio_track_id": TRACK_ID}
        )
    assert response.status_code == 201
    assert response.json()["track"]["audio_track_id"] == TRACK_ID


# ============================================================================
# Playlist routes
# ============================================================================


def test_route_create_playlist_201(api_client):
    with patch.object(playlist_service, "create_playlist", AsyncMock(return_value=SAMPLE_PLAYLIST)):
        response = api_client.post("/api/v1/playlists", json={"name": "Test Playlist"})
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["playlist"]["id"] == PLAYLIST_ID


def test_route_get_playlist_200(api_client):
    with patch.object(playlist_service, "get_playlist", AsyncMock(return_value=SAMPLE_PLAYLIST)):
        response = api_client.get(f"/api/v1/playlists/{PLAYLIST_ID}")
    assert response.status_code == 200
    assert response.json()["playlist"]["name"] == "Test Playlist"


def test_route_get_playlist_bad_uuid_400_envelope(api_client):
    response = api_client.get("/api/v1/playlists/not-a-uuid")
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "VALIDATION_ERROR"


def test_route_get_playlist_404_envelope(api_client):
    with patch.object(
        playlist_service,
        "get_playlist",
        AsyncMock(side_effect=ResourceNotFoundError("Playlist not found")),
    ):
        response = api_client.get(f"/api/v1/playlists/{PLAYLIST_ID}")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "RESOURCE_NOT_FOUND"


def test_route_delete_playlist_204(api_client):
    with patch.object(playlist_service, "delete_playlist", AsyncMock(return_value=True)):
        response = api_client.delete(f"/api/v1/playlists/{PLAYLIST_ID}")
    assert response.status_code == 204


def test_route_add_collaborator_201(api_client):
    collaborator = {"user_id": USER_ID, "role": "viewer", "created_at": "2026-01-01T00:00:00"}
    with patch.object(playlist_service, "add_collaborator", AsyncMock(return_value=collaborator)):
        response = api_client.post(
            f"/api/v1/playlists/{PLAYLIST_ID}/collaborators", json={"user_id": USER_ID}
        )
    assert response.status_code == 201
    assert response.json()["collaborator"]["user_id"] == USER_ID


def test_route_add_collaborator_requires_user_id(api_client):
    response = api_client.post(f"/api/v1/playlists/{PLAYLIST_ID}/collaborators", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_route_reorder_playlist_tracks_requires_order(api_client):
    response = api_client.put(f"/api/v1/playlists/{PLAYLIST_ID}/tracks/order", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "VALIDATION_ERROR"


# ============================================================================
# Old unversioned paths must no longer exist
# ============================================================================


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/albums"),
        ("get", "/api/albums"),
        ("get", f"/api/albums/{ALBUM_ID}"),
        ("put", f"/api/albums/{ALBUM_ID}"),
        ("delete", f"/api/albums/{ALBUM_ID}"),
        ("post", f"/api/albums/{ALBUM_ID}/tracks"),
        ("post", "/api/playlists"),
        ("get", "/api/playlists"),
        ("get", f"/api/playlists/{PLAYLIST_ID}"),
        ("delete", f"/api/playlists/{PLAYLIST_ID}"),
        ("post", f"/api/playlists/{PLAYLIST_ID}/collaborators"),
    ],
)
def test_old_unversioned_paths_are_gone(api_client, method, path):
    response = getattr(api_client, method)(path)
    assert response.status_code == 404
