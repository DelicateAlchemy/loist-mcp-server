-- migration_002_add_waveform_support.sql
-- Add waveform generation support to audio_tracks table
--
-- Adds columns for storing waveform SVG file paths, generation timestamps,
-- and source audio content hashes for cache invalidation.
--
-- Performance targets:
-- - Sub-200ms cache lookups using source_audio_hash index
-- - Efficient waveform path queries using waveform_gcs_path index
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Add waveform-related columns to audio_tracks table
ALTER TABLE audio_tracks
    ADD COLUMN waveform_gcs_path TEXT,
    ADD COLUMN waveform_generated_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN source_audio_hash VARCHAR(64);

-- Add constraint to ensure waveform GCS paths follow the expected format
ALTER TABLE audio_tracks
    ADD CONSTRAINT valid_waveform_path CHECK (waveform_gcs_path IS NULL OR waveform_gcs_path LIKE 'gs://%');

-- Add indexes for performance
CREATE INDEX idx_audio_tracks_waveform_path ON audio_tracks(waveform_gcs_path) WHERE waveform_gcs_path IS NOT NULL;
CREATE INDEX idx_audio_tracks_source_hash ON audio_tracks(source_audio_hash) WHERE source_audio_hash IS NOT NULL;
CREATE INDEX idx_audio_tracks_waveform_generated_at ON audio_tracks(waveform_generated_at DESC) WHERE waveform_generated_at IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN audio_tracks.waveform_gcs_path IS 'Full GCS path (gs://bucket/path) to the generated waveform SVG file';
COMMENT ON COLUMN audio_tracks.waveform_generated_at IS 'Timestamp when the waveform was last generated';
COMMENT ON COLUMN audio_tracks.source_audio_hash IS 'SHA-256 hash of source audio file for cache invalidation';

COMMIT;
