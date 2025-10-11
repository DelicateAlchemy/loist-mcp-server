# Format Validation - Subtask 4.4

## Overview

This document covers the audio format validation implementation for the Loist Music Library MCP Server. It provides validation beyond file extensions using magic numbers (file signatures) to detect corrupted, mislabeled, or malicious files.

## Table of Contents

- [Why Format Validation](#why-format-validation)
- [File Signatures](#file-signatures)
- [Implementation](#implementation)
- [Usage](#usage)
- [Testing](#testing)
- [Security Benefits](#security-benefits)

## Why Format Validation?

### Problems with Extension-Only Validation

**Extension-based validation is insufficient:**
- Users can rename files (`.txt` → `.mp3`)
- Attackers can disguise malicious files
- Corrupted files may have correct extension
- File type can't be verified

### Magic Number Validation

**File signatures (magic numbers) provide:**
- ✅ True format detection
- ✅ Corruption detection
- ✅ Mislabeled file detection
- ✅ Security against disguised files

## File Signatures

### Supported Audio Formats

| Format | Extension | Signature | Offset | Description |
|--------|-----------|-----------|--------|-------------|
| **MP3** | `.mp3` | `ID3` | 0 | ID3v2 tag |
| **MP3** | `.mp3` | `\xff\xfb` | 0 | MPEG-1 Layer 3 |
| **MP3** | `.mp3` | `\xff\xf3` | 0 | MPEG-1 Layer 3 |
| **FLAC** | `.flac` | `fLaC` | 0 | FLAC marker |
| **WAV** | `.wav` | `RIFF` | 0 | RIFF header |
| **WAV** | `.wav` | `WAVE` | 8 | WAVE format |
| **OGG** | `.ogg` | `OggS` | 0 | OGG container |
| **M4A/AAC** | `.m4a` | `ftyp` | 4 | MP4 file type |
| **AAC** | `.aac` | `\xff\xf1` | 0 | AAC ADTS |

## Implementation

### FormatValidator Class

```python
from src.metadata import FormatValidator, FormatValidationError

# Validate file signature
try:
    detected = FormatValidator.validate_signature("song.mp3", ".mp3")
    print(f"Valid MP3 file: {detected}")
except FormatValidationError as e:
    print(f"Invalid file: {e}")

# Auto-detect format from signature
detected = FormatValidator.validate_signature("unknown.bin")
print(f"Detected format: {detected}")

# Comprehensive validation
result = FormatValidator.validate_file("song.mp3")
print(f"Valid: {result['valid']}")
print(f"Extension: {result['extension']}")
print(f"Detected: {result['detected_format']}")
print(f"Match: {result['matches_extension']}")
```

## Usage

### Basic Validation

```python
from src.metadata import validate_audio_format, FormatValidationError

try:
    result = validate_audio_format("song.mp3")
    
    if result['matches_extension']:
        print("✓ File format validated")
    else:
        print("⚠ Extension doesn't match content")
        
except FormatValidationError as e:
    print(f"✗ Invalid file: {e}")
```

### Check if Format is Supported

```python
from src.metadata import FormatValidator

files = ["song.mp3", "track.flac", "document.pdf"]

for file in files:
    if FormatValidator.is_supported_format(file):
        print(f"✓ {file} - Supported")
    else:
        print(f"✗ {file} - Not supported")
```

### Detect Format from Content

```python
from src.metadata import FormatValidator

# File has wrong extension or no extension
detected = FormatValidator.detect_format("unknown_file.bin")

if detected:
    print(f"Actual format: {detected}")
    # Rename file with correct extension
else:
    print("Unknown format")
```

### Validate Before Processing

```python
from src.metadata import validate_audio_format, extract_metadata

def process_audio(file_path):
    # Validate format first
    validation = validate_audio_format(file_path)
    
    if not validation['matches_extension']:
        raise ValueError(
            f"File extension {validation['extension']} doesn't match "
            f"detected format {validation['detected_format']}"
        )
    
    # Safe to process
    metadata = extract_metadata(file_path)
    return metadata
```

## Testing

### Run Format Validation Tests

```bash
# All format validation tests
pytest tests/test_format_validation.py -v

# Specific test class
pytest tests/test_format_validation.py::TestSignatureValidation -v
```

### Test Results

```
24 passed in 0.10s ✅
```

### Test Coverage

- ✅ File signature reading (2 tests)
- ✅ Signature validation for all formats (6 tests)
- ✅ Format detection (3 tests)
- ✅ Comprehensive validation (5 tests)
- ✅ Supported format checking (3 tests)
- ✅ Convenience functions (1 test)
- ✅ Configuration tests (2 tests)
- ✅ Error handling (2 tests)

**Total: 24 comprehensive tests**

## Security Benefits

### Attack Prevention

#### 1. Malicious File Detection

**Attack:**
```bash
# Attacker renames malicious file as audio
mv exploit.exe malware.mp3
```

**Protection:**
```python
# Validation catches the mismatch
result = validate_audio_format("malware.mp3")
# Raises: FormatValidationError - signature does not match .mp3
```

#### 2. Corrupted File Detection

**Problem:**
```python
# Corrupted file with valid extension
process_audio("corrupted.mp3")
```

**Protection:**
```python
# Validation detects corruption
validate_audio_format("corrupted.mp3")
# Raises: FormatValidationError - Unknown or unsupported format
```

#### 3. File Type Confusion

**Problem:**
```bash
# Image file with audio extension
cp album_cover.jpg fake_audio.mp3
```

**Protection:**
```python
# Validation detects mismatch
validate_audio_format("fake_audio.mp3")
# Raises: FormatValidationError - signature does not match
```

## Best Practices

### ✅ DO:

1. **Validate Before Processing**:
   ```python
   validate_audio_format(file_path)
   metadata = extract_metadata(file_path)
   ```

2. **Check Signature Match**:
   ```python
   result = validate_audio_format(file_path)
   if not result['matches_extension']:
       logger.warning("Extension mismatch!")
   ```

3. **Handle Validation Errors**:
   ```python
   try:
       validate_audio_format(file_path)
   except FormatValidationError as e:
       logger.error(f"Invalid file: {e}")
       return None
   ```

### ❌ DON'T:

1. **Don't Trust Extensions Alone**:
   ```python
   # BAD: Only checks extension
   if file_path.endswith('.mp3'):
       process()
   
   # GOOD: Validates signature
   validate_audio_format(file_path)
   ```

2. **Don't Skip Validation**:
   ```python
   # BAD: Process without validation
   extract_metadata(untrusted_file)
   
   # GOOD: Validate first
   validate_audio_format(untrusted_file)
   extract_metadata(untrusted_file)
   ```

## Integration Example

```python
from src.downloader import download_from_url
from src.metadata import validate_audio_format, extract_metadata, extract_artwork
from src.metadata import FormatValidationError

# Download file
audio_file = download_from_url("https://example.com/song.mp3")

try:
    # Validate format
    validation = validate_audio_format(audio_file)
    print(f"✓ Format validated: {validation['detected_format']}")
    
    # Extract metadata
    metadata = extract_metadata(audio_file)
    artwork = extract_artwork(audio_file)
    
    print(f"✓ Extracted: {metadata['artist']} - {metadata['title']}")
    
except FormatValidationError as e:
    print(f"✗ Invalid file: {e}")
    audio_file.unlink()
```

---

**Subtask 4.4 Status**: Complete ✅  
**Date**: 2025-10-09  
**Formats Validated**: MP3, FLAC, WAV, OGG, M4A/AAC  
**Method**: Magic number validation

