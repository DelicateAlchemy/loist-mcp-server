# Technical Specification Extraction - Subtask 4.2

## Overview

This document covers the technical specification extraction functionality implemented in the Loist Music Library MCP Server. Technical specs include duration, sample rate, bit depth, channel count, and bitrate.

## Technical Specifications Extracted

| Specification | Unit | Description | Example |
|--------------|------|-------------|---------|
| **Duration** | seconds | Track length with millisecond precision | 245.678 |
| **Channels** | count | Number of audio channels | 2 (stereo) |
| **Sample Rate** | Hz | Sampling frequency | 44100 |
| **Bitrate** | kbps | Audio bitrate | 320 |
| **Bit Depth** | bits | Bits per sample | 16 |
| **Format** | string | Audio format | MP3 |

## Implementation

### From Subtask 4.1

Technical specification extraction was implemented in subtask 4.1 as part of the `MetadataExtractor.extract()` method using Mutagen's audio.info object.

### Code Location

```python
# src/metadata/extractor.py, lines ~300-318

if hasattr(audio.info, 'length'):
    metadata['duration'] = round(audio.info.length, 3)  # seconds

if hasattr(audio.info, 'channels'):
    metadata['channels'] = audio.info.channels

if hasattr(audio.info, 'sample_rate'):
    metadata['sample_rate'] = audio.info.sample_rate

if hasattr(audio.info, 'bitrate'):
    metadata['bitrate'] = audio.info.bitrate // 1000  # Convert to kbps

if hasattr(audio.info, 'bits_per_sample'):
    metadata['bit_depth'] = audio.info.bits_per_sample
elif hasattr(audio.info, 'sample_width'):
    metadata['bit_depth'] = audio.info.sample_width * 8
```

## Usage

```python
from src.metadata import extract_metadata

metadata = extract_metadata("song.mp3")

print(f"Duration: {metadata['duration']} seconds")
print(f"Channels: {metadata['channels']}")
print(f"Sample Rate: {metadata['sample_rate']} Hz")
print(f"Bitrate: {metadata['bitrate']} kbps")
print(f"Bit Depth: {metadata['bit_depth']} bits")
```

## Format-Specific Details

### MP3
- Duration: From MPEG frame analysis
- Bitrate: Can be constant (CBR) or variable (VBR)
- Bit depth: Not applicable (lossy compression)
- Channels: 1 (mono) or 2 (stereo)
- Sample Rate: Common values: 44100, 48000

### FLAC
- Duration: From frame count
- Bitrate: Variable (lossless)
- Bit Depth: 16 or 24 bits typical
- Channels: 1-8 channels supported
- Sample Rate: Up to 655350 Hz

### M4A/AAC
- Duration: From media header
- Bitrate: Variable or constant
- Bit depth: Not applicable (lossy)
- Channels: Up to 48 channels
- Sample Rate: 8000-96000 Hz typical

### WAV
- Duration: Calculated from file size
- Bitrate: Uncompressed
- Bit Depth: 8, 16, 24, or 32 bits
- Channels: 1-65535 channels
- Sample Rate: Typically 44100 or 48000

## Common Values

### Sample Rates
- 8000 Hz: Telephone quality
- 22050 Hz: Low quality
- 44100 Hz: CD quality (standard)
- 48000 Hz: Professional audio
- 96000 Hz: High-resolution audio

### Bit Depths
- 8 bit: Low quality
- 16 bit: CD quality (standard)
- 24 bit: Professional/studio quality
- 32 bit: Float (professional DAW)

### Channels
- 1: Mono
- 2: Stereo (standard)
- 6: 5.1 surround
- 8: 7.1 surround

### Bitrates (MP3)
- 128 kbps: Acceptable quality
- 192 kbps: Good quality
- 256 kbps: Very good quality
- 320 kbps: Maximum quality

## Testing

Tests for technical specification extraction are in `tests/test_metadata_extraction.py`:

```bash
pytest tests/test_metadata_extraction.py::TestTechnicalSpecExtraction -v
```

---

**Subtask 4.2 Status**: Complete ✅  
**Date**: 2025-10-09  
**Implementation**: Verified in subtask 4.1  
**Specs Extracted**: Duration, channels, sample rate, bitrate, bit depth

