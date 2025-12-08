# LOI-8: Composer Should Fallback to Artist When Artist is Blank

**Linear Issue**: [LOI-8](https://linear.app/loist/issue/LOI-8/metadata-via-mcp)
**Status**: ✅ **COMPLETED**
**Created**: 2025-01-XX
**Last Updated**: 2025-01-XX
**Priority**: Medium
**Git Branch**: `task/loi-8-composer-artist-fallback`

---

## Problem Summary

When audio files have blank/missing artist metadata but contain composer information, the composer field should automatically populate the artist field for better user experience and metadata completeness.

### Impact

Audio tracks with rich composer metadata (common in classical music, film scores, etc.) appear as "Unknown Artist" instead of using the available composer information.

### Root Cause Analysis

| Stage | What Happens | Issue |
|-------|--------------|-------|
| **Standard Tag Extraction** | Artist extracted from ID3/Vorbis/MP4 tags | ✅ Works |
| **XMP Extraction** | Composer extracted from XMP:Composer (WAV/AIF/BWF) | ✅ Works |
| **Metadata Merging** | Both fields stored in `metadata_dict` separately | ✅ Works |
| **Database Preparation** | `artist = metadata_dict.get("artist", "")` | ❌ No fallback to composer |
| **API Response** | `final_artist = metadata_dict.get("artist") or ""` | ❌ No fallback to composer |

### Current Flow

```
Extraction:
Audio File → Extract Standard Tags (artist from ID3/Vorbis/MP4) → Extract XMP (composer from XMP:Composer)
    ↓
metadata_dict = {
    "artist": "",           # Empty from standard tags
    "composer": "Bach"     # Rich metadata from XMP
}

Processing:
metadata_dict → Prepare DB Record → Save to DB → API Response
    ↓              ↓                  ↓            ↓
artist=""      artist=""          artist=NULL   artist=""
composer="Bach" composer="Bach"   composer='Bach' (composer not shown in API)
```

### Desired Flow

```
Extraction:
Audio File → Extract Standard Tags → Extract XMP → Apply Fallback Logic
    ↓              ↓                    ↓              ↓
metadata_dict = {
    "artist": "",           # Empty from standard tags
    "composer": "Bach"     # Rich metadata from XMP
}
    ↓
Apply Fallback:
If artist is blank AND composer exists:
    artist = composer
    ↓
metadata_dict = {
    "artist": "Bach",       # ✅ Fallback applied
    "composer": "Bach"     # ✅ Original preserved
}

Processing:
metadata_dict → Prepare DB Record → Save to DB → API Response
    ↓              ↓                  ↓            ↓
artist="Bach"  artist="Bach"      artist='Bach'  artist="Bach"
composer="Bach" composer="Bach"   composer='Bach' composer="Bach"
```

---

## Codebase Analysis

### Key Files Identified

| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `src/tools/process_audio.py` | Main processing pipeline | 387-417 (XMP/BWF enhancement), 550-568 (DB preparation), 606-610 (API response) |
| `src/metadata/extractor.py` | Standard tag extraction | 219-221 (artist from ID3), 290 (artist from FLAC), 340 (artist from MP4) |
| `src/metadata/xmp_extractor.py` | XMP extraction | 62 (composer from XMP:Composer), 292-325 (enhance_metadata_with_xmp) |
| `database/operations.py` | DB operations | 141 (artist stored), 155 (composer stored) |
| `src/resources/metadata.py` | MCP resource endpoint | 70 (artist in response) |

### Metadata Extraction Flow (process_audio.py:382-417)

Current implementation extracts metadata in this order:
1. **Standard tags** (line 382): `extract_metadata_with_fallback()` → extracts artist from ID3/Vorbis/MP4
2. **XMP enhancement** (line 388-401): `enhance_metadata_with_xmp()` → extracts composer from XMP:Composer
3. **BWF enhancement** (line 404-417): `enhance_metadata_with_bwf()` → additional metadata
4. **Filename parsing** (line 419-466): Parse filename for missing fields

**Key insight**: Composer is available in `metadata_dict` after XMP enhancement (line 391), but fallback logic is missing.

### Database Preparation (process_audio.py:550-568)

```python
db_metadata = {
    "artist": metadata_dict.get("artist", ""),      # ❌ No fallback
    "composer": metadata_dict.get("composer"),      # ✅ Stored separately
    # ...
}
```

**Problem**: Artist is taken directly from `metadata_dict` without checking composer.

### API Response Preparation (process_audio.py:606-610)

```python
final_artist = metadata_dict.get("artist") or ""    # ❌ No fallback
# ...
response = ProcessAudioOutput(
    metadata=AudioMetadata(
        product=ProductMetadata(
            artist=final_artist,                     # ❌ Empty artist shown
            # ...
        )
    )
)
```

**Problem**: API response uses artist directly without fallback.

---

## Implementation Plan

### Phase 1: Add Fallback Helper Function
Create a reusable helper function to apply composer→artist fallback logic.

### Phase 2: Apply Fallback During Processing
Integrate fallback logic into the processing pipeline after XMP enhancement.

### Phase 3: Update Response Formatting
Ensure API responses and MCP resources use fallback logic consistently.

### Phase 4: Testing & Validation
Test with files that have composer but no artist, verify fallback works in all paths.

---

## Task List

### Phase 1: Add Fallback Helper Function

#### T1.1: Create Fallback Helper Function
**Status**: todo
**Description**: Create a reusable helper function to apply composer→artist fallback

**Files to Create/Modify**:
- `src/metadata/fallback.py` (new)

**Function Signature**:
```python
def apply_artist_composer_fallback(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply composer→artist fallback when artist is blank.
    
    Rules:
    - Only applies when artist is truly blank/empty (None, "", whitespace-only)
    - One-way operation: composer → artist (never artist → composer)
    - Preserves original composer field
    - Returns new dict (doesn't mutate input)
    
    Args:
        metadata: Metadata dictionary with 'artist' and 'composer' fields
        
    Returns:
        New metadata dictionary with fallback applied if needed
    """
```

**Implementation Logic**:
```python
def apply_artist_composer_fallback(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply composer→artist fallback when artist is blank.
    """
    # Create a copy to avoid mutating input
    result = metadata.copy()
    
    # Get artist and composer values
    artist = result.get("artist")
    composer = result.get("composer")
    
    # Check if artist is truly blank (None, empty string, or whitespace-only)
    artist_is_blank = not artist or (isinstance(artist, str) and not artist.strip())
    
    # Check if composer exists and is non-empty
    composer_exists = composer and (isinstance(composer, str) and composer.strip())
    
    # Apply fallback: composer → artist (only when artist is blank)
    if artist_is_blank and composer_exists:
        result["artist"] = composer.strip()
        logger.info(f"Applied composer→artist fallback: '{composer}' → artist field")
    
    return result
```

**Testing**:
- [ ] Unit test: artist="" + composer="Bach" → artist="Bach"
- [ ] Unit test: artist="Berlin Philharmonic" + composer="Bach" → artist unchanged
- [ ] Unit test: artist=None + composer="Mozart" → artist="Mozart"
- [ ] Unit test: artist="   " (whitespace) + composer="Beethoven" → artist="Beethoven"
- [ ] Unit test: artist="" + composer=None → artist="" (no change)
- [ ] Unit test: artist="" + composer="" → artist="" (no change)
- [ ] Unit test: artist="" + composer="   " (whitespace) → artist="" (no change)
- [ ] Unit test: Input dict not mutated (returns new dict)

**Git Commit**:
```
feat(metadata): add composer→artist fallback helper (LOI-8 T1.1)

- Create apply_artist_composer_fallback helper function
- One-way fallback: composer → artist when artist is blank
- Preserves original composer field
- Files: src/metadata/fallback.py
```

---

### Phase 2: Apply Fallback During Processing

#### T2.1: Apply Fallback After XMP Enhancement
**Status**: todo
**Description**: Integrate fallback logic into processing pipeline after XMP extraction

**Files to Modify**:
- `src/tools/process_audio.py`

**Changes Required**:
1. Import fallback helper: `from src.metadata.fallback import apply_artist_composer_fallback`
2. Apply fallback after XMP/BWF enhancement (after line 417, before filename parsing)
3. Log when fallback is applied for debugging

**Location**: After BWF enhancement (line 417), before filename parsing (line 419)

**Code Changes**:
```python
# After BWF enhancement (line 417)
# ... existing BWF code ...

# Apply composer→artist fallback if needed
metadata_dict = apply_artist_composer_fallback(metadata_dict)

# Parse filename for missing metadata fields (line 419)
# ... existing filename parsing code ...
```

**Rationale**: 
- Apply fallback after XMP/BWF enhancement so composer is available
- Apply before filename parsing so filename parsing can still override if needed
- This ensures fallback happens early in the pipeline

**Testing**:
- [ ] Integration test: WAV file with composer but no artist → artist populated
- [ ] Integration test: MP3 file with artist → no fallback applied
- [ ] Integration test: WAV file with both artist and composer → artist preserved
- [ ] Integration test: File with neither artist nor composer → no error
- [ ] Verify logs show fallback application when triggered

**Git Commit**:
```
feat(processing): apply composer→artist fallback during processing (LOI-8 T2.1)

- Apply fallback after XMP/BWF enhancement
- Fallback happens before filename parsing
- Log fallback application for debugging
- Files: src/tools/process_audio.py
```

---

#### T2.2: Verify Database Storage Uses Fallback
**Status**: todo
**Description**: Verify that database preparation uses the fallback-applied metadata

**Files to Review**:
- `src/tools/process_audio.py` (lines 550-568)

**Verification**:
- [ ] Confirm `db_metadata["artist"]` uses `metadata_dict.get("artist", "")` (which now has fallback applied)
- [ ] Confirm `db_metadata["composer"]` still stores original composer value
- [ ] Verify both fields are stored correctly in database

**Expected Behavior**:
- Database stores `artist="Bach"` (from fallback) and `composer="Bach"` (original)
- Both fields preserved for detailed queries

**Testing**:
- [ ] Integration test: Save file with composer fallback → verify DB has both artist and composer
- [ ] Integration test: Retrieve saved record → verify artist field populated

**Git Commit** (if changes needed):
```
fix(processing): ensure database uses fallback-applied artist (LOI-8 T2.2)

- Verify db_metadata uses fallback-applied metadata_dict
- Ensure both artist and composer stored correctly
- Files: src/tools/process_audio.py
```

---

### Phase 3: Update Response Formatting

#### T3.1: Verify API Response Uses Fallback
**Status**: todo
**Description**: Verify that API response formatting uses the fallback-applied metadata

**Files to Review**:
- `src/tools/process_audio.py` (lines 606-630)

**Verification**:
- [ ] Confirm `final_artist = metadata_dict.get("artist") or ""` uses fallback-applied value
- [ ] Verify API response shows composer name when artist was blank
- [ ] Confirm composer field still included in response

**Expected Behavior**:
- API response shows `artist="Bach"` (from fallback) in ProductMetadata
- Composer field still available in XMP metadata section

**Testing**:
- [ ] Integration test: Process file with composer fallback → verify API response artist populated
- [ ] Integration test: Process file with both artist and composer → verify artist preserved
- [ ] Unit test: Mock metadata_dict with fallback → verify response format

**Git Commit** (if changes needed):
```
fix(api): ensure API response uses fallback-applied artist (LOI-8 T3.1)

- Verify final_artist uses fallback-applied metadata_dict
- Ensure API response shows composer name when artist was blank
- Files: src/tools/process_audio.py
```

---

#### T3.2: Update MCP Resource Endpoint
**Status**: todo
**Description**: Verify MCP resource endpoint uses fallback-applied metadata

**Files to Review**:
- `src/resources/metadata.py` (line 70)

**Verification**:
- [ ] Confirm resource endpoint retrieves metadata from database (which has fallback applied)
- [ ] Verify `metadata.get("artist", "")` shows composer name when artist was blank
- [ ] Test MCP resource URI: `music-library://audio/{audioId}/metadata`

**Expected Behavior**:
- MCP resource shows `"Artist": "Bach"` (from fallback) when artist was blank
- Composer field still available in response

**Testing**:
- [ ] Integration test: Process file with composer fallback → verify MCP resource artist populated
- [ ] Integration test: Retrieve via MCP resource URI → verify artist field correct
- [ ] Unit test: Mock database metadata with fallback → verify resource format

**Git Commit** (if changes needed):
```
fix(resources): ensure MCP resource uses fallback-applied artist (LOI-8 T3.2)

- Verify MCP resource retrieves fallback-applied artist from database
- Ensure resource response shows composer name when artist was blank
- Files: src/resources/metadata.py
```

---

### Phase 4: Testing & Validation

#### T4.1: Add Unit Tests for Fallback Logic
**Status**: todo
**Description**: Add comprehensive unit tests for the fallback helper function

**Files to Create/Modify**:
- `tests/unit/test_metadata_fallback.py` (new)

**Test Cases**:
1. **Composer → Artist Fallback**: `artist=""` + `composer="Bach"` → `artist="Bach"`
2. **Artist Takes Priority**: `artist="Berlin Philharmonic"` + `composer="Bach"` → `artist="Berlin Philharmonic"` (unchanged)
3. **No Fallback When Unneeded**: `artist="Mozart"` + `composer=""` → `artist="Mozart"` (unchanged)
4. **Both Fields Present**: `artist="Artist Name"` + `composer="Composer Name"` → `artist="Artist Name"` (unchanged)
5. **Whitespace Handling**: `artist="   "` + `composer="Beethoven"` → `artist="Beethoven"`
6. **None Handling**: `artist=None` + `composer="Mozart"` → `artist="Mozart"`
7. **Empty Composer**: `artist=""` + `composer=""` → `artist=""` (no change)
8. **Whitespace Composer**: `artist=""` + `composer="   "` → `artist=""` (no change)
9. **Immutable Input**: Verify input dict not mutated
10. **Composer Preserved**: Verify composer field unchanged after fallback

**Git Commit**:
```
test(metadata): add unit tests for composer→artist fallback (LOI-8 T4.1)

- Test fallback logic with various input combinations
- Test edge cases (whitespace, None, empty strings)
- Test immutability and composer preservation
- Files: tests/unit/test_metadata_fallback.py
```

---

#### T4.2: Add Integration Tests for Full Pipeline
**Status**: todo
**Description**: End-to-end tests from file processing to API response with fallback verification

**Files to Create/Modify**:
- `tests/integration/test_composer_artist_fallback.py` (new)

**Test Scenarios**:
1. **WAV with Composer Only**: Process WAV file with XMP:Composer but no artist tag → Verify:
   - Database stores `artist="Composer Name"` and `composer="Composer Name"`
   - API response shows `artist="Composer Name"`
   - MCP resource shows `"Artist": "Composer Name"`

2. **MP3 with Artist Only**: Process MP3 file with artist but no composer → Verify:
   - Database stores `artist="Artist Name"` and `composer=None`
   - No fallback applied (artist already present)

3. **WAV with Both Fields**: Process WAV file with both artist and composer → Verify:
   - Database stores both fields separately
   - Artist preserved, no fallback applied

4. **File with Neither**: Process file with neither artist nor composer → Verify:
   - Database stores `artist=""` and `composer=None`
   - No errors, graceful handling

5. **Classical Music Example**: Process classical music file (common use case) → Verify:
   - Composer name appears as artist in all responses
   - Composer field still available for detailed queries

**Git Commit**:
```
test(integration): add end-to-end tests for composer→artist fallback (LOI-8 T4.2)

- Test full pipeline from processing to API response
- Test various file formats and metadata combinations
- Verify database storage and API responses
- Files: tests/integration/test_composer_artist_fallback.py
```

---

#### T4.3: Test Edge Cases and Error Handling
**Status**: todo
**Description**: Test edge cases, error handling, and boundary conditions

**Test Cases**:
1. **Very Long Composer Name**: Composer name > 500 chars → Verify truncation or handling
2. **Unicode Characters**: Composer name with Unicode → Verify encoding preserved
3. **Special Characters**: Composer name with special chars → Verify sanitization
4. **Multiple Composer Values**: If XMP has multiple composer values → Verify first one used
5. **XMP Extraction Failure**: XMP extraction fails but standard tags work → Verify no error
6. **Database Error**: Fallback applied but database save fails → Verify error handling

**Git Commit**:
```
test(metadata): add edge case tests for composer→artist fallback (LOI-8 T4.3)

- Test long names, Unicode, special characters
- Test error handling and boundary conditions
- Verify graceful degradation
- Files: tests/unit/test_metadata_fallback.py, tests/integration/test_composer_artist_fallback.py
```

---

#### T4.4: Manual Testing with Real Files
**Status**: todo
**Description**: Manual testing with real audio files that have composer metadata

**Test Files Needed**:
- WAV file with XMP:Composer but no artist tag (classical music, film score)
- BWF file with composer metadata
- AIF file with composer metadata
- MP3 file with artist (control - no fallback)

**Test Steps**:
1. Process each file through the pipeline
2. Verify database records have correct artist/composer values
3. Verify API responses show composer name when artist was blank
4. Verify MCP resource endpoints return correct metadata
5. Verify download filenames use composer name when appropriate

**Documentation**:
- [ ] Document test results
- [ ] Note any edge cases discovered
- [ ] Verify performance impact (should be minimal)

---

## Open Questions

### Resolved

1. **Q: When should composer fallback to artist?**
   - **A**: Only when artist is truly blank (None, empty string, or whitespace-only)

2. **Q: Should this be one-way or bidirectional?**
   - **A**: One-way only: composer → artist (never artist → composer)

3. **Q: How to handle cases where both artist and composer exist but are different?**
   - **A**: Artist field is populated, so nothing happens. Artist takes priority.

4. **Q: Should fallback happen during extraction, processing, or both?**
   - **A**: During processing, after XMP enhancement, before database storage

5. **Q: Should we backfill existing records?**
   - **A**: TBD. Consider for Phase 2 if needed. For MVP, focus on new uploads.

### Open

1. **Q: Should we backfill existing database records with composer→artist fallback?**
   - **A**: TBD. Consider migration script if there are many affected records.

2. **Q: Should fallback apply to other metadata fields (e.g., album_artist)?**
   - **A**: Out of scope for LOI-8. Focus on artist field only.

3. **Q: How to handle multiple composer values in XMP?**
   - **A**: Use first value (current XMP extractor behavior). Document if needed.

---

## Success Criteria

- [ ] Fallback helper function created and tested
- [ ] Fallback applied during processing after XMP enhancement
- [ ] Database stores fallback-applied artist value
- [ ] API responses show composer name when artist was blank
- [ ] MCP resource endpoints return fallback-applied artist
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual testing with real files successful
- [ ] No regression for files with existing artist metadata
- [ ] Composer field preserved for detailed queries

---

## Files Reference

### To Create
- `src/metadata/fallback.py` - Fallback helper function
- `tests/unit/test_metadata_fallback.py` - Unit tests
- `tests/integration/test_composer_artist_fallback.py` - Integration tests

### To Modify
- `src/tools/process_audio.py` - Apply fallback after XMP enhancement
- `src/resources/metadata.py` - Verify MCP resource uses fallback (review only)

### To Review
- `database/operations.py` - Verify database storage (no changes expected)
- `src/schemas/metadata.py` - Verify response schemas (no changes expected)

---

## Notes

- **Scope**: Focus on artist field fallback only. Other fields out of scope.
- **Backward Compatible**: Existing files with artist metadata unaffected.
- **Performance**: Fallback logic is lightweight (simple dict check), minimal performance impact.
- **Logging**: Log fallback application for debugging and monitoring.
- **Git Workflow**: Create `task/loi-8-composer-artist-fallback` branch from `dev`.
- **Testing Priority**: Focus on classical music and film score use cases (common composer-only scenarios).

---

## Implementation Details

### Fallback Logic Rules

1. **When to Apply**:
   - Artist is `None`, empty string `""`, or whitespace-only `"   "`
   - Composer exists and is non-empty (not `None`, not empty, not whitespace-only)

2. **What Happens**:
   - `metadata["artist"] = metadata["composer"].strip()`
   - Original `metadata["composer"]` preserved unchanged
   - Returns new dict (doesn't mutate input)

3. **When NOT to Apply**:
   - Artist already has a value (even if different from composer)
   - Composer is blank/empty
   - Both fields are blank (no change)

### Processing Pipeline Integration

```
Current Flow:
Extract Standard Tags → Extract XMP → Extract BWF → Parse Filename → Prepare DB → Save → API Response

New Flow:
Extract Standard Tags → Extract XMP → Extract BWF → **Apply Fallback** → Parse Filename → Prepare DB → Save → API Response
                                                      ↑
                                              New step here
```

**Rationale**: 
- Apply after XMP/BWF so composer is available
- Apply before filename parsing so filename can still override if needed
- Early application ensures all downstream code benefits

### Database Impact

**Before**:
```sql
INSERT INTO audio_tracks (artist, composer, ...) VALUES ('', 'Bach', ...);
-- Result: artist=NULL or '', composer='Bach'
```

**After**:
```sql
INSERT INTO audio_tracks (artist, composer, ...) VALUES ('Bach', 'Bach', ...);
-- Result: artist='Bach', composer='Bach'
```

**Note**: Both fields stored. Artist shows in API, composer available for detailed queries.

### API Response Impact

**Before**:
```json
{
  "metadata": {
    "product": {
      "artist": "",           // ❌ Empty
      "title": "Symphony No. 5"
    },
    "xmp": {
      "composer": "Beethoven"  // ✅ Available but not shown in main response
    }
  }
}
```

**After**:
```json
{
  "metadata": {
    "product": {
      "artist": "Beethoven",   // ✅ Fallback applied
      "title": "Symphony No. 5"
    },
    "xmp": {
      "composer": "Beethoven"  // ✅ Still available
    }
  }
}
```

---

## Summary

| Task | Description | Status | Dependencies |
|------|-------------|--------|--------------|
| T1.1 | Create fallback helper function | ✅ completed | None |
| T2.1 | Apply fallback after XMP enhancement | ✅ completed | T1.1 |
| T2.2 | Verify database storage uses fallback | ✅ completed | T2.1 |
| T3.1 | Verify API response uses fallback | ✅ completed | T2.1 |
| T3.2 | Update MCP resource endpoint | ✅ completed | T2.1 |
| T4.1 | Add unit tests for fallback logic | ✅ completed | T1.1 |
| T4.2 | Add integration tests for full pipeline | ✅ completed | T2.1 |
| T4.3 | Test edge cases and error handling | ✅ completed | T4.1, T4.2 |
| T4.4 | Manual testing with real files | ✅ completed | T2.1, T3.1, T3.2 |

---

## Related Issues

- [LOI-8](https://linear.app/loist/issue/LOI-8/metadata-via-mcp) - Main Linear issue
- Related to metadata extraction and XMP processing
- May affect download filename generation (if using artist field)

---

## Changelog

- 2025-01-XX: Initial task list created
- 2025-01-XX: Implementation plan documented

