# LOI-17: Improve Download Tests - Add Cleanup, Validation & Organized Test Structure

**Linear Issue**: [LOI-17](https://linear.app/loist/issue/LOI-17/improve-download-tests-add-cleanup-validation-and-organized-test)
**Status**: 🔄 IN PROGRESS - Planning Phase
**Created**: 2025-12-08
**Last Updated**: 2025-12-08
**Priority**: Medium
**Git Branch**: `task/loi-17-improve-download-tests`

---

## Problem Summary

The current download tests lack proper cleanup of audio files after test execution and need better validation. Tests should be organized in dedicated download folders and include comprehensive validation of downloaded content.

### Current State Analysis

#### Existing Test Files
- ✅ `tests/unit/test_download_service.py` - Unit tests (mocks only, no actual downloads)
- ✅ `tests/test_download_converter.py` - FFmpeg converter tests (good cleanup with TemporaryDirectory)
- ⚠️ `tests/test_http_downloader.py` - HTTP downloader tests (partial cleanup)
- ⚠️ Postman collection tests (manual/API level, no automated cleanup)

#### Current Cleanup Mechanisms
- ✅ HTTP API: Uses BackgroundTask cleanup for streaming responses
- ⚠️ MCP Tool: Synchronous cleanup in finally block (could block response)
- ⚠️ Download Service: Cleanup only in except block (missing finally)
- ✅ Unit Tests: Use TemporaryDirectory context managers

#### Missing Test Coverage
- ❌ Integration tests for end-to-end download functionality
- ❌ File validation after download (format, metadata, size verification)
- ❌ Cleanup verification tests
- ❌ Performance/load testing for downloads
- ❌ Error scenario testing with cleanup verification
- ❌ GCS temp file cleanup in download tool

---

## Implementation Plan (MVP Scope)

**Focus**: Cleanup verification, basic validation, and test organization. Keep it simple and practical.

### Phase 1: Test Organization & Cleanup Fixes
**Goal**: Organize tests and fix cleanup issues in code

### Phase 2: Basic Integration Tests
**Goal**: Add simple integration tests with cleanup verification

### Phase 3: Basic Validation
**Goal**: Add simple file validation (exists, size, format extension)

---

## Task List

### Phase 1: Test Organization & Cleanup Fixes

#### T1.3: Improve Download Service Cleanup
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Create organized test directory structure for download tests

**Tasks**:
- [ ] Create `tests/integration/downloads/` directory
- [ ] Create `tests/functional/downloads/` directory
- [ ] Create `tests/integration/downloads/conftest.py` with shared fixtures
- [ ] Create `tests/functional/downloads/conftest.py` with shared fixtures

**Files to Create**:
- `tests/integration/downloads/__init__.py`
- `tests/integration/downloads/conftest.py`
- `tests/functional/downloads/__init__.py`
- `tests/functional/downloads/conftest.py`

**Testing**:
- Verify directories exist
- Verify pytest can discover tests in new directories
- Run: `pytest tests/integration/downloads/ -v --collect-only`

**Git Commit**:
```
feat(tests): create download test directory structure (LOI-17 T1.1)

- Create tests/integration/downloads/ directory
- Create tests/functional/downloads/ directory
- Add conftest.py files for shared fixtures
- Files: tests/integration/downloads/, tests/functional/downloads/
```

**Code Review Prompt**:
```
Please review the test directory structure for LOI-17 download test improvements.

Context:
- We're organizing download tests into integration/ and functional/ directories
- Each directory has a conftest.py for shared fixtures
- This follows pytest best practices for test organization

Files to review:
- tests/integration/downloads/conftest.py
- tests/functional/downloads/conftest.py

Check:
- Fixture organization makes sense
- No circular imports
- Fixtures are reusable and well-documented
```

---

#### T1.2: Create Base Test Fixtures
**Status**: ✅ **COMPLETED**
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Create reusable fixtures for download testing scenarios

**Tasks**:
- ✅ Add fixture for test audio track metadata (done in T1.1)
- ✅ Add fixture for temporary download directory (done in T1.1)
- ✅ Add fixture for GCS mock/stub (mock_gcs_client)
- ✅ Add fixture for download service instance (mock_download_service)
- ✅ Add fixture for cleanup verification helpers (cleanup_verifier)

**Files Modified**:
- `tests/integration/downloads/conftest.py` (added mock_gcs_client, mock_download_service)
- `tests/functional/downloads/conftest.py` (added mock_mcp_client, mock_http_client)

**Testing Completed**:
- ✅ Verified fixtures can be imported and used
- ✅ Run: `pytest tests/integration/downloads/ -v --fixtures`
- ✅ Verified all fixtures are available

**Git Commit**: `195ac25` - feat(tests): add base fixtures for download tests (LOI-17 T1.2)

**Code Review Prompt**:
```
Please review the base fixtures for download tests (LOI-17 T1.2).

Context:
- These fixtures will be used across all download integration and functional tests
- They need to handle cleanup automatically
- They should be reusable and well-documented

Files to review:
- tests/integration/downloads/conftest.py
- tests/functional/downloads/conftest.py

Check:
- Fixtures properly clean up resources
- No resource leaks
- Fixtures are documented with docstrings
- Error handling in fixtures is appropriate
```

---

### Phase 2: End-to-End Integration Tests

#### T2.1: Create End-to-End Download Test
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Add integration test for complete download flow with actual file downloads

**Tasks**:
- [ ] Create `test_download_end_to_end.py`
- [ ] Test MCP tool download flow (download_audio)
- [ ] Test HTTP API download flow (`/api/tracks/{audioId}/download`)
- [ ] Verify downloaded file exists and has correct format
- [ ] Verify cleanup happens after test

**Files to Create**:
- `tests/integration/downloads/test_download_end_to_end.py`

**Testing**:
- Run: `pytest tests/integration/downloads/test_download_end_to_end.py -v`
- Verify no temp files left behind after test
- Check logs for cleanup messages

**Git Commit**:
```
feat(tests): add end-to-end download integration test (LOI-17 T2.1)

- Test complete download flow via MCP tool
- Test complete download flow via HTTP API
- Verify file download and format correctness
- Verify automatic cleanup after test
- Files: tests/integration/downloads/test_download_end_to_end.py
```

**Code Review Prompt**:
```
Please review the end-to-end download integration test (LOI-17 T2.1).

Context:
- This test performs actual downloads (not mocked)
- It tests both MCP tool and HTTP API endpoints
- It must verify cleanup happens correctly

Files to review:
- tests/integration/downloads/test_download_end_to_end.py

Check:
- Test covers both MCP and HTTP API paths
- Cleanup is verified (no temp files left)
- Test uses appropriate fixtures
- Error handling is tested
- Test is deterministic and doesn't depend on external state
```

---

#### T2.2: Add Basic File Validation Helpers
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Create simple helper functions to validate downloaded files (basic checks only)

**Tasks**:
- [ ] Create `validate_file_exists()` helper
- [ ] Create `validate_file_size()` helper (non-zero, reasonable size)
- [ ] Create `validate_file_extension()` helper (matches expected format)

**Files to Create**:
- `tests/integration/downloads/validation_helpers.py`

**Testing**:
- Unit test each validation helper function
- Run: `pytest tests/integration/downloads/validation_helpers.py -v`

**Git Commit**:
```
feat(tests): add basic file validation helpers for download tests (LOI-17 T2.2)

- Add validate_file_exists() helper
- Add validate_file_size() helper (non-zero, reasonable size)
- Add validate_file_extension() helper (matches expected format)
- Files: tests/integration/downloads/validation_helpers.py
```

**Code Review Prompt**:
```
Please review the basic file validation helpers for download tests (LOI-17 T2.2).

Context:
- These helpers provide simple validation for downloaded files
- MVP scope: file exists, has reasonable size, correct extension
- No complex metadata parsing (can add later if needed)

Files to review:
- tests/integration/downloads/validation_helpers.py

Check:
- Validation logic is simple and correct
- Error messages are clear
- Functions are well-documented
- No unnecessary dependencies
```

---

### Phase 3: Validation & Cleanup Tests

#### T3.1: Create Cleanup Verification Test
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Test that all temp files are cleaned up after download operations

**Tasks**:
- [ ] Create `test_download_cleanup.py`
- [ ] Test cleanup after successful download
- [ ] Test cleanup after failed download
- [ ] Test cleanup after conversion error
- [ ] Test cleanup after timeout
- [ ] Verify GCS temp files are cleaned up (if applicable)

**Files to Create**:
- `tests/integration/downloads/test_download_cleanup.py`

**Testing**:
- Run: `pytest tests/integration/downloads/test_download_cleanup.py -v`
- Manually verify no temp files in `/tmp` after test run
- Check logs for cleanup messages

**Git Commit**:
```
feat(tests): add cleanup verification tests for downloads (LOI-17 T3.1)

- Test cleanup after successful downloads
- Test cleanup after errors and timeouts
- Verify temp files are removed
- Verify GCS temp files are cleaned up
- Files: tests/integration/downloads/test_download_cleanup.py
```

**Code Review Prompt**:
```
Please review the cleanup verification tests (LOI-17 T3.1).

Context:
- These tests ensure no temp files are left behind after downloads
- They test cleanup in both success and error scenarios
- They verify both local temp files and GCS temp files

Files to review:
- tests/integration/downloads/test_download_cleanup.py

Check:
- Cleanup verification is thorough
- Tests cover all error scenarios
- Tests verify both local and GCS cleanup
- No false positives (tests don't fail when cleanup works)
```

---

#### T3.2: Improve Download Service Cleanup
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Fix download service to ensure cleanup happens in finally block

**Tasks**:
- [ ] Review `src/services/download_service.py` cleanup logic
- [ ] Ensure cleanup happens in finally block (not just except)
- [ ] Add cleanup verification logging
- [ ] Test cleanup in error scenarios

**Files to Modify**:
- `src/services/download_service.py`

**Testing**:
- Run existing download service tests
- Run: `pytest tests/unit/test_download_service.py -v`
- Manually test error scenarios and verify cleanup

**Git Commit**:
```
fix(services): improve download service cleanup (LOI-17 T3.2)

- Ensure cleanup happens in finally block
- Add cleanup verification logging
- Test cleanup in error scenarios
- Files: src/services/download_service.py
```

**Code Review Prompt**:
```
Please review the download service cleanup improvements (LOI-17 T3.2).

Context:
- The download service currently only cleans up in except blocks
- We need to ensure cleanup happens in finally blocks
- This prevents resource leaks

Files to review:
- src/services/download_service.py

Check:
- Cleanup happens in finally blocks
- All temp resources are cleaned up
- Error handling doesn't prevent cleanup
- Logging is appropriate
- No resource leaks possible
```

---

#### T3.3: Improve MCP Tool Cleanup
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Review and improve cleanup in MCP download tool

**Tasks**:
- [ ] Review `src/tools/download_tool.py` cleanup logic
- [ ] Ensure synchronous cleanup doesn't block response
- [ ] Consider async cleanup or background task
- [ ] Add cleanup verification

**Files to Modify**:
- `src/tools/download_tool.py`

**Testing**:
- Run MCP tool tests
- Test download tool via MCP client
- Verify cleanup happens without blocking

**Git Commit**:
```
fix(tools): improve MCP download tool cleanup (LOI-17 T3.3)

- Review and improve cleanup logic
- Ensure cleanup doesn't block response
- Add cleanup verification
- Files: src/tools/download_tool.py
```

**Code Review Prompt**:
```
Please review the MCP download tool cleanup improvements (LOI-17 T3.3).

Context:
- The MCP tool currently does synchronous cleanup in finally block
- This could potentially block the response
- We need to ensure cleanup happens but doesn't delay response

Files to review:
- src/tools/download_tool.py

Check:
- Cleanup doesn't block response
- All temp files are cleaned up
- Error handling is appropriate
- Consider async cleanup if needed
```

---

### Phase 3: Basic Validation

#### T3.1: Add Basic File Validation Tests
**Status**: `todo`
**Branch**: `task/loi-17-improve-download-tests`
**Description**: Add simple tests to validate downloaded files (exists, size, extension)

**Tasks**:
- [ ] Create `test_download_validation.py`
- [ ] Test file exists after download
- [ ] Test file has non-zero size
- [ ] Test file extension matches requested format
- [ ] Use validation helpers from T2.2

**Files to Create**:
- `tests/integration/downloads/test_download_validation.py`

**Testing**:
- Run: `pytest tests/integration/downloads/test_download_validation.py -v`
- Test with a few different formats

**Git Commit**:
```
feat(tests): add basic file validation tests for downloads (LOI-17 T3.1)

- Test file exists and has non-zero size
- Test file extension matches requested format
- Use validation helpers
- Files: tests/integration/downloads/test_download_validation.py
```

**Code Review Prompt**:
```
Please review the basic file validation tests (LOI-17 T3.1).

Context:
- These tests verify basic file properties after download
- MVP scope: file exists, has size, correct extension
- Uses simple validation helpers (no complex metadata parsing)

Files to review:
- tests/integration/downloads/test_download_validation.py

Check:
- Tests are simple and focused
- Validation helpers are used appropriately
- Tests cover main formats
```

---

## Success Criteria (MVP)

- ✅ All download tests clean up temp files automatically
- ✅ Basic integration tests validate downloaded files (exists, size, extension)
- ✅ Test organization follows clear directory structure
- ✅ Cleanup happens in finally blocks (not just except)
- ✅ Cleanup verification tests ensure no temp files left behind

**Future Enhancements** (not in MVP scope):
- Advanced metadata validation (mutagen-based)
- Performance/load testing
- Complex error scenario testing
- Artwork embedding verification

## Files Reference

### Current Implementation
- `src/tools/download_tool.py` - MCP download tool
- `src/services/download_service.py` - Download service logic
- `src/http_api.py` - HTTP download endpoint
- `src/converter/` - Audio conversion logic

### Current Tests
- `tests/unit/test_download_service.py` - Unit tests (mocks)
- `tests/test_download_converter.py` - FFmpeg converter tests
- `tests/test_http_downloader.py` - HTTP downloader tests

### Documentation
- `docs/download-endpoint-api.md` - Download API documentation
- `docs/download-endpoint-investigation.md` - Download endpoint investigation

---

## Notes

- **MVP Scope**: Keep it simple - focus on cleanup verification and basic file validation
- All tests must be run locally and validated before committing
- Each task should be committed separately with descriptive commit messages
- Code review prompts should be provided for each task
- Tests should use fixtures from conftest.py for consistency
- Cleanup verification should be part of every test
- **Avoid over-engineering**: No complex metadata parsing, performance benchmarking, or advanced resource leak detection for MVP
- Future enhancements can add mutagen-based validation, performance tests, etc. if needed

