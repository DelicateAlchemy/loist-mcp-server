# MCP Server Audit Implementation - Task Tracker

> **Agent Instructions**: This file is your project management brain. Read it at session start, update checkboxes as you complete tasks, and maintain the rolling summary. Execute tasks ONE AT A TIME in order.

---

## 🤖 Agent Rules (MUST FOLLOW)

### Session Start Protocol
1. Read this entire file to restore context
2. Check `## Rolling Summary` for completed work
3. Find the next unchecked task (`- [ ]`)
4. State your intent before starting work

### Task Execution Protocol
```
🎯 Intent: I'm going to [action] because [reason].
   Files affected: [list]
   Expected outcome: [outcome]
```

### After Each Task
1. Mark task complete: `- [ ]` → `- [x]`
2. Update `## Rolling Summary` with what changed
3. If task created follow-up work, add to `## Discovered Tasks`
4. Commit changes if applicable

### Critical Rules
- **ONE task at a time** - never batch multiple tasks
- **Verify before marking done** - test your changes
- **Update this file** - it's your persistent memory
- **Use checkpoints** - run with `gemini -c` for safety
- **Docker only** - never use local venv (outdated)
- **Cost awareness** - use local PostgreSQL, not Cloud SQL for dev

---

## 📋 Project Overview

**Project**: Loist MCP Server - Audit Implementation
**Source**: MCP Server Audit Report (December 3, 2025)
**Goal**: Implement audit recommendations to achieve production-ready MCP server

### Architecture Summary
```
MCP Protocol Layer (server.py)
    ↓
Service Layer (src/services/) ✅ Complete
    ↓
Repository Layer (database operations)
    ↓
Infrastructure (PostgreSQL, GCS)
```

### Current State
- **MCP Tools**: 12 available (consolidating to 4 core for MVP)
- **Transport**: HTTP via `/mcp` endpoint (JSON-RPC)
- **MCP Resources**: Zero (by design - tool-centric architecture)
- **MCP Prompts**: Zero (to be added)

### Target 4-Tool Architecture
| Tool | Purpose | Current Implementation |
|------|---------|----------------------|
| **Tool 1**: Ingest | Content ingestion | `process_audio_complete` |
| **Tool 2**: Search | Library search | `search_library` |
| **Tool 3**: Edit | Metadata editing | `update_metadata` |
| **Tool 4**: Delete | Track deletion | `delete_audio` |

---

## 🚀 Phase 1: MCP Inspector Integration [HIGH PRIORITY]

### P1.1 Setup MCP Inspector with Streamable HTTP
- [x] **P1.1.1** Verify server is running: `curl http://localhost:8080/health/ready`
- [x] **P1.1.2** Create MCP Inspector configuration file at `~/.mcp-inspector/config.json`:
  ```json
  {
    "mcpServers": {
      "loist-music-library": {
        "type": "streamable-http",
        "url": "http://localhost:8080/mcp"
      }
    }
  }
  ```
- [x] **P1.1.3** ~~Test Inspector connection to `/mcp` endpoint~~ (Skipped - Manual step)
- [x] **P1.1.4** ~~Validate MCP handshake (`initialize`, `initialized`) via Inspector~~ (Skipped - Manual step)
- [x] **P1.1.5** ~~Test `tools/list` interactively - verify 12 tools appear~~ (Skipped - Manual step)
- [x] **P1.1.6** Document Inspector setup in `docs/mcp-inspector-setup.md`

### P1.2 Environment Configuration
- [x] **P1.2.1** Audit CORS configuration for `/mcp` endpoint (if Inspector in browser)
- [x] **P1.2.2** Verify auth header passthrough configuration
- [x] **P1.2.3** ~~Test Inspector from both local and proxy contexts~~ (Skipped - Manual step)
- [x] **P1.2.4** Document any environment-specific configuration in setup doc

### P1.3 Optional: stdio Entrypoint (Not needed at this time)
- [x] **P1.3.1** ~~Determine if other clients require stdio transport~~ (Skipped - Not required for Inspector)
- [x] **P1.3.2** ~~If yes: Create `server_stdio.py` with `transport="stdio"`~~ (Skipped)
- [x] **P1.3.3** ~~If yes: Wire to same server definition as HTTP entrypoint~~ (Skipped)
- [x] **P1.3.4** ~~If yes: Test stdio mode with a compatible client~~ (Skipped)
- [x] **P1.3.5** ~~Document stdio usage in `docs/mcp-transports.md`~~ (Skipped)

---

## 🧪 Phase 2: Protocol Testing & Validation [MEDIUM PRIORITY]

