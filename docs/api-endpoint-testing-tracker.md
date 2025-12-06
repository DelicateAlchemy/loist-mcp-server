# API Endpoint Testing Tracker - CLI-Friendly Testing Plan

> **Agent Instructions**: This file is your project management brain for API endpoint testing. Read it at session start, update checkboxes as you complete tasks, and maintain the rolling summary. Execute tasks ONE AT A TIME in order.

> **CLI Agent Note**: This document includes `curl` commands for all tests. CLI agents should use curl commands directly. Postman GUI references are optional for manual testing.

> **For CLI Agents with Limited Context**: If context window is limited, start with **Phase 1** and **Phase 2** only. Request subsequent phases (3-6) as needed. Each phase is designed to be independently executable.

---

## 🤖 Agent Rules (MUST FOLLOW)

### CLI Agent Limitations & Workarounds

**⚠️ Important for CLI Agents**:
- **Postman GUI**: CLI agents cannot interact with Postman GUI. Use alternatives:
  - **Option 1**: Use `curl` commands (provided for each test)
  - **Option 2**: Use Newman CLI (`newman run collection.json`)
  - **Option 3**: Generate curl commands, user executes manually
- **File Updates**: If agent cannot write files, report completion status in chat. User updates tracker file.
- **Interactive Commands**: Some commands require manual execution (e.g., database queries). Agent provides exact commands.
- **Shell State**: Commands that chain variables (e.g., `SIGNED_URL=$(...)`) assume shell state persistence. If not available, use single-line commands or provide variable values explicitly.
- **jq Dependency**: Commands using `jq` require it installed. Fallback: Use `python -m json.tool` or `cat` for raw JSON.
- **Command Chaining**: For tests requiring variable capture, either:
  - Chain commands in single execution: `SIGNED_URL=$(curl ...) && curl -H "Range: bytes=0-1023" "${SIGNED_URL}"`
  - Or provide variable value explicitly in follow-up commands

### Session Start Protocol
1. Read this entire file to restore context (or current phase section)
2. Check `## Rolling Summary` for completed work
3. Find the next unchecked task (`- [STATUS: pending]`)
4. State your intent before starting work

### Task Execution Protocol
```
🎯 Intent: I'm going to [action] because [reason].
   Files affected: [list]
   Expected outcome: [outcome]
   CLI command: [curl/newman/docker command]
```

### After Each Task
1. **If file write access**: Mark task complete: `- [STATUS: pending]` → `- [STATUS: done]`
2. **If no file write access**: Report completion status in chat with task ID
3. Update `## Rolling Summary` (or report in chat)
4. If task created follow-up work, add to `## Discovered Tasks` (or report in chat)
5. Document test results in `## Test Results` section (or report in chat)

### Critical Rules
- **ONE task at a time** - never batch multiple tasks
- **Verify before marking done** - actually run the tests (curl or Newman)
- **Report status** - update tracker file OR report completion in chat
- **Docker only** - use `docker-compose up -d` for local testing
- **Test with real data** - use actual audio IDs from your database
- **Use curl for CLI** - all Postman tests have curl equivalents

---

## 📋 Project Overview

**Project**: Loist Music Library MCP Server - API Endpoint Testing
**Source**: Comprehensive Testing Plan (2025-12-05)
**Goal**: Validate all HTTP REST API endpoints via CLI testing (curl/Newman)
**Focus**: CLI-friendly testing (curl commands provided, Postman GUI optional)

### Endpoint Status Summary

| Endpoint | Method | Current Status | Priority | Notes |
|----------|--------|----------------|----------|-------|
| `/api/tracks/{audioId}` | GET | ✅ Service Layer | High | Uses `audio_service`, verify response format |
| `/api/search` | GET | ✅ Service Layer | High | Uses `audio_service`, verify pagination headers |
| `/api/tracks/{audioId}/stream` | GET | ✅ Redirect | High | Redirects to signed URL (correct approach), verify Range support works |
| `/api/tracks/{audioId}/thumbnail` | GET | ✅ Redirect | High | Redirects to signed URL (correct approach), verify image serving works |
| `/api/tracks/{audioId}/download` | GET | ✅ Good | Medium | Proper implementation, verify conversion |
| `/api/tracks/{audioId}` | DELETE | ✅ Service Layer | Medium | Uses `audio_service`, verify 204 response |
| `/api/embed/{audioId}` | GET | Unknown | Low | OEmbed endpoint, verify exists |
| `/oembed` | GET | ✅ Implemented | Low | OEmbed provider endpoint |

### Current Implementation Notes

**Service Layer Endpoints** (Already Refactored):
- `GET /api/tracks/{audioId}` - Uses `audio_service.get_audio_metadata()`
- `GET /api/search` - Uses `audio_service.search_audio_library()`
- `DELETE /api/tracks/{audioId}` - Uses `audio_service.delete_audio_track_and_files()`

