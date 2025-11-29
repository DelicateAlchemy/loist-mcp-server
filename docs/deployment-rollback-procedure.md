# Deployment Rollback Procedure

This document provides step-by-step procedures for rolling back Cloud Run deployments in case of issues.

## Quick Rollback

### Cloud Run Revision Rollback

**Fastest method** - rollback to previous Cloud Run revision:

```bash
# 1. List recent revisions
gcloud run revisions list \
  --service=music-library-mcp \
  --region=us-central1 \
  --project=loist-music-library \
  --limit=5

# 2. Identify last known good revision (e.g., music-library-mcp-00042-abc)

# 3. Rollback to specific revision
gcloud run services update-traffic music-library-mcp \
  --to-revisions=music-library-mcp-00042-abc=100 \
  --region=us-central1 \
  --project=loist-music-library
```

**Time**: ~30 seconds  
**Downtime**: None (gradual traffic shift)

## Rollback Scenarios

### 1. Bad Deployment (Application Error)

**Symptoms**:
- 500 errors
- Application crashes
- Health check failures

**Steps**:
1. Rollback Cloud Run revision (see Quick Rollback above)
2. Verify service health
3. Investigate logs for root cause

### 2. Database Migration Issues

**Symptoms**:
- Database errors
- Schema mismatches
- Connection failures

**Steps**:
1. Do NOT rollback Cloud Run immediately
2. Rollback database migration first:
```bash
cd /Users/Gareth/loist-mcp-server
python -m database.migrate rollback
```
3. Then rollback Cloud Run revision
4. Verify database schema
5. Test application functionality

### 3. Configuration Issues

**Symptoms**:
- Missing environment variables
- Secret access errors
- Configuration validation failures

**Steps**:
1. Identify missing/incorrect configuration
2. Update Secret Manager or environment variables
3. Redeploy with correct configuration
4. If urgent, rollback to previous revision

### 4. Dependency Issues

**Symptoms**:
- Import errors
- Missing libraries
- Version conflicts

**Steps**:
1. Rollback Cloud Run revision immediately
2. Review `requirements.txt` changes
3. Test dependencies locally
4. Fix and redeploy

## Rollback Decision Matrix

| Issue Type | Rollback Cloud Run? | Rollback Database? | Additional Actions |
|------------|---------------------|--------------------|--------------------|
| Application crash | ✅ Yes | ❌ No | Check logs |
| Database migration | ⏸️ After DB rollback | ✅ Yes | Verify schema |
| Environment config | ✅ Yes | ❌ No | Fix secrets |
| Dependency error | ✅ Yes | ❌ No | Update requirements |
| Performance issue | ⚠️ Maybe | ❌ No | Check resources |
| Security issue | ✅ Yes immediately | ❓ Depends | Audit logs |

## Detailed Procedures

### Cloud Run Rollback

#### Method 1: Traffic Split (Gradual)

```bash
# Send 50% traffic to previous revision
gcloud run services update-traffic music-library-mcp \
  --to-revisions=PREVIOUS_REVISION=50,CURRENT_REVISION=50 \
  --region=us-central1 \
  --project=loist-music-library

# Monitor for 5-10 minutes

# If stable, route 100% to previous
gcloud run services update-traffic music-library-mcp \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1 \
  --project=loist-music-library
```

#### Method 2: Immediate Switch

```bash
# Route 100% traffic immediately
gcloud run services update-traffic music-library-mcp \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1 \
  --project=loist-music-library
```

#### Method 3: Rollback via Cloud Console

1. Go to Cloud Run Console
2. Select `music-library-mcp` service
3. Click "Revisions" tab
4. Find last known good revision
5. Click "Actions" → "Manage traffic"
6. Set traffic to 100% for that revision
7. Click "Save"

### Database Rollback

#### Migration Rollback

```bash
# 1. Check current migration version
python -m database.migrate version

# 2. List available migrations
ls database/migrations/

# 3. Rollback to specific version
python -m database.migrate rollback --to-version=001

# 4. Verify rollback
python -m database.migrate version
```

#### Manual Database Rollback

```bash
# 1. Connect to database
gcloud sql connect loist-music-library-db \
  --user=music_library_user \
  --database=music_library \
  --project=loist-music-library

# 2. Execute rollback SQL
\i database/migrations/001_initial_schema_rollback.sql

# 3. Verify tables
\dt
```

### GCS Rollback

**Note**: GCS bucket changes are usually not rolled back. Data is preserved.

If needed:
```bash
# Restore files from backup
gsutil -m cp -r gs://backup-bucket/* gs://loist-mvp-audio-files/

# Or restore specific file
gsutil cp gs://backup-bucket/audio-file.mp3 gs://loist-mvp-audio-files/
```

## Post-Rollback Checklist

### Immediate (within 5 minutes)
- [ ] Verify service is responding
- [ ] Check error rates in Cloud Logging
- [ ] Test critical user flows
- [ ] Confirm database connectivity
- [ ] Verify GCS operations

### Short-term (within 1 hour)
- [ ] Run validation suite (`./scripts/validate-deployment.sh`)
- [ ] Check metrics in Cloud Monitoring
- [ ] Review user reports
- [ ] Document rollback in incident report
- [ ] Identify root cause

### Medium-term (within 1 day)
- [ ] Fix root cause
- [ ] Test fix in staging
- [ ] Plan redeployment
- [ ] Update deployment procedures
- [ ] Review monitoring/alerting

## Rollback Communication

### Internal Team
```
🚨 ROLLBACK IN PROGRESS

Service: music-library-mcp
Reason: [brief description]
Action: Rolling back to revision [XX]
ETA: [5 minutes]
Status: [In Progress / Complete]
```

### Status Page
```
We are experiencing issues with our service and have initiated a rollback to a stable version. 
Expected resolution time: 10 minutes.
```

## Prevention

### Pre-Deployment
- Run full test suite
- Deploy to staging first
- Validate staging deployment
- Review recent changes
- Check dependency updates

### Deployment
- Use gradual rollout (10% → 50% → 100%)
- Monitor metrics during deployment
- Have rollback plan ready
- Keep team on standby

### Post-Deployment
- Monitor for 30 minutes
- Run validation suite
- Check error rates
- Review performance metrics
- Document deployment

## Rollback Testing

**Regularly test rollback procedures:**

```bash
# 1. Deploy test version
# 2. Verify deployment
# 3. Practice rollback
# 4. Measure rollback time
# 5. Document any issues
```

**Target rollback times:**
- Cloud Run: < 1 minute
- With database: < 5 minutes
- Full stack: < 10 minutes

## Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| Primary On-Call | [Contact info] | 24/7 |
| Secondary On-Call | [Contact info] | 24/7 |
| Database Admin | [Contact info] | Business hours |
| Security Team | [Contact info] | 24/7 (incidents) |

## Related Documentation

- [Deployment Validation Guide](./deployment-validation-guide.md)
- [Troubleshooting Guide](./troubleshooting-deployment.md)
- [Cloud Run Deployment](./cloud-run-deployment.md)

---

**Last Updated**: 2025-11-02  
**Review**: Quarterly or after major incidents

