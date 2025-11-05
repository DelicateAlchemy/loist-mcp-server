"""
Unit test configuration.

Unit tests focus on individual functions, methods, and classes in isolation.
They should not depend on external services, databases, or network calls.
"""

import pytest

# Unit tests can use the base fixtures from the parent conftest.py
# Additional unit-specific fixtures can be added here if needed

@pytest.fixture
def mock_external_service():
    """Mock external service for unit testing."""
    from unittest.mock import Mock
    return Mock()
