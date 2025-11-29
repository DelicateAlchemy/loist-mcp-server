-- migration_003_add_a2a_tasks.sql
-- Add A2A task coordination table for agent-to-agent workflow management
--
-- This migration creates:
-- - a2a_tasks table for tracking A2A task lifecycle
-- - Indexes for efficient task status and time-based queries
-- - JSONB fields for flexible input/output storage
--
-- A2A tasks coordinate multiple operations (unlike audio_tracks which stores final results)
-- Tasks can represent: audio processing requests, batch operations, agent coordination
--
-- Author: Task Master AI
-- Created: $(date)

BEGIN;

-- A2A Tasks table for agent coordination
CREATE TABLE a2a_tasks (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Timestamps (automatically managed)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Task type and status
    task_type VARCHAR(50) NOT NULL,  -- 'process_audio', 'batch_process', 'search', etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

    -- Task data (flexible JSON storage)
    input_data JSONB NOT NULL,   -- Task parameters from agent
    result_data JSONB,           -- Task results/output data

    -- Error handling
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,

    -- Optional webhook for completion notifications
    webhook_url TEXT,
    webhook_secret TEXT,  -- For webhook signature validation

    -- Agent tracking (optional, for multi-agent workflows)
    requesting_agent_id TEXT,     -- ID of agent that created task
    assigned_agent_id TEXT,      -- ID of agent processing task

    -- Links to domain objects (optional)
    audio_track_id UUID REFERENCES audio_tracks(id),  -- Link to processed audio

    -- Ensure webhook URL is valid if provided
    CONSTRAINT valid_webhook_url CHECK (webhook_url IS NULL OR webhook_url LIKE 'http%')
);

-- Indexes for performance

-- Task status filtering (most common query)
CREATE INDEX idx_a2a_tasks_status ON a2a_tasks(status) WHERE status IN ('pending', 'processing');

-- Time-based queries (recent tasks, cleanup)
CREATE INDEX idx_a2a_tasks_created_at ON a2a_tasks(created_at DESC);
CREATE INDEX idx_a2a_tasks_updated_at ON a2a_tasks(updated_at DESC);

-- Task type filtering (for dashboards, monitoring)
CREATE INDEX idx_a2a_tasks_type ON a2a_tasks(task_type);

-- Audio track relationship (for joining with processed results)
CREATE INDEX idx_a2a_tasks_audio_track ON a2a_tasks(audio_track_id) WHERE audio_track_id IS NOT NULL;

-- Agent tracking (for multi-agent workflows)
CREATE INDEX idx_a2a_tasks_requesting_agent ON a2a_tasks(requesting_agent_id) WHERE requesting_agent_id IS NOT NULL;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_a2a_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER trg_update_a2a_tasks_timestamp
    BEFORE UPDATE ON a2a_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_a2a_tasks_updated_at();

-- Comments for documentation
COMMENT ON TABLE a2a_tasks IS 'A2A task coordination table for agent-to-agent workflow management';
COMMENT ON COLUMN a2a_tasks.id IS 'Unique identifier (UUID v4) for each A2A task';
COMMENT ON COLUMN a2a_tasks.task_type IS 'Type of task: process_audio, batch_process, search, etc.';
COMMENT ON COLUMN a2a_tasks.status IS 'Task lifecycle state: pending, processing, completed, failed';
COMMENT ON COLUMN a2a_tasks.input_data IS 'JSONB storage for task parameters and input data';
COMMENT ON COLUMN a2a_tasks.result_data IS 'JSONB storage for task results and output data';
COMMENT ON COLUMN a2a_tasks.audio_track_id IS 'Optional link to audio_tracks record when task produces audio';

COMMIT;
