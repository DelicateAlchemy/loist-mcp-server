# Handover: Loist Frontend — Context for Claude Design & Research

**Date:** July 6, 2026 · **Audience:** Claude Design (arriving with a PRD +
repo access) and Gareth's own research prompts (Perplexity, web search,
DeepWiki)
**Maintainer note:** §1 is deliberately self-contained and repo-path-free so
it can be pasted verbatim into any research tool.

---

## 1. Copy-paste research context (self-contained)

> **Project context for research purposes:**
>
> Loist is a music library platform, currently a headless backend with no
> frontend. The backend is Python (FastMCP/Starlette) on Google Cloud Run,
> with PostgreSQL for metadata and Google Cloud Storage for audio files. It
> exposes two interfaces over one service layer: a versioned JSON REST API
> (`/api/v1`) intended for the future web frontend, and an MCP (Model Context
> Protocol) interface used by AI agents. We are about to design and build the
> first web frontend, starting from wireframes.
>
> **Product domain:** a music library for working with audio recordings and
> music-publishing metadata. Core objects: tracks (audio + artist/title/album/
> genre/year + technical format data), full-text search with facets (composers,
> publishers, record labels), albums and playlists, and a publishing layer —
> "parties" (people/organisations) and "works" (compositions) with writer and
> publisher shares, artist↔recording links, and eventually per-rights-holder
> clearance workflows. Think "internal music catalogue and rights tool with a
> streaming-quality player", not a consumer streaming service.
>
> **Frontend-relevant API facts:**
> - JSON REST, consistent error envelope (`{success, error: CODE, message}`),
>   offset pagination with `X-Total-Count` and RFC-5988 `Link` headers.
> - Audio and artwork are served via 302 redirects to **signed GCS URLs that
>   expire after ~15 minutes** — players must re-request rather than cache
>   URLs. Range requests (seeking) work on the signed URLs.
> - Downloads support server-side format conversion (mp3/wav/flac/aac/ogg)
>   that can take seconds — the UI needs a pending state.
> - File upload will NOT be a multipart POST (Cloud Run caps request bodies
>   at 32 MiB; files up to 100 MB). Planned flow: request a signed PUT URL,
>   browser uploads directly to GCS, then trigger async processing and poll
>   a job endpoint. Upload UX must handle progress + a processing phase.
> - Auth (near-term): a single static bearer token in the `Authorization`
>   header, no user accounts yet. A browser-delivered SPA cannot safely hold
>   the token, so architectures that proxy API calls through a backend (BFF /
>   server components / route handlers) are of particular interest.
>   Multi-user auth and multi-tenancy are explicitly future work.
> - There is an existing embeddable player (iframe pages + oEmbed provider +
>   Open Graph tags, waveform rendering). It will be rebuilt: the plan is a
>   JSON "player config" endpoint (metadata + fresh signed URLs + waveform
>   peaks) consumed by one shared player component that serves both the main
>   app and thin public embed pages.
>
> **Research interests:** frontend framework choice for this shape of app;
> audio player and waveform libraries; large-file direct-to-GCS upload UX;
> data-fetching/caching patterns for expiring signed URLs; BFF/token-handling
> patterns; embed/iframe player architecture; design systems suited to dense
> library/catalogue UIs with audio playback.

## 2. DeepWiki / package-research shortlist

Repos worth querying directly (DeepWiki indexes GitHub repos):

| Repo | Why |
|---|---|
| `katspaugh/wavesurfer.js` | de-facto waveform player; supports pre-computed peaks (matches our peaks-as-JSON plan) |
| `goldfire/howler.js` | audio playback engine, if player UI is custom |
| `video.js` / `sampotts/plyr` | mature player chrome, keyboard a11y patterns |
| `transloadit/uppy` | direct-to-cloud uploads, progress, resumability (GCS via signed URLs / tus) |
| `TanStack/query` | cache invalidation patterns fit expiring signed URLs (staleTime ≈ URL TTL) |
| `vercel/next.js` | BFF-ish route handlers solve the token problem; likely default candidate |
| `jlowin/fastmcp` | our backend framework — useful when questions touch the server |
| `shadcn-ui/ui` + `radix-ui/primitives` | dense catalogue UI building blocks, a11y |

Questions worth asking against them: "how do I render a waveform from
pre-computed peaks JSON?", "resumable upload to GCS signed URL", "refetch on
401/expired media URL", "audio element + 302 redirect + Range request
behaviour".

## 3. For Claude Design specifically

### Screens the API already implies (safe to design against)

Library/search (facets, pagination), track detail (metadata, artwork,
duration), persistent player (play/seek from stream endpoint), download with
format picker + pending state, delete with confirm (irreversible). Coming
shortly behind the wireframes: upload (3-phase: choose → uploading with
progress → processing/pending), albums & playlists (CRUD, membership,
ordering), parties/works browsing and share editing.

### States that must be designed, not improvised

Every endpoint returns a typed error envelope — design error, empty, loading,
and *processing* states from day one. Conversion downloads and upload
processing are seconds-to-minutes: pending affordances are first-class.
**No login screen** — auth is a headerless concern until multi-tenancy work
(LOI-5) happens.

### Authoritative repo references (read in this order)

1. `docs/frontend-api-guide.md` — THE API contract for frontend work:
   entities with exact JSON, endpoints, error catalog, conventions, and the
   available-now vs coming vs nonexistent checklist.
2. `docs/rest-api-expansion-plan.md` — what's landing next and in what order
   (upload flow, metadata PATCH, albums/playlists, publishing under v1).
3. `docs/embed-architecture-notes.md` — the embed/player rebuild direction;
   the player is to become a frontend component fed by a JSON endpoint.
4. `docs/rest-api-auth-plan.md` — token model and why a SPA holding the
   static token is a launch blocker (BFF discussion lives here).
5. `docs/cors-audit-report.md` §6 — CORS is now real and browser-compatible.

**Trust warning on other docs:** this repo has many historical/investigation
docs (`loi-NN-*.md`, `*-investigation.md`, `api-endpoint-refactoring.md`
etc.). They are records, not contracts — where they conflict with the five
above, the five above win. Endpoint paths without `/api/v1` are stale.

### Repo state caveats (July 2026)

- Linear (team "Loist") is the issue tracker; LOI-38/42–48 cover the API
  hardening and expansion this handover sits on.
- `main` and `dev` had diverged (albums/playlists on `main`, song publishing
  on `dev`) — reconciliation is tracked in LOI-43/44. If a capability seems
  missing, check both branches before concluding it doesn't exist.
- Embed subsystem is **frozen** pending the player-API design (LOI-48) —
  don't design new embed variants against the current template system.

### Open product questions design will collide with (flag, don't solve)

- Clearance/licensing workflow modelling (LOI-39 discovery) — publishing
  screens beyond browse/edit-shares are undiscovered territory.
- Multi-tenancy / accounts (LOI-5) — single-tenant assumption is temporary;
  avoid baking "there is exactly one library" into information architecture.
- Public-embed auth posture — how a public embed gets player data once the
  API requires tokens (options sketched in the embed notes).
