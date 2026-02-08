# API Endpoint Refactoring Plan

**Date:** 2025-01-XX  
**Status:** Planning Phase  
**Purpose:** Refactor HTTP API endpoints to remove MCP coupling and introduce a service layer

---

## Planning Structure (For Gemini CLI)

### Root Task
Refactor HTTP API endpoints to remove MCP coupling and introduce a service layer.

### Milestones
1. **Service Layer Creation** - Extract business logic from MCP tools into shared service layer
2. **Metadata Endpoint Refactor** - Refactor GET `/api/tracks/{audioId}` to use service layer
3. **Search Endpoint Refactor** - Refactor GET `/api/search` to use service layer
4. **Streaming Endpoint Refactor** - Refactor GET `/api/tracks/{audioId}/stream` with proper HTTP streaming
5. **Thumbnail Endpoint Refactor** - Refactor GET `/api/tracks/{audioId}/thumbnail` with proper image serving
6. **Delete Endpoint Refactor** - Refactor DELETE `/api/tracks/{audioId}` to use service layer
7. **Testing & Documentation** - Update tests and document new architecture

### Open Questions (Keep Visible Until Resolved)
1. **Streaming Architecture:** Proxy streaming through API server vs signed URL redirect?
2. **Image Optimization:** Should thumbnail endpoint support resizing/format conversion?
3. **Caching Strategy:** What caching headers should be used for each endpoint?
4. **Error Response Format:** Should HTTP API use different error format than MCP?
5. **Versioning:** Should HTTP API be versioned (`/api/v1/...`)?
6. **Rate Limiting:** Should rate limiting be added to HTTP API endpoints?

### Related Files
- **Task List:** `docs/api-refactor-tasks.md` (generated from this plan)
- **Progress Summary:** `docs/api-refactor-summary.md` (rolling summary of work completed)
- **Research Notes:** `docs/api-refactor-research.md` (answers to open questions)

---

## Executive Summary

An audit of the HTTP API endpoints revealed that **5 out of 6 endpoints** are thin wrappers around MCP tools/resources rather than proper HTTP REST API implementations. This creates architectural issues, performance inefficiencies, and maintenance challenges. This document outlines the current state, problems identified, and recommendations for refactoring.

---

## Current State Analysis

### HTTP API Endpoints Overview

The HTTP API is defined in two locations:
- `src/http_api.py` - Main HTTP API routes (5 endpoints)
- `src/server.py` - Additional HTTP routes (1 endpoint + embed/oembed routes)

### Endpoint Inventory

| Endpoint | Method | Location | Type | Wraps MCP | Status |
|----------|--------|----------|------|-----------|--------|
| `/api/tracks/{audioId}` | GET | `http_api.py:67` | Tool wrapper | `get_audio_metadata` | ⚠️ Wrapper |
| `/api/search` | GET | `http_api.py:122` | Tool wrapper | `search_library` | ⚠️ Wrapper |
| `/api/tracks/{audioId}/stream` | GET | `http_api.py:208` | Resource wrapper | `get_audio_stream_resource` | ⚠️ Wrapper + Bugs |
| `/api/tracks/{audioId}/thumbnail` | GET | `http_api.py:263` | Resource wrapper | `get_thumbnail_resource` | ⚠️ Wrapper |
| `/api/tracks/{audioId}/download` | GET | `http_api.py:333` | Direct implementation | N/A | ✅ Proper |
| `/api/tracks/{audioId}` | DELETE | `server.py:2060` | Tool wrapper | `delete_audio` | ⚠️ Wrapper |

---

## Detailed Analysis

### 1. GET `/api/tracks/{audioId}` - Metadata Endpoint

**Current Implementation:**
```python
@mcp.custom_route("/api/tracks/{audioId}", methods=["GET"])
async def get_track(request: Request) -> JSONResponse:
    # ...
    result = await get_metadata_func({"audio_id": audio_id})  # MCP tool call
    return JSONResponse(result, status_code=200)
```

**Issues:**
- Thin wrapper around MCP tool `get_audio_metadata`
- No direct database access or business logic
- Coupled to MCP tool implementation
- Error handling converts MCP tool errors to HTTP status codes

**What It Should Be:**
- Direct database query via repository/service layer
- Proper HTTP semantics (ETags, caching headers)
- Independent of MCP protocol

---

### 2. GET `/api/search` - Search Endpoint

