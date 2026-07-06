# Loist REST API — Frontend Guide (v1)

**Status:** Current as of July 2026 (LOI-38) · **Audience:** Frontend team (wireframing → implementation)
**Base path:** `/api/v1` · **Format:** JSON over HTTPS

This is the authoritative reference for the REST API a frontend can build
against today. It supersedes the endpoint lists scattered across older docs
(`api-endpoint-refactoring.md`, `download-endpoint-api.md`, etc.).

---

## 1. Architecture in one paragraph

The backend serves two independent interfaces over one shared service layer:
the **REST API** (this document, for frontends) and **MCP tools** (for AI
agents). REST is *not* a wrapper around MCP — both call the same
`src/services/` functions, and the REST contract evolves independently of MCP
tool signatures. Build against this document, not the MCP tool docs.

```
Frontend (you)  ──HTTP──>  REST API  /api/v1/*  ──┐
                                                  ├──>  shared services ──> Postgres + GCS
AI agents       ──MCP───>  MCP tools (/mcp)  ─────┘
```

## 2. Environments

| Environment | Base URL | Notes |
|---|---|---|
| Local dev | `http://localhost:8080` | `python run_server.py` (see README) |
| Staging | `https://staging.loist.io` | Cloud Run |

CORS is enabled. Local dev allows `localhost:3000`, `localhost:5173`, and
`localhost:8000` origins out of the box. Before production launch,
`CORS_ORIGINS` will be set to the frontend's real origin. The response headers
you need (`ETag`, `X-Total-Count`, `Link`, `X-Conversion-Time`) are exposed to
browser JavaScript.

## 3. Authentication

**Today: none.** All endpoints are open (`AUTH_ENABLED=false`).

**Planned (scaffolded, not yet enabled):** static bearer token —
`Authorization: Bearer <token>` on every `/api/v1/*` request. When enabled,
missing/invalid tokens return `401` with the standard error envelope and a
`WWW-Authenticate: Bearer` header. Embed player URLs, oEmbed, and health
checks stay public. Design and rollout plan: `docs/rest-api-auth-plan.md`.

**Wireframe implication:** don't design a login flow yet — the near-term model
is a single-tenant token, not user accounts. Multi-user auth is a separate,
undiscovered workstream (LOI-5).

## 4. Conventions

### Success responses

`200` JSON bodies always include `"success": true`. Deletes return `204` with
no body. Media endpoints (stream/thumbnail/some downloads) return `302`
redirects to short-lived signed Google Cloud Storage URLs — just follow them
(browsers, `<audio>` tags, and `fetch` do this automatically).

### Error envelope (all endpoints, all error statuses)

```json
{
  "success": false,
  "error": "TRACK_NOT_FOUND",
  "message": "Track 00000000-0000-0000-0000-000000000000 not found"
}
```

`error` is a stable machine-readable code — switch on it, not on `message`.

| Code | HTTP status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Bad path/query parameter (e.g. malformed UUID, bad format) |
| `INVALID_QUERY` | 400 | Bad search parameters (missing/empty `q`, limit out of range) |
| `UNAUTHORIZED` | 401 | Missing/invalid bearer token (once auth is enabled) |
| `TRACK_NOT_FOUND` | 404 | No track with that ID |
| `CONVERSION_FAILED` | 500 | Audio format conversion failed |
| `SEARCH_FAILED` | 500 | Search backend error |
| `INTERNAL_ERROR` | 500 | Anything else unexpected |
| `CONVERSION_TIMEOUT` | 504 | Conversion exceeded time budget |

### Pagination

Search uses `limit` (1–100, default 20) and `offset` query params. The
response body carries `total` / `has_more`, and the same information is
mirrored in headers: `X-Total-Count` and RFC-5988 `Link` (`rel="next"` /
`rel="prev"`).

### Caching

Track metadata responses send `ETag` and `Cache-Control: public, max-age=3600,
must-revalidate`, and honor `If-None-Match` (returns `304`).

## 5. Entities

### Track

Returned by `GET /api/v1/tracks/{audioId}`; the same `metadata` object appears
inside search results.

```jsonc
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "product": {
      "artist": "The Beatles",
      "title": "Hey Jude",
      "album": "Past Masters",        // nullable
      "mbid": null,                    // MusicBrainz ID, null in MVP
      "genre": ["Rock"],               // list, may be empty
      "year": 1968                     // nullable
    },
    "format": {
      "duration": 431.0,               // seconds, nullable
      "channels": 2,                   // nullable
      "sample_rate": 44100,            // nullable
      "bitrate": 320000,               // nullable
      "format": "MP3"
    },
    "url_embed_link": "https://loist.io/embed/550e8400-..."
  },
  "resources": {
    "audio_url": "...",                // internal URI; use /stream to play
    "thumbnail_url": "...",            // nullable; use /thumbnail to display
    "waveform_url": null               // null in MVP
  }
}
```

