# process_audio_complete API Documentation

## Overview

The `process_audio_complete` MCP tool orchestrates the complete audio processing pipeline for the Loist Music Library MCP Server. It handles downloading, metadata extraction, storage, and database persistence in a single atomic operation.

## Pipeline Stages

The tool executes the following stages in sequence:

1. **Input Validation** - Validates input schema using Pydantic
2. **HTTP Download** - Downloads audio from URL with SSRF protection
3. **Metadata Extraction** - Extracts ID3 tags, XMP metadata, BWF data, and technical specifications
4. **Storage Upload** - Uploads audio and artwork to Google Cloud Storage
5. **Database Persistence** - Saves metadata to PostgreSQL database
6. **Response Formatting** - Returns structured response with resource URIs

## Input Schema

### Required Fields

```json
{
  "source": {
    "type": "http_url",
    "url": "https://example.com/audio.mp3"
  }
}
```

### Complete Schema

```typescript
{
  source: {
    type: "http_url",            // Source type (currently only http_url supported)
    url: string,                 // HTTP/HTTPS URL to audio file
    headers?: {[key: string]: string},  // Optional HTTP headers
    filename?: string,           // Optional filename override
    mimeType?: string           // Optional MIME type
  },
  options?: {
    maxSizeMB?: number,         // Maximum file size in MB (default: 100, max: 500)
    timeout?: number,           // Download timeout in seconds (default: 300, max: 600)
    validateFormat?: boolean    // Whether to validate audio format (default: true)
  }
}
```

## Output Schema

### Success Response

```json
{
  "success": true,
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
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
      "Sample rate": 44100,
      "Bitrate": 320000,
      "Format": "MP3"
    },
    "urlEmbedLink": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform": null
  },
  "processingTime": 2.45
}
```

### Error Response

```json
{
  "success": false,
  "error": "SIZE_EXCEEDED",
  "message": "Audio file exceeds maximum size limit of 100 MB",
  "details": {
    "max_size_mb": 100,
    "actual_size_mb": 150
  }
}
```

## Error Codes

| Error Code | Description | HTTP Equivalent |
|-----------|-------------|-----------------|
| `VALIDATION_ERROR` | Invalid input data | 400 Bad Request |
| `SIZE_EXCEEDED` | File exceeds size limit | 413 Payload Too Large |
| `INVALID_FORMAT` | Unsupported audio format | 415 Unsupported Media Type |
| `FETCH_FAILED` | Download failed | 502 Bad Gateway |
| `TIMEOUT` | Download timeout | 504 Gateway Timeout |
| `EXTRACTION_FAILED` | Metadata extraction failed | 422 Unprocessable Entity |
| `STORAGE_FAILED` | Storage upload failed | 500 Internal Server Error |
| `DATABASE_FAILED` | Database operation failed | 500 Internal Server Error |

## Usage Examples

### Python (Async)

```python
from src.tools import process_audio_complete

# Basic usage
result = await process_audio_complete({
    "source": {
        "type": "http_url",
        "url": "https://example.com/song.mp3"
    }
})

if result["success"]:
    print(f"Audio ID: {result['audioId']}")
    print(f"Artist: {result['metadata']['Product']['Artist']}")
    print(f"Title: {result['metadata']['Product']['Title']}")
else:
    print(f"Error: {result['error']} - {result['message']}")
```

### With Custom Options

```python
result = await process_audio_complete({
    "source": {
        "type": "http_url",
        "url": "https://example.com/large-file.flac",
        "headers": {
            "Authorization": "Bearer token123"
        }
    },
    "options": {
        "maxSizeMB": 200,
        "timeout": 600,
        "validateFormat": True
    }
})
```

### MCP Protocol (JSON-RPC)

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "process_audio_complete",
    "arguments": {
      "source": {
        "type": "http_url",
        "url": "https://example.com/audio.mp3"
      },
      "options": {
        "maxSizeMB": 100
      }
    }
  },
  "id": 1
}
```

## Best Practices

### 1. Always Handle Errors

```python
result = await process_audio_complete(input_data)

if not result["success"]:
    error_code = result["error"]
    
    if error_code == "SIZE_EXCEEDED":
        # Handle large file
        pass
    elif error_code == "TIMEOUT":
        # Retry with longer timeout
        pass
    elif error_code == "INVALID_FORMAT":
        # Notify user of unsupported format
        pass
```

### 2. Set Appropriate Timeouts

```python
# For large files or slow connections
options = {
    "maxSizeMB": 200,
    "timeout": 600  # 10 minutes
}
```

### 3. Use Custom Headers for Protected URLs

```python
source = {
    "type": "http_url",
    "url": "https://protected.example.com/audio.mp3",
    "headers": {
        "Authorization": "Bearer YOUR_TOKEN",
        "User-Agent": "LoisT MusicLibrary/1.0"
    }
}
```

### 4. Monitor Processing Time

```python
result = await process_audio_complete(input_data)

if result["success"]:
    processing_time = result["processingTime"]
    
    if processing_time > 30:
        # Log slow processing for optimization
        logger.warning(f"Slow processing: {processing_time}s")
