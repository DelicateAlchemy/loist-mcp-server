# Migration Guide: GitHub Actions to Google Cloud Build

This guide explains the migration from GitHub Actions to Google Cloud Build for the Loist Music Library MCP Server deployment.

## Why Migrate?

### GitHub Actions Issues
- ❌ Complex IAM permission setup required
- ❌ Manual secret management across platforms
- ❌ Service account key management overhead
- ❌ Permission errors: "artifactregistry.repositories.uploadArtifacts" denied
- ❌ External runner dependency

### Google Cloud Build Benefits
- ✅ **Native GCP integration** - No permission complexity
- ✅ **Zero-config Docker builds** - Built-in Container Registry access
- ✅ **Faster builds** - Google's infrastructure vs GitHub runners
- ✅ **Better security** - No service account keys needed
- ✅ **Cost-effective** - 2500 free build minutes vs GitHub Actions limits
- ✅ **Simpler maintenance** - Single platform management

## Migration Comparison

### Before: GitHub Actions Workflow

```yaml
# .github/workflows/cloud-run-deployment.yml
name: Cloud Run Deployment
on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: google-github-actions/auth@v2
      with:
        credentials_json: ${{ secrets.GCLOUD_SERVICE_KEY }}  # ❌ Manual key management
    - name: Configure Docker for GCR
      run: gcloud auth configure-docker --quiet              # ❌ Manual auth setup
    - name: Build Docker image
      run: docker build -t ${{ env.IMAGE_NAME }}:${{ github.sha }} .
    - name: Push Docker image to GCR
      run: docker push ${{ env.IMAGE_NAME }}:${{ github.sha }} # ❌ Permission errors here
```

**Required Secrets:**
- `GCLOUD_SERVICE_KEY` (service account JSON)
- `CLOUD_RUN_SERVICE_ACCOUNT`
- `DB_CONNECTION_NAME`
- `GCS_BUCKET_NAME`

### After: Google Cloud Build

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/music-library-mcp:$COMMIT_SHA', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/music-library-mcp:$COMMIT_SHA']     # ✅ Built-in permissions
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'music-library-mcp', ...]                      # ✅ Native integration
```

**Required Setup:**
- Cloud Build GitHub App installation (one-time)
- Secret Manager configuration (more secure)
- Build triggers (automatic)

## Step-by-Step Migration

### Step 1: Disable GitHub Actions Workflow

```bash
# Move the existing workflow to prevent conflicts
git mv .github/workflows/cloud-run-deployment.yml .github/workflows/cloud-run-deployment.yml.disabled
```

### Step 2: Add Cloud Build Configuration

The following files have been created:
- `cloudbuild.yaml` - Production deployment configuration
- `cloudbuild-staging.yaml` - Staging deployment configuration
- `docs/google-cloud-build-setup.md` - Complete setup guide

### Step 3: Install Google Cloud Build GitHub App

1. Visit [Google Cloud Build GitHub Marketplace](https://github.com/marketplace/google-cloud-build)
2. Install for the `loist-mcp-server` repository
3. Connect repository in Google Cloud Console

### Step 4: Create Build Triggers

**Production Trigger:**
- **Name**: `production-deployment`
- **Event**: Push to branch `^main$`
- **Configuration**: `/cloudbuild.yaml`

**Staging Trigger:**
- **Name**: `staging-deployment`  
- **Event**: Push to branch `^dev$`
- **Configuration**: `/cloudbuild-staging.yaml`

### Step 5: Migrate Secrets

**From GitHub Secrets → To Secret Manager:**

```bash
# Create secrets in Secret Manager
gcloud secrets create db-connection-name \
  --data-file=- <<< "loist-music-library:us-central1:loist-music-library-db"

gcloud secrets create gcs-bucket-name \
  --data-file=- <<< "loist-mvp-audio-files"
```

**Remove GitHub Secrets:**
- `GCLOUD_SERVICE_KEY` ❌ (no longer needed)
- `CLOUD_RUN_SERVICE_ACCOUNT` ❌ (configured in trigger)
- `DB_CONNECTION_NAME` ❌ (moved to Secret Manager)
- `GCS_BUCKET_NAME` ❌ (moved to Secret Manager)

### Step 6: Configure IAM Permissions

```bash
PROJECT_ID="loist-music-library"
CLOUD_BUILD_SA="${PROJECT_ID}@cloudbuild.gserviceaccount.com"

