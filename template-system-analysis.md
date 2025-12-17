# Template System Analysis: Technical Debt Assessment

## TL;DR

- **Single canonical type**: `PlayerConfig` returned by `get_embed_url` (static embed configuration, not runtime UI state)
- **Removed redundancy**: `check_waveform_availability` has been removed (LOI-21). Use `get_embed_url` with `template="waveform"` instead.
- **Keep dual endpoints**: Simple embeds (`/embed/{id}`) vs rich waveform (`/embed/{id}/waveform`); consider query-param unification later
- **Backend-only embeds**: Open SaaS frontend is a consumer only; embed HTML served solely by backend

## Context & Goals

This document assesses technical debt in the Loist Music Library's embed/template system and defines a consolidated design around `get_embed_url` returning a canonical `PlayerConfig`.

The system supports a dual architecture: backend-hosted embed players consumed by external platforms (Notion, Coda) and a separate Open SaaS frontend application. Share links are served by the MCP server backend, not the frontend application, which acts only as an API consumer.

### Tech Stack Context

- **Backend**: Python (MCP server) — *where implementation work happens*
- **Frontend**: Wasp.sh (React/TypeScript) — *API consumer only*

The TypeScript type definitions below represent API response contracts. The Python implementation should return data matching these shapes (e.g., via `TypedDict` or Pydantic models).

## Current Architecture Snapshot

### MCP Tools & Resources

| Tool Name | Purpose | Key Parameters | Response |
|-----------|---------|----------------|----------|
| **`health_check`** | Server status verification | None | Server version, config, health status |
| **`process_audio_complete`** | Audio ingestion pipeline | `source` (HTTP URL), `options` (processing settings) | Audio metadata, GCS URLs, processing status |
| **`get_audio_metadata`** | Retrieve track metadata | `audio_id` (UUID) | Complete track metadata (artist, title, format, etc.) |
| **`search_library`** | Full-text search across library | `query`, `filters`, `limit`, `offset`, `sort_by` | Search results with relevance scores |
| **`delete_audio`** | Remove tracks from system | `audio_id` (UUID) | Deletion confirmation |
| **`update_metadata`** | Modify track information | `audio_id`, `metadata` (fields to update) | Updated metadata confirmation |
| **`get_embed_url`** | Generate shareable embed links | `audio_id`, `template`, `device` | Embed URL, waveform status, metadata |
| **`list_embed_templates`** | Template capabilities for frontend | None | Available templates with features/devices |
| **`get_embed_url` (with `template="waveform"`)** | Waveform generation status | `audio_id`, `template`, `device` | Waveform availability, URLs, metadata |
| **`download_audio`** | Format conversion & download | `input_data` (audioId, format, preset) | Signed download URL, file info |

### Audio Streaming Resources

| Resource URI | Access Method | Purpose | Response |
|--------------|---------------|---------|----------|
| **`music-library://audio/{audioId}/stream`** | `POST /mcp/resources/` | Audio streaming URLs | Signed GCS URL with 15min expiration + range request support |
| **`music-library://audio/{audioId}/thumbnail`** | `POST /mcp/resources/` | Album artwork URLs | Signed GCS URL for images |

### HTTP Endpoints

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| **`/health/database`** | GET | Database connectivity check | Connection status, latency |
| **`/health/live`** | GET | Application liveness probe | Service availability status |
| **`/health/ready`** | GET | Application readiness probe | Full system health check |
| **`/.well-known/oembed.json`** | GET | oEmbed provider discovery | oEmbed endpoint configuration |
| **`/oembed`** | GET | Rich embed previews for platforms | oEmbed JSON (iframe HTML, metadata) |
| **`GET /embed/{audio_id}`** | GET | Standard audio player (embedding) | HTML page with simple player |
| **`GET /embed/{audio_id}/waveform`** | GET | Waveform player (direct access) | HTML page with interactive waveform |
| **`GET /embed/{audio_id}/waveform/mobile`** | GET | Mobile-optimized waveform player | HTML page optimized for touch devices |
| **`GET /embed/{audio_id}/waveform/desktop`** | GET | Desktop-optimized waveform player | HTML page with full interactive features |
| **`DELETE /api/tracks/{audioId}`** | DELETE | HTTP-accessible track deletion | Deletion confirmation |

## Problems Identified

### Redundant MCP Tools
- ~~`check_waveform_availability`~~ (removed LOI-21) - Use `get_embed_url` with `template="waveform"` instead
- Both validate audio_id existence and check waveform availability
- Both return similar metadata structures and handle same error cases

