-- migration_008_add_a2a_task_id_to_audio_tracks.sql
-- Add a2a_task_id column to audio_tracks table for A2A task linking
--
-- This migration adds support for linking audio_tracks records to A2A tasks
-- that created them. This enables traceability between A2A task coordination
-- and the resulting audio processing output.
--
-- IMPORTANT DESIGN DECISIONS:
-- 1. No Foreign Key Constraint: The a2a_tasks table is managed by the A2A SDK
--    (DatabaseTaskStore) and its schema/structure may change. We intentionally
--    do not add a foreign key constraint to avoid coupling our schema to the
--    SDK's internal implementation.
--
-- 2. Referential Integrity: Enforced at the application level, not database level.
--    The handler validates a2a_task_id as a UUID before storage, and the SDK
--    manages task lifecycle independently.
--
-- 3. Nullable Column: The column is nullable since MCP tools don't use A2A tasks.
--    Only audio tracks processed via A2A endpoints will have this field populated.
--
-- 4. Bidirectional Linking: The audio_track_id is also stored in task.metadata
--    (JSON field in SDK-managed a2a_tasks table) for reverse lookups.
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Add a2a_task_id column to audio_tracks table (idempotent)
ALTER TABLE audio_tracks
ADD COLUMN IF NOT EXISTS a2a_task_id VARCHAR(36);

-- Add comment explaining the column purpose
COMMENT ON COLUMN audio_tracks.a2a_task_id IS 'A2A task ID that created this audio track record. Links to SDK-managed a2a_tasks table.';

-- Create index on a2a_task_id for efficient queries (idempotent)
CREATE INDEX IF NOT EXISTS idx_audio_tracks_a2a_task_id
ON audio_tracks(a2a_task_id) WHERE a2a_task_id IS NOT NULL;

COMMIT;
