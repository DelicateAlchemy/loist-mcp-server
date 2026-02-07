# Frontend API Integration Guide

This document provides a comprehensive list of API endpoints and environment variables needed to integrate the frontend with the Loist Music Library MCP Server backend.

## Table of Contents

- [API Endpoints](#api-endpoints)
- [Frontend Environment Variables](#frontend-environment-variables)
- [Authentication](#authentication)
- [Example Frontend Configuration](#example-frontend-configuration)
- [Google Cloud Setup](#google-cloud-setup)

---

## API Endpoints

### PlayerConfig Response Type

All embed-related MCP tools now return a standardized `PlayerConfig` response shape:

```typescript
type PlayerConfigUrls = {
  embed: string;              // Standard embed player URL
  waveform?: string;          // Waveform player URL (if applicable)
  artwork?: string;           // Album artwork signed URL
  waveform_svg?: string;      // Waveform SVG signed URL
};

type PlayerConfigMetadata = {
  title: string;
  artist: string;
  album?: string;
  duration_seconds?: number;
};

type PlayerConfig = {
  audio_id: string;
  mode: "simple" | "waveform";
  device: "desktop" | "mobile" | "auto";
  context: "embed" | "direct";
  waveform_available: boolean;
  urls: PlayerConfigUrls;
  metadata: PlayerConfigMetadata;
};
```

#### Understanding the `context` Field

The `context` field indicates the intended usage pattern for the player:

- **`"embed"`**: The player is intended for **iframe embedding** in external platforms (Notion, Coda, WordPress, etc.) or third-party websites. This is the default context returned by `get_embed_url` MCP tool.
  - Use when: Embedding the player in an iframe on another website
  - Example: `<iframe src="https://loist.io/embed/{audioId}"></iframe>`
  - The player is optimized for constrained iframe environments

- **`"direct"`**: The player is intended for **direct browser access** where users navigate directly to the embed URL.
  - Use when: Users click a share link and view the player in a full browser window
  - Example: User clicks `https://loist.io/embed/{audioId}` in a browser
  - The player has full browser context and can use additional features

**Note**: Currently, all MCP tools return `context: "embed"` as they are designed for programmatic embed URL generation. The `context` field is included for future extensibility and to clearly communicate the intended usage pattern to API consumers.

### Base URL

The base URL depends on your deployment:

- **Production**: `https://loist.io` (or your production domain)
- **Staging**: `https://staging.loist.io` (or your staging domain)
- **Local Development**: `http://localhost:8080`

### Health Check Endpoints

#### 1. General Health Check
```http
GET /health/live
```
**Purpose**: Liveness probe - checks if the application is running (no database queries)

**Response**:
```json
{
  "status": "alive",
  "timestamp": "2025-01-15T10:30:00Z",
  "service": "Music Library MCP",
  "version": "0.1.0",
  "check": "liveness"
}
```

**Status Codes**: `200` (alive), `500` (dead)

---

#### 2. Readiness Check
```http
GET /health/ready
```
**Purpose**: Readiness probe - checks if the application is ready to serve traffic

**Response**:
```json
{
  "status": "ready",
  "timestamp": "2025-01-15T10:30:00Z",
  "service": "Music Library MCP",
  "version": "0.1.0",
  "check": "readiness",
  "dependencies": {
    "database": {
      "configured": true,
      "available": true,
      "connection_type": "cloud_sql"
    },
    "gcs": {
      "configured": true
    }
  }
}
```

**Status Codes**: `200` (ready), `503` (not ready)

---

#### 3. Database Health Check
```http
GET /health/database
```
**Purpose**: Detailed database connectivity and performance information

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "database": {
    "available": true,
    "connection_type": "cloud_sql",
    "response_time_ms": 12.5,
    "version": "PostgreSQL 16.0",
    "pool_size": 10,
    "pool_stats": {
      "connections_created": 5,
      "connections_closed": 2,
      "queries_executed": 1234
    }
  }
}
```

**Status Codes**: `200` (healthy), `503` (unhealthy), `500` (error)

---

### Audio Processing Endpoints

#### 4. Process Audio (MCP Tool via HTTP)
```http
POST /mcp/tools/process_audio_complete
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "source": {
    "type": "http_url",
    "url": "https://example.com/audio.mp3",
    "headers": {},  // Optional
    "filename": "song.mp3",  // Optional
    "mimeType": "audio/mpeg"  // Optional
  },
  "options": {
    "maxSizeMB": 100,  // Optional, default: 100
    "timeout": 300,  // Optional, default: 300 seconds
    "validateFormat": true  // Optional, default: true
  }
}
```

**Response**:
```json
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "product": {
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "year": 2024
    },
    "format": {
      "duration": 180.5,
      "channels": 2,
      "sample_rate": 44100,
      "bitrate": 320,
      "format": "MP3"
    },
    "url_embed_link": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform_url": null
  },
  "processing_time": 2.45
}
```

**Status Codes**: `200` (success), `400` (validation error), `500` (processing error)

---

### Query Endpoints

#### 5. Get Audio Metadata (MCP Tool via HTTP)
```http
POST /mcp/tools/get_audio_metadata
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "audio_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "product": {
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "year": 2024
    },
    "format": {
      "duration": 180.5,
      "channels": 2,
      "sample_rate": 44100,
      "bitrate": 320,
      "format": "MP3"
    },
    "url_embed_link": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail_url": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform_url": null
  }
}
```

**Status Codes**: `200` (success), `404` (not found), `400` (invalid ID), `500` (error)

---

#### 6. Search Library (MCP Tool via HTTP)
```http
POST /mcp/tools/search_library
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "query": "beatles",
  "filters": {
    "genre": ["Rock"],
    "year": {
      "min": 1960,
      "max": 1970
    },
    "duration": {
      "min": 120,
      "max": 300
    },
    "format": ["MP3", "FLAC"],
    "artist": ["The Beatles"],
    "album": ["Abbey Road"]
  },
  "limit": 20,
  "offset": 0,
  "sortBy": "relevance",
  "sortOrder": "desc"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "audio_id": "550e8400-e29b-41d4-a716-446655440000",
      "metadata": {
        "product": {
          "title": "Hey Jude",
          "artist": "The Beatles",
          "album": "Hey Jude",
          "year": 1968
        },
        "format": {
          "duration": 431.0,
          "channels": 2,
          "sample_rate": 44100,
          "bitrate": 320000,
          "format": "MP3"
        },
        "url_embed_link": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
      },
      "score": 0.95
      "score": 0.95
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

