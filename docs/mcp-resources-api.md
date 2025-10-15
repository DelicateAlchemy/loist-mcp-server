## MCP Resources API Documentation

## Overview

The Loist Music Library MCP Server provides 3 resource endpoints for accessing audio content and metadata:

1. **Audio Stream** - Stream audio files with range request support
2. **Metadata** - Retrieve complete metadata as JSON
3. **Thumbnail** - Access album artwork/thumbnails

All resources use **signed GCS URLs** with **in-memory caching** for performance and security.

---

## Architecture

```
MCP Resource Request
├── URI Parsing & Validation
├── Database Metadata Lookup
├── Signed URL Generation (with caching)
├── Response Formatting
└── Return MCP Resource Response
```

### Caching Strategy

**Signed URL Cache:**
- **TTL**: 13.5 minutes (90% of 15-min signed URL expiration)
- **Thread-safe**: Lock-based concurrent access
- **Statistics**: Hit/miss tracking for monitoring
- **Auto-expiration**: Cleanup of expired entries

**Benefits:**
- ✅ Reduces GCS API calls
- ✅ Improves response time
- ✅ Still secure (short-lived URLs)

---

## Resource 1: Audio Stream

### URI Format

```
music-library://audio/{audioId}/stream
```

### Purpose

Provides signed GCS URL for audio streaming with range request support for seeking.

### Response

```json
{
  "uri": "https://storage.googleapis.com/bucket/audio.mp3?X-Goog-Signature=...",
  "mimeType": "audio/mpeg",
  "text": null,
  "blob": null
}
```

### MIME Types

| Format | Content-Type |
|--------|-------------|
| MP3 | `audio/mpeg` |
| FLAC | `audio/flac` |
| M4A | `audio/mp4` |
| OGG | `audio/ogg` |
| WAV | `audio/wav` |
| AAC | `audio/aac` |
| OPUS | `audio/opus` |

### HTTP Headers (from signed URL)

```
Content-Type: audio/mpeg
Accept-Ranges: bytes
Cache-Control: public, max-age=3600
Access-Control-Allow-Origin: *
Access-Control-Expose-Headers: Content-Length, Content-Range, Accept-Ranges
```

### Range Request Support

The signed GCS URL supports HTTP Range requests for seeking:

```http
GET /audio.mp3 HTTP/1.1
Range: bytes=0-1023

HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/100000
Content-Length: 1024
```

### Usage Example

```python
# Get audio stream resource
uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream"
response = await audio_stream_resource(uri)

print(f"Stream URL: {response['uri']}")
print(f"Content-Type: {response['mimeType']}")

# Use signed URL for streaming
# URL is valid for 15 minutes
# Supports range requests for seeking
```

### Performance

- **First request**: ~50-100ms (database + GCS signed URL generation)
- **Cached requests**: ~5-10ms (cache hit)
- **Cache TTL**: 13.5 minutes
- **URL expiration**: 15 minutes

---

## Resource 2: Metadata

### URI Format

```
music-library://audio/{audioId}/metadata
```

### Purpose

Returns complete audio metadata as JSON.

### Response

```json
{
  "uri": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata",
  "mimeType": "application/json",
  "text": "{\"id\": \"550e8400-...\", \"Product\": {...}, \"Format\": {...}}",
  "blob": null
}
```

### Metadata Structure

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
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform": null
  }
}
```

### HTTP Headers

```
Content-Type: application/json
Cache-Control: public, max-age=3600
Access-Control-Allow-Origin: *
```

### Usage Example

```python
# Get metadata resource
uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/metadata"
response = await metadata_resource(uri)

import json
metadata = json.loads(response['text'])

print(f"Title: {metadata['Product']['Title']}")
print(f"Artist: {metadata['Product']['Artist']}")
print(f"Duration: {metadata['Format']['Duration']}s")
```

### Performance

- **Response time**: ~20-50ms (database lookup only)
- **Cacheable**: Yes (1 hour recommended)

---

## Resource 3: Thumbnail

### URI Format

```
music-library://audio/{audioId}/thumbnail
```

### Purpose

Provides signed GCS URL for album artwork/thumbnail image.

### Response

```json
{
  "uri": "https://storage.googleapis.com/bucket/artwork.jpg?X-Goog-Signature=...",
  "mimeType": "image/jpeg",
  "text": null,
  "blob": null
}
```

### HTTP Headers (from signed URL)

```
Content-Type: image/jpeg
Cache-Control: public, max-age=86400
Access-Control-Allow-Origin: *
```

### Usage Example

```python
# Get thumbnail resource
uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"