**Redirect Endpoints** (Correct Implementation - Verify Behavior):
- `GET /api/tracks/{audioId}/stream` - Uses `streaming_service.get_audio_stream_details()`, returns 302 redirect to signed GCS URL
- `GET /api/tracks/{audioId}/thumbnail` - Uses `streaming_service.get_thumbnail_details()`, returns 302 redirect to signed GCS URL

**Implementation Assessment**:
- ✅ **Redirect approach is correct** for static assets (audio files, pre-generated thumbnails)
- ✅ **No proxy streaming needed** unless adding transformations or analytics
- ✅ **GCS handles Range requests natively** - clients send Range headers to redirected URL, GCS responds with 206 Partial Content
- ✅ **No bugs found** - code review shows endpoints use service layer correctly, no `success` field checks

**Research Finding**: GCS signed URLs natively support HTTP Range requests. Current redirect implementation is correct - clients send Range headers to redirected GCS URL, GCS handles Range requests automatically. No proxy streaming needed for static assets.

---

## 🚀 Phase 1: Environment Setup & Preparation [HIGH PRIORITY]

### P1.1 Environment Setup & Configuration
- [STATUS: pending] **P1.1.1** Verify Docker Compose is running:
  ```bash
  docker-compose up -d
  docker-compose ps  # Verify containers are running
  ```
- [STATUS: pending] **P1.1.2** Verify server health:
  ```bash
  curl http://localhost:8080/health/ready
  curl http://localhost:8080/health/database
  ```
- [STATUS: done] **P1.1.3** Set up testing approach:
  - **Option A (CLI)**: Use curl commands provided in each test
  - **Option B (Newman)**: Use `newman run loist-music-library-local.postman_collection.json --environment postman-env-local.json`
  - **Option C (Manual)**: Use Postman GUI (agent generates curl commands for you)
- [STATUS: done] **P1.1.4** Set environment variables (export for curl, or create Postman/Newman env file):
  ```bash
  export BASE_URL="http://localhost:8080"
  export AUDIO_ID="<get-from-db>"  # See P1.1.5
  export AUDIO_SOURCE_URL="<fresh-url-expires-1hr>"  # See Environment Variables section
  ```
  - ✅ Created `postman-env-local.json` with all required variables
  - ✅ Newman installed globally for automated testing
- [STATUS: pending] **P1.1.5** Get real test audio ID from database:
  ```bash
  # CLI command (requires manual execution or script)
  # Use -t flag for tuples-only output (cleaner for parsing)
  docker-compose exec postgres psql -t -U loist_user -d loist_mvp -c "SELECT id FROM audio_tracks LIMIT 1;" | tr -d ' '
  # Or use existing audio_id from environment if available
  # Example output: ca3f7741-3d32-445f-b837-f1ea92a79ac4
  ```
- [STATUS: pending] **P1.1.6** Get audio ID with thumbnail (for thumbnail endpoint tests):
  ```bash
  # Use -t flag for tuples-only output
  docker-compose exec postgres psql -t -U loist_user -d loist_mvp -c "SELECT id FROM audio_tracks WHERE thumbnail_gcs_path IS NOT NULL LIMIT 1;" | tr -d ' '
  ```

### P1.2 Test Data Preparation
- [STATUS: pending] **P1.2.1** Document test audio IDs with different characteristics:
  - Audio ID with thumbnail
  - Audio ID without thumbnail
  - Audio ID for format conversion testing
- [STATUS: pending] **P1.2.2** Verify test audio files exist in GCS (for streaming/download tests)
- [STATUS: pending] **P1.2.3** Create test search queries for different scenarios:
  - Simple text query
  - Query with special characters
  - Query with filters (genre, year)
- [STATUS: pending] **P1.2.4** Set up `audio_source_url` for audio processing tests:
  - **Critical**: `audio_source_url` expires after 1 hour
  - **Action**: Get fresh URL before starting testing session
  - **Postman**: Update environment variable with new URL if tests fail with expired URL error
  - **Note**: Collection includes validation warning if URL is example/default value

---

## 🧪 Phase 2: High Priority Endpoint Testing [HIGH PRIORITY]

### P2.1 GET `/api/tracks/{audioId}` - Metadata Endpoint

#### Happy Path Tests
- [STATUS: pending] **P2.1.1** Test GET `/api/tracks/{valid-audio-id}` with valid UUID
  - **CLI Command**:
    ```bash
    curl -v -H "Accept: application/json" \
      "http://localhost:8080/api/tracks/${AUDIO_ID}" \
      -o response.json
    ```
  - **Expected**: 200 OK with JSON response
  - **Verify**: Response contains `success: true`, `audio_id`, `metadata` object, `resources` object
  - **Verify**: Response includes ETag header (`grep -i etag` or check headers)
  - **Verify**: Response includes Cache-Control header
  - **Postman**: Use "Get Track Metadata" request in "Custom Routes" folder
