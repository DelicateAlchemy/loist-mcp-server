# LOI-7: Update Filename API Implementation

**Linear Issue**: [LOI-7 Downloads](https://linear.app/loist/issue/LOI-7/downloads)  
**Created**: 2025-12-09  
**Status**: ✅ COMPLETED

**Implementation Summary:**
- ✅ Added `original_filename` field to `TrackMetadataUpdate` schema
- ✅ Added `original_filename` to database `allowed_fields` whitelist  
- ✅ Updated MCP tool docstring to include `original_filename`
- ✅ Tested end-to-end: update → database → download filename generation
- ✅ All changes lint-free and functional  

---

## Executive Summary

This document tracks the implementation of an "Update Filename" API endpoint that allows users to modify the `original_filename` field for audio tracks. This enables users to correct or customize download filenames after ingestion.

---

## Current State Analysis ✅

### What's Already Implemented (LOI-7 Core Work - DONE)

1. **Database Column**: `original_filename VARCHAR(500)` exists in `audio_tracks` table
   - Added via `database/migrations/007_add_original_filename.sql`
   - Verified present in local database ✅

2. **Ingestion Captures Filename**: `src/tools/process_audio.py` lines 473-485
   - Captures from `source.filename` parameter
   - Extracts from URL path
   - Stores in database during save

3. **Download Uses Filename**: `src/tools/download_tool.py` lines 376-425
   - `_generate_download_filename()` prioritizes `original_filename`
   - Falls back to `title - artist.ext` if not available

4. **Database Operations Support It**: `database/operations.py`
   - `save_audio_metadata()` stores `original_filename`
   - `get_audio_metadata_by_id()` returns `original_filename`

### What's NOT Implemented (This Task)

1. **`original_filename` is NOT in the updatable fields whitelist**
   - `database/operations.py:2735-2738` only allows:
     ```python
     allowed_fields = {
         'artist', 'title', 'album', 'genre', 'year',
         'composer', 'publisher', 'record_label', 'isrc'
     }
     ```
   - `original_filename` is intentionally omitted

2. **`update_metadata` MCP tool doesn't support filename**
   - `src/tools/update_schemas.py` `TrackMetadataUpdate` class has no `original_filename` field
   - MCP tool docstring lists editable fields, filename not included

3. **No HTTP API for filename updates**
   - `src/http_api.py` has no PATCH/PUT endpoint for metadata updates
   - All current endpoints are GET or DELETE only

---

## Implementation Decision: Extend Existing vs New Endpoint?

### Option A: Extend `update_metadata` (Recommended)

**Approach**: Add `original_filename` to existing update_metadata tool/API

**Pros**:
- Consistent with existing JSON Merge Patch pattern
- Single endpoint for all metadata updates
- Less code duplication
- Users already familiar with update_metadata

**Cons**:
- Filename is conceptually different from metadata (it's a storage property)
- May confuse users expecting only "music metadata" fields

**Changes Required**:
1. Add `original_filename` to `TrackMetadataUpdate` schema
2. Add `original_filename` to `allowed_fields` whitelist in DB
3. Update MCP tool docstring
4. Add HTTP PATCH endpoint for metadata (if desired)

### Option B: Dedicated `update_filename` Endpoint

**Approach**: Create separate MCP tool and HTTP endpoint just for filename

**Pros**:
- Clear semantic separation
- Can add filename-specific validation (e.g., extension preservation)
- Easier to audit/track filename changes specifically

**Cons**:
- More code to maintain
- Another API for users to learn
- Duplicates validation/error handling patterns

---

## Recommended Implementation Plan

**Decision**: **Option A - Extend `update_metadata`**

This is simpler and follows the existing patterns. Filename is just another piece of track data that users may want to correct.

---

## Task List

### Phase 1: Schema & Database Layer

| ID | Status | Task |
|----|--------|------|
| F1.1 | ✅ | Add `original_filename` field to `TrackMetadataUpdate` in `src/tools/update_schemas.py` |
| F1.2 | ✅ | Add `original_filename` to `allowed_fields` in `database/operations.py:update_audio_metadata()` |
| F1.3 | ✅ | Add filename validation (max 500 chars, no path separators, preserve extension optional) |

### Phase 2: MCP Tool Updates

| ID | Status | Task |
|----|--------|------|
| F2.1 | ✅ | Update `update_metadata` MCP tool docstring in `src/server.py` |
| F2.2 | ✅ | Test MCP tool with filename update via local Docker |

### Phase 3: HTTP API (Optional - Future Enhancement)

| ID | Status | Task |
|----|--------|------|
| F3.1 | todo | Add `PATCH /api/tracks/{audioId}` HTTP endpoint for metadata updates |
| F3.2 | todo | Add request body validation schema in `src/schemas/http_api.py` |
| F3.3 | todo | Document HTTP API in `docs/api-endpoint-testing-tracker.md` |

### Phase 4: Testing & Documentation

| ID | Status | Task |
|----|--------|------|
| F4.1 | todo | Write unit test for filename update via update_metadata |
| F4.2 | todo | Write integration test for end-to-end filename→download flow |
| F4.3 | todo | Update README or API docs with new editable field |

---

## Technical Implementation Details

### F1.1: Schema Change

```python
# src/tools/update_schemas.py - Add to TrackMetadataUpdate class

original_filename: Optional[str] = Field(
    default=None,
    max_length=500,
    description="Original filename for downloads (e.g., 'My Song.mp3')"
)
```

### F1.2: Database Whitelist

```python
# database/operations.py:update_audio_metadata() - Update allowed_fields

allowed_fields = {
    'artist', 'title', 'album', 'genre', 'year',
    'composer', 'publisher', 'record_label', 'isrc',
    'original_filename'  # Add this
}
```

### F1.3: Filename Validation (Optional)

```python
# Additional validation in update_audio_metadata() or Pydantic validator

# Option 1: Simple - just length check (already via Pydantic max_length)
# Option 2: Strict - prevent path separators
if 'original_filename' in updates:
    filename = updates['original_filename']
    if '/' in filename or '\\' in filename:
        raise ValidationError("Filename cannot contain path separators")
```

### F2.1: Docstring Update

```python
# src/server.py - update_metadata tool docstring

"""
Editable fields: artist, title, album, genre, year,
                 composer, publisher, record_label, isrc, original_filename

Args:
    ...
    metadata: Dict with fields to update (omit fields to leave unchanged)
        ...
        - original_filename: Download filename override (max 500 chars)
"""
```

---

## Open Questions

1. **Should filename updates preserve the original extension?**
   - e.g., if original is `song.mp3`, should we prevent changing to `song.flac`?
   - Current thinking: No, let users set whatever they want. Download adds correct extension anyway.

2. **Should we log filename changes separately for audit?**
   - Current thinking: No, existing update logging is sufficient.

3. **Is HTTP PATCH endpoint needed immediately?**
   - Current thinking: No, MCP tool is sufficient for now. Can add later.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users set invalid filenames | Low | Pydantic max_length, optional path separator check |
| Breaking existing update_metadata behavior | Low | Adding optional field, no breaking changes |
| Migration needed | None | Column already exists, just enabling updates |

---

## Summary

This is a **small, focused change** that:
1. Adds 1 field to a Pydantic schema
2. Adds 1 string to a whitelist
3. Updates 1 docstring

**Estimated effort**: 30 minutes - 1 hour  
**Complexity**: Low  
**Dependencies**: None (column already exists)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-09 | AI | Implementation completed - update filename API now functional |
| 2025-12-09 | AI | Initial analysis and task breakdown |

