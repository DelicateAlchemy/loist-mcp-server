# Audio Download Endpoint with Format Conversion - Investigation

> **Document Purpose**: Context for implementing an audio download endpoint with on-the-fly format conversion for the Loist Music Library MCP Server. Designed for an LLM planning agent to create implementation tasks.
>
> **MVP Mindset**: High-quality presets, no caching, fresh conversion each time.

---

## Executive Summary

### Current Capabilities
- ✅ **Upload & Store**: Audio files stored in GCS (`audio/{uuid}/audio.{ext}`)
- ✅ **Stream**: Signed URL generation for streaming original format
- ✅ **FFmpeg Available**: Already installed in Docker container (used for waveform generation)
- ❌ **Download with Conversion**: NOT YET IMPLEMENTED

### Proposed Feature
A download endpoint that:
1. Takes an `audioId` and desired output `format` (with quality preset)
2. Downloads source file from GCS to temp storage
3. Converts using FFmpeg to requested format
4. Returns converted file for download
5. Cleans up temp files (no caching)

### Use Cases
- **MCP/Claude Integration**: Request downloads in specific formats
- **External System Integration**: REST API for frontend or third-party apps
- **Format Flexibility**: Source may be WAV, but user needs MP3 for sharing

---

## Current Architecture Analysis

### Storage Structure (GCS)

```
gs://{bucket}/
├── audio/
│   └── {uuid}/
│       ├── audio.mp3         # Original uploaded file
│       ├── artwork.jpg       # Extracted album art (optional)
│       └── {content_hash}.svg # Waveform (in waveforms/ folder)
```

**Key Observations**:
- Original format preserved on upload
- No pre-rendered alternative formats
- Source files accessible via GCS client or signed URLs

### FFmpeg Integration (Existing)

```python
# From src/waveform/generator.py - FFmpeg usage pattern
cmd = [
    "ffmpeg",
    "-i", str(audio_path),       # Input file
    "-ac", "1",                   # Convert to mono
    "-f", "f32le",                # Output format
    "-acodec", "pcm_f32le",       # Audio codec
    "-"                           # Output to stdout
]

result = subprocess.run(
    cmd,
    capture_output=True,
    check=True,
    timeout=60  # 60 second timeout
)
```

**Key Observations**:
- FFmpeg subprocess pattern already established
- 60-second timeout used for audio processing
- Error handling pattern exists
- Can capture output to stdout or write to file

### Existing Download/Stream Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT STREAMING FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Client Request                                                  │
│       │                                                          │
│       ▼                                                          │
│  /api/tracks/{audioId}/stream                                    │
│       │                                                          │
│       ▼                                                          │
│  get_audio_stream_resource()                                     │
│       │                                                          │
│       ├──► Database: Get audio_gcs_path for audioId              │
│       │                                                          │
│       ├──► GCS: Generate signed URL (15 min expiry)              │
│       │                                                          │
│       ▼                                                          │
│  Return: { uri: signed_url, mimeType: "audio/mpeg" }            │
│       │                                                          │
│       ▼                                                          │
│  Client redirects to signed GCS URL                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### HTTP API Pattern (Existing)

```python
# From src/http_api.py - Endpoint registration pattern
@mcp.custom_route("/api/tracks/{audioId}", methods=["GET"])
async def get_track(request: Request) -> JSONResponse:
    audio_id = request.path_params.get("audioId")
    # ... validation, processing, response
```

---

## Proposed Download Endpoint Design

### Endpoint Specification

```
GET /api/tracks/{audioId}/download?format={format}&preset={preset}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audioId` | path | Yes | UUID of the audio track |
| `format` | query | Yes | Target format: `mp3`, `wav`, `flac`, `aac`, `ogg` |
| `preset` | query | No | Quality preset (defaults to `high`) |

**Example Requests**:
```bash
# Download as 320kbps MP3
GET /api/tracks/550e8400-.../download?format=mp3

# Download as broadcast WAV (48kHz)
GET /api/tracks/550e8400-.../download?format=wav&preset=broadcast

# Download as high-quality FLAC
GET /api/tracks/550e8400-.../download?format=flac
```

### Quality Presets

#### MP3 Presets
| Preset | Bitrate | Sample Rate | Use Case |
|--------|---------|-------------|----------|
| `high` (default) | 320 kbps | Source | Highest quality lossy |
| `standard` | 192 kbps | Source | Good quality, smaller size |
| `compact` | 128 kbps | Source | Minimum acceptable quality |

**FFmpeg Command (MP3 320kbps)**:
```bash
ffmpeg -i input.wav -codec:a libmp3lame -b:a 320k -ar {source_rate} output.mp3
```