- [STATUS: pending] **P2.1.2** Test conditional request with If-None-Match header
  - **CLI Command**:
    ```bash
    # First request to get ETag
    ETAG=$(curl -sI "http://localhost:8080/api/tracks/${AUDIO_ID}" | grep -i etag | cut -d'"' -f2)
    # Second request with If-None-Match
    curl -v -H "If-None-Match: \"${ETAG}\"" \
      "http://localhost:8080/api/tracks/${AUDIO_ID}"
    ```
  - **Expected**: 304 Not Modified when ETag matches
  - **Verify**: Response body is empty (status code 304)
  - **Postman**: Use "Get Track Metadata" request, add If-None-Match header manually

#### Error Handling Tests
- [STATUS: pending] **P2.1.3** Test GET `/api/tracks/{invalid-uuid}` with invalid UUID format
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/tracks/invalid-uuid-format"
    ```
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains `success: false` and error message
  - **Postman**: Use "Get Track Metadata" request, change audio_id to "invalid"
- [STATUS: pending] **P2.1.4** Test GET `/api/tracks/{nonexistent-uuid}` with valid UUID format but non-existent ID
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/tracks/00000000-0000-0000-0000-000000000000"
    ```
  - **Expected**: 404 Not Found
  - **Verify**: Response contains `success: false` and "not found" message
  - **Postman**: Use "Get Track Metadata" request with non-existent UUID

#### Response Format Validation
- [STATUS: pending] **P2.1.5** Verify metadata object structure matches expected schema:
  - `metadata.title`, `metadata.artist`, `metadata.album`, `metadata.genre`, `metadata.year`
  - `metadata.duration_seconds`, `metadata.format`
- [STATUS: pending] **P2.1.6** Verify resources object structure:
  - `resources.stream_url` (if available)
  - `resources.thumbnail_url` (if available)

### P2.2 GET `/api/search` - Search Endpoint

#### Happy Path Tests
- [STATUS: pending] **P2.2.1** Test GET `/api/search?q=rock` with simple query
  - **CLI Command**:
    ```bash
    # With jq (if installed)
    curl -v "http://localhost:8080/api/search?q=rock" | jq .
    # Fallback without jq
    curl -v "http://localhost:8080/api/search?q=rock" | python -m json.tool
    # Or raw output
    curl -v "http://localhost:8080/api/search?q=rock"
    ```
  - **Expected**: 200 OK with JSON response
  - **Verify**: Response contains `success: true`, `results` array, `total` count
  - **Verify**: Response includes `X-Total-Count` header (`curl -I` to check headers)
  - **Verify**: Response includes `Link` header for pagination (if applicable)
  - **Postman**: Use "Search Tracks" request in "Custom Routes" folder
- [STATUS: pending] **P2.2.2** Test search with pagination: `GET /api/search?q=rock&limit=10&offset=0`
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/search?q=rock&limit=10&offset=0" | jq .
    ```
  - **Expected**: 200 OK with 10 results (or fewer)
  - **Verify**: `limit` and `offset` parameters work correctly
  - **Verify**: `has_more` field indicates if more results available
  - **Postman**: Modify "Search Tracks" request query parameters
- [STATUS: pending] **P2.2.3** Test search with genre filter: `GET /api/search?q=rock&genre=Rock`
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/search?q=rock&genre=Rock" | jq .
    ```
  - **Expected**: 200 OK with filtered results
  - **Verify**: Results match genre filter
  - **Postman**: Add `genre=Rock` query parameter to "Search Tracks" request

#### Error Handling Tests
- [STATUS: pending] **P2.2.4** Test GET `/api/search` without `q` parameter
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/search"
    ```
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains `success: false` and "query required" message
  - **Postman**: Use "Search Tracks" request without `q` parameter
- [STATUS: pending] **P2.2.5** Test GET `/api/search?q=` with empty query
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/search?q="
    ```
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains `success: false` and error message
  - **Postman**: Use "Search Tracks" request with empty `q` value
- [STATUS: pending] **P2.2.6** Test search with invalid limit/offset: `GET /api/search?q=rock&limit=-1`
  - **CLI Command**:
    ```bash
    curl -v "http://localhost:8080/api/search?q=rock&limit=-1"
    ```
  - **Expected**: 400 Bad Request or corrected to valid range
  - **Verify**: Invalid parameters are handled gracefully
  - **Postman**: Use "Search Tracks" request with invalid limit value

#### Edge Cases
- [STATUS: pending] **P2.2.7** Test search with special characters: `GET /api/search?q=rock&roll`
  - **Expected**: 200 OK with results (if any)
  - **Verify**: Special characters are handled correctly
