# Deployment Troubleshooting Guide

Common issues and solutions for Cloud Run deployment problems, including signed URL generation failures and deployment mismatches.

## Quick Diagnostics

### Check Service Status

```bash
# Service status
gcloud run services describe music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library \
  --format="value(status.conditions[0].status,status.conditions[0].message)"

# Recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=music-library-mcp" \
  --limit=50 \
  --project=loist-music-library
```

### Check Recent Builds

```bash
# Recent Cloud Build history
gcloud builds list \
  --project=loist-music-library \
  --limit=5 \
  --format="table(id,status,createTime,source.repoSource.branchName)"
```

## Signed URL Generation Issues

### Deployment Mismatch Detection

**Symptom**: `TypeError: Blob.generate_signed_url() got an unexpected keyword argument 'signer'`

**Root Cause**: Old code still deployed despite local updates

**Diagnosis**:
```bash
# Check deployed image tag
gcloud run services describe music-library-mcp-staging \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].image)"

# Check recent logs for error signature
gcloud run services logs read music-library-mcp-staging \
  --region=us-central1 \
  --limit=20 | grep -E "(signer|TypeError)"
```

**Resolution**:
1. Verify latest code is committed and pushed
2. Trigger new deployment:
   ```bash
   gcloud run deploy music-library-mcp-staging \
     --source . \
     --region us-central1
   ```
3. Verify fix:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" "https://staging.loist.io/embed/{audioId}"
   # Should return 200, not 500
   ```

### IAM SignBlob Permission Issues

**Symptom**: `403 Forbidden` errors in signed URL generation

**Diagnosis**:
```bash
# Check service account IAM bindings
gcloud iam service-accounts get-iam-policy \
  mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com
```

**Required Permissions**:
- `roles/iam.serviceAccountTokenCreator` on itself
- `roles/storage.objectAdmin` at project level

**Resolution**:
```bash
# Grant required permissions
gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud iam service-accounts add-iam-policy-binding \
  mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### Debug Signed URL Generation

**Use the debug script**:
```bash
python3 scripts/debug_signed_url_generation.py {audioId}
```

**Expected Success Indicators**:
- `[SIGNED_URL_DEBUG] Signed URL generated successfully`
- `✅ V4 signature components detected`
- HTTP 200 response from embed endpoint

## Common Issues

### 1. Service Not Starting

**Symptoms**:
- Cloud Run shows service as "Not Ready"
- Container crashes immediately
- Health check failures

**Diagnostic**:
```bash
# Check container logs
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit=100 \
  --project=loist-music-library
```

**Common Causes**:

| Cause | Solution |
|-------|----------|
| Missing environment variable | Check `cloudbuild.yaml`, add missing var |
| Secret not accessible | Verify Secret Manager permissions |
| Port mismatch | Ensure app listens on `PORT` env var (8080) |
| Import error | Check `requirements.txt`, rebuild image |
| Database connection error | Verify `DB_CONNECTION_NAME` secret |

**Fix**:
```bash
# Update environment variable
gcloud run services update music-library-mcp \
  --set-env-vars="MISSING_VAR=value" \
  --region=us-central1 \
  --project=loist-music-library
```

### 2. Cloud Build Failing

**Symptoms**:
- Build status: FAILURE
- Image not created
- Deployment not triggered

**Diagnostic**:
```bash
# Get build logs
gcloud builds log BUILD_ID --project=loist-music-library
```

**Common Causes**:

| Error | Cause | Solution |
|-------|-------|----------|
| `pip install failed` | Dependency conflict | Fix `requirements.txt` |
| `No such file` | Missing Dockerfile | Check file exists in repo |
| `Permission denied` | IAM issue | Verify service account roles |
| `timeout` | Build too slow | Increase timeout in `cloudbuild.yaml` |
| `secret not found` | Missing secret | Create secret in Secret Manager |

**Fix**:
```bash
# Rerun build
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=loist-music-library
```

### 3. Database Connection Errors

**Symptoms**:
- `connection refused`
- `timeout connecting to database`
- `authentication failed`

**Diagnostic**:
```bash
# Check Cloud SQL instance
gcloud sql instances describe loist-music-library-db \
  --project=loist-music-library \
  --format="value(state,settings.tier,databaseVersion)"

# Check secret
gcloud secrets versions access latest \
  --secret=db-connection-name \
  --project=loist-music-library
```

**Common Causes**:

| Issue | Solution |
|-------|----------|
| Wrong connection name | Update `DB_CONNECTION_NAME` secret |
| Instance stopped | Start Cloud SQL instance |
| IAM permissions missing | Add `roles/cloudsql.client` to service account |
| Password incorrect | Update `DB_PASSWORD` secret |
| Network issue | Check VPC connector (if using) |

**Fix**:
```bash
# Update connection name secret
echo -n "loist-music-library:us-central1:loist-music-library-db" | \
  gcloud secrets versions add db-connection-name \
  --data-file=- \
  --project=loist-music-library

# Redeploy to pick up new secret
gcloud run services update music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library
```

### 4. GCS Permission Denied

