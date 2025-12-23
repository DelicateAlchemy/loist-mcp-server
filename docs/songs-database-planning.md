# Song Publishing Schema Implementation Plan

> **Project Tracker**: This document tracks the R&D phase for implementing the song publishing schema from `database/migrations/010_song_publishing_schema.sql`.

**Status**: 🟢 Ready for Implementation  
**Last Updated**: 2024-12-22  
**Related Docs**: 
- [Schema Design Philosophy](./songs-schema-design-philosophy.md)
- [Migration SQL](../database/migrations/010_song_publishing_schema.sql)

---

## Table of Contents

- [Overview](#overview)
- [Scope Decisions](#scope-decisions)
- [MCP Tools (Final List)](#mcp-tools-final-list)
- [Implementation Areas](#implementation-areas)
- [Task Breakdown (Linear)](#task-breakdown-linear)
- [Questions & Answers](#questions--answers)
- [Technical Decisions](#technical-decisions)
- [Testing Strategy](#testing-strategy)
- [Progress Tracking](#progress-tracking)

---

## Overview

### What We're Building

A song publishing data model that separates:
- **Works** (compositions) from **Recordings** (audio_tracks)
- **Parties** (people/orgs) with roles as writers, publishers, or artists
- **Splits** (ownership percentages) with WIP-friendly flexibility

### Core Entities

```
┌─────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
│   parties   │       │        works        │       │    audio_tracks     │
│─────────────│       │─────────────────────│       │─────────────────────│
│ id          │       │ id                  │◄──────│ work_id (FK)        │
│ party_type  │       │ title               │       │ title               │
│ name        │       │ iswc                │       │ artist (string)     │
│ ipi_cae     │       │ status              │       │ isrc (string)       │
└─────────────┘       └─────────────────────┘       └─────────────────────┘
       │                         │                             │
       ├─────────────────────────┼─────────────────────────────┤
       ▼                         ▼                             ▼
┌─────────────────┐    ┌─────────────────┐   ┌───────────────────┐
│  work_writers   │    │ work_publishers │   │ recording_artists │
│─────────────────│    │─────────────────│   │───────────────────│
│ work_id (FK)    │    │ work_id (FK)    │   │ audio_track_id(FK)│
│ party_id (FK)   │    │ party_id (FK)   │   │ party_id (FK)     │
│ split_percentage│    │ split_percentage│   │ is_primary        │
│ split_status    │    │ split_status    │   └───────────────────┘
└─────────────────┘    └─────────────────┘
```

---

## Scope Decisions

### MVP Scope (Confirmed)

| Item | Status | Notes |
|------|--------|-------|
| CRUD for parties, works, junction tables | ✅ In | Core functionality |
| Simple search (ILIKE, not full-text) | ✅ In | Works first, parties second priority |
| Auto-creation of works when creating audio_tracks | ✅ In | Core to audio-first workflow |
| 8 MCP tools (reduced from 16) | ✅ In | See tool list below |
| Split warnings in `get_work` response | ✅ In | Cheap to calculate, always available |

### Deferred to v1.1

| Item | Rationale |
|------|-----------|
| Full-text/fuzzy search | Simple ILIKE sufficient for MVP |
| Party deduplication suggestions | Adds UI complexity, users can search first |
| Work merging | Complex feature |
| Bulk CSV import for parties | Scope creep |
| Dedicated split validation endpoint | Client can calculate from `get_work` |
| Status state machine enforcement | Status is informational, not a gate |
| `update_party` tool | Rare operation, can use raw DB |
| `update_work` tool | Work title/status changes infrequent |

---

## MCP Tools (Final List)

**8 tools** instead of 16 — consolidated using batch update patterns.

| Tool | Description | Priority |
|------|-------------|----------|
| `create_party` | Create a person or organization | Essential |
| `search_parties` | Search parties by name (ILIKE) with pagination | Essential |
| `get_party` | Get party details + list of works they're on | Essential |
| `get_work` | Get work with all writers/publishers/recordings + split warnings | Essential |
| `search_works` | Search works by title (ILIKE) with pagination | Essential |
| `update_work_writers` | Batch add/remove/update writers on a work | Essential |
| `update_work_publishers` | Batch add/remove/update publishers on a work | Essential |
| `link_artist_to_recording` | Add artist to a recording | Essential |

### Tool Signatures

#### `update_work_writers` (replaces add/remove/update_writer)

```python
update_work_writers(
    work_id: str,
    writers: List[{
        party_id: str,
        split_percentage: Optional[float],  # null = unknown
        split_status: str  # proposed/confirmed/disputed/unknown
    }]
)
# REPLACES all writers on the work
# To add: include existing + new
# To remove: exclude from list
# To update split: change the values
```

#### `update_work_publishers` (same pattern)

```python
update_work_publishers(
    work_id: str,
    publishers: List[{
        party_id: str,
        split_percentage: Optional[float],
        split_status: str
    }]
)
```

#### `get_work` response includes warnings

```python
{
    "id": "...",
    "title": "...",
    "status": "draft",
    "writers": [...],
    "publishers": [...],
    "recordings": [...],
    "warnings": [
        "Writer splits only add up to 80%",
        "One or more writer splits are disputed"
    ]
}
```

### Tools NOT in MVP

| Cut Tool | Why |
|----------|-----|
| `update_party` | Rare. Use raw DB if needed. |
| `update_work` | Rare. Title/status changes infrequent. |
| `remove_*` as separate tools | Folded into `update_work_*` |
| `get_split_validation` | Included in `get_work` response |
| `merge_works` | Defer to v1.1 |

---

## Implementation Areas

### 1. Database Layer

| Component | Status | Notes |
|-----------|--------|-------|
| Migration SQL | ✅ Done | `010_song_publishing_schema.sql` (reviewed 2024-12-22) |
| Party operations | 🔵 TODO | Create, get, search (ILIKE) |
| Work operations | 🔵 TODO | Create, get, search (ILIKE) |
| Junction table operations | 🔵 TODO | Batch replace for writers/publishers |
| Split warning calculation | 🔵 TODO | SUM query in get_work |

### 2. Repository Layer (Simplified)

| Component | Status | Notes |
|-----------|--------|-------|
| `PartyRepository` | 🔵 TODO | Minimal: create, get, search |
| `WorkRepository` | 🔵 TODO | With junction table batch ops |
| (No separate SplitRepository) | ✅ Decided | Junction ops are part of WorkRepository |

### 3. Service Layer

| Component | Status | Notes |
|-----------|--------|-------|
| `party_service.py` | 🔵 TODO | Create, get, search |
| `work_service.py` | 🔵 TODO | CRUD + batch writer/publisher updates |
| Modify `audio_service.py` | 🔵 TODO | Auto-create work on track creation |
| (No separate split_service) | ✅ Decided | Split logic is in work_service |

### 4. MCP Tools

| Tool | Status | Notes |
|------|--------|-------|
| `create_party` | 🔵 TODO | |
| `search_parties` | 🔵 TODO | ILIKE search |
| `get_party` | 🔵 TODO | With works list |
| `get_work` | 🔵 TODO | With writers/publishers/recordings + warnings |
| `search_works` | 🔵 TODO | ILIKE search |
| `update_work_writers` | 🔵 TODO | Batch replace pattern |
| `update_work_publishers` | 🔵 TODO | Batch replace pattern |
| `link_artist_to_recording` | 🔵 TODO | |

### 5. A2A Integration

| Component | Status | Notes |
|-----------|--------|-------|
| Auto-work creation in audio pipeline | 🔵 TODO | Extend `save_audio_metadata()` |
| (No separate A2A actions) | ✅ Decided | Just modify existing audio flow |

### 6. Pydantic Schemas

| Schema | Status | Notes |
|--------|--------|-------|
| `PartyInput` / `PartyOutput` | 🔵 TODO | |
| `WorkOutput` (with warnings) | 🔵 TODO | |
| `WriterInput` / `PublisherInput` | 🔵 TODO | For batch update tools |
| `SearchInput` / `SearchOutput` | 🔵 TODO | Simple pagination |

### 7. Testing

| Test Type | Status | Notes |
|-----------|--------|-------|
| Unit: Database operations | 🔵 TODO | CRUD + search + batch ops |
| Integration: MCP tools | 🔵 TODO | Tool → service → db |
| Integration: Auto-work creation | 🔵 TODO | Audio track → work linking |

---

## Task Breakdown (Linear)

### Task SP-1: Database Operations Foundation
**Linear**: [LOI-31](https://linear.app/loist/issue/LOI-31) | **Priority**: High | **Estimate**: 2 points

**Subtasks**:
- [x] SP-1.1: Implement party CRUD in `database/operations.py` (create, get_by_id)
- [x] SP-1.2: Implement party search (ILIKE on name)
- [x] SP-1.3: Implement work CRUD (create, get_by_id with writers/publishers/recordings)
- [x] SP-1.4: Implement work search (ILIKE on title)
- [x] SP-1.5: Implement junction table batch operations (replace writers, replace publishers)
- [x] SP-1.6: Add split warning calculation to get_work query
- [x] SP-1.7: Write unit tests

**Acceptance Criteria**:
- CRUD follows existing patterns (parameterized queries, error handling)
- Search uses `WHERE name ILIKE '%query%'` pattern
- Batch replace: DELETE existing + INSERT new in transaction
- Split warnings calculated with SUM aggregation
- Unit tests cover happy path and error cases

---

### Task SP-2: Repository & Service Layer
**Linear**: [LOI-32](https://linear.app/loist/issue/LOI-32) | **Priority**: High | **Estimate**: 2 points

**Subtasks**:
- [ ] SP-2.1: Create `PartyRepository` (interface + Postgres implementation)
- [ ] SP-2.2: Create `WorkRepository` (interface + Postgres implementation)
- [ ] SP-2.3: Create `party_service.py`
- [ ] SP-2.4: Create `work_service.py` with batch writer/publisher logic
- [ ] SP-2.5: Modify `audio_service.py` to auto-create works
- [ ] SP-2.6: Write service unit tests

**Acceptance Criteria**:
- Repositories follow `AudioRepository` pattern
- Auto-work creation happens inside audio track save
- Services wrap repository calls with logging

---

### Task SP-3: Pydantic Schemas
**Linear**: [LOI-33](https://linear.app/loist/issue/LOI-33) | **Priority**: Medium | **Estimate**: 1 point

**Subtasks**:
- [ ] SP-3.1: Create `src/schemas/party.py`
- [ ] SP-3.2: Create `src/schemas/work.py` (with warnings field)
- [ ] SP-3.3: Create `src/schemas/writer.py` and `publisher.py` for batch inputs
- [ ] SP-3.4: Update `src/schemas/__init__.py` exports

**Acceptance Criteria**:
- Schemas follow existing patterns (field validators, examples)
- Enums for party_type, split_status, work status
- Work output includes `warnings: List[str]`

---

### Task SP-4: MCP Tools Implementation
**Linear**: [LOI-34](https://linear.app/loist/issue/LOI-34) | **Priority**: High | **Estimate**: 3 points

**Subtasks**:
- [ ] SP-4.1: Create `src/tools/party_tools.py` (create, search, get)
- [ ] SP-4.2: Create `src/tools/work_tools.py` (get, search)
- [ ] SP-4.3: Create `src/tools/publishing_tools.py` (update_writers, update_publishers, link_artist)
- [ ] SP-4.4: Register all tools in `src/server.py`
- [ ] SP-4.5: Write tool integration tests

**Acceptance Criteria**:
- 8 tools registered and working
- Proper error handling with structured responses
- Integration tests verify full flow

---

### Task SP-5: Auto-Work Creation in Audio Pipeline
**Linear**: [LOI-35](https://linear.app/loist/issue/LOI-35) | **Priority**: High | **Estimate**: 1 point

**Subtasks**:
- [ ] SP-5.1: Modify `save_audio_metadata()` to create work first
- [ ] SP-5.2: Link audio_track to work via work_id
- [ ] SP-5.3: Integration test for audio upload → work creation
- [ ] SP-5.4: Update A2A handler if needed

**Acceptance Criteria**:
- Every audio track has a work
- Work title = audio track title
- Work status = 'draft'
- Existing audio upload flows continue working

---

### Task SP-6: Integration Testing
**Linear**: [LOI-36](https://linear.app/loist/issue/LOI-36) | **Priority**: Medium | **Estimate**: 1 point

**Subtasks**:
- [ ] SP-6.1: Integration tests for party → work → writer workflow
- [ ] SP-6.2: Integration tests for split warning calculation
- [ ] SP-6.3: Integration tests for batch update tools
- [ ] SP-6.4: Document testing approach

**Acceptance Criteria**:
- Tests run in Docker
- Cover realistic user workflows
- Verify warnings appear correctly

---

## Questions & Answers

### Music Copyright / Domain Questions (ANSWERED)

| # | Question | Answer |
|---|----------|--------|
| Q1 | Party deduplication suggestions? | **No for MVP**. Duplicates are annoying but not breaking. Users search before creating. |
| Q2 | Work merge conflict resolution? | **Keep all, flag for manual resolution**. If "John Smith" appears twice with 50% each, that's a warning, not an error. |
| Q3 | Split warnings placement? | **Include in every `get_work` response**. Cheap to calculate (one SUM query). Add `warnings: []` field. |
| Q4 | Auto-create party from artist string? | **No. Confirmed.** Raw strings stay as raw strings. Users intentionally create parties. |

### Technical / Scope Questions (ANSWERED)

| # | Question | Answer |
|---|----------|--------|
| Q5 | Search priority? | **Works first, parties second**. Users search "what song is this?" more than "who is this person?" |
| Q6 | A2A scope? | **Only auto-work creation for MVP**. Just extend audio ingestion. True A2A comes later. |
| Q7 | Bulk CSV import? | **No for MVP**. Single-create sufficient. Can script if needed. |
| Q8 | Status state machine? | **No enforcement**. Status is informational. Allow any transition. |

---

## Technical Decisions

### Confirmed Decisions

| Decision | Rationale |
|----------|-----------|
| Simple ILIKE search, not full-text | Sufficient for MVP, simpler implementation |
| 8 tools with batch update pattern | Reduces complexity, single tool handles add/remove/update |
| Split warnings in get_work | Always available, no separate round-trip |
| No party auto-creation from strings | Prevents duplicate party explosion |
| No status state machine | Status is informational, user manages their catalog |
| Auto-work in audio pipeline, not A2A | Simpler, just extend existing code |
| Junction ops via batch replace | DELETE all + INSERT new in transaction |

### Search Pattern

```sql
-- Party search
SELECT * FROM parties 
WHERE name ILIKE '%' || :query || '%'
ORDER BY name
LIMIT :limit OFFSET :offset;

-- Work search  
SELECT * FROM works
WHERE title ILIKE '%' || :query || '%'
ORDER BY title
LIMIT :limit OFFSET :offset;
```

### Split Warning Calculation

```sql
-- Part of get_work query
SELECT 
    w.*,
    COALESCE(SUM(ww.split_percentage), 0) as total_writer_split,
    COUNT(CASE WHEN ww.split_status = 'disputed' THEN 1 END) as disputed_writer_count
FROM works w
LEFT JOIN work_writers ww ON w.id = ww.work_id
WHERE w.id = :work_id
GROUP BY w.id;
```

---

## Testing Strategy

### Unit Tests
- **Location**: `tests/unit/`
- **Focus**: Database operations, warning calculation
- **Mocking**: Database connections

### Integration Tests
- **Location**: `tests/integration/`
- **Focus**: Tool → Service → Repository → Database flow
- **Environment**: Docker compose with local PostgreSQL

### Test Data Fixtures
- Sample parties (persons, organizations, with/without IPI)
- Sample works (different statuses)
- Sample splits (confirmed, disputed, unknown, >100%)
- Audio tracks with linked works

---

## Progress Tracking

### Sprint Progress

| Task | Linear | Points | Status | Notes |
|------|--------|--------|--------|-------|
| SP-1: Database Operations | [LOI-31](https://linear.app/loist/issue/LOI-31) | 2 | 🔵 TODO | |
| SP-2: Repository & Service | [LOI-32](https://linear.app/loist/issue/LOI-32) | 2 | 🔵 TODO | |
| SP-3: Pydantic Schemas | [LOI-33](https://linear.app/loist/issue/LOI-33) | 1 | 🔵 TODO | |
| SP-4: MCP Tools | [LOI-34](https://linear.app/loist/issue/LOI-34) | 3 | 🔵 TODO | |
| SP-5: Auto-Work Creation | [LOI-35](https://linear.app/loist/issue/LOI-35) | 1 | 🔵 TODO | |
| SP-6: Integration Testing | [LOI-36](https://linear.app/loist/issue/LOI-36) | 1 | 🔵 TODO | |
| **Total** | | **10** | | |

### Completed Items

- ✅ Migration SQL created (`010_song_publishing_schema.sql`)
- ✅ Design philosophy documented (`songs-schema-design-philosophy.md`)
- ✅ Codebase patterns analyzed
- ✅ Planning document created
- ✅ Questions Q1-Q8 answered
- ✅ Scope finalized (8 tools, simple search, auto-work only)
- ✅ Code review completed (2024-12-22):
  - Fixed SQL syntax error (line 1)
  - Fixed DECIMAL(6,4) → DECIMAL(5,2) for split percentages (allows 0-200%)
  - Added UNIQUE indexes for IPI/CAE, ISNI, and ISWC

---

## Next Steps

1. ~~**Create Linear Tasks**: Create SP-1 through SP-6 in Linear~~ ✅ Done (LOI-31 to LOI-36)
2. **Start Implementation**: Begin with SP-1 (Database Operations) - [LOI-31](https://linear.app/loist/issue/LOI-31)
3. **Iterate**: Update this document as implementation progresses

---

*Document maintained by: AI Agent*  
*Last scope review: 2024-12-22*
