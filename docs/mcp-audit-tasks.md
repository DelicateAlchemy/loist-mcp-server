# MCP Server Audit Implementation - Task Tracker

> **Agent Instructions**: This file is your project management brain. Read it at session start, update checkboxes as you complete tasks, and maintain the rolling summary. Execute tasks ONE AT A TIME in order.

---

## 🤖 Agent Rules (MUST FOLLOW)

### Session Start Protocol
1. Read this entire file to restore context
2. Check `## Rolling Summary` for completed work
3. Find the next unchecked task (`- [STATUS: pending]`)
4. State your intent before starting work

### Task Execution Protocol
```
🎯 Intent: I\'m going to [action] because [reason].
   Files affected: [list]
   Expected outcome: [outcome]
```

### After Each Task
1. Mark task complete: `- [STATUS: pending]` → `- [STATUS: done]`
2. Update `## Rolling Summary` with what changed
3. If task created follow-up work, add to `## Discovered Tasks`
4. Commit changes if applicable

### Critical Rules
- **ONE task at a time** - never batch multiple tasks
- **Verify before marking done** - test your changes
- **Update this file** - it\'s your persistent memory
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
- [STATUS: done] **P1.1.1** Verify server is running: `curl http://localhost:8080/health/ready`
- [STATUS: done] **P1.1.2** Create MCP Inspector configuration file at `~/.mcp-inspector/config.json`:
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
- [STATUS: done] **P1.1.3** ~~Test Inspector connection to `/mcp` endpoint~~ (Skipped - Manual step)
- [STATUS: done] **P1.1.4** ~~Validate MCP handshake (`initialize`, `initialized`) via Inspector~~ (Skipped - Manual step)
- [STATUS: done] **P1.1.5** ~~Test `tools/list` interactively - verify 12 tools appear~~ (Skipped - Manual step)
- [STATUS: done] **P1.1.6** Document Inspector setup in `docs/mcp-inspector-setup.md`

### P1.2 Environment Configuration
- [STATUS: done] **P1.2.1** Audit CORS configuration for `/mcp` endpoint (if Inspector in browser)
- [STATUS: done] **P1.2.2** Verify auth header passthrough configuration
- [STATUS: done] **P1.2.3** ~~Test Inspector from both local and proxy contexts~~ (Skipped - Manual step)
- [STATUS: done] **P1.2.4** Document any environment-specific configuration in setup doc

### P1.3 Optional: stdio Entrypoint (Not needed at this time)
- [STATUS: done] **P1.3.1** ~~Determine if other clients require stdio transport~~ (Skipped - Not required for Inspector)
- [STATUS: done] **P1.3.2** ~~If yes: Create `server_stdio.py` with `transport="stdio"`~~ (Skipped)
- [STATUS: done] **P1.3.3** ~~If yes: Wire to same server definition as HTTP entrypoint~~ (Skipped)
- [STATUS: done] **P1.3.4** ~~If yes: Test stdio mode with a compatible client~~ (Skipped)
- [STATUS: done] **P1.3.5** ~~Document stdio usage in `docs/mcp-transports.md`~~ (Skipped)

---

## 🧪 Phase 2: Protocol Testing & Validation [MEDIUM PRIORITY]

### P2.1 MCP Protocol Tests
- [STATUS: done] **P2.1.1** Install FastMCP client for testing: `pip install mcp --break-system-packages`
- [STATUS: done] **P2.1.2** Create test file `tests/test_mcp_protocol.py`
- [STATUS: done] **P2.1.3** Implement test: MCP handshake (`initialize` → `initialized`)
- [STATUS: done] **P2.1.4** Implement test: `tools/list` returns expected 12 tools
- [STATUS: done] **P2.1.5** Implement test: `tools/call` for `health_check` (happy path)
- [STATUS: done] **P2.1.6** Implement test: `tools/call` error handling (invalid tool)
- [STATUS: done] **P2.1.7** Implement test: `tools/call` for `process_audio_complete`
  - **Note:** Requires valid HTTP URL to audio file. Set `audio_source_url` environment variable with fresh test URL (expires after 1 hour)
