# LOI-18: Document and Fix Test Inconsistencies for Local Development

**Linear Issue**: [LOI-18](https://linear.app/loist/issue/LOI-18/document-and-fix-test-inconsistencies-for-local-development)  
**Branch**: `info/loi-18-document-and-fix-test-inconsistencies-for-local-development`  
**Created**: 2025-12-09  
**Status**: In Progress

---

## Problem Summary

Unit tests have inconsistent behavior between local Docker Compose and CI environments. Currently:
- **129 tests fail** in Docker locally
- **659 tests pass** in Docker locally
- Tests fail instead of skipping appropriately when dependencies are unavailable

---

## Task List

### Phase 1: Fix Import Path Conflict (BLOCKING)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P1.1 | Fix conftest.py import path mismatch | todo | `tests/integration/downloads/conftest.py` conflicts with `tests/functional/downloads/conftest.py` |
| P1.2 | Verify test collection works after fix | todo | Run `pytest --collect-only` |

---

### Phase 2: Fix Static Analysis Test File Permissions

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P2.1 | Modify `test_black_configuration` to use `/tmp` | todo | Change `Path("test_black_format.py")` to `Path("/tmp/test_black_format.py")` |
| P2.2 | Modify `test_isort_configuration` to use `/tmp` | todo | Change `Path("test_isort_imports.py")` to `Path("/tmp/test_isort_imports.py")` |
| P2.3 | Modify `test_flake8_configuration` to use `/tmp` | todo | Change `Path("test_flake8_lint.py")` to `Path("/tmp/test_flake8_lint.py")` |
| P2.4 | Modify `test_mypy_configuration` to use `/tmp` | todo | Change `Path("test_mypy_types.py")` to `Path("/tmp/test_mypy_types.py")` |
| P2.5 | Modify `test_pylint_configuration` to use `/tmp` | todo | Change `Path("test_pylint_analyze.py")` to `Path("/tmp/test_pylint_analyze.py")` |
| P2.6 | Add `@pytest.mark.requires_tools` marker to entire file | todo | Add to file header or each class |
| P2.7 | Verify static analysis tests pass in Docker | todo | Run tests in container |

---

### Phase 3: Register Missing Pytest Markers

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P3.1 | Add `regression` marker to `pytest.ini` | todo | Used in `test_regression_tasks_13_14.py` |
| P3.2 | Add `tasks_13_14` marker to `pytest.ini` | todo | Used in `test_regression_tasks_13_14.py` |
| P3.3 | Add `functional` marker to `pytest.ini` | todo | Used in `test_smoke.py` |
| P3.4 | Verify no unknown marker warnings | todo | Run `pytest --collect-only` |

---

### Phase 4: Apply Markers to Tests That Need External Dependencies

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P4.1 | Add `@pytest.mark.requires_db` to database tests | todo | See list below |
| P4.2 | Add `@pytest.mark.requires_gcs` to GCS tests | todo | See list below |
| P4.3 | Add `@pytest.mark.requires_tools` to tool tests | todo | See list below |
| P4.4 | Add `@pytest.mark.slow` to slow tests | todo | Optional |

**Tests needing `@pytest.mark.requires_db`:**
- `tests/test_update_metadata.py`
- `tests/test_database_operations_integration.py`
- `tests/test_database_pool.py`
- `tests/test_full_text_search.py`
- `tests/test_transaction_advanced.py`
- `tests/test_migrations.py`
- `tests/integration/test_api_endpoints.py`
- `tests/integration/test_resource_db_connectivity.py`

**Tests needing `@pytest.mark.requires_gcs`:**
- `tests/test_real_gcs_integration.py`
- `tests/test_audio_storage.py`
- `tests/test_gcs_integration.py`

**Tests needing `@pytest.mark.requires_tools`:**
- `tests/test_static_analysis_tools.py`
- `tests/test_security_scanning_validation.py`

---

### Phase 5: Update pytest.ini Configuration

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P5.1 | Verify all markers are properly registered | todo | Check `pytest.ini` markers section |
| P5.2 | Add marker descriptions | todo | Add clear descriptions for each marker |
| P5.3 | Configure default filter for local development | todo | Consider adding `-m "not (requires_db or requires_gcs)"` |

---

### Phase 6: Update Test Documentation

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P6.1 | Update `tests/README.md` with marker usage guide | todo | Document all markers |
| P6.2 | Add section about expected skip behavior | todo | Explain when tests skip vs fail |
| P6.3 | Add local development testing instructions | todo | Docker-specific guidance |

---

### Phase 7: Verification

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P7.1 | Run full test suite with markers excluded | todo | `pytest -m "not (requires_db or requires_gcs or requires_tools)"` |
| P7.2 | Verify remaining tests pass or skip appropriately | todo | Target: 0 failures for unit tests |
| P7.3 | Document final test counts | todo | Update this file with results |

---

## Detailed Instructions for Each Task

### P1.1: Fix conftest.py Import Path Mismatch

**Problem**: Two `downloads` directories both have `conftest.py` files, causing pytest to confuse them.

```
tests/integration/downloads/conftest.py  <- Integration fixtures
tests/functional/downloads/conftest.py   <- Functional fixtures
```

**Error**: `ImportPathMismatchError: ('downloads.conftest', ...)`

**RECOMMENDED SOLUTION**: Add `__init__.py` files to make proper Python packages.

**Steps**:
1. Create `tests/integration/downloads/__init__.py` with empty content or docstring
2. Create `tests/functional/downloads/__init__.py` with empty content or docstring
3. Create `tests/integration/__init__.py` if it doesn't exist
4. Create `tests/functional/__init__.py` if it doesn't exist
5. Verify with: `docker-compose exec mcp-server python -m pytest tests/ --collect-only 2>&1 | grep "ERROR"`

**File contents for __init__.py**:
```python
"""Downloads test package."""
```

**Alternative if __init__.py doesn't work**: Rename directories to be unique:
- `tests/integration/downloads/` → `tests/integration/integration_downloads/`
- Update any imports accordingly

---

### P2.1-P2.5: Fix Static Analysis Test File Paths

**File**: `tests/test_static_analysis_tools.py`

**Pattern to fix**:

BEFORE:
```python
test_file = Path("test_black_format.py")
```

AFTER:
```python
test_file = Path("/tmp/test_black_format.py")
```

**Do this for ALL temporary file paths in the file** (search for `Path("test_`).

---

### P2.6: Add requires_tools Marker

**File**: `tests/test_static_analysis_tools.py`

Add at the top of the file (after imports):
```python
import pytest

pytestmark = pytest.mark.requires_tools
```

This applies the marker to ALL tests in the file.

---

### P3.1-P3.3: Register Missing Markers

**File**: `pytest.ini`

Add to the `markers` section:
```ini
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    metadata: Metadata generation tests
    social: Social media sharing tests
    asyncio: Async tests using pytest-asyncio
    requires_db: Tests requiring database connection
    requires_gcs: Tests requiring Google Cloud Storage
    requires_tools: Tests requiring static analysis tools (black, isort, etc.)
    regression: Regression tests for fixed bugs
    tasks_13_14: Tests related to tasks 13 and 14
    functional: End-to-end functional tests
```

---

### P4.1-P4.3: Apply Markers to Tests

**Template for adding markers to a test file**:

Add at the top of the file (after imports):
```python
pytestmark = pytest.mark.requires_db  # or requires_gcs or requires_tools
```

OR add to specific test classes:
```python
@pytest.mark.requires_db
class TestDatabaseOperations:
    ...
```

---

### P5.1-P5.3: Verify pytest.ini Configuration

**Final pytest.ini markers section should look like**:
```ini
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (may require external services)
    functional: End-to-end functional tests
    slow: Slow running tests (>5 seconds)
    metadata: Metadata generation tests
    social: Social media sharing tests
    asyncio: Async tests using pytest-asyncio
    requires_db: Tests requiring PostgreSQL database connection
    requires_gcs: Tests requiring Google Cloud Storage access
    requires_tools: Tests requiring static analysis tools (black, isort, mypy, etc.)
    regression: Regression tests for previously fixed bugs
    tasks_13_14: Tests related to tasks 13 and 14
```

---

## Commands Reference

### Run Tests Without External Dependencies
```bash
docker-compose exec mcp-server python -m pytest tests/ \
  -m "not (requires_db or requires_gcs or requires_tools)" \
  -v --tb=short
```

### Collect Tests Only (No Execution)
```bash
docker-compose exec mcp-server python -m pytest tests/ --collect-only
```

### Run Tests With Specific Marker
```bash
docker-compose exec mcp-server python -m pytest tests/ -m "unit" -v
```

### Check for Unknown Markers
```bash
docker-compose exec mcp-server python -m pytest tests/ --collect-only 2>&1 | grep "Unknown"
```

---

## Success Criteria

1. **All tests pass or skip appropriately** in Docker Compose environment
2. **No unknown marker warnings** during test collection
3. **Test markers are implemented** and functional
4. **Clear documentation** for test requirements exists
5. **CI pipeline unaffected** by changes (cloudbuild.yaml already uses correct markers)

---

## Notes for Agent

- **ALWAYS use Docker** for testing: `docker-compose exec mcp-server python -m pytest ...`
- **DO NOT modify cloudbuild.yaml** - it already has the correct marker filters
- **Test incrementally** after each change
- **Commit after completing each phase** (not each task)
- **Focus on making tests SKIP gracefully** when dependencies unavailable, not on making them pass

---

## Current Status

| Metric | Value | Target |
|--------|-------|--------|
| Tests Failing | 129 | 0 (for unit tests without markers) |
| Tests Passing | 659 | All applicable |
| Unknown Markers | 4 | 0 |
| Tests with proper markers | ~20% | 100% |

---

**Last Updated**: 2025-12-09

