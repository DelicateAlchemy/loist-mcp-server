-- Song Publishing Schema
-- migration_010_song_publishing_schema.sql
-- Add song publishing data model for compositions, writers, publishers, and artists
--
-- This migration creates:
-- - parties: People and organizations (writers, publishers, artists, labels)
-- - works: Compositions (the song itself, separate from recordings)
-- - work_alternative_titles: Alternative/translated titles for works
-- - work_writers: Junction table linking writers to works with splits
-- - work_publishers: Junction table linking publishers to works with splits
-- - recording_artists: Junction table linking artists to recordings
-- - Modifications to audio_tracks to link to works
--
-- Design principles:
-- - Audio-first workflow: every audio_track gets a work automatically
-- - WIP-friendly: splits can be incomplete, over 100%, disputed, or unknown
-- - Recording ≠ Composition: separate relationships for artists vs writers
-- - Raw metadata preserved: string fields on audio_tracks remain as ingested data
--

BEGIN;

-- ============================================================================
-- EXTENSION CHECK
-- ============================================================================

-- Ensure required extensions exist (should already be present from migration 001)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- TABLE: parties
-- People and organizations (writers, publishers, artists, labels)
-- ============================================================================

CREATE TABLE parties (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Type discrimination
    party_type VARCHAR(20) NOT NULL DEFAULT 'person'
        CHECK (party_type IN ('person', 'organization')),
    
    -- Names
    name VARCHAR(500) NOT NULL,
    legal_name VARCHAR(500),
    
    -- Industry identifiers (all optional, populated when known)
    ipi_cae_number VARCHAR(20),
    isni VARCHAR(20),
    
    -- Society affiliation
    society_affiliation VARCHAR(50),
    
    -- Contact
    email VARCHAR(255),
    
    -- WIP support
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for parties
CREATE INDEX idx_parties_name ON parties USING GIN(name gin_trgm_ops);
CREATE INDEX idx_parties_party_type ON parties(party_type);
CREATE INDEX idx_parties_ipi_cae ON parties(ipi_cae_number) WHERE ipi_cae_number IS NOT NULL;
CREATE INDEX idx_parties_society ON parties(society_affiliation) WHERE society_affiliation IS NOT NULL;
CREATE INDEX idx_parties_created_at ON parties(created_at DESC);

-- Unique indexes for industry identifiers (IPI/CAE and ISNI are globally unique per identity)
-- Allows multiple NULLs but enforces uniqueness when a value is present
CREATE UNIQUE INDEX idx_parties_ipi_unique ON parties(ipi_cae_number) WHERE ipi_cae_number IS NOT NULL;
CREATE UNIQUE INDEX idx_parties_isni_unique ON parties(isni) WHERE isni IS NOT NULL;

-- Comments
COMMENT ON TABLE parties IS 'People and organizations involved in music creation and rights (writers, publishers, artists, labels)';
COMMENT ON COLUMN parties.party_type IS 'Discriminator: person or organization';
COMMENT ON COLUMN parties.name IS 'Display name for the party';
COMMENT ON COLUMN parties.legal_name IS 'Legal/contract name if different from display name';
COMMENT ON COLUMN parties.ipi_cae_number IS 'CAE/IPI number for PRO registration';
COMMENT ON COLUMN parties.isni IS 'International Standard Name Identifier';
COMMENT ON COLUMN parties.society_affiliation IS 'PRO affiliation: PRS, BMI, ASCAP, SESAC, SOCAN, etc.';
COMMENT ON COLUMN parties.notes IS 'Freeform notes for WIP context, disputes, etc.';

-- ============================================================================
-- TABLE: works
-- Compositions (the song itself, separate from recordings)
-- ============================================================================

CREATE TABLE works (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Core identification
    title VARCHAR(500) NOT NULL,
    
    -- Industry identifiers
    iswc VARCHAR(20),
    
    -- Metadata
    language VARCHAR(10),
    
    -- Workflow status
    status VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft',
            'splits_pending',
            'splits_disputed',
            'ready',
            'registered'
        )),
    
    -- WIP support
    notes TEXT,
    
    -- Full-text search
    search_vector TSVECTOR,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for works
CREATE INDEX idx_works_title ON works USING GIN(title gin_trgm_ops);
CREATE INDEX idx_works_status ON works(status);
CREATE INDEX idx_works_iswc ON works(iswc) WHERE iswc IS NOT NULL;
CREATE INDEX idx_works_created_at ON works(created_at DESC);
CREATE INDEX idx_works_search_vector ON works USING GIN(search_vector);