**Status Codes**: `200` (success), `400` (invalid query), `500` (error)

---

#### 7. Download Audio Track ✅ **IMPLEMENTED & WORKING**

Download audio tracks with on-the-fly format conversion, metadata embedding, and artwork embedding.

```http
GET /api/tracks/{audioId}/download?format={format}&preset={preset}
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track to download

**Query Parameters**:
- `format` (string, required): Target format - `mp3`, `wav`, `flac`, `aac`, `ogg`
- `preset` (string, optional): Quality preset (defaults to `high`)

**Supported Formats & Presets**:

| Format | Presets | Description |
|--------|---------|-------------|
| `mp3` | `high` (320kbps), `standard` (192kbps), `compact` (128kbps) | Lossy compression |
| `wav` | `broadcast` (48kHz/24-bit), `cd` (44.1kHz/16-bit), `high` (96kHz/24-bit) | Lossless with BWF metadata |
| `flac` | `high` (level 8), `fast` (level 0) | Lossless compressed |
| `aac` | `high` (256kbps), `standard` (192kbps) | Lossy for Apple devices |
| `ogg` | `high` (Q8 ~256kbps), `standard` (Q5 ~160kbps) | Lossy VBR |

**Response**:
- **Content-Type**: `audio/mpeg`, `audio/wav`, `audio/flac`, `audio/aac`, or `audio/ogg`
- **Content-Disposition**: `attachment; filename="Track Title - Artist.mp3"`
- **Body**: Audio file with embedded metadata and artwork

**Short-circuit Response**: `302 Found` with `Location` header redirecting to signed GCS URL when no conversion is needed.

**Status Codes**: `200` (converted file), `302` (redirect to original), `400` (invalid params), `404` (not found), `500` (conversion error), `504` (timeout)

**Examples**:
```bash
# Download as high-quality MP3
GET /api/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=mp3

# Download as broadcast WAV
GET /api/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=wav&preset=broadcast

# Download as lossless FLAC
GET /api/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=flac
```

---

#### 8. Delete Audio Track
```http
DELETE /api/tracks/{audioId}
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track to delete

**Response**: `204 No Content` (success)

**Status Codes**: `204` (success), `404` (not found), `400` (invalid ID), `500` (error)

---

### Song Publishing Endpoints

#### 9. Create Party
```http
POST /api/parties
Content-Type: application/json

{
  "name": "John Lennon",
  "party_type": "person",
  "ipi_cae_number": "00000000297",
  "society_affiliation": "PRS",
  "email": "john@example.com",
  "notes": "Songwriter"
}
```

