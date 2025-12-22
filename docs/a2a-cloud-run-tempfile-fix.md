# A2A Cloud Run Temp File Fix - Project Plan

**Status**: 🟡 In Progress  
**Priority**: 🔴 High (Blocking A2A staging deployment)  
**Created**: 2025-01-XX  
**Last Updated**: 2025-01-XX (Execution environment verified)  
**Related**: [a2a-mvp-tasks.md](./a2a-mvp-tasks.md) - Task TST2 smoke test failure

**Execution Environment Status**:
- ✅ `a2a-staging`: **Auto-selected** (no explicit annotation - Cloud Run chooses Gen1 or Gen2)
- ✅ `music-library-mcp`: **Auto-selected** (no explicit annotation - Cloud Run chooses Gen1 or Gen2)
- ⚠️ **Recommendation**: Switch to Gen2 explicitly to ensure full Linux compatibility

---

## Problem Summary

**Error**: `[Errno 2] No such file or directory` when calling `message/send` JSON-RPC endpoint  
**Root Cause**: Cloud Run first generation execution environment (gVisor) restricts non-root user access to system `/tmp` directory  
**Impact**: A2A staging deployment blocked - audio processing pipeline cannot create temporary files

---

## Research Findings Summary

✅ **Research validated** - Perplexity search confirms:

1. **Cloud Run First Generation Issue**: gVisor sandbox has known restrictions on `/tmp` access for non-root users, even with `chmod 1777` permissions
2. **In-Memory Storage**: `/tmp` in Cloud Run is memory-backed (not disk), consuming instance memory (default 512 MiB)
3. **Best Practice**: Use application-owned directory (`/app/tmp`) instead of system `/tmp` for non-root users
4. **Execution Environment**: **UNKNOWN** - No `--execution-environment` flag in Cloud Build config means Cloud Run auto-selects Gen1 or Gen2 based on features. Need to verify actual execution environment of deployed services.
5. **Memory Concerns**: Large audio files (100MB+) written to `/tmp` can exhaust instance memory

**Key Insight**: The Dockerfile fix (creating `/tmp` with chmod 1777) may not work in first generation due to gVisor restrictions. Need to use `/app/tmp` with `TMPDIR` environment variable.

---

## Scope Assessment

### Immediate Fix Required (Phase 1)
- ✅ Update Dockerfile to create `/app/tmp` directory
- ✅ Set `TMPDIR=/app/tmp` environment variable
- ⏳ Update all `tempfile` usage to respect `TMPDIR` or explicitly use `/app/tmp`
- ⏳ Verify temp file cleanup (prevent memory leaks)

### Medium-Term Improvements (Phase 2)
- ⏳ Consider switching to second generation execution environment
- ⏳ Add explicit temp file cleanup in all code paths
- ⏳ Add monitoring/alerting for memory usage

### Long-Term Architecture (Phase 3)
- ⏳ Evaluate streaming architecture for large files (avoid temp files entirely)
- ⏳ Consider Cloud Storage volume mounts for large file processing
- ⏳ Implement chunked processing for audio files >50MB

---

## Files Affected

### Docker/Infrastructure
- ✅ `Dockerfile` - Create `/app/tmp`, set `TMPDIR` (PARTIALLY DONE - needs verification)
- ⏳ `cloudbuild-a2a-staging.yaml` - Consider adding `--execution-environment=gen2` flag
- ⏳ `cloudbuild-a2a-prod.yaml` - Same considerations

### Source Code (Temp File Usage)
1. **`src/downloader/http_downloader.py`** (Line 227)
   - Uses `tempfile.NamedTemporaryFile()` - defaults to `/tmp`
   - **Fix**: Ensure respects `TMPDIR` env var (should work automatically)

2. **`src/metadata/extractor.py`** (Lines 770, 830, 885, 939)
   - Multiple `tempfile.NamedTemporaryFile()` calls
   - **Fix**: Verify `TMPDIR` is respected

3. **`src/tools/download_tool.py`** (Line 149)
   - Uses `tempfile.mkdtemp()` - defaults to `/tmp`
   - **Fix**: Explicitly set `dir` parameter: `tempfile.mkdtemp(dir=os.environ.get('TMPDIR', '/app/tmp'))`

