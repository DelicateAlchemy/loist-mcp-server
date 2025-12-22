# "Aha Moment" Demo Flow Analysis

## Overview

This document analyzes the end-to-end audio ingestion pipeline for a demo scenario where users drop a folder of audio files and get back a structured catalog view.

## API Endpoints on Staging

### Base URL
- **Staging**: `https://staging.loist.io`
- **A2A Staging** (for async/polling): `https://a2a.staging.loist.io` (if using A2A protocol)

### Endpoint Flow (in order of pipeline)

#### 1. **Process Audio Complete** (Ingestion)
**Endpoint**: `POST /mcp` (MCP JSON-RPC protocol)

**Note**: This is accessed via the MCP JSON-RPC protocol, not a simple REST endpoint. The request must be wrapped in the JSON-RPC format.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "process_audio_complete",
    "arguments": {
      "source": {
        "type": "http_url",
        "url": "https://example.com/audio.mp3"
      },
      "options": {
        "maxSizeMB": 100,
        "timeout": 300,
        "validateFormat": true
      }
    }
  }
}
```

**Important**: There is **no direct HTTP REST endpoint** like `POST /api/tracks/process`. You must use the MCP JSON-RPC protocol at `POST /mcp`.

**What it does**:
1. Downloads audio from URL (with SSRF protection)
2. Extracts metadata (ID3 tags, XMP, BWF chunks, filename parsing)
3. Uploads to Google Cloud Storage
4. Saves to PostgreSQL database
5. Returns complete metadata + resource URIs

**Processing Time**: 
- Small files (< 10MB): 1-5 seconds
- Medium files (10-50MB): 5-15 seconds
- Large files (50-100MB): 15-30 seconds

#### 2. **Get Audio Metadata** (Retrieve processed track)
**Endpoint**: `POST /mcp` (MCP JSON-RPC) or `GET /api/tracks/{audioId}` (HTTP REST)

```bash
# HTTP REST (simpler)
GET https://staging.loist.io/api/tracks/{audioId}
```

#### 3. **Search Library** (Catalog view)
**Endpoint**: `GET /api/search` (HTTP REST)

```bash
GET https://staging.loist.io/api/search?q={query}&limit=100&offset=0
```

**Query Parameters**:
- `q` (required): Search query
- `limit` (optional, default: 20, max: 100): Results per page
- `offset` (optional, default: 0): Pagination offset
- `genre` (optional): Filter by genre

**Returns**:
- List of tracks with metadata
- Total count
- Facets (composers, publishers, record labels)
- Pagination info

## Minimum Payload for Ingestion

### Required (minimal)
```json
{
  "source": {
    "type": "http_url",
    "url": "https://example.com/song.mp3"
  }
}
```

### Recommended (with options)
```json
{
  "source": {
    "type": "http_url",
    "url": "https://example.com/song.mp3",
    "headers": {},
    "filename": "optional-override.mp3",
    "mimeType": "audio/mpeg"
  },
  "options": {
    "maxSizeMB": 100,
    "timeout": 300,
    "validateFormat": true
  }
}
```

**Note**: The endpoint processes **one file at a time**. For a folder of files, you'll need to:
1. Upload files to a public URL (Dropbox, GCS, etc.) OR
2. Make multiple sequential/parallel calls to `process_audio_complete`

## Response Schema

### Success Response Structure
```json
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "product": {
      "artist": "Artist Name",
      "title": "Song Title",
      "album": "Album Name",
      "mbid": null,
      "genre": ["Rock", "Pop"],
      "year": 2024,
      "composer": "Composer Name",
      "publisher": "Publisher Name",
      "record_label": "Label Name",
      "isrc": "USRC12345678",
      "copyright": "© 2024"
    },
    "format": {
      "duration": 180.5,
      "channels": 2,
      "sample_rate": 44100,
      "bitrate": 320000,
      "format": "MP3"
    },
    "url_embed_link": "https://staging.loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform_url": null
  },
  "processing_time": 2.45
}
```

### Key Metadata Fields

**Product Metadata**:
- `artist`, `title`, `album` (essential fields)
- `year`, `genre` (array)
- `composer`, `publisher`, `record_label`
- `isrc`, `copyright`
- `mbid` (MusicBrainz ID - currently always null in MVP)

**Format Metadata**:
- `duration` (seconds)
- `channels`, `sample_rate`, `bitrate`
- `format` (MP3, FLAC, WAV, M4A, etc.)

**Resources**:
- `audio_url`: MCP resource URI (can be resolved to signed GCS URL)
- `thumbnail_url`: Album artwork (if available)
- `waveform_url`: Currently null (not yet implemented)

## Webhook/Polling Mechanism

### Current Status: **Synchronous Processing**

The `process_audio_complete` endpoint is **synchronous** - it returns when processing is complete. This means:
- ✅ No webhook needed for basic flow
- ✅ Response contains complete metadata immediately
- ⚠️ Request will timeout if processing takes > 300 seconds (default)

### Alternative: A2A Protocol (Async/Polling)

For async processing with status polling, use the **A2A (Agent-to-Agent) protocol**:

**1. Submit Task** (`tasks/send` or `message/send`):
```bash
POST https://a2a.staging.loist.io/
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": "req-123",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{
        "type": "text",
        "text": "Process: https://example.com/track.mp3"
      }]
    }
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "result": {
    "task": {
      "id": "task-abc123",
      "status": {
        "state": "submitted"
      }
    }
  }
}
```

**2. Poll for Status** (`tasks/get`):
```bash
POST https://a2a.staging.loist.io/
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": "req-124",
  "method": "tasks/get",
  "params": {
    "taskId": "task-abc123"
  }
}
```

**Status States**: `submitted` → `working` → `completed` or `failed`

**When Completed**:
```json
{
  "jsonrpc": "2.0",
  "id": "req-124",
  "result": {
    "task": {
      "id": "task-abc123",
      "status": {
        "state": "completed"
      },
      "metadata": {
        "audio_track_id": "550e8400-e29b-41d4-a716-446655440000",
        "processing_result": { ... }
      }
    }
  }
}
```

## Integration with n8n/Make/Pipedream

### Can it work? **Yes, with caveats**

#### Option 1: Direct HTTP Calls (Simple but sequential)

**n8n/Make Flow**:
1. **Trigger**: Dropbox folder watcher / webhook
2. **Loop**: For each file in folder
   - Get public URL from Dropbox
   - HTTP Request → `POST https://staging.loist.io/mcp` with MCP JSON-RPC payload
   - Parse JSON-RPC response (extract `result` field, then `audio_id`)
   - Store `audio_id` in array
