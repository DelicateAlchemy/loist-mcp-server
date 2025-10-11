# Artwork Extraction - Subtask 4.3

## Overview

This document covers the embedded artwork extraction implementation for the Loist Music Library MCP Server. It provides extraction of album cover images from audio file metadata for multiple formats.

## Table of Contents

- [Supported Formats](#supported-formats)
- [Picture Types](#picture-types)
- [Implementation](#implementation)
- [Usage](#usage)
- [Integration](#integration)
- [Testing](#testing)

## Supported Formats

| Format | Artwork Storage | Method |
|--------|----------------|--------|
| MP3 | APIC frames (ID3 tags) | `_extract_artwork_mp3()` |
| FLAC | Picture blocks | `_extract_artwork_flac()` |
| M4A/AAC | covr atom (MP4 tags) | `_extract_artwork_mp4()` |
| OGG | METADATA_BLOCK_PICTURE | `_extract_artwork_ogg()` |

**Note:** WAV files typically don't contain embedded artwork.

## Picture Types

### APIC/Picture Type Codes

| Type | Description | Priority |
|------|-------------|----------|
| 3 | Front cover | 1st (highest) |
| 0 | Other | 2nd |
| 4 | Back cover | 3rd |
| 2 | Other file icon | 4th |
| 1 | 32x32 file icon | 5th (lowest) |

The extractor prioritizes **front cover (type 3)** when multiple images are present.

## Implementation

### MetadataExtractor Class

```python
from src.metadata import MetadataExtractor

# Extract artwork from any supported format
artwork_path = MetadataExtractor.extract_artwork("song.mp3")

if artwork_path:
    print(f"Artwork saved to: {artwork_path}")
else:
    print("No artwork found")
```

### Extraction Process

```
1. Load audio file with Mutagen
   ↓
2. Check for artwork (APIC/Picture/covr)
   ↓
3. Select artwork by type priority (if multiple)
   ↓
4. Determine image format (JPEG, PNG, etc.)
   ↓
5. Save to destination or temp file
   ↓
6. Return Path to artwork
```

## Usage

### Basic Extraction

```python
from src.metadata import extract_artwork

# Extract to temporary file
artwork_path = extract_artwork("song.mp3")

if artwork_path:
    print(f"Artwork: {artwork_path}")
    print(f"Size: {artwork_path.stat().st_size} bytes")
    
    # Use artwork...
    
    # Cleanup when done
    artwork_path.unlink()
else:
    print("No artwork embedded")
```

### Extract to Specific Location

```python
from src.metadata import extract_artwork
from pathlib import Path

# Extract to specific destination
artwork_path = extract_artwork(
    "song.mp3",
    destination="covers/artist-album.jpg"
)

if artwork_path:
    print(f"Artwork saved to: {artwork_path}")
```

### Disable Front Cover Priority

```python
from src.metadata import extract_artwork

# Get first available artwork (any type)
artwork_path = extract_artwork(
    "song.mp3",
    prefer_front_cover=False
)
```

### Extract from Different Formats

```python
from src.metadata import extract_artwork

formats = {
    "mp3": "song.mp3",
    "flac": "song.flac",
    "m4a": "song.m4a",
    "ogg": "song.ogg",
}

for format_name, file_path in formats.items():
    artwork = extract_artwork(file_path)
    if artwork:
        print(f"{format_name}: {artwork}")
    else:
        print(f"{format_name}: No artwork")
```

## Integration

### Download, Extract, and Upload

Complete workflow with download, metadata extraction, and GCS upload:

```python
from src.downloader import download_from_url
from src.metadata import extract_metadata, extract_artwork
from src.storage import upload_audio_file
from database.utils import AudioTrackDB
from uuid import uuid4

# 1. Download audio file
temp_audio = download_from_url("https://example.com/song.mp3")

try:
    # 2. Extract metadata
    metadata = extract_metadata(temp_audio)
    
    # 3. Extract artwork
    artwork_path = extract_artwork(temp_audio)
    
    # 4. Upload audio to GCS
    track_id = uuid4()
    audio_blob = upload_audio_file(
        temp_audio,
        f"audio/{track_id}.mp3"
    )
    
    # 5. Upload artwork to GCS (if exists)
    thumbnail_path = None
    if artwork_path:
        from src.storage import upload_audio_file
        thumbnail_blob = upload_audio_file(
            artwork_path,
            f"thumbnails/{track_id}.jpg"
        )
        thumbnail_path = thumbnail_blob.name
        artwork_path.unlink()  # Cleanup temp artwork
    
    # 6. Store in database
    track = AudioTrackDB.insert_track(
        track_id=track_id,
        title=metadata['title'],
        audio_path=audio_blob.name,
        thumbnail_path=thumbnail_path,
        artist=metadata['artist'],
        album=metadata['album'],
        genre=metadata['genre'],
        year=metadata['year'],
        duration=metadata['duration'],
        channels=metadata['channels'],
        sample_rate=metadata['sample_rate'],
        bitrate=metadata['bitrate'],
        format=metadata['format']
    )
    
    print(f"Track ingested: {track['id']}")
    
finally:
    # Cleanup temporary audio file
    temp_audio.unlink()
```

### Extract and Display

```python
from src.metadata import extract_artwork
from PIL import Image

artwork_path = extract_artwork("song.mp3")

if artwork_path:
    # Display with Pillow
    img = Image.open(artwork_path)
    print(f"Artwork: {img.size[0]}x{img.size[1]}, {img.format}")
    img.show()
    
    # Cleanup
    artwork_path.unlink()
```

## Testing

### Run Artwork Tests

```bash
# All artwork tests
pytest tests/test_metadata_extraction.py::TestArtworkExtraction -v

# Specific test
pytest tests/test_metadata_extraction.py::TestArtworkExtraction::test_extract_artwork_mp3 -v
```

### Test Coverage

- ✅ MP3 artwork extraction (APIC frames)
- ✅ FLAC artwork extraction (Picture blocks)
- ✅ M4A artwork extraction (covr atom, JPEG)
- ✅ M4A artwork extraction (covr atom, PNG)
- ✅ No artwork handling (returns None)
- ✅ Custom destination
- ✅ Front cover priority
- ✅ File not found error

**Total: 8 comprehensive tests**

## Best Practices

### ✅ DO:

1. **Clean Up Temporary Files**:
   ```python
   artwork = extract_artwork("song.mp3")
   try:
       # Use artwork
       upload_to_gcs(artwork)
   finally:
       if artwork:
           artwork.unlink()
   ```

2. **Check for Artwork Before Using**:
   ```python
   artwork = extract_artwork("song.mp3")
   if artwork:
       process_artwork(artwork)
   ```

3. **Handle Missing Artwork Gracefully**:
   ```python
   artwork = extract_artwork("song.mp3") or get_default_cover()
   ```

### ❌ DON'T:

1. **Don't Assume Artwork Exists**:
   ```python
   # BAD: Could be None
   artwork = extract_artwork("song.mp3")
   upload(artwork)  # Fails if None
   
   # GOOD: Check first
   if artwork:
       upload(artwork)
   ```

2. **Don't Forget Cleanup**:
   ```python
   # BAD: Temp files accumulate
   for song in songs:
       artwork = extract_artwork(song)
       # Never cleaned up!
   ```

---

**Subtask 4.3 Status**: Complete ✅  
**Date**: 2025-10-09  
**Formats Supported**: MP3, FLAC, M4A/AAC, OGG  
**Priority**: Front cover (type 3) preferred