- [STATUS: pending] **P2.2.8** Test search with very large result set: `GET /api/search?q=common-term&limit=100`
  - **Expected**: 200 OK with pagination
  - **Verify**: Pagination headers indicate more results available

### P2.3 GET `/api/tracks/{audioId}/stream` - Streaming Endpoint

#### Current Implementation Verification
- [STATUS: pending] **P2.3.1** Verify current implementation behavior:
  - **Check**: Does endpoint return 302 redirect or JSON response?
  - **Check**: Does endpoint check for `success` field (bug mentioned in plan)?
  - **Check**: What headers are included in response?
- [STATUS: pending] **P2.3.2** Review `src/http_api.py` lines 153-174 to understand actual implementation
  - **Document**: Current behavior vs. documented bugs

#### Happy Path Tests
- [STATUS: pending] **P2.3.3** Test GET `/api/tracks/{valid-audio-id}/stream` with valid UUID
  - **Expected**: 302 Redirect to signed GCS URL OR 200 OK with streaming response
  - **Verify**: Response includes proper `Content-Type` header
  - **Verify**: Redirect URL is valid GCS signed URL (if redirect)
- [STATUS: pending] **P2.3.4** Follow redirect and verify audio stream is accessible
  - **Expected**: Audio file can be streamed/downloaded
  - **Verify**: Content-Type matches audio format

#### Error Handling Tests
- [STATUS: pending] **P2.3.5** Test GET `/api/tracks/{invalid-uuid}/stream` with invalid UUID
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains error message
- [STATUS: pending] **P2.3.6** Test GET `/api/tracks/{nonexistent-uuid}/stream` with non-existent ID
  - **Expected**: 404 Not Found
  - **Verify**: Response contains "not found" message

#### Range Request Support (Critical)
- [STATUS: pending] **P2.3.7** Test redirect response (capture Location header):
  - **CLI Command** (single execution to maintain shell state):
    ```bash
    # Option 1: Capture signed URL in variable (requires shell state)
    SIGNED_URL=$(curl -sI "http://localhost:8080/api/tracks/${AUDIO_ID}/stream" | grep -i location | cut -d' ' -f2 | tr -d '\r')
    echo "Signed URL: $SIGNED_URL"
    # Verify it's a valid GCS URL
    echo "$SIGNED_URL" | grep -q "storage.googleapis.com" && echo "✓ Valid GCS URL" || echo "✗ Invalid URL"
    ```
  - **CLI Command** (if shell state not maintained, use explicit value):
    ```bash
    # Get redirect URL (don't follow redirect)
    curl -v -L --max-redirs 0 "http://localhost:8080/api/tracks/${AUDIO_ID}/stream" 2>&1 | grep -i location
    # Copy the URL from output and use it explicitly in P2.3.8
    ```
  - **Expected**: 302 Found redirect response
  - **Verify**: Response includes `Location` header with signed GCS URL
  - **Verify**: Status code is 302
  - **Note**: Save `SIGNED_URL` variable for next test
  - **Postman**: Disable "Follow redirects", check Location header
- [STATUS: pending] **P2.3.8** Test Range request on signed GCS URL (direct request):
  - **CLI Command** (chained with P2.3.7 if shell state maintained):
    ```bash
    # Chain with P2.3.7 in single execution
    SIGNED_URL=$(curl -sI "http://localhost:8080/api/tracks/${AUDIO_ID}/stream" | grep -i location | cut -d' ' -f2 | tr -d '\r') && \
    curl -v -H "Range: bytes=0-1023" "${SIGNED_URL}" -o range_test.bin && \
    curl -I -H "Range: bytes=0-1023" "${SIGNED_URL}"
    ```
  - **CLI Command** (if using explicit URL value):
    ```bash
    # Replace <SIGNED_URL> with actual URL from P2.3.7 output
    curl -v -H "Range: bytes=0-1023" "<SIGNED_URL>" -o range_test.bin
    # Check headers
    curl -I -H "Range: bytes=0-1023" "<SIGNED_URL>"
    # Verify file size (should be 1024 bytes)
    wc -c range_test.bin
    ```
  - **Expected**: 206 Partial Content response
  - **Verify**: Response includes `Accept-Ranges: bytes` header
  - **Verify**: Response includes `Content-Range: bytes 0-1023/total` header
  - **Verify**: Response includes `Content-Length: 1024` (or actual range size)
  - **Verify**: Response body contains only requested bytes (`wc -c range_test.bin` should show 1024)
  - **Postman**: Create new request to signed URL, add Range header
