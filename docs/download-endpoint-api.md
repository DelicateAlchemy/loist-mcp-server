# Download Endpoint API Documentation

## Overview

The download endpoint provides on-the-fly audio format conversion with metadata and artwork embedding. It supports multiple output formats (MP3, WAV, FLAC, AAC, OGG) with quality presets optimized for different use cases.

## Implementation Status ✅ **LIVE & WORKING**

**Status**: Successfully implemented and deployed (November 2025)

**Features Confirmed Working**:
- ✅ All 5 output formats (MP3, WAV, FLAC, AAC, OGG)
- ✅ Quality presets for each format
- ✅ Metadata embedding (ID3, BWF, Vorbis, iTunes)
- ✅ Short-circuit optimization for same-format requests
- ✅ Comprehensive error handling and validation
- ✅ Both HTTP API and MCP tool interfaces
- ⚠️ Artwork embedding (works for short-circuit, has issues with cross-format conversion)

**Testing**: Verified with real audio files, metadata correctly embedded, error responses working properly.

## Protocol Access Methods

The download functionality is available through two primary methods: the canonical MCP JSON-RPC protocol for agentic use and a direct HTTP GET endpoint for convenience, particularly for browser-based downloads.

### MCP JSON-RPC (Canonical)

The `download_audio` tool is the canonical way to access this functionality for programmatic and agentic workflows. It returns a signed URL to the converted file.

```json
{
  "name": "download_audio",
  "description": "Download audio track in specified format with conversion",
  "inputSchema": {
    "type": "object",
    "properties": {
      "audioId": { "type": "string" },
      "format": { "type": "string", "enum": ["mp3", "wav", "flac", "aac", "ogg"] }
    },
    "required": ["audioId", "format"]
  }
}
```

### HTTP REST API (Convenience Wrapper)

For direct browser downloads, a `GET /api/v1/tracks/{audioId}/download` endpoint is provided. This endpoint directly serves the file with appropriate `Content-Disposition` headers, making it easy to integrate with web frontends. This endpoint and the MCP `download_audio` tool are independent interfaces over the same shared download service (`src/services/download_service.py`).

## HTTP API Endpoint

### `GET /api/v1/tracks/{audioId}/download`

Download an audio track in the specified format with on-the-fly conversion.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audioId` | path | Yes | UUID of the audio track |
| `format` | query | Yes | Target format: `mp3`, `wav`, `flac`, `aac`, `ogg` |
| `preset` | query | No | Quality preset (defaults to `high`) |

#### Supported Formats & Presets

##### MP3 Presets
| Preset | Bitrate | Use Case |
|--------|---------|----------|
| `high` (default) | 320 kbps | Highest quality lossy compression |
| `standard` | 192 kbps | Good quality, smaller file size |
| `compact` | 128 kbps | Minimum acceptable quality |

##### WAV Presets
| Preset | Sample Rate | Bit Depth | Use Case |
|--------|-------------|-----------|----------|
| `broadcast` (default) | 48 kHz | 24-bit | Broadcast standard with BWF metadata |
| `cd` | 44.1 kHz | 16-bit | CD quality |
| `high` | 96 kHz | 24-bit | Studio quality |

##### FLAC Presets
| Preset | Compression | Use Case |
|--------|-------------|----------|
| `high` (default) | Level 8 | Best compression ratio |
| `fast` | Level 0 | Fastest encoding |

##### AAC Presets
| Preset | Bitrate | Use Case |
|--------|---------|----------|
| `high` (default) | 256 kbps | High quality for Apple devices |
| `standard` | 192 kbps | Standard quality |

##### OGG Vorbis Presets
| Preset | Quality | Use Case |
|--------|---------|----------|
| `high` (default) | Q8 (~256 kbps VBR) | High quality open format |
| `standard` | Q5 (~160 kbps VBR) | Standard quality |

#### Request Examples

```bash
# Download as high-quality MP3
GET /api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=mp3

# Download as broadcast WAV
GET /api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=wav&preset=broadcast

# Download as lossless FLAC
GET /api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=flac

