# A2A Cloud Build Trigger Setup Guide

**Purpose**: Set up automated Cloud Build triggers for A2A agent server deployment to staging and production environments.

**Important**: A2A triggers mirror MCP triggers and fire on **ANY push** to their branches (no path filters). This ensures triggers fire when merging `dev` → `main`, not just when A2A code changes.

## Prerequisites

Before running the setup script, ensure:

1. ✅ **Cloud Build configs are in GitHub**: Both `cloudbuild-a2a-staging.yaml` and `cloudbuild-a2a-prod.yaml` must be committed and pushed to the repository
2. ✅ **gcloud CLI authenticated**: Run `gcloud auth login` if needed
3. ✅ **Project configured**: Run `gcloud config set project loist-music-library`
4. ✅ **GitHub repository connected**: The repository must be connected to Cloud Build (check Cloud Console → Cloud Build → Triggers → Connect Repository)

## Quick Setup (Automated)

### Step 1: Run the Creation Script

```bash
./scripts/create-a2a-triggers.sh
```

This script will:
- Create `a2a-staging-deployment` trigger (fires on **ANY** push to `dev` branch)
- Create `a2a-prod-deployment` trigger (fires on **ANY** push to `main` branch)
- Verify the triggers were created successfully

**Note**: Triggers are configured **without path filters** to mirror MCP triggers. They fire on any code change, supporting branch merges (dev → main).

## Manual Setup (Alternative)

If you prefer to create triggers manually via Cloud Console:

### Via Cloud Console

1. **Navigate to Cloud Build Triggers**:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Navigate to **Cloud Build** → **Triggers**
   - Click **Create Trigger**

2. **Create A2A Staging Trigger**:
   - **Name**: `a2a-staging-deployment`
   - **Event**: Push to a branch
   - **Branch**: `^dev$`
   - **Configuration**: Cloud Build configuration file
   - **Location**: Repository
   - **Cloud Build configuration file**: `cloudbuild-a2a-staging.yaml`
   - **Service account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
   - **Path filters**: Leave empty (triggers on ANY push, mirroring MCP triggers)
   - Click **Create**

3. **Create A2A Production Trigger**:
   - **Name**: `a2a-prod-deployment`
   - **Event**: Push to a branch
   - **Branch**: `^main$`
   - **Configuration**: Cloud Build configuration file
   - **Location**: Repository
   - **Cloud Build configuration file**: `cloudbuild-a2a-prod.yaml`
   - **Service account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
   - **Path filters**: Leave empty (triggers on ANY push, mirroring MCP triggers)
   - Click **Create**

### Via gcloud CLI (Manual Commands)

**Create A2A Staging Trigger**:
```bash
gcloud builds triggers create github \
  --project="loist-music-library" \
  --name="a2a-staging-deployment" \
  --description="Deploy A2A agent server to staging on dev branch" \
  --repo-name="loist-mcp-server" \
  --repo-owner="DelicateAlchemy" \
  --branch-pattern="^dev$" \
  --build-config="cloudbuild-a2a-staging.yaml" \
  --service-account="loist-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --no-require-approval
```

**Create A2A Production Trigger**:
```bash
gcloud builds triggers create github \
  --project="loist-music-library" \
  --name="a2a-prod-deployment" \
  --description="Deploy A2A agent server to production on main branch" \
  --repo-name="loist-mcp-server" \
  --repo-owner="DelicateAlchemy" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild-a2a-prod.yaml" \
  --service-account="loist-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --no-require-approval
```

**Note**: No `--included-files` flag is used. Triggers fire on **ANY push** to their branches, mirroring MCP triggers.

## Verification

### Check Trigger Status

```bash
# List all A2A triggers
gcloud builds triggers list \
  --project=loist-music-library \
  --filter="name~a2a" \
  --format="table(name,description,github.push.branch,filename,includedFiles,disabled)"
```

Expected output should show:
- `a2a-staging-deployment` - Branch: `^dev$`, Config: `cloudbuild-a2a-staging.yaml`, No path filters
- `a2a-prod-deployment` - Branch: `^main$`, Config: `cloudbuild-a2a-prod.yaml`, No path filters

### View Trigger Details

**Staging trigger**:
```bash
gcloud builds triggers describe a2a-staging-deployment \
  --project=loist-music-library \
  --format="yaml(github.push.branch,github.push.includedFiles,filename)"
```

**Production trigger**:
```bash
gcloud builds triggers describe a2a-prod-deployment \
  --project=loist-music-library \
  --format="yaml(github.push.branch,github.push.includedFiles,filename)"
```

### Test Triggers

