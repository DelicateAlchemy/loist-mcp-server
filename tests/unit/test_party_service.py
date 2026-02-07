"""
Unit tests for the party_service layer.

These tests mock the repository to test the service's business logic in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services import party_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_party():
    """Mock party data."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "John Smith",
        "party_type": "person",
        "email": "john@example.com",
        "ipi_cae_number": "12345678901",
        "works_as_writer": [],
        "works_as_publisher": [],
        "recordings_as_artist": [],
    }

@pytest.fixture
def mock_party_list():
    """Mock list of parties from search."""
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "John Smith",
            "party_type": "person",
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "name": "Jane Smith",
            "party_type": "person",
        },
    ]

# ============================================================================
# get_party Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_get_party_success(mock_get_repo, mock_party):
    """Test successful party retrieval in the service."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = mock_party
    mock_get_repo.return_value = mock_repo
    
    result = await party_service.get_party("any_id")
    
    mock_repo.get_by_id.assert_called_once_with("any_id")
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "John Smith"

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_get_party_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised for a missing party."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(ResourceNotFoundError):
        await party_service.get_party("not_found_id")
    
    mock_repo.get_by_id.assert_called_once_with("not_found_id")

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_get_party_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.side_effect = DatabaseOperationError("Connection failed")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await party_service.get_party("any_id")

# ============================================================================
# create_party Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_create_party_success(mock_get_repo, mock_party):
    """Test successful party creation in the service."""
    mock_repo = MagicMock()
    mock_repo.create.return_value = mock_party
    mock_get_repo.return_value = mock_repo
    
    party_data = {
        "name": "John Smith",
        "party_type": "person",
        "email": "john@example.com",
    }
    
    result = await party_service.create_party(party_data)
    
    mock_repo.create.assert_called_once_with(party_data)
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["name"] == "John Smith"

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_create_party_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on creation failure."""
    mock_repo = MagicMock()
    mock_repo.create.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo
    
    party_data = {"name": "John Smith"}
    
    with pytest.raises(DatabaseOperationError):
        await party_service.create_party(party_data)

# ============================================================================
# search_parties Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_search_parties_success(mock_get_repo, mock_party_list):
    """Test successful party search in the service."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = mock_party_list
    mock_get_repo.return_value = mock_repo
    
    result = await party_service.search_parties("Smith", limit=20, offset=0)
    
    mock_repo.search.assert_called_once_with("Smith", limit=20, offset=0)
    assert len(result["results"]) == 2
    assert result["total"] == 2
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["has_more"] is False  # len(results) < limit

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_search_parties_has_more(mock_get_repo):
    """Test search with has_more flag when results equal limit."""
    mock_repo = MagicMock()
    # Return exactly limit number of results
    mock_repo.search.return_value = [{"id": f"id-{i}"} for i in range(20)]
    mock_get_repo.return_value = mock_repo
    
    result = await party_service.search_parties("test", limit=20, offset=0)
    
    assert result["has_more"] is True  # len(results) == limit

@pytest.mark.asyncio
@patch('src.services.party_service.get_party_repository')
async def test_search_parties_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated from search."""
    mock_repo = MagicMock()
    mock_repo.search.side_effect = Exception("Search failed")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await party_service.search_parties("test", limit=20, offset=0)