```

## Performance Considerations

### Processing Times

- **Small files (< 10MB)**: 1-5 seconds
- **Medium files (10-50MB)**: 5-15 seconds  
- **Large files (50-100MB)**: 15-30 seconds

### Optimizations

1. **Async Processing**: The tool uses async/await for efficient I/O
2. **Streaming Download**: Downloads stream to disk (no memory buffering)
3. **Parallel Uploads**: Audio and artwork upload in sequence (could be parallelized)
4. **Database Pooling**: Uses connection pooling for efficient database access

### Resource Limits

- **Max file size**: 500 MB (configurable)
- **Max timeout**: 600 seconds (10 minutes)
- **Concurrent requests**: Limited by database connection pool (default: 10)

## Security

### SSRF Protection

The tool automatically validates URLs to prevent Server-Side Request Forgery (SSRF) attacks:

- ✅ Blocks private IP ranges (10.x.x.x, 192.168.x.x, 172.16.x.x)
- ✅ Blocks localhost (127.x.x.x, ::1)
- ✅ Blocks link-local addresses (169.254.x.x)
- ✅ Blocks cloud metadata endpoints

### URL Validation

Only HTTP and HTTPS URLs are accepted:
- ✅ `https://example.com/audio.mp3`
- ✅ `http://example.com/audio.mp3`
- ❌ `file:///etc/passwd`
- ❌ `ftp://example.com/audio.mp3`

### File Type Validation

When `validateFormat: true` (default), the tool verifies:
- File has valid audio MIME type
- File can be parsed by metadata extractor
- Format is supported (MP3, FLAC, M4A, OGG, WAV, AIF, AIFF, AAC)

### Metadata Extraction Capabilities

The tool extracts metadata using multiple fallback strategies:

#### Primary Metadata Sources
- **ID3 Tags** (MP3, AIF/AIFF): Artist, title, album, genre, year, composer, publisher
- **Vorbis Comments** (FLAC, OGG): Artist, title, album, genre, year
- **MP4 Tags** (M4A, AAC): Artist, title, album, genre, year
- **RIFF INFO** (WAV): Basic metadata chunks

#### Enhanced Metadata Sources
- **XMP Metadata** (WAV, AIF/AIFF): Rich metadata from professional tools (Adobe Audition, Logic Pro, Pro Tools)
  - Music fields: composer, publisher, record_label, ISRC, copyright
  - BWF fields: originator, origination_date, description
  - iXML fields: scene, take, project, speed (DAW session metadata)
- **Broadcast WAV (BWF)** (WAV): Professional broadcast metadata
- **Filename Parsing**: Extracts artist/title from filename patterns when metadata is missing

#### AIF/AIFF XMP Support
AIF files support XMP metadata embedded in custom chunks:
- **Custom Chunks**: 'XMP ', 'iXML' chunks detected by ExifTool
- **DAW Compatibility**: Preserves metadata from Logic Pro, Pro Tools, Adobe Audition
- **Archival Integrity**: XMP used as enhancement only, never overwrites existing ID3 tags
- **Smart Extraction**: XMP attempted only when basic metadata is incomplete (<2 essential fields)

#### Metadata Quality Assessment
- **Essential Fields**: artist, title, album (required for quality)
- **Optional Fields**: genre, year, composer, publisher, etc.
- **Quality Scoring**: 0.0-1.0 scale based on completeness
- **Fallback Handling**: Filename parsing when metadata is missing

## Transaction Management

### Atomic Operations

The tool uses transaction-like semantics:

1. **Database Status Tracking**: Status is updated throughout the pipeline
   - PENDING → PROCESSING → COMPLETED (success)
   - PENDING → PROCESSING → FAILED (error)

2. **Rollback on Failure**: On any error:
   - Temporary files are deleted
   - Database status marked as FAILED
   - GCS files remain (for debugging)

3. **Cleanup Guarantees**: Uses context managers to ensure cleanup even on exceptions

### Idempotency

- Each call generates a new unique audio ID
- Not idempotent by design (multiple calls = multiple entries)
- Implement deduplication at the application level if needed

## Monitoring & Debugging

### Logging

The tool provides detailed logging at multiple levels:

```python
# DEBUG: Detailed progress through pipeline
logger.debug("Extracted metadata: {...}")

# INFO: Major milestones
logger.info("Audio processing completed in 2.45s")

# WARNING: Non-fatal issues
logger.warning("Failed to extract artwork")

# ERROR: Fatal errors
logger.error("Processing failed: Download timeout")
```

### Status Tracking

Query database to monitor processing status:

```sql
SELECT id, status, created_at, updated_at, error_message
FROM audio_tracks
WHERE status = 'PROCESSING'
AND updated_at < NOW() - INTERVAL '5 minutes';
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow processing | Large file or slow network | Increase timeout, monitor `processingTime` |
| Format errors | Unsupported or corrupted file | Validate format before calling tool |
| Storage failures | GCS permissions or quota | Check service account permissions |
| Database errors | Connection pool exhaustion | Increase pool size or reduce concurrency |

## Migration Notes

### From MVP to Production

Current MVP limitations:

1. ❌ `MBID` (MusicBrainz ID) - Always null
2. ❌ `waveform` - Always null
3. ⚠️ GCS files not deleted on error (manual cleanup needed)

Future enhancements:

1. ✅ Add MusicBrainz API integration for MBID lookup
2. ✅ Generate waveform visualization
3. ✅ Implement GCS lifecycle policies for auto-cleanup
4. ✅ Add batch processing for multiple files
5. ✅ Add progress callbacks for long-running uploads

## Related Documentation

- [API Contract Specification](./api-contract.md)
- [Database Schema](./database-schema.md)
- [GCS Storage Organization](./gcs-organization-structure.md)
- [Error Handling Guide](./error-handling.md)

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify all dependencies are installed
3. Ensure database and GCS are accessible
4. Open an issue with reproducible example

