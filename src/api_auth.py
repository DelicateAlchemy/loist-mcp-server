"""
Bearer-token authentication middleware for the REST API.

Scaffolding for the frontend auth story (see docs/rest-api-auth-plan.md):
a single static bearer token, checked on every /api/* request, gated behind
AUTH_ENABLED (default off, so nothing changes for the current MVP deploys).

This deliberately does NOT cover the MCP endpoint (/mcp), embed player routes
(/embed/*), oEmbed, or health checks — those have their own access models.
Pure ASGI middleware (not BaseHTTPMiddleware) so StreamingResponse bodies and
their BackgroundTask cleanups pass through untouched.
"""

import hmac
import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import config
from src.schemas.http_api import ErrorCode

logger = logging.getLogger(__name__)

PROTECTED_PREFIX = "/api/"


class BearerAuthMiddleware:
    """
    Require `Authorization: Bearer <token>` on /api/* requests when
    config.auth_enabled is true.

    Config is read per-request so tests (and future hot-reload) can toggle
    auth without rebuilding the app.
    """

    def __init__(self, app: ASGIApp, protected_prefix: str = PROTECTED_PREFIX):
        self.app = app
        self.protected_prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith(self.protected_prefix) or not config.auth_enabled:
            await self.app(scope, receive, send)
            return

        # CORS preflight requests never carry credentials; the browser sends
        # the Authorization header on the actual request only.
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if not config.bearer_token:
            # Fail closed: auth is on but no token is configured.
            logger.error("AUTH_ENABLED is true but BEARER_TOKEN is not set; rejecting request")
            response = JSONResponse(
                {
                    "success": False,
                    "error": ErrorCode.INTERNAL_ERROR,
                    "message": "Server authentication is misconfigured",
                },
                status_code=500,
            )
            await response(scope, receive, send)
            return

        if not self._is_authorized(scope):
            response = JSONResponse(
                {
                    "success": False,
                    "error": ErrorCode.UNAUTHORIZED,
                    "message": "Missing or invalid bearer token",
                },
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _is_authorized(self, scope: Scope) -> bool:
        auth_header = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                auth_header = value.decode("latin-1")
                break

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return False

        return hmac.compare_digest(token.strip(), config.bearer_token)


__all__ = ["BearerAuthMiddleware", "PROTECTED_PREFIX"]
