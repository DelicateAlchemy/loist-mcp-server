"""
Smoke test to verify pytest framework setup.

This test validates that:
- pytest is properly installed and configured
- Basic fixtures are working
- Test discovery is functioning
- No import errors in the test environment
"""

import pytest

def test_pytest_framework():
    """Basic smoke test for pytest framework."""
    assert True, "Pytest framework is working"


def test_basic_assertions():
    """Test basic assertion functionality."""
    assert 1 + 1 == 2
    assert "test" in "testing"
    assert len([1, 2, 3]) == 3


def test_fixture_injection(sample_audio_metadata):
    """Test that fixtures are properly injected."""
    assert sample_audio_metadata is not None
    assert "id" in sample_audio_metadata
    assert "title" in sample_audio_metadata


def test_environment_setup():
    """Test that test environment variables are set."""
    import os
    assert os.environ.get('LOG_LEVEL') == 'WARNING'
    assert os.environ.get('AUTH_ENABLED') == 'false'


@pytest.mark.unit
def test_unit_marker():
    """Test that unit test markers work."""
    assert True


@pytest.mark.integration
def test_integration_marker():
    """Test that integration test markers work."""
    assert True


@pytest.mark.functional
def test_functional_marker():
    """Test that functional test markers work."""
    assert True
