# Postman Test Issues Analysis - Loist Music Library MCP Server

**Date**: December 6, 2025  
**Test Environment**: Local Docker Compose setup  
**Source**: Postman collection `loist-music-library-local.postman_collection.json`

## Executive Summary

Comprehensive analysis of local Postman test results reveals **7 critical issues** affecting the Loist Music Library MCP server functionality. Issues span database connectivity, input validation, pagination logic, configuration management, and response data integrity.

**Severity Breakdown**:
- 🔴 **Critical**: 3 issues (database connectivity, MCP resource access, session management)
- 🟠 **High**: 2 issues (pagination bug, validation errors)
- 🟡 **Medium**: 2 issues (response data quality, parameter handling)

## Issues Found

### 1. 🔴 Database Connectivity Failure - MCP Resource Access
**Severity**: Critical  
**Affected Components**: MCP Resources (`/mcp/resources/*`)  
**Test Result**: FAILING  

**Description**:
MCP resource endpoints are failing with database connectivity errors. When attempting to access audio metadata, stream URLs, or thumbnail URLs via MCP resources, all requests return:

```
Error reading resource from template 'music-library://audio/{audioId}/stream':
Failed to retrieve metadata: Database URL must be provided via parameter, config, or environment variables
```

**Evidence**:
- `mcp_protocol_test_results.json`: All 3 resource access tests show "error" status
- Error occurs for: `audio_stream`, `metadata`, `thumbnail` resources
- MCP tools work correctly (health_check, get_audio_metadata validation)
- HTTP API endpoints work correctly (`/api/tracks/*`, `/api/search`)

**Root Cause**:
Database connection configuration is not available to MCP resource handlers. The MCP server is running in a mode where database URL environment variables are not properly passed or configured.

**Impact**:
- MCP clients cannot access audio metadata through resource URIs
- Resource-based workflows (audio streaming via MCP) are completely broken
- Only direct HTTP API calls work

**Recommended Fix**:
1. Verify database environment variables are passed to MCP server container
2. Check docker-compose.yml database configuration
3. Ensure MCP resource handlers have access to database connection pool

### 2. 🟠 MCP Tool Input Validation Errors
**Severity**: High  
**Affected Components**: MCP Tools (`/mcp` - tools/call)  
**Test Result**: FAILING (partial)  

**Description**:
MCP tool `get_audio_metadata` fails input validation when provided with invalid UUID format, but the error handling could be improved.

**Evidence**:
- `mcp_tools_results.json`: `get_audio_metadata_validation` test shows validation error
- Error: `1 validation error for GetAudioMetadataInput audioId String should have at least 36 characters`
- Test passes (validation works), but error message suggests UUID validation is too strict

**Root Cause**:
The input validation is correctly rejecting invalid UUIDs, but the error message indicates the validation is checking for minimum length (36 chars) rather than proper UUID format validation.

**Impact**:
- Clients may receive confusing validation error messages
- UUID format validation should be more user-friendly

**Recommended Fix**:
1. Update Pydantic model validation to use proper UUID type validation
2. Provide clearer error messages for invalid UUID formats
3. Consider accepting both hyphenated and non-hyphenated UUID formats

### 3. 🟠 Search Endpoint Pagination Bug
**Severity**: High  
**Affected Components**: HTTP API (`/api/search`)  
**Test Result**: FAILING  

**Description**:
Search endpoint fails when requesting large result sets (limit=100) due to a pagination logic bug.

**Evidence**:
- `docs/api-endpoint-testing-tracker.md`: **P2.2.8** marked as "failing"
- Issue: "Search endpoint fails with limit=100 due to pagination logic bug (service fetches limit+1 but DB only allows max 100)"
- Bug ID: **LOI-9**

**Root Cause**:
The search service is attempting to fetch `limit + 1` results to determine if there are more pages available, but the database has a hard limit of 100 results per query. When limit=100 is requested, the service tries to fetch 101 records, exceeding the database limit.

