# Cloud Run Automated Deployment

This document describes the automated deployment workflow for the Loist Music Library MCP Server to Google Cloud Run.

## Overview

The deployment workflow is triggered automatically when code is pushed to the `main` branch. It builds a Docker image, pushes it to Google Container Registry, and deploys it to Cloud Run.

## Workflow Features

- ✅ **Automated Deployment**: Triggers on `main` branch pushes
- ✅ **Manual Deployment**: Can be triggered manually via GitHub Actions UI
- ✅ **Docker Build & Push**: Builds optimized Docker image and pushes to GCR
- ✅ **Health Verification**: Verifies deployment health before completing
- ✅ **Traffic Management**: Updates traffic to new revision
- ✅ **Comprehensive Logging**: Detailed deployment status and configuration
- ✅ **Failure Handling**: Proper error handling and notifications

## Required GitHub Secrets

The following secrets must be configured in your GitHub repository:

### Authentication & Service Account
- **`GCLOUD_SERVICE_KEY`**: JSON service account key for Google Cloud authentication
- **`CLOUD_RUN_SERVICE_ACCOUNT`**: Email of the service account for Cloud Run (e.g., `music-library-sa@loist-music-library.iam.gserviceaccount.com`)

### Database Configuration
- **`DB_CONNECTION_NAME`**: Cloud SQL connection name (e.g., `loist-music-library:us-central1:loist-music-library-db`)

### Storage Configuration
- **`GCS_BUCKET_NAME`**: Google Cloud Storage bucket name (e.g., `loist-mvp-audio-files`)

## Service Configuration

### Environment Variables
The deployment sets the following environment variables:

```yaml
SERVER_TRANSPORT: http
LOG_LEVEL: INFO
AUTH_ENABLED: false          # Disabled for MVP
ENABLE_CORS: true
CORS_ORIGINS: "*"            # Permissive for MVP
ENABLE_HEALTHCHECK: true
DB_CONNECTION_NAME: <from secrets>
GCS_BUCKET_NAME: <from secrets>
GCS_PROJECT_ID: loist-music-library
```

### Resource Limits
- **Memory**: 2GB
- **CPU**: 1 vCPU
- **Timeout**: 600 seconds (10 minutes)
- **Concurrency**: 80 requests per instance
- **Max Instances**: 10
- **Min Instances**: 0 (scales to zero)

## Deployment Process

1. **Trigger**: Push to `main` branch or manual workflow dispatch
2. **Build**: Docker image built with latest code
3. **Push**: Image pushed to `gcr.io/loist-music-library/music-library-mcp`
4. **Deploy**: New Cloud Run revision created
5. **Verify**: Health check endpoint tested
6. **Traffic**: Traffic routed to new revision
7. **Notify**: Deployment status reported

## Manual Deployment

You can trigger a manual deployment via GitHub Actions:

1. Go to **Actions** tab in GitHub
2. Select **Cloud Run Deployment** workflow
3. Click **Run workflow**
4. Choose environment (production/staging)
5. Click **Run workflow**

## Monitoring Deployment

### GitHub Actions
- View deployment progress in the **Actions** tab
- Check logs for detailed deployment information
- Monitor health check results

### Google Cloud Console
- **Cloud Run**: Monitor service status and revisions
- **Container Registry**: View pushed Docker images
- **Logging**: Check application logs

## Service URLs

After deployment, the service will be available at:
- **Production**: `https://music-library-mcp-<hash>-uc.a.run.app`
- **Health Check**: `https://<service-url>/mcp/health`

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify `GCLOUD_SERVICE_KEY` secret is valid
   - Check service account has required permissions

2. **Image Push Failures**
   - Ensure Docker authentication is configured
   - Verify Container Registry API is enabled

3. **Deployment Failures**
   - Check Cloud Run API is enabled
   - Verify service account permissions
   - Review environment variable configuration

4. **Health Check Failures**
   - Check application startup logs
   - Verify database connectivity
   - Ensure GCS bucket access

### Required IAM Permissions

The service account needs the following roles:
- **Cloud Run Admin**: Deploy and manage Cloud Run services
- **Storage Admin**: Access GCS buckets
- **Cloud SQL Client**: Connect to Cloud SQL database
- **Container Registry Service Agent**: Push/pull images

## Rollback Process

If a deployment fails or causes issues:

1. **Automatic**: Failed deployments don't receive traffic
2. **Manual Rollback**:
   ```bash
   gcloud run services update-traffic music-library-mcp \
     --to-revisions=<previous-revision>=100 \
     --region us-central1
   ```

## Security Considerations

- Service account follows principle of least privilege
- Authentication disabled for MVP (will be enabled later)
- CORS configured permissively for development
- All secrets managed via GitHub Secrets
- Container runs as non-root user

## Next Steps

1. **Enable Authentication**: Configure bearer token authentication
2. **Custom Domain**: Set up custom domain mapping
3. **Monitoring**: Add comprehensive monitoring and alerting
4. **Staging Environment**: Create separate staging deployment
5. **Blue/Green Deployments**: Implement zero-downtime deployments
