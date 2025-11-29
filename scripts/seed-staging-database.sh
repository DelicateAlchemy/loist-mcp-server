#!/bin/bash
# Database Seeding Script for Staging Environment
# Populates staging database with anonymized test data

set -e

PROJECT_ID="loist-music-library"
STAGING_DB_NAME="loist_mvp_staging"
APP_USER="music_library_user"

echo "========================================="
echo " Staging Database Seeding"
echo "========================================="
echo ""

# Function to check command success
check_command() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
    else
        echo "❌ $1"
        exit 1
    fi
}

# Check if staging database exists and is accessible
echo "1. Checking staging database connectivity..."
echo "   Database: $STAGING_DB_NAME"
echo "   Instance: loist-music-library-db"
echo ""

# Test database connection (requires Cloud SQL proxy running or appropriate auth)
# For now, we'll use gcloud sql to run the seeding script

echo "2. Preparing seeding data..."
echo "   Creating anonymized test data for staging..."
echo ""

# Create a temporary SQL file with test data
SQL_FILE=$(mktemp)

cat > "$SQL_FILE" << 'EOF'
-- Staging Database Seeding Script
-- Inserts anonymized test data for development and testing

-- Clear existing data (staging only - be careful!)
DELETE FROM audio_metadata WHERE title LIKE 'Test%';
DELETE FROM audio_metadata WHERE artist LIKE 'Test%';

