# Google Cloud Storage Setup Guide - Subtask 2.3

## Overview

This guide covers the setup and configuration of Google Cloud Storage (GCS) for the Loist Music Library MCP Server. The GCS bucket stores audio files with secure access via signed URLs for streaming.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration Details](#configuration-details)
- [Bucket Structure](#bucket-structure)
- [Security & Access Control](#security--access-control)
- [Lifecycle Policies](#lifecycle-policies)
- [Usage Examples](#usage-examples)
- [Cost Estimation](#cost-estimation)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before setting up the GCS bucket, ensure you have:

1. **Google Cloud Project** - Project ID: `loist-music-library`
2. **gcloud CLI** - Installed and authenticated
3. **Service Account** - Created via `scripts/setup-gcloud.sh`
4. **Billing Enabled** - GCS requires an active billing account
5. **Required APIs Enabled**:
   - Cloud Storage API
   - Cloud Storage JSON API

## Quick Start

### 1. Create GCS Bucket

Run the automated setup script:

```bash
# Set environment variables (optional, defaults provided)
export GCP_PROJECT_ID="loist-music-library"
export GCS_BUCKET_NAME="loist-music-library-audio"
export GCS_REGION="us-central1"
export GCS_STORAGE_CLASS="STANDARD"

# Execute bucket creation script
./scripts/create-gcs-bucket.sh
```

### 2. Verify Configuration

```bash
# Check bucket exists
gsutil ls -b gs://loist-music-library-audio

# View bucket configuration
gsutil ls -L -b gs://loist-music-library-audio

# Test access with service account
gcloud auth activate-service-account \
  --key-file=service-account-key.json

gsutil ls gs://loist-music-library-audio/
```

### 3. Load Environment Configuration

```bash
# Source GCS environment variables
source .env.gcs

# Verify variables are loaded
echo $GCS_BUCKET_NAME
echo $GCS_PROJECT_ID
```

## Configuration Details

### Bucket Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Name** | `loist-music-library-audio` | Globally unique identifier |
| **Storage Class** | `STANDARD` | Frequent access for streaming |
| **Region** | `us-central1` | Co-located with Cloud SQL |
| **Access Control** | Uniform (bucket-level) | Simplified IAM management |
| **Versioning** | Disabled | Audio files are immutable |
| **Public Access** | Disabled | Security best practice |

### Storage Class Comparison

| Class | Use Case | Cost/GB/Month | Retrieval Cost |
|-------|----------|---------------|----------------|
| **STANDARD** | Hot data, streaming | $0.020 | Free |
| **NEARLINE** | Accessed <1x/month | $0.010 | $0.01/GB |
| **COLDLINE** | Accessed <1x/quarter | $0.004 | $0.02/GB |
| **ARCHIVE** | Long-term backup | $0.0012 | $0.05/GB |

**Recommendation**: STANDARD class for audio streaming (frequent access).

## Bucket Structure

The bucket is organized with the following directory structure:

```
gs://loist-music-library-audio/
├── audio/              # Permanent audio file storage
│   ├── {track_id}.mp3
│   ├── {track_id}.flac
│   └── ...
├── thumbnails/         # Album/track cover art
│   ├── {track_id}.jpg
│   └── ...
└── temp/              # Temporary uploads (auto-deleted after 24h)
    ├── {session_id}/{filename}
    └── ...
```

### File Naming Convention

- **Audio Files**: `audio/{uuid}.{extension}` (e.g., `audio/123e4567-e89b-12d3-a456-426614174000.mp3`)
- **Thumbnails**: `thumbnails/{uuid}.jpg`
- **Temp Files**: `temp/{session_id}/{original_filename}`

## Security & Access Control

### IAM Permissions

The service account has the following roles:

```
serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com
  roles/storage.objectAdmin  # Create, read, update, delete objects
```

### Signed URLs for Secure Access

Instead of making files public, we use signed URLs:

```python
from src.storage import generate_signed_url

# Generate 15-minute streaming URL
url = generate_signed_url(
    blob_name="audio/track-123.mp3",
    expiration_minutes=15
)

# URL expires automatically after 15 minutes
```

**Benefits**:
- No public access required
- Time-limited access
- Per-file access control
- Audit trail of access

### CORS Configuration

CORS is enabled for browser-based audio streaming:

```json
{
  "origin": ["*"],
  "method": ["GET", "HEAD", "OPTIONS"],
  "responseHeader": [
    "Content-Type",
    "Content-Length",
    "Content-Range",
    "Accept-Ranges",
    "Range"
  ],
  "maxAgeSeconds": 3600
}
```

This allows:
- HTML5 `<audio>` tag playback
- JavaScript Fetch API requests
- Range requests for seeking

## Lifecycle Policies

Automatic cleanup policies are configured to manage storage costs:

### Policy 1: Temporary Upload Cleanup

```json
{
  "action": {"type": "Delete"},
  "condition": {
    "age": 1,
    "matchesPrefix": ["temp/", "uploads/temp/"]
  }
}
```

- **Purpose**: Delete failed/abandoned uploads
- **Age**: 1 day (24 hours)
- **Impact**: Prevents accumulation of temp files

### Policy 2: Temporary Thumbnail Cleanup

```json
{
  "action": {"type": "Delete"},
  "condition": {
    "age": 7,
    "matchesPrefix": ["thumbnails/temp/"]
  }
}
```

- **Purpose**: Clean up thumbnail processing artifacts
- **Age**: 7 days
- **Impact**: Allows time for thumbnail generation retry

## Usage Examples

### Python Integration

#### Upload Audio File

```python
from pathlib import Path
from src.storage import upload_audio_file

# Upload with metadata
blob = upload_audio_file(
    source_path=Path("/local/path/song.mp3"),
    destination_blob_name="audio/track-123.mp3",
    metadata={
        "track_id": "123",
        "artist": "Example Artist",
        "title": "Example Song"
    }
)

print(f"Uploaded to: {blob.public_url}")
```

#### Generate Streaming URL

```python
from src.storage import generate_signed_url

# Standard 15-minute URL
stream_url = generate_signed_url(
    blob_name="audio/track-123.mp3",
    expiration_minutes=15
)

# Download with custom filename
download_url = generate_signed_url(
    blob_name="audio/track-123.mp3",
    expiration_minutes=5,
    response_disposition='attachment; filename="my-song.mp3"'
)
```

#### List Audio Files

```python
from src.storage import list_audio_files

# List all audio files
files = list_audio_files(prefix="audio/")

for file in files:
    print(f"{file['name']}: {file['size']} bytes")
```

#### Get File Metadata

```python
from src.storage import get_file_metadata

metadata = get_file_metadata("audio/track-123.mp3")
print(f"Size: {metadata['size']} bytes")
print(f"Created: {metadata['created']}")
print(f"MD5: {metadata['md5_hash']}")
```

#### Delete File

```python
from src.storage import delete_file

# Delete audio file and thumbnail
deleted = delete_file("audio/track-123.mp3")
if deleted:
    delete_file("thumbnails/track-123.jpg")
```

### MCP Tool Integration (Future)

```python
# Example MCP tool for streaming
@server.tool()
async def stream_audio(track_id: str) -> dict:
    """Generate a streaming URL for an audio track."""
    blob_name = f"audio/{track_id}.mp3"
    
    url = generate_signed_url(
        blob_name=blob_name,
        expiration_minutes=15
    )
    
    return {
        "stream_url": url,
        "expires_in_seconds": 900,
        "format": "audio/mpeg"
    }
```

## Cost Estimation

### Storage Costs (STANDARD Class, us-central1)

| Component | Rate | Example (10K tracks) | Cost/Month |
|-----------|------|---------------------|------------|
| Storage | $0.020/GB/month | 50 GB | $1.00 |
| Class A Ops (uploads) | $0.05/10K ops | 10K uploads | $0.05 |
| Class B Ops (reads) | $0.004/10K ops | 100K streams | $0.04 |
| Network Egress | $0.12/GB | 50 GB streamed | $6.00 |
| **Total** | | | **~$7.09** |

### Scaling Estimates

| Tracks | Storage | Monthly Cost (incl. streaming) |
|--------|---------|-------------------------------|
| 1,000 | 5 GB | ~$0.70 |
| 10,000 | 50 GB | ~$7.09 |
| 100,000 | 500 GB | ~$70.90 |

**Note**: Actual costs depend heavily on streaming volume (network egress).

### Cost Optimization Tips

1. **Use lifecycle policies** - Automatically delete abandoned uploads
2. **Enable CDN** - Reduce egress costs for popular tracks (Cloud CDN)
3. **Compress thumbnails** - Use WebP format for smaller file sizes
4. **Cache signed URLs** - Reuse URLs within expiration window
5. **Monitor usage** - Set up billing alerts

## Monitoring & Alerts

### Set Up Budget Alerts

```bash
# Create budget alert (via Console or gcloud)
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="GCS Storage Budget" \
  --budget-amount=100USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

### Key Metrics to Monitor

1. **Storage Size** - Track total bytes stored
2. **Request Count** - Monitor API operations
3. **Egress Bandwidth** - Track network data transfer
4. **Error Rate** - Watch for 4xx/5xx errors
5. **Latency** - Monitor request duration

### Cloud Monitoring Queries

```sql
-- Total storage size
fetch gcs_bucket
| metric 'storage.googleapis.com/storage/total_bytes'
| filter resource.bucket_name == 'loist-music-library-audio'

-- Request count by operation
fetch gcs_bucket
| metric 'storage.googleapis.com/api/request_count'
| filter resource.bucket_name == 'loist-music-library-audio'
| group_by [metric.method]
```

## Troubleshooting

### Permission Denied Errors

```bash
# Verify service account has correct roles
gcloud projects get-iam-policy loist-music-library \
  --flatten="bindings[].members" \
  --filter="bindings.members:loist-music-library-sa@"

# Re-apply IAM permissions
gsutil iam ch \
  serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com:roles/storage.objectAdmin \
  gs://loist-music-library-audio
```

### Signed URL Generation Fails

```python
# Error: "Service account must have signBlob permission"
# Solution: Ensure service account has iam.serviceAccountTokenCreator role

gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### CORS Errors in Browser

```bash
# Verify CORS configuration
gsutil cors get gs://loist-music-library-audio

# Re-apply CORS if needed
gsutil cors set cors.json gs://loist-music-library-audio
```

### Lifecycle Policy Not Working

```bash
# Check lifecycle configuration
gsutil lifecycle get gs://loist-music-library-audio

# Verify with test file
echo "test" | gsutil cp - gs://loist-music-library-audio/temp/test.txt

# Check again after 24 hours (policy runs daily)
gsutil ls gs://loist-music-library-audio/temp/
```

## Testing

### Unit Tests

```python
import pytest
from src.storage import GCSClient
from google.cloud.exceptions import NotFound

def test_signed_url_generation():
    client = GCSClient()
    
    # Upload test file first
    blob = client.upload_file(
        "test_audio.mp3",
        "test/audio.mp3"
    )
    
    # Generate signed URL
    url = client.generate_signed_url("test/audio.mp3")
    assert url.startswith("https://storage.googleapis.com")
    assert "Expires=" in url
    
    # Cleanup
    client.delete_file("test/audio.mp3")

def test_file_not_found():
    client = GCSClient()
    
    with pytest.raises(NotFound):
        client.generate_signed_url("nonexistent.mp3")
```

### Integration Tests

```bash
# Test bucket access
python3 << EOF
from src.storage import create_gcs_client

client = create_gcs_client()
print(f"✓ Connected to bucket: {client.bucket_name}")

# Test list files
files = client.list_files(max_results=5)
print(f"✓ Listed {len(files)} files")

# Test file operations
print("✓ GCS integration working!")
EOF
```

## Security Best Practices

1. **Never commit credentials** - Use `.gitignore` for service account keys
2. **Use signed URLs** - Don't make buckets public
3. **Rotate service accounts** - Regularly update credentials
4. **Monitor access logs** - Enable Cloud Audit Logs
5. **Least privilege** - Grant minimum required permissions
6. **Encrypt at rest** - Use Google-managed encryption keys (default)
7. **Require HTTPS** - Only use HTTPS for signed URLs
8. **Set short expirations** - Use 15 minutes or less for streaming URLs

## Next Steps

After completing GCS setup:

1. ✅ **Subtask 2.4** - Implement GCS Authentication and Access Control
2. ✅ **Subtask 2.5** - Configure Database Connection Pooling
3. ✅ **Subtask 2.6** - Develop Database Migration Scripts
4. ✅ **Subtask 2.7** - Configure GCS Lifecycle Policies (already done)
5. ✅ **Subtask 2.8** - Implement Signed URL Generation System (already done)

## References

- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Signed URLs Guide](https://cloud.google.com/storage/docs/access-control/signed-urls)
- [GCS Best Practices](https://cloud.google.com/storage/docs/best-practices)
- [Storage Classes](https://cloud.google.com/storage/docs/storage-classes)
- [Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
- [CORS Configuration](https://cloud.google.com/storage/docs/cross-origin)

## Support

For issues or questions:
- Check GCS status: https://status.cloud.google.com/
- Review Cloud Console: https://console.cloud.google.com/storage/browser/loist-music-library-audio
- Check billing: https://console.cloud.google.com/billing

---

**Subtask 2.3 Status**: Complete ✅  
**Date**: 2025-10-09  
**Bucket**: gs://loist-music-library-audio  
**Region**: us-central1

