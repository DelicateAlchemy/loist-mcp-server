# GCS Organization Structure for Audio Storage

## Overview

This document describes the Google Cloud Storage (GCS) organization structure used for storing audio files and their associated media (thumbnails, metadata, etc.).

## Design Principles

1. **Scalability**: Structure supports millions of audio files without performance degradation
2. **Organization**: Each audio upload gets its own folder for easy management
3. **Traceability**: UUID-based identifiers enable tracking and auditing
4. **Flexibility**: Structure supports future additions (lyrics, waveforms, transcripts, etc.)
5. **Cleanup**: Easy to delete all files associated with a single audio upload

## Folder Structure

### Root Organization

```
gs://bucket-name/
└── audio/
    ├── {uuid-1}/
    │   ├── audio.mp3
    │   └── thumbnail.jpg
    ├── {uuid-2}/
    │   ├── audio.wav
    │   └── thumbnail.jpg
    └── {uuid-3}/
        └── audio.flac
```

### Path Patterns

| File Type | Pattern | Example |
|-----------|---------|---------|
| Audio File | `audio/{uuid}/audio.{ext}` | `audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3` |
| Thumbnail | `audio/{uuid}/thumbnail.{ext}` | `audio/550e8400-e29b-41d4-a716-446655440000/thumbnail.jpg` |

## UUID Generation

### Why UUID v4?

We use **UUID v4** (Universally Unique Identifier, version 4) for generating audio identifiers:

- **122 bits of randomness**: Provides ~5.3×10³⁶ possible unique values
- **Collision probability**: Negligible for all practical purposes
  - Need to generate ~2.71 quintillion UUIDs for 50% collision probability
- **Security**: Non-sequential pattern prevents enumeration attacks
- **Stateless**: No coordination or central database required
- **URL-safe**: Compatible with HTTP URLs and GCS paths

### UUID Format

```
550e8400-e29b-41d4-a716-446655440000
└─────┬────┘ │    │    │    └──────┬──────┘
      │      │    │    │           │
   time_low  │ time_hi │        node
          time_mid  clock_seq
```

Example audio IDs:
- `7c9e6679-7425-40de-944b-e07fc1f90ae7`
- `a3bb189e-8bf9-3888-9912-ace4e6543002`

## File Extension Handling

The system preserves original file extensions for proper content-type handling:

### Supported Audio Formats

| Extension | Content-Type | Example Path |
|-----------|--------------|--------------|
| `.mp3` | `audio/mpeg` | `audio/{uuid}/audio.mp3` |
| `.wav` | `audio/wav` | `audio/{uuid}/audio.wav` |
| `.flac` | `audio/flac` | `audio/{uuid}/audio.flac` |
| `.ogg` | `audio/ogg` | `audio/{uuid}/audio.ogg` |
| `.m4a` | `audio/mp4` | `audio/{uuid}/audio.m4a` |
| `.aac` | `audio/aac` | `audio/{uuid}/audio.aac` |

### Supported Image Formats (Thumbnails)

| Extension | Content-Type | Example Path |
|-----------|--------------|--------------|
| `.jpg` | `image/jpeg` | `audio/{uuid}/thumbnail.jpg` |
| `.jpeg` | `image/jpeg` | `audio/{uuid}/thumbnail.jpeg` |
| `.png` | `image/png` | `audio/{uuid}/thumbnail.png` |
| `.webp` | `image/webp` | `audio/{uuid}/thumbnail.webp` |

## Example Workflows

### Complete Upload

```
1. Generate UUID: 550e8400-e29b-41d4-a716-446655440000
2. Upload audio file to: audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3
3. Upload thumbnail to: audio/550e8400-e29b-41d4-a716-446655440000/thumbnail.jpg
4. Store metadata with paths in database
```

### Listing Files for Audio

```python
# List all files for a specific audio ID
prefix = "audio/550e8400-e29b-41d4-a716-446655440000/"
blobs = bucket.list_blobs(prefix=prefix)
```

### Deleting Audio and All Associated Files

```python
# Delete entire folder (audio + thumbnail + any future files)
prefix = "audio/550e8400-e29b-41d4-a716-446655440000/"
blobs = bucket.list_blobs(prefix=prefix)
for blob in blobs:
    blob.delete()
```

## GCS URI Format

Full GCS URIs follow this format:

```
gs://{bucket-name}/{blob-path}
```

Examples:
```
gs://my-audio-bucket/audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3
gs://my-audio-bucket/audio/550e8400-e29b-41d4-a716-446655440000/thumbnail.jpg
```

## Future Extensibility

The structure supports easy addition of new file types:

```
audio/{uuid}/
├── audio.mp3          # Original audio
├── thumbnail.jpg      # Album artwork
├── waveform.png       # (future) Visual waveform
├── lyrics.txt         # (future) Song lyrics
├── transcript.json    # (future) Speech-to-text
└── metadata.json      # (future) Extended metadata
```

## Benefits

### Scalability
- No flat directory with millions of files
- Efficient GCS listing operations (prefix-based)
- Each folder typically has 1-5 files

### Management
- Easy to locate all files for one audio
- Simple cleanup (delete folder)
- Atomic operations per audio

### Security
- Non-sequential UUIDs prevent enumeration
- No user information in paths
- Compatible with signed URLs

### Performance
- Optimized for GCS list operations
- Minimal I/O for common queries
- Supports parallel uploads

## Implementation Classes

### `FilenameGenerator`

Handles unique identifier and path generation:
- `generate_audio_id()`: Creates new UUID v4
- `generate_blob_name()`: Constructs full GCS path
- `validate_uuid()`: Validates UUID format

### `FileOrganizer`

Manages organizational structure:
- `get_folder_structure()`: Returns folder paths
- `get_expected_files()`: Lists expected files
- `format_gcs_uri()`: Formats GCS URIs

## Best Practices

1. **Always use generated UUIDs** - Don't create custom identifiers
2. **Preserve file extensions** - Ensures proper content-type handling
3. **Store UUIDs in database** - Link to user data and metadata
4. **Use GCS signed URLs** - For secure temporary access
5. **Implement lifecycle policies** - For automatic cleanup of old files
6. **Add custom metadata** - Use GCS blob metadata for additional context

## References

- [UUID Specification (RFC 4122)](https://tools.ietf.org/html/rfc4122)
- [Google Cloud Storage Best Practices](https://cloud.google.com/storage/docs/best-practices)
- [GCS Naming Guidelines](https://cloud.google.com/storage/docs/naming-objects)