**Required Fields**: `name`
**Optional Fields**: `party_type` (default: "person"), `legal_name`, `ipi_cae_number`, `isni`, `society_affiliation`, `email`, `notes`

**Response**: `201 Created` with party data including generated `id`

**Status Codes**: `201` (created), `400` (validation error), `500` (error)

---

#### 10. Search Parties
```http
GET /api/parties/search?q=lennon&limit=20&offset=0
```

**Query Parameters**:
- `q` (string, required): Search query (case-insensitive partial match)
- `limit` (integer, optional): Max results 1-100 (default: 20)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response**: `200 OK` with `results`, `total`, `limit`, `offset`, `has_more`

---

#### 11. Get Party
```http
GET /api/parties/{partyId}
```

**Response**: `200 OK` with party details and involvement summary (works as writer, publisher, recordings as artist)

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

---

#### 12. Get Work
```http
GET /api/works/{workId}
```

**Response**: `200 OK` with work details including `writers`, `publishers`, `alternative_titles`, `recordings`, and `warnings` (split validation)

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

---

#### 13. Search Works
```http
GET /api/works/search?q=imagine&limit=20&offset=0
```

**Query Parameters**:
- `q` (string, required): Search query (case-insensitive partial match on title)
- `limit` (integer, optional): Max results 1-100 (default: 20)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response**: `200 OK` with `results`, `total`, `limit`, `offset`, `has_more`

---

#### 14. Update Work Writers (Batch Replace)
```http
PUT /api/works/{workId}/writers
Content-Type: application/json

{
  "writers": [
    {"party_id": "uuid-1", "split_percentage": 50.0, "split_status": "confirmed"},
    {"party_id": "uuid-2", "split_percentage": 50.0, "split_status": "proposed"}
  ]
}
```

Replaces all writers on the work. Omit a writer to remove them. Pass empty array to clear all.

**Status Codes**: `200` (success), `400` (validation error), `404` (work not found), `500` (error)

---

#### 15. Update Work Publishers (Batch Replace)
```http
PUT /api/works/{workId}/publishers
Content-Type: application/json

{
  "publishers": [
    {"party_id": "uuid-1", "split_percentage": 100.0, "split_status": "confirmed"}
  ]
}
```

Same pattern as writers. Replaces all publishers on the work.

**Status Codes**: `200` (success), `400` (validation error), `404` (work not found), `500` (error)

---

#### 16. Link Artist to Recording
```http
POST /api/tracks/{audioId}/artists
Content-Type: application/json

{
  "party_id": "uuid-of-artist",
  "is_primary": true,
  "notes": "Lead vocalist"
}
```

**Required Fields**: `party_id`
**Optional Fields**: `is_primary` (default: true), `notes`

**Status Codes**: `201` (created), `400` (validation error), `404` (not found), `500` (error)

---

### Embed Endpoints

#### 9. Embed Player Page
```http
GET /embed/{audioId}?template={template}&device={device}&platform={platform}
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track

**Query Parameters**:
- `template` (string, optional): `standard`, `waveform`, or `waveform-minimal` (default: `standard`)
- `compact` (boolean, optional): Alias for `template=waveform` (default: `false`)
- `device` (string, optional): `mobile` or `desktop` (auto-detected if not provided)
- `platform` (string, optional): Platform override (`coda`, `notion`, `slack`, etc.)

**Response**: HTML page with embedded audio player

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

**Example**:
```
GET /embed/550e8400-e29b-41d4-a716-446655440000?template=waveform&device=desktop
```

---

#### 9. Waveform Embed (Auto Device Detection)
```http
GET /embed/{audioId}/waveform
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track

**Response**: HTML page with waveform player (auto-detects mobile/desktop)

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

---

#### 10. Waveform Embed (Mobile)
```http
GET /embed/{audioId}/waveform/mobile
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track

**Response**: HTML page with mobile-optimized waveform player

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

---

#### 11. Waveform Embed (Desktop)
```http
GET /embed/{audioId}/waveform/desktop
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track

**Response**: HTML page with desktop-optimized waveform player (interactive)

**Status Codes**: `200` (success), `400` (invalid ID), `404` (not found), `500` (error)

---

### oEmbed Endpoints

#### 13. oEmbed Endpoint
```http
GET /oembed?url={embed_url}&format=json&maxwidth={width}&maxheight={height}
```

