# End-to-End Deployment Validation Research - Subtask 12.10

## Overview

**Task**: Perform comprehensive testing and validation of the entire production deployment to ensure all components work together correctly.

**Status**: Pending  
**Dependencies**: Subtasks 6 (Cloud SQL), 7 (GCS), 9 (Health Checks) - ✅ All Complete  
**Note**: Custom domain mapping (subtask 8) moved to Task 19, validation proceeds without it.

## What End-to-End Validation Involves

### Core Validation Areas

Based on the subtask details, end-to-end validation includes:

1. **Smoke Tests Against Deployed Service**
   - Verify service endpoints are accessible
   - Test MCP protocol handshake (initialize/initialized)
   - Validate JSON-RPC 2.0 compliance
   - Test error handling and response formats

2. **Database Operations Validation**
   - Test Cloud SQL connection (read/write operations)
   - Validate connection pooling behavior
   - Test query performance and timeouts
   - Verify database migrations if applicable

3. **GCS File Operations Validation**
   - Test file upload to GCS bucket
   - Test file download and signed URL generation
   - Verify bucket permissions and IAM roles
   - Test lifecycle policies if configured

4. **Environment Variables & Secrets Validation**
   - Verify all environment variables are properly injected
   - Test secret access from Secret Manager
   - Validate configuration loading and defaults
   - Check environment variable precedence

5. **Load Testing & Autoscaling Validation**
   - Simulate concurrent requests
   - Verify autoscaling behavior (min/max instances)
   - Test concurrency limits
   - Validate request timeout handling

6. **Monitoring & Logging Validation**
   - Verify metrics collection in Cloud Monitoring
   - Check log aggregation in Cloud Logging
   - Test health check endpoints
   - Validate error tracking and alerting

7. **Security Audit**
   - Review IAM permissions (least privilege)
   - Verify service account configurations
   - Test authentication if enabled
   - Validate secret isolation

8. **Documentation**
   - Document deployment procedure
   - Document rollback steps
   - Create troubleshooting guide
   - Update operational runbooks

## Existing Infrastructure & Files

### Validation Scripts

**Location**: `scripts/`

1. **`scripts/validate-secrets.sh`**
   - Validates Secret Manager access
   - Tests service account permissions
   - Verifies secret injection
   - **Use for**: Secret validation testing

2. **`scripts/validate-env-config.sh`**
   - Validates environment variable configuration
   - Cross-checks Dockerfile, Cloud Build, and application config
   - Tests Python configuration loading
   - **Use for**: Environment variable validation

3. **`scripts/validate-iam-permissions.sh`**
   - Checks project-level IAM roles
   - Validates bucket-level permissions
   - Tests service account access
   - **Use for**: Security audit preparation

4. **`scripts/test-container-build.sh`**
   - Validates Docker image functionality
   - Tests multi-stage build optimization
   - Verifies security features
   - **Use for**: Pre-deployment container validation

### MCP Testing Scripts

**Location**: Root directory

1. **`test_mcp_tools.sh`** & **`test_mcp_tools_ci.sh`**
   - Tests MCP tools via stdio protocol
   - Validates JSON-RPC 2.0 responses
   - **Use for**: MCP protocol compliance testing

2. **`test_mcp_resources.sh`** & **`test_mcp_resources_ci.sh`**
   - Tests MCP resource URIs
   - Validates resource streaming
   - **Use for**: Resource endpoint validation

3. **`scripts/validate_mcp_results.js`**
   - Node.js validator for MCP protocol compliance
   - Validates JSON-RPC 2.0 format
   - Checks error serialization
   - **Use for**: Automated protocol validation

### Unit Test Files

**Location**: `tests/`

1. **`test_process_audio_complete.py`**
   - Tests audio processing pipeline
   - Validates GCS upload and database operations
   - **Use for**: Integration testing reference

2. **`test_database_pool.py`**
   - Tests database connection pooling
   - Validates Cloud SQL Proxy connections
   - **Use for**: Database operation validation

3. **`test_gcs_integration.py`**
   - Tests GCS client operations
   - Validates bucket permissions
   - **Use for**: Storage operation validation

