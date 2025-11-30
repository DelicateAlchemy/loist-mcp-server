# Audio Download Endpoint with Format Conversion - Investigation

> **Document Purpose**: Context for implementing an audio download endpoint with on-the-fly format conversion for the Loist Music Library MCP Server. Designed for an LLM planning agent to create implementation tasks.
>
> **LLM Guidance**: Treat this document as the **source of truth** for allowed formats, presets, and metadata mappings. Do not invent new formats or presets beyond what is explicitly defined here.
>
> **MVP Mindset**: High-quality presets, no caching, fresh conversion each time.

---

## Terminology

| Term | Definition |
|------|------------|
| **Source format** | The original format of the audio file as stored in GCS (e.g., WAV, MP3) |
| **Target format** | The desired output format requested by the client (e.g., MP3, FLAC) |
| **Preset** | A named quality configuration for a target format (e.g., "high" = 320kbps for MP3) |
| **Short-circuit** | Skipping conversion when source matches target format AND quality requirements |

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
4. **Embeds metadata (artist, title, album, etc.) into converted file**
5. **Embeds album artwork where format supports it**
6. Returns converted file for download
7. Cleans up temp files (no caching)

### Non-Goals (Out of Scope for MVP)

The following are **explicitly NOT part of this implementation**:

- ❌ **Caching**: No pre-rendered conversions or cached outputs
- ❌ **Async queue**: No background job processing; conversion is synchronous per-request
- ❌ **Per-user rate limiting**: Rely on Cloud Run scaling, not application-level throttling
- ❌ **Custom bitrate input**: Users select presets, not arbitrary bitrate values
- ❌ **Batch downloads**: No multi-track ZIP downloads
- ❌ **Chapter markers**: No chapter/cue point embedding
- ❌ **ReplayGain**: No loudness normalization tags

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

> **Execution Environment**: FFmpeg runs **server-side in Google Cloud Run**, NOT on the client's machine. The Docker container includes FFmpeg (`apt-get install ffmpeg` in Dockerfile). This means:
> - Conversion happens in the cloud (GCS → Cloud Run → Client)
> - Cloud Run CPU/memory determines conversion capacity
> - No client-side resources required for conversion
> - Network latency is minimal between GCS and Cloud Run (same GCP region)

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
- **Converter module already exists** (`src/converter/ffmpeg_converter.py`) - needs metadata embedding added

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

## Metadata Embedding

> **Key Insight**: Format conversion alone isn't enough. Downloaded files must contain proper metadata tags so they display correctly in media players, DAWs, and file browsers.

### Overview

FFmpeg uses a generic `-metadata key=value` syntax that automatically maps to format-specific tag systems:
- **MP3**: ID3v2 frames (TIT2, TPE1, TALB, etc.)
- **WAV**: RIFF INFO chunks + BWF bext chunk
- **FLAC/OGG**: Vorbis comments
- **AAC/M4A**: iTunes-style atoms (©nam, ©ART, ©alb, etc.)

> **Encoding**: FFmpeg expects all metadata strings as **UTF-8**. Python subprocess calls must pass `encoding='utf-8'` or ensure strings are UTF-8 encoded. FFmpeg handles internal conversion to format-specific encodings (e.g., ID3 frame encodings).

### Known FFmpeg Metadata Limitations

Before diving into implementation, be aware of what FFmpeg **cannot** easily write:

| Limitation | Description | Workaround |
|------------|-------------|------------|
| Custom ID3 TXXX frames | Arbitrary key-value pairs beyond standard fields | Use `mutagen` post-processing |
| Complex chapter structures | Timestamped chapters with titles | Use `mutagen` or `mp4chaps` |
| Full iXML schemas | Broadcast metadata beyond BWF bext | External iXML tools |
| XMP packets | Embedded XML metadata in WAV/AIFF | Use `exiftool` or dedicated XMP tools |
| Advanced podcast tags | iTunes-specific podcast atoms | Use `AtomicParsley` |

**For MVP**: FFmpeg handles all common fields. These limitations are documented for future reference, not immediate implementation.

### Database Fields to Embed

These fields from the database will be embedded into converted files:

