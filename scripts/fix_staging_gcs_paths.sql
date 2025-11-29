-- Fix GCS paths in staging database
-- Update audio_gcs_path and thumbnail_gcs_path to use correct bucket

-- First, let's see what needs to be updated
SELECT
    id,
    audio_gcs_path,
    thumbnail_gcs_path,
    title
FROM audio_tracks
WHERE audio_gcs_path LIKE '%loist-music-library-staging-audio%'
   OR thumbnail_gcs_path LIKE '%loist-music-library-staging-audio%'
LIMIT 10;

-- Update the GCS paths to use the correct bucket
UPDATE audio_tracks
SET
    audio_gcs_path = REPLACE(audio_gcs_path, 'loist-music-library-staging-audio', 'loist-music-library-bucket-staging'),
    thumbnail_gcs_path = REPLACE(thumbnail_gcs_path, 'loist-music-library-staging-audio', 'loist-music-library-bucket-staging'),
    updated_at = NOW()
WHERE audio_gcs_path LIKE '%loist-music-library-staging-audio%'
   OR thumbnail_gcs_path LIKE '%loist-music-library-staging-audio%';

-- Verify the changes
SELECT
    id,
    audio_gcs_path,
    thumbnail_gcs_path,
    title,
    updated_at
FROM audio_tracks
WHERE audio_gcs_path LIKE '%loist-music-library-bucket-staging%'
   OR thumbnail_gcs_path LIKE '%loist-music-library-bucket-staging%'
ORDER BY updated_at DESC
LIMIT 5;

-- Show summary of changes
SELECT
    COUNT(*) as total_tracks_updated
FROM audio_tracks
WHERE updated_at > NOW() - INTERVAL '1 minute';
