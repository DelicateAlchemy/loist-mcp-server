-- migration_009_add_push_notification_configs.sql
-- Add push_notification_configs table for A2A push notification support
--
-- This migration adds support for storing push notification configurations
-- for A2A tasks. This enables agents to receive asynchronous updates about
-- task status changes via webhooks.
--
-- DESIGN DECISIONS:
-- 1. No Foreign Key Constraint: The a2a_tasks table is managed by the A2A SDK
--    (DatabaseTaskStore) and its schema/structure may change. We intentionally
--    do not add a foreign key constraint to avoid coupling our schema to the
--    SDK's internal implementation.
--
-- 2. Multiple Configs Per Task: A task can have multiple push notification
--    configs (different endpoints, different config_ids). The unique constraint
--    on (task_id, config_id) ensures config_id uniqueness per task.
--
-- 3. Flexible Authentication: The authentication field is JSONB to support
--    various authentication schemes (Bearer tokens, custom headers, etc.)
--
-- 4. Config ID: Optional config_id allows clients to manage multiple
--    notification endpoints per task. If not provided, we'll generate one.
--
-- Author: Task Master AI
-- Created: 2025-12-17

BEGIN;

-- Create push_notification_configs table
CREATE TABLE IF NOT EXISTS push_notification_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) NOT NULL,
    config_id VARCHAR(255),
    url TEXT NOT NULL,
    token TEXT,
    authentication JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(task_id, config_id)
);

-- Add comment explaining the table purpose
COMMENT ON TABLE push_notification_configs IS 'Stores push notification configurations for A2A tasks. Links to SDK-managed a2a_tasks table via task_id.';

-- Create index on task_id for efficient queries
CREATE INDEX IF NOT EXISTS idx_push_configs_task_id
ON push_notification_configs(task_id);

-- Create index on config_id for lookups (when provided)
CREATE INDEX IF NOT EXISTS idx_push_configs_config_id
ON push_notification_configs(config_id) WHERE config_id IS NOT NULL;

COMMIT;




