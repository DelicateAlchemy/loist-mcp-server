-- Schema Hygiene
-- migration_016_schema_hygiene.sql
-- Small cleanup pass: multi-tenancy prep on uploads, drop vestigial column,
-- and lock down helper views to run with caller privileges (LOI-50)
--
-- This migration:
-- - Adds uploads.owner_id (multi-tenancy prep, no FK enforcement yet - matches
--   the convention used for albums.owner_id / playlists.owner_id)
-- - Confirms audio_tracks.isrc (multi-tenancy-unrelated XMP field added in
--   migration 004) already satisfies the "nullable ISRC + non-unique index"
--   requirement - no schema change needed there, see note below
-- - Drops audio_tracks.user_id, the vestigial INTEGER column added by
--   migration 002 that was never wired into any application code
-- - Recreates v_work_split_summary and v_party_involvement (from migration
--   010) with security_invoker = true so the views respect RLS/permissions
--   of the querying role instead of the view owner (Postgres 15+ feature;
--   docker-compose.yml pins `postgres:16-alpine`, so this is supported)
--
-- NOTE on audio_tracks.isrc: this column already exists (VARCHAR(20),
-- nullable, added in 004_add_xmp_fields.sql) with two non-unique indexes
-- (idx_audio_tracks_isrc from 004, idx_audio_tracks_isrc_exact from
-- 005_optimize_xmp_indexes.sql). It is not re-created here to avoid
-- shrinking the column (VARCHAR(20) -> VARCHAR(15)) or duplicating
-- indexes. The Pydantic/operations.py wiring gap (isrc was missing from
-- ProductMetadata and the get_audio_metadata_by_id(s) SELECT column
-- lists) is fixed in application code as part of this change instead.

BEGIN;

-- ============================================================================
-- UPLOADS: multi-tenancy prep
-- ============================================================================

ALTER TABLE uploads ADD COLUMN IF NOT EXISTS owner_id UUID;

CREATE INDEX IF NOT EXISTS idx_uploads_owner_id ON uploads(owner_id) WHERE owner_id IS NOT NULL;

COMMENT ON COLUMN uploads.owner_id IS 'UUID of the owning user/tenant (no FK enforcement yet - multi-tenancy prep)';

-- ============================================================================
-- AUDIO_TRACKS: drop vestigial user_id column
-- ============================================================================
-- Added by migration 002 for a multi-user SaaS design that was never
-- implemented. Confirmed via full-codebase grep that no application code
-- (src/, database/, tests/) reads or writes audio_tracks.user_id - the only
-- other `user_id` columns in the schema belong to unrelated tables
-- (playlist_collaborators.user_id, playlist_tracks.added_by). Dropping the
-- column also drops its two dependent indexes automatically.

ALTER TABLE audio_tracks DROP COLUMN IF EXISTS user_id;

-- ============================================================================
-- RLS-SAFE VIEWS: security_invoker
-- ============================================================================
-- Recreated verbatim from 010_song_publishing_schema.sql, adding the
-- security_invoker view option so each view runs with the permissions of
-- the querying role rather than the view owner (required once RLS is
-- introduced on works/parties/audio_tracks).

CREATE OR REPLACE VIEW v_work_split_summary WITH (security_invoker = true) AS
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

CREATE OR REPLACE VIEW v_party_involvement WITH (security_invoker = true) AS
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

COMMIT;
