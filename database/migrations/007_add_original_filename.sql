-- 007_add_original_filename.sql
-- Add original_filename column for download filename preservation
--
-- This column stores the original filename that was provided during ingestion
-- (either via source.filename parameter or extracted from URL). This allows
-- downloads to preserve the original filename instead of generating generic
-- names like "Unknown - Unknown Artist.mp3".
--
-- The column is nullable to maintain backward compatibility with existing records.
-- New records will have this field populated during ingestion.
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Add original_filename column to audio_tracks table
ALTER TABLE audio_tracks ADD COLUMN original_filename VARCHAR(500);

-- Add comment explaining the column purpose
COMMENT ON COLUMN audio_tracks.original_filename IS 'Original filename from source.filename or URL extraction, used for download filenames';

COMMIT;

-- ============================================================================
-- POST-MIGRATION VALIDATION QUERIES
-- ============================================================================

-- Verify column was added
-- \d audio_tracks

-- Check existing records (should all be NULL for original_filename)
-- SELECT COUNT(*) as total_records,
--        COUNT(original_filename) as records_with_filename,
--        COUNT(*) - COUNT(original_filename) as records_without_filename
-- FROM audio_tracks;

-- Sample of records to verify structure
-- SELECT id, title, artist, audio_gcs_path, original_filename
-- FROM audio_tracks
-- LIMIT 5;
