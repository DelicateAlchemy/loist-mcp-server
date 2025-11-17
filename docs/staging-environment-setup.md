# Staging Environment Setup and Usage Guide

**Version:** 1.0
**Last Updated:** November 5, 2025
**Task:** Task #15 - Configure Development/Staging Environment with Docker and GCS Integration

## Overview

The staging environment provides a production-like setup for comprehensive integration testing, QA validation, and pre-deployment verification. It bridges the gap between local development and production deployment with containerization, test data, and automated deployment pipelines.

## Architecture Overview

### Infrastructure Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Staging Environment                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Cloud Run  │  │ Cloud SQL   │  │ Cloud       │         │
│  │  Service    │  │ Database    │  │ Storage     │         │
│  │             │  │ (Staging)   │  │ (Staging)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ CI/CD       │  │ Secrets     │  │ Monitoring  │         │
│  │ Pipeline    │  │ Manager     │  │ (Future)    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Service Specifications

- **Cloud Run Service**: `music-library-mcp-staging`
- **Database**: `loist_mvp_staging` (Cloud SQL)
- **Storage**: `loist-music-library-bucket-staging` (GCS)
- **Domain**: `https://staging.loist.io`
- **Region**: `us-central1`

## Prerequisites

- Google Cloud SDK (`gcloud`)
- Access to Google Cloud Project (`loist-music-library`)
- Appropriate IAM permissions for Cloud Build and Cloud Run

### Environment Variables

Create a `.env.staging` file with:

```bash
# Database Configuration
DB_CONNECTION_NAME=your-project:us-central1:loist-music-library-db
DB_PASSWORD=your-staging-db-password
GCS_PROJECT_ID=loist-music-library

# GCS Configuration (IAM SignBlob - no keyfile secrets needed)
GCS_BUCKET_NAME_STAGING=loist-music-library-bucket-staging
# Note: Cloud Run service account (mcp-music-library-sa) handles GCS access via IAM
# No GOOGLE_APPLICATION_CREDENTIALS secret mounting required

# Application Settings
ENVIRONMENT=staging
LOG_LEVEL=DEBUG
```

## Cloud Deployment

### Automated Deployment

Deployments to staging are triggered automatically when code is pushed to the `dev` branch:

```bash
# Push to dev branch triggers staging deployment
git checkout dev
git merge task-15
git push origin dev
```

### Manual Deployment

For manual deployments or testing:

```bash
# Build and deploy staging
./scripts/test-staging-deployment.sh
```

### Cloud Build Configuration

The `cloudbuild-staging.yaml` handles:

1. **Docker Image Build**: Optimized multi-stage build
2. **Artifact Registry**: Push to `us-central1-docker.pkg.dev`
3. **Database Setup**: Create/verify staging database
4. **Secrets Update**: Refresh staging secrets
5. **Cloud Run Deploy**: Deploy with staging configuration

## Database Management

### Staging Database

- **Name**: `loist_mvp_staging`
- **Instance**: `loist-music-library-db`
- **User**: `music_library_user`
- **Schema**: Mirrors production schema

### Database Operations

#### Create Staging Database
```bash
./scripts/create-staging-database.sh
```

#### Run Migrations
```bash
./scripts/migrate-db.sh
```

#### Seed Test Data
```bash
./scripts/seed-staging-database.sh
```

### Test Data Overview

The staging database includes:

- **12 sample audio tracks** with various formats (FLAC, WAV, MP3, M4A)
- **Full-text search vectors** for testing search functionality
- **Thumbnail records** for image handling tests
- **Processing status records** (completed, in-progress, failed states)
- **Edge cases**: Special characters, long titles, various file sizes

## Storage Management

### GCS Staging Bucket

- **Name**: `loist-music-library-bucket-staging`
- **Location**: `us-central1`
- **Storage Class**: `STANDARD`
- **Lifecycle Policies**: Automatic cleanup of temporary files

### Bucket Structure

```
gs://loist-music-library-bucket-staging/
├── audio/           # Permanent audio file storage
├── thumbnails/      # Album/track thumbnail images
├── temp/           # Temporary uploads (deleted after 24 hours)
├── test/           # Test data files (deleted after 24 hours)
└── staging/        # Staging-specific content (deleted after 7 days)
```

### Storage Operations

#### Configure Bucket
```bash
./scripts/create-staging-gcs-bucket.sh
```

#### Check Bucket Status
```bash
gsutil ls -L gs://loist-music-library-bucket-staging
```

#### View Lifecycle Policies
```bash
gsutil lifecycle get gs://loist-music-library-bucket-staging
```

## Security Configuration

### IAM Permissions

Staging environment uses least-privilege access:

- **Service Account**: `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com`
- **Database**: Read/write access to `loist_mvp_staging`
- **Storage**: Object admin access to staging bucket
- **Cloud Run**: Deploy access for CI/CD

### Secrets Management

Secrets are managed via Google Secret Manager:

- `db-connection-name-staging`
- `db-password-staging`
- `gcs-bucket-name-staging`
- `mcp-bearer-token-staging`

### Authentication

- **Staging**: `AUTH_ENABLED=false` (development mode)
- **CORS**: Permissive for testing (`CORS_ORIGINS=*`)
- **Bearer Token**: Separate staging token for API access

## Monitoring and Logging

### Cloud Run Logs

View staging service logs:

```bash
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=music-library-mcp-staging" \
  --project=loist-music-library \
  --limit=50
```

### Application Logs

