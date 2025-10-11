-- Rollback for migration_001_initial_schema.sql
-- This script rolls back all changes from the initial schema migration
--
-- WARNING: This is a destructive operation!
-- - All data in audio_tracks table will be lost
-- - This cannot be undone
--
-- Usage:
--   psql -d music_library -f 001_initial_schema_rollback.sql
--
-- Author: Task Master AI
-- Created: 2025-10-09

BEGIN;

-- Drop triggers (must be dropped before functions)
DROP TRIGGER IF EXISTS audio_tracks_search_update_trigger ON audio_tracks;
DROP TRIGGER IF EXISTS audio_tracks_update_timestamp_trigger ON audio_tracks;

-- Drop functions
DROP FUNCTION IF EXISTS audio_tracks_search_update();
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS idx_audio_tracks_search;
DROP INDEX IF EXISTS idx_audio_tracks_artist_title;
DROP INDEX IF EXISTS idx_audio_tracks_artist_trgm;
DROP INDEX IF EXISTS idx_audio_tracks_title_trgm;
DROP INDEX IF EXISTS idx_audio_tracks_status_partial;
DROP INDEX IF EXISTS idx_audio_tracks_created_at;
DROP INDEX IF EXISTS idx_audio_tracks_artist;
DROP INDEX IF EXISTS idx_audio_tracks_album;
DROP INDEX IF EXISTS idx_audio_tracks_genre;
DROP INDEX IF EXISTS idx_audio_tracks_year;

-- Drop table
DROP TABLE IF EXISTS audio_tracks;

-- Drop extensions (only if not used by other tables)
-- Note: Be careful with this - other applications may use these extensions
-- DROP EXTENSION IF EXISTS "pg_trgm";
-- DROP EXTENSION IF EXISTS "uuid-ossp";

-- Remove migration record
DELETE FROM schema_migrations WHERE version = '001_initial_schema';

COMMIT;

-- Verification
SELECT 'Rollback completed successfully' as status;