**Query Parameters**:
- `url` (string, required): The embed URL to generate oEmbed data for
- `format` (string, optional): Response format, `json` or `xml` (default: `json`)
- `maxwidth` (integer, optional): Maximum width for embed (default: 500)
- `maxheight` (integer, optional): Maximum height for embed (default: 200)

**Response**:
```json
{
  "version": "1.0",
  "type": "video",
  "provider_name": "Loist Music Library",
  "provider_url": "https://loist.io",
  "title": "Song Title",
  "author_name": "Artist Name",
  "html": "<iframe src=\"https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000\" width=\"500\" height=\"200\" frameborder=\"0\" allow=\"autoplay; encrypted-media; fullscreen\" style=\"border: none;\"></iframe>",
  "width": 500,
  "height": 200,
  "thumbnail_url": "https://storage.googleapis.com/...",
  "thumbnail_width": 500,
  "thumbnail_height": 500,
  "cache_age": 3600
}
```

**Status Codes**: `200` (success), `400` (invalid URL), `404` (not found), `500` (error)

**Example**:
```
GET /oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000&maxwidth=800&maxheight=300
```

---

#### 14. oEmbed Discovery
```http
GET /.well-known/oembed.json
```

**Response**:
```json
{
  "provider_name": "Loist Music Library",
  "provider_url": "https://loist.io",
  "endpoints": [
    {
      "url": "https://loist.io/oembed",
      "formats": ["json"],
      "discovery": true
    }
  ]
}
```

**Status Codes**: `200` (success)

---

### MCP Resource Endpoints

These endpoints return signed GCS URLs for accessing audio content:

#### 15. Audio Stream Resource
```http
POST /mcp/resources/music-library://audio/{audioId}/stream
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Response**:
```json
{
  "uri": "https://storage.googleapis.com/bucket/audio.mp3?X-Goog-Signature=...",
  "mimeType": "audio/mpeg",
  "text": null,
  "blob": null
}
```

**Note**: Signed URLs expire after 15 minutes (900 seconds)

---

#### 16. Metadata Resource
```http
POST /mcp/resources/music-library://audio/{audioId}/metadata
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Response**:
```json
{
  "uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata",
  "mimeType": "application/json",
  "text": "{\"Product\":{\"Title\":\"Song Title\",...}}",
  "blob": null
}
```

---

#### 17. Thumbnail Resource
```http
POST /mcp/resources/music-library://audio/{audioId}/thumbnail
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Response**:
```json
{
  "uri": "https://storage.googleapis.com/bucket/thumbnail.jpg?X-Goog-Signature=...",
  "mimeType": "image/jpeg",
  "text": null,
  "blob": null
}
```

**Note**: Returns `null` if no thumbnail is available

---

### Embed Management Tools

#### 18. Get Embed URL (MCP Tool via HTTP)
```http
POST /mcp/tools/get_embed_url
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "template": "waveform",
  "device": "desktop"
}
```

**Response**: PlayerConfig shape

**Note**: The `context` field indicates the intended usage pattern. `get_embed_url` returns `context: "embed"` by default, indicating the URL is optimized for iframe embedding. The same URL can also be used for direct browser access, but the `context` field helps API consumers understand the primary use case.

```json
{
  "success": true,
  "audio_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "waveform",
  "device": "desktop",
  "context": "embed",
  "waveform_available": true,
  "urls": {
    "embed": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000",
    "waveform": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000/waveform",
    "artwork": "https://storage.googleapis.com/bucket/artwork.jpg?X-Goog-Signature=...",
    "waveform_svg": "https://storage.googleapis.com/bucket/waveform.svg?X-Goog-Signature=..."
  },
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "duration_seconds": 180.5
  }
}
```

---

#### 19. List Embed Templates (MCP Tool via HTTP)
```http
POST /mcp/tools/list_embed_templates
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Response**:
```json
{
  "success": true,
  "templates": [
    {
      "id": "standard",
      "name": "Standard Player",
      "description": "Basic audio player with progress bar and standard controls",
      "endpoint": "/embed/{audioId}",
      "features": ["progress-bar", "volume-control", "keyboard-shortcuts"],
      "deviceSupport": ["mobile", "desktop"],
      "interactive": true
    },
    {
      "id": "waveform",
      "name": "Waveform Player",
      "description": "Interactive waveform visualization with click-to-seek",
      "endpoint": "/embed/{audioId}/waveform",
      "features": ["waveform-visualization", "click-to-seek", "progress-overlay"],
      "deviceSupport": ["mobile", "desktop"],
      "interactive": true
    }
  ],
  "baseUrl": "https://loist.io",
  "supportedFormats": ["MP3", "FLAC", "WAV", "M4A", "OGG", "AAC"]
}
```