**Current Implementation:**
```python
@mcp.custom_route("/api/search", methods=["GET"])
async def search_tracks(request: Request) -> JSONResponse:
    # Parse query params...
    input_data = {
        "query": query.strip(),
        "filters": filters if filters else None,
        "limit": limit,
        "offset": offset,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    result = await search_func(input_data)  # MCP tool call
    return JSONResponse(result, status_code=200)
```

**Issues:**
- Only parses HTTP query parameters, then delegates to MCP tool
- No direct database access
- Coupled to MCP tool parameter structure

**What It Should Be:**
- Direct database query with full-text search
- Proper pagination headers (`Link`, `X-Total-Count`)
- Query parameter validation and sanitization
- Independent search service layer

---

### 3. GET `/api/tracks/{audioId}/stream` - Audio Streaming Endpoint

**Current Implementation:**
```python
@mcp.custom_route("/api/tracks/{audioId}/stream", methods=["GET"])
async def get_track_stream(request: Request) -> JSONResponse:
    uri = f"music-library://audio/{audio_id}/stream"
    result = await get_audio_stream_resource(uri)  # MCP resource call
    
    if not result.get("success", False):  # ⚠️ BUG: success field doesn't exist!
        # Error handling...
    
    return JSONResponse(result, status_code=200)  # Returns JSON with URL
```

**Critical Issues:**
1. **Buggy Error Handling:** Checks for `result.get("success", False)` but MCP resources return `{"uri": "...", "mimeType": "...", "text": null, "blob": null}` - no `success` field
2. **Not Actually Streaming:** Returns JSON with signed GCS URL instead of streaming audio directly
3. **No Range Request Support:** Cannot handle HTTP Range requests (`Range: bytes=0-1023`)
4. **Extra Request Required:** Client must make two requests (one to get URL, one to stream)

**What It Should Be:**
- Direct HTTP streaming from GCS through API server (or proper redirect with headers)
- HTTP Range request support (`Accept-Ranges: bytes`, `Content-Range` headers)
- Proper streaming headers (`Content-Type`, `Content-Length`)
- Single request to stream audio

**Architecture Options:**

**Option A: Proxy Streaming (Recommended)**
- API server streams audio from GCS to client
- Full control over headers, caching, rate limiting
- Supports Range requests properly
- More server load but better control

**Option B: Signed URL Redirect**
- Generate signed URL and redirect with proper headers
- Less server load
- GCS handles Range requests
- Current approach but needs proper headers

---

### 4. GET `/api/tracks/{audioId}/thumbnail` - Thumbnail Endpoint

**Current Implementation:**
```python
@mcp.custom_route("/api/tracks/{audioId}/thumbnail", methods=["GET"])
async def get_track_thumbnail(request: Request) -> JSONResponse:
    uri = f"music-library://audio/{audio_id}/thumbnail"
    result = await get_thumbnail_resource(uri)  # MCP resource call
    
    if not result.get("success", False):  # ⚠️ Same bug as stream endpoint
        # Error handling...
    
    return JSONResponse(result, status_code=200)  # Returns JSON with URL
```

**Issues:**
1. **Same Bug:** Checks for `success` field that doesn't exist
2. **Not Serving Images:** Returns JSON with signed URL instead of serving image directly
3. **No Image Optimization:** Cannot resize, compress, or format-convert images
4. **No Caching Headers:** Missing proper cache control for images

**What It Should Be:**
- Direct image serving (or redirect with proper headers)
- Image optimization (resize, format conversion, compression)
- Proper caching headers (`Cache-Control`, `ETag`)
- Content-Type based on actual image format

---

### 5. DELETE `/api/tracks/{audioId}` - Delete Endpoint

**Current Implementation:**
```python
@mcp.custom_route("/api/tracks/{audioId}", methods=["DELETE"])
async def delete_track(request):
    result = await delete_func({"audio_id": audioId})  # MCP tool call
    
    if result.get("success"):
        return JSONResponse({}, status_code=204)
    # Error handling...
```

**Issues:**
- Thin wrapper around MCP tool
- No direct database access
- Coupled to MCP tool response format

**What It Should Be:**
- Direct database deletion via repository/service layer
- Proper HTTP semantics (204 No Content on success)
- Soft delete option (mark as deleted vs hard delete)
- Cascade handling for related resources

---

### 6. GET `/api/tracks/{audioId}/download` - Download Endpoint ✅

**Current Implementation:**
- Direct implementation with proper HTTP streaming
- Downloads from GCS, converts audio, streams response
- Proper cleanup of temp files
- Good error handling

**Status:** This is the model for how other endpoints should be implemented.

