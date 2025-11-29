-- migration_002_add_user_id.sql
-- Add user_id column to audio_tracks table for multi-user SaaS support
--
-- This migration adds support for multi-user functionality by adding a user_id
-- column to the audio_tracks table. This enables each user to have their own
-- collection of audio tracks while maintaining data isolation.
--
-- The user_id column is initially nullable to allow existing data to remain valid.
-- In a future migration, when a users table is created, this column will become
-- NOT NULL and a foreign key constraint will be added.
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- Add user_id column to audio_tracks table (idempotent)
ALTER TABLE audio_tracks
ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Add comment explaining the column purpose
COMMENT ON COLUMN audio_tracks.user_id IS 'User ID for multi-user SaaS support. Will reference users table in future migration.';

-- Create index on user_id for query performance (idempotent)
CREATE INDEX IF NOT EXISTS idx_audio_tracks_user_id ON audio_tracks(user_id) WHERE user_id IS NOT NULL;

-- Create composite index for common query pattern (user's tracks by status) (idempotent)
CREATE INDEX IF NOT EXISTS idx_audio_tracks_user_status ON audio_tracks(user_id, status) WHERE user_id IS NOT NULL;

-- Add comment to the table explaining the multi-user architecture
COMMENT ON TABLE audio_tracks IS 'Core table storing audio file metadata and technical specifications. Supports multi-user SaaS architecture with user_id column for data isolation.';

COMMIT;
