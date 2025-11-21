#!/bin/bash
# Database Migration Validation Script
# Validates that the user_id column migration ran successfully
# Can be run locally with docker-compose or against deployed databases

set -e

# Configuration - defaults for local development
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-loist_mvp}"
DB_USER="${DB_USER:-loist_user}"
DB_PASSWORD="${DB_PASSWORD:-dev_password}"
DB_CONNECTION_NAME="${DB_CONNECTION_NAME:-}"

echo "🔍 Validating database migration..."
echo "📍 Database: $DB_HOST:$DB_PORT/$DB_NAME"
echo "👤 User: $DB_USER"
echo

# Function to run a database query
run_query() {
    local query="$1"
    local description="$2"

    if [ -n "$DB_CONNECTION_NAME" ]; then
        # Cloud SQL Proxy connection
        PGPASSWORD="$DB_PASSWORD" psql \
            -h "/cloudsql/$DB_CONNECTION_NAME" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -c "$query" \
            --quiet \
            2>/dev/null
    else
        # Direct connection
        PGPASSWORD="$DB_PASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -c "$query" \
            --quiet \
            2>/dev/null
    fi
}

# Test 1: Check if user_id column exists in audio_tracks table
echo "🧪 Test 1: Check user_id column exists"
echo "🔍 Checking user_id column"
if user_id_info=$(run_query "
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'audio_tracks' AND column_name = 'user_id';
"); then

    if echo "$user_id_info" | grep -q "user_id"; then
        echo "✅ PASS: user_id column exists"

        # Extract column properties using cut
        data_type=$(echo "$user_id_info" | grep user_id | cut -d'|' -f2 | tr -d ' ')
        is_nullable=$(echo "$user_id_info" | grep user_id | cut -d'|' -f3 | tr -d ' ')

        if [ "$data_type" = "integer" ]; then
            echo "✅ PASS: user_id column has correct data type (integer)"
        else
            echo "❌ FAIL: user_id column has wrong data type: '$data_type' (expected: 'integer')"
            exit 1
        fi

        if [ "$is_nullable" = "YES" ]; then
            echo "✅ PASS: user_id column is nullable (as expected for initial migration)"
        else
            echo "❌ FAIL: user_id column should be nullable in initial migration, got: '$is_nullable'"
            exit 1
        fi

    else
        echo "❌ FAIL: user_id column does not exist"
        exit 1
    fi
else
    echo "❌ FAIL: Could not query user_id column information"
    exit 1
fi

echo

# Test 2: Check if user_id indexes exist
echo "🧪 Test 2: Check user_id indexes exist"
echo "🔍 Checking user_id indexes"
if index_info=$(run_query "
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'audio_tracks' AND indexname LIKE '%user%';
"); then

    if echo "$index_info" | grep -q "idx_audio_tracks_user_id"; then
        echo "✅ PASS: idx_audio_tracks_user_id index exists"
    else
        echo "❌ FAIL: idx_audio_tracks_user_id index is missing"
        exit 1
    fi

    if echo "$index_info" | grep -q "idx_audio_tracks_user_status"; then
        echo "✅ PASS: idx_audio_tracks_user_status index exists"
    else
        echo "❌ FAIL: idx_audio_tracks_user_status index is missing"
        exit 1
    fi

    # Verify index definitions
    if echo "$index_info" | grep "idx_audio_tracks_user_id" | grep -q "WHERE (user_id IS NOT NULL)"; then
        echo "✅ PASS: idx_audio_tracks_user_id has correct partial index condition"
    else
        echo "❌ FAIL: idx_audio_tracks_user_id should be a partial index for non-null user_id values"
        exit 1
    fi

    if echo "$index_info" | grep "idx_audio_tracks_user_status" | grep -q "WHERE (user_id IS NOT NULL)"; then
        echo "✅ PASS: idx_audio_tracks_user_status has correct partial index condition"
    else
        echo "❌ FAIL: idx_audio_tracks_user_status should be a partial index for non-null user_id values"
        exit 1
fi

else
    echo "❌ FAIL: Could not query index information"
    exit 1
fi

echo

# Test 3: Check table comment mentions multi-user support
echo "🧪 Test 3: Check table comment mentions multi-user support"
echo "🔍 Checking table comment"
if comment_info=$(run_query "
    SELECT obj_description('audio_tracks'::regclass, 'pg_class');
"); then

    if echo "$comment_info" | grep -q "multi-user"; then
        echo "✅ PASS: Table comment mentions multi-user support"
    else
        echo "❌ FAIL: Table comment should mention multi-user support"
        echo "   Comment: $comment_info"
        exit 1
    fi
else
    echo "❌ FAIL: Could not query table comment"
    exit 1
fi

echo

# Test 4: Check column comment exists
echo "🧪 Test 4: Check user_id column comment exists"
echo "🔍 Checking user_id column comment"
if column_comment=$(run_query "
    SELECT col_description('audio_tracks'::regclass, ordinal_position)
    FROM information_schema.columns
    WHERE table_name = 'audio_tracks' AND column_name = 'user_id';
"); then

    if [ -n "$column_comment" ] && echo "$column_comment" | grep -q "SaaS"; then
        echo "✅ PASS: user_id column has descriptive comment mentioning SaaS"
    else
        echo "❌ FAIL: user_id column should have descriptive comment"
        echo "   Comment: $column_comment"
        exit 1
    fi
else
    echo "❌ FAIL: Could not query column comment"
    exit 1
fi

echo

# Test 5: Test inserting data with and without user_id
echo "🧪 Test 5: Test data insertion with user_id column"
echo "🔍 Testing data insertion with user_id column"
if run_query "
    -- Test inserting without user_id (should work)
    INSERT INTO audio_tracks (title, format, audio_gcs_path)
    VALUES ('Test Track 1', 'MP3', 'gs://test/audio1.mp3');

    -- Test inserting with user_id (should work)
    INSERT INTO audio_tracks (title, format, audio_gcs_path, user_id)
    VALUES ('Test Track 2', 'FLAC', 'gs://test/audio2.flac', 123);

    -- Clean up test data
    DELETE FROM audio_tracks WHERE title LIKE 'Test Track%';
" >/dev/null; then
    echo "✅ PASS: Can insert data with and without user_id values"
else
    echo "❌ FAIL: Data insertion test failed"
    exit 1
fi

echo
echo "🎉 Database migration validation completed successfully!"
echo "✅ All tests passed - user_id column migration is working correctly"
exit 0
