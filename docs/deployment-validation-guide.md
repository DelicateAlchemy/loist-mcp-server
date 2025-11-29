# Deployment Validation Guide

This guide explains how to validate Cloud Run deployments using the automated validation scripts.

## Overview

The validation suite tests:
- Cloud Build trigger configuration
- Cloud Run service accessibility
- Database connectivity (Cloud SQL)
- Storage operations (GCS)
- Environment configuration
- MCP protocol functionality

## Quick Start

### Run Full Validation Suite

```bash
cd /Users/Gareth/loist-mcp-server
./scripts/validate-deployment.sh
```

This executes all validation checks and generates a validation report.

### Run Individual Validations

```bash
# Test Cloud Build triggers
./scripts/test-deployment-triggers.sh

# Test Cloud Run service
./scripts/validate-cloud-run.sh

# Test database (requires credentials)
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
./scripts/validate-database.sh

# Test GCS (uses default credentials)
./scripts/validate-gcs.sh
```

## When to Run Validation

### After Deployment
- Run validation after every production deployment
- Verify all components are operational
- Check for configuration issues

### After Configuration Changes
- Environment variable updates
- Secret Manager changes
- IAM permission modifications
- Database schema migrations

### Regular Health Checks
- Weekly automated validation
- Monitor for infrastructure drift
- Catch issues before they impact users

### Troubleshooting
- Service degradation
- Unexpected errors
- Performance issues

## Validation Checklist

### Pre-Deployment
- [ ] All tests pass in staging
- [ ] Environment variables configured
- [ ] Secrets exist in Secret Manager
- [ ] IAM permissions verified
- [ ] Database migrations ready

### Post-Deployment
- [ ] Service accessible (HTTP 200/406)
- [ ] HTTPS enabled
- [ ] Cloud Build triggers operational
- [ ] Database connection works
- [ ] GCS bucket accessible
- [ ] MCP Inspector tests pass

## Interpreting Results

### Success (Exit Code 0)
```
✅ ALL VALIDATIONS PASSED

Production deployment is healthy and operational.
```
All components validated successfully. No action needed.

### Partial Success (Warnings)
```
⚠️  Some checks produced warnings
```
Review warning messages. May be expected (e.g., MCP protocol testing limitations).

### Failure (Exit Code 1)
```
❌ VALIDATION FAILED

Failed validations: 2
```
Review error messages and check:
- Service logs in Cloud Logging
- Recent Cloud Build deployments
- Service account permissions
- Secret Manager configuration

## MCP Protocol Testing

### Using MCP Inspector

**Recommended**: Use MCP Inspector for comprehensive MCP protocol testing.

```bash
# Launch MCP Inspector
npx @modelcontextprotocol/inspector@latest

# Configure in UI:
# Transport: http
# URL: https://music-library-mcp-7de5nxpr4q-uc.a.run.app/mcp
```

### Test MCP Tools
- `health_check` - Server status
- `process_audio_complete` - Audio processing pipeline
- `get_audio_metadata` - Metadata retrieval
- `search_library` - Library search

### Test MCP Resources
- `music-library://audio/{id}/stream` - Audio streaming
- `music-library://audio/{id}/metadata` - Metadata resource
- `music-library://audio/{id}/thumbnail` - Thumbnail resource

## Automated Validation

### GitHub Actions Integration

Add validation to CI/CD pipeline:

```yaml
# .github/workflows/validate-deployment.yml
- name: Validate Deployment
  run: |
    ./scripts/validate-deployment.sh
  env:
    DB_USER: ${{ secrets.DB_USER }}
    DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
```

### Cloud Scheduler

Schedule regular validation:

```bash
# Create Cloud Scheduler job
gcloud scheduler jobs create http validation-check \
  --schedule="0 */6 * * *" \
  --uri="https://your-validation-endpoint.run.app" \
  --http-method=POST
```

## Common Issues

### Cloud Run 503 Errors
**Cause**: Service not ready, cold start, or crashing  
**Action**: Check logs, increase resources, verify health checks

### Database Connection Failures
**Cause**: Missing credentials, wrong connection name, IAM issues  
**Action**: Verify Secret Manager, check service account permissions

### GCS Permission Denied
**Cause**: Missing IAM roles, wrong bucket name  
**Action**: Verify IAM roles, check bucket existence

### MCP Protocol Errors
**Cause**: Session management, transport configuration  
**Action**: Use MCP Inspector for proper testing

## Validation Report

Each validation run generates a report:

```
validation-report-YYYYMMDD-HHMMSS.txt
```

Contains:
- Timestamp
- Service URLs
- Validation results (pass/fail)
- Component status

Archive reports for compliance and troubleshooting.

## Best Practices

1. **Run validation after every deployment**
2. **Use MCP Inspector for protocol testing**
3. **Archive validation reports**
4. **Automate validation in CI/CD**
5. **Monitor validation trends**
6. **Update scripts as infrastructure changes**

## Related Documentation

- [Deployment Validation Results](./deployment-validation-results.md)
- [Rollback Procedures](./deployment-rollback-procedure.md)
- [Troubleshooting Guide](./troubleshooting-deployment.md)
- [Cloud Run Deployment](./cloud-run-deployment.md)
- [MCP Testing](./mcp-testing-guide.md)

---

**Last Updated**: 2025-11-02

