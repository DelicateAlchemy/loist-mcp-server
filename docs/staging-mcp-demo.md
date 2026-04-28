# Staging MCP Capabilities Demo

End-to-end walkthrough proving the staging MCP server can:

1. **Ingest** an audio track from an external URL.
2. **Return** an `audio_id` plus a public embed URL.
3. **Query** the persisted metadata.
4. **Update** that metadata with copyright/registration data.
5. **Re-query** to confirm the update landed.

Every step is shown twice — once as a Claude Code MCP tool call (canonical),
and once as a raw `curl` against the same JSON-RPC endpoint, so you can
validate without an MCP client.

> **Precondition.** Staging readiness must be green:
> `curl -fsS https://staging.loist.io/health/ready` returns `200`.
> Today it returns `503` with `gcs.configured: false` — see
> `docs/staging-mcp-setup.md` § Known issues. Steps 1–2 below will fail until
> that clears; steps 3–5 still demonstrate the read/update path against any
> already-ingested track.

---

## Setup assumed

You have completed `docs/staging-mcp-setup.md` and `/mcp` shows
`loist-staging` as **connected** in Claude Code.

For raw `curl` flows, mint a session once and reuse `$SESSION_ID`:

```bash
SESSION_ID=$(curl -sD - https://staging.loist.io/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  -o /dev/null | awk -F': ' 'tolower($1)=="mcp-session-id"{print $2}' | tr -d '\r')

echo "session: $SESSION_ID"
```

The `AUDIO_URL` used below is a remote, externally fetchable file. The server
downloads it server-side; you do **not** upload bytes:

```bash
AUDIO_URL='https://codahosted.io/docs/RQFw0P6Rnl/blobs/bl-Qpy0vhBkgC/53f3e95b286a72d0aa7cbd21fb91824c63004d501b8545a7643ad1d719826a4426d99045f933e2a95f1c8e355a4f5201e94d8644cf2b07e057a681958abf956985151237dd69bdef0bbf801462397613eaab4b9f74c290f3edbb43cd2e8f271c9b7058a6'
```

> If the Coda blob URL has expired by the time you run this, mirror any
> public MP3/FLAC/WAV into `gs://loist-music-library-bucket-staging/demo/`
> and substitute its public URL.

---

## Step 1 — Ingest the audio (remote URL → audio_id)

The server fetches the URL, extracts ID3/XMP/BWF metadata, uploads to GCS,
and persists a row in PostgreSQL — all in a single tool call.

### From Claude Code

> Using the `loist-staging` MCP server, call `process_audio_complete` with:
> ```json
> {
>   "source": {
>     "type": "http_url",
>     "url": "<AUDIO_URL>"
>   }
> }
> ```
> Show the raw response and remember the `audio_id`.

### From curl

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$(jq -nc --arg url "$AUDIO_URL" '
    {jsonrpc:"2.0", id:10, method:"tools/call",
     params:{name:"process_audio_complete",
             arguments:{source:{type:"http_url", url:$url}}}}')"
```

### Expected response shape

```json
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "product": { "artist": "...", "title": "...", "album": "...", "genre": ["..."], "year": 2017 },
    "format":  { "duration": 215.4, "channels": 2, "sample_rate": 44100, "bitrate": 320000, "format": "MP3" },
    "url_embed_link": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio_url":     "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform_url":  null
  },
  "processing_time": 2.45
}
```

Capture the `audio_id` — every following step uses it.

```bash
AUDIO_ID="550e8400-e29b-41d4-a716-446655440000"   # paste the real one
```

---

## Step 2 — Get the embed URL (the "URL back" deliverable)

`url_embed_link` from Step 1 is already a usable embed URL. To get a richer
player config (artwork, waveform availability, device variant), call
`get_embed_url`:

### From Claude Code

> Call `get_embed_url` with `audio_id: "<AUDIO_ID>"`, `template: "standard"`.

### From curl

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$(jq -nc --arg id "$AUDIO_ID" '
    {jsonrpc:"2.0", id:11, method:"tools/call",
     params:{name:"get_embed_url",
             arguments:{audio_id:$id, template:"standard"}}}')"
```

Expected: a `PlayerConfig` payload with `urls.embed`, `urls.artwork`, and a
`metadata` block for the player chrome. Open `urls.embed` in a browser to
see the playable embed.

---

## Step 3 — Query the persisted metadata (baseline)

### From Claude Code

> Call `get_audio_metadata` with `audio_id: "<AUDIO_ID>"`. Note the
> `metadata.product.composer` and `metadata.product.publisher` fields — most
> likely empty for a fresh ingest from a Coda-hosted MP3 with no XMP tags.