---

## MCP Resources (Audio Streaming & Artwork)

### Overview

The Loist Music Library exposes audio content through MCP resources, not direct HTTP endpoints. These resources provide secure, signed URLs for streaming audio and accessing artwork. All resources use in-memory caching and expire after 15 minutes for security.

### Audio Streaming Resource

**Resource URI**: `music-library://audio/{audio_id}/stream`

**Purpose**: Provides signed GCS URL for audio streaming with range request support for seeking.

**How to Access**:
```javascript
// Via MCP protocol (recommended for MCP clients)
const streamUri = `music-library://audio/${audioId}/stream`;
const resource = await mcpClient.readResource(streamUri);

// Via HTTP API
const response = await fetch(`${API_BASE_URL}/mcp/resources/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${VITE_API_BEARER_TOKEN}` // if auth enabled
  },
  body: JSON.stringify({
    uri: `music-library://audio/${audioId}/stream`
  })
});

const resource = await response.json();
const streamUrl = resource.uri; // Signed GCS URL
```

**Response**:
```json
{
  "uri": "https://storage.googleapis.com/bucket/audio.mp3?X-Goog-Signature=...",
  "mimeType": "audio/mpeg",
  "text": null,
  "blob": null
}
```

**Usage in HTML5 Audio**:
```html
<audio controls preload="metadata">
  <source src="https://storage.googleapis.com/bucket/audio.mp3?X-Goog-Signature=..." type="audio/mpeg">
  Your browser does not support the audio element.
</audio>
```

**Important Notes**:
- URLs expire after **15 minutes** for security
- Supports HTTP Range requests for seeking (`Accept-Ranges: bytes`)
- First request: ~50-100ms (database lookup + URL generation)
- Cached requests: ~5-10ms (cache hit)
- Supported formats: MP3, FLAC, WAV, M4A, OGG, AAC

---

### Artwork/Thumbnail Resource

**Resource URI**: `music-library://audio/{audio_id}/thumbnail`

**Purpose**: Provides signed GCS URL for album artwork/thumbnail images.

**How to Access**:
```javascript
// Via MCP protocol
const thumbnailUri = `music-library://audio/${audioId}/thumbnail`;
const resource = await mcpClient.readResource(thumbnailUri);

// Via HTTP API
const response = await fetch(`${API_BASE_URL}/mcp/resources/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${VITE_API_BEARER_TOKEN}` // if auth enabled
  },
  body: JSON.stringify({
    uri: `music-library://audio/${audioId}/thumbnail`
  })
});

const resource = await response.json();
if (resource.uri) {
  // Artwork exists
  const artworkUrl = resource.uri; // Signed GCS URL
} else {
  // No artwork available
}
```

**Response** (when artwork exists):
```json
{
  "uri": "https://storage.googleapis.com/bucket/artwork.jpg?X-Goog-Signature=...",
  "mimeType": "image/jpeg",
  "text": null,
  "blob": null
}
```

**Response** (when no artwork exists):
```json
{
  "uri": null,
  "mimeType": "image/jpeg",
  "text": null,
  "blob": null
}
```

**Usage in HTML**:
```html
<img src="https://storage.googleapis.com/bucket/artwork.jpg?X-Goog-Signature=..."
     alt="Album artwork"
     style="max-width: 300px; max-height: 300px;">
```

**Important Notes**:
- URLs expire after **15 minutes** for security
- Recommended client cache: 24 hours (`Cache-Control: public, max-age=86400`)
- Size: 600x600px (if available)
- Format: JPEG (if embedded artwork exists)

---

### Metadata Resource

**Resource URI**: `music-library://audio/{audio_id}/metadata`

**Purpose**: Returns complete track metadata as JSON.

**How to Access**:
```javascript
// Via MCP protocol
const metadataUri = `music-library://audio/${audioId}/metadata`;
const resource = await mcpClient.readResource(metadataUri);
const metadata = JSON.parse(resource.text);

// Via HTTP API
const response = await fetch(`${API_BASE_URL}/mcp/resources/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${VITE_API_BEARER_TOKEN}` // if auth enabled
  },
  body: JSON.stringify({
    uri: `music-library://audio/${audioId}/metadata`
  })
});

