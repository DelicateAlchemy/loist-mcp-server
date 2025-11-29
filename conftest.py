"""
Root conftest.py for pytest configuration and automatic marker assignment.

This file provides automatic marker assignment based on test file names and function names,
eliminating the need to manually add markers to hundreds of test files.
"""

import pytest
import os
from typing import List


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """
    Automatically assign markers based on test file paths and function names.

    This hook runs during test collection and applies markers automatically,
    making the test suite much more maintainable.
    """
    for item in items:
        # Database tests - by file name
        if any(pattern in str(item.fspath) for pattern in [
            'test_database_pool.py',
            'test_database_operations_integration.py',
            'test_data_integrity_validation.py',
            'test_migrations.py',
            'test_transaction_advanced.py',
            'test_database_testing_infrastructure.py',
            'test_database_testing_examples.py',
            'database_testing.py',
            'test_full_text_search.py',
            'test_resources.py',
            'test_real_gcs_integration.py',
            'test_query_tools.py',  # Uses database repository
            'test_oembed_endpoint.py',  # Queries database for audio
            'test_process_audio_complete.py',  # Saves to database
        ]):
            item.add_marker(pytest.mark.requires_db)

        # GCS tests - by file name or function name
        if any(pattern in str(item.fspath) for pattern in [
            'test_audio_storage.py',
            'test_gcs_operations.py'
        ]) or 'gcs' in item.name.lower():
            item.add_marker(pytest.mark.requires_gcs)

        # Static analysis tool tests - require tools to be installed
        if any(pattern in str(item.fspath) for pattern in [
            'test_static_analysis_tools.py',
            'test_security_scanning_validation.py',
        ]):
            item.add_marker(pytest.mark.requires_tools)

        # Slow tests - by function name patterns
        if any(pattern in item.name.lower() for pattern in [
            'performance', 'stress', 'load', 'concurrent', 'timing'
        ]):
            item.add_marker(pytest.mark.slow)

        # Unit tests - everything else that's not marked as integration
        if not any(marker.name in ['requires_db', 'requires_gcs'] for marker in item.own_markers):
            item.add_marker(pytest.mark.unit)


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure custom markers for the test suite.
    """
    config.addinivalue_line(
        "markers", "requires_db: marks tests requiring database connectivity"
    )
    config.addinivalue_line(
        "markers", "requires_gcs: marks tests requiring Google Cloud Storage"
    )
    config.addinivalue_line(
        "markers", "requires_external: marks tests requiring external services/APIs"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "requires_tools: marks tests requiring static analysis tools (black, isort, etc.)"
    )