4. **`test_authentication.py`**
   - Tests bearer token authentication
   - Validates auth flow
   - **Use for**: Security validation

5. **`test_resources.py`**
   - Tests MCP resource endpoints
   - Validates streaming operations
   - **Use for**: Resource validation

### CI/CD Infrastructure

**Location**: `.github/workflows/`

1. **`.github/workflows/mcp-validation.yml`**
   - Automated MCP protocol validation
   - Runs on PR and push to main/dev
   - Validates protocol compliance
   - **Use for**: CI/CD integration reference

### Deployment Configuration Files

1. **`cloudbuild.yaml`**
   - Production deployment configuration
   - Environment variables and secrets
   - Cloud Run service settings
   - **Use for**: Deployment validation reference

2. **`cloudbuild-staging.yaml`**
   - Staging deployment configuration
   - Separate secrets and buckets
   - **Use for**: Staging validation reference

3. **`Dockerfile`**
   - Multi-stage Alpine build
   - Runtime configuration
   - **Use for**: Container validation reference

### Documentation Files

1. **`docs/cloud-run-deployment.md`**
   - Complete deployment documentation
   - Monitoring and troubleshooting
   - **Use for**: Operational procedures

2. **`docs/environment-variables.md`**
   - Complete environment variable reference
   - Configuration examples
   - **Use for**: Configuration validation

3. **`README.md`**
   - Project overview and setup
   - Deployment instructions
   - **Use for**: High-level context

## MCP Tools & Resources to Test

### MCP Tools (from `src/server.py`)

1. **`health_check`** (Line 211)
   - Returns server status and configuration
   - **Test**: Basic health check functionality
   - **Expected**: Status 200, JSON response with service info

2. **`process_audio_complete`** (Line 252)
   - Complete audio processing pipeline
   - Downloads, processes, uploads to GCS, saves to DB
   - **Test**: End-to-end audio processing
   - **Expected**: Audio ID, metadata, resource URIs

3. **`get_audio_metadata`** (Line 318)
   - Retrieves metadata for processed audio
   - **Test**: Database read operations
   - **Expected**: Complete metadata from database

4. **`search_library`** (Line 351)
   - Searches audio library
   - **Test**: Database query operations
   - **Expected**: Search results with pagination

### MCP Resources (from `src/server.py`)

1. **`music-library://audio/{audioId}/stream`** (Line 415)
   - Audio file streaming
   - **Test**: GCS file download and streaming
   - **Expected**: Audio file stream with proper headers

2. **`music-library://audio/{audioId}/metadata`** (Line 442)
   - Audio metadata resource
   - **Test**: Resource URI parsing and metadata retrieval
   - **Expected**: JSON metadata response

3. **`music-library://audio/{audioId}/thumbnail`** (Line 466)
   - Album artwork thumbnail
   - **Test**: Image resource streaming
   - **Expected**: Image file stream

## Cloud Run Service Configuration

### Service Details (from `cloudbuild.yaml`)

- **Service Name**: `music-library-mcp`
- **Region**: `us-central1`
- **Memory**: `2Gi`
- **CPU**: `1`
- **Timeout**: `600s`
- **Concurrency**: `80`
- **Max Instances**: `10`
- **Min Instances**: `0`
- **Port**: `8080`
- **Transport**: `http`

### Service Endpoints

- **Production URL**: `https://loist-mcp-server-872391508675.us-central1.run.app/mcp`
- **Health Check**: Available via MCP `health_check` tool
- **MCP Endpoint**: `/mcp` (HTTP transport)

### Secrets Injected

- `DB_CONNECTION_NAME` (from Secret Manager)
- `GCS_BUCKET_NAME` (from Secret Manager)
- `BEARER_TOKEN` (from Secret Manager)

## Testing Approaches

### 1. Smoke Tests

**Script**: Create `scripts/smoke-test-cloud-run.sh`

