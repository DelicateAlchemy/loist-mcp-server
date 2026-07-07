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
| `RESOURCE_NOT_FOUND` | 404 | No party/work with that ID (publishing endpoints) |
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

### Party

A person or organization involved in publishing: writer, publisher, artist,
or label. Returned by the `/api/v1/parties/*` endpoints; `GET` by ID also
includes an involvement summary (works written/published, recordings).

```jsonc
{
  "success": true,
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "name": "John Lennon",
  "party_type": "person",              // "person" | "organization"
  "legal_name": "John Winston Ono Lennon",  // nullable
  "ipi_cae_number": null,              // CAE/IPI identifier, nullable
  "isni": null,                        // ISNI identifier, nullable
  "society_affiliation": "PRS",        // PRO affiliation, nullable
  "email": null,                       // nullable
  "notes": null                        // nullable
}
```

### Work

A musical composition (distinct from a recording/track). `GET` by ID returns
the work with its writers, publishers, alternative titles, linked recordings,
and split warnings (e.g. splits that don't sum to 100%).

```jsonc
{
  "success": true,
  "id": "9b2f3c44-1d26-4b5a-8f0e-2a7d93c1e001",
  "title": "Imagine",
  "iswc": "T-010.140.236-1",           // nullable
  "language": "en",                    // ISO 639-1, nullable
  "status": "draft",                   // workflow status
  "writers": [
    {
      "party_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "split_percentage": 100.0,       // nullable
      "split_status": "confirmed"      // "proposed" | "confirmed" | "disputed" | "unknown"
    }
  ],
  "publishers": [ /* same shape as writers */ ],
  "recordings": [ /* linked tracks */ ],
  "warnings": []                       // split-validation warnings
}
```

### Album

An ordered collection of tracks with a lifecycle status. `GET` by ID returns
the album with its tracks; search returns a lighter shape (no `tracks` array).
Album responses are wrapped: `{"success": true, "album": { ... }}`.

```jsonc
{
  "id": "3f2b8a10-6c1d-4e5f-9a7b-1c2d3e4f5a60",
  "name": "Abbey Road",
  "description": null,                 // nullable
  "status": "project",                 // "project" | "draft" | "released"
  "cover_art_gcs_path": null,          // nullable
  "owner_id": null,                    // UUID, nullable
  "track_count": 2,
  "created_at": "2026-07-01T12:00:00", // ISO timestamp
  "updated_at": "2026-07-01T12:00:00",
  "tracks": [
    {
      "audio_track_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Come Together",        // nullable
      "artist": "The Beatles",         // nullable
      "position": 1,                   // position within disc
      "disc_number": 1,
      "added_at": "2026-07-01T12:00:00"
    }
  ]
}
```

### Playlist

An ordered, optionally collaborative collection of tracks. `GET` by ID
returns the playlist with its tracks and collaborators. Playlist responses
are wrapped: `{"success": true, "playlist": { ... }}`.

```jsonc
{
  "id": "8a1c2d30-4b5e-4f6a-8b9c-0d1e2f3a4b50",
  "name": "Late Night Mix",
  "description": null,                 // nullable
  "is_public": false,
  "owner_id": null,                    // UUID, nullable
  "track_count": 1,
  "created_at": "2026-07-01T12:00:00",
  "updated_at": "2026-07-01T12:00:00",
  "tracks": [
    {
      "audio_track_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Come Together",        // nullable
      "artist": "The Beatles",         // nullable
      "position": 1,                   // position within playlist
      "added_by": null,                // UUID of adding user, nullable
      "added_at": "2026-07-01T12:00:00"
    }
  ],
  "collaborators": [
    {
      "user_id": "b7e2a910-1f2e-4c3d-9a8b-7c6d5e4f3a20",
      "role": "editor",                // "viewer" | "editor" | "admin"
      "created_at": "2026-07-01T12:00:00"
    }
  ]
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

### Uploads & ingestion

Adding music is a **three-step flow** — the file goes directly from the
browser to Google Cloud Storage (Cloud Run caps request bodies at 32 MiB, so
there is deliberately no multipart endpoint). **Design for a pending state:**
processing takes seconds to a minute, and the UI should show per-file
progress (upload) then a spinner/queue state (processing) before the track
appears in the library.

#### `POST /api/v1/uploads`
Declare the file and get a signed upload URL. Body:
`{"filename": "song.mp3", "content_type": "audio/mpeg", "size_bytes": 8388608}`.
Accepted types: mp3, wav, flac, aac, m4a/mp4, ogg, aiff. Max size 100 MB.
Returns `201`:

```jsonc
{
  "success": true,
  "upload_id": "0f0e6f1a-...",
  "signed_put_url": "https://storage.googleapis.com/...",  // valid ~60 min
  "expires_at": "2026-07-06T13:00:00+00:00",
  "required_headers": {"Content-Type": "audio/mpeg"}
}
```

Then `PUT` the raw file bytes to `signed_put_url` **with exactly that
`Content-Type` header** (it is baked into the signature). Use
`XMLHttpRequest`/`fetch` upload progress events for the progress bar.

#### `POST /api/v1/uploads/{uploadId}/process`
Tell the server the upload finished. The server re-validates the staged
object (exists, non-empty, within size limit) and dispatches processing.
Returns `202 {"success": true, "job_id": "...", "status": "pending"}`.
`400 VALIDATION_ERROR` if the file was never uploaded or fails validation;
re-`POST` is allowed after a `failed` job (retry).

#### `GET /api/v1/jobs/{jobId}`
Poll processing status (a sensible interval is 1–2 s):

```jsonc
{
  "success": true,
  "job_id": "0f0e6f1a-...",
  "status": "processing",   // awaiting_upload | pending | processing | complete | failed
  "filename": "song.mp3",
  "audio_id": "550e8400-...",  // present once complete — fetch the Track with it
  "error": "..."               // present when failed
}
```

On `complete`, `GET /api/v1/tracks/{audio_id}` returns the full Track
entity. `awaiting_upload` means `/process` was never called — a client bug.

### Publishing: parties & works

All under the same auth boundary and error envelope as the track endpoints.

#### `POST /api/v1/parties`
Create a party. Body: `{"name": "..."}` (required) plus any optional Party
fields above. Returns the created Party with `201`.

#### `GET /api/v1/parties/search?q=lennon&limit=20&offset=0`
Search parties by name. Same pagination shape as library search (`results` /
`total` / `has_more`), but note `total` reflects the returned page and
`has_more` is estimated from page size — there is no exact global count yet.

#### `GET /api/v1/parties/{partyId}`
Party detail with involvement summary. `404 RESOURCE_NOT_FOUND` if unknown.

#### `GET /api/v1/works/search?q=imagine&limit=20&offset=0`
Search works by title. Same pagination caveat as party search.

#### `GET /api/v1/works/{workId}`
Work detail — the full Work entity above, including writers, publishers,
recordings, and split warnings.

#### `PUT /api/v1/works/{workId}/writers`
**Batch replace** of all writers on the work (not a partial update — send the
complete list). Body:
`{"writers": [{"party_id": "...", "split_percentage": 50.0, "split_status": "confirmed", "notes": null}]}`.
Returns `{"success": true, "work_id": "...", "replaced_count": 2}`.

#### `PUT /api/v1/works/{workId}/publishers`
Same contract as `/writers`, with a `"publishers"` array.

#### `POST /api/v1/tracks/{audioId}/artists`
Link a party as an artist on a recording. Body:
`{"party_id": "...", "is_primary": true, "notes": null}` (`party_id`
required). Returns the created link with `201`.

### Albums & playlists

All under the same auth boundary and error envelope as the track endpoints.
Every `{albumId}` / `{playlistId}` / `{audioId}` / `{userId}` path parameter
is a UUID — malformed IDs return `400 VALIDATION_ERROR`, unknown IDs return
`404 RESOURCE_NOT_FOUND`.

#### `POST /api/v1/albums`
Create an album. Body: `{"name": "..."}` (required) plus optional
`description`, `status`, `cover_art_gcs_path`, `owner_id`. Returns
`201 {"success": true, "album": { ... }}`.

#### `GET /api/v1/albums?q=<query>&limit=20&offset=0&status=released`
Search albums by name. `q` is required; `status` is an optional filter.
Returns `results` / `total` / `has_more` — the same pagination caveat as
party search applies (`total` reflects the returned page).

#### `GET /api/v1/albums/{albumId}`
Album detail — the full Album entity above, including ordered tracks.

#### `PUT /api/v1/albums/{albumId}`
Update album metadata (partial — send only the fields to change: `name`,
`description`, `status`, `cover_art_gcs_path`). Returns the updated Album.

#### `DELETE /api/v1/albums/{albumId}`
Deletes the album (not its tracks). `204` on success.

#### `POST /api/v1/albums/{albumId}/tracks`
Add a track to an album. Body: `{"audio_track_id": "..."}` (required) plus
optional `position` (appends when omitted) and `disc_number` (default 1).
Returns `201 {"success": true, "track": { ... }}`.

#### `DELETE /api/v1/albums/{albumId}/tracks/{audioId}`
Remove a track from an album. `204` on success.

#### `PUT /api/v1/albums/{albumId}/tracks/order`
**Batch replace** of the track order. Body:
`{"track_order": ["<audioId>", ...]}` — the complete ordered list of track
UUIDs. Returns `{"success": true, ...}` with the reorder result.

#### `POST /api/v1/playlists`
Create a playlist. Body: `{"name": "..."}` (required) plus optional
`description`, `is_public` (default `false`), `owner_id`. Returns
`201 {"success": true, "playlist": { ... }}`.

#### `GET /api/v1/playlists?q=<query>&limit=20&offset=0`
Search playlists by name. `q` is required. Same pagination caveat as album
search.

#### `GET /api/v1/playlists/{playlistId}`
Playlist detail — the full Playlist entity above, including tracks and
collaborators.

#### `PUT /api/v1/playlists/{playlistId}`
Update playlist metadata (partial: `name`, `description`, `is_public`).
Returns the updated Playlist.

#### `DELETE /api/v1/playlists/{playlistId}`
Deletes the playlist (not its tracks). `204` on success.

#### `POST /api/v1/playlists/{playlistId}/tracks`
Add a track to a playlist. Body: `{"audio_track_id": "..."}` (required) plus
optional `position` and `added_by` (user UUID). Returns
`201 {"success": true, "track": { ... }}`.

#### `DELETE /api/v1/playlists/{playlistId}/tracks/{audioId}`
Remove a track from a playlist. `204` on success.

#### `PUT /api/v1/playlists/{playlistId}/tracks/order`
Same contract as the album variant: `{"track_order": [...]}`, batch replace.

#### `POST /api/v1/playlists/{playlistId}/collaborators`
Add a collaborator. Body: `{"user_id": "..."}` (required) plus optional
`role` (`"viewer"` | `"editor"` | `"admin"`, default `"viewer"`). Returns
`201 {"success": true, "collaborator": { ... }}`.

#### `DELETE /api/v1/playlists/{playlistId}/collaborators/{userId}`
Remove a collaborator. `204` on success.

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
- Upload / ingestion — three-step signed-URL flow with job polling (see the
  Uploads section above); design for a pending state
- Publishing data: parties and works (search, detail, writer/publisher
  splits, artist↔recording links) — see the Publishing endpoints above
- Albums & playlists — full CRUD, track add/remove/reorder, and playlist
  collaborators under `/api/v1` with the standard error envelope (LOI-47) —
  see the Albums & playlists endpoints above

**Coming to the REST API** (status per `docs/rest-api-expansion-plan.md`;
flag wireframes that depend on these so backend work can be sequenced):

- Metadata editing — `PATCH /api/v1/tracks/{audioId}` planned (LOI-46).
- Player/waveform data as JSON — decided with the embed rework
  (`docs/embed-architecture-notes.md`, LOI-48), not standalone.

Not built anywhere: user accounts, favorites, multi-tenancy (LOI-5, no
discovery done yet).

## 9. Changelog

- **July 2026 (LOI-47):** Albums & playlists (18 endpoints: CRUD, track
  add/remove/reorder, playlist collaborators) moved from unversioned
  `/api/albums*` / `/api/playlists*` to `/api/v1/*` and converted to the
  standard error envelope (old paths now 404). Album/Playlist entities and
  endpoints documented in this guide.
- **July 2026 (LOI-45):** Browser upload & ingestion flow added:
  `POST /api/v1/uploads` (signed PUT URL) → direct-to-GCS upload →
  `POST /api/v1/uploads/{id}/process` → `GET /api/v1/jobs/{id}` polling.
- **July 2026 (LOI-44):** Publishing endpoints (parties, works,
  writer/publisher splits, artist links) moved from `/api/*` to `/api/v1/*`
  and converted to the standard error envelope. `PUT` added to CORS allowed
  methods. Parties/works documented in this guide.
- **July 2026 (LOI-38):** All endpoints moved from `/api/*` to `/api/v1/*`
  (clean cutover — old paths now 404). Error envelope standardized. CORS fixed
  and verified for browser use. Bearer-token auth scaffolded (off by default).