### P2.1 MCP Protocol Tests
- [x] **P2.1.1** Install FastMCP client for testing: `pip install mcp --break-system-packages`
- [x] **P2.1.2** Create test file `tests/test_mcp_protocol.py`
- [x] **P2.1.3** Implement test: MCP handshake (`initialize` → `initialized`)
- [ ] **P2.1.4** Implement test: `tools/list` returns expected 12 tools
- [ ] **P2.1.5** Implement test: `tools/call` for `health_check` (happy path)
- [ ] **P2.1.6** Implement test: `tools/call` error handling (invalid tool)
- [ ] **P2.1.7** Implement test: `tools/call` for `process_audio_complete`
  - **Note:** Requires valid HTTP URL to audio file. Set `audio_source_url` environment variable with fresh test URL (expires after 1 hour)
- [ ] **P2.1.8** Implement test: `tools/call` for `search_library`
- [ ] **P2.1.9** Implement test: `tools/call` for `update_metadata`
- [ ] **P2.1.10** Implement test: `tools/call` for `delete_audio`
- [ ] **P2.1.11** Implement test: `prompts/list` returns empty (currently)
- [ ] **P2.1.12** Implement test: `resources/list` returns empty (by design)
- [ ] **P2.1.13** Run full test suite and verify all pass

### P2.2 Fix Existing Test Mismatches
- [ ] **P2.2.1** Audit `test_mcp_tools_validation.py` for REST assumptions
- [ ] **P2.2.2** Update tests expecting `GET /mcp/tools/{name}` to use JSON-RPC
- [ ] **P2.2.3** Update documentation referencing REST-style endpoints
- [ ] **P2.2.4** Add comment clarifying REST wrappers are optional convenience API

### P2.3 Tool Schema Validation
- [ ] **P2.3.1** Extract tool schemas from `tools/list` response
- [ ] **P2.3.2** Validate each tool has proper `name`, `description`, `inputSchema`
- [ ] **P2.3.3** Verify `inputSchema` matches actual tool parameter requirements
- [ ] **P2.3.4** Document tool schemas in `docs/mcp-tool-schemas.md`

---

## ✨ Phase 3: Workflow Enhancements [MEDIUM PRIORITY]

### P3.1 Add MCP Prompts
- [ ] **P3.1.1** Design Prompt 1: "Ingest and track from URL"
  - Purpose: Guide through URL ingestion workflow
  - Orchestrates: `process_audio_complete`
- [ ] **P3.1.2** Design Prompt 2: "Search and refine results"
  - Purpose: Interactive search with filter refinement
  - Orchestrates: `search_library`
- [ ] **P3.1.3** Design Prompt 3: "Batch edit metadata"
  - Purpose: Guide through multi-track metadata updates
  - Orchestrates: `search_library` + `update_metadata`
- [ ] **P3.1.4** Implement prompt handlers in `server.py`
- [ ] **P3.1.5** Test `prompts/list` returns 3 prompts via Inspector
- [ ] **P3.1.6** Test prompt execution via Inspector
- [ ] **P3.1.7** Document prompts in `docs/mcp-prompts.md`

### P3.2 Tool Consolidation (Optional)
- [ ] **P3.2.1** Review current 12 tools vs desired 4-tool MVP architecture
- [ ] **P3.2.2** Identify tools to keep, deprecate, or merge
- [ ] **P3.2.3** Create deprecation plan for non-core tools
- [ ] **P3.2.4** Update tool documentation to reflect MVP focus
- [ ] **P3.2.5** Consider keeping utility tools but documenting as "internal"

### P3.3 Optional: REST Convenience API
- [ ] **P3.3.1** Determine if REST wrappers are needed for project tests/docs
- [ ] **P3.3.2** If yes: Implement `GET /mcp/tools` as thin pass-through
- [ ] **P3.3.3** If yes: Implement `POST /mcp/tools/{name}` as pass-through
- [ ] **P3.3.4** If yes: Document as "HTTP convenience API" in docs
- [ ] **P3.3.5** Update tests to test both JSON-RPC and REST access

---

## 📚 Phase 4: Documentation & Polish [LOWER PRIORITY]

### P4.1 Documentation Updates
- [ ] **P4.1.1** Update `README.md` to emphasize MCP JSON-RPC as canonical
- [ ] **P4.1.2** Add MCP protocol usage examples to README
- [ ] **P4.1.3** Create `docs/mcp-architecture.md` explaining design decisions
- [ ] **P4.1.4** Document zero-resource design choice and rationale
- [ ] **P4.1.5** Update API docs to clarify REST vs MCP access

