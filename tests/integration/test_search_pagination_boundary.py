"""
Integration tests for search endpoint pagination boundary conditions.

Tests the fix for LOI-12: Search Endpoint Pagination Bug (High Priority)
where limit=100 would fail due to database rejecting limit > 100.
"""

import pytest
from unittest.mock import patch

from src.services import audio_service
from database.operations import ValidationError


class TestSearchPaginationBoundary:
    """
    Test pagination boundary conditions that caused the LOI-12 bug.

    The bug occurred when limit=100 because the service would fetch limit+1=101 results,
    but the database enforces a hard limit of 100. This test suite validates the fix.
    """

    @pytest.mark.asyncio
    @patch('src.services.audio_service.filter_audio_tracks_combined')
    @patch('src.services.audio_service.get_xmp_field_facets')
    async def test_search_limit_99_standard_approach(self, mock_get_facets, mock_db_call):
        """
        Test that limit=99 works with the standard +1 approach.

        This should fetch 100 results and use len(results) > limit for has_more.
        """
        # Mock response with exactly 100 results (would be 99 + 1 extra for has_more check)
        mock_response = {
            'tracks': [
                {
                    "id": f"track-{i}",
                    "artist": f"Artist {i}",
                    "title": f"Title {i}",
                    "album": f"Album {i}",
                    "duration_seconds": 180.0,
                    "format": "MP3",
                    "rank": 0.9,
                }
                for i in range(100)  # 100 results = 99 + 1 extra
            ],
            'total_count': 150,  # More results exist
        }
        mock_db_call.return_value = mock_response
        mock_get_facets.return_value = {}

        # Test limit=99 (should use +1 approach)
        result = await audio_service.search_audio_library("test query", limit=99, offset=0)

        # Verify database was called with limit=100 (99 + 1)
        mock_db_call.assert_called_once()
        call_args = mock_db_call.call_args
        assert call_args.kwargs['limit'] == 100  # 99 + 1

        # Verify results: should return exactly 99 results (trimmed the extra)
        assert len(result['results']) == 99
        assert result['has_more'] is True  # len(100) > 99, so has_more=True
        assert result['total'] == 150
        assert result['limit'] == 99

    @pytest.mark.asyncio
    @patch('src.services.audio_service.filter_audio_tracks_combined')
    @patch('src.services.audio_service.get_xmp_field_facets')
    async def test_search_limit_100_boundary_approach(self, mock_get_facets, mock_db_call):
        """
        Test that limit=100 works with the count-based approach (the bug fix).

        This should fetch exactly 100 results and use total_count for has_more.
        """
        # Mock response with exactly 100 results
        mock_response = {
            'tracks': [
                {
                    "id": f"track-{i}",
                    "artist": f"Artist {i}",
                    "title": f"Title {i}",
                    "album": f"Album {i}",
                    "duration_seconds": 180.0,
                    "format": "MP3",
                    "rank": 0.9,
                }
                for i in range(100)  # Exactly 100 results
            ],
            'total_count': 150,  # More results exist
        }
        mock_db_call.return_value = mock_response
        mock_get_facets.return_value = {}

        # Test limit=100 (should use count-based approach)
        result = await audio_service.search_audio_library("test query", limit=100, offset=0)

        # Verify database was called with limit=100 (no +1 overflow)
        mock_db_call.assert_called_once()
        call_args = mock_db_call.call_args
        assert call_args.kwargs['limit'] == 100  # No overflow

        # Verify results: should return exactly 100 results (no trimming needed)
        assert len(result['results']) == 100
        assert result['has_more'] is True  # (0 + 100) < 150, so has_more=True
        assert result['total'] == 150
        assert result['limit'] == 100

    @pytest.mark.asyncio
    @patch('src.services.audio_service.filter_audio_tracks_combined')
    @patch('src.services.audio_service.get_xmp_field_facets')
    async def test_search_limit_100_has_more_false_at_boundary(self, mock_get_facets, mock_db_call):
        """
        Test that limit=100 correctly sets has_more=False when at the end.

        When offset + limit >= total_count, there should be no more results.
        """
        # Mock response with exactly 100 results (total matches = 100)
        mock_response = {
            'tracks': [
                {
                    "id": f"track-{i}",
                    "artist": f"Artist {i}",
                    "title": f"Title {i}",
                    "album": f"Album {i}",
                    "duration_seconds": 180.0,
                    "format": "MP3",
                    "rank": 0.9,
                }
                for i in range(100)
            ],
            'total_count': 100,  # Exactly at the boundary
        }
        mock_db_call.return_value = mock_response
        mock_get_facets.return_value = {}

        # Test limit=100 with no more results
        result = await audio_service.search_audio_library("test query", limit=100, offset=0)

        # Verify results
        assert len(result['results']) == 100
        assert result['has_more'] is False  # (0 + 100) >= 100, so has_more=False
        assert result['total'] == 100
        assert result['limit'] == 100

    @pytest.mark.asyncio
    @patch('src.services.audio_service.filter_audio_tracks_combined')
    @patch('src.services.audio_service.get_xmp_field_facets')
    async def test_search_limit_100_with_offset_has_more_logic(self, mock_get_facets, mock_db_call):
        """
        Test has_more logic with limit=100 and offset.

        When offset=50 and limit=100, has_more should be True if total > 150.
        """
        # Mock response with 100 results, offset=50, total=200
        mock_response = {
            'tracks': [
                {
                    "id": f"track-{i+50}",  # Offset 50, so tracks 50-149
                    "artist": f"Artist {i+50}",
                    "title": f"Title {i+50}",
                    "album": f"Album {i+50}",
                    "duration_seconds": 180.0,
                    "format": "MP3",
                    "rank": 0.9,
                }
                for i in range(100)
            ],
            'total_count': 200,  # More results exist beyond offset+limit
        }
        mock_db_call.return_value = mock_response
        mock_get_facets.return_value = {}

        # Test limit=100 with offset=50
        result = await audio_service.search_audio_library("test query", limit=100, offset=50)

        # Verify results
        assert len(result['results']) == 100
        assert result['has_more'] is True  # (50 + 100) < 200, so has_more=True
        assert result['total'] == 200
        assert result['limit'] == 100
        assert result['offset'] == 50

    @pytest.mark.asyncio
    @patch('src.services.audio_service.filter_audio_tracks_combined')
    @patch('src.services.audio_service.get_xmp_field_facets')
    async def test_search_limit_100_with_offset_no_more_results(self, mock_get_facets, mock_db_call):
        """
        Test has_more=False when offset + limit >= total_count.
        """
        # Mock response with 100 results, offset=150, total=200
        mock_response = {
            'tracks': [
                {
                    "id": f"track-{i+150}",  # Offset 150, tracks 150-199
                    "artist": f"Artist {i+150}",
                    "title": f"Title {i+150}",
                    "album": f"Album {i+150}",
                    "duration_seconds": 180.0,
                    "format": "MP3",
                    "rank": 0.9,
                }
                for i in range(50)  # Only 50 results left
            ],
            'total_count': 200,  # Total is 200, so at offset 150 we get the last 50
        }
        mock_db_call.return_value = mock_response
        mock_get_facets.return_value = {}

        # Test limit=100 with offset=150 (should get 50 results, has_more=False)
        result = await audio_service.search_audio_library("test query", limit=100, offset=150)

        # Verify results
        assert len(result['results']) == 50  # Only 50 results available
        assert result['has_more'] is False  # (150 + 100) > 200, so has_more=False
        assert result['total'] == 200
        assert result['limit'] == 100
        assert result['offset'] == 150