**Test Staging Trigger**:
```bash
# Make a small change to A2A code and push to dev branch
git checkout dev
echo "# Test" >> src/a2a_server/README.md
git add src/a2a_server/README.md
git commit -m "test: Trigger A2A staging deployment"
git push origin dev

# Monitor the build
gcloud builds list \
  --project=loist-music-library \
  --ongoing \
  --format="table(id,status,createTime,source.repoSource.branchName)"
```

**Test Production Trigger**:
```bash
# Make a small change to A2A code and push to main branch
git checkout main
echo "# Test" >> src/a2a_server/README.md
git add src/a2a_server/README.md
git commit -m "test: Trigger A2A production deployment"
git push origin main

# Monitor the build
gcloud builds list \
  --project=loist-music-library \
  --ongoing \
  --format="table(id,status,createTime,source.repoSource.branchName)"
```

## Trigger Behavior

### When Triggers Fire

**A2A Staging Trigger** (`a2a-staging-deployment`):
- ✅ Fires on **ANY** push to `dev` branch (no path filters)
- ✅ Mirrors MCP staging trigger behavior
- ✅ Supports branch merges and any code changes

**A2A Production Trigger** (`a2a-prod-deployment`):
- ✅ Fires on **ANY** push to `main` branch (no path filters)
- ✅ Mirrors MCP production trigger behavior
- ✅ Supports branch merges (dev → main) and any code changes

### What Happens When Triggered

1. **Cloud Build starts**: Executes `cloudbuild-a2a-staging.yaml` or `cloudbuild-a2a-prod.yaml`
2. **Tests run**: Unit tests execute (coverage thresholds: 65% staging, 75% production)
3. **Image built**: Docker image built with `--target a2a`
4. **Image pushed**: Pushed to Artifact Registry
5. **Cloud Run deployed**: New revision deployed to `a2a-staging` or `a2a-prod` service
6. **Traffic switched**: Cloud Run automatically routes traffic to new revision

## Troubleshooting

### Trigger Not Firing

**Check GitHub connection**:
```bash
gcloud builds triggers list \
  --project=loist-music-library \
  --format=json | jq '.[] | select(.name | contains("a2a")) | {name, github: .github}'
```

**Verify webhook in GitHub**:
1. Go to repository settings → Webhooks
2. Check for Cloud Build webhook
3. Verify recent deliveries show successful requests

**Check path filters**:
```bash
gcloud builds triggers describe a2a-prod-deployment \
  --project=loist-music-library \
  --format="yaml(github.push,includedFiles)"
```

Should show: No `includedFiles` field (triggers on any push)

### Build Failures

**View build logs**:
```bash
# List recent builds
gcloud builds list --project=loist-music-library --limit=5

# View specific build logs
gcloud builds log BUILD_ID --project=loist-music-library
```

**Common issues**:
- Missing secrets in Secret Manager
- Service account permissions insufficient
- Cloud Run service doesn't exist (needs initial deployment)
- Artifact Registry repository missing

### Remove Path Filters (If Present)

If triggers were created with path filters and need to be updated to mirror MCP triggers:

```bash
./scripts/update-a2a-trigger-paths.sh
```

This script removes any `includedFiles` from triggers so they fire on **ANY push**, mirroring MCP trigger behavior.

**Manual update using export/import**:

```bash
# Export trigger
gcloud beta builds triggers export a2a-prod-deployment \
  --project=loist-music-library \
  --destination=/tmp/trigger.yaml

# Edit trigger.yaml to remove includedFiles field (if present)

# Import updated trigger
gcloud beta builds triggers import \
  --project=loist-music-library \
  --source=/tmp/trigger.yaml
```

**Note**: A2A triggers should **NOT** have path filters - they should fire on any push to their branches, just like MCP triggers.

## Next Steps

After triggers are set up:

1. ✅ **Verify triggers exist**: Run verification commands above
2. ✅ **Test staging deployment**: Push A2A code change to `dev` branch
3. ✅ **Monitor first build**: Check Cloud Build logs for any issues
4. ✅ **Test production deployment**: After staging works, test production trigger
5. ✅ **Update test results**: Mark deployment gap as resolved in `docs/a2a-test-results.md`

## Related Documentation

- [Cloud Build Triggers Configuration](./cloud-build-triggers.md) - Complete trigger documentation
- [A2A Test Results](./a2a-test-results.md) - Current deployment status
- [Cloud Run Deployment](./cloud-run-deployment.md) - Deployment pipeline details

---

**Last Updated**: 2025-12-17
**Status**: Ready for setup - Scripts available, manual steps documented

