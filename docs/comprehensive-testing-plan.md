# Comprehensive Testing Plan - Loist Music Library MCP Server

**Date:** 2025-12-05
**Status:** Ready for Execution
**Goal:** Validate all API endpoints, MCP tools, and MCP Inspector functionality

---

## Executive Summary

This document outlines a comprehensive testing plan to validate the Loist Music Library MCP server's functionality. The plan covers:

1. **HTTP API Testing** - All REST endpoints via Postman
2. **MCP Inspector Setup** - UI-based MCP protocol testing
3. **MCP Tools Testing** - All 9 MCP tools validation
4. **MCP Resources Testing** - All 3 MCP resources validation
5. **Download Endpoint Verification** - Audio conversion and streaming
6. **Streaming Bug Fixes** - Range request support and error handling

---

## 1. HTTP API Testing with Postman

### Prerequisites

- **Postman** installed and configured
- **Docker Compose** running locally:
  ```bash
  docker-compose up -d
  ```
- **Postman Collection**: `loist-music-library-local.postman_collection.json`

### API Endpoints to Test

| Endpoint | Method | Status | Priority | Notes |
|----------|--------|--------|----------|-------|
| `/api/tracks/{audioId}` | GET | ⚠️ Wrapper | High | Returns MCP tool response, needs service layer refactor |
| `/api/search` | GET | ⚠️ Wrapper | High | Query parsing, pagination headers needed |
| `/api/tracks/{audioId}/stream` | GET | ⚠️ Bugs | High | **Critical bugs**: success field check, no Range support |
| `/api/tracks/{audioId}/thumbnail` | GET | ⚠️ Bugs | High | **Critical bugs**: success field check, no image serving |
| `/api/tracks/{audioId}/download` | GET | ✅ Good | Medium | Already proper implementation, verify conversion works |
| `/api/tracks/{audioId}` | DELETE | ⚠️ Wrapper | Medium | Thin wrapper around MCP tool |
| `/api/embed/{audioId}` | GET | Unknown | Low | OEmbed endpoint |
| `/oembed` | GET | Unknown | Low | OEmbed provider endpoint |

### Postman Test Strategy

#### Setup Environment
```json
{
  "base_url": "http://localhost:8080",
  "sessionId": "",
  "test_audio_id": "existing-track-id"
}
```

#### Test Categories

**1. Happy Path Tests**
- [ ] GET `/api/tracks/{audioId}` - Valid existing track
- [ ] GET `/api/search` - Valid search query
- [ ] GET `/api/tracks/{audioId}/stream` - Valid audio stream
- [ ] GET `/api/tracks/{audioId}/thumbnail` - Valid thumbnail
- [ ] GET `/api/tracks/{audioId}/download` - Valid download (verify format conversion)
- [ ] DELETE `/api/tracks/{audioId}` - Valid deletion

**2. Error Handling Tests**
- [ ] GET `/api/tracks/{nonexistent}` - 404 Not Found
- [ ] GET `/api/search?query=` - Empty query handling
- [ ] GET `/api/tracks/{invalid}/stream` - Invalid audio ID
- [ ] GET `/api/tracks/{invalid}/thumbnail` - Invalid audio ID
- [ ] DELETE `/api/tracks/{nonexistent}` - 404 Not Found

**3. Edge Cases**
- [ ] GET `/api/search` - Large result sets (pagination)
- [ ] GET `/api/search` - Special characters in query
- [ ] GET `/api/tracks/{audioId}/stream` - **Range header support** (bytes=0-1023)
- [ ] GET `/api/tracks/{audioId}/download` - Different formats (mp3, wav, flac)

**4. Performance Tests**
- [ ] Concurrent requests to streaming endpoints
- [ ] Large file downloads
- [ ] Search with complex filters

### Known Issues to Verify

#### Critical Bugs in Current Implementation

**Stream Endpoint Bug** (`/api/tracks/{audioId}/stream`):
```python
# BUG: Checks for 'success' field that doesn't exist in MCP resource response
if not result.get("success", False):  # ❌ This field doesn't exist!
```

**Thumbnail Endpoint Bug** (`/api/tracks/{audioId}/thumbnail`):
```python
# SAME BUG: Checks for 'success' field that doesn't exist
if not result.get("success", False):  # ❌ This field doesn't exist!
```

#### Missing HTTP Features

- [ ] **Range Request Support**: `Accept-Ranges: bytes` header missing
- [ ] **Content-Range**: For partial content responses
- [ ] **ETag/Cache-Control**: No caching headers
- [ ] **Content-Type**: Proper MIME types for audio/video

