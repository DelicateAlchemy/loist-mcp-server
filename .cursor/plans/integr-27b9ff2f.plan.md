<!-- 27b9ff2f-762f-49d4-9324-d888bd6d70d0 9ba946d5-4e9e-46c6-9196-ffa975d35408 -->
# MCP CI/CD Automation Plan

## Overview

Build on the completed MCP Inspector integration to add automated CI/CD validation using GitHub Actions. This will catch MCP protocol violations, validate error serialization, and ensure server reliability in pull requests and deployments.

## Prerequisites

- ✅ MCP Inspector integration completed (from previous plan)
- ✅ Existing test scripts: `test_mcp_tools.sh`, `test_mcp_resources.sh`
- ✅ Docker-based server setup working
- GitHub repository with Actions enabled

## Implementation Approach

### 1. Enhance Test Scripts with JSON Output

- Modify existing test scripts to output structured JSON results
- Add timestamps, test names, and success/failure indicators
- Ensure consistent error format validation

### 2. Create JSON Response Validation

- Build Node.js validator script to parse MCP JSON responses
- Validate MCP protocol compliance (jsonrpc 2.0, proper error codes)
- Check standardized error format from `src/error_utils.py`
- Verify tool/resource response schemas

### 3. GitHub Actions Quality Gates

- Create workflow that runs on PR and push to main
- Use existing Docker setup for consistent environment
- Fail CI if MCP protocol violations detected
- Block merges on validation failures

### 4. Test Reporting & Debugging

- Generate structured test reports with pass/fail details
- Upload artifacts for failed test debugging
- Create GitHub step summaries with key results
- Include performance metrics (response times)

## Specific Validations

### MCP Protocol Compliance

- All responses follow JSON-RPC 2.0 format
- Tool calls return proper `result` or `error` objects
- Resource URIs parse correctly and return expected formats
- Initialize/initialized handshake works correctly

### Error Serialization Validation

- All custom exceptions serialize to standardized format
- Error codes match `ERROR_CODES` from `src/error_utils.py`
- Database connection errors handled gracefully
- Validation errors include proper details

### Performance & Reliability

- Health check responds within reasonable time
- Server startup completes without errors
- All 10 custom exceptions load correctly
- FastMCP version matches expected (2.12.4)

## Files to Create/Modify

### GitHub Actions Workflow

- `.github/workflows/mcp-validation.yml` - Main CI workflow
- Uses existing Docker build and test scripts
- Includes quality gates and artifact upload

### Enhanced Validation

- `scripts/validate_mcp_results.js` - JSON response validator
- `test_mcp_tools_ci.sh` - Enhanced tools testing with JSON output
- `test_mcp_resources_ci.sh` - Enhanced resources testing with JSON output

### Reporting

- Generate JSON test reports for debugging
- Create GitHub step summaries with key metrics
- Upload test artifacts on failure

## Quality Gates

### Required Validations (CI Fails If Missing)

- health_check returns status "healthy"
- Error responses follow standardized format
- Resource URIs parse without syntax errors
- FastMCP server initializes successfully

### Warning Validations (Log But Don't Fail)

- FastMCP version check
- Response time performance
- Database connection availability (expected to fail in CI)

## Benefits

### Development Workflow

- Catch bugs like the 3 we found (syntax, URI parsing, parameter passing) automatically
- Prevent deployment of broken MCP servers
- Validate error handling consistency across changes

### Quality Assurance

- Ensure MCP protocol compliance
- Validate exception serialization works correctly
- Maintain consistent error response format
- Performance regression detection

### Team Collaboration

- PR validation prevents broken code merges
- Clear test reports for debugging failures
- Automated validation reduces manual testing
- Documentation stays in sync with implementation

### To-dos

- [ ] Launch MCP Inspector and connect via stdio using run_server.py
- [ ] Validate health_check, search_library, get_audio_metadata in Inspector
- [ ] Fetch music-library resource URIs and verify response/error shapes
- [ ] Trigger not-found/validation errors and confirm standardized error format
- [ ] Add Inspector quickstart (stdio) section to README
- [ ] Add Inspector quickstart and validation checklist to docs/local-testing-mcp.md