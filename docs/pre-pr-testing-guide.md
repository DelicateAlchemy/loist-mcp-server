# Pre-PR Testing Guide

This guide helps you test your changes locally before creating a pull request.

## 🚀 Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov=database --cov-report=term-missing

# Run specific test file
pytest tests/test_process_audio_complete.py -v
```

## 📋 Complete Testing Checklist

### 1. Unit Tests

Run all unit tests to verify individual components:

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run specific test categories
pytest tests/test_downloader*.py -v        # Downloader tests
pytest tests/test_metadata*.py -v          # Metadata tests
pytest tests/test_database*.py -v          # Database tests
pytest tests/test_process_audio*.py -v     # Integration tests
```

### 2. Code Coverage

Check test coverage to ensure good test coverage:

```bash
# Generate coverage report
pytest tests/ --cov=src --cov=database --cov-report=html --cov-report=term

# View HTML report (opens in browser)
open htmlcov/index.html
```

**Coverage Goals:**
- ✅ Aim for >80% coverage on new code
- ✅ Critical paths should have >90% coverage
- ⚠️ Some integration tests may require mocks for external services

### 3. Linting & Code Style

Ensure code follows project standards:

```bash
# Check code style with Black (currently not installed)
# black src/ tests/ --check

# Lint with Ruff (currently not installed)  
# ruff check src/ tests/

# For now, verify manually or install:
# pip install black ruff
```

### 4. Type Checking (Optional)

If using type hints:

```bash
# Install mypy if not already installed
# pip install mypy

# Run type checker
# mypy src/
```

### 5. Import Validation

Verify all imports work correctly:

```bash
# Test that modules can be imported
python -c "from src.tools import process_audio_complete; print('✅ Imports OK')"
python -c "from database import save_audio_metadata; print('✅ Database imports OK')"
python -c "from src.downloader import download_from_url; print('✅ Downloader imports OK')"
```

### 6. Quick Smoke Test

Run a subset of critical tests:

```bash
# Run only fast, critical tests
pytest tests/test_process_audio_complete.py::test_valid_input_schema -v
pytest tests/test_process_audio_complete.py::test_invalid_source_type -v
```

## 🧪 Test Categories

### Unit Tests (Fast, No Dependencies)

Tests individual functions without external dependencies:

```bash
pytest tests/test_url_validators.py -v
pytest tests/test_ssrf_protection.py -v
pytest tests/test_format_validation.py -v
```

### Integration Tests (May Require Mocking)

Tests that integrate multiple components:

```bash
pytest tests/test_process_audio_complete.py -v
pytest tests/test_http_downloader.py -v
pytest tests/test_metadata_extraction.py -v
```

### Database Tests (Require Database)

Tests that interact with PostgreSQL:

```bash
# These require database connection
pytest tests/test_database_pool.py -v
pytest tests/test_migrations.py -v
```

**Note:** Database tests may fail locally if you don't have PostgreSQL running. They will run in CI/CD.

### Storage Tests (Require GCS)

Tests that interact with Google Cloud Storage:

```bash
# These require GCS credentials
pytest tests/test_gcs_integration.py -v
pytest tests/test_audio_storage.py -v
```

**Note:** Storage tests may fail locally without GCS credentials. They will run in CI/CD.

## 🔧 Running Tests with Filters

### By Marker (if configured)

```bash
# Run only unit tests
pytest tests/ -v -m unit

# Run only integration tests  
pytest tests/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### By Test Name Pattern

```bash
# Run all validation tests
pytest tests/ -v -k "validation"

# Run all error handling tests
pytest tests/ -v -k "error"

# Run successful processing tests
pytest tests/ -v -k "successful"
```

### By File Pattern

```bash
# Run all downloader-related tests
pytest tests/test_*downloader*.py -v

# Run all metadata-related tests
pytest tests/test_*metadata*.py -v
```

## 📊 Understanding Test Output

### Success Example

```
tests/test_process_audio_complete.py::test_valid_input_schema PASSED     [100%]