const resource = await response.json();
const metadata = JSON.parse(resource.text);
```

**Response**:
```json
{
  "uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata",
  "mimeType": "application/json",
  "text": "{\"id\": \"550e8400-...\", \"Product\": {...}, \"Format\": {...}, \"urlEmbedLink\": \"...\", \"resources\": {...}}",
  "blob": null
}
```

**Complete Metadata Structure**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "Product": {
    "Artist": "The Beatles",
    "Title": "Hey Jude",
    "Album": "Hey Jude",
    "MBID": null,
    "Genre": ["Rock"],
    "Year": 1968
  },
  "Format": {
    "Duration": 431.0,
    "Channels": 2,
    "SampleRate": 44100,
    "Bitrate": 320000,
    "Format": "MP3"
  },
  "urlEmbedLink": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000",
  "resources": {
    "audio": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
  }
}
```

**Important Notes**:
- Response time: ~20-50ms (database lookup only)
- Recommended client cache: 1 hour (`Cache-Control: public, max-age=3600`)
- MBID field is null (no fingerprinting in MVP)

---

### Resource Access Patterns

#### Recommended Integration Flow

```javascript
// 1. Get PlayerConfig from get_embed_url (contains artwork URL)
const embedConfig = await getEmbedUrl(audioId, 'waveform', 'desktop');

// 2. Access audio stream via MCP resource
const streamResource = await mcpClient.readResource(embedConfig.resources.audio);
const streamUrl = streamResource.uri;

// 3. Access artwork via MCP resource (or use PlayerConfig.urls.artwork)
const thumbnailResource = await mcpClient.readResource(embedConfig.resources.thumbnail);
const artworkUrl = thumbnailResource.uri || '/default-artwork.png';

// 4. Use in HTML5 player
const audioElement = new Audio(streamUrl);
const imgElement = new Image();
imgElement.src = artworkUrl;
```

#### Error Handling

```javascript
try {
  const resource = await mcpClient.readResource(uri);
  if (resource.uri) {
    // Resource available
    return resource.uri;
  } else {
    // Resource not available (e.g., no artwork)
    return defaultValue;
  }
} catch (error) {
  if (error.code === 'ResourceNotFoundError') {
    // Audio track doesn't exist
    throw new Error('Audio track not found');
  }
  throw error;
}
```

#### Performance Considerations

- **Caching**: Resources are cached server-side (13.5 min TTL)
- **Batch Requests**: Request multiple resources in parallel
- **Prefetching**: Request resources before they're needed
- **URL Expiration**: Plan for 15-minute URL expiration

### Related Documentation

For complete technical details, see:
- **[MCP Resources API](./mcp-resources-api.md)**: Comprehensive resource documentation with examples
- **[Embed Player Guide](./embed-player-guide.md)**: Player integration and embedding patterns

---

## Frontend Environment Variables

### Required Environment Variables

These environment variables must be configured in your frontend application:

```bash
# API Configuration
VITE_API_BASE_URL=https://loist.io  # or staging.loist.io for staging
VITE_API_TIMEOUT=30000  # Request timeout in milliseconds (30 seconds)

# Authentication (if AUTH_ENABLED=true on backend)
VITE_API_BEARER_TOKEN=your-bearer-token-here  # Only if authentication is enabled

# Embed Configuration
VITE_EMBED_BASE_URL=https://loist.io  # Base URL for embed links

# Feature Flags
VITE_ENABLE_AUTHENTICATION=false  # Set to true if backend has AUTH_ENABLED=true
VITE_ENABLE_DEBUG_LOGGING=false  # Enable debug logging in development
```

### Optional Environment Variables

```bash
# Development/Staging Configuration
VITE_ENVIRONMENT=production  # production, staging, development
VITE_API_RETRY_ATTEMPTS=3  # Number of retry attempts for failed requests
VITE_API_RETRY_DELAY=1000  # Delay between retries in milliseconds

# UI Configuration
VITE_DEFAULT_PAGE_SIZE=20  # Default number of results per page
VITE_MAX_PAGE_SIZE=100  # Maximum number of results per page
VITE_DEFAULT_SORT_BY=relevance  # Default sort field
VITE_DEFAULT_SORT_ORDER=desc  # Default sort order

# Embed Player Configuration
VITE_EMBED_DEFAULT_TEMPLATE=standard  # standard, waveform, waveform-minimal
VITE_EMBED_DEFAULT_DEVICE=auto  # auto, mobile, desktop
VITE_EMBED_AUTO_PLAY=false  # Auto-play audio when embed loads

# Analytics (if applicable)
VITE_ANALYTICS_ENABLED=false
VITE_ANALYTICS_ID=your-analytics-id
```

