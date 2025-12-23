#!/bin/bash
# Grant database permissions using Cloud SQL proxy

set -e

PROJECT_ID="loist-music-library"
INSTANCE_ID="loist-music-library-db"
STAGING_DB_NAME="loist_mvp_staging"
APP_USER="music_library_user"
CONNECTION_NAME="${PROJECT_ID}:us-central1:${INSTANCE_ID}"

echo "========================================="
echo " Granting Database Permissions via Proxy"
echo "========================================="
echo "Database: $STAGING_DB_NAME"
echo "User: $APP_USER"
echo "Connection: $CONNECTION_NAME"
echo ""

# Detect platform and set download URL
PLATFORM=$(uname -s)
if [ "$PLATFORM" = "Darwin" ]; then
    PROXY_URL="https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.20.0/cloud-sql-proxy.darwin.amd64"
elif [ "$PLATFORM" = "Linux" ]; then
    PROXY_URL="https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.20.0/cloud-sql-proxy.linux.amd64"
else
    echo "❌ Unsupported platform: $PLATFORM"
    exit 1
fi

# Create SQL script
SQL_FILE="/tmp/grant_permissions_proxy.sql"
cat > "$SQL_FILE" << SQL_EOF
-- Grant database-level permissions
GRANT ALL PRIVILEGES ON DATABASE $STAGING_DB_NAME TO $APP_USER;

-- Connect to the database and grant schema permissions  
\c $STAGING_DB_NAME;

-- Grant all existing permissions
GRANT ALL ON SCHEMA public TO $APP_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $APP_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $APP_USER;

-- Grant future permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $APP_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $APP_USER;

-- Verify permissions
SELECT grantee, privilege_type 
FROM information_schema.role_table_grants 
WHERE grantee = '$APP_USER' 
LIMIT 5;
SQL_EOF

echo "Setting up Cloud SQL proxy..."
echo "Platform: $PLATFORM"
echo "Download URL: $PROXY_URL"

# Download Cloud SQL proxy if not available
if ! command -v cloud-sql-proxy &> /dev/null; then
    echo "Downloading Cloud SQL proxy..."
    curl -L -s "$PROXY_URL" -o /tmp/cloud-sql-proxy
    chmod +x /tmp/cloud-sql-proxy
    CLOUD_SQL_PROXY="/tmp/cloud-sql-proxy"
else
    CLOUD_SQL_PROXY="cloud-sql-proxy"
fi

# Start Cloud SQL proxy in background
echo "Starting Cloud SQL proxy..."
$CLOUD_SQL_PROXY "$CONNECTION_NAME" --port=5433 &
PROXY_PID=$!

# Wait for proxy to start
sleep 5

# Test connection and run SQL
echo "Testing database connection..."
if PGPASSWORD="$(gcloud secrets versions access latest --secret=db-password --project=$PROJECT_ID)" psql \
    -h 127.0.0.1 \
    -p 5433 \
    -U postgres \
    -d postgres \
    -c "SELECT version();" > /dev/null 2>&1; then
    
    echo "✅ Database connection successful"
    
    echo "Running permission grants..."
    PGPASSWORD="$(gcloud secrets versions access latest --secret=db-password --project=$PROJECT_ID)" psql \
        -h 127.0.0.1 \
        -p 5433 \
        -U postgres \
        -d postgres \
        -f "$SQL_FILE"
        
    echo "✅ Permissions granted successfully"
else
    echo "❌ Database connection failed"
    kill $PROXY_PID 2>/dev/null || true
    exit 1
fi

# Clean up
kill $PROXY_PID 2>/dev/null || true
rm -f "$SQL_FILE"

echo ""
echo "========================================="
echo " Permissions Granted Successfully"
echo "========================================="
echo "User '$APP_USER' now has full access to '$STAGING_DB_NAME'"
