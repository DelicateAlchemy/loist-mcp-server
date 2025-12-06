# LOI-13: Fix Postman Collection Session Management - Implementation Plan

**Linear Issue**: [LOI-13](https://linear.app/loist/issue/LOI-13/loi-12-fix-postman-collection-session-management-critical)  
**Priority**: Critical (Urgent)  
**Status**: Planning → Implementation

## Problem Statement

Postman collection's asynchronous MCP session initialization causes intermittent test failures. The root cause is that Postman's synchronous request execution conflicts with asynchronous JavaScript pre-request scripts. The auto-initialization script may not complete before the main request executes.

### Current Behavior

1. **Pre-request script** uses `pm.sendRequest()` (asynchronous) to initialize session
2. **Main request** executes immediately after pre-request script finishes
3. **Session ID callback** completes AFTER main request has already been sent
4. **Result**: Main request fails with "Missing session ID" or "RESOURCE_NOT_FOUND" errors

### Evidence

- Individual MCP tool requests may fail with session errors
- Collection uses asynchronous pre-request scripts for session initialization
- Manual intervention required for reliable testing
- Poor developer experience

## Solution Approach

### Strategy: Synchronous Session Initialization

Postman doesn't support truly synchronous HTTP requests, but we can use a **busy-wait pattern** to ensure session initialization completes before the main request executes.

### Implementation Steps

1. **Research Postman synchronous patterns** - Verify best approach for blocking until async completes
2. **Implement synchronous session initialization** - Use busy-wait or request blocking pattern
3. **Add session validation** - Check sessionId exists and is valid before proceeding
4. **Improve error messages** - Provide actionable guidance when session is missing
5. **Update documentation** - Document new approach and troubleshooting steps
6. **Test thoroughly** - Verify fixes work with individual requests and full collection runs
7. **Document Newman CLI alternative** - Provide automated testing option

## Technical Details

### Current Pre-Request Script Flow

```javascript
// Current (ASYNC - PROBLEMATIC):
if (!sessionId) {
    pm.sendRequest(initRequest, function(err, initResponse) {
        // This callback runs AFTER main request executes!
        pm.environment.set('sessionId', newSessionId);
    });
}
// Main request executes here - sessionId may not be set yet!
```

### Proposed Synchronous Flow

```javascript
// Proposed (SYNCHRONOUS - FIXED):
if (!sessionId) {
    let sessionReady = false;
    let sessionError = null;
    
    pm.sendRequest(initRequest, function(err, initResponse) {
        if (err) {
            sessionError = err;
            sessionReady = true;
            return;
        }
        const newSessionId = initResponse.headers.get('mcp-session-id');
        if (newSessionId) {
            pm.environment.set('sessionId', newSessionId);
            sessionReady = true;
        }
    });
    
    // Busy-wait until session is ready (with timeout)
    const maxWait = 5000; // 5 seconds
    const startTime = Date.now();
    while (!sessionReady && (Date.now() - startTime) < maxWait) {
        // Busy-wait
    }
    
    if (sessionError) {
        throw new Error('Session initialization failed: ' + sessionError);
    }
    if (!sessionReady) {
        throw new Error('Session initialization timeout');
    }
}
```

### Session Validation

Add validation checks before each MCP request:

```javascript
// Validate session exists
const sessionId = pm.environment.get('sessionId');
if (!sessionId) {
    throw new Error('MCP session not initialized. Run "Initialize MCP Session" request first.');
}

// Validate session age (optional - prevent stale sessions)
const sessionAge = Date.now() - new Date(pm.environment.get('sessionInitializedAt')).getTime();
if (sessionAge > 3600000) { // 1 hour
    console.warn('⚠️ Session is older than 1 hour - consider re-initializing');
}
```

## Testing Strategy

### Test Cases

1. **Individual MCP Tool Request** (without pre-initialization)
   - Expected: Session auto-initializes synchronously, request succeeds
   - Verify: No "Missing session ID" errors

2. **Multiple Sequential Requests**
   - Expected: First request initializes session, subsequent requests reuse it
   - Verify: Session persists across requests

3. **Full Collection Run**
   - Expected: All MCP requests succeed without manual intervention
   - Verify: No session-related failures

4. **Session Expiry Handling**
   - Expected: Clear error message when session is missing or expired
   - Verify: Actionable error messages guide user

5. **Newman CLI Testing**
   - Expected: Newman runs collection successfully
   - Verify: Automated testing works reliably

## Files to Modify

1. `loist-music-library-local.postman_collection.json`
   - Update collection-level pre-request script
   - Add session validation logic
   - Improve error handling

2. `POSTMAN_README.md`
   - Document new session management approach
   - Add troubleshooting section
   - Include Newman CLI instructions

3. `postman-test-issues-analysis.md`
   - Mark LOI-13 as resolved
   - Document solution approach

## Git Workflow

Following task branch workflow:

1. Create branch: `task-13` (or `loi-13` if Linear uses different naming)
2. One commit per logical change:
   - Commit 1: Research and document synchronous patterns
   - Commit 2: Implement synchronous session initialization
   - Commit 3: Add session validation checks
   - Commit 4: Improve error messages
   - Commit 5: Update documentation
   - Commit 6: Test and verify fixes
3. Push branch and create PR to `dev`

## Success Criteria

- ✅ Individual MCP tool requests work without manual session initialization
- ✅ Full collection runs succeed without session errors
- ✅ Clear error messages guide users when session issues occur
- ✅ Documentation updated with new approach
- ✅ Newman CLI alternative documented
- ✅ All tests pass consistently

## Risks & Mitigation

### Risk: Busy-wait may cause performance issues
- **Mitigation**: Use reasonable timeout (5 seconds), add clear error messages

### Risk: Postman may not support busy-wait pattern
- **Mitigation**: Research alternative approaches (request blocking, collection structure changes)

### Risk: Changes may break existing workflows
- **Mitigation**: Test thoroughly with both individual requests and full collection runs

## References

- [Linear Issue LOI-13](https://linear.app/loist/issue/LOI-13/loi-12-fix-postman-collection-session-management-critical)
- [Postman Test Issues Analysis](./postman-test-issues-analysis.md)
- [Postman README](./POSTMAN_README.md)
- [API Endpoint Testing Tracker](./api-endpoint-testing-tracker.md)

---

**Created**: 2025-12-06  
**Last Updated**: 2025-12-06  
**Status**: Planning Complete → Ready for Implementation

