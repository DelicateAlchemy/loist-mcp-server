"""
Unit tests for the REST API bearer-token middleware (src/api_auth.py).

The middleware is tested against a minimal Starlette app so no database or
FastMCP setup is involved. Config flags are monkeypatched per-test.
"""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.api_auth import BearerAuthMiddleware
from src.config import config


async def api_endpoint(request):
    return PlainTextResponse("api ok")


async def other_endpoint(request):
    return PlainTextResponse("other ok")


@pytest.fixture
def client():
    app = Starlette(routes=[
        Route("/api/v1/tracks", api_endpoint),
        Route("/embed/something", other_endpoint),
    ])
    return TestClient(BearerAuthMiddleware(app))


def test_disabled_auth_passes_through(client, monkeypatch):
    monkeypatch.setattr(config, "auth_enabled", False)

    assert client.get("/api/v1/tracks").status_code == 200


def test_enabled_auth_rejects_missing_token(client, monkeypatch):
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", "secret-token")

    response = client.get("/api/v1/tracks")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "UNAUTHORIZED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_enabled_auth_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", "secret-token")

    response = client.get(
        "/api/v1/tracks", headers={"Authorization": "Bearer wrong-token"}
    )

    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"


def test_enabled_auth_accepts_valid_token(client, monkeypatch):
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", "secret-token")

    response = client.get(
        "/api/v1/tracks", headers={"Authorization": "Bearer secret-token"}
    )

    assert response.status_code == 200
    assert response.text == "api ok"


def test_non_api_paths_are_not_protected(client, monkeypatch):
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", "secret-token")

    assert client.get("/embed/something").status_code == 200


def test_options_preflight_bypasses_auth(monkeypatch):
    """CORS preflight requests carry no Authorization header and must pass."""
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", "secret-token")

    app = Starlette(routes=[
        Route("/api/v1/tracks", api_endpoint, methods=["GET", "OPTIONS"]),
    ])
    client = TestClient(BearerAuthMiddleware(app))

    assert client.options("/api/v1/tracks").status_code == 200


def test_missing_token_config_fails_closed(client, monkeypatch):
    """auth_enabled without a configured token must reject, not allow."""
    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "bearer_token", None)

    response = client.get(
        "/api/v1/tracks", headers={"Authorization": "Bearer anything"}
    )

    assert response.status_code == 500
    assert response.json()["error"] == "INTERNAL_ERROR"