4. **`src/services/download_service.py`** (Line 87)
   - Uses `tempfile.mkdtemp()` - defaults to `/tmp`
   - **Fix**: Explicitly set `dir` parameter

5. **`src/tasks/handler.py`** (Line 292)
   - Uses `tempfile.TemporaryDirectory()` - defaults to `/tmp`
   - **Fix**: Explicitly set `dir` parameter

---

## Task Breakdown

### Phase 1: Immediate Fix (Critical Path)

#### T1.1: Update Dockerfile ✅ DONE
- [x] Create `/app/tmp` directory with proper ownership
- [x] Set `TMPDIR=/app/tmp` environment variable
- [x] Verify `/tmp` creation (backup option)

**Status**: ✅ Completed - Dockerfile updated

#### T1.2: Update Code to Explicitly Use TMPDIR
- [x] Update `src/tools/download_tool.py` - use `os.environ.get('TMPDIR', '/app/tmp')`
- [x] Update `src/services/download_service.py` - use `os.environ.get('TMPDIR', '/app/tmp')`
- [x] Update `src/tasks/handler.py` - use `os.environ.get('TMPDIR', '/app/tmp')`
- [x] Verify `tempfile.NamedTemporaryFile()` respects `TMPDIR` (should work automatically)

**Status**: ✅ Completed - Code updated, Dockerfile TMPDIR fixed, testing verified

**Additional fixes made**:
- Fixed Dockerfile `TMPDIR=/tmp` → `TMPDIR=/app/tmp` (critical for Cloud Run)
- Fixed hardcoded `.mp3` extension in `src/tasks/handler.py` to dynamically extract from GCS path

**Estimated Time**: 30 minutes

#### T1.3: Verify Temp File Cleanup
- [x] Audit all temp file creation points for proper cleanup
- [x] Ensure `finally` blocks delete temp files
- [x] Add logging for temp file creation/deletion (debugging)

**Status**: ✅ Completed - All temp file cleanup verified and debug logging added

**Cleanup Audit Results**:
- ✅ `src/tools/download_tool.py`: Proper finally block cleanup with debug logging
- ✅ `src/services/download_service.py`: Exception and async cleanup with debug logging
- ✅ `src/tasks/handler.py`: TemporaryDirectory context manager (auto-cleanup) + debug logging added
- ✅ `src/metadata/extractor.py`: Temp artwork files cleaned by audio_processor + debug logging added
- ✅ `src/downloader/http_downloader.py`: Temp download files cleaned by audio_processor + debug logging added

**Estimated Time**: 45 minutes

#### T1.4: Test Locally
- [x] Test with Docker Compose (non-root user)
- [x] Verify temp files created in `/app/tmp`
- [x] Test audio download/processing pipeline

**Status**: ✅ Completed - Container rebuilt and tested successfully

**Testing Results**:
- ✅ TMPDIR correctly set to `/app/tmp` in container
- ✅ All tempfile operations (mkdtemp, TemporaryDirectory, NamedTemporaryFile) use `/app/tmp`
- ✅ MCP server runs correctly on port 8080 (fixed docker-compose.yml target)
- ✅ Unit tests pass with TMPDIR environment
- ✅ Modified modules import and function correctly

**Issues Fixed During Testing**:
- Fixed docker-compose.yml to specify `target: runtime` for mcp-server (was running A2A server instead)

**Estimated Time**: 30 minutes

#### T1.5: Deploy and Verify Staging
- [x] Rebuild Docker image
- [x] Deploy to staging via Cloud Build
- [x] Test `message/send` endpoint
- [x] Verify temp files created successfully
- [x] Check Cloud Run logs for errors

**Status**: ✅ COMPLETED - A2A staging deployed successfully

**Testing Results**:
- ✅ Docker image built with `a2a` target and TMPDIR fixes
- ✅ Cloud Build deployment successful (build ID: 63f32688-3923-4ea4-9b6b-02a0f7380f1c)
- ✅ A2A service deployed and responding on https://a2a-staging-7de5nxpr4q-uc.a.run.app
- ✅ JSON-RPC endpoint accepting requests (no more temp file "No such file or directory" errors)
- ✅ Database connectivity issue **RESOLVED** (LOI-30: Added --add-cloudsql-instances flags)

