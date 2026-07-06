# CORS Configuration Audit Report

**Date:** December 3, 2025
**Auditor:** Task Master AI

## 1. Executive Summary

The CORS configuration for the MCP server is handled by `starlette.middleware.cors.CORSMiddleware`. The configuration is loaded from environment variables and is sufficiently permissive for local development and testing with the MCP Inspector.

## 2. Configuration Files

-   **`src/config.py`**: Defines the default CORS configuration values.
-   **`src/server.py`**: Applies the CORS middleware to the Starlette application.
-   **`docker-compose.yml`**: Overrides the default `CORS_ORIGINS` for local development.

## 3. Configuration Details

The following environment variables control the CORS configuration:

| Variable                 | `src/config.py` Default                                         | `docker-compose.yml` Override                               |
| ------------------------ | --------------------------------------------------------------- | ----------------------------------------------------------- |
| `ENABLE_CORS`            | `True`                                                          | `true`                                                      |
| `CORS_ORIGINS`           | `*`                                                             | `http://localhost:3000,http://localhost:8000,http://localhost:5173` |
| `CORS_ALLOW_CREDENTIALS` | `True`                                                          | `true`                                                      |
| `CORS_ALLOW_METHODS`     | `GET,POST,OPTIONS`                                              | Not set (uses default)                                      |
| `CORS_ALLOW_HEADERS`     | `Authorization,Content-Type,Range,X-Requested-With,Accept,Origin` | Not set (uses default)                                      |
| `CORS_EXPOSE_HEADERS`    | `Content-Range,Accept-Ranges,Content-Length,Content-Type`         | Not set (uses default)                                      |

## 4. Analysis

The current configuration is suitable for local development. The `CORS_ORIGINS` setting in `docker-compose.yml` allows requests from common local development servers.

For the MCP Inspector running in a browser, the default configuration should be sufficient, as it allows requests from any origin. If the Inspector is running on a different origin and credentials are required, the `CORS_ORIGINS` would need to be updated to include the Inspector's origin.

## 5. Conclusion

The CORS configuration is correctly implemented and is flexible enough for both development and production environments by adjusting the environment variables. No immediate changes are required for the current task.

---

## 6. Re-Audit — July 6, 2026 (LOI-38)

**The December 2025 conclusion above was wrong in practice.** The CORS middleware
was configured in `create_http_app()` in `src/server.py`, but that function was
**never called**: the production entrypoint (`run_server.py`, per the Dockerfile
`CMD`) invokes `mcp.run(transport="http")` directly, and FastMCP (2.12.x) adds no
CORS middleware of its own. **The deployed server therefore sent no CORS headers
at all** — any browser frontend on a different origin would have been blocked.

### Fixes applied (LOI-38)

1. **Wiring:** `create_http_app()` was replaced by `build_http_middleware()` in
   `src/server.py`, and the middleware list is now passed to
   `mcp.run(transport="http", middleware=...)` in both `run_server.py` and the
   `src/server.py` `__main__` branches. This is the only wiring point that
   reaches the running server.
2. **`DELETE` added to `CORS_ALLOW_METHODS`** — the API exposes
   `DELETE /api/v1/tracks/{audioId}`, but preflight would have rejected it.
3. **Exposed headers extended** with `ETag`, `X-Total-Count`, `Link`, and
   `X-Conversion-Time` — set by the REST API but previously unreadable from
   browser JavaScript.
4. **`CORS_ALLOW_CREDENTIALS` default changed to `false`** — browsers reject
   wildcard origins combined with credentials, so the old default
   (`CORS_ORIGINS=*` + credentials) was self-contradictory. REST auth uses the
   `Authorization` header, which does not require credentialed CORS. Enable
   credentials only together with an explicit origin allowlist if cookie-based
   auth is ever adopted.
5. **Middleware order:** CORS is outermost so auth rejections (401 from the
   bearer-token middleware) still carry CORS headers and are readable by
   frontends.

### Production guidance for frontend launch

Set `CORS_ORIGINS` to an explicit allowlist (e.g. `https://app.loist.io`)
instead of `*` before the frontend goes live. Everything else works with the
defaults.