- [STATUS: pending] **P2.3.9** Test multiple Range requests (verify seeking works):
  - **CLI Command** (chained with P2.3.7):
    ```bash
    # Get signed URL and test multiple ranges in one execution
    SIGNED_URL=$(curl -sI "http://localhost:8080/api/tracks/${AUDIO_ID}/stream" | grep -i location | cut -d' ' -f2 | tr -d '\r') && \
    curl -H "Range: bytes=0-1023" "${SIGNED_URL}" -o range1.bin && \
    curl -H "Range: bytes=2048-4095" "${SIGNED_URL}" -o range2.bin && \
    diff range1.bin range2.bin && echo "✓ Ranges differ (expected)" || echo "✗ Ranges are identical (unexpected)"
    ```
  - **CLI Command** (if using explicit URL):
    ```bash
    # Replace <SIGNED_URL> with actual URL
    curl -H "Range: bytes=0-1023" "<SIGNED_URL>" -o range1.bin
    curl -H "Range: bytes=2048-4095" "<SIGNED_URL>" -o range2.bin
    diff range1.bin range2.bin  # Should differ (exit code 1 is expected)
    ```
  - **Expected**: Both return 206 Partial Content with correct ranges
  - **Verify**: Different byte ranges work independently
  - **Postman**: Create multiple requests with different Range headers
- [STATUS: pending] **P2.3.10** Test invalid Range request (negative test):
  - **CLI Command** (chained):
    ```bash
    # Get signed URL and test invalid range
    SIGNED_URL=$(curl -sI "http://localhost:8080/api/tracks/${AUDIO_ID}/stream" | grep -i location | cut -d' ' -f2 | tr -d '\r') && \
    curl -v -H "Range: bytes=999999999-" "${SIGNED_URL}"
    ```
  - **CLI Command** (explicit URL):
    ```bash
    # Replace <SIGNED_URL> with actual URL
    curl -v -H "Range: bytes=999999999-" "<SIGNED_URL>"
    ```
  - **Expected**: 416 Range Not Satisfiable
  - **Verify**: Response includes `Content-Range: bytes */total` header
  - **Verify**: Error response is spec-compliant
  - **Postman**: Create request with invalid Range header

#### Response Headers Verification
- [STATUS: pending] **P2.3.11** Verify redirect response headers (from P2.3.7):
  - **Verify**: `Location` header contains valid signed GCS URL
  - **Verify**: URL format matches GCS signed URL pattern
  - **Note**: Redirect response doesn't include Range headers (content not in redirect)
- [STATUS: pending] **P2.3.12** Verify GCS response headers (from P2.3.8):
  - **Verify**: `Accept-Ranges: bytes` header present
  - **Verify**: `ETag` header present (for caching)
  - **Verify**: `Content-Type` header matches actual audio format (e.g., `audio/mpeg`)
  - **Verify**: `Content-Length` header present (matches range size)

### P2.4 GET `/api/tracks/{audioId}/thumbnail` - Thumbnail Endpoint

#### Current Implementation Verification
- [STATUS: pending] **P2.4.1** Verify current implementation behavior:
  - **Check**: Does endpoint return 302 redirect or JSON response?
  - **Check**: Does endpoint check for `success` field (bug mentioned in plan)?
  - **Check**: What headers are included in response?
- [STATUS: pending] **P2.4.2** Review `src/http_api.py` lines 177-196 to understand actual implementation
  - **Document**: Current behavior vs. documented bugs

#### Happy Path Tests
- [STATUS: pending] **P2.4.3** Test GET `/api/tracks/{valid-audio-id}/thumbnail` with valid UUID that has thumbnail
  - **Expected**: 302 Redirect to signed GCS URL OR 200 OK with image response
  - **Verify**: Response includes proper `Content-Type: image/jpeg` header
  - **Verify**: Redirect URL is valid GCS signed URL (if redirect)
- [STATUS: pending] **P2.4.4** Follow redirect and verify image is accessible
  - **Expected**: Image can be displayed/downloaded
  - **Verify**: Image format is correct (JPEG/PNG)

#### Error Handling Tests
- [STATUS: pending] **P2.4.5** Test GET `/api/tracks/{invalid-uuid}/thumbnail` with invalid UUID
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains error message
- [STATUS: pending] **P2.4.6** Test GET `/api/tracks/{nonexistent-uuid}/thumbnail` with non-existent ID
  - **Expected**: 404 Not Found
  - **Verify**: Response contains "not found" message
- [STATUS: pending] **P2.4.7** Test GET `/api/tracks/{audio-id-without-thumbnail}/thumbnail` with valid ID but no thumbnail
  - **Expected**: 404 Not Found OR 200 OK with `success: false`
  - **Verify**: Error handling is consistent

#### Image Serving Verification
- [STATUS: pending] **P2.4.8** Verify redirect flow works correctly:
  - **Expected**: 302 Redirect to signed GCS URL (not JSON response)
  - **Verify**: Client follows redirect automatically
  - **Verify**: Image data is accessible after redirect
  - **Note**: Redirect approach is correct for static thumbnails
