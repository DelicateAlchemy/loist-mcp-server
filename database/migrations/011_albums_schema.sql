-- Albums Schema
-- migration_011_albums_schema.sql
-- Add albums as flexible track groupings with project/album hybrid status
--
-- This migration creates:
-- - albums: Flexible collections of tracks (project -> draft -> released)
-- - album_tracks: Junction table linking audio_tracks to albums with ordering
--
-- Design principles:
-- - Project/album hybrid: status evolves from WIP project to released album
-- - Multi-tenancy prep: owner_id column with no FK enforcement yet
-- - Flexible ordering: tracks have position and optional disc_number
-- - Cascade deletes: removing an album removes its track associations

BEGIN;

-- ============================================================================
-- EXTENSION CHECK
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- TABLE: albums
-- Flexible track groupings (project/album hybrid) with status progression
-- ============================================================================

CREATE TABLE albums (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Multi-tenancy prep (no enforcement yet)
    owner_id UUID,

    -- Core fields
    name VARCHAR(500) NOT NULL,
    description TEXT,

    -- Cover art stored in GCS (optional)
    cover_art_gcs_path TEXT,

    -- Status progression: project -> draft -> released
    status VARCHAR(20) NOT NULL DEFAULT 'project'
        CHECK (status IN ('project', 'draft', 'released')),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_albums_owner_id ON albums(owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX idx_albums_name ON albums USING GIN(name gin_trgm_ops);
CREATE INDEX idx_albums_status ON albums(status);
CREATE INDEX idx_albums_created_at ON albums(created_at DESC);

-- Trigger for updated_at
CREATE TRIGGER trg_albums_updated_at
    BEFORE UPDATE ON albums
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE albums IS 'Flexible track groupings (project/album hybrid) with status: project -> draft -> released';
COMMENT ON COLUMN albums.owner_id IS 'UUID of the owning user/tenant (no FK enforcement yet - multi-tenancy prep)';
COMMENT ON COLUMN albums.cover_art_gcs_path IS 'GCS path to cover art image (gs://bucket/path)';
COMMENT ON COLUMN albums.status IS 'Lifecycle status: project (WIP), draft (structured), released (final)';

-- ============================================================================
-- TABLE: album_tracks
-- Junction table: tracks within albums with ordering
-- ============================================================================

CREATE TABLE album_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    audio_track_id UUID NOT NULL REFERENCES audio_tracks(id) ON DELETE CASCADE,

    -- Position/ordering within album (1-based)
    position INTEGER NOT NULL CHECK (position > 0),

    -- Optional per-track metadata within album context
    disc_number INTEGER NOT NULL DEFAULT 1 CHECK (disc_number > 0),

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints: each track appears once per album, each position unique per disc
    UNIQUE(album_id, audio_track_id),
    UNIQUE(album_id, disc_number, position)
);

-- Indexes
CREATE INDEX idx_album_tracks_album_id ON album_tracks(album_id);
CREATE INDEX idx_album_tracks_track_id ON album_tracks(audio_track_id);
CREATE INDEX idx_album_tracks_position ON album_tracks(album_id, disc_number, position);

-- Comments
COMMENT ON TABLE album_tracks IS 'Junction table linking audio_tracks to albums with ordering';
COMMENT ON COLUMN album_tracks.position IS 'Track position within disc (1-based)';
COMMENT ON COLUMN album_tracks.disc_number IS 'Disc number for multi-disc albums (default 1)';

COMMIT;