try:
    response = await thumbnail_resource(uri)
    print(f"Thumbnail URL: {response['uri']}")
except ResourceNotFoundError:
    print("No thumbnail available for this track")
```

### Performance

- **First request**: ~50-100ms (database + GCS signed URL)
- **Cached requests**: ~5-10ms (cache hit)
- **Cache TTL**: 13.5 minutes
- **Recommended browser cache**: 24 hours

---

## Error Handling

### Error Types

| Error | HTTP Status | When It Occurs |
|-------|------------|----------------|
| `ResourceNotFoundError` | 404 | Audio ID not found, thumbnail missing |
| `ValidationError` | 400 | Invalid URI format |
| `DatabaseOperationError` | 500 | Database query failure |
| `StorageError` | 500 | GCS signed URL generation failure |

### Error Examples

#### Audio Not Found

```python
uri = "music-library://audio/00000000-0000-0000-0000-000000000000/stream"

try:
    response = await audio_stream_resource(uri)
except ResourceNotFoundError as e:
    print(f"Error: {e}")  # "Audio track 00000000-... not found"
```

#### Invalid URI Format

```python
uri = "invalid://uri/format"

try:
    response = await metadata_resource(uri)
except ValidationError as e:
    print(f"Error: {e}")  # "Invalid URI format: invalid://uri/format"
```

#### Thumbnail Not Available

```python
uri = "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail"

try:
    response = await thumbnail_resource(uri)
except ResourceNotFoundError as e:
    print(f"Error: {e}")  # "Thumbnail not available for audio 550e8400-..."
```

---

## Caching Details

### SignedURLCache Class

```python
from src.resources.cache import get_cache

# Get global cache instance
cache = get_cache()

# Get statistics
stats = cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate_percent']}%")
print(f"Total requests: {stats['total_requests']}")
print(f"Cache size: {stats['size']} entries")

# Manual invalidation (if needed)
cache.invalidate("gs://bucket/path/to/file")

# Clear all cached URLs
cache.clear()
```

### Cache Statistics

```python
{
  "size": 42,              # Number of cached URLs
  "hits": 150,             # Cache hits
  "misses": 50,            # Cache misses
  "total_requests": 200,   # Total requests
  "hit_rate_percent": 75.0,# Hit rate percentage
  "ttl_seconds": 810       # TTL in seconds
}
```

### Cache Behavior

**Cache Hit Scenario:**
```
Request 1: /audio/{id}/stream
  └─ Cache MISS → Generate signed URL → Cache for 13.5 min

Request 2 (within 13.5 min): /audio/{id}/stream
  └─ Cache HIT → Return cached URL (fast!)
  
Request 3 (after 13.5 min): /audio/{id}/stream
  └─ Cache MISS (expired) → Generate new signed URL
```

---

## Security

### Signed URL Security

- **Time-Limited**: URLs expire after 15 minutes
- **Cryptographically Signed**: GCS validates signature
- **No Credential Exposure**: Credentials never sent to client
- **Cache Safety**: Cache TTL (90%) is shorter than URL expiration

### Best Practices

1. **Short Expiration**: 15 minutes balances security and UX
2. **Cache Timing**: 90% of expiration prevents serving expired URLs
3. **HTTPS Only**: Signed URLs use HTTPS
4. **Access Control**: Database lookup verifies track exists

---

## Performance Optimization

### Recommended Client-Side Caching

```http
# Audio streams (1 hour)
Cache-Control: public, max-age=3600

# Thumbnails (24 hours)
Cache-Control: public, max-age=86400

# Metadata (1 hour)
Cache-Control: public, max-age=3600
```

### Server-Side Optimization

1. **Connection Pooling**: Database connections reused
2. **Signed URL Caching**: Reduces GCS API calls by ~75%
3. **Efficient Database Queries**: Primary key lookups (O(1))
4. **Async Operations**: Non-blocking resource handling

### Performance Targets

| Operation | Target | Actual (Cached) |
|-----------|--------|-----------------|
| Audio stream | <100ms | ~10ms |
| Metadata | <50ms | ~30ms |
| Thumbnail | <100ms | ~10ms |

---

## Integration Examples

### HTML5 Audio Player

```html
<!DOCTYPE html>
<html>
<head>
    <title>Music Player</title>
