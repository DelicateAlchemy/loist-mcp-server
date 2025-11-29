-- migration_004_add_xmp_fields.sql
-- Add XMP metadata fields for enhanced music metadata support
--
-- Adds fields for composer, publisher, record_label, and isrc
-- to support rich music metadata from XMP embedded in WAV/BWF files.
--
-- These fields maintain a flat structure as requested, avoiding
-- complex relationships between publishers, composers, and societies.
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Add XMP metadata fields to audio_tracks table
ALTER TABLE audio_tracks ADD COLUMN composer VARCHAR(500);
ALTER TABLE audio_tracks ADD COLUMN publisher VARCHAR(500);
ALTER TABLE audio_tracks ADD COLUMN record_label VARCHAR(500);
ALTER TABLE audio_tracks ADD COLUMN isrc VARCHAR(20);  -- ISRC format: CC-XXX-YY-NNNNN

-- Add comments for documentation
COMMENT ON COLUMN audio_tracks.composer IS 'Composer/arranger information from XMP metadata';
COMMENT ON COLUMN audio_tracks.publisher IS 'Publisher information from XMP metadata';
COMMENT ON COLUMN audio_tracks.record_label IS 'Record label information from XMP metadata';
COMMENT ON COLUMN audio_tracks.isrc IS 'International Standard Recording Code (ISRC) from XMP metadata';

-- Add indexes for the new fields
CREATE INDEX idx_audio_tracks_composer ON audio_tracks USING GIN(composer gin_trgm_ops) WHERE composer IS NOT NULL;
CREATE INDEX idx_audio_tracks_publisher ON audio_tracks USING GIN(publisher gin_trgm_ops) WHERE publisher IS NOT NULL;
CREATE INDEX idx_audio_tracks_record_label ON audio_tracks USING GIN(record_label gin_trgm_ops) WHERE record_label IS NOT NULL;
CREATE INDEX idx_audio_tracks_isrc ON audio_tracks(isrc) WHERE isrc IS NOT NULL;

-- Update the search vector function to include new fields
CREATE OR REPLACE FUNCTION update_audio_tracks_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Build weighted search vector from metadata fields (including new XMP fields)
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||      -- Highest weight
        setweight(to_tsvector('english', COALESCE(NEW.artist, '')), 'A') ||     -- Highest weight
        setweight(to_tsvector('english', COALESCE(NEW.album, '')), 'B') ||      -- Medium weight
        setweight(to_tsvector('english', COALESCE(NEW.composer, '')), 'B') ||   -- Medium weight (new)
        setweight(to_tsvector('english', COALESCE(NEW.publisher, '')), 'C') ||  -- Lower weight (new)
        setweight(to_tsvector('english', COALESCE(NEW.record_label, '')), 'C') || -- Lower weight (new)
        setweight(to_tsvector('english', COALESCE(NEW.genre, '')), 'C');        -- Lower weight

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update the trigger to include the new fields
DROP TRIGGER IF EXISTS trg_update_audio_tracks_search_vector ON audio_tracks;
CREATE TRIGGER trg_update_audio_tracks_search_vector
    BEFORE INSERT OR UPDATE OF artist, title, album, genre, composer, publisher, record_label
    ON audio_tracks
    FOR EACH ROW
    EXECUTE FUNCTION update_audio_tracks_search_vector();

COMMIT;