| Database Field | FFmpeg Key | MP3 (ID3) | WAV (RIFF) | FLAC/OGG | M4A |
|----------------|------------|-----------|------------|----------|-----|
| `title` | `title` | TIT2 | INAM | TITLE | ©nam |
| `artist` | `artist` | TPE1 | IART | ARTIST | ©ART |
| `album` | `album` | TALB | IPRD | ALBUM | ©alb |
| `album_artist` | `album_artist` | TPE2 | — | ALBUMARTIST | aART |
| `genre` | `genre` | TCON | IGNR | GENRE | ©gen |
| `year` | `date` | TDRC | ICRD | DATE | ©day |
| `track_number` | `track` | TRCK | ITRK | TRACKNUMBER | trkn |
| `composer` | `composer` | TCOM | — | COMPOSER | ©wrt |
| `publisher` | `publisher` | TPUB | — | PUBLISHER | — |
| `isrc` | `ISRC` | TSRC | ISRC | ISRC | — |

### Format-Specific Implementation

#### MP3 with Metadata

**Recommendation**: Use ID3v2.3 + ID3v1 for maximum compatibility (Windows Explorer, older players, car stereos).

```bash
ffmpeg -i input.wav \
  -codec:a libmp3lame -b:a 320k \
  -id3v2_version 3 -write_id3v1 1 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata album_artist="Album Artist" \
  -metadata genre="Rock" \
  -metadata date="2024" \
  -metadata track="1/12" \
  -metadata composer="Composer Name" \
  -metadata publisher="Publisher Name" \
  -metadata ISRC="US-ABC-24-00001" \
  output.mp3
```

**Key Flags**:
- `-id3v2_version 3`: ID3v2.3 for compatibility (v2.4 is default but less compatible)
- `-write_id3v1 1`: Also write legacy ID3v1 tags

#### WAV with Metadata (Complex Case)

WAV requires **two metadata systems** for full compatibility:

1. **RIFF INFO** (LIST/INFO chunk): Generic/legacy, DAW-compatible
2. **BWF bext chunk**: Professional/broadcast standard (preferred for archival)

```bash
ffmpeg -i input.mp3 \
  -acodec pcm_s24le -ar 48000 \
  -write_bext 1 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata ISRC="US-ABC-24-00001" \
  -metadata description="Full track description for BWF bext chunk" \
  -metadata originator="Loist Music Library" \
  -metadata originator_reference="LOIST-{audioId}" \
  -metadata coding_history="A=PCM,F=48000,W=24,M=stereo,T=Loist" \
  output.wav
```

**Key Flags**:
- `-write_bext 1`: Enable BWF bext chunk writing
- Generic metadata keys (`title`, `artist`) → RIFF INFO chunks
- BWF-specific keys (`description`, `originator`, `originator_reference`, `coding_history`) → bext chunk

**WAV Metadata Mapping**:

| Purpose | RIFF INFO Field | BWF bext Field |
|---------|-----------------|----------------|
| Title | INAM | — |
| Artist | IART | — |
| Album | IPRD | — |
| Description | — | Description (256 chars) |
| Creator | — | Originator |
| Reference | — | OriginatorReference |
| Encoding info | — | CodingHistory |

#### FLAC with Metadata

FLAC uses Vorbis comments. Straightforward mapping:

```bash
ffmpeg -i input.mp3 \
  -codec:a flac -compression_level 8 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata album_artist="Album Artist" \
  -metadata genre="Rock" \
  -metadata date="2024" \
  -metadata track="1" \
  -metadata composer="Composer Name" \
  -metadata publisher="Publisher Name" \
  -metadata ISRC="US-ABC-24-00001" \
  output.flac
```

#### AAC/M4A with Metadata

iTunes-style atoms. FFmpeg maps automatically:

```bash
ffmpeg -i input.wav \
  -codec:a aac -b:a 256k \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata album_artist="Album Artist" \
  -metadata genre="Rock" \
  -metadata date="2024" \
  -metadata track="1/12" \
  -metadata disc="1/2" \
  -metadata composer="Composer Name" \
  output.m4a
```

#### OGG Vorbis with Metadata

Same as FLAC (Vorbis comments):

```bash
ffmpeg -i input.wav \
  -codec:a libvorbis -qscale:a 8 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata genre="Rock" \
  -metadata date="2024" \
  -metadata track="1" \
  output.ogg
```

### Album Artwork Embedding

Album artwork can be embedded during conversion for formats that support it.

