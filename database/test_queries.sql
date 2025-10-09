-- test_queries.sql
-- Test queries to validate PostgreSQL schema performance and functionality
-- 
-- These queries test:
-- - Full-text search capabilities
-- - Fuzzy matching on text fields
-- - Status filtering performance
-- - Composite index usage
-- - Error handling and edge cases
--
-- Run these after applying migration_001_initial_schema.sql

-- ============================================================================
-- FULL-TEXT SEARCH TESTS
-- ============================================================================

-- Test 1: Basic full-text search with ranking
-- Expected: Sub-200ms for 100K+ tracks
EXPLAIN (ANALYZE, BUFFERS) 
SELECT id, artist, title, album, 
       ts_rank(search_vector, to_tsquery('english', 'rock & music')) AS rank
FROM audio_tracks
WHERE search_vector @@ to_tsquery('english', 'rock & music')
  AND status = 'COMPLETED'
ORDER BY rank DESC
LIMIT 20;

-- Test 2: Full-text search with phrase matching
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album
FROM audio_tracks
WHERE search_vector @@ phraseto_tsquery('english', 'dark side moon')
  AND status = 'COMPLETED'
ORDER BY ts_rank(search_vector, phraseto_tsquery('english', 'dark side moon')) DESC
LIMIT 10;

-- ============================================================================
-- FUZZY SEARCH TESTS
-- ============================================================================

-- Test 3: Fuzzy artist search (trigram matching)
-- Expected: Fast fuzzy matching for typos and variations
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album, similarity(artist, 'beatles') AS similarity_score
FROM audio_tracks
WHERE artist % 'beatles'  -- Fuzzy match using trigram
  AND status = 'COMPLETED'
ORDER BY similarity_score DESC
LIMIT 20;

-- Test 4: Fuzzy title search
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album, similarity(title, 'hotel california') AS similarity_score
FROM audio_tracks
WHERE title % 'hotel california'
  AND status = 'COMPLETED'
ORDER BY similarity_score DESC
LIMIT 15;

-- ============================================================================
-- STATUS FILTERING TESTS
-- ============================================================================

-- Test 5: Get pending tracks for processing
-- Expected: Uses partial index on status
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, artist, created_at
FROM audio_tracks
WHERE status = 'PENDING'
ORDER BY created_at ASC
LIMIT 50;

-- Test 6: Get failed tracks for retry
-- Expected: Uses partial index on failed status
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, artist, error_message, retry_count, last_processed_at
FROM audio_tracks
WHERE status = 'FAILED'
  AND retry_count < 3
  AND last_processed_at < NOW() - INTERVAL '1 hour'
ORDER BY last_processed_at ASC;

-- ============================================================================
-- COMPOSITE INDEX TESTS
-- ============================================================================

-- Test 7: Artist + Album queries (common pattern)
-- Expected: Uses composite index idx_audio_tracks_artist_album
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, duration_seconds, file_size_bytes
FROM audio_tracks
WHERE artist = 'Pink Floyd'
  AND album = 'The Dark Side of the Moon'
  AND status = 'COMPLETED'
ORDER BY created_at DESC;

-- ============================================================================
-- TIMESTAMP-BASED QUERIES
-- ============================================================================

-- Test 8: Recent uploads (dashboard query)
-- Expected: Uses idx_audio_tracks_created_at
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album, status, created_at
FROM audio_tracks
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 100;

-- Test 9: Recently updated tracks
-- Expected: Uses idx_audio_tracks_updated_at
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, status, updated_at
FROM audio_tracks
WHERE updated_at >= NOW() - INTERVAL '1 hour'
ORDER BY updated_at DESC;

-- ============================================================================
-- TECHNICAL SPECIFICATION QUERIES
-- ============================================================================

-- Test 10: Filter by audio format
SELECT format, COUNT(*) as track_count, 
       AVG(duration_seconds) as avg_duration,
       AVG(file_size_bytes) as avg_file_size
FROM audio_tracks
WHERE status = 'COMPLETED'
GROUP BY format
ORDER BY track_count DESC;

-- Test 11: High-quality audio tracks (lossless formats)
SELECT id, artist, title, format, sample_rate, bitrate, duration_seconds
FROM audio_tracks
WHERE format IN ('FLAC', 'WAV', 'ALAC')
  AND status = 'COMPLETED'
ORDER BY sample_rate DESC, bitrate DESC
LIMIT 20;

-- ============================================================================
-- PERFORMANCE BENCHMARK QUERIES
-- ============================================================================

-- Test 12: Large result set query (stress test)
-- Expected: Efficient pagination with indexes
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album, duration_seconds
FROM audio_tracks
WHERE status = 'COMPLETED'
  AND created_at >= NOW() - INTERVAL '30 days'
