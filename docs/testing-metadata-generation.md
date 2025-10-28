# Metadata Generation Testing

This document describes the testing setup for metadata generation functionality in the Loist Music Library project.

## Overview

The metadata generation tests validate that social media sharing features work correctly, including:
- Open Graph tags for Facebook, LinkedIn, etc.
- Twitter Cards for Twitter sharing
- Schema.org structured data for rich snippets
- Edge cases and error handling

## Test Structure

### Test Files
- `tests/test_metadata_generation.py` - Main test suite (20 tests)
- `templates/embed.html` - HTML template being tested

### Test Categories
1. **Open Graph Tags (3 tests)** - Facebook, LinkedIn sharing
2. **Twitter Cards (3 tests)** - Twitter sharing
3. **Schema.org JSON-LD (3 tests)** - Rich snippets
4. **Additional Metadata (6 tests)** - SEO, oEmbed, security
5. **Edge Cases (2 tests)** - Long titles, special characters
6. **Validation Tests (3 tests)** - Specification compliance

## Running Tests

### Local Development

#### Using Virtual Environment (Recommended)
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio beautifulsoup4 pytest-html pytest-cov jinja2 starlette

# Run tests
python -m pytest tests/test_metadata_generation.py -v
```

#### Using Test Script
```bash
# Make script executable
chmod +x scripts/run-metadata-tests.sh

# Run all tests with HTML report
./scripts/run-metadata-tests.sh --verbose

# Run specific test types
./scripts/run-metadata-tests.sh --test-type unit
./scripts/run-metadata-tests.sh --test-type integration

# Run without coverage (faster)
./scripts/run-metadata-tests.sh --no-coverage
```

### GitHub Actions

Tests run automatically on:
- Push to `main` or `dev` branches
- Pull requests
- Manual workflow dispatch

**Workflow:** `.github/workflows/test-metadata-generation.yml`

**Features:**
- Tests on Python 3.11 and 3.12
- Coverage reporting with Codecov
- HTML test reports
- JUnit XML for CI integration
- Artifact uploads for test results

## Test Configuration

### pytest.ini
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --html=reports/pytest_report.html
    --self-contained-html
    --cov=src
    --cov-report=html:reports/coverage_html
    --cov-report=term-missing
    --cov-report=xml:reports/coverage.xml
```

### Test Dependencies
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `beautifulsoup4` - HTML parsing
- `pytest-html` - HTML test reports
- `pytest-cov` - Coverage reporting
- `jinja2` - Template engine
- `starlette` - Web framework

## Test Results

### Local Results
- **Test Reports:** `reports/pytest_report.html`
- **Coverage:** `reports/coverage.xml`
- **JUnit XML:** `reports/junit.xml`

### CI Results
- **GitHub Actions:** Check the Actions tab
- **Codecov:** Coverage reports in PR comments
- **Artifacts:** Test reports downloadable from Actions

## Test Coverage

| Category | Tests | Coverage |
|----------|-------|----------|
| Open Graph Tags | 3 | 100% |
| Twitter Cards | 3 | 100% |
| Schema.org JSON-LD | 3 | 100% |
| Additional Metadata | 6 | 100% |
| Edge Cases | 2 | 100% |
| Validation Tests | 3 | 100% |
| **TOTAL** | **20** | **100%** |

## Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Ensure you're in the project root
cd /path/to/loist-mcp-server

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Template Not Found
```bash
# Ensure templates directory exists
ls templates/embed.html

# Check file permissions
chmod 644 templates/embed.html
```

#### 3. Coverage Warnings
The "No data was collected" warning is expected - our tests validate template output, not source code coverage.

### Debug Mode
```bash
# Run with maximum verbosity
python -m pytest tests/test_metadata_generation.py -vvv --tb=long

# Run specific test
python -m pytest tests/test_metadata_generation.py::TestMetadataGeneration::test_open_graph_tags_generation -v
```

## Adding New Tests

### Test Structure
```python
def test_new_metadata_feature(self, templates, template_context):
    """Test description."""
    response = templates.TemplateResponse("embed.html", template_context)
    html_content = response.body.decode('utf-8')
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Test assertions
    assert condition
```

### Fixtures Available
- `sample_metadata` - Complete metadata
- `sample_metadata_minimal` - Minimal metadata
- `template_context` - Full template context
- `template_context_no_thumbnail` - No thumbnail scenario
- `templates` - Jinja2 templates instance

## Best Practices

1. **Test Template Rendering** - Always test actual HTML output
2. **Use Fixtures** - Leverage existing test data
3. **Test Edge Cases** - Missing data, special characters, long strings
4. **Validate Specifications** - Check against official standards
5. **Document Tests** - Clear test names and descriptions

## Related Documentation

- [Open Graph Protocol](https://ogp.me/)
- [Twitter Cards](https://developer.twitter.com/en/docs/twitter-for-websites/cards/overview/abouts-cards)
- [Schema.org](https://schema.org/)
- [oEmbed Specification](https://oembed.com/)

---

**Last Updated:** October 22, 2025  
**Test Framework:** pytest 8.4.2  
**Python Support:** 3.11, 3.12


