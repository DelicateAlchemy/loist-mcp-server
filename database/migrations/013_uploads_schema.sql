-- Browser Upload Tracking Schema
-- migration_013_uploads_schema.sql
-- Add uploads table for the browser upload & ingestion flow (LOI-45)
--
-- Flow:
--   1. POST /api/v1/uploads               -> row created (awaiting_upload) + GCS signed PUT URL
--   2. Browser PUTs file directly to GCS  -> staging prefix uploads/{upload_id}/...
--   3. POST /api/v1/uploads/{id}/process  -> status pending, processing job dispatched
--   4. GET /api/v1/jobs/{id}              -> poll status until complete/failed
--
-- The staging GCS prefix (uploads/) should carry a lifecycle rule deleting
-- objects after 24h so abandoned uploads don't accumulate — see
-- scripts/setup-upload-staging-lifecycle.sh.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE: uploads
-- One row per browser upload attempt; doubles as the processing job record.
-- ============================================================================

CREATE TABLE uploads (
    -- Primary identification (also used as the job_id in the polling API)
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Client-declared file facts (validated at signing time, re-validated
    -- against the staged GCS object at process time)
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(255) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),

    -- Staging object path within the bucket (uploads/{upload_id}/{filename})
    gcs_object_name TEXT NOT NULL,

    -- Lifecycle: awaiting_upload -> pending -> processing -> complete | failed
    -- (failed uploads may be re-processed: failed -> pending)
    status VARCHAR(20) NOT NULL DEFAULT 'awaiting_upload'
        CHECK (status IN ('awaiting_upload', 'pending', 'processing', 'complete', 'failed')),

    -- Set on successful processing
    audio_id UUID REFERENCES audio_tracks(id) ON DELETE SET NULL,

    -- Set on failed processing
    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_uploads_status ON uploads(status);
CREATE INDEX idx_uploads_created_at ON uploads(created_at);

COMMENT ON TABLE uploads IS 'Browser upload staging + processing job tracking (LOI-45)';
COMMENT ON COLUMN uploads.status IS 'awaiting_upload -> pending -> processing -> complete | failed';

COMMIT;