-- Unique index for ISWC (globally unique per composition)
-- Allows multiple NULLs but enforces uniqueness when assigned
CREATE UNIQUE INDEX idx_works_iswc_unique ON works(iswc) WHERE iswc IS NOT NULL;

-- Comments
COMMENT ON TABLE works IS 'Compositions/musical works (the song itself, separate from recordings)';
COMMENT ON COLUMN works.title IS 'Canonical title of the work';
COMMENT ON COLUMN works.iswc IS 'International Standard Musical Work Code (assigned by societies)';
COMMENT ON COLUMN works.language IS 'ISO 639-1 language code (e.g., en, es, fr)';
COMMENT ON COLUMN works.status IS 'Workflow status: draft → splits_pending → splits_disputed → ready → registered';
COMMENT ON COLUMN works.notes IS 'Freeform notes for WIP context';
COMMENT ON COLUMN works.search_vector IS 'Full-text search vector for work discovery';

-- ============================================================================
-- TABLE: work_alternative_titles
-- Alternative/translated titles for works
-- ============================================================================

CREATE TABLE work_alternative_titles (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Parent work
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    
    -- Title data
    title VARCHAR(500) NOT NULL,
    
    title_type VARCHAR(30) NOT NULL DEFAULT 'alternative'
        CHECK (title_type IN (
            'alternative',
            'translated',
            'original',
            'abbreviated',
            'working'
        )),
    
    language VARCHAR(10),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for work_alternative_titles
CREATE INDEX idx_work_alt_titles_work_id ON work_alternative_titles(work_id);
CREATE INDEX idx_work_alt_titles_title ON work_alternative_titles USING GIN(title gin_trgm_ops);
CREATE INDEX idx_work_alt_titles_type ON work_alternative_titles(title_type);

-- Comments
COMMENT ON TABLE work_alternative_titles IS 'Alternative, translated, or working titles for compositions';
COMMENT ON COLUMN work_alternative_titles.title_type IS 'Type: alternative, translated, original, abbreviated, working';
COMMENT ON COLUMN work_alternative_titles.language IS 'ISO 639-1 code for translated titles';

-- ============================================================================
-- TABLE: work_writers
-- Junction table linking writers to works with split information
-- ============================================================================

CREATE TABLE work_writers (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign keys
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    
    -- Split information (WIP-friendly: no sum constraint)
    -- DECIMAL(5,2) allows 0.00 to 200.00 (max 999.99), sufficient for percentage with 2 decimal places
    split_percentage DECIMAL(5,2)
        CHECK (split_percentage IS NULL OR (split_percentage >= 0 AND split_percentage <= 200)),
    
    split_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (split_status IN (
            'proposed',
            'confirmed',
            'disputed',
            'unknown'
        )),
    
    -- WIP support
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(work_id, party_id)
);

-- Indexes for work_writers
CREATE INDEX idx_work_writers_work_id ON work_writers(work_id);
CREATE INDEX idx_work_writers_party_id ON work_writers(party_id);
CREATE INDEX idx_work_writers_split_status ON work_writers(split_status);
CREATE INDEX idx_work_writers_work_party ON work_writers(work_id, party_id);

-- Comments
COMMENT ON TABLE work_writers IS 'Junction table: writers/composers on a musical work with split information';
COMMENT ON COLUMN work_writers.split_percentage IS 'Writer share percentage (0-200, nullable if unknown). No constraint that all splits sum to 100%.';
COMMENT ON COLUMN work_writers.split_status IS 'Status of this split: proposed, confirmed, disputed, unknown';
COMMENT ON COLUMN work_writers.notes IS 'Negotiation notes, context for disputes, etc.';

-- ============================================================================
-- TABLE: work_publishers
-- Junction table linking publishers to works with split information
-- ============================================================================

CREATE TABLE work_publishers (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign keys
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    
    -- Split information (WIP-friendly: no sum constraint)
    -- DECIMAL(5,2) allows 0.00 to 200.00 (max 999.99), sufficient for percentage with 2 decimal places
    split_percentage DECIMAL(5,2)
        CHECK (split_percentage IS NULL OR (split_percentage >= 0 AND split_percentage <= 200)),
    
    split_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (split_status IN (
            'proposed',
            'confirmed',
            'disputed',
            'unknown'
        )),
    
    -- WIP support
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(work_id, party_id)
);

-- Indexes for work_publishers
CREATE INDEX idx_work_publishers_work_id ON work_publishers(work_id);
CREATE INDEX idx_work_publishers_party_id ON work_publishers(party_id);
CREATE INDEX idx_work_publishers_split_status ON work_publishers(split_status);
CREATE INDEX idx_work_publishers_work_party ON work_publishers(work_id, party_id);

-- Comments
COMMENT ON TABLE work_publishers IS 'Junction table: publishers on a musical work with split information';
COMMENT ON COLUMN work_publishers.split_percentage IS 'Publisher share percentage (0-200, nullable if unknown). No constraint that all splits sum to 100%.';
COMMENT ON COLUMN work_publishers.split_status IS 'Status of this split: proposed, confirmed, disputed, unknown';

-- ============================================================================
-- TABLE: recording_artists
-- Junction table linking artists to recordings (audio_tracks)
-- ============================================================================

CREATE TABLE recording_artists (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign keys
    audio_track_id UUID NOT NULL REFERENCES audio_tracks(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    
    -- Role on recording
    is_primary BOOLEAN NOT NULL DEFAULT true,
    
    -- WIP support
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(audio_track_id, party_id)
);

-- Indexes for recording_artists
CREATE INDEX idx_recording_artists_track_id ON recording_artists(audio_track_id);
CREATE INDEX idx_recording_artists_party_id ON recording_artists(party_id);
CREATE INDEX idx_recording_artists_is_primary ON recording_artists(is_primary) WHERE is_primary = true;
CREATE INDEX idx_recording_artists_track_party ON recording_artists(audio_track_id, party_id);

-- Comments
COMMENT ON TABLE recording_artists IS 'Junction table: artists credited on a recording (audio_track)';
COMMENT ON COLUMN recording_artists.is_primary IS 'True for primary/main artist, false for featuring/guest artists';
COMMENT ON COLUMN recording_artists.notes IS 'Additional context about artist involvement';

-- ============================================================================
-- MODIFY: audio_tracks
-- Add work_id foreign key (nullable initially for migration)
-- ============================================================================

-- Add work_id column (nullable for now, will be made NOT NULL after data migration)
ALTER TABLE audio_tracks 
ADD COLUMN work_id UUID REFERENCES works(id) ON DELETE RESTRICT;

-- Index for work relationship
CREATE INDEX idx_audio_tracks_work_id ON audio_tracks(work_id) WHERE work_id IS NOT NULL;

-- Comment
COMMENT ON COLUMN audio_tracks.work_id IS 'Foreign key to the composition/work this recording represents';

-- ============================================================================
-- TRIGGERS: Auto-update timestamps
-- ============================================================================

-- Trigger function already exists from migration 001, reuse it
-- CREATE OR REPLACE FUNCTION update_updated_at_column() already exists

-- Apply to new tables
CREATE TRIGGER trg_parties_updated_at
    BEFORE UPDATE ON parties
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_works_updated_at
    BEFORE UPDATE ON works
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_work_writers_updated_at
    BEFORE UPDATE ON work_writers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_work_publishers_updated_at
    BEFORE UPDATE ON work_publishers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_recording_artists_updated_at
    BEFORE UPDATE ON recording_artists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TRIGGERS: Auto-update works search vector
-- ============================================================================

CREATE OR REPLACE FUNCTION update_works_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.title, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_works_search_vector
    BEFORE INSERT OR UPDATE OF title ON works
    FOR EACH ROW
    EXECUTE FUNCTION update_works_search_vector();

-- ============================================================================
-- DATA MIGRATION: Create works for existing audio_tracks
-- ============================================================================

-- Step 1: Create a work for each existing audio_track that doesn't have one
INSERT INTO works (id, title, status, created_at, updated_at)
SELECT 
    uuid_generate_v4() AS id,
    at.title AS title,
    'draft' AS status,
    at.created_at,
    at.updated_at
FROM audio_tracks at
WHERE at.work_id IS NULL;

-- Step 2: Link audio_tracks to their newly created works
-- We need to match by title and created_at since we just created these works
WITH work_mapping AS (
    SELECT 
        at.id AS track_id,
        w.id AS work_id
    FROM audio_tracks at
    INNER JOIN works w ON w.title = at.title AND w.created_at = at.created_at
    WHERE at.work_id IS NULL
)
UPDATE audio_tracks
SET work_id = work_mapping.work_id
FROM work_mapping
WHERE audio_tracks.id = work_mapping.track_id;

-- Step 3: Handle any tracks that still don't have a work_id (edge case: duplicate titles + timestamps)
-- Create individual works for any remaining orphaned tracks
DO $$
DECLARE
    track_record RECORD;
    new_work_id UUID;
BEGIN
    FOR track_record IN 
        SELECT id, title, created_at, updated_at 
        FROM audio_tracks 
        WHERE work_id IS NULL
    LOOP
        -- Generate new work
        new_work_id := uuid_generate_v4();
        
        -- Insert work
        INSERT INTO works (id, title, status, created_at, updated_at)
        VALUES (new_work_id, track_record.title, 'draft', track_record.created_at, track_record.updated_at);
        
        -- Link track to work
        UPDATE audio_tracks 
        SET work_id = new_work_id 
        WHERE id = track_record.id;
    END LOOP;
END $$;

-- ============================================================================
-- ENFORCE NOT NULL: Now that all tracks have works
-- ============================================================================

-- Verify no nulls remain (this will fail if data migration missed any)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM audio_tracks WHERE work_id IS NULL) THEN
        RAISE EXCEPTION 'Data migration incomplete: audio_tracks with NULL work_id exist';
    END IF;
END $$;

-- Make work_id NOT NULL
ALTER TABLE audio_tracks 
ALTER COLUMN work_id SET NOT NULL;

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: Work with aggregated split totals (for validation warnings in UI)
CREATE VIEW v_work_split_summary AS
SELECT 
    w.id AS work_id,
    w.title,
    w.status,
    COALESCE(writer_splits.total_split, 0) AS total_writer_split,
    COALESCE(writer_splits.writer_count, 0) AS writer_count,
    COALESCE(publisher_splits.total_split, 0) AS total_publisher_split,
    COALESCE(publisher_splits.publisher_count, 0) AS publisher_count,
    COALESCE(recording_counts.recording_count, 0) AS recording_count
FROM works w
LEFT JOIN (
    SELECT 
        work_id,
        SUM(split_percentage) AS total_split,
        COUNT(DISTINCT party_id) AS writer_count
    FROM work_writers
    GROUP BY work_id
) writer_splits ON w.id = writer_splits.work_id
LEFT JOIN (
    SELECT 
        work_id,
        SUM(split_percentage) AS total_split,
        COUNT(DISTINCT party_id) AS publisher_count
    FROM work_publishers
    GROUP BY work_id
) publisher_splits ON w.id = publisher_splits.work_id
LEFT JOIN (
    SELECT 
        work_id,
        COUNT(*) AS recording_count
    FROM audio_tracks
    GROUP BY work_id
) recording_counts ON w.id = recording_counts.work_id;

COMMENT ON VIEW v_work_split_summary IS 'Aggregated view of work splits for validation (split totals may not equal 100% during WIP)';

-- View: Party involvement summary
CREATE VIEW v_party_involvement AS
SELECT 
    p.id AS party_id,
    p.name,
    p.party_type,
    COALESCE(writer_counts.works_as_writer, 0) AS works_as_writer,
    COALESCE(publisher_counts.works_as_publisher, 0) AS works_as_publisher,
    COALESCE(artist_counts.recordings_as_artist, 0) AS recordings_as_artist
FROM parties p
LEFT JOIN (
    SELECT party_id, COUNT(DISTINCT work_id) AS works_as_writer
    FROM work_writers
    GROUP BY party_id
) writer_counts ON p.id = writer_counts.party_id
LEFT JOIN (
    SELECT party_id, COUNT(DISTINCT work_id) AS works_as_publisher
    FROM work_publishers
    GROUP BY party_id
) publisher_counts ON p.id = publisher_counts.party_id
LEFT JOIN (
    SELECT party_id, COUNT(DISTINCT audio_track_id) AS recordings_as_artist
    FROM recording_artists
    GROUP BY party_id
) artist_counts ON p.id = artist_counts.party_id;

COMMENT ON VIEW v_party_involvement IS 'Summary of party involvement across works and recordings';

-- ============================================================================
-- DOCUMENTATION
-- ============================================================================

COMMENT ON SCHEMA public IS 'Loist MVP schema with song publishing support. Audio-first workflow: audio_tracks → works with writers/publishers. WIP-friendly: splits can be incomplete or disputed.';

COMMIT;

-- ============================================================================
-- POST-MIGRATION VALIDATION QUERIES (run manually)
-- ============================================================================

-- Check all audio_tracks have a work
-- SELECT COUNT(*) FROM audio_tracks WHERE work_id IS NULL; -- Should be 0

-- Check work counts match track counts (1:1 after initial migration)
-- SELECT 
--     (SELECT COUNT(*) FROM audio_tracks) AS track_count,
--     (SELECT COUNT(*) FROM works) AS work_count;

-- Check split summary view works
-- SELECT * FROM v_work_split_summary LIMIT 10;

-- Check party involvement view works
-- SELECT * FROM v_party_involvement LIMIT 10;