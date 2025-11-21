# Querying Waveform Generation Logs

This guide shows how to query Google Cloud logs to check waveform generation status for audio tracks.

## Prerequisites

1. **Authenticate with gcloud:**
   ```bash
   gcloud auth login
   gcloud config set project loist-music-library
   ```

2. **Set your project:**
   ```bash
   export PROJECT_ID="loist-music-library"
   export SERVICE_NAME="music-library-mcp-staging"
   export REGION="us-central1"
   ```

## Quick Query Commands

### 1. Check for Waveform Enqueue Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=music-library-mcp-staging AND \
   (jsonPayload.message:\"waveform\" OR textPayload:\"waveform\")" \
  --project=loist-music-library \
  --limit=50 \
  --format="table(timestamp,severity,jsonPayload.message,textPayload)" \
  --freshness=1h
```

### 2. Check for Specific Audio ID

Replace `AUDIO_ID` with your track ID (e.g., `4ad7d3a1-4271-4754-b816-a4d99423631a`):

```bash
AUDIO_ID="4ad7d3a1-4271-4754-b816-a4d99423631a"

gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=music-library-mcp-staging AND \
   (jsonPayload.audio_id=\"$AUDIO_ID\" OR jsonPayload.audioId=\"$AUDIO_ID\")" \
  --project=loist-music-library \
  --limit=100 \
  --format=json \
  --freshness=1h | grep -i waveform
```

### 3. Check Waveform Task Handler Execution

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=music-library-mcp-staging AND \
   (jsonPayload.message:\"Processing waveform\" OR \
    jsonPayload.message:\"Successfully generated waveform\" OR \
    jsonPayload.message:\"Enqueued waveform generation task\")" \
  --project=loist-music-library \
  --limit=30 \
  --format="table(timestamp,severity,jsonPayload.message,jsonPayload.audioId)" \
  --freshness=1h
```

### 4. Check for Waveform Generation Errors

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=music-library-mcp-staging AND \
   severity>=ERROR AND \
   (jsonPayload.message:\"waveform\" OR textPayload:\"waveform\")" \
  --project=loist-music-library \
  --limit=20 \
  --format="table(timestamp,severity,jsonPayload.message,textPayload)" \
  --freshness=1h
```

### 5. Check GCS Bucket for Waveform Files

```bash
# List waveform files in the bucket
gsutil ls -l gs://loist-music-library-bucket-staging/audio/*/waveform.svg

# Check for specific audio ID
AUDIO_ID="4ad7d3a1-4271-4754-b816-a4d99423631a"
gsutil ls -l gs://loist-music-library-bucket-staging/audio/$AUDIO_ID/waveform.svg
```

### 6. Check Cloud Tasks Queue Status

```bash
# Describe the queue
gcloud tasks queues describe audio-processing-queue \
  --location=us-central1 \
  --project=loist-music-library

# List recent tasks
gcloud tasks list \
  --queue=audio-processing-queue \
  --location=us-central1 \
  --project=loist-music-library \
  --limit=10
```

### 7. Comprehensive Log Query (JSON Format)

For detailed analysis, use JSON format:

```bash
AUDIO_ID="4ad7d3a1-4271-4754-b816-a4d99423631a"

gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=music-library-mcp-staging AND \
   (jsonPayload.message:\"waveform\" OR \
    jsonPayload.audio_id=\"$AUDIO_ID\" OR \
    jsonPayload.audioId=\"$AUDIO_ID\")" \
  --project=loist-music-library \
  --limit=100 \
  --format=json \
  --freshness=1h > waveform-logs-$AUDIO_ID.json
```

## Using the Script

A convenience script is available at `scripts/query-waveform-logs.sh`:

```bash
# Query logs for a specific audio ID
./scripts/query-waveform-logs.sh 4ad7d3a1-4271-4754-b816-a4d99423631a

# Or use default (the track we just processed)
./scripts/query-waveform-logs.sh
```

## Understanding the Logs

### Waveform Generation Flow

1. **Enqueue Phase:**
   - Look for: `"Triggering asynchronous waveform generation"`
   - Look for: `"Enqueued waveform generation task: {task_id}"`

2. **Task Processing Phase:**
   - Look for: `"Processing waveform generation for audio_id: {audio_id}"`
   - Look for: `"Downloading audio from {gcs_path}"`
   - Look for: `"Generating waveform SVG"`
   - Look for: `"Uploading waveform SVG to GCS"`

3. **Completion Phase:**
   - Look for: `"Successfully generated waveform for audio_id: {audio_id}"`
   - Look for: `"Waveform generation completed in {time}s"`

### Common Log Patterns

**Successful Generation:**
```
INFO: Enqueued waveform generation task: projects/.../tasks/...
INFO: Processing waveform generation for audio_id: ...
INFO: Downloading audio from gs://...
INFO: Generating waveform SVG
INFO: Uploading waveform SVG to GCS
INFO: Successfully generated waveform for audio_id: ...
```

**Cache Hit:**
```
INFO: Cache hit for audio_id ... - waveform already exists
```

**Errors:**
```
ERROR: Failed to enqueue waveform generation task: ...
ERROR: Failed to process waveform task for ...: ...
WARNING: Failed to generate waveform signed URL for ...: ...
```

## Troubleshooting

### No Logs Found

1. **Check time range:** Increase `--freshness` value (e.g., `--freshness=24h`)
2. **Check service name:** Verify `music-library-mcp-staging` is correct
3. **Check project:** Ensure `loist-music-library` is the correct project

### Waveform Not Generated

1. **Check Cloud Tasks queue:** Ensure queue exists and is active
2. **Check task handler endpoint:** Verify `/tasks/waveform` endpoint is accessible
3. **Check GCS permissions:** Ensure service account can read/write to bucket
4. **Check for errors:** Run error query (command #4 above)

### Authentication Issues

If you get authentication errors:

```bash
# Re-authenticate
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Use service account (if you have key file)
gcloud auth activate-service-account --key-file=path/to/key.json
```

## Related Documentation

- [Cloud Run Deployment Guide](./cloud-run-deployment.md)
- [Troubleshooting Guide](./troubleshooting-deployment.md)
- [Waveform Generation Implementation](../src/waveform/generator.py)

---

**Last Updated**: 2025-01-XX