### Over-engineered URL Structure
- 4 separate waveform endpoints (`/waveform`, `/waveform/mobile`, `/waveform/desktop`) for 2 player types
- Query parameter templates (`?template=waveform`) mentioned in docs but not implemented
- Inconsistent routing patterns mixing path-based and query parameter approaches

### Documentation Drift
- Embed player guide claims query params work, but actual implementation uses path routing
- Missing audio streaming API documentation (only discovered during analysis)
- Frontend API integration docs don't fully reflect MCP vs HTTP API separation

### Missing API Coverage
- Audio streaming APIs completely missing from initial analysis
- Album artwork endpoints not properly documented as MCP resources
- Frontend integration points confused MCP tools with HTTP endpoints

## Target Design: Canonical Types & Responsibilities

### Canonical MCP Response Shape

**All MCP tools that deal with embeds MUST return or embed the `PlayerConfig` shape:**

*Note: This TypeScript type defines the API response contract. Python implementation should return matching data structures.*

```typescript
type PlayerConfig = {
  audio_id: string;
  mode: "simple" | "waveform";
  device: "desktop" | "mobile" | "auto";
  context: "embed" | "direct";
  waveform_available: boolean;
  urls: {
    embed: string;
    waveform?: string;
    artwork?: string;
    waveform_svg?: string;
  };
  metadata: {
    title: string;
    artist: string;
    album?: string;
    duration_seconds?: number;
  };
};
```

**Note**: "PlayerConfig" describes static embed/playback configuration, not runtime UI state. MCP tools expose library facts, not live playback position.

### MCP Tool Responsibilities (Explicit Contract)

- `get_embed_url(audio_id, template?, device?)` → **PRIMARY**: Returns complete `PlayerConfig` (URLs + waveform_available + metadata)
- `list_embed_templates()` → **STATIC**: Returns template/device capabilities; never queries track-specific data
- ~~`check_waveform_availability(audio_id)`~~ → **REMOVED** (LOI-21): Use `get_embed_url(audio_id, template="waveform", device="auto")` instead

### Dual Player Behavior

- **Simple embeds** (`/embed/{id}`): For platforms like Notion/Coda - minimal player, no waveform
- **Rich waveform** (`/embed/{id}/waveform`): For direct access - interactive waveform player
- **Future consideration**: Query parameter unification (`?template=waveform&device=mobile`)

### Phase 1: Safe Consolidation (Immediate)
- **Implement `PlayerConfig` type and update `get_embed_url` to return it consistently** (M)  
  *Depends on: None*  
  *Done when: `get_embed_url` returns full `PlayerConfig` shape with all required fields, existing tests pass*
- **Refactor `check_waveform_availability` to delegate to `get_embed_url` and mark as deprecated** (S)  
  *Depends on: PlayerConfig type implementation*  
  *Done when: tool returns identical data to `get_embed_url`, deprecation warning logged, tests pass*
- **Update documentation to clarify dual embed vs direct access patterns** (S)  
  *Depends on: None (can run in parallel)*  
  *Done when: API docs clearly distinguish embed vs direct contexts, no ambiguous references*

### Phase 2: Enhanced Capabilities (Additive)
- **Add missing audio streaming and artwork resource documentation** (S)  
  *Depends on: None (can run in parallel)*  
  *Done when: docs include MCP resource endpoints and signed URL mechanics*
- **Implement device detection APIs if needed for frontend** (M)  
  *Depends on: Frontend requirements analysis*  
  *Done when: frontend can detect device type for optimal embed URLs*
- **Add/update tests ensuring single source of truth for embed configuration** (M)  
  *Depends on: PlayerConfig type and check_waveform_availability refactoring*  
  *Done when: all waveform/embed tests use `get_embed_url`, no direct `check_waveform_availability` calls*

### Phase 3: URL Simplification (Future)
- **Consider query parameter approach for waveform variants** (`?template=waveform&device=mobile`) (L)  
  *Depends on: Phase 1 completion*  
  *Done when: design decision made, implementation plan documented*
- **Evaluate deprecation/removal of redundant waveform endpoints** (M)  
  *Depends on: Phase 1 completion*  
  *Done when: impact analysis complete, migration plan documented*
- **Simplify URL structure once frontend integration is stable** (L)  
  *Depends on: Frontend integration stability + Phase 2 completion*  
  *Done when: unified URL scheme implemented, backward compatibility maintained*

