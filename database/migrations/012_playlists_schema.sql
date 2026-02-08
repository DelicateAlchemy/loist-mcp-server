-- Playlists Schema
-- migration_012_playlists_schema.sql
-- Add playlists with collaboration support for front-end music management
--
-- This migration creates:
-- - playlists: User-created track collections
-- - playlist_tracks: Junction table linking audio_tracks to playlists with ordering
-- - playlist_collaborators: Collaboration roles (schema-only, no auth enforcement)
--
-- Design principles:
-- - Multi-tenancy prep: owner_id and added_by columns with no FK enforcement yet
-- - Collaboration-ready: playlist_collaborators table with role-based access
-- - Flexible ordering: tracks have position within playlist
-- - Cascade deletes: removing a playlist removes its associations

BEGIN;

-- ============================================================================
-- EXTENSION CHECK
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- TABLE: playlists
-- User-created track collections with collaboration support
-- ============================================================================

CREATE TABLE playlists (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Multi-tenancy prep (no enforcement yet)
    owner_id UUID,

    -- Core fields
    name VARCHAR(500) NOT NULL,
    description TEXT,

    -- Visibility (future use, schema-only for now)
    is_public BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_playlists_owner_id ON playlists(owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX idx_playlists_name ON playlists USING GIN(name gin_trgm_ops);
CREATE INDEX idx_playlists_created_at ON playlists(created_at DESC);
CREATE INDEX idx_playlists_public ON playlists(is_public) WHERE is_public = true;

-- Trigger for updated_at
CREATE TRIGGER trg_playlists_updated_at
    BEFORE UPDATE ON playlists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE playlists IS 'User-created track collections with collaboration support';
COMMENT ON COLUMN playlists.owner_id IS 'UUID of the owning user/tenant (no FK enforcement yet - multi-tenancy prep)';
COMMENT ON COLUMN playlists.is_public IS 'Whether playlist is publicly visible (future use)';

-- ============================================================================
-- TABLE: playlist_tracks
-- Junction table: tracks within playlists with ordering
-- ============================================================================

CREATE TABLE playlist_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    playlist_id UUID NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    audio_track_id UUID NOT NULL REFERENCES audio_tracks(id) ON DELETE CASCADE,

    -- Position/ordering within playlist (1-based)
    position INTEGER NOT NULL CHECK (position > 0),

    -- Who added this track (multi-tenancy prep)
    added_by UUID,

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints: each track appears once per playlist, each position unique
    UNIQUE(playlist_id, audio_track_id),
    UNIQUE(playlist_id, position)
);

-- Indexes
CREATE INDEX idx_playlist_tracks_playlist_id ON playlist_tracks(playlist_id);
CREATE INDEX idx_playlist_tracks_track_id ON playlist_tracks(audio_track_id);
CREATE INDEX idx_playlist_tracks_position ON playlist_tracks(playlist_id, position);
CREATE INDEX idx_playlist_tracks_added_by ON playlist_tracks(added_by) WHERE added_by IS NOT NULL;

-- Comments
COMMENT ON TABLE playlist_tracks IS 'Junction table linking audio_tracks to playlists with ordering';
COMMENT ON COLUMN playlist_tracks.position IS 'Track position within playlist (1-based)';
COMMENT ON COLUMN playlist_tracks.added_by IS 'UUID of user who added this track (multi-tenancy prep)';

-- ============================================================================
-- TABLE: playlist_collaborators
-- Collaboration roles for playlists (schema-only, no auth enforcement)
-- ============================================================================

CREATE TABLE playlist_collaborators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    playlist_id UUID NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,  -- No FK to users table (doesn't exist yet)

    -- Role-based access (schema-only, no enforcement)
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'editor', 'admin')),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints: one role per user per playlist
    UNIQUE(playlist_id, user_id)
);

-- Indexes
CREATE INDEX idx_playlist_collaborators_playlist_id ON playlist_collaborators(playlist_id);
CREATE INDEX idx_playlist_collaborators_user_id ON playlist_collaborators(user_id);
CREATE INDEX idx_playlist_collaborators_role ON playlist_collaborators(role);

-- Trigger for updated_at
CREATE TRIGGER trg_playlist_collaborators_updated_at
    BEFORE UPDATE ON playlist_collaborators
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE playlist_collaborators IS 'Collaboration roles for playlists (schema-only, no auth enforcement yet)';
COMMENT ON COLUMN playlist_collaborators.user_id IS 'UUID of collaborator (no FK - users table pending)';
COMMENT ON COLUMN playlist_collaborators.role IS 'Access level: viewer (read-only), editor (add/remove tracks), admin (manage collaborators)';

COMMIT;
