# LOI-15: Fix Metadata Duration Field - Task Tracking

**Linear Issue**: [LOI-15](https://linear.app/loist/issue/LOI-15/loi-15-fix-metadata-duration-field-medium)  
**Status**: Done ✅  
**Priority**: Medium
**Created**: 2025-12-08
**Completed**: 2025-12-08
**Merged to Dev**: 2025-12-08
**Linear Issue Closed**: 2025-12-08

---

## 🎯 Project Goal

Fix metadata duration field returning `null` by correcting field name mismatches in audio processing pipeline and MCP resource handlers. Ensure duration is properly stored during audio processing and correctly returned via all API endpoints.

---

## 📊 Current State Analysis

### Root Causes Identified

#### 1. 🔴 Primary Issue: Duration Not Stored During Processing
- **Location**: `src/tools/process_audio.py:539`
- **Problem**: Process audio tool passes `"duration"` to database function, but database expects `"duration_seconds"`
- **Current Behavior**: Duration never gets saved to database (all tracks show `duration_seconds: None`)
- **Evidence**: Database query confirmed all existing tracks have `duration_seconds: None`

#### 2. 🟡 Secondary Issue: MCP Resource Handler Field Mismatch
- **Location**: `src/resources/metadata.py:78`
- **Problem**: MCP resources look for `"duration"` but database returns `"duration_seconds"`
- **Current Behavior**: MCP API returns `null` for duration in metadata resources
- **Impact**: MCP clients cannot access duration information

#### 3. ✅ Service Layer: Working Correctly
- **Location**: `src/services/audio_service.py:59`
- **Status**: Has fallback logic `get("duration") or get("duration_seconds")`
- **Result**: HTTP API works correctly via service layer

### Field Name Mapping

| Component | Field Name Used | Status |
|-----------|----------------|--------|
| **Database Schema** | `duration_seconds` | ✅ Correct |
| **Metadata Extractor** | `"duration"` | ✅ Correct (Mutagen convention) |
| **Process Audio Tool** | `"duration"` → database | ❌ Wrong |
| **Service Layer** | Both (fallback) | ✅ Compatible |
| **HTTP API** | Via service layer | ✅ Works |
| **MCP Resources** | `"duration"` from raw DB | ❌ Wrong |

---

## 📋 Task List

### Phase 1: Git Setup & Branch Creation

- [STATUS: todo] **D1.1**: Create feature branch from `dev`
  - **Command**: `git checkout dev && git pull origin dev && git checkout -b task/loi-15-fix-duration-field`
  - **Rationale**: Follow project git workflow (task branches from dev)
  - **Verification**: Confirm branch created and on latest dev

### Phase 2: Fix Duration Storage (Primary Fix)

- [STATUS: todo] **D2.1**: Fix field name in process_audio.py
  - **Location**: `src/tools/process_audio.py:539`
  - **Change**: `"duration": metadata_dict.get("duration", 0)` → `"duration_seconds": metadata_dict.get("duration", 0)`
  - **Rationale**: Database expects `duration_seconds`, not `duration`
  - **Impact**: New audio files will have duration stored correctly

- [STATUS: todo] **D2.2**: Commit Phase 2 changes
  - **Commit Message**: 
    ```
    fix(metadata): correct duration field name in audio processing (Task LOI-15.2)
    
    - Change "duration" to "duration_seconds" in process_audio.py
    - Ensures duration is stored in database during audio processing
    - Files: src/tools/process_audio.py
    ```
  - **Command**: `git add src/tools/process_audio.py && git commit -m "..."`

### Phase 3: Fix MCP Resource Handler (Secondary Fix)

- [STATUS: todo] **D3.1**: Fix field name in metadata resource handler
  - **Location**: `src/resources/metadata.py:78`
  - **Change**: `metadata.get("duration", 0.0)` → `metadata.get("duration_seconds", 0.0)`
  - **Rationale**: Database returns `duration_seconds`, not `duration`
  - **Impact**: MCP resources will return correct duration values

- [STATUS: todo] **D3.2**: Commit Phase 3 changes
  - **Commit Message**:
    ```
    fix(mcp-resources): correct duration field name in metadata resource (Task LOI-15.3)
    
    - Change "duration" to "duration_seconds" in metadata resource handler
    - Ensures MCP resources return correct duration values
    - Files: src/resources/metadata.py
    ```

### Phase 4: Testing & Validation

- [STATUS: todo] **D4.1**: Test new audio processing with duration storage
  - **Steps**:
    1. Process a new audio file via MCP tool `process_audio_complete`
    2. Query database: `SELECT duration_seconds FROM audio_tracks WHERE id = '<new_track_id>'`
    3. Verify `duration_seconds` is NOT NULL and has correct value
  - **Expected**: Duration stored correctly in database

- [STATUS: todo] **D4.2**: Test HTTP API returns duration correctly
  - **Steps**:
    1. Call `GET /api/tracks/{audioId}` for newly processed track
    2. Verify `metadata.format.duration` is numeric (not null)
    3. Verify duration matches expected value
  - **Expected**: HTTP API returns duration correctly

- [STATUS: todo] **D4.3**: Test MCP resources return duration correctly
  - **Steps**:
    1. Call MCP resource `music-library://audio/{audioId}/metadata`
    2. Verify `Format.Duration` is numeric (not null)
    3. Verify duration matches expected value
  - **Expected**: MCP resources return duration correctly

- [STATUS: todo] **D4.4**: Verify no regression in existing functionality
  - **Steps**:
    1. Test HTTP API with existing tracks (should still work via service layer fallback)
    2. Test MCP tools still work correctly
    3. Verify no errors in logs
  - **Expected**: All existing functionality continues to work

- [STATUS: todo] **D4.5**: Run existing test suite
  - **Command**: `pytest tests/ -v`
  - **Expected**: All tests pass (no regressions)

### Phase 5: Documentation & Cleanup

- [STATUS: todo] **D5.1**: Update API testing tracker if needed
  - **File**: `docs/api-endpoint-testing-tracker.md`
  - **Action**: Remove note about `metadata.format.duration` being null (LOI-14)
  - **Rationale**: Issue is now fixed

- [STATUS: todo] **D5.2**: Update postman-test-issues-analysis.md if needed
  - **File**: `docs/postman-test-issues-analysis.md`
  - **Action**: Mark LOI-14/LOI-15 as resolved
  - **Rationale**: Document fix completion

- [STATUS: todo] **D5.3**: Commit documentation updates
  - **Commit Message**:
    ```
    docs: update duration field fix documentation (Task LOI-15.5)
    
    - Remove LOI-14 note from api-endpoint-testing-tracker.md
    - Mark duration field issue as resolved
    - Files: docs/api-endpoint-testing-tracker.md, docs/postman-test-issues-analysis.md
    ```

### Phase 6: Git Workflow Completion

- [STATUS: todo] **D6.1**: Push branch to remote
  - **Command**: `git push origin task/loi-15-fix-duration-field`
  - **Rationale**: Backup work and enable code review

- [STATUS: todo] **D6.2**: Create pull request (if applicable)
  - **Base**: `dev`
  - **Title**: `fix(metadata): Fix duration field storage and retrieval (LOI-15)`
  - **Description**: Reference Linear issue and summarize changes

- [STATUS: todo] **D6.3**: Update Linear issue status
  - **Action**: Mark LOI-15 as "In Progress" → "Done" after PR merge
  - **Comment**: Add summary of changes and test results

---

## 🔍 Implementation Details

### Code Changes Summary

#### Change 1: Process Audio Tool
```python
# src/tools/process_audio.py:539
# BEFORE:
"duration": metadata_dict.get("duration", 0),

# AFTER:
"duration_seconds": metadata_dict.get("duration", 0),
```

#### Change 2: MCP Resource Handler
```python
# src/resources/metadata.py:78
# BEFORE:
"Duration": metadata.get("duration", 0.0),

# AFTER:
"Duration": metadata.get("duration_seconds", 0.0),
```

### Testing Commands Reference

```bash
# Test new audio processing
# (Use MCP tool or HTTP API to process audio file)

# Verify duration in database
docker-compose exec mcp-server python3 -c "
from database import get_connection
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT id, duration_seconds FROM audio_tracks WHERE id = %s', ('<track_id>',))
        result = cur.fetchone()
        print(f'Duration: {result[1]}')
"

# Test HTTP API
curl -v "http://localhost:8080/api/tracks/<track_id>" | jq '.metadata.format.duration'

# Test MCP Resource (via MCP client)
# Call: music-library://audio/<track_id>/metadata
# Verify: Format.Duration is numeric
```

---

## ✅ Completion Checklist

- [ ] All Phase 1 tasks complete (git setup)
- [ ] All Phase 2 tasks complete (fix duration storage)
- [ ] All Phase 3 tasks complete (fix MCP resources)
- [ ] All Phase 4 tasks complete (testing)
- [ ] All Phase 5 tasks complete (documentation)
- [ ] All Phase 6 tasks complete (git workflow)
- [ ] New audio files store duration correctly
- [ ] HTTP API returns duration correctly
- [ ] MCP resources return duration correctly
- [ ] No regression in existing functionality
- [ ] All tests pass
- [ ] Linear issue updated and marked complete

---

## 🔄 Rolling Summary

**2025-12-08**: Task tracking file created. Root causes identified:
- Primary: Field name mismatch in `process_audio.py` (duration → duration_seconds)
- Secondary: Field name mismatch in `metadata.py` resource handler
- Solution: Two one-line fixes to correct field names

**Next Steps**: Create branch, implement fixes, test thoroughly, update documentation.

---

## 📚 Related Files

- `src/tools/process_audio.py` - Audio processing pipeline (fix location)
- `src/resources/metadata.py` - MCP resource handler (fix location)
- `src/services/audio_service.py` - Service layer (already has fallback, no changes needed)
- `database/operations.py` - Database operations (expects `duration_seconds`, correct)
- `docs/api-endpoint-testing-tracker.md` - API testing documentation (update needed)
- `docs/postman-test-issues-analysis.md` - Postman test issues (update needed)

---

## 🚨 Notes & Considerations

### Existing Data
- **Note**: All existing tracks have `duration_seconds: None`
- **Impact**: Existing tracks will continue to show null duration until reprocessed
- **Future Work**: Consider data backfill script to reprocess existing audio files (separate task)

### Backward Compatibility
- **Service Layer**: Already handles both field names via fallback logic
- **HTTP API**: No changes needed (uses service layer)
- **Risk**: Low - changes are field name corrections only

### Testing Priority
1. **Critical**: New audio processing stores duration
2. **High**: MCP resources return duration correctly
3. **Medium**: HTTP API continues to work (should already work)
4. **Low**: Existing tracks (will remain null until reprocessed)