#### WAV Presets
| Preset | Sample Rate | Bit Depth | Use Case |
|--------|-------------|-----------|----------|
| `broadcast` (default) | 48000 Hz | 24-bit | Broadcast standard |
| `cd` | 44100 Hz | 16-bit | CD quality |
| `high` | 96000 Hz | 24-bit | Studio quality (if source supports) |

**FFmpeg Command (WAV Broadcast)**:
```bash
ffmpeg -i input.mp3 -acodec pcm_s24le -ar 48000 output.wav
```

#### FLAC Presets
| Preset | Compression | Sample Rate | Use Case |
|--------|-------------|-------------|----------|
| `high` (default) | Level 8 | Source | Best compression |
| `fast` | Level 0 | Source | Fastest encode |

**FFmpeg Command (FLAC High)**:
```bash
ffmpeg -i input.mp3 -codec:a flac -compression_level 8 output.flac
```

#### AAC Presets
| Preset | Bitrate | Use Case |
|--------|---------|----------|
| `high` (default) | 256 kbps | High quality |
| `standard` | 192 kbps | Good quality |

**FFmpeg Command (AAC High)**:
```bash
ffmpeg -i input.wav -codec:a aac -b:a 256k output.m4a
```

#### OGG Vorbis Presets
| Preset | Quality | Use Case |
|--------|---------|----------|
| `high` (default) | Q8 (~256 kbps VBR) | High quality |
| `standard` | Q5 (~160 kbps VBR) | Good quality |

**FFmpeg Command (OGG High)**:
```bash
ffmpeg -i input.wav -codec:a libvorbis -qscale:a 8 output.ogg
```

---

## Implementation Architecture

### Proposed Flow

```
┌─────────────────────────────────────────────────────────────────┐
│               PROPOSED DOWNLOAD WITH CONVERSION FLOW             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Client Request                                                  │
│  GET /api/tracks/{id}/download?format=mp3&preset=high           │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 1. VALIDATION                           │                    │
│  │    - Validate audioId (UUID format)     │                    │
│  │    - Validate format parameter          │                    │
│  │    - Validate preset (or use default)   │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 2. DATABASE LOOKUP                      │                    │
│  │    - Fetch audio_gcs_path               │                    │
│  │    - Fetch source format/metadata       │                    │
│  │    - Verify track exists & COMPLETED    │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 3. SHORT-CIRCUIT CHECK                  │                    │
│  │    - If source format == target format  │                    │
│  │      AND no quality change needed:      │                    │
│  │      → Redirect to signed URL           │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼ (conversion needed)                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │ 4. DOWNLOAD SOURCE FROM GCS             │                    │
│  │    - Download to temp file              │                    │
│  │    - Verify file integrity              │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 5. FFMPEG CONVERSION                    │                    │
│  │    - Build FFmpeg command from preset   │                    │
│  │    - Execute with timeout (5 minutes)   │                    │
│  │    - Output to temp file                │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 6. STREAMING RESPONSE                   │                    │
│  │    - Set Content-Type header            │                    │
│  │    - Set Content-Disposition (filename) │                    │
│  │    - Stream converted file to client    │                    │
│  │    - Cleanup temp files on completion   │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  Client receives converted audio file                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### File Organization

```
src/
├── downloader/
│   ├── __init__.py
│   ├── http_downloader.py      # Existing HTTP download
│   └── gcs_downloader.py       # NEW: Download from GCS to temp file
│
├── converter/                   # NEW MODULE
│   ├── __init__.py
│   ├── ffmpeg_converter.py     # FFmpeg conversion wrapper
│   ├── presets.py              # Quality preset definitions
│   └── formats.py              # Format-specific configurations
│
├── tools/
│   └── download_tool.py        # NEW: MCP tool for downloads
│
└── http_api.py                 # Add new /download endpoint
```

### Key Components

#### 1. Preset Configuration (`converter/presets.py`)

```python
# Example structure - not actual implementation
PRESETS = {
    "mp3": {
        "high": {"bitrate": "320k", "codec": "libmp3lame"},
        "standard": {"bitrate": "192k", "codec": "libmp3lame"},
        "compact": {"bitrate": "128k", "codec": "libmp3lame"},
    },
    "wav": {
        "broadcast": {"sample_rate": 48000, "bit_depth": 24, "codec": "pcm_s24le"},
        "cd": {"sample_rate": 44100, "bit_depth": 16, "codec": "pcm_s16le"},
        "high": {"sample_rate": 96000, "bit_depth": 24, "codec": "pcm_s24le"},
    },
    "flac": {
        "high": {"compression_level": 8, "codec": "flac"},
        "fast": {"compression_level": 0, "codec": "flac"},
    },
    # ... more formats
}
```

#### 2. FFmpeg Converter (`converter/ffmpeg_converter.py`)

```python
# Example interface - not actual implementation
class FFmpegConverter:
    async def convert(
        self,
        source_path: Path,
        output_path: Path,
        target_format: str,
        preset: str = "high",
        timeout_seconds: int = 300,
    ) -> ConversionResult:
        """
        Convert audio file using FFmpeg.
        
        Returns:
            ConversionResult with success status, output path, 
            processing time, output size
        """
        pass
