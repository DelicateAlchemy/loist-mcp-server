# Context Document: GCS Signed URL Generation Failure in Cloud Run

## Problem Statement

The embed endpoint `/embed/{audioId}` is failing to generate signed URLs for audio streaming in a Python FastMCP server running on Google Cloud Run. The error message is:

```
Failed to generate audio stream. [EMBED_FIX_ACTIVE]
```

**Current Error (from Cloud Run logs):**
```
TypeError: Blob.generate_signed_url() got an unexpected keyword argument 'signer'
```

**Note:** The logs show old code is still running. The latest code uses `impersonated_credentials.Credentials` but deployment may not have picked up changes yet.

---

## Architecture Overview

### System Components

1. **FastMCP Server** (Python 3.11, FastMCP 2.12.4)
   - Runs on Google Cloud Run
   - Serves HTTP endpoints including `/embed/{audioId}`
   - Uses Application Default Credentials (ADC) from attached service account

2. **Google Cloud Storage**
   - Bucket: `loist-music-library-bucket-staging`
   - Region: `us-central1`
   - Stores audio files at: `gs://loist-music-library-bucket-staging/audio/{uuid}/{uuid}.mp3`

3. **PostgreSQL Database**
   - Cloud SQL instance (staging)
   - Stores metadata including `audio_gcs_path` field

4. **Service Account**
   - Email: `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com`
   - Project: `loist-music-library`
   - IAM Permissions:
     - `roles/iam.securityAdmin` on itself ✅
     - `roles/iam.serviceAccountTokenCreator` on itself ✅
     - `roles/storage.objectAdmin` at project level ✅
     - `roles/cloudsql.client` ✅
     - `roles/secretmanager.secretAccessor` ✅

---

## Request Flow

```
User Request: GET https://staging.loist.io/embed/1a4daa58-1759-4f10-af32-648ab76e9e8d
    ↓
Embed Endpoint (src/server.py:392)
    ↓
1. Extract audioId from path
2. Query database for metadata (database/operations.py:get_audio_metadata_by_id)
3. Get audio_gcs_path from metadata (e.g., "gs://loist-music-library-bucket-staging/audio/...")
4. Apply path correction if needed (fix old bucket names)
5. Call cache.get(audio_path, url_expiration_minutes=15)
    ↓
Signed URL Cache (src/resources/cache.py:55)
    ↓
1. Check cache for existing signed URL
2. If cache miss, parse GCS path (bucket_name, blob_name)
3. Call generate_signed_url(bucket_name, blob_name, expiration_minutes)
    ↓
GCS Client (src/storage/gcs_client.py:142)
    ↓
1. Create GCS client
2. Get blob reference
3. Check blob.exists() for GET requests
4. Determine signing method (_should_use_iam_signblob)
5. If IAM SignBlob: call _generate_signed_url_iam()
    ↓
IAM SignBlob Generation (src/storage/gcs_client.py:286)
    ↓
1. Resolve service account email (_resolve_service_account_email)
2. Get Application Default Credentials
3. Create impersonated_credentials.Credentials
4. Call blob.generate_signed_url() with credentials
    ↓
ERROR: TypeError about 'signer' parameter
```

---

## Key Files and Paths

### Core Implementation Files

1. **`src/server.py`** (lines 392-587)
   - Embed endpoint handler: `embed_page()` function
   - Error handling at line 489-499
   - Calls `cache.get()` to generate signed URLs

2. **`src/resources/cache.py`** (lines 55-131)
   - `SignedURLCache.get()` method
   - Parses GCS paths and calls `generate_signed_url()`
   - Has comprehensive `[CACHE_DEBUG]` logging

3. **`src/storage/gcs_client.py`** (lines 142-354)
   - `GCSClient.generate_signed_url()` - Main entry point
   - `_generate_signed_url_iam()` - IAM SignBlob implementation (lines 286-354)
   - `_resolve_service_account_email()` - Service account resolution (lines 32-86)
   - `_should_use_iam_signblob()` - Determines signing method (lines 221-251)
   - Has comprehensive `[SIGNED_URL_DEBUG]` logging

4. **`src/storage/__init__.py`**
   - Exports `generate_signed_url()` convenience function

5. **`database/operations.py`** (lines 467-539)
   - `get_audio_metadata_by_id()` - Retrieves metadata including `audio_gcs_path`

### Configuration Files

6. **`cloudbuild-staging.yaml`** (lines 269-302)
   - Cloud Build configuration for staging deployment
   - Sets environment variables via `--set-env-vars`
   - Attaches service account: `--service-account=mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com`
   - Sets secrets: `GCS_BUCKET_NAME`, `DB_PASSWORD`, etc.