-- Insert test audio metadata
INSERT INTO audio_metadata (
    id, title, artist, album, duration, file_size, mime_type, bitrate,
    sample_rate, channels, created_at, updated_at, status, file_path
) VALUES
-- Classical music samples
(gen_random_uuid(), 'Test Symphony No. 1', 'Test Composer', 'Test Orchestral Works', 1800, 52428800, 'audio/flac', 1411, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-symphony-1.flac'),
(gen_random_uuid(), 'Test Piano Concerto', 'Test Pianist', 'Test Solo Works', 1500, 41943040, 'audio/flac', 1411, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-piano-concerto.flac'),

-- Jazz samples
(gen_random_uuid(), 'Test Jazz Quartet', 'Test Jazz Ensemble', 'Test Live Sessions', 2400, 67108864, 'audio/wav', 1411, 48000, 2, NOW(), NOW(), 'processed', 'audio/test-jazz-quartet.wav'),
(gen_random_uuid(), 'Test Blues Standard', 'Test Blues Band', 'Test Studio Recordings', 2100, 58720256, 'audio/mp3', 320, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-blues-standard.mp3'),

-- Rock/Pop samples
(gen_random_uuid(), 'Test Rock Anthem', 'Test Rock Band', 'Test Greatest Hits', 270, 9437184, 'audio/m4a', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-rock-anthem.m4a'),
(gen_random_uuid(), 'Test Pop Ballad', 'Test Pop Artist', 'Test Singles Collection', 195, 6815744, 'audio/mp3', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-pop-ballad.mp3'),

-- Electronic/Dance samples
(gen_random_uuid(), 'Test Electronic Mix', 'Test DJ', 'Test Club Tracks', 420, 14680064, 'audio/wav', 1411, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-electronic-mix.wav'),
(gen_random_uuid(), 'Test Ambient Soundscape', 'Test Electronic Artist', 'Test Ambient Works', 1800, 62914560, 'audio/flac', 1411, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-ambient-soundscape.flac'),

-- World/Traditional samples
(gen_random_uuid(), 'Test Traditional Folk', 'Test Folk Ensemble', 'Test Cultural Heritage', 300, 10485760, 'audio/mp3', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-traditional-folk.mp3'),
(gen_random_uuid(), 'Test World Music Fusion', 'Test World Music Collective', 'Test Global Sounds', 360, 12582912, 'audio/m4a', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-world-music-fusion.m4a'),

-- Test various file sizes and formats
(gen_random_uuid(), 'Test Small File', 'Test Artist', 'Test Mini Album', 30, 1048576, 'audio/mp3', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-small-file.mp3'),
(gen_random_uuid(), 'Test Large File', 'Test Artist', 'Test Maxi Album', 7200, 251658240, 'audio/flac', 1411, 96000, 2, NOW(), NOW(), 'processed', 'audio/test-large-file.flac'),

-- Test edge cases
(gen_random_uuid(), 'Test File With Special Chars: àáâãäå', 'Test Ümlaut Artist', 'Test Album with Symbols: ♪♫♬', 120, 4194304, 'audio/mp3', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-special-chars.mp3'),
(gen_random_uuid(), 'Test Very Long Title That Might Cause Display Issues In Some Interfaces', 'Test Artist With Extremely Long Name That Could Potentially Break Layouts', 'Test Album With Very Long Title That Might Cause Issues With Database Field Lengths', 240, 8388608, 'audio/m4a', 256, 44100, 2, NOW(), NOW(), 'processed', 'audio/test-long-titles.m4a');

-- Insert test full-text search vectors
UPDATE audio_metadata SET search_vector =
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(artist, '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(album, '')), 'C')
WHERE title LIKE 'Test%';

-- Insert some test thumbnails (placeholder data)
INSERT INTO thumbnails (
    id, audio_id, thumbnail_path, width, height, format, file_size, created_at
) SELECT
    gen_random_uuid(),
    id,
    'thumbnails/test-thumbnail-' || substr(md5(random()::text), 1, 8) || '.jpg',
    300,
    300,
    'jpeg',
    51200,
    NOW()
FROM audio_metadata
WHERE title LIKE 'Test%'
LIMIT 5;

-- Insert some processing status records for testing
INSERT INTO processing_status (
    id, audio_id, status, progress_percentage, error_message, started_at, completed_at
) SELECT
    gen_random_uuid(),
    id,
    'completed',
    100,
    NULL,
    NOW() - interval '1 hour',
    NOW()
FROM audio_metadata
WHERE title LIKE 'Test%'
LIMIT 3;

-- Insert a few "in progress" records for testing
INSERT INTO processing_status (
    id, audio_id, status, progress_percentage, error_message, started_at, completed_at
) SELECT
    gen_random_uuid(),
    id,
    'processing',
    75,
    NULL,
    NOW() - interval '30 minutes',
    NULL
FROM audio_metadata
WHERE title LIKE 'Test%'
ORDER BY id
LIMIT 2;

-- Insert some failed processing records for testing error handling
INSERT INTO processing_status (
    id, audio_id, status, progress_percentage, error_message, started_at, completed_at
) SELECT
    gen_random_uuid(),
    id,
    'failed',
    25,
    'Test error: Unable to process corrupted audio file',
    NOW() - interval '45 minutes',
    NOW() - interval '40 minutes'
FROM audio_metadata
WHERE title LIKE 'Test%'
ORDER BY id DESC
LIMIT 1;

COMMIT;

-- Verification query
SELECT
    COUNT(*) as total_test_tracks,
    COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_tracks,
    pg_size_pretty(pg_total_relation_size('audio_metadata')) as table_size
FROM audio_metadata
WHERE title LIKE 'Test%';

EOF

echo "3. Executing database seeding..."
echo "   Running SQL script against staging database..."
echo ""

# Execute the SQL script against the staging database
gcloud sql import sql "$STAGING_DB_NAME" "$SQL_FILE" \
    --database="$STAGING_DB_NAME" \
    --instance="loist-music-library-db" \
    --project="$PROJECT_ID" \
    --quiet

check_command "Database seeding completed"

# Clean up
rm "$SQL_FILE"

echo ""
echo "========================================="
echo " Staging Database Seeded Successfully!"
echo "========================================="
echo ""
echo "✅ Test data inserted:"
echo "   - 12 test audio tracks with various formats and sizes"
echo "   - Full-text search vectors for testing search functionality"
echo "   - Thumbnail records for testing image handling"
echo "   - Processing status records (completed, in-progress, failed)"
echo ""
echo "🔍 Test data includes:"
echo "   - Classical, Jazz, Rock, Electronic, and World music samples"
echo "   - Various file formats (FLAC, WAV, MP3, M4A)"
echo "   - Edge cases (special characters, long titles, different sizes)"
echo "   - Processing states for testing UI and error handling"
echo ""
echo "🧹 Cleanup Policy:"
echo "   - Test data is automatically cleaned up via staging lifecycle policies"
echo "   - GCS test files deleted after 24 hours"
echo "   - Database test records can be cleared with: DELETE FROM audio_metadata WHERE title LIKE 'Test%'"
echo ""
echo "Next steps:"
echo "1. Test the staging MCP server with the seeded data"
echo "2. Verify search functionality works correctly"
echo "3. Test thumbnail and processing status endpoints"
echo "4. Run integration tests against staging environment"
