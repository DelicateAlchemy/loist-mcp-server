## ID3 Tag Extraction - Subtask 4.1

## Overview

This document covers the ID3 tag extraction implementation for the Loist Music Library MCP Server. It provides comprehensive metadata extraction from audio files using the Mutagen library with support for multiple formats and tag versions.

## Table of Contents

- [Supported Formats](#supported-formats)
- [ID3 Tag Support](#id3-tag-support)
- [Implementation](#implementation)
- [Usage](#usage)
- [Testing](#testing)
- [Error Handling](#error-handling)

## Supported Formats

The metadata extractor supports the following audio formats:

| Format | Extension | Tag System | Library |
|--------|-----------|------------|---------|
| MP3 | `.mp3` | ID3v1, ID3v2.3, ID3v2.4 | mutagen.id3 |
| FLAC | `.flac` | Vorbis Comments | mutagen.flac |
| M4A/AAC | `.m4a`, `.aac` | MP4 Tags | mutagen.mp4 |
| OGG | `.ogg` | Vorbis Comments | mutagen.oggvorbis |
| WAV | `.wav` | RIFF INFO | mutagen.wave |

## ID3 Tag Support

### ID3v2.4 Tags (Recommended)

| Tag | ID3 Frame | Field | Description |
|-----|-----------|-------|-------------|
| Artist | TPE1 | `artist` | Track artist/performer |
| Title | TIT2 | `title` | Track title |
| Album | TALB | `album` | Album name |
| Genre | TCON | `genre` | Genre |
| Date | TDRC | `year` | Recording date (YYYY-MM-DD) |

### ID3v2.3 Tags (Legacy Support)

| Tag | ID3 Frame | Field | Description |
|-----|-----------|-------|-------------|
| Year | TYER | `year` | Year (YYYY) |

Both ID3v2.3 and ID3v2.4 are fully supported with automatic fallback.

## Implementation

### MetadataExtractor Class

```python
from src.metadata import MetadataExtractor

# Extract all metadata
metadata = MetadataExtractor.extract("song.mp3")

# Extract only ID3 tags
id3_tags = MetadataExtractor.extract_id3_tags("song.mp3")

# Extract from other formats
flac_metadata = MetadataExtractor.extract("song.flac")
m4a_metadata = MetadataExtractor.extract("song.m4a")
```

### Metadata Structure

```python
{
    "artist": "The Beatles",
    "title": "Hey Jude",
    "album": "The Beatles 1967-1970",
    "genre": "Rock",
    "year": 1968,
    "duration": 431.133,  # seconds
    "channels": 2,
    "sample_rate": 44100,
    "bitrate": 320,  # kbps
    "format": "MP3"
}
```

## Usage

### Basic Extraction

```python
from src.metadata import extract_metadata

# Extract all metadata
metadata = extract_metadata("path/to/song.mp3")

print(f"Artist: {metadata['artist']}")
print(f"Title: {metadata['title']}")
print(f"Duration: {metadata['duration']} seconds")
print(f"Bitrate: {metadata['bitrate']} kbps")
```

### ID3-Only Extraction

```python
from src.metadata import extract_id3_tags

# Extract only ID3 tags (faster for MP3)
tags = extract_id3_tags("song.mp3")

print(f"{tags['artist']} - {tags['title']}")
```

### Handle Missing Metadata

```python
from src.metadata import extract_metadata

metadata = extract_metadata("song.mp3")

# Use fallbacks for missing fields
artist = metadata['artist'] or "Unknown Artist"
title = metadata['title'] or "Untitled"
album = metadata['album'] or "Unknown Album"

print(f"{artist} - {title} ({album})")
```

### Format-Specific Extraction

```python
from src.metadata import MetadataExtractor

# MP3 with ID3 tags
mp3_metadata = MetadataExtractor.extract("song.mp3")

# FLAC with Vorbis comments
flac_metadata = MetadataExtractor.extract("song.flac")

# M4A with MP4 tags
m4a_metadata = MetadataExtractor.extract("song.m4a")
```

## Testing

### Run Metadata Tests

```bash
# All metadata tests
pytest tests/test_metadata_extraction.py -v

# Specific test classes
pytest tests/test_metadata_extraction.py::TestID3TagExtraction -v
```

## Error Handling

### Missing File

```python
from src.metadata import extract_metadata, MetadataExtractionError

try:
    metadata = extract_metadata("/nonexistent/song.mp3")
except MetadataExtractionError as e:
    print(f"File not found: {e}")
```

### Unsupported Format

```python
try:
    metadata = extract_metadata("document.pdf")
except MetadataExtractionError as e:
    print(f"Unsupported format: {e}")
```

### Missing Tags

```python
# Files with no tags return None values
metadata = extract_metadata("untagged.mp3")

if not metadata['artist']:
    print("No artist tag found")
    metadata['artist'] = "Unknown Artist"
```

---

**Subtask 4.1 Status**: Complete ✅  
**Date**: 2025-10-09  
**Formats Supported**: MP3, FLAC, M4A/AAC, OGG, WAV  
**Tag Versions**: ID3v1, ID3v2.3, ID3v2.4