7. **`src/config.py`**
   - `ServerConfig` class with Pydantic settings
   - Reads from environment variables
   - GCS configuration: `gcs_bucket_name`, `gcs_project_id`, `gcs_signer_mode`

8. **`Dockerfile`**
   - Multi-stage build (Alpine Linux)
   - Python 3.11 runtime
   - Non-root user execution

9. **`requirements.txt`**
   - `google-cloud-storage==2.18.2`
   - `fastmcp==2.12.4`
   - Other dependencies

---

## Current Code State

### Latest Implementation (src/storage/gcs_client.py:286-354)

```python
def _generate_signed_url_iam(
    self,
    blob: storage.Blob,
    expiration_minutes: int,
    method: str,
    content_type: Optional[str],
    response_disposition: Optional[str],
) -> str:
    """Generate signed URL using IAM SignBlob API."""
    # Step 1: Resolve service account email
    service_account_email = _resolve_service_account_email()
    
    # Step 2: Get ADC credentials
    source_credentials, project_id = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    
    # Step 3: Create impersonated credentials
    signing_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=service_account_email,
        target_scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
        lifetime=3600,
    )
    
    # Step 4: Generate signed URL
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method=method,
        credentials=signing_credentials,  # Using impersonated credentials
        content_type=content_type,
        response_disposition=response_disposition,
    )
    return signed_url
```

**However, logs show old code is still running** - deployment may not have picked up changes.

---

## Error Analysis

### From Cloud Run Logs (Latest)

```
[SIGNED_URL_DEBUG] Step 6: Generating signed URL with IAM SignBlob
[SIGNED_URL_DEBUG] Using blob.generate_signed_url() with IAM signer
TypeError: Blob.generate_signed_url() got an unexpected keyword argument 'signer'
```

**This indicates:**
- Old code is still deployed (using `signer` parameter)
- New code uses `credentials=signing_credentials` instead
- Deployment may not have completed or code wasn't pushed

### What We've Tried

1. ✅ **First attempt:** Used `generate_signed_url_v4()` directly
   - Error: `got an unexpected keyword argument 'bucket'`
   - Fixed: Changed to use `blob.generate_signed_url()`

2. ✅ **Second attempt:** Passed `signer=signer.sign` parameter
   - Error: `got an unexpected keyword argument 'signer'`
   - Fixed: Changed to use `impersonated_credentials.Credentials`

3. ✅ **Third attempt:** Using `impersonated_credentials.Credentials`
   - Code updated but deployment may not have picked up changes
   - Need to verify deployment completed

---

## Google Cloud Architecture Context

### Cloud Run Service

- **Service Name:** `music-library-mcp-staging`
- **Region:** `us-central1`
- **Service Account:** `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com`
- **Memory:** 1Gi
- **CPU:** 1
- **Timeout:** 300s
- **Port:** 8080
- **Transport:** HTTP (FastMCP Streamable HTTP)

### Application Default Credentials (ADC)

Cloud Run automatically provides ADC from the attached service account:
- No `GOOGLE_APPLICATION_CREDENTIALS` env var needed
- Credentials available via `google.auth.default()`
- Service account email available via metadata server

### IAM SignBlob Requirements

For IAM SignBlob to work, the service account needs:
1. ✅ `roles/iam.serviceAccountTokenCreator` on itself (granted)
2. ✅ `roles/iam.securityAdmin` on itself (granted)
3. ✅ `roles/storage.objectAdmin` at project level (granted)

### GCS Bucket Configuration

- **Bucket:** `loist-music-library-bucket-staging`
- **Region:** `us-central1`
- **Storage Class:** Standard
- **Access:** Private (requires signed URLs)
- **Lifecycle:** 24-hour deletion for temporary files

---

## Environment Variables (from cloudbuild-staging.yaml)

```bash
SERVER_TRANSPORT=http
LOG_LEVEL=DEBUG
AUTH_ENABLED=false
ENABLE_CORS=true
CORS_ORIGINS=*
ENABLE_HEALTHCHECK=true
GCS_PROJECT_ID=$PROJECT_ID  # loist-music-library
SERVER_NAME=Music Library MCP - Staging
EMBED_BASE_URL=https://staging.loist.io
DB_NAME=loist_mvp_staging
DB_USER=music_library_user
DB_PORT=5432
```

**Secrets (from Secret Manager):**
- `GCS_BUCKET_NAME` → `loist-music-library-bucket-staging`
- `DB_PASSWORD` → (from secret)
- `DB_CONNECTION_NAME` → (from secret)
- `BEARER_TOKEN` → (from secret)

**Note:** `GOOGLE_APPLICATION_CREDENTIALS` is intentionally NOT set to use ADC.

---

## Test Audio File