**Symptoms**:
- `403 Forbidden`
- `storage.buckets.get permission denied`
- Upload/download failures

**Diagnostic**:
```bash
# Check bucket IAM
gsutil iam get gs://loist-mvp-audio-files

# Check service account
gcloud run services describe music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library \
  --format="value(spec.template.spec.serviceAccountName)"
```

**Fix**:
```bash
# Grant storage permissions
gsutil iam ch \
  serviceAccount:loist-music-library-sa@loist-music-library.iam.gserviceaccount.com:roles/storage.objectAdmin \
  gs://loist-mvp-audio-files
```

### 5. Trigger Not Firing

**Symptoms**:
- Push to `main`/`dev` doesn't trigger build
- No build appears in Cloud Build history

**Diagnostic**:
```bash
# Check trigger configuration
gcloud builds triggers describe production-deployment-init-location \
  --project=loist-music-library

# Check GitHub webhook
# Go to: GitHub repo → Settings → Webhooks
# Look for cloudbuild.googleapis.com webhook
# Check "Recent Deliveries" for errors
```

**Common Causes**:

| Issue | Solution |
|-------|----------|
| Trigger disabled | Enable trigger in Cloud Build console |
| Wrong branch pattern | Update trigger branch regex |
| GitHub app disconnected | Reconnect GitHub app |
| Webhook delivery failed | Redeliver webhook in GitHub |

**Fix**:
```bash
# Manually trigger build
gcloud builds triggers run production-deployment-init-location \
  --branch=main \
  --project=loist-music-library
```

### 6. MCP Protocol Errors

**Symptoms**:
- `Missing session ID`
- `Not Acceptable`
- `Bad Request`

**Diagnostic**:
- These are expected for HTTP transport without proper session setup
- Use MCP Inspector for testing

**Solution**:
```bash
# Use MCP Inspector
npx @modelcontextprotocol/inspector@latest

# Configure:
# - Transport: http
# - URL: https://music-library-mcp-7de5nxpr4q-uc.a.run.app/mcp
```

### 7. High Latency / Timeouts

**Symptoms**:
- Requests taking > 10 seconds
- Timeout errors
- 504 Gateway Timeout

**Diagnostic**:
```bash
# Check Cloud Run metrics
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_latencies"' \
  --format=json \
  --project=loist-music-library
```

**Common Causes**:

| Issue | Solution |
|-------|----------|
| Cold start | Increase min instances |
| Database query slow | Add indexes, optimize queries |
| Memory limit | Increase memory allocation |
| CPU throttling | Increase CPU allocation |
| External API timeout | Add timeout/retry logic |

**Fix**:
```bash
# Increase resources
gcloud run services update music-library-mcp \
  --memory=4Gi \
  --cpu=2 \
  --min-instances=1 \
  --region=us-central1 \
  --project=loist-music-library
```

### 8. High Error Rate

**Symptoms**:
- Many 500 errors in logs
- Error rate spike in monitoring

**Diagnostic**:
```bash
# Count recent errors
gcloud logging read \
  "resource.type=cloud_run_revision AND severity=ERROR" \
  --limit=100 \
  --project=loist-music-library \
  --format="table(timestamp,textPayload)"
```

**Actions**:
1. Check error patterns in logs
2. Review recent deployments
3. Check dependency versions
4. Verify external service status
5. Consider rollback if severe

## Debugging Techniques

### Enable Debug Logging

```bash
# Update service with debug logging
gcloud run services update music-library-mcp \
  --set-env-vars="LOG_LEVEL=DEBUG" \
  --region=us-central1 \
  --project=loist-music-library
```

### Test Locally

```bash
# Run server locally
cd /Users/Gareth/loist-mcp-server
docker-compose up

# Or with Docker
docker build -t music-library-mcp:debug .
docker run -p 8080:8080 \
  -e LOG_LEVEL=DEBUG \
  music-library-mcp:debug
```

### Reproduce Issue

```bash
# Test endpoint directly
curl -X POST https://music-library-mcp-7de5nxpr4q-uc.a.run.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'
```

## Monitoring Queries

### Cloud Monitoring

```bash
# Request count
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count"'

# Error rate
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count" AND metric.label.response_code_class="5xx"'

# Instance count
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/container/instance_count"'
```

### Cloud Logging Filters

```bash
# All errors
resource.type="cloud_run_revision" AND severity>=ERROR

# Specific service
resource.type="cloud_run_revision" AND resource.labels.service_name="music-library-mcp"

# Time range
resource.type="cloud_run_revision" AND timestamp>="2025-11-02T00:00:00Z"

# Search text
resource.type="cloud_run_revision" AND textPayload:"database connection"
```

## When to Escalate

Escalate if:
- ❌ Service down > 15 minutes
- ❌ Data loss or corruption
- ❌ Security incident
- ❌ Unable to rollback
- ❌ Affects multiple services

## Related Documentation

- [Deployment Validation Guide](./deployment-validation-guide.md)
- [Rollback Procedures](./deployment-rollback-procedure.md)
- [Cloud Run Deployment](./cloud-run-deployment.md)
- [Environment Variables](./environment-variables.md)

---

**Last Updated**: 2025-11-02