</head>
<body>
    <div id="player">
        <img id="artwork" src="" alt="Album Artwork">
        <div id="track-info">
            <h2 id="title"></h2>
            <p id="artist"></p>
        </div>
        <audio id="audio-player" controls>
            <source id="audio-source" src="" type="audio/mpeg">
        </audio>
    </div>
    
    <script>
        const audioId = "550e8400-e29b-41d4-a716-446655440000";
        
        // Fetch metadata
        fetch(`music-library://audio/${audioId}/metadata`)
            .then(r => r.json())
            .then(data => {
                document.getElementById('title').textContent = data.Product.Title;
                document.getElementById('artist').textContent = data.Product.Artist;
            });
        
        // Set audio source
        document.getElementById('audio-source').src = 
            `music-library://audio/${audioId}/stream`;
        
        // Set artwork
        document.getElementById('artwork').src = 
            `music-library://audio/${audioId}/thumbnail`;
    </script>
</body>
</html>
```

### Python MCP Client

```python
import asyncio
from mcp import Client

async def play_audio(audio_id: str):
    """Example MCP client usage"""
    
    # Get metadata
    metadata_uri = f"music-library://audio/{audio_id}/metadata"
    metadata_resource = await client.read_resource(metadata_uri)
    metadata = json.loads(metadata_resource.text)
    
    print(f"Now playing: {metadata['Product']['Title']}")
    print(f"By: {metadata['Product']['Artist']}")
    
    # Get stream URL
    stream_uri = f"music-library://audio/{audio_id}/stream"
    stream_resource = await client.read_resource(stream_uri)
    stream_url = stream_resource.uri
    
    # Get thumbnail (if available)
    thumbnail_uri = f"music-library://audio/{audio_id}/thumbnail"
    try:
        thumbnail_resource = await client.read_resource(thumbnail_uri)
        thumbnail_url = thumbnail_resource.uri
        print(f"Artwork: {thumbnail_url}")
    except Exception:
        print("No artwork available")
    
    return stream_url
```

---

## Use Cases

### Use Case 1: Build a Web Player

```typescript
// TypeScript/React example
async function loadTrack(audioId: string) {
  // Fetch metadata
  const metadataUri = `music-library://audio/${audioId}/metadata`;
  const metadata = await mcpClient.readResource(metadataUri);
  
  // Set player state
  setTrackInfo({
    title: metadata.Product.Title,
    artist: metadata.Product.Artist,
    artwork: `music-library://audio/${audioId}/thumbnail`,
    streamUrl: `music-library://audio/${audioId}/stream`
  });
}
```

### Use Case 2: Download for Offline Use

```python
async def download_track(audio_id: str, output_path: str):
    """Download audio file for offline use"""
    import httpx
    
    # Get signed stream URL
    stream_uri = f"music-library://audio/{audio_id}/stream"
    resource = await audio_stream_resource(stream_uri)
    signed_url = resource["uri"]
    
    # Download file
    async with httpx.AsyncClient() as client:
        response = await client.get(signed_url)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
    
    print(f"Downloaded to: {output_path}")