---

## Problems Identified

### 1. Architectural Issues

**No Separation of Concerns:**
- HTTP API logic is mixed with MCP protocol logic
- Business logic is embedded in MCP tools/resources
- No shared service layer

**Tight Coupling:**
- HTTP API depends on MCP tool/resource implementations
- Changes to MCP tools affect HTTP API behavior
- Cannot evolve HTTP API independently

**Protocol Confusion:**
- HTTP endpoints return MCP protocol responses
- MCP resource URIs (`music-library://...`) used in HTTP API
- Mixed abstraction levels

### 2. Performance Issues

**Extra Indirection:**
- HTTP request → MCP tool/resource → Business logic → Database
- Should be: HTTP request → Service layer → Database

**Inefficient Streaming:**
- Stream endpoint returns JSON URL instead of streaming
- Client must make two requests (get URL, then stream)
- No Range request support

**No Caching:**
- Missing HTTP caching headers
- No ETag support
- Cannot leverage CDN/cache layers

### 3. Buggy Error Handling

**Incorrect Field Checks:**
- Stream/thumbnail endpoints check for `success` field that doesn't exist in MCP resource responses
- Error paths may never execute correctly
- Inconsistent error response formats

**Exception Handling:**
- Some endpoints catch exceptions but don't handle MCP-specific errors properly
- Error messages may leak internal implementation details

### 4. Missing HTTP Features

**No Proper Headers:**
- Missing `ETag`, `Last-Modified`, `Cache-Control`
- No `Accept-Ranges` for streaming
- No `Content-Range` for partial content

**No HTTP Semantics:**
- Not using proper status codes consistently
- Missing `Link` headers for pagination
- No `Location` headers for redirects

**No Content Negotiation:**
- Cannot request different response formats
- No compression support
- No format negotiation

---

## Recommended Architecture

### Proposed Service Layer Structure

```
HTTP API Layer (REST endpoints)
    ↓
Service Layer (Business logic)
    ↓
Repository Layer (Data access)
    ↓
Database / GCS
```

### Shared Service Layer

Create `src/services/` directory with:

- **`audio_service.py`** - Audio metadata operations
  - `get_audio_metadata(audio_id)` - Get track metadata
  - `search_audio(query, filters, pagination)` - Search tracks
  - `delete_audio(audio_id)` - Delete track
  - `update_audio_metadata(audio_id, metadata)` - Update metadata

- **`streaming_service.py`** - Audio streaming operations
  - `get_audio_stream(audio_id, range_header=None)` - Get audio stream
  - `get_thumbnail(audio_id, size=None, format=None)` - Get thumbnail
  - `generate_signed_url(gcs_path, expiration)` - Generate signed URLs

- **`download_service.py`** - Audio download/conversion
  - `download_audio(audio_id, format, preset)` - Download with conversion
  - (Already partially implemented in download endpoint)

### MCP Tools/Resources Use Services

MCP tools and resources should call the same service layer:

```python
# MCP Tool
@mcp.tool()
async def get_audio_metadata(audio_id: str) -> dict:
    from src.services.audio_service import get_audio_metadata
    return await get_audio_metadata(audio_id)

# HTTP API Endpoint
@mcp.custom_route("/api/tracks/{audioId}", methods=["GET"])
async def get_track(request: Request) -> JSONResponse:
    from src.services.audio_service import get_audio_metadata
    audio_id = request.path_params.get("audioId")
    metadata = await get_audio_metadata(audio_id)
    return JSONResponse(metadata, status_code=200)
```

---

## Refactoring Plan

### Phase 1: Create Service Layer

1. **Create `src/services/` directory structure**
   - `__init__.py`
   - `audio_service.py`
   - `streaming_service.py`
   - `download_service.py`

2. **Extract business logic from MCP tools**
   - Move logic from `src/tools/query_tools.py` to `audio_service.py`
   - Move logic from `src/resources/audio_stream.py` to `streaming_service.py`
   - Move logic from `src/resources/thumbnail.py` to `streaming_service.py`

3. **Update MCP tools to use services**
   - Refactor MCP tools to call service layer
   - Keep MCP protocol-specific formatting in tools

### Phase 2: Refactor HTTP API Endpoints

1. **Refactor GET `/api/tracks/{audioId}`**
   - Use `audio_service.get_audio_metadata()` directly
   - Add proper HTTP headers (ETag, Cache-Control)
   - Remove MCP tool dependency