- [STATUS: done] **P2.1.8** Implement test: `tools/call` for `search_library`
- [STATUS: done] **P2.1.9** Implement test: `tools/call` for `update_metadata`
- [STATUS: done] **P2.1.10** Implement test: `tools/call` for `delete_audio`
- [STATUS: done] **P2.1.11** Implement test: `prompts/list` returns empty (currently)
- [STATUS: done] **P2.1.12** Implement test: `resources/list` returns empty (by design)
- [STATUS: done] **P2.1.13** Run full test suite and verify all pass

### P2.2 Fix Existing Test Mismatches
- [STATUS: done] **P2.2.1** Audit `test_mcp_tools_validation.py` for REST assumptions
- [STATUS: done] **P2.2.2** Update tests expecting `GET /mcp/tools/{name}` to use JSON-RPC
- [STATUS: done] **P2.2.3** Update documentation referencing REST-style endpoints
- [STATUS: done] **P2.2.4** Add comment clarifying REST wrappers are optional convenience API

### P2.3 Tool Schema Validation
- [STATUS: done] **P2.3.1** Extract tool schemas from `tools/list` response
- [STATUS: done] **P2.3.2** Validate each tool has proper `name`, `description`, `inputSchema`
- [STATUS: done] **P2.3.3** Verify `inputSchema` matches actual tool parameter requirements
- [STATUS: done] **P2.3.4** Document tool schemas in `docs/mcp-tool-schemas.md`

---

## ✨ Phase 3: Workflow Enhancements [MEDIUM PRIORITY]

### P3.1 Add MCP Prompts
- [STATUS: done] **P3.1.1** Design Prompt 1: "Ingest and track from URL"
  - Purpose: Guide through URL ingestion workflow
  - Orchestrates: `process_audio_complete`
- [STATUS: done] **P3.1.2** Design Prompt 2: "Search and refine results"
  - Purpose: Interactive search with filter refinement
  - Orchestrates: `search_library`
- [STATUS: done] **P3.1.3** Design Prompt 3: "Batch edit metadata"
  - Purpose: Guide through multi-track metadata updates
  - Orchestrates: `search_library` + `update_metadata`
- [STATUS: done] **P3.1.4** Implement prompt handlers in `server.py`
- [STATUS: done] **P3.1.5** Test `prompts/list` returns 3 prompts via Inspector
- [STATUS: done] **P3.1.6** Test prompt execution via Inspector
- [STATUS: done] **P3.1.7** Document prompts in `docs/mcp-prompts.md`

### P3.2 Tool Consolidation (Minimal Action)
- [STATUS: done] **P3.2.1** Review current 12 tools vs desired 4-tool MVP architecture (completed via research)
- [STATUS: done] **P3.2.2** Remove deprecated `check_waveform_availability` tool from server.py (completed LOI-21)
- [STATUS: pending] **P3.2.3** Move operational tools (`health_check`, `get_waveform_metrics_tool`, `get_circuit_breaker_status`) to HTTP-only endpoints
- [STATUS: pending] **P3.2.4** Document rationale: "Keep granular tools for token efficiency; operational tools via HTTP only"

### P3.3 REST Convenience API (Deferred - Not Needed for MVP)

**Status: Deferred** - Research indicates automation platforms (Zapier/Make/Pipedream) work fine with MCP's native JSON-RPC. REST wrappers add maintenance burden without clear MVP value.

- [STATUS: cancelled] **P3.3.1** Determine if REST wrappers are needed for project tests/docs
- [STATUS: cancelled] **P3.3.2** If yes: Implement `GET /mcp/tools` as thin pass-through
- [STATUS: cancelled] **P3.3.3** If yes: Implement `POST /mcp/tools/{name}` as pass-through
- [STATUS: cancelled] **P3.3.4** If yes: Document as "HTTP convenience API" in docs
- [STATUS: cancelled] **P3.3.5** Update tests to test both JSON-RPC and REST access

---

## 📚 Phase 4: Documentation & Polish [LOWER PRIORITY]

### P4.1 Documentation Updates
- [STATUS: pending] **P4.1.1** Update `README.md` to emphasize MCP JSON-RPC as canonical
  - Note: Operational tools (health_check, metrics, circuit_breaker) are HTTP-only, not MCP tools
  - Reference: Research findings on tool granularity and A2A compatibility