```bash
# Test service accessibility
curl -X POST https://loist-mcp-server-872391508675.us-central1.run.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "health_check", "arguments": {}}, "id": 1}'

# Test MCP initialize
curl -X POST https://loist-mcp-server-872391508675.us-central1.run.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}, "id": 1}'
```

### 2. Database Operations

**Reference**: `tests/test_database_pool.py`, `tests/test_process_audio_complete.py`

```python
# Test Cloud SQL connection
from database.pool import get_connection_pool
pool = get_connection_pool()
conn = pool.get_connection()
# Execute test queries
```

### 3. GCS Operations

**Reference**: `tests/test_gcs_integration.py`, `tests/test_audio_storage.py`

```python
# Test GCS upload/download
from src.storage import create_gcs_client
client = create_gcs_client()
# Test upload, download, signed URLs
```

### 4. Load Testing

**Tools**: `ab`, `wrk`, or Python `locust`

```bash
# Simple load test
ab -n 1000 -c 10 -T application/json \
  -p health_check.json \
  https://loist-mcp-server-872391508675.us-central1.run.app/mcp
```

### 5. Monitoring Validation

**Cloud Monitoring Queries**:
- Request latency: `run.googleapis.com/request_latencies`
- Request count: `run.googleapis.com/request_count`
- Instance count: `run.googleapis.com/container/instance_count`
- Error rate: `run.googleapis.com/request_count` with status filter

**Cloud Logging Filters**:
```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=music-library-mcp" --limit 50

# Filter for errors
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 50
```

## Validation Checklist

### Pre-Deployment Validation

- [ ] Run `scripts/validate-env-config.sh`
- [ ] Run `scripts/validate-secrets.sh`
- [ ] Run `scripts/validate-iam-permissions.sh`
- [ ] Run `scripts/test-container-build.sh`
- [ ] Verify Cloud Build configuration

### Post-Deployment Validation

- [ ] **Service Accessibility**
  - [ ] Service responds to health check
  - [ ] MCP initialize handshake works
  - [ ] Service URL is accessible

- [ ] **MCP Protocol Compliance**
  - [ ] JSON-RPC 2.0 format validation
  - [ ] Tool calls return proper responses
  - [ ] Error serialization works correctly
  - [ ] Resource URIs parse correctly

- [ ] **Database Operations**
  - [ ] Cloud SQL connection established
  - [ ] Read operations work
  - [ ] Write operations work
  - [ ] Connection pooling functions correctly
  - [ ] Query timeouts work as expected

- [ ] **GCS Operations**
  - [ ] File upload to bucket works
  - [ ] File download works
  - [ ] Signed URL generation works
  - [ ] Bucket permissions correct
  - [ ] Service account has access

- [ ] **Environment Configuration**
  - [ ] All environment variables injected
  - [ ] Secrets accessible from Secret Manager
  - [ ] Configuration loading works
  - [ ] Default values correct

- [ ] **Performance & Scaling**
  - [ ] Autoscaling works (min/max instances)
  - [ ] Concurrency limits respected
  - [ ] Request timeouts work
  - [ ] Cold start performance acceptable

- [ ] **Monitoring & Logging**
  - [ ] Cloud Monitoring metrics collected
  - [ ] Cloud Logging aggregation works
  - [ ] Health check endpoints respond
  - [ ] Error tracking functional

- [ ] **Security**
  - [ ] IAM permissions follow least privilege
  - [ ] Service account configured correctly
  - [ ] Secrets isolated properly
  - [ ] Authentication works (if enabled)

### Documentation

- [ ] Document deployment procedure
- [ ] Document rollback steps
- [ ] Create troubleshooting guide
- [ ] Update operational runbooks

## Recommended Test Script Structure

Create `scripts/validate-deployment.sh`:

