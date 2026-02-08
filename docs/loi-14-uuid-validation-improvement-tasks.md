# LOI-14: Improve MCP Tool Input Validation - UUID Format Validation

**Linear Issue**: [LOI-14](https://linear.app/loist/issue/LOI-14/improve-mcp-tool-input-validation-medium)
**Status**: ✅ APPROVED - Implementation Complete, Ready for Merge
**Created**: 2025-12-08
**Last Updated**: 2025-12-08
**Priority**: Medium
**Root Cause**: Pydantic validates `min_length`/`max_length` before pattern/custom validators, causing confusing error messages
**Solution**: Remove redundant length constraints, use `uuid.UUID()` validation, provide clear error messages with examples

---

## Problem Summary

MCP tool `get_audio_metadata` (and other tools) fail input validation with confusing error messages when provided with invalid UUID formats. The error message indicates validation is checking for minimum length (36 chars) rather than proper UUID format validation.

**Current Error Message**:
```
1 validation error for GetAudioMetadataInput
audioId String should have at least 36 characters
```

**Expected Error Message**:
```
audio_id must be a valid UUID format (e.g., 550e8400-e29b-41d4-a716-446655440000)
```

**Impact**: 
- Clients receive confusing validation error messages
- Error messages don't clearly indicate UUID format requirements
- May lead to incorrect client-side fixes (padding strings to 36 chars instead of fixing format)

---

## Root Cause Analysis

### ✅ CONFIRMED: Pydantic Validation Order (🟢 CONFIDENCE: 0.95)

**Status**: VERIFIED via codebase investigation on 2025-12-08

**Location**: Multiple schema files:
- `src/tools/query_schemas.py` - `GetAudioMetadataInput`, `DeleteAudioInput`
- `src/schemas/http_api.py` - `UUIDPathParams`
- `src/tools/update_schemas.py` - `UpdateMetadataInput` (already correct - no min/max length)

**Problem**: Pydantic validates field constraints in this order:
1. Type validation
2. `min_length` / `max_length` constraints
3. `pattern` regex validation
4. Custom `@field_validator` functions

When a UUID string is shorter than 36 characters (e.g., `"abc"`), Pydantic fails at step 2 with "String should have at least 36 characters" before it reaches the pattern or custom validator that would provide a clearer UUID format error.

**Evidence**:

```199:205:src/tools/query_schemas.py
    audio_id: str = Field(
        ...,
        description="UUID of the audio track",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=36,
        max_length=36
    )
```

The `pattern` already enforces the exact length (36 chars with hyphens), so `min_length` and `max_length` are redundant and cause the confusing error message.

**Current Implementation Issues**:

1. **GetAudioMetadataInput** (`src/tools/query_schemas.py:199-205`):
   - Has `min_length=36, max_length=36` causing confusing errors
   - Has custom validator but it's never reached for short strings

2. **DeleteAudioInput** (`src/tools/query_schemas.py:608-614`):
   - Same issue: `min_length=36, max_length=36`
   - Has custom validator but not reached for short strings

3. **UUIDPathParams** (`src/schemas/http_api.py:139-145`):
   - Same issue: `min_length=36, max_length=36`
   - Only has normalization validator, no format validation

4. **UpdateMetadataInput** (`src/tools/update_schemas.py:97-101`):
   - ✅ Already correct: Only has `pattern`, no `min_length`/`max_length`
   - This is the pattern we should follow

5. **download_tool.py** (`src/tools/download_tool.py:81-84`):
   - Uses `uuid.UUID()` directly for validation (good approach)
   - Provides clear error: `f"Invalid audio_id format: {audio_id}"`

---

## Solution Approach

### Primary Fix: Remove Redundant Length Constraints

1. **Remove `min_length` and `max_length`** from UUID fields
   - The regex pattern already enforces exact length
   - This prevents Pydantic from showing length-based errors

2. **Improve Custom Validator Error Messages**
   - Make error messages more user-friendly
   - Include example UUID format in error message
   - Consider using Python's `uuid.UUID()` for validation (more robust)

3. **Standardize UUID Validation Across Codebase**
   - Create a shared UUID validation utility if needed
   - Ensure consistent error messages

### Optional Enhancement: Support Non-Hyphenated UUIDs

**Consideration**: Some systems generate UUIDs without hyphens (32 chars). We could:
- Accept both formats: `550e8400-e29b-41d4-a716-446655440000` and `550e840041d4a716446655440000`
- Normalize to hyphenated format internally
- This increases flexibility but adds complexity

**Recommendation**: Start with hyphenated-only (current behavior), add non-hyphenated support later if needed.

---

## Task List

### Phase 1: Investigation & Analysis ✅ COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| I1 | Investigate current UUID validation implementation | ✅ done | Found 4 schemas with min/max length issues |
| I2 | Identify all locations using UUID validation | ✅ done | Found in query_schemas.py, http_api.py, update_schemas.py, download_tool.py |
| I3 | Review error message patterns | ✅ done | Confirmed confusing "should have at least 36 characters" messages |
| I4 | Check existing tests for UUID validation | ✅ done | Found tests in test_query_tools.py |
| I5 | Document root cause and solution approach | ✅ done | This document |

### Phase 2: Core Fixes - Remove Length Constraints

| ID | Task | Status | Notes |
|----|------|--------|-------|
| F1 | Fix GetAudioMetadataInput schema | ✅ done | Removed min_length/max_length, improved validator using uuid.UUID() |
| F2 | Fix DeleteAudioInput schema | ✅ done | Removed min_length/max_length, improved validator using uuid.UUID() |
| F3 | Fix UUIDPathParams schema | ✅ done | Removed min_length/max_length, improved validator using uuid.UUID() |
| F4 | Verify UpdateMetadataInput is correct | ✅ done | Confirmed it doesn't need changes (already good, but consider standardizing) |

### Phase 3: Improve Error Messages

| ID | Task | Status | Notes |
|----|------|--------|-------|
| E1 | Update GetAudioMetadataInput validator error message | ✅ done | User-friendly message with UUID example, truncates long strings |
| E2 | Update DeleteAudioInput validator error message | ✅ done | User-friendly message with UUID example, truncates long strings |
| E3 | Update UUIDPathParams validation error | ✅ done | Improved validate_uuid_path() error message propagation |
| E4 | Consider using uuid.UUID() for validation | ✅ done | Implemented uuid.UUID() for robust validation |

### Phase 4: Testing & Validation

| ID | Task | Status | Notes |
|----|------|--------|-------|
| T1 | Update existing tests for new error messages | ✅ done | Updated test expectations for new error messages |
| T2 | Add test for short UUID string (e.g., "abc") | ✅ done | Added edge case test showing format error, not length error |
| T3 | Add test for invalid UUID format (e.g., "gggggggggggg") | ✅ done | Added test for invalid hex characters in UUID |
| T4 | Add test for valid UUID | ✅ done | Existing tests verify valid UUIDs pass validation |
| T5 | Test HTTP API UUID path validation | ✅ done | Verified validate_uuid_path() works correctly |
| T6 | Test MCP tool UUID validation | ✅ done | All query tool tests pass (12/12) |

### Phase 5: Optional Enhancements (Future)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| O1 | Research non-hyphenated UUID support | ✅ done | Decided not to implement - stick with hyphenated UUIDs |
| O2 | Create shared UUID validation utility | 🤔 optional | Consider for future if more UUID fields added |
| O3 | Add non-hyphenated UUID support | ❌ cancelled | Not needed - hyphenated UUIDs sufficient |

---

## Code Review Feedback

### ✅ Overall Assessment: Approved with Minor Notes

**Reviewer**: Another LLM agent
**Date**: 2025-12-08
**Verdict**: ✅ APPROVED - Ready to merge

### What's Good

1. **Core Fix**: Removed redundant constraints, switched to `uuid.UUID()` validation, clearer error messages
2. **Consistency**: Applied to all three schemas consistently
3. **Testing**: All 12 tests pass, comprehensive edge case coverage
4. **Error Handling**: Good error message formatting with truncation

### Minor Issues and Recommendations

#### 1. Docker Compose Change - Development Convenience
- **Issue**: Added `./tests:/app/tests:ro` volume mount for live testing
- **Assessment**: Reasonable for development, not required for core fix
- **Recommendation**: Keep it, but document as dev convenience (not core fix)

#### 2. Pattern Removal Inconsistency
- **Issue**: Removed `pattern` from UUID fields, creating slight inconsistency with `UpdateMetadataInput`
- **Assessment**: Custom validator approach is preferable, creates minor inconsistency
- **Recommendation**: Consider standardizing `UpdateMetadataInput` for consistency (optional, not blocking)

#### 3. Import Placement Style
- **Issue**: `import uuid` placed inside validator functions
- **Assessment**: Works fine, but unusual style (standard is module-level imports)
- **Recommendation**: Consider moving to module-level imports for consistency (optional)

### Code Quality Checklist

| Item | Status | Notes |
|------|--------|-------|
| UUID validation works correctly | ✅ | All tests pass |
| Error messages are user-friendly | ✅ | Clear format with examples |
| Valid UUIDs pass validation | ✅ | Tested |
| Invalid UUIDs show clear errors | ✅ | No more length-based errors |
| No redundant constraints | ✅ | Removed min/max length |
| Consistent validation approach | ⚠️ | Slight inconsistency with UpdateMetadataInput |
| Good error message formatting | ✅ | Includes examples, truncates long strings |
| Proper imports | ⚠️ | Imports inside functions (works, but unusual) |
| All tests pass | ✅ | 12/12 passing |
| Edge cases covered | ✅ | Short strings, invalid formats tested |
| No breaking API changes | ✅ | Same behavior, better errors |
| HTTP API validation works | ✅ | Updated `validate_uuid_path()` |

### Final Recommendations

1. ✅ Keep the docker-compose change (documented as dev convenience)
2. 🤔 Consider standardizing `UpdateMetadataInput` to match (optional)
3. 🤔 Optional: Move `uuid` imports to module level for consistency

---

## Implementation Details

### Files to Modify

1. **src/tools/query_schemas.py**
   - `GetAudioMetadataInput.audio_id` field (lines 199-205)
   - `GetAudioMetadataInput.validate_uuid_format()` validator (lines 207-217)
   - `DeleteAudioInput.audio_id` field (lines 608-614)
   - `DeleteAudioInput.validate_uuid_format()` validator (lines 632-642)

2. **src/schemas/http_api.py**
   - `UUIDPathParams.audio_id` field (lines 139-145)
   - `UUIDPathParams.normalize_uuid()` validator (lines 147-151)
   - `validate_uuid_path()` function (lines 241-258) - improve error message

3. **tests/test_query_tools.py**
   - Update tests to expect new error messages (lines 66-72, 152-156)

### Code Changes Preview

**Before** (`GetAudioMetadataInput`):
```python
audio_id: str = Field(
    ...,
    description="UUID of the audio track",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    min_length=36,  # ❌ Causes confusing error
    max_length=36   # ❌ Causes confusing error
)

@field_validator('audio_id')
@classmethod
def validate_uuid_format(cls, v):
    """Ensure audio_id is a valid UUID format"""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    if not uuid_pattern.match(v):
        raise ValueError("audio_id must be a valid UUID format")  # Generic message
    return v.lower()
```

**After** (`GetAudioMetadataInput`):
```python
audio_id: str = Field(
    ...,
    description="UUID of the audio track",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    # ✅ Removed min_length/max_length - pattern enforces length
)

@field_validator('audio_id')
@classmethod
def validate_uuid_format(cls, v):
    """Ensure audio_id is a valid UUID format"""
    import uuid
    try:
        # Use Python's uuid.UUID for robust validation
        parsed_uuid = uuid.UUID(v)
        return str(parsed_uuid).lower()  # Normalize to lowercase hyphenated
    except ValueError:
        raise ValueError(
            f"audio_id must be a valid UUID format (e.g., 550e8400-e29b-41d4-a716-446655440000), "
            f"got: {v[:50]}"  # Truncate long strings in error message
        )
```

**Alternative Approach** (using regex with better error):
```python
audio_id: str = Field(
    ...,
    description="UUID of the audio track",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
)

@field_validator('audio_id')
@classmethod
def validate_uuid_format(cls, v):
    """Ensure audio_id is a valid UUID format"""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    if not uuid_pattern.match(v):
        raise ValueError(
            f"audio_id must be a valid UUID format "
            f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {v[:50]}"
        )
    return v.lower()
```

---

## Testing Strategy

### Test Cases

1. **Valid UUID (hyphenated)**:
   - Input: `"550e8400-e29b-41d4-a716-446655440000"`
   - Expected: ✅ Passes validation, normalized to lowercase

2. **Valid UUID (uppercase)**:
   - Input: `"550E8400-E29B-41D4-A716-446655440000"`
   - Expected: ✅ Passes validation, normalized to lowercase

3. **Invalid UUID (too short)**:
   - Input: `"abc"`
   - Expected: ❌ Error: "audio_id must be a valid UUID format (e.g., ...), got: abc"
   - NOT: "String should have at least 36 characters"

4. **Invalid UUID (wrong format)**:
   - Input: `"not-a-uuid"`
   - Expected: ❌ Error: "audio_id must be a valid UUID format (e.g., ...), got: not-a-uuid"

5. **Invalid UUID (missing hyphens)**:
   - Input: `"550e8400e29b41d4a716446655440000"`
   - Expected: ❌ Error: "audio_id must be a valid UUID format (e.g., ...), got: ..."
   - (Unless we implement non-hyphenated support)

6. **Invalid UUID (wrong length with hyphens)**:
   - Input: `"550e8400-e29b-41d4-a716-44665544000"` (35 chars)
   - Expected: ❌ Error: "audio_id must be a valid UUID format (e.g., ...), got: ..."

### Test Locations

- `tests/test_query_tools.py` - Unit tests for schemas
- `tests/integration/test_api_endpoints.py` - Integration tests for HTTP API
- Manual MCP tool testing via Postman/curl

---

## Open Questions

1. **Non-hyphenated UUID support**: Should we accept UUIDs without hyphens?
   - **Decision**: Start with hyphenated-only, add non-hyphenated support later if needed
   - **Rationale**: Simpler implementation, can add flexibility later

2. **Shared UUID validation utility**: Should we create a shared function?
   - **Decision**: Not needed initially, but consider if we add more UUID fields
   - **Rationale**: Current approach (validator per schema) is fine for now

3. **Error message format**: Should we include the invalid value in the error?
   - **Decision**: Yes, but truncate long strings (max 50 chars)
   - **Rationale**: Helps debugging but prevents error message spam

---

## Related Issues

- **LOI-16**: API Validation Standardization (may have overlapping concerns)
- **Postman Test Issues**: `postman-test-issues-analysis.md` documents this issue

---

## Success Criteria ✅ ALL MET

- [x] All UUID validation error messages clearly indicate UUID format requirements
- [x] No more "String should have at least 36 characters" errors for UUID validation
- [x] Error messages include example UUID format
- [x] All existing tests pass with updated error messages (12/12 tests passing)
- [x] New tests verify improved error messages (edge cases covered)
- [x] HTTP API and MCP tools both use consistent UUID validation

---

## Implementation Summary

### ✅ Core Fix Implemented
- **Problem**: Pydantic's validation order caused confusing "String should have at least 36 characters" errors
- **Solution**: Removed redundant `min_length`/`max_length` constraints, improved custom validators
- **Result**: Clear, user-friendly UUID format error messages with examples

### ✅ Code Review Approved
- **Status**: Approved with minor notes (ready to merge)
- **Minor Issues**: Documented and addressed (docker-compose dev convenience, style preferences)
- **Impact**: No breaking changes, better user experience

### 📋 Follow-up Considerations (Optional)

1. **Consistency**: Consider updating `UpdateMetadataInput` to use `uuid.UUID()` validator instead of regex pattern
2. **Style**: Move `uuid` imports to module level for consistency (current: function-level imports work fine)
3. **Future**: Create shared UUID validation utility if more UUID fields are added

### 🚀 Ready for Merge
- Branch: `task-14`
- Status: ✅ Approved, tested, documented
- Next: Merge to `dev` after final verification

---

## Notes

- `UpdateMetadataInput` in `src/tools/update_schemas.py` already follows the correct pattern (no min/max length)
- `download_tool.py` uses `uuid.UUID()` directly - this is a good pattern to consider
- Consider creating a shared UUID validation pattern if we add more UUID fields in the future