---

## Authentication

### Current Status

**Authentication is currently disabled** (`AUTH_ENABLED=false`) for pre-MVP development. Bearer token authentication will be added later when ready for production security.

### When Authentication is Enabled

If `AUTH_ENABLED=true` on the backend, include the bearer token in all API requests:

```javascript
// Example: Fetch with authentication
const response = await fetch(`${API_BASE_URL}/mcp/tools/search_library`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${VITE_API_BEARER_TOKEN}`
  },
  body: JSON.stringify({
    query: 'beatles',
    limit: 20
  })
});
```

---

## Example Frontend Configuration

### React/Vite Example

Create a `.env.production` file:

```bash
# Production Environment
VITE_API_BASE_URL=https://loist.io
VITE_EMBED_BASE_URL=https://loist.io
VITE_ENVIRONMENT=production
VITE_ENABLE_AUTHENTICATION=false
VITE_API_TIMEOUT=30000
```

Create a `.env.staging` file:

```bash
# Staging Environment
VITE_API_BASE_URL=https://staging.loist.io
VITE_EMBED_BASE_URL=https://staging.loist.io
VITE_ENVIRONMENT=staging
VITE_ENABLE_AUTHENTICATION=false
VITE_API_TIMEOUT=30000
VITE_ENABLE_DEBUG_LOGGING=true
```

Create a `.env.local` file (for local development):

```bash
# Local Development
VITE_API_BASE_URL=http://localhost:8080
VITE_EMBED_BASE_URL=http://localhost:8080
VITE_ENVIRONMENT=development
VITE_ENABLE_AUTHENTICATION=false
VITE_API_TIMEOUT=30000
VITE_ENABLE_DEBUG_LOGGING=true
```

### API Client Example (TypeScript)

```typescript
// src/api/client.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || '30000');
const BEARER_TOKEN = import.meta.env.VITE_API_BEARER_TOKEN;

interface ApiRequest {
  method: 'GET' | 'POST' | 'DELETE';
  path: string;
  body?: any;
  headers?: Record<string, string>;
}