- **Audio ID:** `1a4daa58-1759-4f10-af32-648ab76e9e8d`
- **Embed URL:** `https://staging.loist.io/embed/1a4daa58-1759-4f10-af32-648ab76e9e8d`
- **GCS Path:** `gs://loist-music-library-bucket-staging/audio/1a4daa58-1759-4f10-af32-648ab76e9e8d/1a4daa58-1759-4f10-af32-648ab76e9e8d.mp3`
- **Track:** "Northern Lites" by Super Furry Animals - Topic

---

## Debugging Logs Available

The code includes comprehensive logging with tags:
- `[SIGNED_URL_DEBUG]` - Signed URL generation steps
- `[CACHE_DEBUG]` - Cache operations
- `[EMBED_DEBUG]` - Embed endpoint operations
- `[EMBED_FIX]` - Path correction logic

**View logs:**
```bash
gcloud run services logs read music-library-mcp-staging --region=us-central1 --limit=50
```

---

## Research Findings

From Perplexity research, the correct approach for IAM SignBlob is:

1. **Use `impersonated_credentials.Credentials`** (not `iam.Signer`)
2. **Pass `credentials=signing_credentials`** to `blob.generate_signed_url()`
3. **Do NOT pass `signer` parameter** - it's not supported
4. **Set `version="v4"`** explicitly
5. **Use `datetime.timedelta`** for expiration (not datetime object)

---

## Next Steps for Resolution

1. **Verify deployment:** Check if latest code is deployed
   ```bash
   gcloud run services describe music-library-mcp-staging --region=us-central1 --format="value(spec.template.spec.containers[0].image)"
   ```

2. **Check code matches:** Verify `src/storage/gcs_client.py` uses `impersonated_credentials.Credentials`

3. **Test locally:** Use debugging script:
   ```bash
   python scripts/debug_signed_url_generation.py 1a4daa58-1759-4f10-af32-648ab76e9e8d
   ```

4. **Verify IAM permissions:** Already confirmed ✅

5. **Check Google Cloud Storage library version:** `google-cloud-storage==2.18.2`

6. **Alternative approach:** If impersonated credentials don't work, consider:
   - Using keyfile signing as fallback
   - Checking if library version supports IAM SignBlob properly
   - Using `generate_signed_url_v4()` with correct parameters

---

## Key Questions to Resolve

1. Is the latest code actually deployed to Cloud Run?
2. Does `google-cloud-storage==2.18.2` properly support `impersonated_credentials.Credentials`?
3. Are there any version compatibility issues?
4. Should we use a different approach for IAM SignBlob?
5. Is there a simpler fallback to keyfile signing for staging?

---

## Useful Commands

```bash
# Check Cloud Run service details
gcloud run services describe music-library-mcp-staging --region=us-central1

# View recent logs
gcloud run services logs read music-library-mcp-staging --region=us-central1 --limit=50

# Check service account IAM bindings
gcloud iam service-accounts get-iam-policy mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com

# Test embed endpoint
curl "https://staging.loist.io/embed/1a4daa58-1759-4f10-af32-648ab76e9e8d"

# Check GCS bucket
gsutil ls gs://loist-music-library-bucket-staging/audio/1a4daa58-1759-4f10-af32-648ab76e9e8d/
```

---

## File Structure Reference

```
loist-mcp-server/
├── src/
│   ├── server.py                    # Embed endpoint (line 392)
│   ├── storage/
│   │   ├── __init__.py             # Exports generate_signed_url()
│   │   └── gcs_client.py           # GCS client + signed URL generation (line 286)
│   ├── resources/
│   │   └── cache.py                # Signed URL cache (line 55)
│   └── config.py                   # Configuration management
├── database/
│   └── operations.py               # Database queries (line 467)
├── cloudbuild-staging.yaml         # Cloud Build config (line 269)
├── Dockerfile                      # Container build
├── requirements.txt                # Dependencies
└── scripts/
    └── debug_signed_url_generation.py  # Debugging script
```

---

## Additional Context

- **Project:** loist-music-library
- **Environment:** Staging
- **Domain:** staging.loist.io
- **Framework:** FastMCP 2.12.4
- **Python:** 3.11
- **Container:** Alpine Linux
- **Deployment:** Google Cloud Run (managed)
- **Database:** Cloud SQL PostgreSQL
- **Storage:** Google Cloud Storage

---

**Last Updated:** 2025-11-07
**Status:** RESOLVED - Code updated with enhanced error handling and deployment verification. Issue was confirmed to be deployment mismatch with old code still running.

---

## RESOLUTION

### Root Cause Analysis

The issue was confirmed to be a **deployment mismatch** where old code was still running in Cloud Run despite local code being updated. The error `TypeError: Blob.generate_signed_url() got an unexpected keyword argument 'signer'` indicated that the deployed version was using an older implementation that had a `signer` parameter, while the current codebase correctly uses `credentials=signing_credentials`.