```

#### 3. HTTP Endpoint (`http_api.py` addition)

```python
# Example structure - not actual implementation
@mcp.custom_route("/api/tracks/{audioId}/download", methods=["GET"])
async def download_audio(request: Request) -> Response:
    """
    Download audio file with optional format conversion.
    
    Query params:
    - format: Target format (mp3, wav, flac, aac, ogg)
    - preset: Quality preset (high, standard, etc.)
    
    Returns:
    - StreamingResponse with converted audio file
    - OR redirect to signed URL if no conversion needed
    """
    pass
```

#### 4. MCP Tool (`tools/download_tool.py`)

```python
# Example interface - not actual implementation
async def download_audio_tool(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool for downloading audio in specified format.
    
    Input:
    {
        "audioId": "550e8400-...",
        "format": "mp3",
        "preset": "high"  # optional
    }
    
    Output:
    {
        "success": true,
        "downloadUrl": "https://...",  # Temporary signed URL
        "format": "mp3",
        "quality": "320kbps",
        "expiresIn": 300  # seconds
    }
    """
    pass
```

---

## Technical Considerations

### 1. Timeout Management

| Operation | Recommended Timeout | Notes |
|-----------|---------------------|-------|
| GCS Download | 120 seconds | Large files may take time |
| FFmpeg Conversion | 300 seconds | WAV to FLAC can be slow |
| Total Request | 600 seconds | Cloud Run max is 3600s |

### 2. Memory Management

**Challenge**: Large audio files (100MB+ WAV) in memory.

**Solution**: Stream-based processing
- Download GCS → temp file (not memory)
- FFmpeg reads temp file → writes temp file
- Stream response from temp file
- Cleanup temp files after response completes

### 3. Temp File Cleanup

```python
# Pattern from existing code (src/tools/process_audio.py)
@contextmanager
def managed_temp_files(*temp_paths):
    """Context manager for automatic cleanup."""
    try:
        yield
    finally:
        for path in temp_paths:
            if path and Path(path).exists():
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup: {e}")
```

### 4. Error Handling

| Error Scenario | HTTP Status | Error Code |
|----------------|-------------|------------|
| Track not found | 404 | `TRACK_NOT_FOUND` |
| Invalid format | 400 | `INVALID_FORMAT` |
| Invalid preset | 400 | `INVALID_PRESET` |
| Conversion failed | 500 | `CONVERSION_FAILED` |
| Timeout | 504 | `CONVERSION_TIMEOUT` |
| Source file missing | 500 | `SOURCE_FILE_MISSING` |

### 5. Content-Disposition Headers

```
Content-Disposition: attachment; filename="Track Title - Artist.mp3"
Content-Type: audio/mpeg
Content-Length: 12345678
```

**Filename Generation**:
```python
# Sanitize metadata for filename
def generate_download_filename(metadata: dict, format: str) -> str:
    title = sanitize_filename(metadata.get("title", "Unknown"))
    artist = sanitize_filename(metadata.get("artist", "Unknown Artist"))
    return f"{title} - {artist}.{format}"
```

### 6. Concurrent Request Handling

**Concern**: Multiple simultaneous conversion requests could overwhelm CPU.

**Mitigation Options** (for future consideration):
- Rate limiting per user/IP
- Queue system for conversions (async with callback URL)
- Cloud Run CPU scaling (current approach: let Cloud Run handle it)

---

## Security Considerations

### 1. Input Validation

- **audioId**: Must be valid UUID format
- **format**: Must be in allowed list (`mp3`, `wav`, `flac`, `aac`, `ogg`)
- **preset**: Must be valid for the selected format
- **No path traversal**: FFmpeg commands use sanitized paths only

### 2. FFmpeg Security

```python
# NEVER allow user input in FFmpeg commands
# BAD: subprocess.run(f"ffmpeg -i {user_input} ...")
# GOOD: Pass as list with validated paths
cmd = ["ffmpeg", "-i", str(validated_source_path), ...]
```

### 3. Resource Limits

- Max file size for conversion: 500MB (configurable)
- Max conversion duration: 5 minutes
- Temp storage cleanup: Immediate after response

### 4. Authentication

- Inherit existing auth pattern from `http_api.py`
- Bearer token authentication when `AUTH_ENABLED=true`
- All endpoints protected equally

---

## MCP Integration

### Tool Schema

```json
{
  "name": "download_audio",
  "description": "Download an audio track in a specific format with quality conversion",
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
        "enum": ["high", "standard", "compact", "broadcast", "cd", "fast"],
        "description": "Quality preset (format-specific, defaults to 'high')"
      }
    },
    "required": ["audioId", "format"]
  }
}
```

### Example MCP Interaction

```javascript
// Claude requesting MP3 download
await mcp.call("download_audio", {
  audioId: "550e8400-e29b-41d4-a716-446655440000",
  format: "mp3",
  preset: "high"
});

// Response
{
  "success": true,
  "downloadUrl": "https://storage.googleapis.com/bucket/temp/...",
  "format": "mp3",
  "quality": {
    "bitrate": "320kbps",
    "sampleRate": 44100
  },
  "originalFormat": "wav",
  "fileSize": 12345678,
  "filename": "Song Title - Artist.mp3",
  "expiresIn": 300
}
```

---

## Testing Strategy

### Unit Tests

1. **Preset validation tests**
   - Valid format + preset combinations
   - Invalid format rejection
   - Invalid preset rejection
   - Default preset assignment

2. **FFmpeg command builder tests**
   - Correct command generation for each format/preset
   - Proper escaping and quoting

3. **Filename sanitization tests**
   - Special characters removed
   - Unicode handling
   - Length limits

### Integration Tests

1. **End-to-end conversion tests**
   - MP3 → WAV conversion
   - WAV → MP3 conversion
   - FLAC → MP3 conversion
   - Same format (no conversion) shortcut

2. **Error handling tests**
   - Invalid audioId
   - Missing source file
   - FFmpeg failure simulation
   - Timeout handling

### Manual Testing Checklist

- [ ] Download MP3 as WAV (broadcast quality)
- [ ] Download WAV as MP3 (320kbps)
- [ ] Download same format (verify redirect/shortcut)
- [ ] Large file conversion (>100MB)
- [ ] Concurrent conversion requests
- [ ] Error response format validation

---

## Implementation Tasks Overview

### Phase 1: Core Infrastructure
1. Create `src/converter/` module structure
2. Implement preset configuration system
3. Implement FFmpeg wrapper with error handling
4. Add GCS download-to-temp functionality

### Phase 2: HTTP Endpoint
1. Add `/api/tracks/{audioId}/download` endpoint
2. Implement format/preset validation
3. Implement short-circuit for same-format requests
4. Add streaming response with temp cleanup

### Phase 3: MCP Integration
1. Create `download_audio` MCP tool
2. Add tool schema and registration
3. Implement tool handler with URL generation

### Phase 4: Testing & Documentation
1. Unit tests for converter module
2. Integration tests for endpoint
3. Update API documentation
4. Add usage examples

---

## Dependencies

### Existing (No Changes Required)
- FFmpeg (already in Dockerfile)
- Google Cloud Storage client
- Starlette for HTTP responses
- FastMCP for tool registration

### New Python Packages (If Needed)
- None required - all functionality available with existing dependencies

---

## Configuration

### Environment Variables (New)

```env
# Conversion Settings
CONVERSION_TIMEOUT_SECONDS=300        # Max conversion time
CONVERSION_MAX_FILE_SIZE_MB=500       # Max source file size for conversion
CONVERSION_TEMP_DIR=/tmp/conversions  # Temp file location
```

### Cloud Run Considerations

- **Memory**: May need 2GB+ for large file conversions
- **CPU**: Conversion is CPU-intensive
- **Timeout**: Ensure Cloud Run timeout > conversion timeout

---

## Future Enhancements (Out of Scope for MVP)

1. **Caching**: Cache popular conversions in GCS (e.g., all tracks as MP3 320)
2. **Async Processing**: Queue-based conversion with webhook callback
3. **Batch Downloads**: Download multiple tracks as ZIP
4. **Custom Bitrate**: Allow advanced users to specify exact bitrate
5. **Waveform in Converted File**: Embed waveform image in ID3 tag
6. **Progress Tracking**: WebSocket-based conversion progress

---

## References

### Existing Code Patterns
- FFmpeg usage: `src/waveform/generator.py`
- GCS operations: `src/storage/gcs_client.py`
- HTTP endpoints: `src/http_api.py`
- Temp file management: `src/tools/process_audio.py`
- Error handling: `src/exceptions/`

### External Resources
- [FFmpeg Audio Conversion Guide](https://trac.ffmpeg.org/wiki/Encode/MP3)
- [Starlette StreamingResponse](https://www.starlette.io/responses/#streamingresponse)
- [Cloud Run Request Timeout](https://cloud.google.com/run/docs/configuring/request-timeout)

---

**Document Status**: Investigation Complete  
**Next Step**: Create implementation tasks from this specification  
**Created**: 2025-11-29

