-- migration_002_performance_indexes.sql
-- Performance optimization indexes for database operations
--
-- This migration adds indexes to improve query performance for:
-- - Status filtering across all values (not just non-completed)
-- - Year-based filtering and sorting
-- - Format-based filtering
-- - Composite indexes for common query patterns
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Status index for all values (complements existing partial index)
-- This enables fast filtering by any status value
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_status_all
ON audio_tracks(status);

-- Year index for filtering and sorting by release year
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_year
ON audio_tracks(year) WHERE year IS NOT NULL;

-- Format index for filtering by audio format
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_format
ON audio_tracks(format);

-- Duration index for sorting and range queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_duration
ON audio_tracks(duration_seconds) WHERE duration_seconds IS NOT NULL;

-- File size index for filtering large/small files
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_file_size
ON audio_tracks(file_size_bytes) WHERE file_size_bytes IS NOT NULL;

-- Composite index for status + created_at (common dashboard queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_status_created_at
ON audio_tracks(status, created_at DESC);

-- Composite index for format + year (format statistics by year)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_format_year
ON audio_tracks(format, year) WHERE year IS NOT NULL;

-- Composite index for status + format (processing statistics)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_status_format
ON audio_tracks(status, format);

-- Partial index for processing status (frequently queried)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_processing
ON audio_tracks(last_processed_at DESC) WHERE status = 'PROCESSING';

-- Partial index for recently updated tracks (dashboard queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audio_tracks_recent_updates
ON audio_tracks(updated_at DESC) WHERE updated_at > NOW() - INTERVAL '24 hours';

-- Comments for documentation
COMMENT ON INDEX idx_audio_tracks_status_all IS 'Index for fast status filtering across all status values';
COMMENT ON INDEX idx_audio_tracks_year IS 'Index for year-based filtering and sorting';
COMMENT ON INDEX idx_audio_tracks_format IS 'Index for audio format filtering';
COMMENT ON INDEX idx_audio_tracks_duration IS 'Index for duration-based sorting and range queries';
COMMENT ON INDEX idx_audio_tracks_file_size IS 'Index for file size filtering and sorting';
COMMENT ON INDEX idx_audio_tracks_status_created_at IS 'Composite index for status + timestamp dashboard queries';
COMMENT ON INDEX idx_audio_tracks_format_year IS 'Composite index for format statistics by year';
COMMENT ON INDEX idx_audio_tracks_status_format IS 'Composite index for processing statistics by format';
COMMENT ON INDEX idx_audio_tracks_processing IS 'Index for active processing queries';
COMMENT ON INDEX idx_audio_tracks_recent_updates IS 'Index for recent activity queries (last 24h)';

COMMIT;