# Download as AAC for Apple devices
GET /api/v1/tracks/550e8400-e29b-41d4-a716-446655440000/download?format=aac
```

#### Response

**Success Response (200 OK):**
- **Content-Type**: `audio/mpeg`, `audio/wav`, `audio/flac`, `audio/aac`, or `audio/ogg`
- **Content-Disposition**: `attachment; filename="Track Title - Artist.mp3"`
- **Content-Length**: File size in bytes
- **X-Conversion-Time**: Processing time in seconds (custom header)
- **Body**: Audio file with embedded metadata and artwork

**Short-circuit Response (302 Found):**
- Returned when no conversion is needed (same format, compatible quality)
- **Location**: Signed GCS URL for direct download
- Redirects to the original file

**Error Responses:**
- `400 Bad Request`: Invalid format, preset, or audioId
- `404 Not Found`: Track not found
- `500 Internal Server Error`: Conversion failed
- `504 Gateway Timeout`: Conversion timed out

#### Error Response Format

```json
{
  "success": false,
  "message": "Error description",
  "error": "ERROR_CODE",
  "supportedFormats": ["mp3", "wav", "flac", "aac", "ogg"]
}
```

## MCP Tool API

### `download_audio` Tool

The download functionality is also available as an MCP tool for AI assistants.

#### Tool Schema

```json
{
  "name": "download_audio",
  "description": "Download audio track in specified format with conversion",
  "inputSchema": {
    "type": "object",
    "properties": {
      "audioId": {
        "type": "string",
        "description": "UUID of the audio track"
      },
      "format": {
        "type": "string",
        "enum": ["mp3", "wav", "flac", "aac", "ogg"],
        "description": "Target audio format"
      },
      "preset": {
        "type": "string",
        "description": "Quality preset (format-specific, defaults to 'high')"
      }
    },
    "required": ["audioId", "format"]
  }
}
```

#### Tool Response

```json
{
  "success": true,
  "downloadUrl": "https://storage.googleapis.com/bucket/temp/...",
  "format": "mp3",
  "quality": "320kbps",
  "originalFormat": "wav",
  "fileSize": 12345678,
  "filename": "Song Title - Artist.mp3",
  "expiresIn": 900
}
```

## Metadata Embedding

### Supported Metadata Fields

Converted files include the following metadata embedded in format-appropriate tags:

| Database Field | MP3 (ID3) | WAV (RIFF/BWF) | FLAC (Vorbis) | AAC (iTunes) | OGG (Vorbis) |
|----------------|-----------|----------------|---------------|--------------|--------------|
| `title` | TIT2 | INAM | TITLE | ©nam | TITLE |
| `artist` | TPE1 | IART | ARTIST | ©ART | ARTIST |
| `album` | TALB | IPRD | ALBUM | ©alb | ALBUM |
| `album_artist` | TPE2 | — | ALBUMARTIST | aART | ALBUMARTIST |
| `genre` | TCON | IGNR | GENRE | ©gen | GENRE |
| `year` | TDRC | ICRD | DATE | ©day | DATE |
| `track_number` | TRCK | ITRK | TRACKNUMBER | trkn | TRACKNUMBER |
| `composer` | TCOM | — | COMPOSER | ©wrt | COMPOSER |
| `publisher` | TPUB | — | PUBLISHER | — | PUBLISHER |
| `isrc` | TSRC | ISRC | ISRC | — | ISRC |

### Artwork Embedding

Album artwork is embedded when available and supported by the target format:

- **MP3**: ID3v2 APIC frames
- **AAC/M4A**: iTunes `covr` atom
- **FLAC**: PICTURE metadata block
- **OGG**: METADATA_BLOCK_PICTURE
- **WAV**: Not supported (artwork remains external)

### Character Encoding

All metadata uses UTF-8 encoding internally. FFmpeg handles conversion to format-specific encodings (ID3 frame encodings, etc.).

## Implementation Details

### Conversion Process

1. **Validation**: Check audioId, format, and preset validity
2. **Database Lookup**: Fetch track metadata and GCS paths
3. **Short-circuit Check**: Redirect to original if no conversion needed
4. **Download Source**: Fetch audio file from GCS to temp storage
5. **Artwork Download**: Fetch artwork if available and supported
6. **FFmpeg Conversion**: Convert with metadata and artwork embedding
7. **Upload Result**: Store converted file in GCS temp location
8. **Signed URL**: Generate temporary download URL
9. **Cleanup**: Remove temp files after response

### Performance Characteristics

- **Typical Conversion Time**: 5-30 seconds depending on file size and format
- **Memory Usage**: Streaming processing (no large files in memory)
- **Temp Storage**: Files stored temporarily during conversion
- **Timeout**: 5 minutes maximum per conversion
- **Concurrent Requests**: Handled by Cloud Run scaling

### Error Handling

- **Track Not Found**: 404 with clear error message
- **Invalid Parameters**: 400 with validation details
- **Conversion Failure**: 500 with error details
- **Timeout**: 504 when conversion exceeds time limit
- **GCS Errors**: 500 for storage-related failures

### Security Considerations

- **Input Validation**: Strict parameter validation
- **Path Safety**: Sanitized file paths and names
- **Resource Limits**: File size and conversion time limits
- **Temp File Cleanup**: Automatic cleanup on success/error
- **No Arbitrary Commands**: Predefined FFmpeg argument sets only

## Usage Examples

### Frontend Integration

```javascript
// Download as MP3
const response = await fetch(`/api/v1/tracks/${audioId}/download?format=mp3`);
if (response.ok) {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '');
    a.click();
}
```

### AI Assistant Integration

```javascript
// Using MCP tool
const result = await mcp.call("download_audio", {
    audioId: "550e8400-e29b-41d4-a716-446655440000",
    format: "wav",
    preset: "broadcast"
});

if (result.success) {
    console.log(`Download ready: ${result.downloadUrl}`);
    console.log(`Expires in: ${result.expiresIn} seconds`);
}
```

## Testing

### Postman Collection

The download endpoints are included in the Postman collection:
- `HTTP API Endpoints > Download Audio Track - MP3`
- `HTTP API Endpoints > Download Audio Track - WAV`
- `HTTP API Endpoints > Download Audio Track - FLAC`
- `MCP Tools > Download Audio`

### Unit Tests

Comprehensive unit tests cover:
- Metadata mapping for all formats
- FFmpeg command generation
- Error handling and validation
- Character encoding and escaping

---

**Related Documentation:**
- [Download Endpoint Investigation](download-endpoint-investigation.md) - Technical design details
- [Frontend API Integration Guide](frontend-api-integration.md) - Client integration examples
- [MCP Testing Guide](mcp-testing-guide.md) - Testing MCP tools

**Last Updated**: November 30, 2025