# Grant Cloud Build permissions (one-time setup)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"
```

## Feature Comparison

| Feature | GitHub Actions | Google Cloud Build |
|---------|---------------|-------------------|
| **Build Speed** | ~3-5 minutes | ~2-3 minutes |
| **Setup Complexity** | High (IAM, secrets) | Low (native integration) |
| **Permission Management** | Manual service account keys | Automatic |
| **Cost (Free Tier)** | 2000 minutes/month | 2500 minutes/month |
| **Security** | External secrets | Google-managed |
| **Maintenance** | High (key rotation) | Low (automatic) |
| **Integration** | External auth required | Native GCP |
| **Debugging** | GitHub logs | Cloud Console |

## Deployment Workflow Changes

### Before (GitHub Actions)
1. Push to `main` → GitHub Actions triggered
2. Runner authenticates with service account key
3. Build Docker image on GitHub runner
4. Push to GCR (often fails with permissions)
5. Deploy to Cloud Run (if push succeeds)

### After (Google Cloud Build)
1. Push to `main` → Cloud Build triggered automatically
2. Build Docker image on Google infrastructure
3. Push to GCR (built-in permissions)
4. Deploy to Cloud Run (native integration)
5. Health checks and traffic management
6. Deployment summary and verification

## Testing the Migration

### 1. Test Staging Deployment
```bash
# Push to dev branch to trigger staging build
git checkout dev
git push origin dev

# Monitor build progress
gcloud builds list --limit=1
```

### 2. Test Production Deployment
```bash
# Push to main branch to trigger production build
git checkout main
git merge dev
git push origin main

# Monitor build progress
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")
```

### 3. Verify Deployment
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe music-library-mcp \
  --region=us-central1 --format="value(status.url)")

# Test health endpoint
curl $SERVICE_URL/mcp/health
```

## Rollback Plan

If issues occur, you can quickly rollback:

### 1. Re-enable GitHub Actions
```bash
git mv .github/workflows/cloud-run-deployment.yml.disabled \
       .github/workflows/cloud-run-deployment.yml
```

### 2. Disable Cloud Build Triggers
```bash
# Disable triggers temporarily
gcloud builds triggers update production-deployment --disabled
gcloud builds triggers update staging-deployment --disabled
```

### 3. Manual Deployment
```bash
# Deploy previous working version manually
gcloud run deploy music-library-mcp \
  --image=gcr.io/loist-music-library/music-library-mcp:latest \
  --region=us-central1
```

## Benefits Realized

After migration, you'll have:

1. **Simplified Deployment** - No more IAM permission debugging
2. **Faster Builds** - Google's infrastructure vs GitHub runners  
3. **Better Security** - No service account keys to manage
4. **Cost Savings** - More free build minutes
5. **Native Integration** - Seamless GCP service interaction
6. **Easier Maintenance** - Single platform management
7. **Better Monitoring** - Integrated Cloud Console logging

## Cleanup

After successful migration:

### Remove GitHub Actions Files
```bash
rm .github/workflows/cloud-run-deployment.yml.disabled
rm docs/cloud-run-deployment.md  # GitHub Actions specific docs
```

### Remove GitHub Secrets
1. Go to repository Settings → Secrets and variables → Actions
2. Delete unused secrets:
   - `GCLOUD_SERVICE_KEY`
   - `CLOUD_RUN_SERVICE_ACCOUNT` (if not used elsewhere)

### Update Documentation
- Update README.md deployment instructions
- Reference new Cloud Build setup guide
- Update any deployment runbooks

## Support

If you encounter issues during migration:

1. **Check Cloud Build logs**: `gcloud builds log <BUILD_ID>`
2. **Verify permissions**: Ensure service accounts have required roles
3. **Test manually**: Use `gcloud builds submit` for debugging
4. **Consult documentation**: [Cloud Build Setup Guide](./google-cloud-build-setup.md)

The migration provides significant benefits in terms of simplicity, security, and performance while reducing maintenance overhead.
