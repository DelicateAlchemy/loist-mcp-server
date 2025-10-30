<!-- 27b9ff2f-762f-49d4-9324-d888bd6d70d0 9ba946d5-4e9e-46c6-9196-ffa975d35408 -->
# MCP Inspector Integration Plan (stdio, auth disabled)

### Scope

- Use MCP Inspector with stdio transport and auth disabled for local debugging.
- Validate tools, resources, and exception serialization. No server code changes.

### Prerequisites

- Node.js installed (for npx).
- Python env ready per README; ensure auth disabled:
```bash
export AUTH_ENABLED=false
export LOG_LEVEL=DEBUG
```


### Option A (recommended): FastMCP dev helper

```bash
# From /Users/Gareth/loist-mcp-server
fastmcp dev src/server.py
```

- Opens Inspector and attaches via stdio automatically.

### Option B: Standalone Inspector + run_server.py (ensures stdio)

1) Launch Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

2) In Inspector: New connection → Transport: stdio → Command:

```bash
python3 /Users/Gareth/loist-mcp-server/run_server.py
```

- Working directory: `/Users/Gareth/loist-mcp-server`
- Env: `AUTH_ENABLED=false`, `LOG_LEVEL=DEBUG` (no token needed)

### Validation Scenarios in Inspector

- Tools
  - health_check: Expect status + transport stdio, auth disabled.
  - get_audio_metadata (nonexistent id): Expect standardized error from `src/error_utils.py` with `RESOURCE_NOT_FOUND`.
  - search_library (simple query): Expect empty results or valid schema.
  - process_audio_complete (optional): Use a small public MP3; verify success or consistent `VALIDATION_ERROR` on bad URL.
- Resources
  - music-library://audio/{id}/metadata|stream|thumbnail: Verify response shape; for unknown id, confirm error serialization.
- Exception Serialization
  - Intentionally trigger `ResourceNotFoundError`/`ValidationError` and confirm FastMCP returns your standardized error fields (code/message/details).
- Logging
  - Terminal logs show DEBUG lines for each call (useful alongside Inspector request/response views).

### Documentation updates (no code changes)

- README: Add a short “Using MCP Inspector (stdio)” section with the Option A and Option B commands above.
- docs/local-testing-mcp.md: Add an “Inspector quickstart” section mirroring the steps and typical validations.

### To-dos

- [ ] Launch MCP Inspector and connect via stdio using run_server.py
- [ ] Validate health_check, search_library, get_audio_metadata in Inspector
- [ ] Fetch music-library resource URIs and verify response/error shapes
- [ ] Trigger not-found/validation errors and confirm standardized error format
- [ ] Add Inspector quickstart (stdio) section to README
- [ ] Add Inspector quickstart and validation checklist to docs/local-testing-mcp.md