| Format | Artwork Support | Notes |
|--------|-----------------|-------|
| MP3 | ✅ Full | ID3 APIC frames |
| M4A | ✅ Full | `covr` atom |
| FLAC | ✅ Full | PICTURE block |
| OGG | ⚠️ Partial | METADATA_BLOCK_PICTURE; player support varies |
| WAV | ❌ Not standardized | Keep artwork external |

**MP3 Artwork Command**:
```bash
ffmpeg -i audio.wav -i cover.jpg \
  -map 0:a -map 1:v \
  -codec:a libmp3lame -b:a 320k \
  -codec:v mjpeg \
  -metadata:s:v title="Cover" -metadata:s:v comment="Cover (front)" \
  -id3v2_version 3 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  output.mp3
```

**M4A Artwork Command**:
```bash
ffmpeg -i audio.wav -i cover.jpg \
  -map 0:a -map 1:v \
  -codec:a aac -b:a 256k \
  -codec:v mjpeg \
  -disposition:v attached_pic \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  output.m4a
```

**FLAC Artwork Command**:
```bash
ffmpeg -i audio.wav -i cover.jpg \
  -map 0:a -map 1:v \
  -codec:a flac -compression_level 8 \
  -codec:v mjpeg \
  -disposition:v attached_pic \
  -metadata title="Song Title" \
  output.flac
```

### Character Encoding

FFmpeg treats all metadata strings as **UTF-8** internally. Implementation notes:

- Ensure Python passes UTF-8 strings to subprocess
- FFmpeg handles conversion to format-specific encodings (e.g., ID3 frame encodings)
- Test with international characters (Japanese, Arabic, emoji, etc.)

```python
# Python implementation note
import subprocess

# Ensure UTF-8 encoding in subprocess call
cmd = ["ffmpeg", "-i", source, "-metadata", f"title={title}", ...]
result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
```

### Limitations and Future Considerations

> See **"Known FFmpeg Metadata Limitations"** table at the start of this section for detailed limitations.

**What FFmpeg handles well (MVP scope)**:
- All common descriptive fields (title, artist, album, genre, year, track, composer, publisher, ISRC)
- Standard tag mappings across all target formats
- Basic artwork embedding (MP3, M4A, FLAC)
- UTF-8 encoding with automatic format-specific conversion

**Post-MVP enhancement path**:
If limitations are hit, `mutagen` (v1.47.0, already installed) can be used as a **post-processing step** after FFmpeg conversion:

```python
# Example: Add custom TXXX frame after FFmpeg conversion
from mutagen.id3 import ID3, TXXX

tags = ID3(output_path)
tags.add(TXXX(encoding=3, desc="CUSTOM_FIELD", text=["custom_value"]))
tags.save()
```

This pattern (FFmpeg for conversion + mutagen for advanced tags) avoids the complexity of mutagen-based audio conversion while leveraging its superior tag manipulation.

### Metadata Embedding Summary

| Format | Complexity | Key Considerations |
|--------|------------|-------------------|
| MP3 | Medium | Use `-id3v2_version 3 -write_id3v1 1` for compatibility |
| WAV | **High** | Use `-write_bext 1` + generic metadata for dual-system support |
| FLAC | Low | Vorbis comments "just work" |
| M4A | Low | iTunes atoms mapped automatically |
| OGG | Low | Vorbis comments "just work" |

---

## Implementation Architecture

### Proposed Flow

> **Execution**: All steps run server-side in **Google Cloud Run**. Client only receives the final converted file.

