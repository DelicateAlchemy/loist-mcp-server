#!/bin/bash
# Query Google Cloud logs for waveform generation related to a specific audio track
# Usage: ./scripts/query-waveform-logs.sh <audio_id>

AUDIO_ID="${1:-4ad7d3a1-4271-4754-b816-a4d99423631a}"
PROJECT_ID="loist-music-library"
SERVICE_NAME="music-library-mcp-staging"
REGION="us-central1"

echo "=========================================="
echo "Waveform Generation Logs for Audio ID:"
echo "$AUDIO_ID"
echo "=========================================="
echo ""

# 1. Check for waveform enqueue logs
echo "1. Checking for waveform task enqueue logs..."
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=$SERVICE_NAME AND \
   (jsonPayload.message:\"waveform\" OR textPayload:\"waveform\" OR jsonPayload.audio_id=\"$AUDIO_ID\")" \
  --project=$PROJECT_ID \
  --limit=50 \
  --format="table(timestamp,severity,jsonPayload.message,textPayload)" \
  --freshness=1h

echo ""
echo ""

# 2. Check for Cloud Tasks queue logs
echo "2. Checking Cloud Tasks queue logs..."
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=$SERVICE_NAME AND \
   (jsonPayload.message:\"Enqueued waveform\" OR jsonPayload.message:\"Triggering asynchronous waveform\")" \
  --project=$PROJECT_ID \
  --limit=20 \
  --format="table(timestamp,severity,jsonPayload.message)" \
  --freshness=1h

echo ""
echo ""

# 3. Check for waveform task handler execution
echo "3. Checking waveform task handler execution logs..."
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=$SERVICE_NAME AND \
   (jsonPayload.message:\"Processing waveform\" OR jsonPayload.message:\"waveform generation\" OR jsonPayload.message:\"Successfully generated waveform\")" \
  --project=$PROJECT_ID \
  --limit=30 \
  --format="table(timestamp,severity,jsonPayload.message,jsonPayload.audioId)" \
  --freshness=1h

echo ""
echo ""

# 4. Check for GCS upload logs related to waveforms
echo "4. Checking GCS waveform upload logs..."
echo "----------------------------------------"
gcloud logging read \
  "resource.type=gcs_bucket AND \
   resource.labels.bucket_name=\"loist-music-library-bucket-staging\" AND \
   jsonPayload.resourceName:\"waveform\" AND \
   jsonPayload.resourceName:\"$AUDIO_ID\"" \
  --project=$PROJECT_ID \
  --limit=20 \
  --format="table(timestamp,severity,jsonPayload.resourceName,jsonPayload.methodName)" \
  --freshness=1h

echo ""
echo ""

# 5. Check for any errors related to waveform generation
echo "5. Checking for waveform generation errors..."
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=$SERVICE_NAME AND \
   severity>=ERROR AND \
   (jsonPayload.message:\"waveform\" OR textPayload:\"waveform\")" \
  --project=$PROJECT_ID \
  --limit=20 \
  --format="table(timestamp,severity,jsonPayload.message,textPayload)" \
  --freshness=1h

echo ""
echo ""

# 6. Check Cloud Tasks queue status
echo "6. Checking Cloud Tasks queue status..."
echo "----------------------------------------"
gcloud tasks queues describe audio-processing-queue \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="table(name,state,rateLimits.maxDispatchesPerSecond,retryConfig.maxAttempts)"

echo ""
echo ""

# 7. List recent tasks in the queue
echo "7. Listing recent tasks in queue..."
echo "----------------------------------------"
gcloud tasks list \
  --queue=audio-processing-queue \
  --location=$REGION \
  --project=$PROJECT_ID \
  --limit=10 \
  --format="table(name,createTime,scheduleTime,dispatchCount,responseCount)"

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="