---

## 2. MCP Inspector Setup and Testing

### MCP Inspector Overview

The MCP Inspector is a **browser-based UI tool** for testing MCP (Model Context Protocol) servers. It provides a web interface to interact with MCP tools and resources, with configuration entirely through the browser UI.

### Setup Instructions

#### 1. Install MCP Inspector

**2025 Recommended Method**: No global installation needed - run on-demand via npx:

```bash
npx @modelcontextprotocol/inspector
```

**Prerequisites**: Node.js 18+

This launches a local web server (typically on `localhost:6274`) with a browser-based interface.

#### 2. Server Connection Configuration

In the Inspector's web UI connection panel, specify:

- **Transport**: Choose `HTTP streaming` (for your FastMCP server)
- **Server URL**: `http://localhost:8080/mcp`
- **Environment variables**: Add any needed env vars for your server

**Note**: Configuration is entirely UI-based and ephemeral - no config files needed for basic usage.

#### 3. Proxy Configuration (if needed)

For corporate environments with proxies:

- **Localhost bypass**: Most corporate proxies don't intercept `127.0.0.1` traffic
- **Header passthrough**: Ensure proxy forwards `Authorization`, `Content-Type` headers unchanged
- **Long-lived connections**: Proxy must support long-lived HTTP connections (no short idle timeouts)
- **Recommendation**: Use `127.0.0.1` addresses to avoid proxy issues entirely

#### 4. Start Local Server

```bash
# Ensure Docker Compose is running
docker-compose up -d

# Verify server health
curl http://localhost:8080/health/ready
```

#### 5. Launch MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Then open the provided localhost URL in your browser and configure the connection to your server.

### MCP Tools to Test

#### Core Tools (High Priority)

| Tool | Function | Test Cases |
|------|----------|------------|
| `health_check` | Server health status | ✅ Basic connectivity |
| `process_audio_complete` | Upload and process audio | 📁 File upload, metadata extraction |
| `get_audio_metadata` | Get track metadata | 🎵 Valid ID, invalid ID, error handling |
| `search_library` | Search audio tracks | 🔍 Text search, filters, pagination |
| `delete_audio` | Delete audio track | 🗑️ Valid deletion, invalid ID |

#### Management Tools (Medium Priority)

| Tool | Function | Test Cases |
|------|----------|------------|
| `update_metadata` | Update track metadata | ✏️ Partial updates, full updates, validation |
| `download_audio` | Download with conversion | ⬇️ Format conversion (mp3, wav, flac) |

#### Embed Tools (Low Priority)

| Tool | Function | Test Cases |
|------|----------|------------|
| `get_embed_url` | Generate embed URLs | 🔗 Different templates, devices |
| `list_embed_templates` | List available templates | 📋 Template enumeration |
| `check_waveform_availability` | Waveform status | 📊 Availability checking |

### MCP Resources to Test

#### Audio Resources

| Resource URI | Type | Test Cases |
|--------------|------|------------|
| `music-library://audio/{audio_id}/stream` | Audio Stream | ▶️ Stream access, format validation |
| `music-library://audio/{audio_id}/metadata` | Metadata | 📄 JSON metadata retrieval |
| `music-library://audio/{audio_id}/thumbnail` | Image | 🖼️ Thumbnail access, format validation |

### Inspector Testing Workflow

#### 1. Connection Test
- [ ] Connect to "loist-music-library" server
- [ ] Verify server handshake completes
- [ ] Check available tools/resources list

#### 2. Tool Execution Tests
- [ ] Execute each tool with valid parameters
- [ ] Test error handling with invalid parameters
- [ ] Verify response formats match schemas
- [ ] Test tool performance (response times)

#### 3. Resource Access Tests
- [ ] Access each resource URI
- [ ] Verify resource content types
- [ ] Test resource streaming (for audio streams)
- [ ] Validate resource metadata

#### 4. Integration Tests
- [ ] Upload audio → Get metadata → Search → Stream → Delete workflow
- [ ] Test concurrent tool execution
- [ ] Verify session management

---

## 2.5 Newman CLI vs Postman Desktop for HTTP API Testing

### Testing Tool Comparison

#### Postman Desktop (Primary Recommendation)
- ✅ **Interactive GUI** - Perfect for exploring and debugging API responses
- ✅ **Session Management** - Handles complex auth flows and cookie management
- ✅ **Visual Debugging** - Easy inspection of request/response cycles
- ✅ **Collection Runner** - Batch execution with visual results
- ⚠️ **Manual Process** - Requires manual execution and observation

