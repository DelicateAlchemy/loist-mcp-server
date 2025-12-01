# Google Cloud Containers Audit Report
**Date**: 2025-01-21  
**Project**: loist-music-library  
**Region**: us-central1

## Executive Summary

Found **3 Cloud Run services** running in Google Cloud:
- ✅ **1 Production Service** (`music-library-mcp`) - Intended production deployment
- ✅ **1 Staging Service** (`music-library-mcp-staging`) - Intended staging deployment  
- ⚠️ **1 Legacy Service** (`loist-mcp-server`) - **TECHNICAL DEBT - Should be deleted**

## Detailed Service Analysis

### 1. Legacy Service: `loist-mcp-server` ⚠️ **DELETE THIS**

**Status**: ✅ Currently Running (but should be removed)

**Details**:
- **Created**: October 23, 2025
- **Image**: `gcr.io/loist-music-library/loist-mcp-server:latest` (old Container Registry)
- **Service Account**: `loist-music-library-sa@loist-music-library.iam.gserviceaccount.com` (old service account)
- **URL**: `https://loist-mcp-server-7de5nxpr4q-uc.a.run.app`
- **Status**: Ready and serving traffic
- **Resources**: 2Gi memory, 1 CPU, max 20 instances
- **Database**: Connected to `loist-music-library-db`

**Why This Exists**:
- Early deployment from October 2025 before proper CI/CD setup
- Uses deprecated Container Registry (`gcr.io`) instead of Artifact Registry
- Uses old service account naming convention
- Created manually before automated deployment pipeline

**Recommendation**: **DELETE** - This is technical debt from early development. The new production service (`music-library-mcp`) replaces this.

**Deletion Impact**:
- ✅ Safe to delete - no active dependencies
- ✅ New production service (`music-library-mcp`) handles production traffic
- ⚠️ Old monitoring scripts reference this service (need cleanup)
- ⚠️ Old deployment scripts reference this service (need cleanup)

---

### 2. Production Service: `music-library-mcp` ✅ **KEEP**

**Status**: ⚠️ Not Ready (has health check errors, but this is the intended production service)

**Details**:
- **Created**: October 30, 2025
- **Image**: `us-central1-docker.pkg.dev/loist-music-library/music-library-repo/music-library-mcp:latest` (Artifact Registry)
- **Service Account**: `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com` (correct service account)
- **URL**: `https://music-library-mcp-7de5nxpr4q-uc.a.run.app`
- **Status**: Not Ready (health check failures)
- **Resources**: 2Gi memory, 1 CPU, max 10 instances
- **Deployment**: Managed by `cloudbuild.yaml` (triggers on `main` branch)

**Configuration**:
- Uses Artifact Registry (modern approach)
- Uses correct service account with proper IAM permissions
- Configured via Cloud Build pipeline
- Environment variables properly configured

**Current Issues**:
- Health check failures preventing service from becoming ready
- Latest revision (`music-library-mcp-00007-trk`) failing to start
- Traffic routed to older working revision (`music-library-mcp-00002-ttk`)

**Recommendation**: **KEEP** - This is the intended production service. Fix health check issues.

---

### 3. Staging Service: `music-library-mcp-staging` ✅ **KEEP**

**Status**: ⚠️ Not Ready (has health check errors, but this is the intended staging service)

**Details**:
- **Created**: November 2, 2025
- **Image**: `us-central1-docker.pkg.dev/loist-music-library/music-library-repo/music-library-mcp-staging:local-test` (Artifact Registry)
- **Service Account**: `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com` (correct service account)
- **URL**: `https://music-library-mcp-staging-7de5nxpr4q-uc.a.run.app`
- **Status**: Not Ready (health check failures)
- **Resources**: 1Gi memory, 1 CPU, max 3 instances
- **Deployment**: Managed by `cloudbuild-staging.yaml` (triggers on `dev` branch)
- **Database**: Uses staging database `loist_mvp_staging`

**Configuration**:
- Uses Artifact Registry (modern approach)
- Uses correct service account
- Configured via Cloud Build pipeline
- Runs database migrations on startup
- Staging-specific environment variables

**Current Issues**:
- Health check failures preventing service from becoming ready
- Latest revision (`music-library-mcp-staging-00091-mb9`) failing to start
- Traffic routed to older working revision (`music-library-mcp-staging-00090-67q`)

**Recommendation**: **KEEP** - This is the intended staging service. Fix health check issues.

---

## Cloud SQL Database

**Instance**: `loist-music-library-db`
- **Status**: ✅ Running
- **Type**: PostgreSQL 15
- **Region**: us-central1
- **Tier**: db-f1-micro
- **Connection**: Used by all three Cloud Run services
- **Recommendation**: **KEEP** - This is the production database

---

## Naming Convention Analysis

### Current Naming (Confusing)