- [STATUS: pending] **P2.4.9** Verify GCS response (after redirect) includes proper headers:
  - **Verify**: `Content-Type: image/jpeg` (or appropriate format) header present
  - **Verify**: `ETag` header present (for caching)
  - **Verify**: `Cache-Control` header present (if set on GCS object)
  - **Note**: GCS handles image headers automatically
- [STATUS: pending] **P2.4.10** Verify image displays correctly in browser/application
  - **Expected**: Image loads and displays properly
  - **Verify**: No CORS issues with redirected image URL

---

## 🧪 Phase 3: Medium Priority Endpoint Testing [MEDIUM PRIORITY]

### P3.1 GET `/api/tracks/{audioId}/download` - Download Endpoint

#### Happy Path Tests
- [STATUS: pending] **P3.1.1** Test GET `/api/tracks/{valid-audio-id}/download?format=mp3` with MP3 format
  - **Expected**: 200 OK with audio file stream OR 302 redirect
  - **Verify**: File is downloadable
  - **Verify**: Format conversion works correctly
- [STATUS: pending] **P3.1.2** Test download with high quality preset: `?format=mp3&preset=high`
  - **Expected**: 200 OK with high-quality audio
  - **Verify**: File quality matches preset
- [STATUS: pending] **P3.1.3** Test download with different formats:
  - `format=wav` - Uncompressed WAV
  - `format=flac` - Lossless FLAC
  - `format=aac` - AAC format
  - **Verify**: Each format conversion works

#### Error Handling Tests
- [STATUS: pending] **P3.1.4** Test GET `/api/tracks/{valid-audio-id}/download` without format parameter
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains "format required" message
- [STATUS: pending] **P3.1.5** Test download with invalid format: `?format=invalid`
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains "unsupported format" message
- [STATUS: pending] **P3.1.6** Test download with invalid preset: `?format=mp3&preset=invalid`
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains error message
- [STATUS: pending] **P3.1.7** Test download with non-existent audio ID
  - **Expected**: 404 Not Found
  - **Verify**: Response contains "not found" message

#### Response Headers Verification
- [STATUS: pending] **P3.1.8** Verify download response includes proper headers:
  - `Content-Disposition: attachment; filename="..."`
  - `Content-Type: audio/mpeg` (or appropriate format)
  - `Content-Length: <file-size>`
  - `X-Conversion-Time: <seconds>` (if conversion occurred)

### P3.2 DELETE `/api/tracks/{audioId}` - Delete Endpoint

#### Happy Path Tests
- [STATUS: pending] **P3.2.1** Test DELETE `/api/tracks/{valid-audio-id}` with valid UUID
  - **Expected**: 204 No Content
  - **Verify**: Response body is empty
  - **Verify**: Audio track is deleted from database
  - **Verify**: Audio file is deleted from GCS (if applicable)
- [STATUS: pending] **P3.2.2** Verify track is actually deleted by attempting GET after DELETE
  - **Expected**: GET returns 404 Not Found
  - **Verify**: Deletion was successful

#### Error Handling Tests
- [STATUS: pending] **P3.2.3** Test DELETE `/api/tracks/{invalid-uuid}` with invalid UUID format
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains error message
- [STATUS: pending] **P3.2.4** Test DELETE `/api/tracks/{nonexistent-uuid}` with non-existent ID
  - **Expected**: 404 Not Found
  - **Verify**: Response contains "not found" message

---

## 🧪 Phase 4: Low Priority Endpoint Testing [LOW PRIORITY]

### P4.1 GET `/api/embed/{audioId}` - Embed Endpoint

#### Endpoint Discovery
- [STATUS: pending] **P4.1.1** Verify endpoint exists: `GET /api/embed/{audio-id}`
  - **Check**: Does this endpoint exist in `src/http_api.py` or `src/server.py`?
  - **Check**: What is the actual route path?
- [STATUS: pending] **P4.1.2** Test GET `/api/embed/{valid-audio-id}` if endpoint exists
  - **Expected**: 200 OK with embed data
  - **Verify**: Response format matches expected schema

### P4.2 GET `/oembed` - OEmbed Provider Endpoint

#### Happy Path Tests
- [STATUS: pending] **P4.2.1** Test GET `/oembed?url=https://loist.io/embed/{audio-id}` with valid embed URL
  - **Expected**: 200 OK with oEmbed JSON response
  - **Verify**: Response includes `version`, `type`, `provider_name`, `html` fields
  - **Verify**: Response includes `title`, `author_name` fields
- [STATUS: pending] **P4.2.2** Test oEmbed with maxwidth/maxheight parameters
  - **Expected**: Dimensions are respected in iframe HTML
  - **Verify**: `width` and `height` fields match parameters

#### Error Handling Tests
- [STATUS: pending] **P4.2.3** Test GET `/oembed` without url parameter
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains error message
- [STATUS: pending] **P4.2.4** Test oEmbed with invalid URL format
  - **Expected**: 400 Bad Request
  - **Verify**: Response contains "invalid URL" message
