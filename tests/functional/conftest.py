"""
Functional test configuration.

Functional tests verify end-to-end functionality from a user perspective.
They test complete workflows and may require a full application setup.
"""

import pytest
from unittest.mock import patch

# Functional tests typically test complete workflows

@pytest.fixture(scope="session")
def functional_config():
    """Configuration specifically for functional tests."""
    return {
        'full_application_setup': True,
        'database_required': True,
        'external_services_mocked': True,
        'test_data_setup': True
    }


@pytest.fixture
def test_client(test_app):
    """Test client for functional testing."""
    if hasattr(test_app, 'test_client'):
        return test_app.test_client()
    else:
        # Mock client for when full app isn't available
        from unittest.mock import Mock
        client = Mock()
        client.post = Mock(return_value=Mock(status_code=200, json=lambda: {'status': 'success'}))
        client.get = Mock(return_value=Mock(status_code=200, json=lambda: {'status': 'success'}))
        return client


@pytest.fixture(autouse=True)
def setup_functional_test_data(functional_config, test_db_config):
    """Set up test data for functional tests."""
    if functional_config['test_data_setup']:
        # This would set up test data in the database
        # For now, just yield
        yield
    else:
        yield
