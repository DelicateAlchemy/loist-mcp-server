# Embed Architecture Notes — read before writing the frontend spec

**Date:** July 6, 2026 · **Author:** LOI-38 follow-up session
**Purpose:** capture what the embed subsystem actually is, where the debt
lives, and the direction to take when the frontend spec lands — so we don't
rediscover this the hard way mid-build.

## Why this doc exists

The embed player is the closest thing this project has to a frontend today,
and a lot of infrastructure has accreted around it. When the real frontend
arrives, most of this will be rebuilt — the players will need first-class
JSON API endpoints rather than server-rendered HTML — and we should make
those decisions deliberately instead of extending the current system by
reflex. **Default stance until the frontend spec exists: freeze embed
investment; don't add templates, variants, or new embed features.**

## Inventory (what exists, July 2026)

### HTTP surface (all in `src/server.py`, outside `/api/v1` and outside auth)

| Route | Size | Notes |
|---|---|---|
| `GET /embed/{audio_id}` | ~295 lines | server-rendered player page (OG/Twitter tags, oEmbed discovery, keyboard shortcuts) |
| `GET /embed/{audio_id}/waveform` | ~108 lines | waveform player variant |
| `GET /embed/{audio_id}/waveform/mobile` | ~157 lines | device-specific variant |
| `GET /embed/{audio_id}/waveform/desktop` | ~157 lines | near-duplicate of mobile |
| `GET /oembed` | ~209 lines | oEmbed provider (rich-embed unfurls) |
| `GET /.well-known/oembed.json` | ~34 lines | discovery |

≈960 lines of inline route handlers in `server.py` — more code than the
entire REST API.

### Templates (`templates/`, ≈2,200 lines of HTML+inline JS)

`embed.html` (942), `embed-waveform.html` (804),
`embed-waveform-minimal.html` (431). Each carries its own inline JS player —
three player implementations to keep in sync.

### Supporting machinery

- **Waveform pipeline:** `src/waveform/generator.py`, async generation via
  Cloud Tasks (`src/tasks/handler.py`, ~630 lines, `POST /tasks/waveform`),
  thread-safe metrics (`get_waveform_metrics_tool` — *operational* metrics,
  not player data).
- **MCP tools:** `get_embed_url`, `list_embed_templates` returning
  `PlayerConfig` (a decent JSON shape: urls/metadata/mode/device — see
  `docs/frontend-api-integration.md`).
- **Docs:** at least six (`embed-player-guide`, `embed-implementation-status`,
  `enhanced-social-sharing`, `iframe-embedding-troubleshooting`,
  `security-embed-analysis`, `TESTING_OEMBED.md`) plus
  `template-system-analysis.md` and ~15 `test_embed_*` / `test_iframe*`
  scratch files in the repo root.

## Known debt & confusion points

1. **Embed routes bypass the service layer.** The handlers import `database`
   functions directly (e.g. `get_audio_metadata_by_id`) — the REST/MCP
   "shared services" rule doesn't hold here. Any service-layer change can
   silently break embeds.
2. **Device forking by URL.** `/waveform/mobile` vs `/waveform/desktop` are
   ~157-line near-duplicates; device detection belongs in CSS/JS, not routes.
3. **Three inline JS players** across the templates — no shared player code,
   no build step, no tests for player behavior.
4. **Signed-URL expiry is baked into rendered HTML.** Pages render with
   ~15-minute GCS URLs; an embed left open longer dies quietly. A JSON
   endpoint with client-side refresh is the structural fix.
5. **`server.py` is 2,300 lines** largely because of this — embeds are the
   main obstacle to ever splitting it.
6. **Naming confusion:** "waveform" means three unrelated things (player
   variant, SVG/peaks artifact, metrics tool). Say which one, always.
7. **Root-directory scratch:** the `test_embed_*`/`test_iframe*` files predate
   the tests/ layout and aren't collected by pytest.

## Direction for the frontend era (positions, pending the spec)

1. **The player becomes a frontend component; the backend serves data.**
   Add `GET /api/v1/tracks/{id}/player` returning a `PlayerConfig`-shaped
   JSON document (metadata + fresh signed URLs + waveform peaks). The MCP
   `get_embed_url` tool already proves the shape. Client refreshes URLs on
   expiry — fixes debt item 4.
2. **Embeds stay, but as thin shells.** `/embed/{id}` remains a public,
   unauthenticated, iframe-able page (oEmbed and social unfurls depend on
   it) — but it should become one minimal template that loads the same
   frontend player bundle and calls the player endpoint. One player
   implementation everywhere.
3. **oEmbed + OG tags survive as-is conceptually** — they're
   standards-driven and work; only their rendering path changes.
4. **Waveform peaks as data, not markup:** expose peaks JSON via the player
   endpoint (or `/api/v1/tracks/{id}/waveform`); the SVG-in-template approach
   ends with the rebuild.
5. **Auth boundary stays as drawn in LOI-38:** embed/oEmbed public, player
   *data* endpoint under `/api/v1` — decide at spec time whether it's
   token-protected (embeds may need a public-scope token or a signed variant).

## What NOT to do meanwhile

- Don't add embed templates or new device variants.
- Don't extend the inline JS players except for security fixes.
- Don't build a standalone "waveform JSON" endpoint ahead of the player
  endpoint design — it's the same decision and should be made once.