### Breaking vs Safe Changes

**Safe Changes (Phase 1)**:
- Enhancing `get_embed_url` with additional fields
- Adding deprecation warnings to redundant tools
- Improving documentation without breaking APIs

**Breaking Changes (Phase 3)**:
- Removing `check_waveform_availability` endpoint
- Changing URL patterns (though backward compatibility possible)
- Major API contract changes

## Task Breakdown for Planning Agent

| Task | Files | Effort | Depends On | Done When |
|------|-------|--------|------------|-----------|
| Define PlayerConfig type | `src/server.py` (add type definition) | S | — | Type exported and imported correctly |
| Update get_embed_url return | `src/server.py` (lines ~1646-1669) | M | PlayerConfig type | Returns full PlayerConfig shape, existing tests pass |
| Deprecate check_waveform_availability | `src/server.py` (lines ~1774-1781) | S | get_embed_url updated | Delegates internally, logs deprecation warning |
| Update embed tests | `test_embed_*.py`, `test_mcp_tools.py` | M | get_embed_url updated | All tests use get_embed_url, no direct check_waveform_availability calls |
| Update documentation | `docs/frontend-api-integration.md`, `docs/embed-player-guide.md` | S | None (parallel) | Docs clarify dual embed vs direct patterns |
| Add streaming/artwork docs | `docs/mcp-resources-api.md` | S | None (parallel) | Resource endpoints documented with signed URL mechanics |

## Current Test Coverage

**Key test files for embed/template functionality:**
- `test_embed_simple.py` - Basic embed endpoint testing
- `test_embed_mock_gcs.py` - Embed functionality with mocked GCS
- `test_embed_direct.py` - Direct embed URL testing
- `test_mcp_tools.py` - MCP tool functionality including `get_embed_url`
- `tests/test_query_tools.py` - Search and embed URL generation
- `tests/test_oembed_endpoint.py` - oEmbed endpoint testing

**Current coverage gaps:**
- Limited testing of `check_waveform_availability` deprecation path
- No explicit tests for `PlayerConfig` shape consistency
- Missing integration tests for frontend consumption patterns

**CI/CD integration:** Tests run via pytest in `pytest.ini` configuration with coverage reporting.

---

## Background Analysis (Reference Only)

*The following sections document the detailed analysis that informed the task breakdown above. Not required reading for implementation.*

```python
# check_waveform_availability (lines 1774-1781)
waveform_context = await get_waveform_context(audio_id)
metadata = get_audio_metadata_by_id(audio_id)
return {
    "waveform_available": waveform_context.get("waveform_available", False),
    "metadata": AudioMetadata(...)  # Full metadata object
}

# get_embed_url (lines 1646-1669)
waveform_context = await get_waveform_context(audio_id)
metadata = get_audio_metadata_by_id(audio_id)
return {
    "waveform_available": waveform_available,  # Same check
    "metadata": {                              # Simpler metadata
        "title": metadata.get("title", "Untitled"),
        "artist": metadata.get("artist", "Unknown Artist"),
        ...
    }
}
```

### 2. Over-Engineered URL Structure

**Current URLs**:
```
/embed/{id}                          # Standard
/embed/{id}/waveform                 # Auto-detect
/embed/{id}/waveform/mobile          # Mobile-specific
/embed/{id}/waveform/desktop         # Desktop-specific
```

**Problems**:
- **4 separate endpoints** for 2 player types
- Device detection logic duplicated across endpoints
- Query parameter approach (`?template=waveform`) mentioned in docs but not consistently implemented

### 3. Template System Inconsistency

**Documentation vs Implementation**:

**Docs claim** (embed-player-guide.md:73-79):
```
Standard Player    | /embed/{audioId}              | Traditional audio player
Standard + Waveform| /embed/{audioId}?template=waveform | Interactive waveform
Waveform Player    | /embed/{audioId}/waveform        | Dedicated waveform endpoint
```

**Actual Implementation**:
- Query parameter `?template=waveform` **NOT implemented**
- All waveform variants use path-based routing
- No fallback from query params to standard player

### 4. MCP Tool Overlap

**get_embed_url** already does everything check_waveform_availability does, plus:
- URL generation logic
- Device-specific endpoint selection
- Template validation

## Recommended Consolidation

### Option 1: Minimal Changes (Recommended)

**Keep existing endpoints but eliminate redundancy:**

1. **Remove `check_waveform_availability`** - Functionality absorbed into `get_embed_url`
2. **Update `get_embed_url`** to return waveform availability status by default
3. **Keep `list_embed_templates`** - Useful for frontend integration