2. **Refactor GET `/api/search`**
   - Use `audio_service.search_audio()` directly
   - Add pagination headers (Link, X-Total-Count)
   - Improve query parameter validation

3. **Refactor GET `/api/tracks/{audioId}/stream`**
   - Use `streaming_service.get_audio_stream()` directly
   - Implement proper HTTP streaming with Range support
   - Fix error handling bugs
   - Add proper streaming headers

4. **Refactor GET `/api/tracks/{audioId}/thumbnail`**
   - Use `streaming_service.get_thumbnail()` directly
   - Serve images directly (or redirect with proper headers)
   - Add image optimization
   - Fix error handling bugs

5. **Refactor DELETE `/api/tracks/{audioId}`**
   - Use `audio_service.delete_audio()` directly
   - Improve error handling
   - Add proper HTTP semantics

### Phase 3: Testing & Documentation

1. **Update tests**
   - Test service layer independently
   - Test HTTP endpoints independently
   - Test MCP tools still work

2. **Update documentation**
   - Document new service layer
   - Update API documentation
   - Document architecture changes

## Testing Strategy

### Testing Environment

**Important**: This project uses **Docker-based testing** (not venv). Integration tests require Docker Compose to be running.

**Test Setup:**
```bash
# Start Docker Compose (provides PostgreSQL for integration tests)
docker-compose up -d postgres

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run unit tests only (no Docker required)
pytest -m "not (requires_db or requires_gcs or slow)"

# Run integration tests (requires Docker)
pytest -m "requires_db"
```

### Testing Requirements for Refactoring

#### Service Layer Testing

**Test each service independently:**
- `audio_service.py`: Test metadata operations, search, delete
- `streaming_service.py`: Test audio streaming, thumbnail generation, signed URLs
- `download_service.py`: Test audio download/conversion (already partially tested)

**Test Patterns:**
```python
# Unit tests with mocked dependencies
def test_get_audio_metadata_success(mock_repository):
    """Test successful metadata retrieval."""
    service = AudioService(mock_repository)
    result = await service.get_audio_metadata("test-id")
    assert result["id"] == "test-id"

# Integration tests with real database (Docker required)
@pytest.mark.requires_db
def test_get_audio_metadata_integration(db_pool):
    """Test metadata retrieval with real database."""
    service = AudioService(PostgresAudioRepository(db_pool))
    result = await service.get_audio_metadata("existing-id")
    assert result is not None
```

#### HTTP Endpoint Testing

**Test each refactored endpoint:**
- GET `/api/tracks/{audioId}`: Test direct service calls, HTTP headers, error handling
- GET `/api/search`: Test query parsing, pagination headers, service integration
- GET `/api/tracks/{audioId}/stream`: Test streaming, Range requests, headers
- GET `/api/tracks/{audioId}/thumbnail`: Test image serving, optimization, caching
- DELETE `/api/tracks/{audioId}`: Test deletion, HTTP semantics, error handling

**Test Patterns:**
```python
@pytest.mark.asyncio
async def test_get_track_endpoint(client, mock_audio_service):
    """Test GET /api/tracks/{audioId} endpoint."""
    # Mock service layer
    mock_audio_service.get_audio_metadata.return_value = {"id": "test-id"}
    
    # Test endpoint
    response = await client.get("/api/tracks/test-id")
    assert response.status_code == 200
    assert response.headers.get("ETag") is not None
    assert response.headers.get("Cache-Control") is not None

@pytest.mark.requires_db
async def test_get_track_endpoint_integration(client, db_pool):
    """Test endpoint with real database."""
    # Create test data
    # Test endpoint
    response = await client.get("/api/tracks/existing-id")
    assert response.status_code == 200
```

#### MCP Tool Compatibility Testing

**Verify MCP tools still work after refactoring:**
- `get_audio_metadata`: Should use same service layer
- `search_library`: Should use same service layer
- `delete_audio`: Should use same service layer
- Resources (`get_audio_stream_resource`, `get_thumbnail_resource`): Should use streaming service

**Test Pattern:**
```python
@pytest.mark.asyncio
async def test_mcp_tool_uses_service_layer():
    """Verify MCP tool calls service layer correctly."""
    from src.tools.query_tools import get_audio_metadata
    
    # Mock service layer
    with patch('src.services.audio_service.get_audio_metadata') as mock_service:
        mock_service.return_value = {"id": "test-id"}
        
        # Call MCP tool
        result = await get_audio_metadata({"audio_id": "test-id"})
        
        # Verify service was called
        mock_service.assert_called_once_with("test-id")
        assert result["id"] == "test-id"
```