#### Newman CLI (Automation & CI/CD)
- ✅ **Headless Execution** - `newman run collection.json --environment env.json`
- ✅ **CI/CD Integration** - Machine-friendly output formats (JSON, JUnit, HTML)
- ✅ **Exit Codes** - Pass/fail status for automated pipelines
- ✅ **HTTP/SSE Coverage** - Can test REST endpoints and simple streaming
- ⚠️ **Limited MCP Support** - Cannot drive full MCP protocol (stdio/SSE transports)
- ⚠️ **No Visual Debugging** - Harder to troubleshoot complex issues

### Recommended Testing Strategy

#### Phase 1: Interactive Testing (Postman Desktop)
Use Postman Desktop for initial API exploration and debugging:
- Manual endpoint testing
- Session management setup
- Error condition investigation
- Collection development and refinement

#### Phase 2: Automated Testing (Newman CLI)
Use Newman for regression testing and CI/CD:
```bash
# Run collection with environment
newman run loist-music-library-local.postman_collection.json \
  --environment postman-env-staging.json \
  --reporters json,html,junit \
  --reporter-json-export results.json

# Exit code indicates pass/fail
echo "Exit code: $?"
```

#### When to Use Each Tool

**Use Postman Desktop when:**
- First-time API exploration
- Debugging complex request/response cycles
- Setting up authentication and sessions
- Inspecting large or complex responses

**Use Newman CLI when:**
- Running automated regression tests
- CI/CD pipeline integration
- Performance benchmarking
- Generating test reports

---

## 3. Download Endpoint Deep Testing

### Current Implementation Status

The download endpoint (`GET /api/tracks/{audioId}/download`) is already properly implemented with:
- Direct GCS access (no MCP wrapper)
- Audio format conversion (ffmpeg)
- Proper HTTP streaming
- Error handling and cleanup

### Test Scenarios

#### Format Conversion Tests
- [ ] **MP3 Download**: `?format=mp3&preset=high` (320kbps)
- [ ] **WAV Download**: `?format=wav` (uncompressed)
- [ ] **FLAC Download**: `?format=flac` (lossless)
- [ ] **AAC Download**: `?format=aac` (128kbps)
- [ ] **OGG Download**: `?format=ogg` (Vorbis)

#### Parameter Validation
- [ ] Invalid format parameter
- [ ] Invalid preset parameter
- [ ] Unsupported audio ID
- [ ] Missing format parameter (default behavior)

#### Error Handling
- [ ] GCS access failures
- [ ] FFmpeg conversion errors (timeouts, resource limits)
- [ ] Invalid source audio format
- [ ] Temporary file cleanup on errors
- [ ] Process termination on timeouts

---

## 4. Streaming Endpoints Bug Fixes

### Current Critical Issues

#### Range Request Support Missing
- **Problem**: Endpoints return JSON URLs instead of streaming audio directly
- **Impact**: Clients must make 2 requests (get URL, then stream)
- **Solution**: Implement proper HTTP Range request support

#### Error Handling Bugs
- **Problem**: Code checks for `result.get("success", False)` but MCP resources don't return this field
- **Impact**: Error handling never executes correctly
- **Solution**: Fix field checks to match actual MCP resource response format

### Required Fixes

#### For `/api/tracks/{audioId}/stream` (HTTP Range Request Implementation):

1. **Fix Error Handling**: Remove incorrect `result.get("success", False)` check - MCP resources don't return this field

2. **Implement Standards-Compliant Range Requests**:
   ```python
   # Accept Range: bytes=start-end header
   # Return 206 Partial Content with:
   # Content-Range: bytes start-end/total-size
   # Accept-Ranges: bytes (on all responses)
   ```

3. **GCS Byte-Range Reads**: Use GCS client APIs or signed URLs with Range header passthrough to fetch only requested slices

4. **Streaming Response**: Pass GCS stream directly to HTTP response (no full buffering)

5. **Performance**: Choose 256-1024 KiB chunk sizes, ensure CORS exposes Content-Range

#### For `/api/tracks/{audioId}/thumbnail`:
1. Fix error handling to check correct fields
2. Serve images directly instead of returning JSON URLs
3. Add proper image headers (`Content-Type`, `Cache-Control`)
4. Consider image optimization (resize, format conversion)

---

## 5. Testing Environment Setup

### Local Development Environment

```bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check health endpoints
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/database

# View logs if needed
docker-compose logs -f mcp-server
```