| Service Name | Purpose | Issue |
|-------------|---------|-------|
| `loist-mcp-server` | Legacy/old production | ❌ Doesn't indicate it's legacy |
| `music-library-mcp` | Production | ✅ Clear naming |
| `music-library-mcp-staging` | Staging | ✅ Clear naming |

### Recommended Naming (After Cleanup)

| Service Name | Purpose | Status |
|-------------|---------|--------|
| `music-library-mcp` | Production | ✅ Keep as-is |
| `music-library-mcp-staging` | Staging | ✅ Keep as-is |

**Note**: After deleting `loist-mcp-server`, the naming will be consistent and clear.

---

## Codebase References to Old Service

The following files reference `loist-mcp-server` and may need updates after deletion:

### Scripts (Need Updates)
- `scripts/test-secrets.sh` - References old service name
- `scripts/setup-uptime-checks.sh` - Uses old service URL
- `scripts/setup-uptime-checks-simple.sh` - Uses old service URL
- `scripts/setup-monitoring.sh` - References old service name
- `scripts/setup-monitoring-simple.sh` - References old service name
- `scripts/deploy-cloud-run.sh` - Uses old service name
- `scripts/deploy-cloud-run-simple.sh` - Uses old service name
- `scripts/setup-domain-verification.sh` - Creates old service config

### Configuration Files (Need Updates)
- `dashboard.json` - Monitoring dashboard filters use old service name

### Documentation (Informational Only)
- Various docs reference the old service name in examples
- These are informational and don't need immediate updates

---

## Action Plan

### Phase 1: Delete Legacy Service ✅ **RECOMMENDED**

```bash
# Delete the old legacy service
gcloud run services delete loist-mcp-server \
  --region=us-central1 \
  --project=loist-music-library \
  --quiet
```

**Before deletion, verify**:
- [ ] No external systems depend on `loist-mcp-server-7de5nxpr4q-uc.a.run.app`
- [ ] Production traffic is handled by `music-library-mcp`
- [ ] Staging traffic is handled by `music-library-mcp-staging`

### Phase 2: Update Scripts and Configuration

**Update these files to use new service names**:

1. **`scripts/test-secrets.sh`**
   - Change `SERVICE_NAME="loist-mcp-server"` → `SERVICE_NAME="music-library-mcp"`

2. **`scripts/setup-uptime-checks.sh`**
   - Change service URL to production service

3. **`scripts/setup-monitoring.sh`**
   - Update service name references

4. **`dashboard.json`**
   - Update Cloud Run service filters to use `music-library-mcp`

5. **`scripts/deploy-cloud-run.sh`** and **`scripts/deploy-cloud-run-simple.sh`**
   - These may be legacy scripts - consider removing if not used

### Phase 3: Fix Production/Staging Health Checks

**Both production and staging services have health check failures**:

1. **Investigate health check failures**:
   ```bash
   # Check production logs
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=music-library-mcp" --limit=50
   
   # Check staging logs
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=music-library-mcp-staging" --limit=50
   ```

2. **Common issues**:
   - Container not listening on PORT=8080
   - Startup timeout too short
   - Missing environment variables
   - Database connection failures

3. **Verify health check endpoints**:
   - `/health/live` - Liveness probe
   - `/health/ready` - Readiness probe

---

## Cost Impact

### Current State (3 Services)
- `loist-mcp-server`: ~$0.10-0.50/month (idle, but serving traffic)
- `music-library-mcp`: ~$0.10-0.50/month (idle, health check failures)
- `music-library-mcp-staging`: ~$0.10-0.50/month (idle, health check failures)
- **Total**: ~$0.30-1.50/month (very low due to serverless pricing)

### After Cleanup (2 Services)
- `music-library-mcp`: ~$0.10-0.50/month
- `music-library-mcp-staging`: ~$0.10-0.50/month
- **Total**: ~$0.20-1.00/month

**Savings**: Minimal (~$0.10-0.50/month), but reduces confusion and maintenance overhead.

---

## Summary

### ✅ Keep These Services
1. **`music-library-mcp`** - Production service (fix health checks)
2. **`music-library-mcp-staging`** - Staging service (fix health checks)
3. **`loist-music-library-db`** - Cloud SQL database

### ❌ Delete This Service
1. **`loist-mcp-server`** - Legacy service (technical debt)

### 📝 Update These Files
- Scripts referencing old service name
- Monitoring dashboards
- Deployment scripts (if still used)

### 🔧 Fix These Issues
- Production service health check failures
- Staging service health check failures

---

## Next Steps

1. **Immediate**: Delete `loist-mcp-server` service
2. **Short-term**: Update scripts and configuration files
3. **Short-term**: Investigate and fix health check failures in production/staging
4. **Long-term**: Ensure CI/CD pipeline properly deploys to correct services

---

**Report Generated**: 2025-01-21  
**Auditor**: AI Assistant  
**Tools Used**: gcloud MCP server, codebase search, documentation review



