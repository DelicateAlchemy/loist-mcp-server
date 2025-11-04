"""
Integration tests for database operations.

Tests cover:
- Batch operations performance improvements
- Connection pooling and validation
- Query optimization and indexing
- Transaction management
- Error handling and recovery
"""

import pytest
import time
import os
from unittest.mock import patch, MagicMock
from src.exceptions import DatabaseOperationError, ValidationError


def is_db_configured() -> bool:
    """Check if database configuration is available."""
    # Check for connection URL environment variables
    has_direct = bool(
        os.getenv("DB_HOST") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    has_proxy = bool(
        os.getenv("DB_CONNECTION_NAME") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    return has_direct or has_proxy


@pytest.fixture
def db_pool():
    """Fixture to create a test database pool."""
    if not is_db_configured():
        pytest.skip("Database not configured")

    from database import get_connection_pool, close_pool

    # Get fresh pool for testing
    pool = get_connection_pool(force_new=True)

    yield pool

    # Cleanup
    close_pool()


class TestBatchOperations:
    """Test batch database operations and performance improvements."""

    def test_save_audio_metadata_batch_performance(self, db_pool):
        """Test batch metadata saving performance improvement."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata_batch

        # Create test data
        batch_data = [
            {
                'metadata': {
                    'title': f'Test Track {i}',
                    'artist': f'Artist {i}',
                    'album': f'Album {i % 5}',  # Some albums repeat
                    'genre': 'Test Genre',
                    'year': 2020 + (i % 10),
                    'duration': 180.0 + i,
                    'format': 'MP3',
                },
                'audio_gcs_path': f'gs://test/audio_{i}.mp3',
                'thumbnail_gcs_path': f'gs://test/thumb_{i}.jpg',
            }
            for i in range(10)
        ]

        # Measure performance
        start_time = time.time()
        result = save_audio_metadata_batch(batch_data)
        end_time = time.time()

        execution_time = end_time - start_time

        # Verify results
        assert result['inserted_count'] == 10
        assert 'tracks' in result
        assert len(result['tracks']) == 10

        # Performance should be reasonable (< 1 second for 10 records)
        assert execution_time < 1.0, f"Batch operation took {execution_time:.2f}s"

        # Verify data was inserted
        from database.operations import get_audio_metadata_by_ids
        track_ids = [track['id'] for track in result['tracks']]
        retrieved = get_audio_metadata_by_ids(track_ids)

        assert len(retrieved) == 10
        for track in retrieved.values():
            assert track['title'].startswith('Test Track')
            assert track['artist'].startswith('Artist')

    def test_batch_vs_individual_performance(self, db_pool):
        """Compare batch vs individual insert performance."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata, save_audio_metadata_batch

        # Create test data
        test_data = {
            'title': 'Performance Test Track',
            'artist': 'Performance Test Artist',
            'album': 'Performance Test Album',
            'genre': 'Test',
            'year': 2023,
            'duration': 200.0,
            'format': 'MP3',
            'audio_path': 'gs://test/perf_test.mp3',
            'thumbnail_path': 'gs://test/perf_thumb.jpg',
        }

        # Test individual inserts (simulate old N+1 pattern)
        individual_start = time.time()
        individual_results = []
        for i in range(5):
            data = test_data.copy()
            data['title'] = f'{test_data["title"]} {i}'
            data['audio_path'] = f'gs://test/perf_test_{i}.mp3'
            result = save_audio_metadata(
                metadata=data,
                audio_gcs_path=data['audio_path'],
                thumbnail_gcs_path=data['thumbnail_path']
            )
            individual_results.append(result)
        individual_time = time.time() - individual_start

        # Test batch insert
        batch_data = []
        for i in range(5, 10):  # Different range to avoid conflicts
            data = test_data.copy()
            data['title'] = f'{test_data["title"]} {i}'
            record = {
                'metadata': data,
                'audio_gcs_path': f'gs://test/perf_test_{i}.mp3',
                'thumbnail_gcs_path': f'gs://test/perf_thumb_{i}.jpg'
            }
            batch_data.append(record)

        batch_start = time.time()
        batch_result = save_audio_metadata_batch(batch_data)
        batch_time = time.time() - batch_start

        # Batch should be significantly faster
        improvement_ratio = individual_time / batch_time
        assert improvement_ratio > 2.0, f"Batch improvement ratio: {improvement_ratio:.2f}x"

        # Both should insert same number of records
        assert len(individual_results) == 5
        assert batch_result['inserted_count'] == 5

    def test_batch_error_handling(self, db_pool):
        """Test error handling in batch operations."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata_batch

        # Create batch with invalid data
        batch_data = [
            {
                'metadata': {
                    'title': 'Valid Track',
                    'artist': 'Valid Artist',
                    'album': 'Valid Album',
                    'genre': 'Test',
                    'year': 2023,
                    'duration': 200.0,
                    'format': 'MP3',
                },
                'audio_gcs_path': 'gs://test/valid.mp3',
            },
            {
                'metadata': {
                    # Missing required fields (format)
                    'title': 'Invalid Track',
                    'artist': 'Invalid Artist',
                },
                'audio_gcs_path': 'gs://test/invalid.mp3',
            }
        ]

        # Should handle errors gracefully
        with pytest.raises(DatabaseOperationError):
            save_audio_metadata_batch(batch_data)


class TestConnectionPooling:
    """Test connection pooling and validation improvements."""

    def test_connection_pool_health(self, db_pool):
        """Test connection pool health monitoring."""
        if not db_pool:
            pytest.skip("Database not configured")

        # Test health check
        health = db_pool.health_check()
        assert health['healthy'] is True
        assert 'database_version' in health
        assert 'min_connections' in health
        assert 'max_connections' in health

    def test_connection_validation_caching(self, db_pool):
        """Test that connection validation uses caching."""
        if not db_pool:
            pytest.skip("Database not configured")

        # Get a connection (should validate)
        with db_pool.get_connection() as conn:
            assert conn is not None

        # Get another connection quickly (should use cache)
        start_time = time.time()
        with db_pool.get_connection() as conn:
            assert conn is not None
        end_time = time.time()

        # Should be very fast (< 10ms) if validation is cached
        assert (end_time - start_time) < 0.01

    def test_connection_retry_logic(self, db_pool):
        """Test connection retry on transient failures."""
        if not db_pool:
            pytest.skip("Database not configured")

        # Test successful connection with retry
        with db_pool.get_connection(retry=True, max_retries=3) as conn:
            assert conn is not None

        # Test connection without retry
        with db_pool.get_connection(retry=False) as conn:
            assert conn is not None


class TestQueryOptimization:
    """Test query optimization and indexing improvements."""

    def test_search_performance(self, db_pool):
        """Test search query performance with indexes."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import search_audio_tracks_advanced

        # Insert test data
        test_tracks = [
            {
                'title': f'Search Test Track {i}',
                'artist': f'Search Artist {i % 3}',  # Repeat artists
                'album': f'Search Album {i % 2}',   # Repeat albums
                'genre': 'Search Test',
                'year': 2020 + (i % 5),  # Different years
                'duration': 180.0,
                'format': 'MP3',
                'audio_path': f'gs://test/search_{i}.mp3',
            }
            for i in range(20)
        ]

        from database.operations import save_audio_metadata_batch
        save_audio_metadata_batch(test_tracks)

        # Test search performance
        start_time = time.time()
        results = search_audio_tracks_advanced(
            query="Search",
            limit=10,
            format_filter="MP3"
        )
        end_time = time.time()

        search_time = end_time - start_time

        # Should return results
        assert 'tracks' in results
        assert len(results['tracks']) > 0

        # Search should be reasonably fast (< 100ms)
        assert search_time < 0.1, f"Search took {search_time:.3f}s"

    def test_index_usage_verification(self, db_pool):
        """Verify that database indexes are being used."""
        if not db_pool:
            pytest.skip("Database not configured")

        # This is a basic check - in a real scenario, you'd use EXPLAIN
        # to verify index usage, but that's complex to automate

        from database.operations import get_all_audio_metadata

        # Insert some test data
        test_tracks = [
            {
                'title': f'Index Test {i}',
                'artist': 'Index Artist',
                'album': 'Index Album',
                'genre': 'Index Test',
                'year': 2023,
                'duration': 200.0,
                'format': 'MP3',
                'audio_path': f'gs://test/index_{i}.mp3',
                'status': 'COMPLETED' if i % 2 == 0 else 'PROCESSING',  # Mix statuses
            }
            for i in range(10)
        ]

        from database.operations import save_audio_metadata_batch
        save_audio_metadata_batch(test_tracks)

        # Test filtering by status (should use status index)
        start_time = time.time()
        results = get_all_audio_metadata(
            status_filter='COMPLETED',
            limit=5
        )
        end_time = time.time()

        filter_time = end_time - start_time

        # Should return only completed tracks
        assert 'tracks' in results
        completed_tracks = [t for t in results['tracks'] if t.get('status') == 'COMPLETED']
        assert len(completed_tracks) == len(results['tracks'])

        # Filtering should be fast (< 50ms)
        assert filter_time < 0.05, f"Status filtering took {filter_time:.3f}s"


class TestTransactionManagement:
    """Test transaction management improvements."""

    def test_transaction_rollback_on_error(self, db_pool):
        """Test that transactions roll back on errors."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import get_connection

        # Start a transaction and cause an error
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Insert test data
                cur.execute("""
                    INSERT INTO audio_tracks (title, artist, audio_path, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, ('Transaction Test', 'Test Artist', 'gs://test/tx_test.mp3', 'PROCESSING'))

                track_id = cur.fetchone()[0]

                # Force an error
                try:
                    cur.execute("INVALID SQL STATEMENT")
                except Exception:
                    pass  # Expected to fail

        # Verify the transaction was rolled back
        from database.operations import get_audio_metadata_by_id
        result = get_audio_metadata_by_id(track_id)
        assert result is None, "Transaction should have been rolled back"

    def test_transaction_commit_on_success(self, db_pool):
        """Test that transactions commit on success."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata

        # Save metadata (should commit)
        result = save_audio_metadata(
            metadata={
                'title': 'Commit Test Track',
                'artist': 'Commit Test Artist',
                'album': 'Commit Test Album',
                'genre': 'Test',
                'year': 2023,
                'duration': 180.0,
                'format': 'MP3',
            },
            audio_gcs_path='gs://test/commit_test.mp3'
        )

        # Verify it was committed
        from database.operations import get_audio_metadata_by_id
        retrieved = get_audio_metadata_by_id(result['id'])
        assert retrieved is not None
        assert retrieved['title'] == 'Commit Test Track'


class TestErrorHandling:
    """Test error handling in database operations."""

    def test_invalid_data_validation(self, db_pool):
        """Test validation of invalid data."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata

        # Test with missing required fields
        with pytest.raises((ValidationError, DatabaseOperationError)):
            save_audio_metadata(
                metadata={
                    'title': 'Invalid Track',
                    # Missing artist, album, etc.
                },
                audio_gcs_path='gs://test/invalid.mp3'
            )

    def test_duplicate_handling(self, db_pool):
        """Test handling of duplicate data."""
        if not db_pool:
            pytest.skip("Database not configured")

        from database.operations import save_audio_metadata

        # Insert first track
        result1 = save_audio_metadata(
            metadata={
                'title': 'Duplicate Test',
                'artist': 'Duplicate Artist',
                'album': 'Duplicate Album',
                'genre': 'Test',
                'year': 2023,
                'duration': 200.0,
                'format': 'MP3',
            },
            audio_gcs_path='gs://test/duplicate.mp3'
        )

        # Insert duplicate (should work or handle gracefully)
        result2 = save_audio_metadata(
            metadata={
                'title': 'Duplicate Test',
                'artist': 'Duplicate Artist',
                'album': 'Duplicate Album',
                'genre': 'Test',
                'year': 2023,
                'duration': 200.0,
                'format': 'MP3',
            },
            audio_gcs_path='gs://test/duplicate2.mp3'  # Different path
        )

        # Should create different records
        assert result1['id'] != result2['id']

    def test_connection_timeout_handling(self, db_pool):
        """Test handling of connection timeouts."""
        if not db_pool:
            pytest.skip("Database not configured")

        # This is hard to test directly without mocking network issues
        # In a real scenario, you'd use network simulation tools

        from database.operations import get_connection

        # Test that connections can be obtained within reasonable time
        start_time = time.time()
        with get_connection(timeout=5.0) as conn:
            end_time = time.time()
            connection_time = end_time - start_time

            assert conn is not None
            # Should connect quickly (< 1 second in normal conditions)
            assert connection_time < 1.0, f"Connection took {connection_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