- [STATUS: pending] **P4.1.2** Add MCP protocol usage examples to README
  - Include examples of core business tools (process_audio_complete, search_library, etc.)
  - Exclude operational tools from MCP examples (they're HTTP endpoints)
- [STATUS: pending] **P4.1.3** Create `docs/mcp-architecture.md` explaining design decisions
  - Bridge pattern: MCP stdio transport vs A2A HTTP transport (separate apps required)
  - Tool selection: Core business tools in MCP, operational tools HTTP-only
  - A2A compatibility: Current design already A2A-ready (typed schemas, idempotent operations)
  - Reference: `docs/a2a-integration-analysis.md` for bridge pattern details
- [STATUS: pending] **P4.1.4** Document zero-resource design choice and rationale
  - Tool-centric architecture fits use case (computed/parameterized actions)
  - Resources are for large read-only artifacts, not our workflow
- [STATUS: pending] **P4.1.5** Update API docs to clarify REST vs MCP access
  - MCP JSON-RPC is canonical protocol (tools/list, tools/call)
  - REST wrappers are optional convenience APIs, not MCP requirements
  - Operational endpoints are HTTP-only (not MCP tools)

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
| 2025-12-03 | P2.1.4 | Implemented tools/list test | tests/test_mcp_protocol.py, docs/mcp-audit-tasks.md |

### Key Decisions Made
<!-- Document important architectural/technical decisions -->
- _None yet_

### Blockers & Issues
<!-- Track any blockers encountered -->
- _None yet_

---

## 🔍 Discovered Tasks

> Add new tasks discovered during implementation here. Review periodically and integrate into phases.

- [STATUS: pending] **A2A Documentation Refactoring**: Update A2A planning docs based on research findings:
  - A2A complements MCP (agent-to-agent vs agent-to-tool)
  - Current tool design is A2A-ready (typed schemas, idempotent reads, explicit side effects)
  - Document A2A-compatible tool patterns for future reference

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
**Status**: Resolved ✅ - Deferred for MVP
**Answer**: Research indicates automation platforms (Zapier/Make/Pipedream) work fine with MCP's native JSON-RPC. REST wrappers add maintenance burden without clear MVP value. Deferred until proven necessary.

### Q: Tool granularity and token efficiency for agent workflows?
**Status**: Resolved ✅ - Keep current design
**Answer**: Lightweight single-purpose tools like `get_audio_metadata` save tokens for simple agent automations vs heavier `search_library`. Keep granular tools (3-6 semantically strong) for automation platforms. Separate exact-ID lookups from semantic search. Move operational tools (health_check, metrics, circuit_breaker) to HTTP-only endpoints, not MCP tools.

### Q: A2A compatibility with current MCP tool design?
**Status**: Resolved ✅ - Current design is A2A-ready
**Answer**: A2A complements MCP (agent-to-agent vs agent-to-tool). Current typed schemas, idempotent reads, and explicit side effects make tools A2A-compatible. Focus on structured outputs that can pass between agents without natural language rewriting.

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
- [STATUS: pending] Inspector connects successfully
- [STATUS: pending] `initialize` handshake completes
- [STATUS: pending] `tools/list` returns 12 tools
- [STATUS: pending] `resources/list` returns empty array
- [STATUS: pending] `prompts/list` returns empty array

### Phase 2 Validation
- [STATUS: pending] All protocol tests pass
- [STATUS: pending] Tool schemas are valid JSON Schema
- [STATUS: pending] Error responses follow MCP spec
- [STATUS: pending] No tests assume REST-only access

### Phase 3 Validation
- [STATUS: pending] `prompts/list` returns 3 prompts
- [STATUS: pending] Prompts execute successfully
- [STATUS: pending] Prompts orchestrate correct tools

---

## 📅 Session Log

> Record session starts/ends for continuity across multi-day work.

| Session | Date | Tasks Completed | Next Task |
|---------|------|-----------------|-----------|
| 1 | _YYYY-MM-DD_ | _P1.1.1, P1.1.2_ | _P1.1.3_ |

---

**Last Updated**: _Update this timestamp when modifying the file_
**Audit Source**: MCP Server Audit Report v1.0 (December 3, 2025)