### Test Data Setup

#### Upload Test Audio
Use the `process_audio_complete` MCP tool or HTTP endpoint to upload test audio files.

#### Required Test Files
- [ ] MP3 audio file (various bitrates)
- [ ] WAV audio file (uncompressed)
- [ ] FLAC audio file (lossless)
- [ ] Audio with metadata (ID3 tags, album art)

---

## 6. Success Criteria

### HTTP API Testing
- [ ] All endpoints return correct HTTP status codes
- [ ] Error responses include proper error messages
- [ ] Streaming endpoints support Range requests
- [ ] Download endpoint successfully converts audio formats
- [ ] All endpoints include appropriate HTTP headers

### MCP Inspector Testing
- [ ] All 9 MCP tools execute successfully
- [ ] All 3 MCP resources are accessible
- [ ] Error handling works for invalid inputs
- [ ] Response formats match documented schemas

### Performance Requirements

#### API Response Times (Realistic 2025 Targets)
- [ ] **Metadata Operations**: p50 < 50-100ms, p95 < 200-300ms (local/nearby DB)
- [ ] **GCS-Involved Operations**: p95 < 200-600ms (signed URL generation, audio probing)
- [ ] **Search Queries**: p50 < tens of milliseconds with proper GIN indexes
- [ ] **Streaming Startup**: First playable byte < 500-800ms in typical conditions

#### Search Performance
- [ ] Result ranking and pagination keeps response sizes manageable
- [ ] Heavy queries ("common terms") use limits to prevent large result sets

#### Streaming Performance
- [ ] Initial Range response headers within 100-300ms
- [ ] Chunked reads (256-1024 KiB) balance seek latency and network overhead
- [ ] Memory-efficient streaming (no full file buffering)

### Bug Fixes Verified
- [ ] Stream endpoint error handling fixed
- [ ] Thumbnail endpoint error handling fixed
- [ ] Range request support implemented
- [ ] Image serving works correctly

---

## 7. Test Execution Order

### Phase 1: Environment Setup (30 minutes)
1. Start Docker Compose environment
2. Verify server health and connectivity
3. Upload test audio files
4. Set up Postman environment

### Phase 2: HTTP API Testing (2 hours)
1. Test all endpoints with Postman collection
2. Verify download functionality
3. Document any issues found
4. Test edge cases and error conditions

### Phase 3: MCP Inspector Setup (30 minutes)
1. Install and configure MCP Inspector
2. Connect to local server
3. Verify tool and resource discovery

### Phase 4: MCP Tools Testing (1 hour)
1. Test each MCP tool individually
2. Test tool parameter validation
3. Test error handling scenarios
4. Document response formats

### Phase 5: MCP Resources Testing (30 minutes)
1. Test each MCP resource access
2. Verify resource content types
3. Test streaming resources

### Phase 6: Integration Testing (1 hour)
1. Test complete workflows (upload → metadata → search → stream → delete)
2. Test concurrent operations
3. Performance validation
4. Bug fix verification

---

## 8. Documentation Updates

After testing completion, update the following documentation:

- [ ] `docs/api-endpoint-refactoring.md` - Mark completed fixes
- [ ] `docs/mcp-testing-guide.md` - Add Inspector testing procedures
- [ ] `docs/download-endpoint-api.md` - Document verified functionality
- [ ] `docs/mcp-inspector-setup.md` - Update setup instructions if needed
- [ ] Postman collection - Update with any new test cases

---

## 9. Risk Assessment

### High Risk Items
- **Streaming endpoint bugs**: May cause silent failures in production (fixed MCP error checking)
- **HTTP Range request implementation**: Complex GCS byte-range reads required
- **Corporate proxy issues**: MCP Inspector may fail through corporate proxies

### Mitigation Strategies
- **Localhost Development**: Use `127.0.0.1` to bypass corporate proxy issues
- **GCS Byte-Range Testing**: Implement and test Range requests thoroughly
- **Fallback Testing**: Use direct HTTP API testing if MCP Inspector fails

---

## 10. Next Steps

1. **Execute Phase 1**: Set up testing environment
2. **Execute Phase 2**: Run Postman API tests
3. **Execute Phase 3-5**: Test MCP functionality
4. **Fix Critical Bugs**: Address streaming endpoint issues
5. **Update Documentation**: Reflect testing results
6. **Prepare for Production**: Validate deployment readiness

---

**Document Status:** Ready for execution
**Estimated Time:** 6-8 hours total
**Dependencies:** Docker Compose, Postman, MCP Inspector