### From curl

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$(jq -nc --arg id "$AUDIO_ID" '
    {jsonrpc:"2.0", id:12, method:"tools/call",
     params:{name:"get_audio_metadata", arguments:{audio_id:$id}}}')"
```

---

## Step 4 — Update the metadata with copyright data

### Source data

The following copyright record (MCPS / PRS / ICE registration for the
work **"Your Taxi"**) is the "copy data" we want to attach to the track:

| Field                | Value                                                        |
| -------------------- | ------------------------------------------------------------ |
| Tunecode             | `291171KS`                                                   |
| ISWC                 | `T-922.363.499-9`                                            |
| ICE work key         | `37750296`                                                   |
| MCPS Claims          | `100.00%`                                                    |
| Composers / Authors  | `Dion (PRS/MCPS)`, `Levy, Aaron (PRS/MCPS)`, `Raphael Lake (ASCAP)` |
| Publisher            | `Extreme Music Library Ltd (PRS/MCPS)`                       |

### What `update_metadata` actually accepts (MVP)

The current `update_metadata` MCP tool follows JSON Merge Patch semantics
and accepts the following editable fields on a track:

`artist`, `title`, `album`, `genre`, `year`, **`composer`**, **`publisher`**,
`record_label`, `isrc`, `original_filename`.

Notably, **Tunecode, ISWC, and ICE work key have no track-level columns
yet** — they are work-registration identifiers, not per-track tags. For this
demo we therefore map only the fields the schema supports: `composer` (the
three writers, semicolon-joined) and `publisher`.

> If the CTO wants Tunecode/ISWC/ICE to be first-class fields, that is a
> schema migration on `audio_tracks` plus a new section in
> `TrackMetadataUpdate` — explicitly out of scope for this demo.

### From Claude Code

> Call `update_metadata` with:
> ```json
> {
>   "audio_id": "<AUDIO_ID>",
>   "metadata": {
>     "title": "Your Taxi",
>     "composer": "Dion; Levy, Aaron; Raphael Lake",
>     "publisher": "Extreme Music Library Ltd"
>   }
> }
> ```

### From curl

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$(jq -nc --arg id "$AUDIO_ID" '
    {jsonrpc:"2.0", id:13, method:"tools/call",
     params:{name:"update_metadata",
             arguments:{
               audio_id:$id,
               metadata:{
                 title:"Your Taxi",
                 composer:"Dion; Levy, Aaron; Raphael Lake",
                 publisher:"Extreme Music Library Ltd"
               }
             }}}')"
```

### Expected response shape

```json
{
  "success": true,
  "audio_id": "<AUDIO_ID>",
  "updated_fields": ["title", "composer", "publisher"],
  "metadata": { "...full updated row..." }
}
```

`updated_fields` confirms the JSON Merge Patch semantics: only the fields
you provided are touched, everything else is left as-is.

---

## Step 5 — Re-query to verify the update

### From Claude Code

> Call `get_audio_metadata` with `audio_id: "<AUDIO_ID>"` again and diff the
> `composer` / `publisher` / `title` fields against Step 3.

### From curl

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$(jq -nc --arg id "$AUDIO_ID" '
    {jsonrpc:"2.0", id:14, method:"tools/call",
     params:{name:"get_audio_metadata", arguments:{audio_id:$id}}}')" \
  | jq '.result.content[0].text | fromjson | .metadata.product
        | {title, composer, publisher}'
```

Expected:

```json
{
  "title": "Your Taxi",
  "composer": "Dion; Levy, Aaron; Raphael Lake",
  "publisher": "Extreme Music Library Ltd"
}
```

You can also confirm via faceted search:

```bash
curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc":"2.0","id":15,"method":"tools/call",
    "params":{
      "name":"search_library",
      "arguments":{
        "query":"Your Taxi",
        "filters":{"publisher":"Extreme Music Library Ltd"},
        "limit":5
      }
    }
  }'
```

---

## What this proves

| Capability                           | Tool used                | Step |
| ------------------------------------ | ------------------------ | ---- |
| Server-side ingest from a remote URL | `process_audio_complete` | 1    |
| GCS persistence + DB row creation    | `process_audio_complete` | 1    |
| Public, shareable embed URL          | `get_embed_url`          | 2    |
| Read-after-write metadata fetch      | `get_audio_metadata`     | 3, 5 |
| Partial (Merge Patch) update         | `update_metadata`        | 4    |
| Faceted search by XMP fields         | `search_library`         | 5    |

If all five steps return `success: true` and Step 5 shows the new field
values, the staging MCP deployment is functionally correct end-to-end.