### P4.2 Service Layer Extensions (Future)
- [ ] **P4.2.1** Design batch operations API for multiple tracks
- [ ] **P4.2.2** Implement batch metadata update service
- [ ] **P4.2.3** Design advanced search with aggregations
- [ ] **P4.2.4** Implement playlist/collection management service
- [ ] **P4.2.5** Add caching optimizations

---

## 📝 Rolling Summary

> Update this section after completing each task. Keep it concise.

### Completed Work
<!-- Add entries as you complete tasks -->
| Date | Task ID | Summary | Files Changed |
|------|---------|---------|---------------|
| 2025-12-03 | P1.1.1 | Verified server is running via readiness probe | docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.1.2 | Created MCP Inspector config file | N/A (user home dir) |
| 2025-12-03 | P1.1.3-5 | Skipped manual MCP Inspector tests | docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.1.6 | Documented MCP Inspector setup | docs/mcp-inspector-setup.md, docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.2.1 | Audited and documented CORS configuration | docs/cors-audit-report.md, docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.2.2 | Audited and documented auth header passthrough | docs/auth-header-audit.md, docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.2.3 | Skipped manual MCP Inspector proxy test | docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.2.4 | Documented environment-specific config | docs/mcp-inspector-setup.md, docs/mcp-audit-tasks.md |
| 2025-12-03 | P1.3 | Skipped optional stdio entrypoint | docs/mcp-audit-tasks.md |
| 2025-12-03 | P2.1.1 | Installed FastMCP client for testing | docs/mcp-audit-tasks.md |
| 2025-12-03 | P2.1.2 | Created MCP protocol test file | tests/test_mcp_protocol.py, docs/mcp-audit-tasks.md |
| 2025-12-03 | P2.1.3 | Implemented MCP handshake test | tests/test_mcp_protocol.py, docs/mcp-audit-tasks.md |

### Key Decisions Made
<!-- Document important architectural/technical decisions -->
- _None yet_

### Blockers & Issues
<!-- Track any blockers encountered -->
- _None yet_

---

## 🔍 Discovered Tasks

> Add new tasks discovered during implementation here. Review periodically and integrate into phases.

- [ ] _Example: Add rate limiting to tools_

---

## 📖 Research Notes

> Document answers to open questions from investigation.

### Q: Does MCP Inspector support Streamable HTTP?
**Status**: Confirmed ✅
**Answer**: Yes, Inspector supports Streamable HTTP transport directly. Configure with `{ type: "streamable-http", url: "http://localhost:8080/mcp" }`

### Q: Is zero MCP resources acceptable?
**Status**: Confirmed ✅
**Answer**: Yes, zero resources is valid MCP architecture. Resources are for large read-only artifacts. Tool-centric architecture fits this use case.

### Q: REST convenience API - required?
**Status**: Pending investigation
**Answer**: _To be determined based on project needs_

---

## 🛠️ Quick Reference Commands

### Local Development
```bash
# Start environment (uses local PostgreSQL - FREE)
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Health checks
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/database

# Test MCP tools/list
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run MCP protocol tests only
pytest tests/test_mcp_protocol.py -v

# With coverage
pytest --cov=src --cov-report=html
```

### Git Workflow
```bash
# Create task branch
git checkout dev
git pull origin dev
git checkout -b task-P1.1

# Commit format
git commit -m "feat(mcp): Setup Inspector configuration (Task P1.1.2)

- Created ~/.mcp-inspector/config.json
- Configured Streamable HTTP transport
- Files: docs/mcp-inspector-setup.md"
```

---

## 🎯 MCP Validation Checklist

Use this checklist to validate MCP compliance at each phase:

### Phase 1 Validation
- [ ] Inspector connects successfully
- [ ] `initialize` handshake completes
- [ ] `tools/list` returns 12 tools
- [ ] `resources/list` returns empty array
- [ ] `prompts/list` returns empty array

### Phase 2 Validation
- [ ] All protocol tests pass
- [ ] Tool schemas are valid JSON Schema
- [ ] Error responses follow MCP spec
- [ ] No tests assume REST-only access

### Phase 3 Validation
- [ ] `prompts/list` returns 3 prompts
- [ ] Prompts execute successfully
- [ ] Prompts orchestrate correct tools

---

## 📅 Session Log

> Record session starts/ends for continuity across multi-day work.

| Session | Date | Tasks Completed | Next Task |
|---------|------|-----------------|-----------|
| 1 | _YYYY-MM-DD_ | _P1.1.1, P1.1.2_ | _P1.1.3_ |

---

**Last Updated**: _Update this timestamp when modifying the file_
**Audit Source**: MCP Server Audit Report v1.0 (December 3, 2025)