- [STATUS: pending] **P4.2.5** Test oEmbed with non-existent audio ID in URL
  - **Expected**: 404 Not Found
  - **Verify**: Response contains "not found" message

#### Discovery Endpoint
- [STATUS: pending] **P4.2.6** Test GET `/.well-known/oembed.json` discovery endpoint
  - **Expected**: 200 OK with provider information
  - **Verify**: Response includes `endpoints` array with oEmbed URL

---

## 📊 Phase 5: Performance & Edge Case Testing [MEDIUM PRIORITY]

### P5.1 Performance Tests
- [STATUS: pending] **P5.1.1** Test concurrent requests to streaming endpoint (5+ simultaneous requests)
  - **Expected**: All requests complete successfully
  - **Verify**: No errors or timeouts
  - **Verify**: Response times are reasonable
- [STATUS: pending] **P5.1.2** Test large file download performance
  - **Expected**: Download completes without timeout
  - **Verify**: Streaming works for large files
- [STATUS: pending] **P5.1.3** Test search with complex filters and large result sets
  - **Expected**: Response time is acceptable (< 2 seconds)
  - **Verify**: Pagination works correctly

### P5.2 Edge Cases
- [STATUS: pending] **P5.2.1** Test search with very long query strings
  - **Expected**: Handled gracefully (400 or truncated)
  - **Verify**: No server errors
- [STATUS: pending] **P5.2.2** Test endpoints with malformed headers
  - **Expected**: Proper error responses
  - **Verify**: No server crashes

---

## 📝 Phase 6: Documentation & Summary [LOW PRIORITY]

### P6.1 Test Results Documentation
- [STATUS: pending] **P6.1.1** Document all test results in `## Test Results` section below
- [STATUS: pending] **P6.1.2** Create summary of passing vs. failing tests
- [STATUS: pending] **P6.1.3** Document any discrepancies between expected and actual behavior
- [STATUS: pending] **P6.1.4** List any bugs discovered during testing

### P6.2 Postman Collection Updates
- [STATUS: pending] **P6.2.1** Update Postman collection with any new test cases discovered
- [STATUS: pending] **P6.2.2** Add test scripts/assertions to Postman collection
- [STATUS: pending] **P6.2.3** Document environment variables needed for testing

---

## 📝 Rolling Summary

> Update this section after completing each task. Keep it concise.

### Completed Work
<!-- Add entries as you complete tasks -->
| Date | Task ID | Summary | Files Changed |
|------|---------|---------|---------------|
| _YYYY-MM-DD_ | _P1.1.1_ | _Description_ | _files_ |

### Key Findings
<!-- Document important discoveries during testing -->
- _None yet_

### Bugs Discovered
<!-- Track bugs found during testing -->
- _None yet_

### Blockers & Issues
<!-- Track any blockers encountered -->
- _None yet_

---

## 🔍 Discovered Tasks

> Add new tasks discovered during testing here. Review periodically and integrate into phases.

- _None yet_

---

## 📊 Test Results

> Document test results here as you complete testing phases.

### Phase 1: Environment Setup
- **Status**: _Not Started_
- **Results**: _TBD_

### Phase 2: High Priority Endpoints
- **Status**: _Not Started_
- **Results**: _TBD_
- **Passing**: _0/XX tests_
- **Failing**: _0/XX tests_

### Phase 3: Medium Priority Endpoints
- **Status**: _Not Started_
- **Results**: _TBD_
- **Passing**: _0/XX tests_
- **Failing**: _0/XX tests_

### Phase 4: Low Priority Endpoints
- **Status**: _Not Started_
- **Results**: _TBD_
- **Passing**: _0/XX tests_
- **Failing**: _0/XX tests_

### Phase 5: Performance & Edge Cases
- **Status**: _Not Started_
- **Results**: _TBD_

---

## 🛠️ Quick Reference Commands

### Local Development
```bash
# Start environment
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Health checks
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/database
```

### Database Queries
```bash
# Get test audio ID (use -t for tuples-only, cleaner output)
docker-compose exec postgres psql -t -U postgres -d loist_music_library -c "SELECT audio_id FROM audio_tracks LIMIT 1;" | tr -d ' '

# Get audio ID with thumbnail
docker-compose exec postgres psql -t -U postgres -d loist_music_library -c "SELECT audio_id FROM audio_tracks WHERE thumbnail_gcs_path IS NOT NULL LIMIT 1;" | tr -d ' '
```

### Postman Testing
```bash
# Load collection
# File: loist-music-library-local.postman_collection.json

# Set environment variables (see Environment Variables section below)
```

---

## 📋 Postman Environment Variables

### Required Variables