========================= 1 passed in 0.05s =========================
```

### Failure Example

```
tests/test_process_audio_complete.py::test_invalid_source_type FAILED   [100%]

================================= FAILURES =================================
______________________ test_invalid_source_type _______________________

    def test_invalid_source_type():
        with pytest.raises(Exception):
>           ProcessAudioInput(**{...})
E           ValidationError: Invalid source type

tests/test_process_audio_complete.py:45: ValidationError
========================= 1 failed in 0.12s ========================
```

### Coverage Report Example

```
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
src/tools/process_audio.py          245     12    95%   156-158, 234-240
src/tools/schemas.py                 89      0   100%
---------------------------------------------------------------
TOTAL                               334     12    96%
```

## 🚨 Common Issues & Fixes

### Issue: ModuleNotFoundError

```bash
# Solution: Install package in development mode
pip install -e .
```

### Issue: Import Errors

```bash
# Solution: Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Issue: Database Connection Errors

```bash
# Solution: Skip database tests locally
pytest tests/ -v --ignore=tests/test_database_pool.py --ignore=tests/test_migrations.py
```

### Issue: Async Test Warnings

```bash
# Solution: pytest-asyncio should handle this automatically
# If issues persist, add to pyproject.toml:
# [tool.pytest.ini_options]
# asyncio_mode = "auto"
```

## ✅ Pre-PR Checklist

Before creating your PR, ensure:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Code coverage >80%: `pytest tests/ --cov=src --cov=database`
- [ ] No linting errors: `black --check src/ tests/` (if installed)
- [ ] All imports work: Test imports manually
- [ ] New features have tests
- [ ] Existing tests still pass
- [ ] Documentation updated (if applicable)
- [ ] Commit messages are clear and descriptive

## 🎯 Recommended Pre-PR Test Commands

Run these commands before creating a PR:

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Install/update dependencies
pip install -e .

# 3. Run all tests with coverage
pytest tests/ -v --cov=src --cov=database --cov-report=term-missing

# 4. Run only new tests (Task 7)
pytest tests/test_process_audio_complete.py -v

# 5. Test imports
python -c "from src.tools import process_audio_complete; print('✅ OK')"

# 6. Check for obvious errors
python -m py_compile src/tools/*.py
```

## 📈 CI/CD Comparison

Your local tests should match what runs in CI/CD:

| Test Type | Local | CI/CD |
|-----------|-------|-------|
| Unit Tests | ✅ Run locally | ✅ Run in CI |
| Integration Tests (mocked) | ✅ Run locally | ✅ Run in CI |
| Database Tests | ⚠️ May fail (no DB) | ✅ Run in CI (Cloud SQL) |
| Storage Tests | ⚠️ May fail (no GCS) | ✅ Run in CI (GCS access) |

**Tip:** Focus on unit and mocked integration tests locally. Full integration tests will run in CI/CD with proper infrastructure.

## 🔍 Debugging Failed Tests

### 1. Run with More Verbosity

```bash
pytest tests/test_process_audio_complete.py -vv --tb=long
```

### 2. Run Single Test

```bash
pytest tests/test_process_audio_complete.py::test_valid_input_schema -vv
```

### 3. Drop into Debugger on Failure

```bash
pytest tests/ --pdb
```

### 4. Print Debug Output

```bash
pytest tests/ -v -s  # -s shows print statements
```

### 5. Check Test Logs

```bash
pytest tests/ -v --log-cli-level=DEBUG
```

## 🎓 Best Practices

1. **Run tests frequently** - After each significant change
2. **Focus on what you changed** - Run related tests first
3. **Check coverage** - Ensure new code is tested
4. **Mock external services** - Don't rely on real GCS/DB for unit tests
5. **Test edge cases** - Include error scenarios
6. **Keep tests fast** - Use mocks to avoid slow operations
7. **Write descriptive test names** - Make failures easy to understand

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-mock Documentation](https://pytest-mock.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)

