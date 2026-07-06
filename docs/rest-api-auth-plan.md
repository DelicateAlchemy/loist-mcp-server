# REST API Authentication Plan

**Date:** July 6, 2026 · **Issue:** LOI-38 · **Status:** Phase 1 scaffolded (off by default)

## Where we are

`AUTH_ENABLED=false` everywhere. Until LOI-38, the auth story was worse than
"disabled": `SimpleBearerAuth` (`src/auth/bearer.py`, a FastMCP `AuthProvider`)
was instantiated in `src/server.py` but never passed to the `FastMCP(...)`
constructor, so even flipping the flag would have protected nothing.

## Decisions

1. **The REST API and the MCP endpoint get separate auth mechanisms.** REST
   uses plain ASGI middleware (`src/api_auth.py`); MCP will use a FastMCP
   `AuthProvider` when needed. They share the same token config for now but
   can diverge without touching each other.
2. **Public surfaces stay public:** embed player pages (`/embed/*`), oEmbed
   (`/oembed`, `/.well-known/oembed.json`), and health checks (`/health/*`)
   are outside the auth boundary by design — embeds must work in third-party
   iframes and Cloud Run must probe health unauthenticated.
3. **Token travels in the `Authorization: Bearer` header, never cookies.**
   This keeps CORS simple (no credentialed requests, no CSRF surface).

## Phase 1 — shipped with LOI-38 (scaffold, off by default)

`BearerAuthMiddleware` (`src/api_auth.py`) guards every `/api/*` path:

- Gated on `AUTH_ENABLED`; a no-op when false, so current deploys are unchanged.
- Validates `Authorization: Bearer <token>` against `BEARER_TOKEN`
  (constant-time comparison).
- `401` + `WWW-Authenticate: Bearer` + standard error envelope
  (`"error": "UNAUTHORIZED"`) on failure.
- CORS preflight (`OPTIONS`) passes through — browsers do not attach
  `Authorization` to preflights.
- Fails **closed** (500) if `AUTH_ENABLED=true` but no token is configured.
- Sits *inside* the CORS middleware so 401s carry CORS headers and are
  readable by the frontend.

Frontend contract when enabled: attach the header to every `/api/v1` call;
treat `401` as "re-authenticate", not as a retryable error.

### Enabling it (staging first)

```
AUTH_ENABLED=true
BEARER_TOKEN=<from Secret Manager, not plaintext env>
```

## Phase 2 — before a public frontend launch

Single static token is fine while the frontend and backend are operated by the
same team (token lives server-side in the frontend's BFF/proxy, or the app is
private). Before real users:

- **Per-client tokens with revocation** (DB-backed API keys) *or* short-lived
  JWTs issued by an identity provider — decision depends on the LOI-5
  multi-tenancy discovery, which owns the "who are the users?" question.
- Rotate via Secret Manager; never bake tokens into frontend bundles — a
  browser-delivered SPA must not hold the static token (anyone can read it).
  If the frontend is a SPA calling this API directly, Phase 2 is a **launch
  blocker**, not a nice-to-have.
- Rate limiting (still an open question in `api-endpoint-refactoring.md`)
  becomes meaningful once tokens identify clients.

## Phase 3 — user-level auth

Blocked on LOI-5 (multi-tenancy discovery). Out of scope here; nothing in
Phase 1/2 should be built in a way that assumes single-tenancy is permanent.

## Test coverage

`tests/unit/test_api_auth.py` — enabled/disabled, valid/invalid/missing token,
non-API paths untouched, OPTIONS bypass, fail-closed misconfiguration.