```
┌─────────────────────────────────────────────────────────────────┐
│       PROPOSED DOWNLOAD WITH CONVERSION FLOW (Cloud Run)         │
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
│  │    - Fetch metadata for embedding       │                    │
│  │      (title, artist, album, etc.)       │                    │
│  │    - Fetch artwork_gcs_path (if exists) │                    │
│  │    - Verify track exists & COMPLETED    │                    │
│  └─────────────────────────────────────────┘                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                    │
│  │ 3. SHORT-CIRCUIT CHECK                  │                    │
│  │    - See "Short-Circuit Rules" below    │                    │
│  │    - If eligible: redirect to signed URL│                    │
│  │    - If not: proceed to conversion      │                    │
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
│  │ 5. FFMPEG CONVERSION + METADATA         │                    │
│  │    - Build FFmpeg command from preset   │                    │
│  │    - Add -metadata args from database   │                    │
│  │    - Add format flags (ID3, BWF, etc.)  │                    │
│  │    - Embed artwork (if supported)       │                    │
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

### Short-Circuit Rules

The short-circuit optimization skips conversion and redirects directly to a signed GCS URL. This saves Cloud Run CPU and reduces latency.

**Short-circuit IS allowed when ALL conditions are met**:
1. Source format == target format (e.g., MP3 → MP3)
2. No quality downgrade requested (preset implies same or lower quality than source)
3. No metadata re-embedding required (source already has correct metadata)

**Short-circuit is NOT allowed when**:
| Scenario | Reason | Action |
|----------|--------|--------|
| Format differs | Obvious conversion needed | Convert |
| Higher quality requested | e.g., source is 128kbps, preset is "high" (320kbps) | Convert (can't upscale, but re-encode at target) |
| Preset specifies different sample rate | e.g., WAV `cd` preset (44.1kHz) on 48kHz source | Convert |
| Metadata is missing or stale | Source file lacks embedded metadata | Convert to embed |

**Implementation note**: For MVP, consider **always converting** if metadata embedding is enabled, since we can't easily verify if source file's embedded metadata matches database. This ensures downloaded files always have correct, up-to-date metadata.

```python
# Simplified short-circuit logic
def should_short_circuit(source_format: str, target_format: str, preset: str) -> bool:
    """
    Determine if we can skip conversion and redirect to source file.
    
    For MVP: Return False if metadata embedding is required (almost always).
    Future: Add logic to verify source metadata matches database.
    """
    if source_format.lower() != target_format.lower():
        return False
    
    # MVP: Always convert to ensure metadata is embedded
    # This trades CPU for metadata correctness
    return False  # TODO: Implement smart short-circuit with metadata verification