```bash
#!/bin/bash
# End-to-End Deployment Validation Script

set -e

SERVICE_URL="https://loist-mcp-server-872391508675.us-central1.run.app/mcp"
PROJECT_ID="loist-music-library"

# 1. Service Accessibility Tests
echo "Testing service accessibility..."
# Health check, initialize, etc.

# 2. MCP Protocol Tests
echo "Testing MCP protocol compliance..."
# Use test_mcp_tools.sh adaptation for HTTP

# 3. Database Tests
echo "Testing database operations..."
# Cloud SQL connection, read/write

# 4. GCS Tests
echo "Testing GCS operations..."
# Upload, download, signed URLs

# 5. Configuration Tests
echo "Testing configuration..."
# Environment variables, secrets

# 6. Performance Tests
echo "Testing performance..."
# Load testing, autoscaling

# 7. Monitoring Tests
echo "Testing monitoring..."
# Metrics, logs, health checks

# 8. Security Tests
echo "Testing security..."
# IAM, permissions, authentication
```

## Key Files to Reference

### Implementation Files
- `src/server.py` - MCP server implementation
- `src/config.py` - Configuration management
- `src/tools/` - Tool implementations
- `database/pool.py` - Database connection pooling
- `src/storage/` - GCS storage operations

### Configuration Files
- `cloudbuild.yaml` - Production deployment config
- `cloudbuild-staging.yaml` - Staging deployment config
- `Dockerfile` - Container build configuration
- `.env.example` - Environment variable template

### Test Files
- `tests/test_process_audio_complete.py` - Integration test example
- `tests/test_database_pool.py` - Database test example
- `tests/test_gcs_integration.py` - GCS test example

### Validation Scripts
- `scripts/validate-secrets.sh` - Secret validation
- `scripts/validate-env-config.sh` - Config validation
- `scripts/validate-iam-permissions.sh` - IAM validation
- `scripts/test-container-build.sh` - Container validation

### Documentation
- `docs/cloud-run-deployment.md` - Deployment guide
- `docs/environment-variables.md` - Config reference
- `README.md` - Project overview

## Expected Outcomes

### Success Criteria

1. **Service Operational**
   - Service responds to all MCP tool calls
   - Health check returns healthy status
   - MCP protocol compliance validated

2. **Database Functional**
   - Cloud SQL connection works
   - Read/write operations succeed
   - Connection pooling functions correctly

3. **Storage Functional**
   - GCS upload/download works
   - Signed URLs generated correctly
   - Permissions configured properly

4. **Configuration Correct**
   - All environment variables injected
   - Secrets accessible
   - Default values work

5. **Performance Acceptable**
   - Autoscaling works
   - Concurrency limits respected
   - Response times acceptable

6. **Monitoring Active**
   - Metrics collected
   - Logs aggregated
   - Health checks functional

7. **Security Compliant**
   - IAM permissions correct
   - Secrets isolated
   - Service account configured

### Deliverables

1. **Validation Script**
   - `scripts/validate-deployment.sh` - Comprehensive validation script

2. **Test Results Report**
   - Validation results document
   - Performance metrics
   - Security audit results

3. **Documentation**
   - Deployment procedure document
   - Rollback procedure document
   - Troubleshooting guide

4. **Monitoring Dashboard**
   - Cloud Monitoring dashboard configuration
   - Alerting policies

## Next Steps for Planning Agent

1. **Review Existing Infrastructure**
   - Examine validation scripts
   - Review test files
   - Understand MCP protocol requirements

2. **Design Validation Script**
   - Create comprehensive test script
   - Integrate existing validation tools
   - Add HTTP endpoint testing for Cloud Run

3. **Create Test Scenarios**
   - Define specific test cases
   - Create test data
   - Design load testing scenarios

4. **Implement Monitoring Validation**
   - Create Cloud Monitoring queries
   - Set up log filters
   - Configure alerting

5. **Document Procedures**
   - Write deployment procedure
   - Document rollback steps
   - Create troubleshooting guide

## Related Context

- **Task 12**: Parent task (Cloud Run Deployment)
- **Task 19**: Custom domain mapping (future enhancement)
- **Subtask 12.6**: Cloud SQL Connection Setup (✅ Complete)
- **Subtask 12.7**: GCS Permissions (✅ Complete)
- **Subtask 12.9**: Health Checks (✅ Complete)

---

**Last Updated**: 2025-11-02  
**Status**: Research Complete - Ready for Planning Agent