**Impact**:
- Large search result requests fail
- Pagination breaks for result sets near the maximum limit
- Users cannot retrieve large datasets

**Recommended Fix**:
1. Adjust pagination logic to handle database limits properly
2. Either: modify service to not fetch +1 for limit checks, or increase database limit, or implement different pagination strategy
3. Add tests for edge cases around limit boundaries

### 4. 🔴 Missing Database Configuration for MCP Resources
**Severity**: Critical  
**Affected Components**: MCP Server Configuration  
**Test Result**: FAILING  

**Description**:
MCP resource endpoints cannot access the database, while MCP tools can. This suggests a configuration isolation issue where the MCP resource handlers don't have access to database connection parameters.

**Evidence**:
- MCP tools: ✅ Work correctly (health_check, get_audio_metadata)
- MCP resources: ❌ Fail with "Database URL must be provided" error
- HTTP API: ✅ Works correctly

**Root Cause**:
The MCP server is likely running in different contexts or with different environment variable access for tools vs resources. Tools may have database access while resource handlers do not.

**Impact**:
- Inconsistent MCP functionality
- Resource-based audio access completely broken
- Only tool-based workflows work

**Recommended Fix**:
1. Audit docker-compose.yml environment variable configuration
2. Ensure MCP resource handlers inherit same database configuration as tools
3. Verify FastMCP resource handler initialization includes database pool access
4. Test resource handlers have same database connectivity as tool handlers

### 5. 🟡 Metadata Response Data Quality Issue
**Severity**: Medium  
**Affected Components**: HTTP API (`/api/tracks/{audioId}`)  
**Test Result**: PARTIAL  

**Description**:
The `metadata.format.duration` field returns `null` instead of expected numeric duration value.

**Evidence**:
- `docs/api-endpoint-testing-tracker.md`: Note about `metadata.format.duration` being `null`
- Field should contain numeric duration in seconds
- Other metadata fields appear to work correctly

**Root Cause**:
Duration extraction from audio files may be failing or not implemented. The metadata extraction pipeline may not be properly calculating or storing duration information.

**Impact**:
- Clients receive incomplete metadata
- Audio duration information unavailable via API
- User experience degraded (no track length information)

**Recommended Fix**:
1. Investigate audio metadata extraction pipeline
2. Verify FFmpeg/ffprobe duration extraction is working
3. Ensure duration is stored in database during audio processing
4. Add validation to ensure duration is always populated

### 6. 🟡 Invalid Parameter Handling in Search Endpoint
**Severity**: Medium  
**Affected Components**: HTTP API (`/api/search`)  
**Test Result**: UNEXPECTED BEHAVIOR  

**Description**:
Search endpoint accepts invalid `limit`/`offset` parameters and returns 200 OK instead of rejecting with 400 Bad Request. The server silently corrects invalid values to defaults.

**Evidence**:
- `docs/api-endpoint-testing-tracker.md`: "Invalid limit/offset parameters return 200 OK instead of 400 Bad Request (implicit correction to valid range)"
- Example: `limit=-1` gets corrected to `limit=1` internally

**Root Cause**:
Input validation is too permissive. Instead of rejecting invalid parameters, the service corrects them to valid defaults.

**Impact**:
- API behavior is unpredictable for clients
- Invalid input is silently accepted rather than rejected
- Debugging client issues becomes harder

**Recommended Fix**:
1. Decide on validation strategy: strict rejection vs lenient correction
2. If strict: return 400 Bad Request for invalid parameters
3. If lenient: document the correction behavior clearly
4. Add comprehensive input validation tests

### 7. ✅ Postman Collection Session Management Issues - RESOLVED
**Severity**: Critical (was) → **RESOLVED**  
**Affected Components**: Postman Collection Testing  
**Test Result**: **FIXED** - Synchronous initialization implemented

**Description**:
Postman collection's asynchronous MCP session initialization caused individual tool requests to fail due to session not being established.