3. **After Loop**: 
   - Wait 30-60 seconds (for processing to complete)
   - HTTP Request → `GET https://staging.loist.io/api/search?q=*&limit=100`
   - Transform to CSV/table format
   - Send to Google Sheets/Notion/Airtable

**Limitations**:
- No native batch endpoint (must call multiple times)
- Sequential processing (unless you parallelize in the automation tool)
- Must handle HTTP timeouts for large files

#### Option 2: A2A Protocol (Better for async)

**n8n/Make Flow**:
1. **Trigger**: Dropbox folder watcher
2. **Loop**: For each file
   - Submit via `message/send` → get `task_id`
   - Store `task_id` in array
3. **Wait Module**: Wait 30-60 seconds
4. **Loop**: For each `task_id`
   - Poll `tasks/get` until `state == "completed"`
   - Extract `audio_track_id` from metadata
5. **Catalog Query**: `GET /api/search` to get all processed tracks
6. **Export**: Transform and send to destination

**Advantages**:
- Async processing (doesn't block on long operations)
- Status tracking per file
- Better error handling

### Required HTTP Request Nodes

For **n8n**:
- HTTP Request node (POST for MCP JSON-RPC)
- Code/Function node (for JSON-RPC envelope)
- Loop/Iterator node (for batch processing)
- Wait node (for processing delay)

For **Make**:
- HTTP module (POST for MCP JSON-RPC)
- Data Store (to track task_ids/audio_ids)
- Iterator (for batch processing)
- Delay (for processing wait)

**Example HTTP Request (n8n/Make)**:
```
POST https://staging.loist.io/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "process_audio_complete",
    "arguments": {
      "source": {
        "type": "http_url",
        "url": "{{$json.public_url}}"
      }
    }
  }
}
```

**Response Format** (JSON-RPC):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "audio_id": "550e8400-e29b-41d4-a716-446655440000",
    "metadata": { ... },
    "resources": { ... },
    "processing_time": 2.45
  }
}
```

**Note**: In n8n/Make, you'll need to parse the `result` field from the JSON-RPC response to access the actual data.

## Gotchas & Missing Pieces

### ✅ What Works Now

1. **Single File Processing**: Fully functional
2. **Metadata Extraction**: Comprehensive (ID3, XMP, BWF, filename parsing)
3. **Search/Catalog Endpoint**: Working (`GET /api/search`)
4. **Staging Environment**: Deployed and accessible
5. **Synchronous Processing**: Returns complete results immediately

### ⚠️ Limitations for Demo

1. **No Batch Endpoint**: 
   - Must call `process_audio_complete` once per file
   - No native "process folder" endpoint
   - **Workaround**: Loop in automation tool (n8n/Make)

2. **No Folder Upload**:
   - Endpoint expects HTTP URLs, not file uploads
   - **Workaround**: 
     - Upload folder to Dropbox/Google Drive first
     - Get public shareable links
     - Process each URL

3. **No Webhooks**:
   - Synchronous endpoint returns immediately
   - For async flow, use A2A protocol with polling

4. **Processing Time**:
   - Large files (50-100MB) take 15-30 seconds
   - Default timeout is 300 seconds
   - May need to increase timeout for very large files

5. **Metadata Completeness**:
   - `mbid` (MusicBrainz ID) is always `null` in MVP
   - `waveform_url` is always `null` (not yet implemented)

6. **Error Handling**:
   - Failed files return error response (not in catalog)
   - No bulk status endpoint to check which files succeeded/failed
   - **Workaround**: Track `audio_id` responses and query individually

### 🔍 Things to Verify on Staging

1. **Endpoint Availability**: 
   - Verify `POST /mcp` accepts MCP JSON-RPC calls (this is the primary endpoint)
   - Test `GET /api/search` returns expected format
   - Verify JSON-RPC response parsing works correctly

2. **CORS Configuration**:
   - If calling from browser/frontend, verify CORS is enabled
   - Staging config shows `ENABLE_CORS=true,CORS_ORIGINS=*`

3. **Authentication**:
   - Currently disabled (`AUTH_ENABLED=false`)
   - No bearer token required

4. **Database Status**:
   - Verify staging database is accessible
   - Check that processed tracks persist

5. **GCS Bucket**:
   - Verify staging bucket has write permissions
   - Check that files are uploaded successfully

## Recommended Demo Flow

### Simple Demo (Synchronous)

1. **Setup**: Upload 3-5 test audio files to Dropbox/Google Drive
2. **Get URLs**: Create public shareable links
3. **Process**: Loop through URLs, call `process_audio_complete` for each
4. **Wait**: Wait 30 seconds for all processing to complete
5. **Catalog**: Call `GET /api/search?q=*&limit=100`
6. **Display**: Show results in table/CSV format

### Production-Ready Demo (Async with A2A)

1. **Setup**: Same as above
2. **Submit**: Use A2A `message/send` to submit all files
3. **Poll**: Poll `tasks/get` until all tasks are `completed`
4. **Catalog**: Query `/api/search` for processed tracks
5. **Export**: Transform and export to destination

## Testing Checklist

Before running the demo:

- [ ] Verify staging health: `GET https://staging.loist.io/health/ready`
- [ ] Test single file processing: `POST /mcp` with `process_audio_complete`
- [ ] Verify response schema matches expected format
- [ ] Test search endpoint: `GET /api/search?q=test`
- [ ] Verify authentication is disabled (no bearer token needed)
- [ ] Check CORS if calling from browser
- [ ] Test with 2-3 files to verify batch loop works
- [ ] Verify catalog export format (CSV/table structure)

## Conclusion

**Can you run `process_audio_complete` on staging now?** 

**Yes**, with the following:
- ✅ Endpoint is available via MCP JSON-RPC protocol
- ✅ Staging environment is deployed at `https://staging.loist.io`
- ✅ Single file processing works end-to-end
- ⚠️ No batch endpoint (must loop in automation tool)
- ⚠️ No folder upload (must use HTTP URLs)

**Recommended Approach for Demo**:
1. Use **n8n/Make** to orchestrate the flow
2. Process files **one at a time** in a loop
3. Use **synchronous endpoint** for simplicity (or A2A for async)
4. Query **`/api/search`** after processing to get catalog view
5. Export to **Google Sheets/CSV** for visualization

The pipeline works, but requires orchestration logic in the automation tool to handle multiple files.