ORDER BY created_at DESC
LIMIT 1000 OFFSET 0;

-- Test 13: Complex search with multiple conditions
-- Expected: Efficient execution with multiple index usage
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, artist, title, album, genre, duration_seconds,
       ts_rank(search_vector, to_tsquery('english', 'jazz & blues')) AS rank
FROM audio_tracks
WHERE search_vector @@ to_tsquery('english', 'jazz & blues')
  AND status = 'COMPLETED'
  AND duration_seconds BETWEEN 180 AND 300  -- 3-5 minute tracks
  AND format = 'MP3'
ORDER BY rank DESC, duration_seconds ASC
LIMIT 50;

-- ============================================================================
-- DATA VALIDATION QUERIES
-- ============================================================================

-- Test 14: Check for invalid GCS paths
SELECT id, title, audio_gcs_path, thumbnail_gcs_path
FROM audio_tracks
WHERE audio_gcs_path NOT LIKE 'gs://%'
   OR (thumbnail_gcs_path IS NOT NULL AND thumbnail_gcs_path NOT LIKE 'gs://%');

-- Test 15: Check for invalid technical specifications
SELECT id, title, channels, sample_rate, bitrate, duration_seconds
FROM audio_tracks
WHERE channels <= 0 OR channels > 16
   OR sample_rate <= 0
   OR bitrate <= 0
   OR duration_seconds <= 0;

-- Test 16: Check for invalid years
SELECT id, title, year
FROM audio_tracks
WHERE year IS NOT NULL AND (year < 1800 OR year > 2100);

-- ============================================================================
-- SAMPLE DATA INSERTION (for testing)
-- ============================================================================

-- Insert sample data for testing (run after schema creation)
INSERT INTO audio_tracks (
    title, artist, album, genre, year,
    duration_seconds, channels, sample_rate, bitrate, format, file_size_bytes,
    audio_gcs_path, thumbnail_gcs_path, status
) VALUES 
(
    'Money', 'Pink Floyd', 'The Dark Side of the Moon', 'Progressive Rock', 1973,
    382.123, 2, 44100, 320000, 'MP3', 15284928,
    'gs://loist-audio-bucket/pink-floyd/dark-side-moon/money.mp3',
    'gs://loist-audio-bucket/pink-floyd/dark-side-moon/artwork.jpg',
    'COMPLETED'
),
(
    'Hotel California', 'Eagles', 'Hotel California', 'Rock', 1976,
    391.456, 2, 44100, 320000, 'MP3', 15658224,
    'gs://loist-audio-bucket/eagles/hotel-california/hotel-california.mp3',
    'gs://loist-audio-bucket/eagles/hotel-california/artwork.jpg',
    'COMPLETED'
),
(
    'Bohemian Rhapsody', 'Queen', 'A Night at the Opera', 'Rock', 1975,
    355.789, 2, 44100, 320000, 'MP3', 14231568,
    'gs://loist-audio-bucket/queen/night-at-opera/bohemian-rhapsody.mp3',
    'gs://loist-audio-bucket/queen/night-at-opera/artwork.jpg',
    'COMPLETED'
),
(
    'Stairway to Heaven', 'Led Zeppelin', 'Led Zeppelin IV', 'Rock', 1971,
    482.234, 2, 44100, 320000, 'MP3', 19289376,
    'gs://loist-audio-bucket/led-zeppelin/led-zeppelin-iv/stairway-to-heaven.mp3',
    'gs://loist-audio-bucket/led-zeppelin/led-zeppelin-iv/artwork.jpg',
    'COMPLETED'
),
(
    'Imagine', 'John Lennon', 'Imagine', 'Pop', 1971,
    183.567, 2, 44100, 320000, 'MP3', 7342680,
    'gs://loist-audio-bucket/john-lennon/imagine/imagine.mp3',
    'gs://loist-audio-bucket/john-lennon/imagine/artwork.jpg',
    'COMPLETED'
);

-- ============================================================================
-- PERFORMANCE MONITORING QUERIES
-- ============================================================================

-- Test 17: Index usage statistics
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'audio_tracks'
ORDER BY idx_tup_read DESC;

-- Test 18: Table statistics
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
WHERE tablename = 'audio_tracks';

-- ============================================================================
-- CLEANUP QUERIES (for testing)
-- ============================================================================

-- Remove test data (uncomment when needed)
-- DELETE FROM audio_tracks WHERE title IN ('Money', 'Hotel California', 'Bohemian Rhapsody', 'Stairway to Heaven', 'Imagine');