### Testing Documentation References

**Comprehensive Testing Guides:**
- **[Testing Strategy and Recovery](docs/testing-strategy-and-recovery.md)** - Complete testing architecture, patterns, and best practices
- **[Testing Practices Guide](docs/testing-practices-guide.md)** - Detailed testing infrastructure, fixtures, and CI/CD integration
- **[Pre-PR Testing Guide](docs/pre-pr-testing-guide.md)** - Local testing before pull requests

**Key Testing Concepts:**
- **Docker-Based Testing**: Integration tests use Docker Compose PostgreSQL container
- **Test Markers**: Use `@pytest.mark.requires_db` for database tests, `@pytest.mark.requires_gcs` for GCS tests
- **Repository Pattern**: Mock repositories for unit tests, real repositories for integration tests
- **Coverage Requirements**: 75% unit test coverage, 70% database test coverage (production)

### Testing Checklist

**Before completing each refactored endpoint:**
- [ ] Service layer has unit tests (mocked dependencies)
- [ ] Service layer has integration tests (real database via Docker)
- [ ] HTTP endpoint has unit tests (mocked service layer)
- [ ] HTTP endpoint has integration tests (real service + database)
- [ ] MCP tool compatibility verified (still works with service layer)
- [ ] Error handling tested (all error paths covered)
- [ ] HTTP headers tested (ETag, Cache-Control, etc.)
- [ ] Performance validated (no regression from wrapper approach)

---

## Implementation Considerations

### Streaming Architecture Decision

**Question:** Should streaming endpoints proxy through API server or redirect to signed URLs?

**Option A: Proxy Streaming (Recommended)**
- Pros: Full control, proper Range support, analytics, rate limiting
- Cons: More server load, bandwidth costs

**Option B: Signed URL Redirect**
- Pros: Less server load, GCS handles Range requests
- Cons: Less control, harder to add features

**Recommendation:** Start with Option B (redirect) for simplicity, but design service layer to support Option A (proxy) if needed later.

### Backward Compatibility

- MCP tools/resources must continue to work
- HTTP API endpoints should maintain same URL structure
- Response formats may change (but should be documented)

### Migration Strategy

1. Create service layer alongside existing code
2. Update HTTP endpoints to use services
3. Update MCP tools to use services
4. Remove old MCP tool implementations (keep protocol wrappers)
5. Test thoroughly
6. Deploy incrementally

---

## Success Criteria

### Functional Requirements

- [ ] All HTTP endpoints work without MCP dependency
- [ ] MCP tools/resources still work (use same services)
- [ ] Streaming endpoints support Range requests
- [ ] Thumbnail endpoints serve images directly
- [ ] All error handling bugs fixed
- [ ] Proper HTTP headers added

### Performance Requirements

- [ ] No performance regression
- [ ] Reduced request latency (remove indirection)
- [ ] Proper caching headers for cacheable resources

### Code Quality Requirements

- [ ] Service layer is testable independently
- [ ] HTTP API endpoints are testable independently
- [ ] MCP tools are thin protocol wrappers
- [ ] Clear separation of concerns
- [ ] No code duplication

---

## Open Questions (Detailed)

> **Note:** These questions are tracked in the "Open Questions" section at the top. Research answers should be documented in `docs/api-refactor-research.md`.

1. **Streaming Architecture:** Proxy vs redirect? (See Implementation Considerations)

2. **Image Optimization:** Should thumbnail endpoint support resizing/format conversion?

3. **Caching Strategy:** What caching headers should be used for each endpoint?

4. **Error Response Format:** Should HTTP API use different error format than MCP?

5. **Versioning:** Should HTTP API be versioned (`/api/v1/...`)?

6. **Rate Limiting:** Should rate limiting be added to HTTP API endpoints?

---

## References

- Current HTTP API implementation: `src/http_api.py`
- MCP tools: `src/tools/query_tools.py`
- MCP resources: `src/resources/audio_stream.py`, `src/resources/thumbnail.py`
- Download endpoint (good example): `src/http_api.py:333-640`

---

## Next Steps

1. **Review this document** - Validate findings and recommendations
2. **Decide on streaming architecture** - Proxy vs redirect
3. **Create service layer** - Extract business logic
4. **Refactor endpoints incrementally** - One endpoint at a time
5. **Test thoroughly** - Ensure no regressions
6. **Update documentation** - Reflect new architecture

---

**Document Status:** Ready for review and planning phase

