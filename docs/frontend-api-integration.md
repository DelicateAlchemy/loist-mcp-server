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
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "Product": {
      "Title": "Song Title",
      "Artist": "Artist Name",
      "Album": "Album Name",
      "Year": 2024
    },
    "Format": {
      "Duration": 180.5,
      "Channels": 2,
      "SampleRate": 44100,
      "Bitrate": 320,
      "Format": "MP3"
    }
  },
  "resourceUris": {
    "stream": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "metadata": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata",
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
  }
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
  "audioId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "Product": {
      "Title": "Song Title",
      "Artist": "Artist Name",
      "Album": "Album Name",
      "Year": 2024
    },
    "Format": {
      "Duration": 180.5,
      "Channels": 2,
      "SampleRate": 44100,
      "Bitrate": 320,
      "Format": "MP3"
    }
  },
  "resourceUris": {
    "stream": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "metadata": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata",
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"
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
      "audioId": "550e8400-e29b-41d4-a716-446655440000",
      "metadata": {
        "Product": {
          "Title": "Hey Jude",
          "Artist": "The Beatles",
          "Album": "The Beatles",
          "Year": 1968
        },
        "Format": {
          "Duration": 431.0,
          "Format": "MP3"
        }
      },
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

#### 7. Delete Audio Track
```http
DELETE /api/tracks/{audioId}
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Path Parameters**:
- `audioId` (string, required): UUID of the audio track to delete

**Response**: `204 No Content` (success)

**Status Codes**: `204` (success), `404` (not found), `400` (invalid ID), `500` (error)

---

### Embed Endpoints

#### 8. Embed Player Page
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

#### 12. oEmbed Endpoint
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

#### 13. oEmbed Discovery
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

#### 14. Audio Stream Resource
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

#### 15. Metadata Resource
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

#### 16. Thumbnail Resource
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

#### 17. Get Embed URL (MCP Tool via HTTP)
```http
POST /mcp/tools/get_embed_url
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "template": "waveform",
  "device": "desktop"
}
```

**Response**:
```json
{
  "success": true,
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "embedUrl": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000/waveform/desktop",
  "template": "waveform",
  "device": "desktop",
  "waveformAvailable": true,
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "duration": 180.5,
    "format": "MP3"
  }
}
```

---

#### 18. List Embed Templates (MCP Tool via HTTP)
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

#### 19. Check Waveform Availability (MCP Tool via HTTP)
```http
POST /mcp/tools/check_waveform_availability
Content-Type: application/json
Authorization: Bearer {token}  # If AUTH_ENABLED=true
```

**Request Body**:
```json
{
  "audioId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "waveformAvailable": true,
  "waveformUrl": "https://storage.googleapis.com/...",
  "generatedAt": "2025-01-15T10:30:00Z",
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "duration": 180.5,
    "format": "MP3"
  }
}
```

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
      body: { audioId }
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
      body: { audioId, template, device }
    }),

  listEmbedTemplates: () =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/list_embed_templates',
      body: {}
    }),

  checkWaveformAvailability: (audioId: string) =>
    apiRequest({
      method: 'POST',
      path: '/mcp/tools/check_waveform_availability',
      body: { audioId }
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
  -d '{"audioId": "550e8400-e29b-41d4-a716-446655440000"}'
```

---

## Support

For issues or questions:
- Check the [Backend Documentation](../README.md)
- Review [Environment Variables Configuration](./environment-variables.md)
- See [Cloud Run Deployment Guide](./cloud-run-deployment.md)

