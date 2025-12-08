# LOI-7: Downloads - Preserve Original Filenames for Downloads

**Linear Issue**: [LOI-7](https://linear.app/loist/issue/LOI-7/downloads)
**Status**: 🔄 **IN PROGRESS**
**Created**: 2025-12-08
**Last Updated**: 2025-12-08
**Priority**: Medium
**Git Branch**: `task/loi-7-download-filename-improvement`

---

## Problem Summary

Downloaded audio files get generic names like `Unknown - Unknown Artist.mp3` instead of preserving the original filename from when the file was ingested.

### Root Cause Analysis

| Stage | What Happens | Issue |
|-------|--------------|-------|
| **Ingestion** | Filename captured from `source.filename` or URL | ✅ Works |
| **GCS Upload** | File stored at `audio/{id}/{filename}` | ✅ Filename in path |
| **Database Save** | Only `audio_gcs_path` stored | ❌ Filename not stored separately |
| **Download** | `_generate_download_filename()` uses title/artist from DB | ❌ Original filename lost |

### Current Flow

```
Ingestion:
User Upload → source.filename captured → GCS: audio/{id}/{filename} → DB: only stores GCS path

Download:
Request → get_audio_metadata_by_id() → _generate_download_filename(title, artist) → "{title} - {artist}.mp3"
```

### Desired Flow

```
Ingestion:
User Upload → source.filename captured → GCS: audio/{id}/{filename} → DB: stores original_filename

Download:
Request → get_audio_metadata_by_id() → original_filename from DB → use original or fallback to metadata
```

---

## Codebase Analysis

### Key Files Identified

| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `src/tools/process_audio.py` | Ingestion orchestration | 426-457 (filename extraction), 498-506 (GCS upload) |
| `src/tools/download_tool.py` | Download tool | 343-386 (`_generate_download_filename()`) |
| `database/operations.py` | DB operations | 166-177 (INSERT), 579-619 (get_audio_metadata_by_id) |
| `database/migrations/001_initial_schema.sql` | Schema definition | No `original_filename` column |
| `src/tools/schemas.py` | Input validation | 71-75 (`filename` field exists) |

### Filename Capture Logic (process_audio.py:426-457)

Current implementation already captures filenames with priority order:
1. `source.filename` (explicit API parameter) - **highest priority**
2. URL path extraction - **fallback**
3. `{audio_id}.{format}` - **last resort**

**Good news**: The capture logic exists, just not persisted to DB.

### Download Filename Generation (download_tool.py:343-386)

```python
def _generate_download_filename(metadata: Dict[str, Any], target_format: str) -> str:
    title = str(metadata.get('title') or '').strip() or 'Unknown'
    artist = str(metadata.get('artist') or '').strip() or 'Unknown Artist'
    # ... sanitization ...
    filename = f"{title} - {artist}.{ext}"
    return filename
```

**Problem**: Completely ignores original filename, even if available.

---

## Implementation Plan

### Phase 1: Database Migration
Add `original_filename` column to `audio_tracks` table.

### Phase 2: Ingestion Update
Store captured filename in database during processing.

### Phase 3: Download Update
Update `_generate_download_filename()` to prefer original filename with fallback.

### Phase 4: Testing & Verification
Test with new uploads, existing data, and edge cases.

---

## Task List

### Phase 1: Database Migration

#### T1.1: Create Database Migration
**Status**: todo
**Description**: Add `original_filename` column to audio_tracks table

**Tasks**:
- [ ] Create `007_add_original_filename.sql` migration file
- [ ] Add `original_filename VARCHAR(500)` column (nullable for existing data)
- [ ] Add comment documenting the column purpose
- [ ] No index needed (not searchable)

**Migration SQL**:
```sql
-- 007_add_original_filename.sql
-- Add original_filename column for download filename preservation
BEGIN;

ALTER TABLE audio_tracks ADD COLUMN original_filename VARCHAR(500);

COMMENT ON COLUMN audio_tracks.original_filename IS 'Original filename from source.filename or URL extraction, used for download filenames';

COMMIT;
```

**Testing**:
- [ ] Apply migration to local database: `docker-compose exec postgres psql -U postgres -d loist_dev -f /path/to/migration.sql`
- [ ] Verify column exists: `\d audio_tracks`
- [ ] Verify existing rows have NULL for original_filename

**Git Commit**:
```
feat(database): add original_filename column for download filenames (LOI-7 T1.1)

- Add 007_add_original_filename.sql migration
- Add nullable VARCHAR(500) column for backward compatibility
- Files: database/migrations/007_add_original_filename.sql
```

---

#### T1.2: Update Database Operations - Insert
**Status**: todo
**Description**: Update save_audio_metadata to include original_filename

**Files to Modify**:
- `database/operations.py`

**Changes Required**:
1. Add `original_filename` to INSERT query columns (line ~167)
2. Add `original_filename` to VALUES placeholders (line ~172)
3. Add `original_filename` to RETURNING clause (line ~179)
4. Add validation in docstring
5. Update batch insert function similarly (line ~411-433)

**Testing**:
- [ ] Unit test: save_audio_metadata with original_filename
- [ ] Unit test: save_audio_metadata without original_filename (NULL)
- [ ] Integration test: full pipeline with filename preservation

**Git Commit**:
```
feat(database): include original_filename in save operations (LOI-7 T1.2)

- Update save_audio_metadata to accept/store original_filename
- Update save_audio_metadata_batch for batch operations
- Add original_filename to RETURNING clause
- Files: database/operations.py
```

---

#### T1.3: Update Database Operations - Retrieve
**Status**: todo
**Description**: Update get_audio_metadata_by_id to return original_filename

**Files to Modify**:
- `database/operations.py`

**Changes Required**:
1. Add `original_filename` to SELECT query in get_audio_metadata_by_id (line ~620)
2. Add `original_filename` to SELECT query in get_audio_metadata_by_ids (line ~654)
3. Update docstrings to document the field

**Testing**:
- [ ] Unit test: verify original_filename in returned dict
- [ ] Integration test: retrieve record with original_filename

**Git Commit**:
```
feat(database): include original_filename in retrieval operations (LOI-7 T1.3)

- Add original_filename to get_audio_metadata_by_id SELECT
- Add original_filename to get_audio_metadata_by_ids SELECT
- Update docstrings
- Files: database/operations.py
```

---

### Phase 2: Ingestion Update

#### T2.1: Update Process Audio to Store Filename
**Status**: todo
**Description**: Modify process_audio_complete to store original_filename in database

**Files to Modify**:
- `src/tools/process_audio.py`

**Changes Required**:
1. Extract final filename used for GCS (after priority logic at lines 426-457)
2. Store in a variable that persists to database save
3. Pass to save_audio_metadata call (line ~551-556)
4. Add `original_filename` to `db_metadata` dict

**Filename Priority Logic** (already exists, just need to capture):
```python
# Priority 1: source.filename (explicit)
# Priority 2: URL extraction
# Priority 3: temp file path (fallback)
filename = source.filename or _extract_filename_from_url(source.url) or f"{audio_id}.{format}"
```

**Testing**:
- [ ] Integration test: ingest with source.filename → verify stored
- [ ] Integration test: ingest with URL only → verify extracted filename stored
- [ ] Integration test: ingest with neither → verify fallback stored

**Git Commit**:
```
feat(ingestion): store original_filename during audio processing (LOI-7 T2.1)

- Capture filename from source.filename or URL extraction
- Store in database via save_audio_metadata
- Maintain backward compatibility with existing data
- Files: src/tools/process_audio.py
```

---

### Phase 3: Download Update

#### T3.1: Update Download Filename Generation
**Status**: todo
**Description**: Modify _generate_download_filename to prefer original_filename

**Files to Modify**:
- `src/tools/download_tool.py`

**Changes Required**:
1. Check for `original_filename` in metadata dict first
2. If present and valid, use it (with format extension override if needed)
3. If not present, fall back to current title/artist generation
4. Ensure filename sanitization still applies

**New Logic**:
```python
def _generate_download_filename(metadata: Dict[str, Any], target_format: str) -> str:
    """
    Generate a safe filename for download from track metadata.
    
    Priority:
    1. original_filename (if stored during ingestion)
    2. Synthesized from title/artist metadata (fallback)
    """
    ext = target_format if target_format != 'aac' else 'm4a'
    
    # Priority 1: Original filename
    original_filename = metadata.get('original_filename')
    if original_filename:
        # Extract stem (without extension) and add target format extension
        stem = Path(original_filename).stem
        sanitized_stem = _sanitize_filename_component(stem)
        if sanitized_stem:
            return f"{sanitized_stem}.{ext}"
    
    # Priority 2: Fallback to title/artist
    title = str(metadata.get('title') or '').strip() or 'Unknown'
    artist = str(metadata.get('artist') or '').strip() or 'Unknown Artist'
    # ... existing sanitization ...
    return f"{title} - {artist}.{ext}"
```

**Testing**:
- [ ] Unit test: with original_filename → uses it
- [ ] Unit test: without original_filename → falls back to title/artist
- [ ] Unit test: with invalid original_filename (empty, whitespace) → falls back
- [ ] Unit test: format conversion changes extension correctly
- [ ] Integration test: download after ingest preserves filename

**Git Commit**:
```
feat(download): prefer original_filename for download filenames (LOI-7 T3.1)

- Update _generate_download_filename to check original_filename first
- Fall back to title/artist synthesis if not available
- Handle format conversion (change extension for target format)
- Files: src/tools/download_tool.py
```

---

#### T3.2: Add Filename Sanitization Helper
**Status**: todo
**Description**: Extract filename sanitization into reusable helper

**Files to Modify**:
- `src/tools/download_tool.py`

**Changes Required**:
1. Create `_sanitize_filename_component()` helper function
2. Handle unsafe characters: `<>:"/\|?*`
3. Handle length limits (100 chars for title, 50 for artist)
4. Handle empty/whitespace-only strings
5. Use in both original filename path and fallback path

**Testing**:
- [ ] Unit test: various unsafe characters replaced
- [ ] Unit test: length truncation works
- [ ] Unit test: empty string returns None/empty
- [ ] Unit test: Unicode characters preserved (international filenames)

**Git Commit**:
```
refactor(download): extract filename sanitization helper (LOI-7 T3.2)

- Create _sanitize_filename_component helper
- Handle unsafe characters and length limits
- Reuse for both original filename and fallback paths
- Files: src/tools/download_tool.py
```

---

### Phase 4: Testing & Verification

#### T4.1: Add Unit Tests for Filename Preservation
**Status**: todo
**Description**: Add comprehensive unit tests for the new filename logic

**Files to Create/Modify**:
- `tests/unit/test_download_filename.py` (new)
- `tests/unit/test_process_audio_filename.py` (new or extend existing)

**Test Cases**:
1. `_generate_download_filename` with original_filename
2. `_generate_download_filename` without original_filename (fallback)
3. `_generate_download_filename` with empty original_filename
4. `_generate_download_filename` with format conversion
5. `_sanitize_filename_component` edge cases
6. Filename extraction from various URL patterns
7. Database round-trip: save → retrieve → download filename

**Git Commit**:
```
test(download): add unit tests for filename preservation (LOI-7 T4.1)

- Test _generate_download_filename with original_filename
- Test fallback to title/artist
- Test sanitization edge cases
- Files: tests/unit/test_download_filename.py
```

---

#### T4.2: Add Integration Test for Full Pipeline
**Status**: todo
**Description**: End-to-end test from ingestion to download with filename verification

**Files to Create/Modify**:
- `tests/integration/downloads/test_filename_preservation.py` (new)

**Test Scenarios**:
1. Ingest with explicit `source.filename` → Download → Verify filename matches
2. Ingest with URL only → Download → Verify URL filename preserved
3. Ingest with neither → Download → Verify fallback to metadata
4. Convert format during download → Verify extension changes correctly

**Git Commit**:
```
test(integration): add filename preservation integration test (LOI-7 T4.2)

- End-to-end test for filename preservation
- Test source.filename, URL extraction, and fallback scenarios
- Test format conversion
- Files: tests/integration/downloads/test_filename_preservation.py
```

---

#### T4.3: Handle Existing Data Migration (Optional)
**Status**: todo
**Description**: Consider backfilling original_filename for existing records

**Options**:
1. **Do nothing**: Existing records use fallback (title/artist) - **Recommended for MVP**
2. **Parse from GCS path**: Extract filename from `audio_gcs_path` (brittle)
3. **Manual backfill**: Update specific high-value tracks manually

**Decision**: Start with option 1 (do nothing). New uploads will have filename, existing use fallback.

**Testing**:
- [ ] Verify existing records download with title/artist filename (no regression)
- [ ] Verify new records download with original filename

**Git Commit** (if implementing backfill):
```
feat(database): backfill original_filename from GCS paths (LOI-7 T4.3)

- Extract filename from audio_gcs_path for existing records
- Only update records where original_filename is NULL
- Files: scripts/backfill_original_filename.py
```

---

## Open Questions

### Resolved

1. **Q: Should we prefer original filename over metadata-based names?**
   - **A**: Yes. Priority: `original_filename` → `{title} - {artist}.{ext}` → `Unknown - Unknown Artist.{ext}`

2. **Q: How to handle format conversion?**
   - **A**: Keep original filename stem, replace extension with target format (e.g., `song.wav` → `song.mp3`)

3. **Q: Database migration required?**
   - **A**: Yes. Add `original_filename VARCHAR(500)` column.

4. **Q: Handle existing records without filename?**
   - **A**: Graceful fallback to current behavior (title/artist). No backfill for MVP.

### Open

1. **Q: Should we parse filename from GCS path as fallback?**
   - **A**: TBD. Could be useful for existing data but adds complexity. Consider for Phase 2.

2. **Q: Maximum filename length?**
   - **A**: Use 500 chars to match other VARCHAR fields. Truncate if necessary.

---

## Success Criteria

- [ ] New uploads store `original_filename` in database
- [ ] Downloads use `original_filename` when available
- [ ] Downloads fall back to title/artist when `original_filename` is NULL
- [ ] Format conversion changes extension correctly
- [ ] Existing data continues to work (no regression)
- [ ] All tests pass

---

## Files Reference

### To Modify
- `database/migrations/007_add_original_filename.sql` (new)
- `database/operations.py`
- `src/tools/process_audio.py`
- `src/tools/download_tool.py`

### To Create
- `tests/unit/test_download_filename.py`
- `tests/integration/downloads/test_filename_preservation.py`

### Related Documentation
- `docs/download-endpoint-api.md`
- `docs/download-endpoint-investigation.md`

---

## Notes

- **MVP Scope**: Focus on forward-looking fix (new uploads). Backfill existing data is optional.
- **No breaking changes**: Existing downloads continue to work with fallback behavior.
- **Unicode support**: Preserve international characters in filenames.
- **Security**: Continue using filename sanitization to prevent path traversal.
- Follow git workflow: Create `task/loi-7-download-filename-improvement` branch from `dev`.

---

## Summary

| Task | Description | Status | Dependencies |
|------|-------------|--------|--------------|
| T1.1 | Create database migration | todo | None |
| T1.2 | Update DB operations - Insert | todo | T1.1 |
| T1.3 | Update DB operations - Retrieve | todo | T1.1 |
| T2.1 | Update ingestion to store filename | todo | T1.2 |
| T3.1 | Update download filename generation | todo | T1.3 |
| T3.2 | Add filename sanitization helper | todo | None |
| T4.1 | Add unit tests | todo | T3.1 |
| T4.2 | Add integration test | todo | T2.1, T3.1 |
| T4.3 | Handle existing data (optional) | todo | T3.1 |

