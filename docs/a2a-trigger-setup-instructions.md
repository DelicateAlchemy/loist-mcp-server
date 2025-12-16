# A2A Cloud Build Trigger Setup Instructions

**Status**: Triggers need to be created manually via Cloud Console  
**Reason**: CLI creation fails with INVALID_ARGUMENT (likely due to file validation)

## Prerequisites

1. ✅ Cloud Build configs committed and pushed to GitHub:
   - `cloudbuild-a2a-staging.yaml`
   - `cloudbuild-a2a-prod.yaml`

2. ✅ GitHub repository connected to Cloud Build (already done)

## Manual Setup via Cloud Console

### A2A Staging Trigger

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=loist-music-library)
2. Click **"Create Trigger"**
3. Configure:
   - **Name**: `a2a-staging-deployment`
   - **Description**: `Deploy A2A agent server to staging on dev branch`
   - **Event**: Push to a branch
   - **Source**: 
     - Repository: `DelicateAlchemy/loist-mcp-server`
     - Branch: `^dev$`
   - **Configuration**: 
     - Type: Cloud Build configuration file
     - Location: Repository
     - Cloud Build configuration file location: `cloudbuild-a2a-staging.yaml`
   - **Advanced** → **Included files filter**: 
     - `src/a2a_server/**`
     - `cloudbuild-a2a-staging.yaml`
   - **Service account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
   - **Require approval**: Unchecked
4. Click **"Create"**

### A2A Production Trigger

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=loist-music-library)
2. Click **"Create Trigger"**
3. Configure:
   - **Name**: `a2a-prod-deployment`
   - **Description**: `Deploy A2A agent server to production on main branch`
   - **Event**: Push to a branch
   - **Source**: 
     - Repository: `DelicateAlchemy/loist-mcp-server`
     - Branch: `^main$`
   - **Configuration**: 
     - Type: Cloud Build configuration file
     - Location: Repository
     - Cloud Build configuration file location: `cloudbuild-a2a-prod.yaml`
   - **Advanced** → **Included files filter**: 
     - `src/a2a_server/**`
     - `cloudbuild-a2a-prod.yaml`
   - **Service account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com`
   - **Require approval**: Unchecked
4. Click **"Create"**

## Verification

After creating triggers, verify they exist:

```bash
gcloud builds triggers list \
  --project=loist-music-library \
  --filter="name~a2a" \
  --format="table(name,description,github.push.branch,filename,includedFiles)"
```

## Alternative: Update Existing Triggers

If triggers are created without path filters, update them using:

```bash
./scripts/update-a2a-trigger-paths.sh
```

## Troubleshooting

**Issue**: CLI creation fails with `INVALID_ARGUMENT`  
**Solution**: Use Cloud Console UI instead (see above)

**Issue**: Trigger doesn't fire  
**Solution**: 
1. Verify path filters include both `src/a2a_server/**` and `cloudbuild-a2a-*.yaml`
2. Check that files exist in the repository
3. Verify branch pattern matches (`^dev$` for staging, `^main$` for production)

---

**Last Updated**: 2025-12-15  
**Status**: Manual setup required via Cloud Console