| Variable | Description | Example | Expiry/Notes |
|----------|-------------|---------|--------------|
| `base_url` | API server base URL | `http://localhost:8080` | No expiry |
| `audio_id` | UUID of audio track for testing | `ca3f7741-3d32-445f-b837-f1ea92a79ac4` | Auto-set by "Process Audio Complete" request |
| `audio_source_url` | **HTTP URL to audio file for processing** | `https://example.com/audio.mp3` | **⚠️ EXPIRES AFTER 1 HOUR** |
| `embed_url` | Embed URL for oEmbed testing | `https://loist.io/embed/{audio_id}` | Auto-set by "Get Embed URL" request |

### Optional Variables

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `audio_source_filename` | Override filename for audio processing | Auto-derived from URL | Optional |
| `download_format` | Target format for download tests | `mp3` | Options: mp3, wav, flac, aac, ogg |
| `download_preset` | Quality preset for downloads | `high` | Options: high, standard, broadcast |
| `sessionId` | MCP session ID | Auto-set by "Initialize MCP Session" | Managed automatically |
| `sessionInitializedAt` | MCP session timestamp | Auto-set | Managed automatically |

### Critical Expiry Notes

**`audio_source_url` Expiry (1 Hour)**:
- ⚠️ **URLs expire after 1 hour** - get fresh URL before starting testing session
- If tests fail with "expired URL" or "not found" errors, update `audio_source_url` with fresh URL
- Postman collection includes validation warning if URL is still set to example/default value
- **Action**: Check URL freshness if audio processing tests fail unexpectedly

**Signed URL Expiry (15 Minutes)**:
- GCS signed URLs (from `/api/tracks/{audioId}/stream` and `/api/tracks/{audioId}/thumbnail`) expire after 15 minutes
- These are generated per-request, so expiry only affects saved URLs in Postman
- **Action**: Re-run requests to get fresh signed URLs if needed

### Postman Collection Structure

The collection (`loist-music-library-local.postman_collection.json`) is organized into folders:

1. **Health Checks** - Server health endpoints
2. **MCP Tools** - JSON-RPC tool calls (process_audio_complete, search_library, etc.)
3. **MCP Resources** - Resource access endpoints
4. **Custom Routes** - HTTP API endpoints (`/api/tracks/*`, `/embed/*`, `/oembed`)

**Collection Features**:
- Auto-initializes MCP session if not present (collection-level pre-request script)
- Auto-extracts `audio_id` from "Process Audio Complete" response
- Auto-stores `embed_url` from "Get Embed URL" response
- Validates environment variables before requests
- Includes test scripts for response validation

**Request Naming Convention**:
- MCP Tools: Tool name (e.g., "Process Audio Complete", "Search Library")
- HTTP API: Endpoint description (e.g., "Get Audio Stream (HTTP API)", "Download Audio Track - MP3")
- Error Tests: Include error type (e.g., "Update Metadata - Empty (Validation Error)")

---

## 📖 Implementation Notes

> Key implementation decisions and testing approach.

### Redirect vs Proxy Streaming
**Decision**: Use 302 redirects to signed GCS URLs for static assets (audio, thumbnails).

**Rationale**:
- GCS signed URLs natively support HTTP Range requests
- Redirects are sufficient for static assets (no transformations needed)
- Lower server load (client talks directly to GCS)
- Simpler implementation

**When to use proxy streaming**:
- Dynamic transformations (on-the-fly transcoding, image resizing)
- Per-byte authorization/analytics requirements
- Custom headers beyond what GCS provides

**Current Implementation**: ✅ Correct - redirects are appropriate for MVP.

### Range Request Testing Approach
**Testing Strategy**:
1. Disable "Follow redirects" in Postman to capture redirect response
2. Copy `Location` header URL from redirect response
3. Send direct request to signed URL with `Range` header
4. Verify GCS returns 206 Partial Content with correct headers

**Expected Behavior**:
- API endpoint returns 302 redirect with `Location` header
- GCS signed URL handles Range requests natively
- GCS returns 206 Partial Content with `Content-Range` header
- No proxy streaming needed for static assets

### Signed URL Expiry
**Important**: Signed URLs expire after 15 minutes.

**Testing Implications**:
- Capture fresh URLs for each test session
- Don't save signed URLs in Postman collection (they'll expire)
- Re-run requests if tests fail after 15 minutes
- Use environment variables to store URLs temporarily during testing

---

## 📅 Session Log

> Record session starts/ends for continuity across multi-day work.

| Session | Date | Tasks Completed | Next Task |
|---------|------|-----------------|-----------|
| 1 | _YYYY-MM-DD_ | _P1.1.1, P1.1.2_ | _P1.1.3_ |

---

**Last Updated**: _Update this timestamp when modifying the file_
**Source**: Comprehensive Testing Plan (2025-12-05)
**Focus**: Postman Testing Only

