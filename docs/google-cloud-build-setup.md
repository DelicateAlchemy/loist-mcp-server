# Google Cloud Build Setup Guide

This guide walks you through setting up Google Cloud Build for automated deployment of the Loist Music Library MCP Server to Cloud Run.

## Overview

Google Cloud Build provides a superior deployment experience compared to GitHub Actions for Google Cloud services:

- ✅ **Zero-config Docker builds** - Native GCP integration
- ✅ **No IAM permission complexity** - Built-in service account permissions
- ✅ **Faster builds** - Google's global network infrastructure
- ✅ **Generous free tier** - 120 free build-minutes per day
- ✅ **Better security** - Google's infrastructure protection
- ✅ **Simpler maintenance** - No external secret management

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **GitHub repository** with the MCP server code
3. **Required APIs enabled**:
   - Cloud Build API
   - Cloud Run API
   - Container Registry API (or Artifact Registry API)
   - Secret Manager API

## Step 1: Install Google Cloud Build GitHub App

1. Go to the [Google Cloud Build GitHub Marketplace](https://github.com/marketplace/google-cloud-build)
2. Click **"Set up a plan"** → **"Install it for free"**
3. Choose your GitHub account/organization
4. Select **"Only select repositories"** → Choose `loist-mcp-server`
5. Click **"Install & Authorize"**
6. You'll be redirected to Google Cloud Console

## Step 2: Connect Repository in Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Cloud Build** → **Triggers**
3. Click **"Connect Repository"**
4. Select **"GitHub (Cloud Build GitHub App)"**
5. Choose your repository: `DelicateAlchemy/loist-mcp-server`
6. Click **"Connect"**

## Step 3: Create Build Triggers

### Production Trigger (Main Branch)

1. In Cloud Build → Triggers, click **"Create Trigger"**
2. Configure the trigger:

```yaml
Name: production-deployment
Description: Deploy to production Cloud Run on main branch
Event: Push to a branch
Source:
  Repository: DelicateAlchemy/loist-mcp-server
  Branch: ^main$
Configuration:
  Type: Cloud Build configuration file (yaml or json)
  Cloud Build configuration file location: /cloudbuild.yaml
Substitution variables:
  _CLOUD_RUN_SERVICE_ACCOUNT: music-library-sa@loist-music-library.iam.gserviceaccount.com
  _DB_CONNECTION_NAME: db-connection-name
  _GCS_BUCKET_NAME: gcs-bucket-name
```

### Staging Trigger (Dev Branch)

1. Click **"Create Trigger"** again
2. Configure the staging trigger:

```yaml
Name: staging-deployment
Description: Deploy to staging Cloud Run on dev branch
Event: Push to a branch
Source:
  Repository: DelicateAlchemy/loist-mcp-server
  Branch: ^dev$
Configuration:
  Type: Cloud Build configuration file (yaml or json)
  Cloud Build configuration file location: /cloudbuild-staging.yaml
Substitution variables:
  _CLOUD_RUN_SERVICE_ACCOUNT: music-library-sa@loist-music-library.iam.gserviceaccount.com
  _DB_CONNECTION_NAME_STAGING: db-connection-name-staging
  _GCS_BUCKET_NAME_STAGING: gcs-bucket-name-staging
```

## Step 4: Configure Secrets in Secret Manager

### Create Required Secrets

```bash
# Database connection name
gcloud secrets create db-connection-name --data-file=- <<< "loist-music-library:us-central1:loist-music-library-db"

# GCS bucket name
gcloud secrets create gcs-bucket-name --data-file=- <<< "loist-mvp-audio-files"

# Staging secrets (if using staging environment)
gcloud secrets create db-connection-name-staging --data-file=- <<< "loist-music-library:us-central1:loist-music-library-db-staging"
gcloud secrets create gcs-bucket-name-staging --data-file=- <<< "loist-mvp-audio-files-staging"
```

### Grant Secret Access to Cloud Build

```bash
# Get Cloud Build service account
PROJECT_ID="loist-music-library"
CLOUD_BUILD_SA="${PROJECT_ID}@cloudbuild.gserviceaccount.com"

# Grant access to secrets
gcloud secrets add-iam-policy-binding db-connection-name \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gcs-bucket-name \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 5: Configure Service Account Permissions

The Cloud Build service account needs the following roles:

```bash
PROJECT_ID="loist-music-library"
CLOUD_BUILD_SA="${PROJECT_ID}@cloudbuild.gserviceaccount.com"

# Cloud Run Admin (to deploy services)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin"

# Service Account User (to deploy with service account)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"

# Storage Admin (for Container Registry)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/storage.admin"
```

## Step 6: Create Cloud Run Service Account

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create music-library-sa \
  --display-name="Music Library MCP Service Account" \
  --description="Service account for Music Library MCP Cloud Run service"

# Grant necessary permissions
SERVICE_ACCOUNT="music-library-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Cloud SQL Client
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudsql.client"

# Storage Object Admin (for GCS)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"

# Secret Manager Secret Accessor
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## Build Configuration Files

### Production Build (`cloudbuild.yaml`)

- **Triggers on**: Push to `main` branch
- **Deploys to**: `music-library-mcp` Cloud Run service
- **Resources**: 2GB RAM, 1 CPU, up to 10 instances
- **Features**: Health checks, traffic management, comprehensive logging

### Staging Build (`cloudbuild-staging.yaml`)

- **Triggers on**: Push to `dev` branch  
- **Deploys to**: `music-library-mcp-staging` Cloud Run service
- **Resources**: 1GB RAM, 1 CPU, up to 3 instances
- **Features**: Basic health checks, debug logging

## Deployment Process

### Automatic Deployment

1. **Push to `main`** → Triggers production deployment
2. **Push to `dev`** → Triggers staging deployment
3. **Build steps**:
   - Build Docker image with commit SHA
   - Push to Google Container Registry
   - Deploy to Cloud Run with environment variables
   - Perform health checks
   - Update traffic to new revision
   - Generate deployment summary

### Manual Deployment

```bash
# Trigger production build manually
gcloud builds triggers run production-deployment --branch=main

# Trigger staging build manually
gcloud builds triggers run staging-deployment --branch=dev

# Build from local directory
gcloud builds submit --config=cloudbuild.yaml .
```

## Monitoring and Logs

### Cloud Build Logs
- **Console**: Cloud Build → History
- **CLI**: `gcloud builds log <BUILD_ID>`

### Cloud Run Logs
- **Console**: Cloud Run → Service → Logs
- **CLI**: `gcloud logging read "resource.type=cloud_run_revision"`

### Build Status
- **Console**: Cloud Build → Dashboard
- **CLI**: `gcloud builds list --limit=10`

## Environment Variables

The build automatically configures these environment variables:

### Production
```yaml
SERVER_TRANSPORT: http
LOG_LEVEL: INFO
AUTH_ENABLED: false
ENABLE_CORS: true
CORS_ORIGINS: "*"
ENABLE_HEALTHCHECK: true
GCS_PROJECT_ID: <project-id>
```

### Staging
```yaml
SERVER_TRANSPORT: http
LOG_LEVEL: DEBUG  # More verbose for testing
AUTH_ENABLED: false
ENABLE_CORS: true
CORS_ORIGINS: "*"
ENABLE_HEALTHCHECK: true
GCS_PROJECT_ID: <project-id>
```

## Troubleshooting

### Common Issues

1. **Build fails with permission errors**
   - Check Cloud Build service account has required roles
   - Verify Secret Manager permissions

2. **Cloud Run deployment fails**
   - Check service account exists and has permissions
   - Verify secret names match configuration

3. **Health check fails**
   - Check application logs in Cloud Run
   - Verify database connectivity
   - Ensure GCS bucket access

### Debug Commands

```bash
# Check build status
gcloud builds list --filter="status=FAILURE" --limit=5

# View build logs
gcloud builds log <BUILD_ID>

# Check Cloud Run service
gcloud run services describe music-library-mcp --region=us-central1

# Test health endpoint
curl https://<service-url>/mcp/health
```

## Cost Optimization

### Free Tier Limits
- **2500 free build minutes** per month with e2-standard-2 machines
- **120 free build-minutes per day** 
- **10 concurrent builds** included

### Cost Reduction Tips
1. **Use smaller machine types** for staging builds
2. **Enable build caching** with `--cache-from` flag
3. **Optimize Docker layers** for faster builds
4. **Use multi-stage builds** to reduce image size

## Security Best Practices

1. **Least privilege**: Service accounts have minimal required permissions
2. **Secret management**: Sensitive data stored in Secret Manager
3. **Network security**: Cloud Run services use Google's secure infrastructure
4. **Image scanning**: Container images automatically scanned for vulnerabilities
5. **Audit logging**: All build and deployment activities logged

## Next Steps

1. **Enable authentication** when ready for production
2. **Set up custom domain** for the Cloud Run service
3. **Configure monitoring alerts** for service health
4. **Implement blue/green deployments** for zero-downtime updates
5. **Add integration tests** to the build pipeline

## Support Resources

- [Cloud Build Documentation](https://cloud.google.com/cloud-build/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GitHub App Integration](https://cloud.google.com/cloud-build/docs/automating-builds/github/connect-repo-github)
- [Pricing Calculator](https://cloud.google.com/products/calculator)