```

### File Organization

> **Note**: The `src/converter/` module **already exists** with `ffmpeg_converter.py` and `presets.py`. It needs to be extended with metadata embedding capabilities.

```
src/
├── downloader/
│   ├── __init__.py
│   ├── http_downloader.py      # Existing HTTP download
│   └── gcs_downloader.py       # NEW: Download from GCS to temp file
│
├── converter/                   # EXISTS - needs metadata extension
│   ├── __init__.py             # Existing
│   ├── ffmpeg_converter.py     # Existing - ADD metadata embedding
│   ├── presets.py              # Existing - ADD format-specific metadata flags
│   ├── formats.py              # Format-specific configurations
│   └── metadata_mapper.py      # NEW: Database fields → FFmpeg metadata args
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
        metadata: Optional[Dict[str, str]] = None,  # Database metadata to embed
        artwork_path: Optional[Path] = None,        # Album artwork to embed
        extra_args: Optional[List[str]] = None,     # Future: chapters, replaygain, etc.
        timeout_seconds: int = 300,
    ) -> ConversionResult:
        """
        Convert audio file using FFmpeg with metadata embedding.
        
        Args:
            source_path: Input audio file
            output_path: Output file path
            target_format: Target format (mp3, wav, flac, aac, ogg)
            preset: Quality preset
            metadata: Dict of metadata fields to embed (title, artist, album, etc.)
            artwork_path: Optional path to artwork image for embedding
            extra_args: Optional list of additional FFmpeg arguments for future
                        extensions (chapters, replaygain, etc.) without changing
                        method signature
            timeout_seconds: Max conversion time
        
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
   - **Metadata arguments correctly formatted**
   - **Format-specific flags present (e.g., `-id3v2_version 3`, `-write_bext 1`)**

3. **Metadata mapper tests**
   - Database fields correctly mapped to FFmpeg keys
   - Empty/null fields handled gracefully
   - **UTF-8 characters preserved**
   - **Special characters in metadata escaped properly**

4. **Filename sanitization tests**
   - Special characters removed
   - Unicode handling
   - Length limits

### Integration Tests

1. **End-to-end conversion tests**
   - MP3 → WAV conversion
   - WAV → MP3 conversion
   - FLAC → MP3 conversion
   - Same format (no conversion) shortcut

2. **Metadata embedding tests**
   - **MP3: Verify ID3v2.3 tags present and readable**
   - **WAV: Verify RIFF INFO + BWF bext chunks written**
   - **FLAC: Verify Vorbis comments present**
   - **M4A: Verify iTunes atoms present**
   - **UTF-8 metadata: Test Japanese/Arabic/emoji characters**

3. **Metadata preservation tests** (important for `-c:a copy` paths)
   - **Same-format conversion**: Verify metadata survives when re-encoding same format
   - **Stream copy vs re-encode**: If short-circuit uses `-c:a copy`, verify `-map_metadata` is explicit
   - **Source metadata vs database**: Ensure database metadata overwrites stale source tags

4. **Artwork embedding tests**
   - **MP3 with cover art**
   - **M4A with cover art**
   - **FLAC with cover art**
   - **WAV without artwork (verify no error)**

5. **Error handling tests**
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
- [ ] **Verify metadata in downloaded MP3 using BOTH `ffprobe -show_format -show_streams` AND a media player (e.g., VLC, iTunes)**
- [ ] **Verify RIFF INFO in downloaded WAV (use `mediainfo` or DAW)**
- [ ] **Verify BWF bext chunk in downloaded WAV (use `ffprobe` or `bwfmetaedit`)**
- [ ] **Test track with non-ASCII characters in metadata (Japanese, Arabic, emoji)**
- [ ] **Test track with album artwork (verify embedded in MP3/M4A/FLAC)**
- [ ] **Cross-verify tags with external tool** - don't rely solely on FFmpeg's own decoder

---

## Implementation Tasks Overview

### Phase 1: Core Infrastructure
1. Create `src/converter/` module structure
2. Implement preset configuration system
3. Implement FFmpeg wrapper with error handling
4. Add GCS download-to-temp functionality
5. **Implement metadata mapper (database fields → FFmpeg args)**
6. **Add format-specific metadata handling (ID3, RIFF, BWF, Vorbis, iTunes atoms)**

### Phase 2: HTTP Endpoint
1. Add `/api/tracks/{audioId}/download` endpoint
2. Implement format/preset validation
3. Implement short-circuit for same-format requests
4. Add streaming response with temp cleanup
5. **Fetch metadata from database and pass to converter**
6. **Download artwork from GCS for embedding (when available)**

### Phase 3: MCP Integration
1. Create `download_audio` MCP tool
2. Add tool schema and registration
3. Implement tool handler with URL generation

### Phase 4: Testing & Documentation
1. Unit tests for converter module
2. **Unit tests for metadata mapper**
3. Integration tests for endpoint
4. **Metadata embedding verification tests**
5. Update API documentation
6. Add usage examples

---

## Dependencies

### Existing (No Changes Required)
- FFmpeg (already in Dockerfile, runs in Cloud Run container)
- Google Cloud Storage client
- Starlette for HTTP responses
- FastMCP for tool registration
- **mutagen v1.47.0** (already installed, used for metadata extraction - available for writing if needed)
- **Converter module** (`src/converter/`) - exists, needs metadata extension

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

**FFmpeg Documentation**:
- [FFmpeg Audio Conversion Guide](https://trac.ffmpeg.org/wiki/Encode/MP3)
- [FFmpeg Metadata Wiki](https://wiki.multimedia.cx/index.php/FFmpeg_Metadata)
- [FFmpeg Formats Documentation](https://ffmpeg.org/ffmpeg-formats.html)
- [FFmpeg Metadata API](https://ffmpeg.org/doxygen/trunk/group__metadata__api.html)

**Format-Specific References**:
- [FFmpeg ID3v2 Header Documentation](https://ffmpeg.org/doxygen/7.0/id3v2_8h.html)
- [Broadcast Wave Format (BWF) in FFmpeg](https://ffmpeg.org/pipermail/ffmpeg-user/2019-March/043902.html)
- [Album Art Embedding Guide](https://hhsprings.bitbucket.io/docs/programming/examples/ffmpeg/metadata/album_art.html)

**Infrastructure**:
- [Starlette StreamingResponse](https://www.starlette.io/responses/#streamingresponse)
- [Cloud Run Request Timeout](https://cloud.google.com/run/docs/configuring/request-timeout)

---

**Document Status**: Investigation Complete  
**Next Step**: Create implementation tasks from this specification  
**Created**: 2025-11-29  
**Updated**: 2025-11-30 - Added Metadata Embedding section, Terminology, Non-Goals, Short-Circuit Rules, FFmpeg limitations table

