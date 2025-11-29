"""
Full-Text Search Testing Infrastructure for Loist MCP Server.

This module provides comprehensive testing for PostgreSQL full-text search functionality
including index creation, query execution, performance validation, and relevance testing.

Author: Task Master AI (Task 17.4)
Created: 2025-11-05
"""

import time
import pytest
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import database testing infrastructure
from tests.database_testing import (
    DatabaseTestHelper,
    TestDatabaseManager,
    TestDataFactory,
    insert_test_track,
    insert_test_track_batch,
    count_tracks_in_database,
    verify_track_exists,
)

# Import search operations
from database.operations import (
    search_audio_tracks,
    search_audio_tracks_advanced,
)

logger = logging.getLogger(__name__)


class SearchIndexTests:
    """
    Tests for search index creation and updates.

    Verifies that full-text search indexes are properly created,
    maintained, and updated when data changes.
    """

    def __init__(self, test_db_manager: TestDatabaseManager):
        self.test_db_manager = test_db_manager

    def test_search_index_creation(self) -> None:
        """
        Test that full-text search index is properly created in test schema.

        Verifies the index exists and is configured correctly.
        """
        with self.test_db_manager.transaction_context() as conn:
            with conn.cursor() as cur:
                # Check if the full-text search index exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE schemaname = 'test_schema'
                        AND tablename = 'audio_tracks'
                        AND indexname = 'idx_test_tracks_fts'
                    )
                """)
                index_exists = cur.fetchone()[0]
                assert index_exists, "Full-text search index not found in test schema"

                # Verify index definition (GIN index on tsvector)
                cur.execute("""
                    SELECT am.amname as index_type
                    FROM pg_indexes i
                    JOIN pg_class c ON i.indexname = c.relname
                    JOIN pg_am am ON c.relam = am.oid
                    WHERE i.schemaname = 'test_schema'
                    AND i.tablename = 'audio_tracks'
                    AND i.indexname = 'idx_test_tracks_fts'
                """)
                result = cur.fetchone()
                assert result, "Index definition not found"
                assert result[0] == 'gin', f"Expected GIN index, got {result[0]}"

                logger.info("Full-text search index creation verified successfully")

    def test_search_index_updates(self) -> None:
        """
        Test that search index is updated when track data changes.

        Verifies that INSERT, UPDATE operations properly update the search vector.
        """
        # Create test track
        track_data = TestDataFactory.create_search_test_tracks()[0]
        inserted_track = insert_test_track(track_data)

        with self.test_db_manager.transaction_context() as conn:
            with conn.cursor() as cur:
                # Verify search vector was created for the inserted track
                cur.execute("""
                    SELECT search_vector IS NOT NULL as has_search_vector,
                           ts_rank(search_vector, to_tsquery('english', 'queen')) > 0 as searchable
                    FROM test_schema.audio_tracks
                    WHERE id = %s
                """, (inserted_track['track_id'],))

                result = cur.fetchone()
                assert result, "Track not found after insertion"
                assert result[0], "Search vector not created for inserted track"
                assert result[1], "Track not searchable after insertion"

                # Update track title and verify search vector updates
                new_title = "Updated Bohemian Rhapsody"
                cur.execute("""
                    UPDATE test_schema.audio_tracks
                    SET title = %s, updated_at = NOW()
                    WHERE id = %s
                """, (new_title, inserted_track['track_id']))

                # Verify search vector reflects the update
                cur.execute("""
                    SELECT ts_rank(search_vector, to_tsquery('english', 'updated')) > 0 as updated_searchable,
                           ts_rank(search_vector, to_tsquery('english', 'bohemian')) > 0 as still_searchable
                    FROM test_schema.audio_tracks
                    WHERE id = %s
                """, (inserted_track['track_id'],))

                result = cur.fetchone()
                assert result[0], "Search vector not updated after title change"
                assert result[1], "Original search terms still searchable"

                logger.info("Search index updates verified successfully")

    def test_search_vector_composition(self) -> None:
        """
        Test that search vectors properly combine all searchable fields.

        Verifies that title, artist, album, and genre are all included in search.
        """
        # Create track with distinct words in each field
        track_data = TestDataFactory.create_basic_track(
            title="UniqueTitleWord",
            artist="UniqueArtistWord",
            album="UniqueAlbumWord",
            genre="UniqueGenreWord"
        )
        inserted_track = insert_test_track(track_data)

        # Test that each field is searchable
        search_terms = ["UniqueTitleWord", "UniqueArtistWord", "UniqueAlbumWord", "UniqueGenreWord"]

        for term in search_terms:
            results = search_audio_tracks(term, limit=10)
            found = any(r['id'] == inserted_track['track_id'] for r in results)
            assert found, f"Term '{term}' not found in search results"

        logger.info("Search vector composition verified successfully")


class SearchQueryTests:
    """
    Tests for various search query types and patterns.

    Tests exact matches, fuzzy searches, prefix/suffix matching,
    and complex query operations.
    """

    def __init__(self, test_db_manager: TestDatabaseManager):
        self.test_db_manager = test_db_manager

    def test_exact_match_search(self) -> None:
        """
        Test exact word matching in search queries.
        """
        # Insert test tracks
        tracks = TestDataFactory.create_search_test_tracks()
        insert_test_track_batch(tracks)

        # Test exact matches
        test_cases = [
            ("Queen", "Bohemian Rhapsody"),
            ("Led Zeppelin", "Stairway to Heaven"),
            ("Eagles", "Hotel California"),
            ("John Lennon", "Imagine"),
            ("The Beatles", "Hey Jude"),
        ]

        for artist, title in test_cases:
            # Search for artist
            results = search_audio_tracks(artist, limit=5)
            assert len(results) > 0, f"No results for artist: {artist}"

            # Verify correct track is found
            found_track = next((r for r in results if r['artist'] == artist), None)
            assert found_track, f"Artist '{artist}' not found in results"

            # Search for title
            results = search_audio_tracks(title, limit=5)
            assert len(results) > 0, f"No results for title: {title}"

            found_track = next((r for r in results if r['title'] == title), None)
            assert found_track, f"Title '{title}' not found in results"

        logger.info("Exact match search verified successfully")

    def test_multi_word_search(self) -> None:
        """
        Test multi-word search queries (AND operations).
        """
        tracks = TestDataFactory.create_search_test_tracks()
        insert_test_track_batch(tracks)

        # Test multi-word searches
        test_cases = [
            ("queen bohemian", "Queen", "Bohemian Rhapsody"),
            ("led zeppelin stairway", "Led Zeppelin", "Stairway to Heaven"),
            ("eagles hotel california", "Eagles", "Hotel California"),
        ]

        for query, expected_artist, expected_title in test_cases:
            results = search_audio_tracks(query, limit=5)
            assert len(results) > 0, f"No results for query: {query}"

            # Verify both terms match
            found_track = next((r for r in results
                              if r['artist'] == expected_artist and
                                 expected_title in r['title']), None)
            assert found_track, f"Expected track not found for query: {query}"

            # Verify rank is higher for multi-word match
            assert found_track['rank'] > 0.1, f"Low relevance score for multi-word match: {found_track['rank']}"

        logger.info("Multi-word search verified successfully")

    def test_prefix_suffix_matching(self) -> None:
        """
        Test prefix and suffix matching capabilities.
        """
        # Create tracks with specific patterns
        tracks = [
            TestDataFactory.create_basic_track(title="PrefixTest", artist="TestArtist"),
            TestDataFactory.create_basic_track(title="TestSuffix", artist="TestArtist"),
            TestDataFactory.create_basic_track(title="MiddleTestWord", artist="TestArtist"),
        ]
        insert_test_track_batch(tracks)

        # Test prefix matching (word starts with)
        results = search_audio_tracks("prefix", limit=10)
        prefix_found = any("PrefixTest" in r['title'] for r in results)
        assert prefix_found, "Prefix matching failed"

        # Test suffix matching (word ends with)
        results = search_audio_tracks("suffix", limit=10)
        suffix_found = any("TestSuffix" in r['title'] for r in results)
        assert suffix_found, "Suffix matching failed"

        # Test middle word matching
        results = search_audio_tracks("middle", limit=10)
        middle_found = any("MiddleTestWord" in r['title'] for r in results)
        assert middle_found, "Middle word matching failed"

        logger.info("Prefix/suffix matching verified successfully")

    def test_fuzzy_search_patterns(self) -> None:
        """
        Test fuzzy search capabilities and partial matching.
        """
        tracks = TestDataFactory.create_search_test_tracks()
        insert_test_track_batch(tracks)

        # Test partial word matching
        test_cases = [
            ("bohem", "Bohemian Rhapsody"),  # Partial title
            ("zepp", "Led Zeppelin"),        # Partial artist
            ("hotel", "Hotel California"),   # Partial album
            ("rock", "Rock"),                # Genre matching
        ]

        for partial_term, expected_match in test_cases:
            results = search_audio_tracks(partial_term, limit=10, min_rank=0.01)
            assert len(results) > 0, f"No results for partial term: {partial_term}"

            # Check if expected match is found
            found = any(expected_match in str(r.values()) for r in results)
            assert found, f"Expected match '{expected_match}' not found for term '{partial_term}'"

        logger.info("Fuzzy search patterns verified successfully")

    def test_search_ranking(self) -> None:
        """
        Test that search results are properly ranked by relevance.
        """
        tracks = TestDataFactory.create_search_test_tracks()
        insert_test_track_batch(tracks)

        # Search for a common term that should appear in multiple tracks
        results = search_audio_tracks("rock", limit=10)
        assert len(results) >= 2, "Need at least 2 results for ranking test"

        # Verify results are sorted by rank (descending)
        ranks = [r['rank'] for r in results]
        assert ranks == sorted(ranks, reverse=True), "Results not sorted by rank"

        # Verify all ranks are positive and reasonable
        for rank in ranks:
            assert rank > 0, f"Invalid rank: {rank}"
            assert rank <= 1.0, f"Rank too high: {rank}"

        logger.info("Search ranking verified successfully")

    def test_empty_and_invalid_queries(self) -> None:
        """
        Test handling of empty and invalid search queries.
        """
        from src.exceptions import ValidationError

        # Test empty query
        with pytest.raises(ValidationError):
            search_audio_tracks("")

        with pytest.raises(ValidationError):
            search_audio_tracks("   ")

        # Test invalid tsquery syntax (should be handled gracefully)
        with pytest.raises(ValidationError):
            search_audio_tracks("invalid & & syntax")

        logger.info("Empty and invalid query handling verified successfully")


class SearchPerformanceTests:
    """
    Performance tests for search operations with different dataset sizes.

    Measures search operation timing and validates performance characteristics.
    """

    def __init__(self, test_db_manager: TestDatabaseManager):
        self.test_db_manager = test_db_manager

    def test_small_dataset_performance(self) -> None:
        """
        Test search performance with small dataset (10-50 tracks).
        """
        # Create small dataset
        tracks = []
        for i in range(25):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Performance Track {i}",
                artist=f"Artist {i % 5}",  # Repeat artists for better search results
                album=f"Album {i % 3}",
                genre="Rock"
            ))

        insert_test_track_batch(tracks)

        # Measure search performance
        start_time = time.time()
        results = search_audio_tracks("rock", limit=20)
        end_time = time.time()

        search_time = end_time - start_time
        assert search_time < 0.1, f"Small dataset search too slow: {search_time:.3f}s"
        assert len(results) > 0, "No results found"

        logger.info(".3f")

    def test_medium_dataset_performance(self) -> None:
        """
        Test search performance with medium dataset (100-500 tracks).
        """
        # Create medium dataset
        tracks = []
        for i in range(200):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Medium Track {i}",
                artist=f"Medium Artist {i % 10}",
                album=f"Medium Album {i % 5}",
                genre=["Rock", "Pop", "Jazz", "Classical"][i % 4]
            ))

        insert_test_track_batch(tracks)

        # Test multiple search queries
        search_terms = ["rock", "pop", "medium artist 1", "medium album 1"]
        total_time = 0

        for term in search_terms:
            start_time = time.time()
            results = search_audio_tracks(term, limit=50)
            end_time = time.time()

            total_time += (end_time - start_time)
            assert len(results) > 0, f"No results for term: {term}"

        avg_time = total_time / len(search_terms)
        assert avg_time < 0.2, f"Medium dataset search too slow: {avg_time:.3f}s avg"

        logger.info(".3f")

    def test_search_pagination_performance(self) -> None:
        """
        Test performance of paginated search results.
        """
        # Create dataset for pagination testing
        tracks = []
        for i in range(100):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Pagination Track {i}",
                artist="Pagination Artist",
                genre="Rock"
            ))

        insert_test_track_batch(tracks)

        # Test pagination performance
        total_results = 0
        start_time = time.time()

        for offset in range(0, 50, 10):  # Test first 5 pages
            results = search_audio_tracks("rock", limit=10, offset=offset)
            total_results += len(results)

        end_time = time.time()
        pagination_time = end_time - start_time

        assert pagination_time < 0.5, f"Pagination too slow: {pagination_time:.3f}s"
        assert total_results >= 50, f"Insufficient results: {total_results}"

        logger.info(".3f")

    def test_search_with_filters_performance(self) -> None:
        """
        Test performance of advanced search with filters.
        """
        # Create dataset with various years and formats
        tracks = []
        for i in range(150):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Filter Track {i}",
                artist=f"Filter Artist {i % 8}",
                album=f"Filter Album {i % 4}",
                genre="Rock",
                year=1970 + (i % 50),  # Years 1970-2019
                format=["MP3", "FLAC", "WAV"][i % 3]
            ))

        insert_test_track_batch(tracks)

        # Test advanced search with filters
        start_time = time.time()
        results = search_audio_tracks_advanced(
            query="rock",
            limit=20,
            year_min=1980,
            year_max=2000,
            format_filter="MP3",
            min_rank=0.1
        )
        end_time = time.time()

        search_time = end_time - start_time
        assert search_time < 0.3, f"Filtered search too slow: {search_time:.3f}s"
        assert len(results['tracks']) > 0, "No filtered results found"

        # Verify filters were applied
        for track in results['tracks']:
            assert 1980 <= track['year'] <= 2000, f"Year filter failed: {track['year']}"
            assert track['format'] == 'MP3', f"Format filter failed: {track['format']}"

        logger.info(".3f")


class SearchRelevanceTests:
    """
    Tests for search result relevance and ranking accuracy.

    Creates datasets with known relevance patterns and verifies
    that search results match expected ordering.
    """

    def __init__(self, test_db_manager: TestDatabaseManager):
        self.test_db_manager = test_db_manager

    def test_relevance_ranking_accuracy(self) -> None:
        """
        Test that relevance ranking matches expected patterns.
        """
        # Create tracks with known relevance patterns
        tracks = [
            # High relevance: exact matches in title
            TestDataFactory.create_basic_track(
                title="Bohemian Rhapsody Queen",
                artist="Queen",
                album="A Night at the Opera"
            ),
            # Medium relevance: partial matches
            TestDataFactory.create_basic_track(
                title="Bohemian Symphony",
                artist="Queen Orchestra",
                album="Classical Night"
            ),
            # Lower relevance: single word matches
            TestDataFactory.create_basic_track(
                title="Simple Song",
                artist="Other Artist",
                album="Bohemian Tales"
            ),
        ]

        insert_test_track_batch(tracks)

        # Search for "bohemian queen"
        results = search_audio_tracks("bohemian queen", limit=10)

        # Verify ranking: exact title match should rank highest
        assert len(results) >= 2, "Need at least 2 results for relevance test"

        # First result should be the exact match
        top_result = results[0]
        assert "Bohemian Rhapsody Queen" in top_result['title'], "Exact match not ranked first"

        # Verify rank decreases appropriately
        if len(results) > 1:
            assert results[0]['rank'] > results[1]['rank'], "Ranking not properly ordered"

        logger.info("Relevance ranking accuracy verified successfully")

    def test_relevance_with_multiple_matches(self) -> None:
        """
        Test relevance when query matches multiple fields.
        """
        tracks = [
            # Title + Artist match
            TestDataFactory.create_basic_track(
                title="Stairway to Heaven",
                artist="Led Zeppelin",
                album="IV"
            ),
            # Title only match
            TestDataFactory.create_basic_track(
                title="Stairway to Paradise",
                artist="Other Band",
                album="Other Album"
            ),
            # Artist only match
            TestDataFactory.create_basic_track(
                title="Other Song",
                artist="Led Zeppelin",
                album="Other Album"
            ),
        ]

        insert_test_track_batch(tracks)

        results = search_audio_tracks("led zeppelin stairway", limit=10)

        # Title + Artist match should rank highest
        assert len(results) >= 1, "No results found"
        top_result = results[0]
        assert top_result['title'] == "Stairway to Heaven", "Title+Artist match not ranked first"
        assert top_result['artist'] == "Led Zeppelin", "Title+Artist match not ranked first"

        logger.info("Multiple field relevance verified successfully")

    def test_relevance_score_distribution(self) -> None:
        """
        Test that relevance scores are properly distributed.
        """
        # Create varied tracks
        tracks = TestDataFactory.create_search_test_tracks()
        # Add some less relevant tracks
        for i in range(10):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Unrelated Track {i}",
                artist=f"Unrelated Artist {i}",
                genre="Jazz"
            ))

        insert_test_track_batch(tracks)

        results = search_audio_tracks("queen", limit=20, min_rank=0.01)

        # Should have multiple results with different relevance scores
        assert len(results) >= 3, "Need at least 3 results for score distribution test"

        ranks = [r['rank'] for r in results]

        # Check score distribution
        max_rank = max(ranks)
        min_rank = min(ranks)

        # Should have some variation in scores
        assert max_rank > min_rank, "All relevance scores identical"

        # Highest relevance should be reasonably high
        assert max_rank > 0.5, f"Maximum relevance too low: {max_rank}"

        logger.info("Relevance score distribution verified successfully")


# ==============================================================================
# Pytest Fixtures and Test Functions
# ==============================================================================

@pytest.fixture
def search_index_tests(test_db_manager):
    """Fixture providing SearchIndexTests instance."""
    return SearchIndexTests(test_db_manager)


@pytest.fixture
def search_query_tests(test_db_manager):
    """Fixture providing SearchQueryTests instance."""
    return SearchQueryTests(test_db_manager)


@pytest.fixture
def search_performance_tests(test_db_manager):
    """Fixture providing SearchPerformanceTests instance."""
    return SearchPerformanceTests(test_db_manager)


@pytest.fixture
def search_relevance_tests(test_db_manager):
    """Fixture providing SearchRelevanceTests instance."""
    return SearchRelevanceTests(test_db_manager)


@pytest.fixture
def clean_search_test_data(test_db_manager):
    """Fixture that ensures clean state for search tests."""
    test_db_manager.clear_all_test_data()
    yield
    # Cleanup happens automatically via transaction rollback


# ==============================================================================
# Test Functions
# ==============================================================================

class TestSearchIndexInfrastructure:
    """Test search index creation and maintenance."""

    def test_index_creation(self, search_index_tests, clean_search_test_data):
        """Test that search indexes are properly created."""
        search_index_tests.test_search_index_creation()

    def test_index_updates(self, search_index_tests, clean_search_test_data):
        """Test that search indexes update when data changes."""
        search_index_tests.test_search_index_updates()

    def test_vector_composition(self, search_index_tests, clean_search_test_data):
        """Test that search vectors include all relevant fields."""
        search_index_tests.test_search_vector_composition()


class TestSearchQueryFunctionality:
    """Test various search query types and patterns."""

    def test_exact_matches(self, search_query_tests, clean_search_test_data):
        """Test exact word matching."""
        search_query_tests.test_exact_match_search()

    def test_multi_word_queries(self, search_query_tests, clean_search_test_data):
        """Test multi-word AND searches."""
        search_query_tests.test_multi_word_search()

    def test_prefix_suffix_matching(self, search_query_tests, clean_search_test_data):
        """Test prefix and suffix matching."""
        search_query_tests.test_prefix_suffix_matching()

    def test_fuzzy_patterns(self, search_query_tests, clean_search_test_data):
        """Test fuzzy and partial matching."""
        search_query_tests.test_fuzzy_search_patterns()

    def test_result_ranking(self, search_query_tests, clean_search_test_data):
        """Test that results are properly ranked by relevance."""
        search_query_tests.test_search_ranking()

    def test_edge_cases(self, search_query_tests, clean_search_test_data):
        """Test handling of empty and invalid queries."""
        search_query_tests.test_empty_and_invalid_queries()


class TestSearchPerformance:
    """Test search performance across different dataset sizes."""

    def test_small_dataset_timing(self, search_performance_tests, clean_search_test_data):
        """Test performance with small datasets."""
        search_performance_tests.test_small_dataset_performance()

    def test_medium_dataset_timing(self, search_performance_tests, clean_search_test_data):
        """Test performance with medium datasets."""
        search_performance_tests.test_medium_dataset_performance()

    def test_pagination_timing(self, search_performance_tests, clean_search_test_data):
        """Test pagination performance."""
        search_performance_tests.test_search_pagination_performance()

    def test_filtered_search_timing(self, search_performance_tests, clean_search_test_data):
        """Test performance of advanced searches with filters."""
        search_performance_tests.test_search_with_filters_performance()


class TestSearchRelevance:
    """Test search result relevance and ranking accuracy."""

    def test_ranking_accuracy(self, search_relevance_tests, clean_search_test_data):
        """Test that relevance ranking matches expectations."""
        search_relevance_tests.test_relevance_ranking_accuracy()

    def test_multiple_field_relevance(self, search_relevance_tests, clean_search_test_data):
        """Test relevance when query matches multiple fields."""
        search_relevance_tests.test_relevance_with_multiple_matches()

    def test_score_distribution(self, search_relevance_tests, clean_search_test_data):
        """Test that relevance scores are properly distributed."""
        search_relevance_tests.test_relevance_score_distribution()


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestFullTextSearchIntegration:
    """Integration tests combining multiple search components."""

    def test_complete_search_workflow(self, test_db_manager, clean_search_test_data):
        """Test complete search workflow from data insertion to result retrieval."""
        # Insert diverse test data
        tracks = TestDataFactory.create_search_test_tracks()
        tracks.extend(TestDataFactory.create_edge_case_tracks())
        insert_test_track_batch(tracks)

        # Verify data was inserted
        total_tracks = count_tracks_in_database()
        assert total_tracks >= len(tracks), f"Expected {len(tracks)} tracks, found {total_tracks}"

        # Test various search patterns
        search_queries = [
            "queen",
            "rock",
            "bohemian rhapsody",
            "led zeppelin stairway",
            "imagine john",
        ]

        for query in search_queries:
            results = search_audio_tracks(query, limit=10)
            assert len(results) > 0, f"No results for query: {query}"

            # Verify all results have required fields
            for result in results:
                required_fields = ['id', 'title', 'artist', 'rank']
                for field in required_fields:
                    assert field in result, f"Missing field '{field}' in result"
                    assert result[field] is not None, f"Field '{field}' is None"

        logger.info("Complete search workflow integration verified successfully")

    def test_search_result_consistency(self, test_db_manager, clean_search_test_data):
        """Test that search results are consistent across multiple queries."""
        # Insert known dataset
        tracks = TestDataFactory.create_search_test_tracks()
        insert_test_track_batch(tracks)

        # Perform same search multiple times
        query = "queen bohemian"
        results1 = search_audio_tracks(query, limit=5)
        results2 = search_audio_tracks(query, limit=5)

        # Results should be identical
        assert len(results1) == len(results2), "Result counts differ between queries"

        for i, (r1, r2) in enumerate(zip(results1, results2)):
            assert r1['id'] == r2['id'], f"Result {i} ID mismatch"
            assert r1['rank'] == r2['rank'], f"Result {i} rank mismatch"

        logger.info("Search result consistency verified successfully")

    def test_advanced_search_integration(self, test_db_manager, clean_search_test_data):
        """Test advanced search with multiple filters."""
        # Create dataset with varied metadata
        tracks = []
        for i in range(50):
            tracks.append(TestDataFactory.create_basic_track(
                title=f"Advanced Track {i}",
                artist=f"Artist {i % 5}",
                album=f"Album {i % 3}",
                genre=["Rock", "Pop", "Jazz"][i % 3],
                year=1980 + (i % 40),  # 1980-2019
                format=["MP3", "FLAC"][i % 2]
            ))

        insert_test_track_batch(tracks)

        # Test advanced search with multiple filters
        result = search_audio_tracks_advanced(
            query="rock",
            limit=10,
            status_filter="COMPLETED",
            year_min=1990,
            year_max=2010,
            format_filter="MP3",
            min_rank=0.1
        )

        assert len(result['tracks']) > 0, "No results from advanced search"
        assert result['total_matches'] >= len(result['tracks']), "Invalid total_matches"

        # Verify all filters were applied
        for track in result['tracks']:
            assert track['genre'] == 'Rock', f"Genre filter failed: {track['genre']}"
            assert 1990 <= track['year'] <= 2010, f"Year filter failed: {track['year']}"
            assert track['format'] == 'MP3', f"Format filter failed: {track['format']}"
            assert track['status'] == 'COMPLETED', f"Status filter failed: {track['status']}"

        logger.info("Advanced search integration verified successfully")


# ==============================================================================
# Utility Functions for Search Testing
# ==============================================================================

def create_search_performance_dataset(size: int) -> List[Dict[str, Any]]:
    """
    Create a dataset optimized for search performance testing.

    Args:
        size: Number of tracks to create

    Returns:
        List of track data for insertion
    """
    tracks = []

    # Common words for realistic search patterns
    artists = ["Queen", "Led Zeppelin", "The Beatles", "Pink Floyd", "The Rolling Stones",
              "Bob Dylan", "David Bowie", "Bruce Springsteen", "Tom Petty", "Fleetwood Mac"]

    albums = ["Greatest Hits", "Best Of", "Live", "Studio", "Collection", "Anthology",
             "The Complete", "Original", "Remastered", "Deluxe Edition"]

    genres = ["Rock", "Pop", "Classic Rock", "Hard Rock", "Blues Rock", "Progressive Rock"]

    for i in range(size):
        tracks.append(TestDataFactory.create_basic_track(
            title=f"Performance Track {i}",
            artist=artists[i % len(artists)],
            album=albums[i % len(albums)],
            genre=genres[i % len(genres)],
            year=1960 + (i % 60)  # 1960-2019
        ))

    return tracks


def benchmark_search_operation(query: str, iterations: int = 5) -> Dict[str, float]:
    """
    Benchmark search operation performance.

    Args:
        query: Search query to test
        iterations: Number of times to run the search

    Returns:
        Dict with timing statistics
    """
    times = []

    for _ in range(iterations):
        start_time = time.time()
        results = search_audio_tracks(query, limit=20)
        end_time = time.time()
        times.append(end_time - start_time)

    return {
        'min_time': min(times),
        'max_time': max(times),
        'avg_time': sum(times) / len(times),
        'total_time': sum(times),
        'iterations': iterations
    }


# Export key classes and functions
__all__ = [
    'SearchIndexTests',
    'SearchQueryTests',
    'SearchPerformanceTests',
    'SearchRelevanceTests',
    'create_search_performance_dataset',
    'benchmark_search_operation',
]