**Benefits**:
- Reduces API surface area
- Single source of truth for embed URL generation
- Maintains backward compatibility

### Option 2: URL Simplification

**Consolidate to 2 endpoints with query parameters:**

```
/embed/{id}              # Standard player
/embed/{id}?template=waveform&auto=true  # Auto-detect device
/embed/{id}?template=waveform&device=mobile   # Explicit device
/embed/{id}?template=waveform&device=desktop # Explicit device
```

**Benefits**:
- Single endpoint per player type
- Flexible device targeting
- Easier to extend with new templates

## Implementation Impact Assessment

### Breaking Changes
- Removing `check_waveform_availability` would break existing integrations
- URL structure changes would affect bookmarking and sharing

### Safe Changes
- `get_embed_url` can be enhanced without breaking changes
- `list_embed_templates` can remain as-is

## Documentation Gaps Identified

### Inconsistent Response Formats
- `frontend-api-integration.md` shows different field names than actual implementation
- Missing documentation for device-specific waveform endpoints
- No clear guidance on when to use which endpoint

### Missing Context
- No explanation of why multiple waveform endpoints exist
- No performance comparison between different approaches
- No guidance on template selection for different use cases

## Files Requiring Review

### Core Implementation
- `src/server.py` - All embed endpoints and MCP tools
- `src/resources/embed.py` - HTTP route handlers (if separate)

### Documentation
- `docs/embed-player-guide.md` - Template selection and URL patterns
- `docs/frontend-api-integration.md` - API endpoint documentation
- `docs/embed-implementation-status.md` - Architecture overview

### Testing
- `test_embed_*.py` files - Test coverage for different endpoints
- Postman collection entries for all endpoints

### Configuration
- Any routing configuration files
- Template detection logic

---

---

## Appendix: Reference Documentation (Not In Scope for Core Work)

*This appendix contains detailed technical information for reference. The core PlayerConfig consolidation work does not require changes to streaming, oEmbed, or error handling systems documented here.*

### Audio Streaming Technical Details

**Audio streaming is handled through MCP resources (not direct HTTP endpoints):**

| Resource URI | Access Method | Purpose | Response |
|--------------|---------------|---------|----------|
| **`music-library://audio/{audioId}/stream`** | `POST /mcp/resources/` | **Audio streaming URLs** | Signed GCS URL with 15min expiration + range request support |
| **`music-library://audio/{audioId}/thumbnail`** | `POST /mcp/resources/` | Album artwork URLs | Signed GCS URL for images |

**How Audio Streaming Works:**
- **Embed players** generate signed GCS URLs internally using cached URL generation
- **Frontend** calls MCP resource endpoints to get streaming URLs
- **URLs expire** in 15 minutes for security
- **Range requests** supported for seeking (HTTP 206 Partial Content)
- **MIME types**: MP3, FLAC, M4A, OGG, WAV, AAC with proper `Content-Type` headers
- **Performance**: First request ~50-100ms, cached requests ~5-10ms, 13.5min cache TTL

### Additional Technical Details

#### Signed URL Security Model
- **Expiration**: 15 minutes for audio streams, 15 minutes for thumbnails
- **Access Control**: GCS bucket policies restrict to authenticated service account
- **Cache Strategy**: URL generation cached for 13.5 minutes to reduce GCS API calls
- **CORS**: Enabled for browser access with appropriate headers

#### Range Request Implementation
```http
GET /audio.mp3 HTTP/1.1
Range: bytes=0-1023
Accept-Ranges: bytes

HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/100000
Content-Length: 1024
Content-Type: audio/mpeg
```

#### oEmbed Integration Details
- **Discovery**: `/embed/{id}` pages include `<link rel="alternate" type="application/json+oembed">` tags
- **Provider Endpoint**: `/oembed` supports JSON format with iframe HTML responses
- **Platform Optimization**: Automatic detection and formatting for Notion, Coda, Slack, etc.

#### Error Handling Patterns
- **Validation Errors**: 400 Bad Request with detailed field validation messages
- **Not Found**: 404 with user-friendly HTML pages for embed endpoints
- **Server Errors**: 500 with logging and graceful degradation
- **MCP Protocol**: Consistent `{success: false, error: "CODE", message: "..."}` format

---

**Analysis Date**: December 2025
**Analyst**: AI Assistant
**Next Step**: Ready for implementation with consolidated PlayerConfig approach
