# Staging MCP Server Setup

How to connect to the Loist Music Library MCP server running on staging from
**Claude Code**.

- **MCP endpoint:** `https://staging.loist.io/mcp`
- **Transport:** Remote HTTP (streamable HTTP MCP, SSE-style responses with
  per-session `mcp-session-id`)
- **Auth:** None — staging is currently open
- **Companion demo doc:** `docs/staging-mcp-demo.md`

> **Precondition — staging readiness.** As of this writing, `GET
> https://staging.loist.io/health/ready` returns **HTTP 503** with
> `dependencies.gcs.configured: false`. Tool calls that touch GCS
> (`process_audio_complete`, embed/thumbnail URLs) will fail until that
> clears. See [Known issues](#known-issues) below before running the demo.

---

## 1. Verify staging is reachable

```bash
# Should return 200 once GCS readiness is fixed; today returns 503.
curl -i https://staging.loist.io/health/ready
```

Expected (healthy) body:

```json
{
  "status": "ready",
  "service": "music-library-mcp",
  "check": "readiness",
  "dependencies": {
    "database": { "configured": true, "available": true, "connection_type": "..." },
    "gcs":      { "configured": true }
  }
}
```

If `gcs.configured` is `false`, see [Known issues](#known-issues).

A quick MCP-level handshake (no client required) — confirms the server speaks
streamable HTTP and issues a session ID:

```bash
curl -i https://staging.loist.io/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": { "name": "curl-probe", "version": "0.0.1" }
    }
  }'
```

You should see response headers including:

```
content-type: text/event-stream
mcp-session-id: <uuid>
```

The `mcp-session-id` returned here must be sent back as a header on every
subsequent request in the same session. Claude Code handles this for you.

---

## 2. Add the server to Claude Code

Use the `claude mcp add` command with HTTP transport:

```bash
claude mcp add --transport http loist-staging https://staging.loist.io/mcp
```

This registers the server in your **user-scoped** Claude Code config. To make
it available to anyone working in this repository instead, add it to project
scope (commits a `.mcp.json` to the repo):

```bash
claude mcp add --transport http --scope project loist-staging https://staging.loist.io/mcp
```

The resulting `.mcp.json` looks like:

```json
{
  "mcpServers": {
    "loist-staging": {
      "type": "http",
      "url": "https://staging.loist.io/mcp"
    }
  }
}
```

> Do **not** use `--transport stdio`. The staging deployment is remote HTTP,
> not a local subprocess.

---

## 3. Verify the server is connected

In Claude Code:

```
/mcp
```

You should see `loist-staging` listed as **connected**, with the tools below
discovered. Claude Code will issue `tools/list` against the session
automatically.

Expected tools (subset relevant to the demo):

| Tool                     | Purpose                                                |
| ------------------------ | ------------------------------------------------------ |
| `process_audio_complete` | Fetch an audio URL, extract metadata, persist to GCS+DB |
| `get_audio_metadata`     | Read a single track by `audio_id`                      |
| `search_library`         | Full-text + faceted search                             |
| `update_metadata`        | JSON Merge Patch update of editable track fields       |
| `delete_audio`           | Remove a track + its files                             |
| `get_embed_url`          | Generate an embed URL for a track                      |

---

## 4. Smoke test from Claude Code

Once `/mcp` shows `connected`, ask Claude Code something like:

> Using the `loist-staging` MCP server, call `search_library` with query
> `"taxi"` and `limit: 5`. Show me the raw JSON response.

A clean response confirms the session, transport, and tool dispatch are all
working.

If you would rather drive the same call from the shell:

```bash
SESSION_ID=$(curl -sD - https://staging.loist.io/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  -o /dev/null | awk -F': ' 'tolower($1)=="mcp-session-id"{print $2}' | tr -d '\r')

curl -s https://staging.loist.io/mcp \
  -H "mcp-session-id: $SESSION_ID" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

---

## Known issues

### `gcs.configured: false` on `/health/ready`

Staging IAM impersonation and bucket writes have been verified manually
(`gcloud storage cp --impersonate-service-account=...` succeeds end-to-end).
The 503 is now a **runtime config** issue, not an IAM issue.

The `is_gcs_configured` check in `src/config.py` requires *all three* of:

1. `GCS_BUCKET_NAME`
2. `GCS_PROJECT_ID`
3. **EITHER** `gcs_credentials_path` set in config **OR** the
   `GOOGLE_APPLICATION_CREDENTIALS` env var pointing at a key file

On Cloud Run with an attached service account, credentials come from the
metadata server — `GOOGLE_APPLICATION_CREDENTIALS` is **not** set. So the
property short-circuits to `False`, the readiness probe returns 503, and the
demo cannot ingest audio until this is unblocked.

This is being tracked separately. Until then:

- The setup steps above (handshake, `/mcp add`, `tools/list`) work.
- Read-only tool calls against existing data (`search_library`,
  `get_audio_metadata` for already-ingested tracks) work.
- Write paths that touch GCS (`process_audio_complete`, embed URL generation
  for new tracks) will fail.

### Session expiry

`mcp-session-id` is short-lived. If a tool call returns a 4xx with a
session-related message, Claude Code will re-`initialize` automatically; for
manual `curl` sessions, just repeat the handshake to mint a new ID.

---

## Removing the server

```bash
claude mcp remove loist-staging
```

Or, for project scope, delete the entry from `.mcp.json`.
