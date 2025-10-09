# GCS Authentication and Access Control - Subtask 2.4

## Overview

This document covers the authentication and access control implementation for Google Cloud Storage in the Loist Music Library MCP Server. It details service account configuration, IAM roles, credential management, and security best practices.

## Table of Contents

- [Service Account Overview](#service-account-overview)
- [IAM Roles and Permissions](#iam-roles-and-permissions)
- [Credential Management](#credential-management)
- [Authentication Flow](#authentication-flow)
- [Security Best Practices](#security-best-practices)
- [Access Control Patterns](#access-control-patterns)
- [Monitoring and Auditing](#monitoring-and-auditing)
- [Troubleshooting](#troubleshooting)

## Service Account Overview

### Primary Service Account

**Name:** Loist Music Library Service Account  
**Email:** `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`  
**Purpose:** Application-level authentication for GCS and Cloud SQL access  
**Status:** Active

### Service Account Creation

The service account was created during initial project setup with the following command:

```bash
gcloud iam service-accounts create loist-music-library-sa \
  --display-name="Loist Music Library Service Account" \
  --description="Service account for MCP server authentication" \
  --project=loist-music-library
```

### Key Management

**Key File:** `service-account-key.json` (gitignored)  
**Key Type:** JSON  
**Rotation Policy:** Manual, recommended every 90 days  
**Storage:** Local filesystem, excluded from version control

## IAM Roles and Permissions

### Project-Level Roles

The service account has the following project-level IAM bindings:

| Role | Purpose | Permissions Summary |
|------|---------|-------------------|
| `roles/storage.admin` | Full GCS management | Create, read, update, delete objects and buckets |
| `roles/cloudsql.admin` | Database management | Connect to Cloud SQL, manage instances |
| `roles/logging.logWriter` | Application logging | Write logs to Cloud Logging |
| `roles/monitoring.metricWriter` | Metrics collection | Write custom metrics to Cloud Monitoring |

### Bucket-Level Roles

The service account has the following bucket-specific IAM bindings on `loist-music-library-audio`:

| Role | Purpose | Scope |
|------|---------|-------|
| `roles/storage.objectAdmin` | Object management | Create, read, update, delete objects |

### Permission Matrix

| Operation | Required Role | Service Account Has |
|-----------|--------------|-------------------|
| Upload audio files | `storage.objects.create` | ✅ Yes (`objectAdmin`) |
| Download audio files | `storage.objects.get` | ✅ Yes (`objectAdmin`) |
| Delete audio files | `storage.objects.delete` | ✅ Yes (`objectAdmin`) |
| List bucket contents | `storage.objects.list` | ✅ Yes (`objectAdmin`) |
| Generate signed URLs | `iam.serviceAccounts.signBlob` | ✅ Yes (`storage.admin`) |
| Modify bucket settings | `storage.buckets.update` | ✅ Yes (`storage.admin`) |
| Read object metadata | `storage.objects.get` | ✅ Yes (`objectAdmin`) |
| Set object metadata | `storage.objects.update` | ✅ Yes (`objectAdmin`) |

### Least-Privilege Recommendations

**Current State:** The service account has `roles/storage.admin` at project level, which is broader than necessary.

**Recommended Refinement:**

```bash
# Remove project-level storage.admin
gcloud projects remove-iam-policy-binding loist-music-library \
  --member="serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Keep bucket-level objectAdmin (already configured)
# This provides sufficient permissions for application operations
```

**Result:** Application retains full object management capabilities on the specific bucket while reducing project-wide permissions.

## Credential Management

### Configuration Hierarchy

The application uses a layered configuration approach for credentials:

1. **Direct parameters** (highest priority)
2. **Application config** (`src/config.py` loaded from `.env`)
3. **Environment variables** (fallback)
4. **Google Application Default Credentials** (ADC)

### Environment Variables

#### GCS Authentication

```bash
# Method 1: Service account key file (recommended for development)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Method 2: Via application config
export GCS_PROJECT_ID="loist-music-library"
export GCS_BUCKET_NAME="loist-music-library-audio"
export GCS_SERVICE_ACCOUNT_EMAIL="loist-music-library-sa@loist-music-library.iam.gserviceaccount.com"
```

#### Database Authentication

```bash
# Cloud SQL Proxy connection (recommended)
export DB_CONNECTION_NAME="loist-music-library:us-central1:loist-music-library-db"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"

# Or direct connection
export DB_HOST="34.121.42.105"
export DB_PORT="5432"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"
```

### Configuration Loading

#### Python Config Module

```python
from src.config import config

# Check if services are configured
print(config.is_gcs_configured)      # True/False
print(config.is_database_configured) # True/False

# Validate all credentials
status = config.validate_credentials()
print(status)  # {'gcs': True, 'database': True, 'auth': True}

# Get credentials path
creds_path = config.gcs_credentials_path
print(creds_path)  # /path/to/service-account-key.json
```

#### GCS Client Initialization

```python
from src.storage import create_gcs_client

# Option 1: Use application config (automatic)
client = create_gcs_client()

# Option 2: Explicit configuration
client = create_gcs_client(
    bucket_name="loist-music-library-audio",
    project_id="loist-music-library",
    credentials_path="/path/to/service-account-key.json"
)

# Option 3: Environment variables only
# Set GOOGLE_APPLICATION_CREDENTIALS, GCS_BUCKET_NAME, GCS_PROJECT_ID
client = create_gcs_client()
```

### Production Deployment

#### Compute Engine / GKE

For production deployments on Google Cloud infrastructure, use **Workload Identity** instead of service account keys:

```yaml
# Kubernetes deployment with Workload Identity
apiVersion: v1
kind: ServiceAccount
metadata:
  name: loist-music-library-ksa
  annotations:
    iam.gke.io/gcp-service-account: loist-music-library-sa@loist-music-library.iam.gserviceaccount.com
```

**Benefits:**
- No service account keys to manage
- Automatic credential rotation
- Better audit trail
- Reduced security risk

#### Cloud Run

```bash
gcloud run deploy loist-music-library \
  --service-account=loist-music-library-sa@loist-music-library.iam.gserviceaccount.com \
  --set-env-vars="GCS_BUCKET_NAME=loist-music-library-audio,GCS_PROJECT_ID=loist-music-library"
```

## Authentication Flow

### Application Startup

```
1. Load configuration from .env file
   ↓
2. Check credential sources:
   - config.google_application_credentials
   - GOOGLE_APPLICATION_CREDENTIALS env var
   ↓
3. Validate credentials exist and are readable
   ↓
4. Initialize GCS client with credentials
   ↓
5. Verify bucket access
   ↓
6. Ready for operations
```

### GCS Operation Authentication

```
1. Application receives request (e.g., upload audio file)
   ↓
2. GCS client checks for credentials:
   - From initialization parameters
   - From application config
   - From environment variables
   - From Google ADC
   ↓
3. Google Cloud SDK authenticates request
   ↓
4. IAM evaluates permissions
   ↓
5. Operation succeeds or fails with permission error
   ↓
6. Result returned to application
```

### Signed URL Generation

```
1. Application requests signed URL for blob
   ↓
2. GCS client uses service account credentials
   ↓
3. Requires iam.serviceAccounts.signBlob permission
   ↓
4. Generates cryptographic signature
   ↓
5. Returns time-limited URL (default: 15 minutes)
   ↓
6. Client uses URL for direct GCS access
   ↓
7. URL expires automatically
```

## Security Best Practices

### 1. Credential Protection

✅ **DO:**
- Store service account keys outside version control (`.gitignore`)
- Use environment variables for sensitive data
- Rotate service account keys regularly (90 days)
- Use Workload Identity in production
- Implement secret management (Google Secret Manager)
- Restrict key file permissions (`chmod 600`)

❌ **DON'T:**
- Commit service account keys to Git
- Store keys in Docker images
- Share keys via insecure channels
- Use keys in client-side code
- Leave keys in log files

### 2. Least Privilege Access

✅ **DO:**
- Grant minimum required permissions
- Use bucket-level IAM over project-level
- Create role-specific service accounts
- Regularly audit IAM policies
- Use conditions for fine-grained access

❌ **DON'T:**
- Grant project Owner role
- Use wildcard permissions
- Share service accounts across applications
- Grant permanent broad access

### 3. Signed URL Security

✅ **DO:**
- Use short expiration times (5-15 minutes)
- Generate URLs per-request
- Log URL generation for audit
- Use HTTPS-only URLs
- Validate blob existence before signing

❌ **DON'T:**
- Cache signed URLs beyond expiration
- Use long expiration times (hours/days)
- Share signed URLs publicly
- Log complete signed URLs
- Allow client-side URL generation

### 4. Network Security

✅ **DO:**
- Use VPC Service Controls (if applicable)
- Enable uniform bucket-level access
- Require TLS 1.2+ for connections
- Monitor unusual access patterns
- Implement rate limiting

❌ **DON'T:**
- Allow public bucket access
- Use HTTP for sensitive operations
- Disable SSL certificate validation
- Ignore failed authentication attempts

### 5. Monitoring and Alerting

✅ **DO:**
- Enable Cloud Audit Logs
- Monitor authentication failures
- Alert on permission changes
- Track unusual API usage
- Review access logs regularly

❌ **DON'T:**
- Disable audit logging
- Ignore security alerts
- Skip log analysis
- Allow anonymous access

## Access Control Patterns

### Pattern 1: Application-Level Access Control

```python
from src.storage import GCSClient
from src.auth import require_user_role

@require_user_role("audio_uploader")
async def upload_track(user_id: str, file_path: str):
    """Upload track with user-level access control."""
    client = GCSClient()
    
    # Application enforces authorization
    if not user_can_upload(user_id):
        raise PermissionError("User not authorized to upload")
    
    # GCS operation uses service account
    blob_name = f"audio/{user_id}/{uuid4()}.mp3"
    return client.upload_file(file_path, blob_name)
```

### Pattern 2: Signed URLs for Client Access

```python
from src.storage import generate_signed_url

async def get_stream_url(track_id: str, user_id: str):
    """Generate streaming URL with user validation."""
    
    # Application validates user access
    if not user_can_stream(user_id, track_id):
        raise PermissionError("Access denied")
    
    # Generate time-limited URL
    blob_name = f"audio/{track_id}.mp3"
    url = generate_signed_url(
        blob_name=blob_name,
        expiration_minutes=15
    )
    
    return {"stream_url": url, "expires_in": 900}
```

### Pattern 3: Service Account Impersonation

```python
from google.auth import impersonated_credentials
from google.cloud import storage

def create_impersonated_client(target_sa_email: str):
    """Create client with impersonated service account."""
    
    # Source credentials (application default)
    source_credentials, _ = google.auth.default()
    
    # Impersonate target service account
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=target_sa_email,
        target_scopes=['https://www.googleapis.com/auth/devstorage.read_write']
    )
    
    # Create client with impersonated credentials
    return storage.Client(credentials=target_credentials)
```

## Monitoring and Auditing

### Cloud Audit Logs

Enable and monitor the following audit log types:

1. **Admin Activity Logs**
   - IAM policy changes
   - Service account creation/deletion
   - Bucket configuration changes

2. **Data Access Logs**
   - Object read/write operations
   - Signed URL generation
   - Authentication attempts

### Key Metrics to Monitor

```yaml
Metrics:
  - storage.googleapis.com/authz/acl_operations_count
  - storage.googleapis.com/authz/acl_based_object_access_count
  - storage.googleapis.com/api/request_count (filtered by 403 errors)
  - iam.googleapis.com/service_account/key/authn_events_count
  
Alerts:
  - Failed authentication rate > 10/minute
  - New service account key created
  - IAM policy changes
  - Unusual access patterns (e.g., high download volume)
```

### Audit Query Examples

```sql
-- Find all signed URL generations
resource.type="gcs_bucket"
protoPayload.methodName="storage.buckets.get"
protoPayload.authorizationInfo.permission="storage.buckets.get"

-- Find failed authentication attempts
protoPayload.status.code!=0
protoPayload.authenticationInfo.principalEmail=~".*@loist-music-library.iam.gserviceaccount.com"

-- Find IAM policy changes
protoPayload.methodName:"SetIamPolicy"
resource.labels.bucket_name="loist-music-library-audio"
```

## Troubleshooting

### Authentication Errors

#### Error: "Permission denied"

```python
# Symptom
google.cloud.exceptions.Forbidden: 403 Permission denied

# Diagnosis
gcloud projects get-iam-policy loist-music-library \
  --flatten="bindings[].members" \
  --filter="bindings.members:loist-music-library-sa@"

# Solution
# Grant required IAM role
gsutil iam ch \
  serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com:roles/storage.objectAdmin \
  gs://loist-music-library-audio
```

#### Error: "Could not automatically determine credentials"

```python
# Symptom
google.auth.exceptions.DefaultCredentialsError

# Diagnosis
echo $GOOGLE_APPLICATION_CREDENTIALS
ls -l $GOOGLE_APPLICATION_CREDENTIALS

# Solution
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

#### Error: "Service account does not have permission to sign blobs"

```python
# Symptom
google.api_core.exceptions.Forbidden: Missing signBlob permission

# Diagnosis
# Check if service account has iam.serviceAccounts.signBlob permission

# Solution
gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### Configuration Issues

#### Credentials not loading

```python
# Debug credential loading
from src.config import config

print("GCS configured:", config.is_gcs_configured)
print("Credentials path:", config.gcs_credentials_path)
print("Bucket name:", config.gcs_bucket_name)
print("Project ID:", config.gcs_project_id)

# Validate credentials
status = config.validate_credentials()
print("Validation:", status)
```

#### Multiple credential sources

```python
# Credential precedence (highest to lowest):
1. Explicit parameters to GCSClient()
2. Application config (src/config.py)
3. Environment variables
4. Google Application Default Credentials

# To force a specific source, use explicit parameters:
client = GCSClient(credentials_path="/specific/path/to/key.json")
```

## Security Checklist

Use this checklist to validate authentication and access control:

- [ ] Service account key file is gitignored
- [ ] Service account has minimum required permissions
- [ ] Bucket-level IAM is used instead of project-level where possible
- [ ] Signed URLs use short expiration times (< 15 minutes)
- [ ] Cloud Audit Logs are enabled
- [ ] Failed authentication monitoring is configured
- [ ] Service account key rotation schedule is defined
- [ ] Production uses Workload Identity (not keys)
- [ ] Credentials are never logged or printed
- [ ] Access control is enforced at application level
- [ ] Regular security audits are scheduled
- [ ] IAM policy changes trigger alerts

## Next Steps

After completing authentication setup:

1. ✅ **Subtask 2.5** - Configure Database Connection Pooling
2. ✅ **Subtask 2.6** - Develop Database Migration Scripts
3. ✅ **Subtask 2.7** - Configure GCS Lifecycle Policies (complete)
4. ✅ **Subtask 2.8** - Implement Signed URL Generation System (complete)

## References

- [Google Cloud IAM Documentation](https://cloud.google.com/iam/docs)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [GCS Access Control](https://cloud.google.com/storage/docs/access-control)
- [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [Cloud Audit Logs](https://cloud.google.com/logging/docs/audit)

---

**Subtask 2.4 Status**: Complete ✅  
**Date**: 2025-10-09  
**Service Account**: loist-music-library-sa@loist-music-library.iam.gserviceaccount.com  
**Bucket**: gs://loist-music-library-audio

