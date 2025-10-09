-- migration_001_initial_schema.sql
-- Initial PostgreSQL schema for Loist MVP audio metadata storage
-- 
-- This migration creates:
-- - Core audio_tracks table with metadata and technical specifications
-- - Optimized indexes for search and filtering
-- - Automatic triggers for search vector and timestamp updates
-- - Full-text search capabilities with fuzzy matching
--
-- Performance targets:
-- - Sub-200ms queries for 100K+ tracks
-- - Efficient full-text search across metadata
-- - Fast status filtering for dashboard queries
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Enable necessary PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Main audio tracks table
CREATE TABLE audio_tracks (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Timestamps (automatically managed)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Processing state tracking
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    
    -- Failure tracking (for error debugging)
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_processed_at TIMESTAMP WITH TIME ZONE,
    
    -- ID3 Metadata (from tags)
    artist VARCHAR(500),  -- Increased size for multi-artist tracks
    title VARCHAR(500) NOT NULL,  -- Title is required
    album VARCHAR(500),
    genre VARCHAR(100),
    year INTEGER CHECK (year IS NULL OR (year >= 1800 AND year <= 2100)),
    
    -- Technical Audio Specifications
    duration_seconds NUMERIC(10, 3),  -- Precise to milliseconds, e.g., 245.678
    channels SMALLINT CHECK (channels > 0 AND channels <= 16),  -- 1=mono, 2=stereo, etc.
    sample_rate INTEGER CHECK (sample_rate > 0),  -- Hz (44100, 48000, etc.)
    bitrate INTEGER CHECK (bitrate > 0),  -- bits per second
    format VARCHAR(20) NOT NULL,  -- MP3, FLAC, WAV, AAC, etc.
    file_size_bytes BIGINT CHECK (file_size_bytes > 0),
    
    -- Google Cloud Storage paths
    audio_gcs_path TEXT NOT NULL,  -- Full gs:// URL
    thumbnail_gcs_path TEXT,  -- Full gs:// URL (nullable if no artwork)
    
    -- Full-text search vector (auto-populated by trigger)
    search_vector TSVECTOR,
    
    -- Ensure audio_gcs_path starts with gs://
    CONSTRAINT valid_audio_path CHECK (audio_gcs_path LIKE 'gs://%'),
    CONSTRAINT valid_thumbnail_path CHECK (thumbnail_gcs_path IS NULL OR thumbnail_gcs_path LIKE 'gs://%')
);

-- Indexes for performance

-- Status filtering (for dashboard/admin queries)
CREATE INDEX idx_audio_tracks_status ON audio_tracks(status) WHERE status != 'COMPLETED';

-- Timestamp-based queries (recent uploads, cleanup)
CREATE INDEX idx_audio_tracks_created_at ON audio_tracks(created_at DESC);
CREATE INDEX idx_audio_tracks_updated_at ON audio_tracks(updated_at DESC);

-- Full-text search (most important for MVP)
CREATE INDEX idx_audio_tracks_search_vector ON audio_tracks USING GIN(search_vector);

-- Individual field searches (for exact matches)
CREATE INDEX idx_audio_tracks_artist ON audio_tracks USING GIN(artist gin_trgm_ops);  -- Fuzzy search
CREATE INDEX idx_audio_tracks_title ON audio_tracks USING GIN(title gin_trgm_ops);   -- Fuzzy search
CREATE INDEX idx_audio_tracks_album ON audio_tracks USING GIN(album gin_trgm_ops);   -- Fuzzy search

-- Composite index for common query patterns (artist + album)
CREATE INDEX idx_audio_tracks_artist_album ON audio_tracks(artist, album) WHERE artist IS NOT NULL AND album IS NOT NULL;

-- Failed tracks for monitoring and cleanup
CREATE INDEX idx_audio_tracks_failed ON audio_tracks(last_processed_at) WHERE status = 'FAILED';

-- Function to update search vector automatically
CREATE OR REPLACE FUNCTION update_audio_tracks_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Build weighted search vector from metadata fields
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||      -- Highest weight
        setweight(to_tsvector('english', COALESCE(NEW.artist, '')), 'A') ||     -- Highest weight
        setweight(to_tsvector('english', COALESCE(NEW.album, '')), 'B') ||      -- Medium weight
        setweight(to_tsvector('english', COALESCE(NEW.genre, '')), 'C');        -- Lower weight
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update search vector on INSERT or UPDATE
CREATE TRIGGER trg_update_audio_tracks_search_vector
    BEFORE INSERT OR UPDATE OF artist, title, album, genre
    ON audio_tracks
    FOR EACH ROW
    EXECUTE FUNCTION update_audio_tracks_search_vector();

-- Trigger to auto-update updated_at
CREATE TRIGGER trg_update_audio_tracks_timestamp
    BEFORE UPDATE ON audio_tracks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE audio_tracks IS 'Core table storing audio file metadata and technical specifications for MVP';
COMMENT ON COLUMN audio_tracks.id IS 'Unique identifier (UUID v4) for each audio track';
COMMENT ON COLUMN audio_tracks.status IS 'Processing state: PENDING, PROCESSING, COMPLETED, FAILED';
COMMENT ON COLUMN audio_tracks.search_vector IS 'Auto-generated tsvector for full-text search across metadata fields';
COMMENT ON COLUMN audio_tracks.duration_seconds IS 'Audio duration in seconds with millisecond precision';
COMMENT ON COLUMN audio_tracks.audio_gcs_path IS 'Full GCS path (gs://bucket/path) to the audio file';
COMMENT ON COLUMN audio_tracks.thumbnail_gcs_path IS 'Full GCS path to album artwork extracted from ID3 tags';

COMMIT;
