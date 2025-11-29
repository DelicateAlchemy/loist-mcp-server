# Cloud Build Triggers Configuration

This document describes the automated Cloud Build triggers for the Loist Music Library MCP Server deployment pipeline.

## Overview

The project uses GitHub-connected Cloud Build triggers for automated CI/CD deployments:

- **Production**: Automatically deploys to Cloud Run when code is pushed to `main` branch
- **Staging**: Automatically deploys to staging when code is pushed to `dev` branch

## Configured Triggers

### Production Trigger

**Trigger Name**: `production-deployment-init-location`

**Configuration**:
- **Branch Pattern**: `^main$` (main branch only)
- **Build Config**: `cloudbuild.yaml` (auto-detected)
- **Service Account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
- **Approval**: Not required (automated deployment)
- **GitHub Repo**: `DelicateAlchemy/loist-mcp-server`

**Deployment Target**:
- Service: `music-library-mcp`
- Region: `us-central1`
- Environment: Production

### Staging Trigger

**Trigger Name**: `staging-deployment-dev-branch`

**Configuration**:
- **Branch Pattern**: `^dev$` (dev branch only)
- **Build Config**: `cloudbuild-staging.yaml`
- **Service Account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
- **Approval**: Not required (automated deployment)
- **GitHub Repo**: `DelicateAlchemy/loist-mcp-server`

**Deployment Target**:
- Service: `music-library-mcp-staging`
- Region: `us-central1`
- Environment: Staging

## Trigger Workflow

### Production Deployment

```
Push to main → GitHub webhook → Cloud Build trigger → Build image → Deploy to Cloud Run (production)
```

1. Developer pushes code to `main` branch
2. GitHub sends webhook to Cloud Build
3. Cloud Build executes `cloudbuild.yaml`:
   - Builds Docker image
   - Pushes to Artifact Registry
   - Deploys to `music-library-mcp` service
4. Cloud Run automatically switches traffic to new revision

### Staging Deployment

```
Push to dev → GitHub webhook → Cloud Build trigger → Build image → Deploy to Cloud Run (staging)
```

1. Developer pushes code to `dev` branch
2. GitHub sends webhook to Cloud Build
3. Cloud Build executes `cloudbuild-staging.yaml`:
   - Builds Docker image (tagged with `-staging`)
   - Pushes to Artifact Registry
   - Deploys to `music-library-mcp-staging` service
4. Cloud Run automatically switches traffic to new revision

## Verifying Trigger Configuration

### List All Triggers

```bash
gcloud builds triggers list \
  --project=loist-music-library \
  --format="table(name,description,github.push.branch,filename,disabled)"
```

### View Production Trigger Details

```bash
gcloud builds triggers describe production-deployment-init-location \
  --project=loist-music-library
```

### View Staging Trigger Details

```bash
gcloud builds triggers describe staging-deployment-dev-branch \
  --project=loist-music-library
```

### View Recent Builds

```bash
gcloud builds list \
  --project=loist-music-library \
  --limit=10 \
  --format="table(id,status,createTime,source.repoSource.branchName,images)"
```

## Testing Triggers

### Test Production Trigger

Push a commit to `main` branch:

```bash
git checkout main
git add .
git commit -m "test: Trigger production deployment"
git push origin main
```

Monitor the build:

```bash
gcloud builds list --project=loist-music-library --ongoing --format="table(id,status,createTime)"
```

### Test Staging Trigger

Push a commit to `dev` branch:

```bash
git checkout dev
git add .
git commit -m "test: Trigger staging deployment"
git push origin dev
```

Monitor the build:

```bash
gcloud builds list --project=loist-music-library --ongoing --format="table(id,status,createTime)"
```

## Manual Approval Workflow (Optional)

If you need to re-enable manual approval for production deployments:

### Enable Approval Requirement

1. Export current trigger configuration:
```bash
gcloud builds triggers describe production-deployment-init-location \
  --project=loist-music-library \
  --format=json > trigger-config.json
```

2. Edit the JSON file and set `approvalRequired` to `true`:
```json
{
  "approvalConfig": {
    "approvalRequired": true
  },
  ...
}
```

3. Update the trigger:
```bash
gcloud builds triggers update github production-deployment-init-location \
  --project=loist-music-library \
  --trigger-config=trigger-config.json
```

### Approve Pending Builds

View pending builds:
```bash
gcloud builds list \
  --project=loist-music-library \
  --filter="status=PENDING" \
  --format="table(id,status,createTime,source.repoSource.branchName)"
```

Approve a specific build:
```bash
gcloud builds approve BUILD_ID --project=loist-music-library
```

## Troubleshooting

### Trigger Not Firing

**Check GitHub App connection:**
```bash
gcloud builds triggers list --project=loist-music-library --format=json | grep -A 10 "github"
```

**Verify webhook delivery in GitHub:**
1. Go to GitHub repository settings
2. Navigate to Webhooks
3. Check recent deliveries for Cloud Build webhook
4. Look for failed deliveries and error messages

**Check IAM permissions:**
```bash
gcloud projects get-iam-policy loist-music-library \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:loist-music-library-sa@"
```

### Build Failures

**View build logs:**
```bash
# Get the build ID from the list
gcloud builds list --project=loist-music-library --limit=5

# View logs for specific build
gcloud builds log BUILD_ID --project=loist-music-library
```

**Common issues:**
- **Missing secrets**: Verify Secret Manager secrets exist and are accessible
- **Invalid cloudbuild.yaml**: Check syntax and step definitions
- **Service account permissions**: Ensure service account has required roles
- **Image push failures**: Verify Artifact Registry repository exists

### Trigger Updates Not Taking Effect

**Clear trigger cache:**
```bash
# Re-describe the trigger to force cache refresh
gcloud builds triggers describe production-deployment-init-location \
  --project=loist-music-library
```

**Verify trigger was updated:**
```bash
gcloud builds triggers describe TRIGGER_NAME \
  --project=loist-music-library \
  --format="yaml(approvalConfig,github,filename)"
```

## Security Considerations

### Service Account Permissions

The triggers use `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com` which has:
- `roles/cloudbuild.builds.builder` - Execute Cloud Build operations
- `roles/run.admin` - Deploy to Cloud Run
- `roles/artifactregistry.writer` - Push images to Artifact Registry
- `roles/secretmanager.secretAccessor` - Access Secret Manager secrets
- `roles/cloudsql.client` - Connect to Cloud SQL

### Branch Protection

**Recommended GitHub settings:**
- Enable branch protection for `main` branch
- Require pull request reviews before merging
- Require status checks to pass (GitHub Actions MCP validation)
- Require branches to be up to date before merging

### Secret Management

All sensitive data is stored in Google Secret Manager:
- `DB_CONNECTION_NAME` - Database connection string
- `GCS_BUCKET_NAME` - Storage bucket name
- `BEARER_TOKEN` - API authentication token

Secrets are injected at deployment time via `cloudbuild.yaml` configuration.

## Additional Resources

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [GitHub Triggers](https://cloud.google.com/build/docs/automating-builds/github/build-repos-from-github)
- [Cloud Run Deployment](./cloud-run-deployment.md)
- [Environment Variables](./environment-variables.md)

---

**Last Updated**: 2025-11-02  
**Status**: Automated triggers configured and operational

