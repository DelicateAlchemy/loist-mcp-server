-- migration_006_optimize_search_vector.sql
-- Optimize full-text search ranking for XMP metadata fields
--
-- Adjusts ts_rank weights so XMP fields (composer, publisher, record_label)
-- rank higher than basic metadata fields. This reflects that XMP data
-- from professional music libraries is often more valuable and specific
-- than filename-based metadata extraction.
--
-- Weight hierarchy (highest to lowest):
-- A: Title, Artist (core identifiers)
-- B: Composer, Publisher (professional metadata)
-- C: Album, Record Label, Genre (contextual metadata)
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- ============================================================================
-- OPTIMIZED SEARCH VECTOR FUNCTION
-- ============================================================================

-- Replace the search vector update function with improved XMP field weighting
CREATE OR REPLACE FUNCTION update_audio_tracks_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Build weighted search vector prioritizing XMP professional metadata
    NEW.search_vector :=
        -- A-weight: Core identifiers (highest priority)
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.artist, '')), 'A') ||
        -- B-weight: Professional XMP metadata (high priority)
        setweight(to_tsvector('english', COALESCE(NEW.composer, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.publisher, '')), 'B') ||
        -- C-weight: Contextual metadata (lower priority)
        setweight(to_tsvector('english', COALESCE(NEW.album, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.record_label, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.genre, '')), 'C');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- RECREATE TRIGGER WITH UPDATED FIELDS
-- ============================================================================

-- Drop and recreate trigger to include all XMP fields in the watch list
DROP TRIGGER IF EXISTS trg_update_audio_tracks_search_vector ON audio_tracks;
CREATE TRIGGER trg_update_audio_tracks_search_vector
    BEFORE INSERT OR UPDATE OF
        artist, title, album, genre, composer, publisher, record_label
    ON audio_tracks
    FOR EACH ROW
    EXECUTE FUNCTION update_audio_tracks_search_vector();

-- ============================================================================
-- UPDATE EXISTING SEARCH VECTORS
-- ============================================================================

-- Update search vectors for all existing records to use new weighting
UPDATE audio_tracks
SET search_vector = (
    -- Recalculate with new weighting for each row
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(artist, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(composer, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(publisher, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(album, '')), 'C') ||
    setweight(to_tsvector('english', COALESCE(record_label, '')), 'C') ||
    setweight(to_tsvector('english', COALESCE(genre, '')), 'C')
)
WHERE search_vector IS NOT NULL;  -- Only update rows that have been processed

-- ============================================================================
-- ADD SEARCH VECTOR INDEX OPTIMIZATION
-- ============================================================================

-- Ensure the search vector has a GIN index for fast full-text queries
-- (This should already exist from migration 001, but verify it's optimized)
CREATE INDEX IF NOT EXISTS idx_audio_tracks_search_vector
ON audio_tracks USING GIN (search_vector);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VALIDATION QUERIES
-- ============================================================================

-- Verify search vector weighting (composer should rank higher than album/genre)
-- SELECT
--     title,
--     composer,
--     album,
--     genre,
--     ts_rank(search_vector, to_tsquery('english', 'jazz')) as rank
-- FROM audio_tracks
-- WHERE search_vector @@ to_tsquery('english', 'jazz')
-- ORDER BY rank DESC
-- LIMIT 10;

-- Test XMP field ranking priority
-- SELECT
--     id,
--     artist,
--     title,
--     composer,
--     publisher,
--     ts_rank(search_vector, to_tsquery('english', 'music')) as rank
-- FROM audio_tracks
-- WHERE search_vector @@ to_tsquery('english', 'music')
--   AND (composer IS NOT NULL OR publisher IS NOT NULL)
-- ORDER BY rank DESC
-- LIMIT 20;