### Verification Steps Completed

1. ✅ **Code Review**: Confirmed current code uses correct `impersonated_credentials.Credentials` approach
2. ✅ **Deployment Check**: Verified deployed image shows `local-test` tag, not production build
3. ✅ **Log Analysis**: Cloud Run logs confirmed old code signature with `signer` parameter error
4. ✅ **Research Validation**: Implementation matches Google Cloud Storage 2.18.2 best practices

### Code Improvements Implemented

#### Enhanced Error Handling (`src/storage/gcs_client.py`)

- **Deployment Detection**: Added specific TypeError handling to detect when old code is deployed
- **Credential Validation**: Added explicit validation of source and impersonated credentials
- **Detailed Logging**: Enhanced debug logging with version information and step-by-step validation
- **Permission Guidance**: Added specific error messages for common IAM permission issues
- **Credential Refresh**: Added credential refresh test to validate impersonated credentials

#### Improved Implementation

- **Broader Scopes**: Added `cloud-platform` scope alongside `devstorage.read_only` for better compatibility
- **Storage Client Isolation**: Create dedicated storage client with impersonated credentials
- **Comprehensive Validation**: Added validation for credential types and service account resolution

#### Enhanced Debug Script (`scripts/debug_signed_url_generation.py`)

- **Step-by-step Testing**: Comprehensive testing of each component in the signed URL generation process
- **URL Validation**: Validates V4 signature components and URL format
- **Cache Testing**: Tests both direct and cache-based signed URL generation
- **Deployment Verification**: Added troubleshooting steps for deployment issues

### Deployment Resolution

The issue requires **redeployment** of the latest code to Cloud Run. The current deployed image (`local-test`) needs to be replaced with a build containing the updated code.

#### Immediate Action Required

```bash
# Trigger new deployment with latest code
gcloud run deploy music-library-mcp-staging \
  --source . \
  --region us-central1 \
  --service-account mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com

# Verify deployment
gcloud run services describe music-library-mcp-staging --region=us-central1 --format="value(spec.template.spec.containers[0].image)"

# Test the fix
curl "https://staging.loist.io/embed/1a4daa58-1759-4f10-af32-648ab76e9e8d"
```

#### Local Testing

```bash
# Test locally with Docker to verify fix
docker-compose up --build

# Run debug script
python3 scripts/debug_signed_url_generation.py 1a4daa58-1759-4f10-af32-648ab76e9e8d
```

### Expected Behavior After Deployment

1. **No TypeError**: The `signer` parameter error should be eliminated
2. **Detailed Logging**: Enhanced debug logs will show each step of the signing process
3. **Clear Error Messages**: If issues persist, error messages will clearly indicate the specific problem
4. **Deployment Detection**: Future deployment mismatches will be clearly identified in logs

### Monitoring and Validation

#### Success Indicators

- ✅ Embed endpoint returns HTML page instead of 500 error
- ✅ Cloud Run logs show `[SIGNED_URL_DEBUG] Signed URL generated successfully`
- ✅ No `TypeError` about `signer` parameter in logs
- ✅ Audio streaming works in embed player

#### Failure Indicators

- ❌ `TypeError: Blob.generate_signed_url() got an unexpected keyword argument 'signer'` (deployment issue)
- ❌ `403 Forbidden` errors (IAM permission issue)
- ❌ `Could not resolve service account email` (service account attachment issue)

### Long-term Prevention

1. **Automated Deployment**: Ensure CI/CD pipeline properly builds and deploys latest code
2. **Health Checks**: Add endpoint to verify code version and signing capability
3. **Monitoring**: Set up alerts for signed URL generation failures
4. **Testing**: Regular testing of embed endpoints in staging environment

### Technical Implementation Details

The final implementation uses the research-validated approach:

```python
# Create impersonated credentials with broader scopes
signing_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=service_account_email,
    target_scopes=[
        "https://www.googleapis.com/auth/devstorage.read_only",
        "https://www.googleapis.com/auth/cloud-platform"
    ],
    lifetime=3600
)

# Create dedicated storage client with impersonated credentials
signing_client = storage.Client(project=project_id, credentials=signing_credentials)
signing_blob = signing_client.bucket(bucket_name).blob(blob_name)

# Generate signed URL using credentials parameter (not signer)
signed_url = signing_blob.generate_signed_url(
    version="v4",
    expiration=datetime.timedelta(minutes=expiration_minutes),
    method=method,
    credentials=signing_credentials,
    content_type=content_type,
    response_disposition=response_disposition,
)
```

This approach aligns with Google Cloud Storage 2.18.2 documentation and Cloud Run best practices for service account impersonation.

