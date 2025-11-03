#!/bin/bash
# Database migration script for Cloud Build
# This script runs migrations during deployment

set -e

echo "Running database migrations..."

# Get database credentials from secrets
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-staging --format="value" 2>/dev/null || echo "")
DB_CONNECTION_NAME=$(gcloud secrets versions access latest --secret=db-connection-name-staging --format="value" 2>/dev/null || echo "")
DB_NAME=loist_mvp_staging

if [ -z "$DB_PASSWORD" ] || [ -z "$DB_CONNECTION_NAME" ]; then
    echo "Database secrets not available, skipping migrations"
    exit 0
fi

# Run migrations using Cloud SQL proxy
python3 -c "
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Database connection
conn_string = f'postgresql://music_library_user:{os.environ.get(\"DB_PASSWORD\")}@/loist_mvp_staging?host=/cloudsql/{os.environ.get(\"DB_CONNECTION_NAME\")}'
print('Connecting to database...')

try:
    conn = psycopg2.connect(conn_string)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'audio_tracks')\")
    exists = cursor.fetchone()[0]
    
    if exists:
        print('Database schema already exists, skipping migration')
    else:
        print('Running initial migration...')
        
        # Read and execute migration file
        with open('database/migrations/001_initial_schema.sql', 'r') as f:
            migration_sql = f.read()
        
        cursor.execute(migration_sql)
        print('Migration completed successfully!')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'Migration failed: {e}')
    sys.exit(1)
" DB_PASSWORD="$DB_PASSWORD" DB_CONNECTION_NAME="$DB_CONNECTION_NAME"
