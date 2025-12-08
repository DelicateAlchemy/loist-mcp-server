# LOI-16: API Parameter Validation Standardization - Task Tracking

**Linear Issue**: [LOI-16](https://linear.app/loist/issue/LOI-16/loi-16-standardize-api-parameter-validation-medium)  
**Status**: In Progress  
**Priority**: Medium  
**Created**: 2025-01-09

---

## 🎯 Project Goal

Standardize HTTP API parameter validation to use strict rejection (400 Bad Request) instead of silent correction, aligning with MCP tool validation patterns and REST API best practices.

---

## 📊 Current State Analysis

### Issues Found

#### 1. 🔴 Search Endpoint - Silent Correction (Primary Issue)
- **Location**: `src/http_api.py:108-109`
- **Problem**: 
  - `limit = max(1, min(limit, 100))` - silently corrects invalid values
  - `offset = max(0, offset)` - silently corrects negative values
- **Current Behavior**: Returns 200 OK with corrected values
- **Expected**: Return 400 Bad Request for invalid input
- **MCP Comparison**: `query_schemas.py` uses strict Pydantic validation (`Field(ge=1, le=100)`, `Field(ge=0)`)

#### 2. 🟡 Download Endpoint - Minor Validation Gap
- **Location**: `src/http_api.py:218`
- **Issue**: `preset` parameter uses `.lower()` before validation - could fail if preset validation is case-sensitive elsewhere
- **Impact**: Low (preset validation is already strict)

#### 3. ✅ Other Endpoints - Validated
- **UUID validation**: All endpoints using `uuid.UUID()` correctly reject invalid formats with 400
- **Format validation**: Download endpoint uses strict `validate_format()` and `validate_preset()` with proper 400 responses
- **Query validation**: Search endpoint properly validates empty `q` parameter

---

## 📋 Task List

### Phase 1: Search Endpoint Validation Fix

- [STATUS: todo] **V1.1**: Create Pydantic schema for search endpoint parameters
  - **Location**: `src/http_api.py` or new `src/schemas/http_api.py`
  - **Schema**: `SearchQueryParams` with `limit: int = Field(ge=1, le=100)`, `offset: int = Field(ge=0)`
  - **Rationale**: Align with MCP tool patterns, use Pydantic for consistent validation

- [STATUS: todo] **V1.2**: Replace silent correction with strict validation in search endpoint
  - **Location**: `src/http_api.py:96-150` (search_tracks function)
  - **Change**: Remove `max(1, min(limit, 100))` and `max(0, offset)`, use Pydantic schema
  - **Error Response**: Return 400 with clear error message when validation fails

- [STATUS: todo] **V1.3**: Update error response format to match MCP tool patterns
  - **Format**: Use consistent error structure with `error` code field
  - **Example**: `{"success": false, "error": "INVALID_QUERY", "message": "Limit must be between 1 and 100"}`
  - **Location**: Search endpoint error responses

### Phase 2: Comprehensive Validation Audit

- [STATUS: todo] **V2.1**: Audit genre parameter validation in search endpoint
  - **Location**: `src/http_api.py:115-116`
  - **Check**: Should genre list be validated? Empty strings? Duplicates?
  - **Action**: Document current behavior or add validation if needed

- [STATUS: todo] **V2.2**: Verify all UUID validations are consistent
  - **Endpoints**: GET, DELETE `/api/tracks/{audioId}`, stream, thumbnail, download
  - **Current**: All use `uuid.UUID()` with proper 400 responses
  - **Action**: Confirm no silent corrections or edge cases

- [STATUS: todo] **V2.3**: Verify format/preset validation in download endpoint
  - **Location**: `src/http_api.py:210-220`
  - **Current**: Uses `validate_format()` and `validate_preset()` with 400 responses
  - **Action**: Confirm no edge cases (empty strings, whitespace, etc.)

- [STATUS: todo] **V2.4**: Check query parameter type conversion edge cases
  - **Focus**: Integer conversions (`int()` calls) across all endpoints
  - **Check**: Float strings, empty strings, very large numbers, non-numeric values
  - **Action**: Ensure all `int()` calls are properly wrapped with validation

### Phase 3: Testing & Documentation

- [STATUS: todo] **V3.1**: Update API testing tracker with new expected behavior
  - **File**: `docs/api-endpoint-testing-tracker.md`
  - **Update**: Search endpoint tests to expect 400 for invalid limit/offset
  - **Remove**: Tests expecting silent correction behavior

- [STATUS: todo] **V3.2**: Add validation test cases for search endpoint
  - **Test Cases**:
    - `limit=-1` → 400 Bad Request
    - `limit=0` → 400 Bad Request
    - `limit=101` → 400 Bad Request
    - `limit=abc` → 400 Bad Request (already handled)
    - `offset=-1` → 400 Bad Request
    - `offset=abc` → 400 Bad Request (already handled)
    - `limit=50, offset=0` → 200 OK (valid)

- [STATUS: todo] **V3.3**: Verify no breaking changes for valid inputs
  - **Test**: Ensure all valid inputs (limit=1-100, offset≥0) still work correctly
  - **Verify**: Response format unchanged for successful requests

- [STATUS: todo] **V3.4**: Update Linear issue with completion status
  - **Action**: Mark LOI-16 as complete with summary of changes

---

## 🔍 Validation Patterns Reference

### MCP Tool Pattern (Strict Rejection)
```python
# From query_schemas.py
limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
offset: int = Field(default=0, ge=0, description="Number of results to skip")
```

### Current HTTP API Pattern (Silent Correction) - TO FIX
```python
# From http_api.py:108-109
limit = max(1, min(limit, 100))  # ❌ Silent correction
offset = max(0, offset)          # ❌ Silent correction
```

### Target Pattern (Strict Rejection)
```python
# Target implementation
class SearchQueryParams(BaseModel):
    q: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    genre: Optional[str] = None
```

---

## 📝 Implementation Notes

### Error Response Format
- **Consistent Structure**: Use `{"success": false, "error": "ERROR_CODE", "message": "..."}` for all validation errors
- **Error Codes**:
  - `INVALID_QUERY` - Invalid query parameters (limit, offset)
  - `VALIDATION_ERROR` - General validation failures
- **Status Code**: Always 400 Bad Request for validation errors

### Backward Compatibility
- **Breaking Change**: Yes, but acceptable for MVP stage
- **Impact**: Clients using invalid limit/offset values will now receive 400 instead of 200
- **Mitigation**: Document breaking change, update tests, no production clients to break

---

## ✅ Completion Checklist

- [x] All Phase 1 tasks complete (search endpoint fix)
- [x] All Phase 2 tasks complete (audit other endpoints)
- [x] All Phase 3 tasks complete (testing & documentation)
- [x] No regression in existing functionality
- [x] Error responses are consistent across all endpoints
- [x] Tests updated and passing

---

## 🔄 Rolling Summary

**2025-01-09**: Task tracking file created. Identified primary issue in search endpoint (silent correction of limit/offset). Ready to begin implementation.

**2025-01-09**: Implementation completed successfully. Created Pydantic schemas, updated search endpoint with strict validation, audited all HTTP endpoints, updated documentation, and marked Linear issue as done. Breaking change implemented as approved for MVP stage.

---

## 📚 Related Files

- `src/http_api.py` - HTTP API endpoint implementations
- `src/tools/query_schemas.py` - MCP tool validation schemas (reference pattern)
- `docs/api-endpoint-testing-tracker.md` - API testing documentation
- `docs/api-endpoint-refactoring.md` - Previous API refactoring work (if exists)

