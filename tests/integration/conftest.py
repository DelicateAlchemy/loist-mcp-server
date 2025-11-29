"""
Integration test configuration.

Integration tests verify that multiple components work together correctly.
They may include database interactions, external service calls, and component integration.
"""

import pytest
from unittest.mock import patch

# Integration tests can use database fixtures and external service mocks

@pytest.fixture(scope="session")
def integration_config():
    """Configuration specifically for integration tests."""
    return {
        'use_real_services': False,  # Set to True for full integration testing
        'database_required': True,
        'external_services_required': False
    }


@pytest.fixture(autouse=True)
def mock_external_apis(integration_config):
    """Mock external APIs for integration testing."""
    if not integration_config['external_services_required']:
        # Mock external API calls
        with patch('httpx.Client') as mock_client, \
             patch('google.cloud.storage.Client') as mock_gcs:
            mock_client.return_value = mock_client
            mock_gcs.return_value = mock_gcs
            yield
    else:
        yield
