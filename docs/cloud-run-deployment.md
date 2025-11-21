# Cloud Run Automated Deployment

This document describes the comprehensive automated deployment pipeline for the Loist Music Library MCP Server to Google Cloud Run, featuring vulnerability scanning, security hardening, and complete environment variable management.

## Overview

The deployment uses Google Cloud Build with an optimized pipeline that includes:

- **7-step automated process**: Tests → Validation → Migrations → Build → Deploy
- **Multi-stage Docker builds** with Alpine builder → Alpine runtime for optimal security and reliability
- **Cloud Build optimized** for Google Cloud Build compatibility (no BuildKit dependencies)
- **Comprehensive environment variable configuration** (50+ variables across all functional areas)
- **Secret management** for sensitive data via Google Secret Manager
- **Artifact Registry integration** for modern container registry management
- **Built-in health checks** via Cloud Run (no manual health check steps needed)
- **Automatic database migrations** during deployment for schema consistency

## Table of Contents

- [Prerequisites](#prerequisites)
- [Required Setup](#required-setup)
- [Staging Environment](#staging-environment)
- [Database Migrations](#database-migrations)
- [Cloud Build Pipeline](#cloud-build-pipeline)
- [Environment Variables](#environment-variables)
- [Deployment Process](#deployment-process)
- [Deployment Validation](#deployment-validation)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Security Considerations](#security-considerations)
- [Rollback Procedures](#rollback-procedures)

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed (for local testing)
- Required APIs enabled:
  - Cloud Run API
  - Container Registry API
  - Cloud Build API
  - Secret Manager API
  - Cloud SQL API (if using database)

## Required Setup

### 1. Service Account & Permissions

Create a service account with required roles:

```bash
# Create service account
gcloud iam service-accounts create music-library-deployer \
  --display-name="Music Library Deployment Service Account" \
  --project=loist-music-library

# Grant required roles
gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:music-library-deployer@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:music-library-deployer@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:music-library-deployer@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:music-library-deployer@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:music-library-deployer@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Create and download key (for local development)
gcloud iam service-accounts keys create deployer-key.json \
  --iam-account=music-library-deployer@loist-music-library.iam.gserviceaccount.com
```

### 1.5. Runtime Service Account (IAM SignBlob)

For Cloud Run runtime, create a dedicated service account for GCS signed URL generation using IAM SignBlob:

```bash
# Create runtime service account
gcloud iam service-accounts create mcp-music-library-sa \
  --display-name="Music Library MCP Runtime Service Account" \
  --project=loist-music-library

# Grant GCS permissions
gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Grant IAM SignBlob permission (required for signed URL generation)
gcloud iam service-accounts add-iam-policy-binding mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

# Note: No keyfile needed - Cloud Run uses Application Default Credentials (ADC)
# with IAM SignBlob for secure signed URL generation without storing private keys
```

**Why IAM SignBlob?**
- ✅ No private key files to store/rotate/manage
- ✅ Automatic key rotation by Google
- ✅ Works with Cloud Run's built-in IAM authentication
- ✅ More secure than keyfile-based signing

### 2. Artifact Registry Repository

Create the container registry:

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create music-library-repo \
  --repository-format=docker \
  --location=us-central1 \
  --project=loist-music-library \
  --description="Docker repository for Music Library MCP Server"

# Or use the provided script
./scripts/create-artifact-registry.sh
```

### 3. Secrets Manager Setup

Store sensitive configuration in Secret Manager:

```bash
# Database connection name
echo -n "loist-music-library:us-central1:loist-music-library-db" | \
  gcloud secrets create db-connection-name \
    --data-file=- \
    --project=loist-music-library

# GCS bucket name
echo -n "loist-mvp-audio-files" | \
  gcloud secrets create gcs-bucket-name \
    --data-file=- \
    --project=loist-music-library

# Optional: Database credentials (if not using IAM authentication)
echo -n "your-db-password" | \
  gcloud secrets create db-password \
    --data-file=- \
    --project=loist-music-library
```

### 4. Cloud SQL Instance (Optional)

If using Cloud SQL:

```bash
# Create Cloud SQL instance
gcloud sql instances create loist-music-library-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --project=loist-music-library

# Create database
gcloud sql databases create loist_mvp \
  --instance=loist-music-library-db \
  --project=loist-music-library

# Create user
gcloud sql users create music_library_user \
  --instance=loist-music-library-db \
  --password=your-secure-password \
  --project=loist-music-library
```

## Staging Environment

The staging environment provides a complete testing environment that mirrors production with the following key differences:

### Staging Database Setup

- **Database Name**: `loist_mvp_staging` (separate from production `music_library`)
- **Automatic Creation**: Cloud Build creates the staging database if it doesn't exist
- **Schema Migration**: Full schema applied during deployment
- **Data Isolation**: Completely separate from production data

### Staging Configuration

```yaml
# Staging-specific environment variables
EMBED_BASE_URL=https://staging.loist.io
SERVER_NAME=Music Library MCP - Staging
LOG_LEVEL=DEBUG
AUTH_ENABLED=false
DB_NAME=loist_mvp_staging
```

### Staging Deployment Pipeline

The `cloudbuild-staging.yaml` includes steps for staging setup:

1. **Unit Tests**: Fast tests without external dependencies (65% coverage)
2. **Database Tests**: Integration tests using testcontainers (60% coverage)
3. **Static Analysis**: Code quality checks (black, isort, mypy, flake8, bandit)
4. **Build & Push**: Optimized Docker image for staging
5. **Database Setup**: Create `loist_mvp_staging` database if needed
6. **Deploy**: Deploy to Cloud Run with staging configuration

**Note**: Database migrations for staging run post-deployment using `scripts/migrate-db.sh staging`

## Database Migrations

The deployment pipeline includes automatic database migration execution to ensure schema consistency across environments using a robust Python-based migration system.

### Production & Staging Migrations

**Automatic execution**: Both production and staging pipelines run all pending database migrations automatically. The system ensures:

- Zero-downtime schema updates
- Consistent database state across all environments
- Automatic rollback capability if migrations fail
- Migration tracking to prevent duplicate execution
- Seamless schema evolution as features are added

### Migration System Features

- **Automatic discovery**: All `.sql` files in `database/migrations/` are applied in order
- **Idempotent**: Migrations only run once, tracked in `schema_migrations` table
- **Transactional**: Each migration runs in a transaction for consistency
- **Ordered**: Migrations execute in version order (001, 002, 003, etc.)
- **Environment-aware**: Automatically detects and connects to appropriate databases
- **Error handling**: Failed migrations prevent deployment continuation
- **Validation**: Post-migration status checks ensure all migrations applied

### Available Migrations

1. **001_initial_schema.sql**: Core audio_tracks table, indexes, and triggers
2. **002_add_user_id.sql**: Multi-user support with user_id column
3. **002_add_waveform_support.sql**: Waveform generation columns (waveform_gcs_path, waveform_generated_at, source_audio_hash)
4. **002_performance_indexes.sql**: Additional performance optimizations
5. **003_add_a2a_tasks.sql**: Agent-to-agent task coordination table
6. **004_add_xmp_fields.sql**: XMP metadata fields (composer, publisher, record_label, isrc)
7. **005_optimize_xmp_indexes.sql**: Composite indexes for XMP field filtering
8. **006_optimize_search_vector.sql**: Enhanced full-text search optimization

### Migration Scripts

Two migration tools are available:

- **`database/migrate.py`**: Python-based migration system (automatic discovery, robust error handling)
- **`scripts/migrate-db.sh`**: Shell script wrapper that uses the Python migrator (Cloud Build compatible)

### Migration Execution

Migrations run automatically during deployment:

```bash
# Staging environment (post-deployment)
./scripts/migrate-db.sh staging

# Production environment (during deployment)
# Handled automatically by Cloud Build pipeline
```

The Python migrator (`database/migrate.py`) automatically:
- Discovers all migration files in `database/migrations/`
- Applies them in sorted order
- Tracks execution in `schema_migrations` table
- Provides detailed status reporting

### EMBED_BASE_URL Configuration Fix

**Issue Fixed**: Dockerfile ENV defaults were preventing runtime overrides.

**Solution Applied**:
- Removed `EMBED_BASE_URL="https://loist.io"` from Dockerfile
- Updated Pydantic config to handle missing `.env` files gracefully
- Cloud Run runtime injection now works: `EMBED_BASE_URL=https://staging.loist.io`

**Verification**: MCP `process_audio_complete` returns `urlEmbedLink: "https://staging.loist.io/embed/{uuid}"`

### Staging Testing

Use the comprehensive test script to verify staging deployment:

```bash
# Run full staging deployment and EMBED_BASE_URL test
./scripts/test-staging-deployment.sh

# Or test EMBED_BASE_URL fix specifically
./scripts/test-embed-url-fix.sh
```

## Cloud Build Pipeline

The optimized `cloudbuild.yaml` pipeline includes the following **7 steps**:

### Build Configuration

```yaml
steps:
  # 1. Build optimized Docker image with BuildKit caching
  - name: 'gcr.io/cloud-builders/docker'
    id: 'build-image'
    args: [
      'build',
      # Enable BuildKit for better performance and caching
      '--build-arg', 'BUILDKIT_INLINE_CACHE=1',
      # Use cache from previous builds
      '--cache-from', 'us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:latest',
      # Enable BuildKit cache mounts for faster builds
      '--build-arg', 'BUILDKIT_PROGRESS=plain',
      # Optimized tagging: commit SHA and latest only
      '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:$COMMIT_SHA',
      '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:latest',
      # Build context
      '.'
    ]
    env:
      - 'DOCKER_BUILDKIT=1'
    timeout: '600s'

  # 2. Push image to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    id: 'push-image'
    args: ['push', '--all-tags', 'us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp']
    waitFor: ['build-image']

  # 3. Deploy to Cloud Run (uses built-in health checks)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    id: 'deploy-cloud-run'
    args:
      - 'run'
      - 'deploy'
      - 'music-library-mcp'
      - '--image=us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:$COMMIT_SHA'
      - '--platform=managed'
      - '--region=us-central1'
      - '--allow-unauthenticated'
      - '--memory=2Gi'
      - '--cpu=1'
      - '--max-instances=10'
      - '--min-instances=0'
      - '--timeout=600'
      - '--concurrency=80'
      - '--service-account=mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com'
      # Note: No --update-secrets for GOOGLE_APPLICATION_CREDENTIALS - uses IAM SignBlob
      # Comprehensive environment variables...
```

### Build Optimizations

- **BuildKit Cache Mounts**: `--mount=type=cache` for pip and apk caching (faster subsequent builds)
- **Layer Caching**: `--cache-from` uses previous builds for faster builds
- **Optimized Machine Type**: `E2_HIGHCPU_8` for faster builds at same cost
- **Reduced Build Steps**: Streamlined from 9 to 3 steps (Build → Push → Deploy)
- **BuildKit Features**: Advanced build features with inline cache and progress optimization
- **Timeout Optimization**: Reduced from 20 to 10 minutes (builds complete in ~5min)

### Vulnerability Scanning

The pipeline includes automated security scanning:

```yaml
# Check for critical/high severity vulnerabilities
- name: 'gcr.io/cloud-builders/gcloud'
  id: 'check-vulnerabilities'
  entrypoint: 'bash'
  args:
    - '-c'
    - |
      echo "🔍 Checking vulnerability scan results..."
      CRITICAL_VULNS=$(gcloud artifacts docker images list-vulnerabilities \
        us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:$COMMIT_SHA \
        --format='value(vulnerability.effectiveSeverity)' \
        --filter='vulnerability.effectiveSeverity:(CRITICAL HIGH)' | wc -l)

      if [ "$CRITICAL_VULNS" -gt 0 ]; then
        echo "❌ Found $CRITICAL_VULNS critical/high severity vulnerabilities"
        # Log but don't fail build (uncomment to fail)
        # exit 1
      fi
```

## Environment Variables

The deployment configures 50+ environment variables across all functional areas:

### Server Identity & Runtime
```yaml
SERVER_NAME: "Music Library MCP"
SERVER_VERSION: "0.1.0"
SERVER_TRANSPORT: http
SERVER_HOST: 0.0.0.0
SERVER_PORT: 8080
```

### Authentication & Security
```yaml
AUTH_ENABLED: false
ENABLE_CORS: true
CORS_ORIGINS: "*"
CORS_ALLOW_CREDENTIALS: true
```

### Logging & Monitoring
```yaml
LOG_LEVEL: INFO
LOG_FORMAT: text
ENABLE_METRICS: false
ENABLE_HEALTHCHECK: true
```

### Performance & Scaling
```yaml
MAX_WORKERS: 4
REQUEST_TIMEOUT: 30
STORAGE_PATH: /tmp/storage
MAX_FILE_SIZE: 104857600
```

### Google Cloud Integration
```yaml
GCS_PROJECT_ID: $PROJECT_ID
GCS_REGION: us-central1
GCS_SIGNED_URL_EXPIRATION: 900
DB_CONNECTION_NAME: <from secrets>
```

### MCP Protocol Configuration
```yaml
MCP_PROTOCOL_VERSION: "2024-11-05"
INCLUDE_FASTMCP_META: true
ON_DUPLICATE_TOOLS: error
ON_DUPLICATE_RESOURCES: warn
ON_DUPLICATE_PROMPTS: replace
```

📚 **Complete Environment Variables**: See [`docs/environment-variables.md`](docs/environment-variables.md) for detailed documentation of all variables.

## Deployment Process

### Automated Deployment

1. **Trigger**: Push to `main` branch or manual Cloud Build trigger
2. **Build**: Optimized multi-stage Docker build with BuildKit caching
3. **Push**: Image pushed to Artifact Registry with commit SHA and latest tags
4. **Deploy**: Cloud Run service updated with new image and configuration
5. **Health Check**: Automatic Cloud Run built-in health validation
6. **Complete**: Deployment status reported

### Manual Deployment

```bash
# Set project
export PROJECT_ID=loist-music-library

# Build and submit to Cloud Build
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _GCS_BUCKET_NAME=loist-mvp-audio-files,_DB_CONNECTION_NAME=loist-music-library:us-central1:loist-music-library-db \
  --project=$PROJECT_ID \
  .
```

## Rollback Procedures

### IAM SignBlob Rollback

If IAM SignBlob signed URL generation fails in production, you can temporarily revert to keyfile-based signing:

#### Option 1: Environment Variable Override
```bash
# Deploy with keyfile mode
gcloud run deploy music-library-mcp \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:latest \
  --region=us-central1 \
  --set-env-vars=GCS_SIGNER_MODE=keyfile \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=your-service-account-key:latest \
  --service-account=mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com
```

#### Option 2: Code Rollback
If environment variable override fails, revert the GCS client code:

```bash
# Revert src/storage/gcs_client.py to previous version
git revert HEAD~3  # Revert the IAM SignBlob implementation

# Redeploy with keyfile support
gcloud run deploy music-library-mcp \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:latest \
  --region=us-central1 \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=your-service-account-key:latest \
  --service-account=mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com
```

#### Option 3: Emergency Keyfile Mount
For immediate emergency rollback (not recommended for production):

```bash
# Mount service account key as secret
gcloud run deploy music-library-mcp \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/music-library-mcp:latest \
  --region=us-central1 \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=your-service-account-key:latest \
  --set-env-vars=GOOGLE_APPLICATION_CREDENTIALS=/secrets/GOOGLE_APPLICATION_CREDENTIALS/latest \
  --service-account=mcp-music-library-sa@$PROJECT_ID.iam.gserviceaccount.com
```

### GitHub Actions Integration (Optional)

For GitHub-triggered deployments:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud Run
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/setup-gcloud@v2
        with:
          service_account_key: ${{ secrets.GCLOUD_SERVICE_KEY }}
      - run: gcloud builds submit --config cloudbuild.yaml .
```

## Monitoring & Troubleshooting

### Cloud Build Logs

```bash
# View recent builds
gcloud builds list --project=loist-music-library

# View specific build logs
gcloud builds log --project=loist-music-library BUILD_ID
```

### Cloud Run Monitoring

```bash
# View service status
gcloud run services describe music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=music-library-mcp" \
  --project=loist-music-library \
  --limit=50
```

### Common Issues & Solutions

#### Build Failures

**Issue**: `psutil` compilation fails
```
fatal error: linux/ethtool.h: No such file or directory
```
**Solution**: Ensure `linux-headers` is installed in builder stage (already configured)

**Issue**: Cache import authorization failed
**Solution**: Ensure Artifact Registry permissions are correct

#### Deployment Failures

**Issue**: Service account permission denied
**Solution**: Verify IAM roles are correctly assigned

**Issue**: Secret not found
**Solution**: Check Secret Manager setup and permissions

**Issue**: Health check timeout
**Solution**: Verify application startup and database connectivity

#### Runtime Issues

**Issue**: Container exits immediately
**Solution**: Check logs for startup errors, verify environment variables

**Issue**: Database connection fails
**Solution**: Verify Cloud SQL IAM authentication or secret configuration

### Health Checks

The deployment includes health verification:

```bash
# Health checks are handled automatically by Cloud Run
# Manual verification (optional):
curl -f https://music-library-mcp-<hash>-uc.a.run.app/mcp/health

# Expected response
{
  "status": "healthy",
  "service": "Music Library MCP",
  "version": "0.1.0"
}
```

## Deployment Validation

### Automated Validation Suite

After deployment, validate all components using the comprehensive validation scripts:

```bash
# Run full validation suite
./scripts/validate-deployment.sh
```

This validates:
- ✅ Cloud Build trigger configuration
- ✅ Cloud Run service accessibility
- ✅ Database connectivity
- ✅ GCS bucket operations
- ✅ Environment configuration
- ✅ MCP protocol functionality (via Inspector)

### Individual Validation Scripts

Test specific components:

```bash
# Test Cloud Build triggers
./scripts/test-deployment-triggers.sh

# Test Cloud Run service
./scripts/validate-cloud-run.sh

# Test database (requires credentials)
./scripts/validate-database.sh

# Test GCS storage
./scripts/validate-gcs.sh
```

### Validation Documentation

For comprehensive validation procedures, see:
- **[Deployment Validation Guide](./deployment-validation-guide.md)** - How to run validation scripts
- **[Deployment Validation Results](./deployment-validation-results.md)** - Latest validation status
- **[Troubleshooting Guide](./troubleshooting-deployment.md)** - Common issues and solutions
- **[Rollback Procedures](./deployment-rollback-procedure.md)** - How to rollback deployments

### Post-Deployment Checklist

- [ ] Run validation suite: `./scripts/validate-deployment.sh`
- [ ] Verify service URLs accessible
- [ ] Test MCP tools via MCP Inspector
- [ ] Check Cloud Monitoring metrics
- [ ] Review Cloud Logging for errors
- [ ] Verify database connectivity
- [ ] Test GCS upload/download
- [ ] Confirm environment variables loaded
- [ ] Review security settings

## Security Considerations

### Container Security

- **Non-root user**: Container runs as `fastmcpuser` (UID 1000)
- **Minimal base image**: Alpine Linux runtime with only required libraries
- **Proper permissions**: Files and directories have restricted permissions (644/755)
- **Stateless design**: No persistent data in containers

### Network Security

- **IAM authentication**: Service account-based authentication
- **Secret Manager**: Sensitive data stored securely
- **VPC connectivity**: Cloud SQL accessed via VPC (recommended)
- **Firewall rules**: Restrictive ingress rules

### Runtime Security

- **Environment hardening**: `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE`
- **Stateless operation**: `/tmp` for temporary files, no persistent state
- **Resource limits**: Memory and CPU limits enforced
- **Timeout protection**: Request timeouts prevent resource exhaustion

## Rollback Procedures

### Automatic Rollback

Failed deployments automatically roll back to the previous revision.

### Manual Rollback

```bash
# List revisions
gcloud run revisions list \
  --service=music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library

# Roll back to specific revision
gcloud run services update-traffic music-library-mcp \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1 \
  --project=loist-music-library
```

### Emergency Rollback

For immediate rollback to a known good state:

```bash
# Deploy known good image directly
gcloud run deploy music-library-mcp \
  --image=us-central1-docker.pkg.dev/loist-music-library/music-library-repo/music-library-mcp:v1.0.0 \
  --platform=managed \
  --region=us-central1 \
  --project=loist-music-library
```

## Performance Optimization

### Build Performance

- **Layer caching**: Reduces build time for unchanged layers
- **Parallel builds**: Multiple CPU cores utilized
- **Incremental builds**: Only changed files trigger rebuilds

### Runtime Performance

- **Memory optimization**: 2GB RAM allocation for typical workloads
- **CPU allocation**: 1 vCPU with burst capacity
- **Concurrency**: 80 concurrent requests per instance
- **Auto-scaling**: 0-10 instances based on load

### Cost Optimization

- **Scale to zero**: No instances when idle
- **Regional deployment**: Single region deployment
- **Resource limits**: Appropriate CPU/memory allocation
- **Build optimization**: Faster builds reduce costs

## Integration with Development Workflow

This deployment pipeline integrates with the Task-Master development workflow:

1. **Local Development**: Use `docker-compose.yml` for development
2. **Testing**: Use `scripts/test-container-build.sh` for validation
3. **Staging**: Deploy to staging environment for QA
4. **Production**: Automated deployment on main branch merges

## Next Steps

1. **Staging Environment**: Create separate staging Cloud Run service
2. **Blue/Green Deployments**: Implement zero-downtime deployments
3. **Custom Domain**: Set up custom domain mapping
4. **Advanced Monitoring**: Add Cloud Monitoring and alerting
5. **CI/CD Integration**: Connect with GitHub Actions for full automation
6. **Multi-region**: Deploy to multiple regions for high availability

---

📚 **Related Documentation**:
- [Environment Variables Configuration](docs/environment-variables.md)
- [Docker Build Scripts](../scripts/)
- [Local Development Setup](README.md#docker)
