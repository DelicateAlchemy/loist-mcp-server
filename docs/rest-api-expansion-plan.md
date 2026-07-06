# REST API Expansion Plan — closing the MCP-only gaps

**Date:** July 6, 2026 · **Follows:** LOI-38 (API hardening) · **Status:** Plan — issues tracked in Linear

The LOI-38 frontend guide listed capabilities that exist "as MCP tools only."
Investigating how to build the missing REST endpoints surfaced something more
urgent first: **the repo's branches have diverged**, and part of the "missing"
API surface already exists — just not where this checkout could see it.

## 0. Ground truth: three divergent lines (July 2026)

| Line | Has | Lacks |
|---|---|---|
| local `dev` (base of the LOI-38 branch) | 6 track/search REST routes, 10 MCP tools | everything below |
| `origin/dev` (+7 commits) | **Song publishing** — party/work services, MCP tools, and 8 REST routes (`/api/parties*`, `/api/works/*`, `/api/tracks/{id}/artists`); ruff migration; GCS identity fix | albums/playlists |
| `origin/main` (+2 commits not on dev) | **Albums & playlists** — ~18 REST routes (`/api/albums*`, `/api/playlists*`), waveform metrics hardening | song publishing |

The deployed staging MCP server runs the `origin/dev` line (its tool list
includes party/work tools, no album/playlist tools). So:

- The LOI-38 ticket's mention of party/work REST routes was correct **against
  `origin/dev`** — the local checkout was stale.
- The LOI-38 branch (v1 prefix, error envelope, auth, CORS) was cut from the
  stale base and **must be rebased onto `origin/dev`**, extending the v1
  prefix + error envelope + frontend-guide coverage to the 8 publishing routes.
- Albums/playlists — exactly what a frontend needs — are stranded on `main`
  and never made it to `dev`. Branch reconciliation is a prerequisite for the
  album/playlist REST work, not an optional cleanup.

## 1. True gaps after reconciliation

### 1a. Upload / ingestion — the big design piece

`process_audio_complete` (MCP) only accepts `{"type": "http_url", ...}` — it
downloads from a URL. There is **no browser-upload path at all**, and a naive
`POST` multipart endpoint won't work: `MAX_FILE_SIZE` is 100 MB but Cloud Run
caps HTTP request bodies at 32 MiB. The upload flow must go around the server:

```
1. POST /api/v1/uploads {filename, contentType, sizeBytes}
      → 201 {upload_id, signed_put_url, expires_at}     (GCS V4 signed PUT)
2. Browser PUTs the file directly to GCS (progress events work natively)
3. POST /api/v1/uploads/{upload_id}/process
      → 202 {job_id}   — triggers the existing pipeline with a GCS source
4. GET /api/v1/jobs/{job_id}
      → {status: pending|processing|complete|failed, audio_id?, error?}
```

Backend work implied: a `gcs` source type for the ingestion pipeline (or
internally signing a GET URL for its own bucket and reusing the `http_url`
path — pragmatic first cut), an uploads/jobs tracking table, and reuse of the
existing Cloud Tasks async machinery (`src/tasks/`) for step 3. Processing
takes seconds-to-minutes, so 202 + polling is the contract; SSE/webhooks can
come later.

### 1b. Track metadata editing

`update_metadata` (MCP) delegates to `src/tools/update_tools.py` — note: a
`tools/` module, not `src/services/`, so the "shared service layer" claim is
slightly aspirational here. Plan: extract/confirm the update logic as a
service function, expose `PATCH /api/v1/tracks/{audioId}` accepting a partial
metadata document, validate with the existing schemas, return the updated
Track entity. Small, self-contained.

### 1c. Albums & playlists

Full REST surface already written (on `main`): CRUD + track membership +
ordering for albums and playlists. Work: get it onto `dev` (reconciliation),
then apply the LOI-38 conventions (v1 prefix, error envelope, auth boundary),
add to the frontend guide. Mostly integration work, little new code.

### 1d. Song publishing (parties/works)

Already on `origin/dev` as REST. Work is folded into the LOI-38 rebase:
apply v1 prefix + envelope, document in the frontend guide (these routes
currently use their own response shapes — need auditing against the envelope).

### 1e. Waveform data as JSON

`get_waveform_metrics_tool` exposes *operational metrics*, not waveform peaks
— it is not the frontend feature. What a custom frontend player actually
needs is the waveform *rendering data* (peaks array / SVG) that the embed
templates currently consume server-side. This belongs to the embed/player-API
work (see `docs/embed-architecture-notes.md`) rather than a standalone
endpoint designed in a vacuum.

## 2. Sequencing

```
Reconcile main↔dev  ──►  Rebase LOI-38 onto origin/dev  ──►  merge LOI-38
        │                        (incl. publishing routes under v1)
        └──►  Albums/playlists v1  ─┐
              Upload/ingestion flow ├──  independent after LOI-38 merges
              PATCH metadata        │
              Player/waveform API  ─┘  (with embed rework, LOI-45)
```

## 3. Linear issues

Tracked as an umbrella issue with children (created 2026-07-06; see Linear
for current state): branch reconciliation, LOI-38 rebase, upload flow,
metadata PATCH, albums/playlists v1, and the embed/player API notes issue.