> For playback and artwork, use the `/stream` and `/thumbnail` endpoints
> below rather than the `resources` URIs — the endpoints handle signed-URL
> generation and expiry for you.

### Search result

```jsonc
{
  "success": true,
  "results": [
    {
      "audio_id": "550e8400-e29b-41d4-a716-446655440000",
      "metadata": { /* same shape as Track.metadata above */ },
      "score": 0.87                    // relevance, higher = better
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "facets": null                       // optional facet counts (composers, publishers, record labels)
}
```

## 6. Endpoints

### `GET /api/v1/tracks/{audioId}`
Track metadata. `audioId` is a UUID.
Returns the Track entity above; `304` on ETag match; `404 TRACK_NOT_FOUND`.

### `GET /api/v1/search?q=<query>&limit=20&offset=0&genre=Rock,Jazz`
Full-text search over the library. `q` is required (1–500 chars); `genre` is
an optional comma-separated filter. Returns the search result shape above
plus `X-Total-Count` and `Link` headers.

### `GET /api/v1/tracks/{audioId}/stream`
`302` redirect to a signed GCS URL for the audio file. Point an `<audio src>`
directly at this endpoint; Range requests (seeking) work on the signed URL.
Signed URLs expire after ~15 minutes — always link to this endpoint, never
store the redirect target.

### `GET /api/v1/tracks/{audioId}/thumbnail`
`302` redirect to a signed URL for the artwork image. Same expiry caveat.
`404` if the track has no artwork.

### `GET /api/v1/tracks/{audioId}/download?format=mp3&preset=high`
Download with optional format conversion. `format` is required: `mp3`, `wav`,
`flac`, `aac`, `ogg`. `preset` is optional (per-format quality, defaults
applied server-side). Same-format downloads redirect (`302`) to a signed URL;
conversions stream back directly with `Content-Disposition: attachment` and an
`X-Conversion-Time` header. Conversions can take seconds — design for a
pending state. Errors: `CONVERSION_FAILED` (500), `CONVERSION_TIMEOUT` (504).

### `DELETE /api/v1/tracks/{audioId}`
Deletes the track and its stored files. `204` on success, `404` if unknown.
**Irreversible — wireframes should include a confirm step.**

## 7. Embed player (separate from the REST API)

Each track has a hosted embed player at `url_embed_link`
(`/embed/{audioId}`, plus waveform variants and oEmbed discovery at
`/oembed`). These are public HTML pages meant for iframes and social unfurls,
not JSON endpoints, and they are intentionally outside `/api/v1` and outside
the auth boundary. See `docs/embed-player-guide.md`.

## 8. What exists vs. what doesn't (wireframe checklist)

Available via REST **today** — safe to wireframe against:

- Library search with pagination + genre filter
- Track detail (metadata, artwork, duration)
- In-browser playback (stream endpoint) and embeds
- Download in multiple formats
- Delete track

**Coming to the REST API** (status per `docs/rest-api-expansion-plan.md`;
flag wireframes that depend on these so backend work can be sequenced):

- Upload / ingestion — genuinely missing; will be a GCS signed-URL flow with
  async processing + job polling (LOI-45). Design for a pending state.
- Metadata editing — `PATCH /api/v1/tracks/{audioId}` planned (LOI-46).
- Parties (people/organizations) and Works (compositions, writers/publishers,
  artist↔recording links) — REST routes already exist on `origin/dev`; being
  brought under `/api/v1` + this guide's conventions (LOI-44).
- Albums & playlists — full REST surface exists on `main` (not yet on `dev`);
  landing via LOI-43/LOI-47.
- Player/waveform data as JSON — decided with the embed rework
  (`docs/embed-architecture-notes.md`, LOI-48), not standalone.

Not built anywhere: user accounts, favorites, multi-tenancy (LOI-5, no
discovery done yet).

## 9. Changelog

- **July 2026 (LOI-38):** All endpoints moved from `/api/*` to `/api/v1/*`
  (clean cutover — old paths now 404). Error envelope standardized. CORS fixed
  and verified for browser use. Bearer-token auth scaffolded (off by default).
