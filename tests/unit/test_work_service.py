"""
Unit tests for the work_service layer.

These tests mock the repository to test the service's business logic in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services import work_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_work():
    """Mock work data with relations."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Test Song",
        "status": "draft",
        "language": "en",
        "writers": [],
        "publishers": [],
        "alternative_titles": [],
        "recordings": [],
        "warnings": [],
    }

@pytest.fixture
def mock_work_list():
    """Mock list of works from search."""
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Bohemian Rhapsody",
            "status": "draft",
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "title": "Bohemian Nights",
            "status": "draft",
        },
    ]

@pytest.fixture
def mock_writers():
    """Mock writer data for batch operations."""
    return [
        {
            "party_id": "party-1",
            "split_percentage": 50.0,
            "split_status": "confirmed",
        },
        {
            "party_id": "party-2",
            "split_percentage": 50.0,
            "split_status": "confirmed",
        },
    ]

@pytest.fixture
def mock_publishers():
    """Mock publisher data for batch operations."""
    return [
        {
            "party_id": "publisher-1",
            "split_percentage": 100.0,
            "split_status": "confirmed",
        },
    ]

# ============================================================================
# get_work Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_get_work_success(mock_get_repo, mock_work):
    """Test successful work retrieval in the service."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = mock_work
    mock_get_repo.return_value = mock_repo
    
    result = await work_service.get_work("any_id")
    
    mock_repo.get_by_id.assert_called_once_with("any_id")
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["title"] == "Test Song"
    assert "writers" in result
    assert "publishers" in result
    assert "warnings" in result

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_get_work_not_found(mock_get_repo):
    """Test that ResourceNotFoundError is raised for a missing work."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(ResourceNotFoundError):
        await work_service.get_work("not_found_id")
    
    mock_repo.get_by_id.assert_called_once_with("not_found_id")

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_get_work_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.side_effect = DatabaseOperationError("Connection failed")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await work_service.get_work("any_id")

# ============================================================================
# create_work Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_create_work_success(mock_get_repo, mock_work):
    """Test successful work creation in the service."""
    mock_repo = MagicMock()
    mock_repo.create.return_value = mock_work
    mock_get_repo.return_value = mock_repo
    
    work_data = {
        "title": "Test Song",
        "status": "draft",
        "language": "en",
    }
    
    result = await work_service.create_work(work_data)
    
    mock_repo.create.assert_called_once_with(work_data)
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["title"] == "Test Song"

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_create_work_db_error(mock_get_repo):
    """Test that DatabaseOperationError is raised on creation failure."""
    mock_repo = MagicMock()
    mock_repo.create.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo
    
    work_data = {"title": "Test Song"}
    
    with pytest.raises(DatabaseOperationError):
        await work_service.create_work(work_data)

# ============================================================================
# search_works Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_search_works_success(mock_get_repo, mock_work_list):
    """Test successful work search in the service."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = mock_work_list
    mock_get_repo.return_value = mock_repo
    
    result = await work_service.search_works("Bohemian", limit=20, offset=0)
    
    mock_repo.search.assert_called_once_with("Bohemian", limit=20, offset=0)
    assert len(result["results"]) == 2
    assert result["total"] == 2
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["has_more"] is False  # len(results) < limit

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_search_works_has_more(mock_get_repo):
    """Test search with has_more flag when results equal limit."""
    mock_repo = MagicMock()
    # Return exactly limit number of results
    mock_repo.search.return_value = [{"id": f"id-{i}"} for i in range(20)]
    mock_get_repo.return_value = mock_repo
    
    result = await work_service.search_works("test", limit=20, offset=0)
    
    assert result["has_more"] is True  # len(results) == limit

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_search_works_db_error(mock_get_repo):
    """Test that DatabaseOperationError is propagated from search."""
    mock_repo = MagicMock()
    mock_repo.search.side_effect = Exception("Search failed")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await work_service.search_works("test", limit=20, offset=0)

# ============================================================================
# update_work_writers Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_writers_success(mock_get_repo, mock_writers):
    """Test successful writer update in the service."""
    mock_repo = MagicMock()
    mock_repo.replace_writers.return_value = {
        "replaced_count": 2,
        "work_id": "work-1",
    }
    mock_get_repo.return_value = mock_repo
    
    result = await work_service.update_work_writers("work-1", mock_writers)
    
    mock_repo.replace_writers.assert_called_once_with("work-1", mock_writers)
    assert result["replaced_count"] == 2
    assert result["work_id"] == "work-1"

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_writers_not_found(mock_get_repo, mock_writers):
    """Test that ResourceNotFoundError is propagated."""
    mock_repo = MagicMock()
    mock_repo.replace_writers.side_effect = ResourceNotFoundError("Work not found")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(ResourceNotFoundError):
        await work_service.update_work_writers("work-1", mock_writers)

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_writers_db_error(mock_get_repo, mock_writers):
    """Test that DatabaseOperationError is raised on update failure."""
    mock_repo = MagicMock()
    mock_repo.replace_writers.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await work_service.update_work_writers("work-1", mock_writers)

# ============================================================================
# update_work_publishers Tests
# ============================================================================

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_publishers_success(mock_get_repo, mock_publishers):
    """Test successful publisher update in the service."""
    mock_repo = MagicMock()
    mock_repo.replace_publishers.return_value = {
        "replaced_count": 1,
        "work_id": "work-1",
    }
    mock_get_repo.return_value = mock_repo
    
    result = await work_service.update_work_publishers("work-1", mock_publishers)
    
    mock_repo.replace_publishers.assert_called_once_with("work-1", mock_publishers)
    assert result["replaced_count"] == 1
    assert result["work_id"] == "work-1"

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_publishers_not_found(mock_get_repo, mock_publishers):
    """Test that ResourceNotFoundError is propagated."""
    mock_repo = MagicMock()
    mock_repo.replace_publishers.side_effect = ResourceNotFoundError("Work not found")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(ResourceNotFoundError):
        await work_service.update_work_publishers("work-1", mock_publishers)

@pytest.mark.asyncio
@patch('src.services.work_service.get_work_repository')
async def test_update_work_publishers_db_error(mock_get_repo, mock_publishers):
    """Test that DatabaseOperationError is raised on update failure."""
    mock_repo = MagicMock()
    mock_repo.replace_publishers.side_effect = Exception("Database error")
    mock_get_repo.return_value = mock_repo
    
    with pytest.raises(DatabaseOperationError):
        await work_service.update_work_publishers("work-1", mock_publishers)