async function apiRequest<T>({ method, path, body, headers = {} }: ApiRequest): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  
  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers
  };

  // Add authentication if enabled
  if (BEARER_TOKEN) {
    requestHeaders['Authorization'] = `Bearer ${BEARER_TOKEN}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const response = await fetch(url, {
      method,
      headers: requestHeaders,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  }
}

// API Methods
export const api = {
  // Health checks
  health: {
    live: () => apiRequest<{ status: string }>({ method: 'GET', path: '/health/live' }),
    ready: () => apiRequest<{ status: string }>({ method: 'GET', path: '/health/ready' }),
    database: () => apiRequest<{ status: string }>({ method: 'GET', path: '/health/database' })
  },

  // Audio processing
  processAudio: (source: any, options?: any) =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/process_audio_complete',
      body: { source, options }
    }),

  // Query
  getAudioMetadata: (audioId: string) =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/get_audio_metadata',
      body: { audio_id: audioId }
    }),

  searchLibrary: (query: string, filters?: any, limit = 20, offset = 0, sortBy = 'relevance', sortOrder = 'desc') =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/search_library',
      body: { query, filters, limit, offset, sortBy, sortOrder }
    }),

  deleteTrack: (audioId: string) =>
    apiRequest({
      method: 'DELETE',
      path: `/api/tracks/${audioId}`
    }),

  // Embed
  getEmbedUrl: (audioId: string, template = 'standard', device?: string) =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/get_embed_url',
      body: { audio_id: audioId, template, device }
    }),

  listEmbedTemplates: () =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/list_embed_templates',
      body: {}
    }),

  getEmbedUrlWaveform: (audioId: string) =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/get_embed_url',
      body: { audio_id: audioId, template: 'waveform', device: 'auto' }
    })
};
```

---

## Google Cloud Setup

### Frontend Deployment on Google Cloud

To deploy your frontend on the same Google Cloud project:

#### 1. Create a Cloud Storage Bucket for Frontend Assets

```bash
# Create bucket for frontend static assets
gsutil mb -p $PROJECT_ID -l us-central1 gs://$PROJECT_ID-frontend

# Enable static website hosting
gsutil web set -m index.html -e index.html gs://$PROJECT_ID-frontend

# Set CORS configuration
gsutil cors set cors.json gs://$PROJECT_ID-frontend
```

#### 2. Create Cloud Load Balancer (Optional, for Custom Domain)

If you want a custom domain (e.g., `app.loist.io`):

```bash
# Create backend bucket
gcloud compute backend-buckets create frontend-backend \
  --gcs-bucket-name=$PROJECT_ID-frontend

# Create URL map
gcloud compute url-maps create frontend-url-map \
  --default-backend-bucket=frontend-backend

# Create HTTPS proxy
gcloud compute target-https-proxies create frontend-https-proxy \
  --url-map=frontend-url-map \
  --ssl-certificates=your-ssl-certificate

# Create forwarding rule
gcloud compute forwarding-rules create frontend-forwarding-rule \
  --global \
  --target-https-proxy=frontend-https-proxy \
  --ports=443
```

#### 3. Environment Variables for Cloud Build

Add these to your Cloud Build configuration for frontend deployment:

```yaml
# cloudbuild-frontend.yaml
steps:
  - name: 'node:18'
    entrypoint: 'npm'
    args: ['install']
  
  - name: 'node:18'
    entrypoint: 'npm'
    args: ['run', 'build']
    env:
      - 'VITE_API_BASE_URL=https://loist.io'
      - 'VITE_EMBED_BASE_URL=https://loist.io'
      - 'VITE_ENVIRONMENT=production'
      - 'VITE_ENABLE_AUTHENTICATION=false'
  
  - name: 'gcr.io/cloud-builders/gsutil'
    args: ['-m', 'rsync', '-r', '-d', 'dist/', 'gs://$PROJECT_ID-frontend/']
```

#### 4. Cloud Run Alternative (for SSR/API Routes)

If your frontend needs server-side rendering or API routes, deploy to Cloud Run:

```yaml
# cloudbuild-frontend-cloudrun.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/frontend', '.']
  
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/frontend']
  
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'frontend'
      - '--image=gcr.io/$PROJECT_ID/frontend'
      - '--region=us-central1'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--set-env-vars=VITE_API_BASE_URL=https://loist.io'
      - '--set-env-vars=VITE_EMBED_BASE_URL=https://loist.io'
      - '--set-env-vars=VITE_ENVIRONMENT=production'
```

### CORS Configuration

The backend is configured with CORS enabled. Ensure your frontend domain is included in `CORS_ORIGINS`:

**Backend Configuration** (in Cloud Run):
```bash
CORS_ORIGINS=https://app.loist.io,https://loist.io
```

Or allow all origins (development only):
```bash
CORS_ORIGINS=*
```

### Shared Environment Variables

Both frontend and backend share these concepts:

| Frontend Variable | Backend Variable | Purpose |
|------------------|------------------|---------|
| `VITE_API_BASE_URL` | `EMBED_BASE_URL` | Base URL for API calls |
| `VITE_EMBED_BASE_URL` | `EMBED_BASE_URL` | Base URL for embed links |
| `VITE_API_BEARER_TOKEN` | `BEARER_TOKEN` | Authentication token (when enabled) |

---

## Error Handling

### Common Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "additional error details"
  }
}
```

### Error Codes

- `VALIDATION_ERROR`: Invalid input parameters
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `AUTHENTICATION_ERROR`: Authentication failed (when enabled)
- `RATE_LIMIT_ERROR`: Too many requests
- `STORAGE_ERROR`: GCS operation failed
- `DATABASE_ERROR`: Database operation failed
- `TIMEOUT_ERROR`: Request timed out
- `INTERNAL_ERROR`: Unexpected server error

### HTTP Status Codes

- `200`: Success
- `204`: Success (No Content)
- `400`: Bad Request (validation error)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error
- `503`: Service Unavailable (dependency unavailable)

---

## Rate Limiting

Currently, there is no rate limiting implemented. Rate limiting will be added in a future update.

---

## Testing

### Health Check Test

```bash
# Test liveness
curl https://loist.io/health/live

# Test readiness
curl https://loist.io/health/ready

# Test database health
curl https://loist.io/health/database
```

### API Test

```bash
# Search library
curl -X POST https://loist.io/mcp/tools/search_library \
  -H "Content-Type: application/json" \
  -d '{"query": "beatles", "limit": 10}'

# Get metadata
curl -X POST https://loist.io/mcp/tools/get_audio_metadata \
  -H "Content-Type: application/json" \
  -d '{"audio_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

---

## Support

For issues or questions:
- Check the [Backend Documentation](../README.md)
- Review [Environment Variables Configuration](./environment-variables.md)
- See [Cloud Run Deployment Guide](./cloud-run-deployment.md)