```

### Use Case 3: Batch Metadata Retrieval

```python
async def get_multiple_metadata(audio_ids: List[str]):
    """Fetch metadata for multiple tracks"""
    tasks = [
        metadata_resource(f"music-library://audio/{id}/metadata")
        for id in audio_ids
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    metadata_list = []
    for result in results:
        if isinstance(result, Exception):
            continue  # Skip errors
        metadata_list.append(json.loads(result["text"]))
    
    return metadata_list
```

---

## Security Considerations

### Signed URL Expiration

```python
# URLs expire after 15 minutes
signed_url_expires_at = time.time() + (15 * 60)

# Cache expires slightly earlier (13.5 min) for safety
cache_expires_at = time.time() + (13.5 * 60)
```

### Access Control

Resources verify track exists in database before generating signed URLs:

```python
# Prevents generating URLs for non-existent tracks
metadata = get_audio_metadata_by_id(audio_id)
if not metadata:
    raise ResourceNotFoundError(...)
```

### CORS Policy

Current configuration allows all origins for public audio:

```python
"Access-Control-Allow-Origin": "*"
```

**For production**, restrict to specific domains:

```python
"Access-Control-Allow-Origin": "https://yourdomain.com"
```

---

## Troubleshooting

### Issue: Resource Not Found

**Symptom:** `ResourceNotFoundError: Audio track {id} not found`

**Causes:**
1. Invalid or non-existent audioId
2. Track not yet processed (status != COMPLETED)
3. Track deleted from database

**Solution:**
```python
# Verify track exists first
from database import get_audio_metadata_by_id

metadata = get_audio_metadata_by_id(audio_id)
if not metadata:
    print("Track not found")
elif metadata.get("status") != "COMPLETED":
    print(f"Track still processing: {metadata['status']}")
```

### Issue: Thumbnail Not Available

**Symptom:** `ResourceNotFoundError: Thumbnail not available`

**Cause:** Audio track has no embedded artwork

**Solution:**
```python
# Check if thumbnail exists before requesting
metadata = get_audio_metadata_by_id(audio_id)

if metadata.get("thumbnail_path"):
    # Thumbnail exists
    thumbnail_uri = f"music-library://audio/{audio_id}/thumbnail"
    resource = await thumbnail_resource(thumbnail_uri)
else:
    # Use default artwork
    print("Using default artwork")
```

### Issue: Signed URL Expired

**Symptom:** GCS returns 403 Forbidden

**Cause:** Signed URL expired (>15 minutes old)

**Solution:**
```python
# Request a fresh resource - cache will regenerate
uri = f"music-library://audio/{audio_id}/stream"
resource = await audio_stream_resource(uri)
# New signed URL generated automatically
```

### Issue: Cache Performance

**Symptom:** Low cache hit rate

**Investigation:**
```python
from src.resources.cache import get_cache

cache = get_cache()
stats = cache.get_stats()

print(f"Hit rate: {stats['hit_rate_percent']}%")

if stats['hit_rate_percent'] < 50:
    print("Low cache hit rate - consider:")
    print("- Increasing cache TTL")
    print("- Checking request patterns")
    print("- Verifying same URIs are used")
```

---

## Monitoring

### Cache Statistics

Monitor cache performance:

```python
# Get stats periodically
stats = get_cache().get_stats()

# Log to monitoring system
logger.info(f"Cache stats: {stats}")

# Alert on low hit rate
if stats['hit_rate_percent'] < 60:
    logger.warning("Low cache hit rate")
```

### Resource Access Logging

All resource handlers log:

```
INFO: Audio stream resource requested: music-library://audio/{id}/stream
DEBUG: Requesting audio stream for ID: 550e8400-...
INFO: Generated signed URL for 550e8400-... (format: MP3)
```

### Performance Metrics

Track these metrics:

- **Resource request rate**: Requests per second
- **Cache hit rate**: Percentage of cached requests
- **Response time**: P50, P95, P99
- **Error rate**: Failed requests percentage

---

## Best Practices

### 1. Cache Signed URLs

```python
# ✅ Good: Let the cache handle it
uri = f"music-library://audio/{audio_id}/stream"
resource = await audio_stream_resource(uri)
```

### 2. Check Thumbnail Availability

```python
# ✅ Good: Check before requesting
metadata = await get_metadata_resource(metadata_uri)
data = json.loads(metadata["text"])

if data["resources"]["thumbnail"]:
    thumbnail = await thumbnail_resource(thumbnail_uri)
```

### 3. Handle Errors Gracefully

```python
# ✅ Good: Catch and handle errors
try:
    resource = await audio_stream_resource(uri)
except ResourceNotFoundError:
    # Show default content
    print("Track not found - showing default")
except Exception as e:
    # Log and show error
    logger.error(f"Resource error: {e}")
```

### 4. Use Appropriate Cache Headers

```python
# ✅ Good: Respect cache headers
# Audio streams: 1 hour (content doesn't change)
# Thumbnails: 24 hours (images rarely change)
# Metadata: 1 hour (balance freshness and performance)
```

---

## Related Documentation

- [Query Tools API](./query-tools-api.md) - get_audio_metadata and search_library
- [Process Audio API](./process-audio-complete-api.md) - Audio ingestion
- [GCS Organization](./gcs-organization-structure.md) - Storage structure

---

## API Summary

| Resource | URI Pattern | Returns | Cacheable | Range Support |
|----------|-------------|---------|-----------|---------------|
| Audio Stream | `music-library://audio/{id}/stream` | Signed GCS URL | Yes (13.5 min) | Yes |
| Metadata | `music-library://audio/{id}/metadata` | JSON metadata | Yes (1 hour) | No |
| Thumbnail | `music-library://audio/{id}/thumbnail` | Signed GCS URL | Yes (13.5 min) | No |

---

**Last Updated:** 2025-10-11  
**Version:** 1.0  
**Status:** Production Ready

<<<<<<< HEAD
=======


>>>>>>> task-10-html5-audio-player
