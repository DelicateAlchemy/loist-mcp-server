# Cloud Build CI/CD Setup - GitHub Triggers Only

This document describes the streamlined CI/CD pipeline that uses **Google Cloud Build exclusively** for all build, test, and deployment operations, with GitHub serving only as a trigger mechanism.

## Architecture Overview

```
GitHub (Triggers Only)
    ↓
Google Cloud Build (Full CI/CD)
    ↓
Production/Staging Deployment
```

### Key Principles

1. **GitHub**: Minimal triggers only (pushes to main/dev branches)
2. **Cloud Build**: Complete CI/CD pipeline (test, build, deploy)
3. **No Dual Systems**: Single source of truth for all CI/CD operations

## GitHub Configuration

### Minimal Trigger Workflow (`.github/workflows/cloud-build-trigger.yml`)

```yaml
name: Cloud Build Trigger

on:
  push:
    branches: [ main, dev ]

jobs:
  trigger-cloud-build:
    runs-on: ubuntu-latest
    steps:
    - name: Authenticate to Google Cloud
      uses: google-github-actions/auth@v2
      with:
        credentials_json: ${{ secrets.GCLOUD_SERVICE_KEY }}

    - name: Trigger Cloud Build
      run: |
        gcloud builds submit \
          --config=cloudbuild.yaml \
          --substitutions=_COMMIT_SHA=${{ github.sha }},_BRANCH=${{ github.ref_name }}
```

**Purpose**: GitHub handles authentication and triggers Cloud Build with commit context.

## Cloud Build Pipeline

### Production Pipeline (`cloudbuild.yaml`)

1. **Unit Tests** - Fast tests without external dependencies
2. **Database Tests** - Integration tests using testcontainers
3. **Migration Check** - Database migration validation
4. **MCP Validation** - Protocol compliance testing
5. **Static Analysis** - Code quality checks
6. **Build & Deploy** - Container build and Cloud Run deployment

### Staging Pipeline (`cloudbuild-staging.yaml`)

Same steps as production but with:
- Relaxed test coverage thresholds (65% vs 75%)
- Warning-only test failures (continues deployment)
- Different environment variables and secrets

## Test Strategy

### Marker-Based Test Filtering

**Root `conftest.py`** provides automatic marker assignment:

```python
# Database tests automatically marked with @pytest.mark.requires_db
# GCS tests automatically marked with @pytest.mark.requires_gcs
# Unit tests are everything else

# Cloud Build runs:
# - Unit tests: pytest -m "not (requires_db or requires_gcs or slow)"
# - Database tests: pytest -m "requires_db" (with testcontainers)
```

### Test Execution Strategy

| Environment | Unit Tests | Database Tests | Coverage Required |
|-------------|------------|----------------|-------------------|
| Production  | ✅ Blocking | ✅ Blocking    | 75% unit, 70% DB |
| Staging     | ⚠️ Warning  | ⚠️ Warning     | 65% unit, 60% DB |

## Database Testing with TestContainers

### Configuration

```yaml
# In Cloud Build step
- name: 'python:3.11-slim'
  id: 'run-database-tests'
  env:
    - 'DOCKER_HOST=unix:///var/run/docker.sock'
  args:
    - '-c'
    - |
      # Install testcontainers
      pip install testcontainers[postgresql]

      # Start Docker daemon
      service docker start

      # Run database tests
      python -m pytest -m "requires_db" --cov-fail-under=70
```

### Benefits

- **Isolated Testing**: Each test gets a fresh PostgreSQL container
- **No External Dependencies**: No need for shared test databases
- **Parallel Execution**: Tests can run concurrently
- **CI/CD Ready**: Works in Google Cloud Build environment

## Migration Validation

### Automated Checks

```yaml
# Database migration validation step
- name: 'python:3.11-slim'
  id: 'db-migration-check'
  env:
    - 'DB_HOST=${_DB_HOST}'
    - 'DB_PASSWORD=${_DB_PASSWORD}'
  args:
    - '-c'
    - |
      python -c "
      from database.migrate import MigrationRunner
      runner = MigrationRunner()
      status = runner.get_status()
      print(f'Migrations: {status}')
      "
```

## Artifact Storage

### Automatic Upload to GCS

```yaml
# Store all test artifacts
- name: 'gcr.io/cloud-builders/gsutil'
  id: 'store-artifacts'
  args: [
    '-m', 'cp', '-r',
    'test-results/',
    'coverage-reports/',
    'analysis-results/',
    'migration-check/',
    'mcp-validation-results/',
    'gs://$PROJECT_ID-build-artifacts/$COMMIT_SHA/'
  ]
```

## Environment Variables

### Production vs Staging

| Variable Type | Production | Staging |
|---------------|------------|---------|
| Database Host | `${_DB_HOST}` | `${_DB_HOST_STAGING}` |
| Coverage Threshold | 75% unit, 70% DB | 65% unit, 60% DB |
| Test Failure Behavior | Blocking | Warning |
| Secrets | Production secrets | Staging secrets |

## Monitoring & Debugging

### Build Logs

All build logs are available in Google Cloud Logging with structured logging for:
- Test results and coverage reports
- Migration status
- MCP validation results
- Deployment status

### Artifact Access

Test artifacts and reports are stored in:
- `gs://$PROJECT_ID-build-artifacts/$COMMIT_SHA/`

## Benefits of This Approach

### ✅ Advantages

1. **Single Source of Truth**: All CI/CD logic in Cloud Build
2. **Better Performance**: Optimized for Google Cloud infrastructure
3. **Cost Effective**: No duplicate GitHub Actions runners
4. **Security**: Secrets managed in Google Secret Manager
5. **Scalability**: Cloud Build can handle large builds
6. **Integration**: Native Google Cloud service integration

### ❌ Trade-offs

1. **Google Cloud Lock-in**: Tied to GCP ecosystem
2. **Less GitHub Integration**: No GitHub checks/statuses
3. **Learning Curve**: Cloud Build syntax different from GitHub Actions

## Migration from GitHub Actions

### What Was Removed

- `cloud-run-deployment.yml` - Manual deployment steps
- `database-provisioning.yml` - Database provisioning workflows
- All manual CI/CD steps in GitHub Actions

### What Was Kept

- Branch-based triggers (main/dev)
- Authentication setup
- Minimal Cloud Build triggering

## Troubleshooting

### Common Issues

1. **TestContainers Not Working**: Ensure Docker daemon starts in Cloud Build
2. **Database Connection Issues**: Check Cloud SQL connectivity and secrets
3. **MCP Validation Failures**: Verify stdio mode compatibility
4. **Artifact Upload Failures**: Check GCS bucket permissions

### Debug Steps

1. Check Cloud Build logs in Google Cloud Console
2. Review stored artifacts in GCS bucket
3. Test locally with `cloud-build-local` if available
4. Validate environment variable substitution

---

## Summary

This Cloud Build-only CI/CD setup provides a streamlined, maintainable pipeline that leverages Google's infrastructure while keeping GitHub as a simple trigger mechanism. The marker-based test filtering and testcontainers approach ensures reliable, isolated testing without external dependencies.
