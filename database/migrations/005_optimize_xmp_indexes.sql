-- migration_005_optimize_xmp_indexes.sql
-- Optimize database indexes and queries for XMP metadata fields
--
-- Adds composite indexes for common filter combinations involving
-- composer, publisher, record_label, and isrc fields.
--
-- These indexes support efficient multi-field filtering that will
-- be common with rich music metadata (e.g., find tracks by composer AND publisher).
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- ============================================================================
-- COMPOSITE INDEXES FOR XMP FIELD FILTERING
-- ============================================================================

-- Composite index: composer + publisher (most common combination for music libraries)
-- Supports queries like: "find tracks by composer X published by company Y"
CREATE INDEX idx_audio_tracks_composer_publisher
ON audio_tracks (composer, publisher)
WHERE composer IS NOT NULL AND publisher IS NOT NULL;

-- Composite index: composer + record_label
-- Supports queries like: "find tracks by composer X on label Y"
CREATE INDEX idx_audio_tracks_composer_record_label
ON audio_tracks (composer, record_label)
WHERE composer IS NOT NULL AND record_label IS NOT NULL;

-- Composite index: publisher + record_label
-- Supports queries like: "find tracks published by X on label Y"
CREATE INDEX idx_audio_tracks_publisher_record_label
ON audio_tracks (publisher, record_label)
WHERE publisher IS NOT NULL AND record_label IS NOT NULL;

-- Three-field composite: composer + publisher + record_label
-- Supports complex filtering: "find tracks by composer X, published by Y, on label Z"
CREATE INDEX idx_audio_tracks_composer_publisher_label
ON audio_tracks (composer, publisher, record_label)
WHERE composer IS NOT NULL AND publisher IS NOT NULL AND record_label IS NOT NULL;

-- ============================================================================
-- OPTIMIZED INDEXES FOR COMMON QUERY PATTERNS
-- ============================================================================

-- Index for ISRC exact matches (ISRCs are unique identifiers)
-- Supports queries like: "find track with specific ISRC"
CREATE INDEX idx_audio_tracks_isrc_exact
ON audio_tracks (isrc)
WHERE isrc IS NOT NULL;

-- Composite index for status + XMP fields (filter by processing status + metadata)
-- Supports queries like: "find completed tracks by composer X"
CREATE INDEX idx_audio_tracks_status_composer
ON audio_tracks (status, composer)
WHERE composer IS NOT NULL;

CREATE INDEX idx_audio_tracks_status_publisher
ON audio_tracks (status, publisher)
WHERE publisher IS NOT NULL;

-- ============================================================================
-- COVERING INDEXES FOR COMMON QUERIES
-- ============================================================================

-- Covering index for composer queries with essential metadata
-- Includes commonly selected fields to avoid table lookups
CREATE INDEX idx_audio_tracks_composer_covering
ON audio_tracks (composer, id, artist, title, album, year)
WHERE composer IS NOT NULL;

-- Covering index for publisher queries
CREATE INDEX idx_audio_tracks_publisher_covering
ON audio_tracks (publisher, id, artist, title, composer, record_label)
WHERE publisher IS NOT NULL;

-- ============================================================================
-- PARTIAL INDEXES FOR FREQUENT FILTERS
-- ============================================================================

-- Index for tracks with complete XMP metadata (all fields populated)
-- Useful for "professional music" or "fully tagged" filters
CREATE INDEX idx_audio_tracks_complete_xmp
ON audio_tracks (id, artist, title)
WHERE composer IS NOT NULL
  AND publisher IS NOT NULL
  AND record_label IS NOT NULL
  AND isrc IS NOT NULL;

-- Index for tracks with any XMP metadata (at least one field)
-- Useful for "enhanced metadata" filters
CREATE INDEX idx_audio_tracks_any_xmp
ON audio_tracks (id, artist, title, composer, publisher, record_label, isrc)
WHERE (composer IS NOT NULL OR publisher IS NOT NULL OR record_label IS NOT NULL OR isrc IS NOT NULL);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VALIDATION QUERIES
-- ============================================================================

-- Verify indexes were created successfully
-- SELECT indexname FROM pg_indexes WHERE tablename = 'audio_tracks' ORDER BY indexname;

-- Test composite index usage
-- EXPLAIN ANALYZE SELECT id, artist, title FROM audio_tracks
-- WHERE composer = 'ROB JAGER (BUMA)' AND publisher = 'EXTREME MUSIC LIBRARY'
-- ORDER BY created_at DESC LIMIT 20;