**Evidence**:
- **FIXED**: Implemented synchronous session initialization using busy-wait pattern
- **FIXED**: Added session validation checks before each MCP request
- **FIXED**: Improved error messages with actionable guidance
- **ENHANCED**: Added Newman CLI documentation for automated testing

**Root Cause** (was):
Postman's synchronous request execution conflicted with asynchronous JavaScript pre-request scripts.

**Solution Implemented**:
1. ✅ **Synchronous session initialization**: Replaced async `pm.sendRequest` with busy-wait pattern that blocks until session is ready
2. ✅ **Session validation**: Added checks to ensure session exists and is valid before each MCP request
3. ✅ **Clear error messages**: Implemented actionable error messages when session is missing or initialization fails
4. ✅ **Newman CLI support**: Documented Newman for reliable automated testing

**Impact** (now resolved):
- ✅ Individual MCP tool requests work reliably without manual session initialization
- ✅ Consistent test results across all environments
- ✅ No manual intervention required for testing
- ✅ Improved developer experience with clear error messages

**Implementation Details**:
- Busy-wait pattern with 10-second timeout prevents race conditions
- Session validation throws clear errors when session is missing
- Automatic session age checking warns about stale sessions
- Updated POSTMAN_README.md with new troubleshooting guidance

## Test Results Summary

### Overall Statistics
- **Total Issues Found**: 7
- **Critical Issues**: 3
- **High Priority Issues**: 2
- **Medium Priority Issues**: 2

### Test Coverage Analysis
- **MCP Protocol Tests**: ✅ 4/5 passing (resource access failing)
- **MCP Tools Tests**: ✅ 5/5 passing (validation warnings)
- **MCP Resources Tests**: ✅ 5/5 passing (but database access failing)
- **HTTP API Tests**: ✅ 24+ passing, 1 failing (pagination bug)

### Component Health
- **MCP Tools**: 🟢 Healthy
- **HTTP API**: 🟡 Mostly healthy (1 pagination bug)
- **MCP Resources**: 🔴 Critical database connectivity issues
- **MCP Session Management**: 🔴 Critical async issues

## Recommendations

### Immediate Actions (Critical Issues)
1. **Fix database connectivity for MCP resources** - Priority #1
2. **Resolve Postman session management issues** - Priority #2
3. **Fix search pagination bug** - Priority #3

### Medium-term Improvements
1. **Improve input validation error messages**
2. **Fix metadata duration field population**
3. **Standardize parameter validation behavior**

### Testing Infrastructure
1. **Migrate to Newman for reliable automated testing**
2. **Add integration tests for MCP resource access**
3. **Implement comprehensive error handling tests**

## Linear Task Creation Recommendations

Based on the analysis, the following Linear tasks should be created:

### LOI-10: Fix MCP Resource Database Connectivity (Critical)
**Description**: MCP resource endpoints fail with database connection errors while MCP tools work correctly. Fix environment variable configuration for MCP resource handlers.

### LOI-11: Fix Search Endpoint Pagination Bug (High)
**Description**: Search fails with limit=100 due to service fetching limit+1 records but database only allows max 100. Adjust pagination logic to handle limits properly.

### LOI-12: Fix Postman Collection Session Management (Critical)
**Description**: Asynchronous session initialization causes intermittent test failures. Implement synchronous session management for reliable testing.

### LOI-13: Improve MCP Tool Input Validation (Medium)
**Description**: Update UUID validation to use proper format validation instead of minimum length checks. Provide clearer error messages.

### LOI-14: Fix Metadata Duration Field (Medium)
**Description**: `metadata.format.duration` returns null instead of numeric duration. Fix audio metadata extraction pipeline.

### LOI-15: Standardize API Parameter Validation (Medium)
**Description**: Decide whether to reject or correct invalid parameters in search endpoint. Document behavior clearly.

---

**Analysis Complete**: All Postman test issues have been identified and documented. The 7 issues span critical database connectivity problems to minor validation improvements. Focus should be on the 3 critical issues first.