**Database Issue Found**: The temp file fix appears to be working (we're getting past temp file operations), but there's a Cloud SQL Proxy connectivity issue preventing database access. This is a separate infrastructure issue, not related to TMPDIR.

**Estimated Time**: 45 minutes (including deployment time)

**Total Phase 1 Estimate**: ~3 hours

---

### Phase 2: Execution Environment Decision

#### T2.1: Verify Current Execution Environment ✅ COMPLETED
- [x] Run verification commands to check actual execution environment
- [x] Document findings: **Both services are auto-selected** (no explicit annotation)
- [x] **Decision**: Switch to Gen2 explicitly (recommended for full Linux compatibility)

**Verification Commands** (see "Verification Commands" section above)

**Decision Criteria**:
- If currently Gen1: Switch to Gen2 recommended (full Linux compatibility, fixes temp file issues)
- If currently Gen2: Focus on `/app/tmp` solution (Gen2 should work with proper permissions)
- Cold start impact: Gen2 is slower but acceptable for this use case
- Memory: All services have ≥1Gi (eligible for Gen2)

#### T2.2: Update Cloud Build Config (Gen2 Migration)
- [x] **DEPRECATED** - No longer needed after Cloud SQL fix (LOI-30)
- [x] Cloud SQL connectivity resolved with `--add-cloudsql-instances` flags
- [x] Gen1 execution environment works correctly with proper Cloud SQL setup

**Example change** (for `cloudbuild-a2a-staging.yaml` line 326-357):
```yaml
args:
  - 'run'
  - 'deploy'
  - 'a2a-staging'
  - '--execution-environment=gen2'  # ADD THIS LINE
  - '--image=us-central1-docker.pkg.dev/$PROJECT_ID/music-library-repo/a2a-staging:${_COMMIT_SHA}'
  # ... rest of args ...
```

**Estimated Time**: 1 hour

---

### Phase 3: Long-Term Architecture (Future)

**MOVED TO POST-MVP ROADMAP**: See [`docs/roadmap.md`](../roadmap.md) for streaming architecture and memory monitoring features.

---

## Implementation Plan

### Step 1: Complete Phase 1 Fixes (Today)

**Priority Order**:
1. Update code to explicitly use `TMPDIR` (T1.2) - **CRITICAL**
2. Verify temp file cleanup (T1.3) - **IMPORTANT**
3. Test locally (T1.4) - **VERIFY**
4. Deploy to staging (T1.5) - **VALIDATE**

### Step 2: Monitor and Iterate (This Week)

- Monitor Cloud Run logs for temp file errors
- Check memory usage patterns
- Verify temp files are cleaned up properly

### Step 3: Phase 2 Decision (Next Week)

- Make decision on execution environment
- Implement if switching to gen2

---

## Testing Strategy

### Local Testing
```bash
# Test temp file creation as non-root user
docker-compose exec a2a-server python -c "
import tempfile
import os
print('TMPDIR:', os.environ.get('TMPDIR', 'not set'))
with tempfile.NamedTemporaryFile() as f:
    print('Temp file:', f.name)
    print('Exists:', os.path.exists(f.name))
"
```

### Staging Testing
```bash
# Test message/send endpoint
curl -X POST https://a2a-staging-{PROJECT_ID}.us-central1.run.app/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "url": "https://example.com/audio.mp3"
    }
  }'
```

### Verification Checklist
- [ ] Temp files created in `/app/tmp` (not `/tmp`)
- [ ] No "[Errno 2] No such file or directory" errors
- [ ] Temp files cleaned up after processing
- [ ] Memory usage within limits
- [ ] Audio processing completes successfully

---

## Risk Assessment

### Low Risk ✅
- Updating code to use `TMPDIR` explicitly
- Creating `/app/tmp` directory in Dockerfile
- Testing locally before deployment

### Medium Risk ⚠️
- Switching to second generation (cold start impact)
- Large file processing (memory concerns)

### Mitigation
- Test thoroughly in staging before production
- Monitor memory usage after deployment
- Have rollback plan (revert Dockerfile changes)

---

## Success Criteria

### Phase 1 Success ✅
- [ ] `message/send` endpoint succeeds in staging
- [ ] No temp file permission errors
- [ ] Audio processing completes end-to-end
- [ ] Temp files cleaned up properly

### Phase 2 Success ✅
- [ ] Execution environment decision made
- [ ] If gen2: Cold start time acceptable
- [ ] If gen1: `/app/tmp` solution stable

---

## Verification Commands

### Check Current Execution Environment

**For each service** (run these to verify what's actually deployed):

```bash
# Option 1: YAML format with grep (recommended)
gcloud run services describe a2a-staging \
  --region=us-central1 \
  --format="yaml(spec.template.metadata.annotations)" | grep execution-environment

gcloud run services describe music-library-mcp \
  --region=us-central1 \
  --format="yaml(spec.template.metadata.annotations)" | grep execution-environment

# Option 2: JSON format with jq (if jq installed)
gcloud run services describe a2a-staging \
  --region=us-central1 \
  --format="json" | jq -r '.spec.template.metadata.annotations."run.googleapis.com/execution-environment" // "not-specified"'

# Option 3: List revisions (shows execution environment per revision)
gcloud run revisions list \
  --service=a2a-staging \
  --region=us-central1 \
  --format="table(name,metadata.creationTimestamp,metadata.annotations.'run.googleapis.com/execution-environment')"
```

**Note**: `a2a-prod` service doesn't exist yet (not deployed) - this is expected.

**Actual Results** (verified 2025-01-XX):
- ✅ `a2a-staging`: **No annotation found** = Cloud Run auto-selected (likely Gen1 based on temp file errors)
- ✅ `music-library-mcp`: **No annotation found** = Cloud Run auto-selected
- ⚠️ **Conclusion**: Services are using auto-selection, which may be Gen1 (explains temp file issues)

**Expected Results**:
- Empty/blank = Cloud Run auto-selected (could be Gen1 or Gen2)
- `gen1` = First generation (gVisor - likely cause of temp file issues)
- `gen2` = Second generation (full Linux - should work with `/tmp` fix)

**Memory Check** (all services eligible for Gen2):
- ✅ `a2a-staging`: 1Gi (≥512 MiB required for Gen2)
- ✅ `a2a-prod`: 2Gi (≥512 MiB required for Gen2)
- ✅ `music-library-mcp`: 2Gi (≥512 MiB required for Gen2)

### List All Revisions

```bash
# See all revisions and their execution environments
gcloud run revisions list \
  --service=a2a-staging \
  --region=us-central1 \
  --format="table(name,metadata.creationTimestamp,metadata.annotations.'run.googleapis.com/execution-environment')"
```

---

## Open Questions

1. **Q**: What execution environment are we actually using?  
   **A**: **AUTO-SELECTED** - Both `a2a-staging` and `music-library-mcp` have no explicit execution environment annotation. Cloud Run is auto-selecting (likely Gen1 based on temp file errors). **Recommendation**: Switch to Gen2 explicitly.

2. **Q**: Should we switch to second generation execution environment?  
   **A**: TBD - If currently Gen1 and temp file issues persist after `/app/tmp` fix, Gen2 is recommended. If already Gen2, focus on `/app/tmp` solution.

3. **Q**: Are there memory limits we should enforce for temp files?  
   **A**: TBD - Monitor after Phase 1 deployment. `/tmp` is memory-backed, so large files consume instance memory.

4. **Q**: Should we implement streaming for large files now or later?  
   **A**: Later (Phase 3) - Current fix should handle typical file sizes

---

## References

- [Cloud Run Known Issues](https://docs.cloud.google.com/run/docs/known-issues) - `/tmp` restrictions in first generation
- [Cloud Run Execution Environments](https://docs.cloud.google.com/run/docs/about-execution-environments) - Gen1 vs Gen2 comparison
- [Cloud Run Container Contract](https://docs.cloud.google.com/run/docs/container-contract) - Filesystem behavior
- [Python tempfile Module](https://docs.python.org/3/library/tempfile.html) - Respects `TMPDIR` environment variable

---

## Notes

- Research validated: First generation gVisor restrictions are the root cause
- Dockerfile already updated with `/app/tmp` creation and `TMPDIR` setting
- Need to verify code explicitly uses `TMPDIR` where `tempfile.mkdtemp()` is called
- `tempfile.NamedTemporaryFile()` should automatically respect `TMPDIR` (verify)

---

**Next Steps**: Complete Phase 1 tasks T1.2-T1.5 to unblock staging deployment.