Staging uses structured JSON logging with:

- **Log Level**: `DEBUG` (verbose for troubleshooting)
- **Format**: JSON for log aggregation
- **Context**: Request IDs, operation tracking

### Health Checks

- **Endpoint**: `/health` (HTTP GET)
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Unhealthy Threshold**: 3 consecutive failures

## Testing Procedures

### Automated Testing

Run the staging validation suite:

```bash
./scripts/test-staging-deployment.sh
```

This performs:

1. **Build Verification**: Docker image builds successfully
2. **Deployment Test**: Cloud Run service starts and responds
3. **Database Connection**: Can connect to staging database
4. **GCS Access**: Can read/write to staging bucket
5. **API Validation**: Basic MCP functionality works

### Manual Testing Checklist

#### Environment Validation
- [ ] Docker containers start without errors
- [ ] Services can communicate with each other
- [ ] Environment variables are loaded correctly
- [ ] Server naming includes "staging" context

#### Database Testing
- [ ] Connection to staging database succeeds
- [ ] Schema matches production schema
- [ ] Test data is properly anonymized
- [ ] Migration scripts run without errors

#### Storage Testing
- [ ] File uploads to staging bucket work
- [ ] IAM permissions allow necessary operations
- [ ] Lifecycle policies delete temporary files
- [ ] Bucket naming conventions are followed

#### API Testing
- [ ] MCP server responds to health checks
- [ ] Basic tool operations function correctly
- [ ] Error handling works as expected
- [ ] Logging captures appropriate information

## Troubleshooting

### Common Issues

#### Container Won't Start
```
Error: The user-provided container failed to start
```
**Solutions:**
1. Check Cloud Run logs for import errors
2. Verify environment variables are set correctly
3. Ensure database connectivity
4. Check GCS bucket permissions

#### Database Connection Failed
```
Error: Connection refused
```
**Solutions:**
1. Verify Cloud SQL instance is running
2. Check service account has database access
3. Confirm connection name is correct
4. Test with Cloud SQL proxy locally

#### GCS Access Denied
```
Error: 403 Forbidden
```
**Solutions:**
1. Verify service account key is mounted
2. Check IAM permissions on staging bucket
3. Confirm bucket name is correct
4. Test with gsutil locally

#### Build Failures
```
Error: Build step failed
```
**Solutions:**
1. Check Cloud Build logs for specific errors
2. Verify Dockerfile syntax
3. Ensure all required files are included
4. Check for missing dependencies

### Debug Commands

#### Check Service Status
```bash
gcloud run services describe music-library-mcp-staging \
  --project=loist-music-library \
  --region=us-central1
```

#### View Recent Logs
```bash
gcloud logging read "resource.type=cloud_run_revision" \
  --project=loist-music-library \
  --filter="resource.labels.service_name=music-library-mcp-staging" \
  --limit=20
```

#### Test Database Connection
```bash
gcloud sql connect loist-music-library-db \
  --project=loist-music-library \
  --user=music_library_user \
  --database=loist_mvp_staging
```

#### Check Bucket Contents
```bash
gsutil ls -l gs://loist-music-library-bucket-staging/**
```

## Cost Management

### Staging Environment Costs

**Estimated Monthly Costs:**

- **Cloud Run**: $5-15 (based on traffic)
- **Cloud SQL**: $10-20 (staging instance)
- **Cloud Storage**: $1-5 (test data with lifecycle policies)
- **Cloud Build**: $5-10 (CI/CD operations)

**Cost Optimization:**

- **Auto-scaling**: Cloud Run scales to zero when idle
- **Lifecycle Policies**: Automatic cleanup of test data
- **Resource Limits**: Smaller instance sizes than production
- **Monitoring**: Track usage and adjust as needed

### Cleanup Procedures

#### Remove Test Data
```bash
# Clear database test records
gcloud sql connect loist-music-library-db \
  --project=loist-music-library \
  --user=music_library_user \
  --database=loist_mvp_staging \
  -c "DELETE FROM audio_metadata WHERE title LIKE 'Test%';"
```

#### Clean GCS Bucket
```bash
# Remove test files manually if needed
gsutil rm -r gs://loist-music-library-bucket-staging/test/**
```

## Development Workflow

### Branching Strategy

```
main (production) ← dev (staging) ← task-X (feature branches)
                              ↑
                       auto-deploy
```

### Staging Deployment Flow

1. **Feature Development**: Work on `task-X` branch
2. **Merge to Dev**: Push feature to `dev` branch
3. **Auto Deployment**: Cloud Build deploys to staging
4. **Testing**: QA team validates in staging
5. **Production**: Merge `dev` to `main` for production

### Environment Promotion

```bash
# From task branch to dev (triggers staging)
git checkout dev
git merge task-15
git push origin dev

# From dev to main (triggers production)
git checkout main
git merge dev
git push origin main
```

## Support and Resources

### Documentation Links

- [Cloud Run Deployment Guide](cloud-run-deployment.md)
- [Database Best Practices](database-best-practices.md)
- [Environment Variables Reference](environment-variables.md)
- [Troubleshooting Guide](troubleshooting-deployment.md)

### Contact Information

For staging environment issues:

- **Logs**: Check Cloud Logging console
- **Metrics**: Cloud Monitoring dashboard
- **Alerts**: Check notification channels
- **Support**: Development team Slack channel

---

**Remember**: The staging environment is for testing and validation only. All production deployments must go through the main branch and production Cloud Build pipeline.
