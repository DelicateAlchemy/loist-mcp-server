# HTTP/HTTPS Download Logic - Subtask 3.1

## Overview

This document covers the implementation of HTTP/HTTPS download functionality for the Loist Music Library MCP Server. It provides secure, robust downloading of audio files from URLs with comprehensive error handling and validation.

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Usage](#usage)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Best Practices](#best-practices)

## Architecture

### Components

1. **HTTPDownloader Class** (`src/downloader/http_downloader.py`):
   - Main downloader implementation
   - Session management with retry logic
   - Streaming downloads
   - Progress tracking

2. **Custom Exceptions**:
   - `DownloadError` - Base exception
   - `DownloadTimeoutError` - Timeout failures
   - `DownloadSizeError` - Size limit exceeded

3. **Convenience Function**:
   - `download_from_url()` - Simple one-line downloads

## Features

### ✅ Core Features

- **HTTP/HTTPS Support**: Secure protocol handling
- **Streaming Downloads**: Efficient memory usage for large files
- **File Size Validation**: HEAD request before download
- **Timeout Handling**: Configurable timeouts
- **Retry Logic**: Automatic retries with exponential backoff
- **Redirect Support**: Follows redirects automatically
- **Custom Headers**: Support for authentication headers
- **Progress Tracking**: Optional progress callbacks
- **Temporary Files**: Safe temporary storage
- **Error Handling**: Comprehensive exception handling

### ✅ Security Features

- **Protocol Validation**: Only HTTP/HTTPS allowed
- **Size Limits**: Prevents resource exhaustion
- **Timeout Protection**: Prevents hanging downloads
- **Cleanup on Failure**: Removes partial files

## Usage

### Basic Download

```python
from src.downloader import download_from_url

# Simple download to temporary file
file_path = download_from_url("https://example.com/audio.mp3")
print(f"Downloaded to: {file_path}")

# Download to specific location
file_path = download_from_url(
    "https://example.com/audio.mp3",
    destination="downloads/my-audio.mp3"
)
```

### Using HTTPDownloader Class

```python
from src.downloader import HTTPDownloader

# Create downloader with custom settings
downloader = HTTPDownloader(
    max_size_mb=50,      # 50MB limit
    timeout_seconds=30,  # 30 second timeout
    max_retries=5        # 5 retry attempts
)

# Download file
file_path = downloader.download("https://example.com/audio.mp3")
print(f"Downloaded: {file_path}")

# Close session when done
downloader.close()
```

### Context Manager (Recommended)

```python
from src.downloader import HTTPDownloader

# Automatic session cleanup
with HTTPDownloader(max_size_mb=100) as downloader:
    file1 = downloader.download("https://example.com/audio1.mp3")
    file2 = downloader.download("https://example.com/audio2.mp3")
    print(f"Downloaded: {file1}, {file2}")

# Session automatically closed
```

### Progress Tracking

```python
from src.downloader import download_from_url

def show_progress(downloaded, total):
    """Show download progress."""
    if total > 0:
        percent = (downloaded / total) * 100
        print(f"Progress: {percent:.1f}% ({downloaded}/{total} bytes)")
    else:
        print(f"Downloaded: {downloaded} bytes")

# Download with progress tracking
file_path = download_from_url(
    "https://example.com/large-audio.mp3",
    progress_callback=show_progress
)
```

### Custom Headers

```python
from src.downloader import download_from_url

# Download with authentication
file_path = download_from_url(
    "https://api.example.com/audio.mp3",
    headers={
        "Authorization": "Bearer your-token-here",
        "X-API-Key": "your-api-key"
    }
)
```

### Download Multiple Files

```python
from src.downloader import HTTPDownloader

urls = [
    "https://example.com/track1.mp3",
    "https://example.com/track2.mp3",
    "https://example.com/track3.mp3",
]

with HTTPDownloader() as downloader:
    for url in urls:
        try:
            file_path = downloader.download(url)
            print(f"✓ Downloaded: {file_path}")
        except Exception as e:
            print(f"✗ Failed: {url} - {e}")
```

## Configuration

### Initialization Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_size_mb` | int | 100 | Maximum file size in megabytes |
| `timeout_seconds` | int | 60 | Download timeout in seconds |
| `chunk_size` | int | 8192 | Download chunk size in bytes |
| `max_retries` | int | 3 | Maximum retry attempts |
| `follow_redirects` | bool | True | Follow HTTP redirects |
| `user_agent` | str | "Loist-MCP-Server/0.1.0" | User-Agent header |

### Retry Configuration

The downloader uses exponential backoff for retries:

```python
# Retry timing:
# Attempt 1: Immediate
# Attempt 2: 1 second delay
# Attempt 3: 2 second delay
# Attempt 4: 4 second delay

# Retries on these status codes:
# - 429 (Too Many Requests)
# - 500 (Internal Server Error)
# - 502 (Bad Gateway)
# - 503 (Service Unavailable)
# - 504 (Gateway Timeout)
```

### Timeout Configuration

```python
from src.downloader import HTTPDownloader

# Short timeout for quick failures
downloader = HTTPDownloader(timeout_seconds=10)

# Long timeout for large files
downloader = HTTPDownloader(timeout_seconds=300)  # 5 minutes

# Per-request timeout can't be changed
# Use initialization parameter
```

## Error Handling

### Exception Hierarchy

```python
DownloadError
├── DownloadTimeoutError  # Timeout occurred
└── DownloadSizeError     # Size limit exceeded
```

### Handling Exceptions

```python
from src.downloader import download_from_url
from src.downloader import DownloadError, DownloadTimeoutError, DownloadSizeError

try:
    file_path = download_from_url("https://example.com/audio.mp3")
    print(f"Success: {file_path}")
    
except DownloadTimeoutError as e:
    print(f"Download timed out: {e}")
    # Retry with longer timeout or different source
    
except DownloadSizeError as e:
    print(f"File too large: {e}")
    # Handle oversized file
    
except DownloadError as e:
    print(f"Download failed: {e}")
    # Generic error handling
    
except Exception as e:
    print(f"Unexpected error: {e}")
    # Unknown error
```

### Common Error Scenarios

#### 404 Not Found

```python
# Raises: DownloadError with message about HTTP 404
try:
    download_from_url("https://example.com/nonexistent.mp3")
except DownloadError as e:
    if "404" in str(e):
        print("File not found on server")
```

#### Connection Timeout

```python
# Raises: DownloadTimeoutError
try:
    download_from_url("https://slow-server.com/audio.mp3", timeout_seconds=5)
except DownloadTimeoutError:
    print("Server is too slow, trying alternative source...")
```

#### File Too Large

```python
# Raises: DownloadSizeError
try:
    download_from_url("https://example.com/huge.mp3", max_size_mb=10)
except DownloadSizeError as e:
    print(f"File exceeds size limit: {e}")
```

## Testing

### Unit Tests

```bash
# Run all downloader tests
pytest tests/test_http_downloader.py -v

# Run specific test
pytest tests/test_http_downloader.py::TestHTTPDownloaderInitialization -v

# Run with coverage
pytest tests/test_http_downloader.py --cov=src.downloader
```

### Test Coverage

The test suite includes:
- ✅ Module imports (3 tests)
- ✅ Initialization (3 tests)
- ✅ URL scheme validation (5 tests)
- ✅ File size validation (3 tests)
- ✅ File extension extraction (4 tests)
- ✅ Download function (5 tests)
- ✅ Convenience function (2 tests)
- ✅ Context manager (2 tests)
- ✅ Error handling (2 tests)
- ✅ Redirect handling (2 tests)

**Total: 30+ comprehensive tests**

### Manual Testing

```python
# Test with real URL
from src.downloader import download_from_url

# Download a small test file
file_path = download_from_url(
    "https://file-examples.com/storage/fe783ac56cbf0acb91a3e3f/2017/11/file_example_MP3_700KB.mp3",
    max_size_mb=1
)

print(f"Downloaded to: {file_path}")
print(f"File size: {file_path.stat().st_size} bytes")

# Cleanup
file_path.unlink()
```

## Best Practices

### ✅ DO:

1. **Use Context Manager**:
   ```python
   with HTTPDownloader() as downloader:
       # Automatic cleanup
   ```

2. **Set Appropriate Limits**:
   ```python
   # For audio files, 100MB is reasonable
   downloader = HTTPDownloader(max_size_mb=100)
   ```

3. **Handle Exceptions**:
   ```python
   try:
       download_from_url(url)
   except DownloadError as e:
       logger.error(f"Download failed: {e}")
   ```

4. **Use Progress Callbacks**:
   ```python
   download_from_url(url, progress_callback=log_progress)
   ```

5. **Validate URLs Before Downloading**:
   ```python
   downloader.validate_url_scheme(url)  # Fails fast
   ```

### ❌ DON'T:

1. **Don't Download to Same Location Concurrently**:
   ```python
   # BAD: Race condition
   download_from_url(url1, destination="file.mp3")
   download_from_url(url2, destination="file.mp3")
   ```

2. **Don't Ignore Size Limits**:
   ```python
   # BAD: Could exhaust disk space
   downloader = HTTPDownloader(max_size_mb=10000)
   ```

3. **Don't Forget Cleanup**:
   ```python
   # BAD: Temp files left behind
   for url in huge_list:
       download_from_url(url)  # Each creates temp file
   ```

4. **Don't Reuse Temp Files**:
   ```python
   # BAD: Temp file path changes each time
   temp_path = download_from_url(url1)
   # Don't reuse temp_path for another download
   ```

## Performance

### Streaming vs. Full Download

The downloader uses **streaming** by default:

```python
# Streaming (memory-efficient)
# Only chunk_size bytes in memory at a time
with response.get(url, stream=True) as r:
    for chunk in r.iter_content(chunk_size=8192):
        file.write(chunk)

# vs.

# Full download (memory-intensive)
# Entire file in memory
response = requests.get(url)
file.write(response.content)
```

**Benefits of Streaming:**
- Low memory footprint
- Can handle files larger than available RAM
- Early detection of size violations
- Progress tracking support

### Chunk Size Optimization

| Chunk Size | Use Case | Memory | Speed |
|------------|----------|--------|-------|
| 4096 | Low memory systems | Low | Slower |
| 8192 | Default (balanced) | Medium | Good |
| 16384 | Fast networks | Medium | Faster |
| 65536 | Very fast networks | High | Fastest |

**Recommendation**: Use default 8192 bytes for most cases.

### Retry Strategy

```python
# Retry configuration
max_retries = 3
backoff_factor = 1

# Retry timing:
# 1st retry: 1 second
# 2nd retry: 2 seconds
# 3rd retry: 4 seconds
```

## Integration Examples

### Download and Upload to GCS

```python
from src.downloader import download_from_url
from src.storage import upload_audio_file
from uuid import uuid4

# Download from URL
temp_file = download_from_url("https://example.com/audio.mp3")

try:
    # Upload to GCS
    track_id = uuid4()
    blob = upload_audio_file(
        source_path=temp_file,
        destination_blob_name=f"audio/{track_id}.mp3",
        metadata={"source_url": "https://example.com/audio.mp3"}
    )
    
    print(f"Uploaded to GCS: {blob.name}")
    
finally:
    # Cleanup temporary file
    temp_file.unlink()
```

### Download and Store in Database

```python
from src.downloader import download_from_url
from src.storage import upload_audio_file
from database.utils import AudioTrackDB
from uuid import uuid4
import mutagen

# Download audio file
temp_file = download_from_url("https://example.com/audio.mp3")

try:
    # Extract metadata (to be implemented in future tasks)
    # audio = mutagen.File(temp_file)
    # metadata = extract_metadata(audio)
    
    # Upload to GCS
    track_id = uuid4()
    blob = upload_audio_file(temp_file, f"audio/{track_id}.mp3")
    
    # Store in database
    track = AudioTrackDB.insert_track(
        track_id=track_id,
        title="Downloaded Track",
        audio_path=blob.name,
        format="mp3"
    )
    
    print(f"Track stored: {track['id']}")
    
finally:
    temp_file.unlink()
```

## Next Steps

After completing HTTP/HTTPS download logic:

1. ✅ **Subtask 3.2** - Validate URL Scheme (ready!)
2. ✅ **Subtask 3.3** - Apply SSRF Protection
3. ✅ **Subtask 3.4** - Handle File Size Validation
4. ✅ **Subtask 3.5** - Manage Timeout and Retry Logic
5. ✅ **Subtask 3.6** - Temporary File Management
6. ✅ **Subtask 3.7** - Implement Progress Tracking

## References

- [Requests Documentation](https://requests.readthedocs.io/)
- [HTTP Status Codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [Retry Strategies](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry)

---

**Subtask 3.1 Status**: Complete ✅  
**Date**: 2025-10-09  
**Module**: src/downloader/http_downloader.py  
**Tests**: 30+ comprehensive tests

