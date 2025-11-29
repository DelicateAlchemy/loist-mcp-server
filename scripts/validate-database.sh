#!/bin/bash
# Validate Cloud SQL database operations

set -e

PROJECT_ID="loist-music-library"
INSTANCE_NAME="loist-music-library-db"
DB_NAME="music_library"

echo "========================================="
echo " Cloud SQL Database Validation"
echo "========================================="
echo ""

# Test 1: Cloud SQL instance status
echo "1. Checking Cloud SQL Instance Status..."
echo "-------------------------------------"
INSTANCE_STATUS=$(gcloud sql instances describe $INSTANCE_NAME \
  --project=$PROJECT_ID \
  --format="value(state)" 2>&1)

if [ "$INSTANCE_STATUS" == "RUNNABLE" ]; then
    echo "✅ Cloud SQL instance is running"
else
    echo "❌ Cloud SQL instance is not running (Status: $INSTANCE_STATUS)"
    exit 1
fi
echo ""

# Test 2: Database connectivity
echo "2. Testing Database Connectivity..."
echo "-------------------------------------"
echo "Note: This test requires Cloud SQL Proxy and environment variables"

if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "⚠️  DB_USER or DB_PASSWORD not set, skipping connection test"
    echo "   Set these environment variables to test database connection"
else
    # Test connection using Python (if available)
    if command -v python3 &> /dev/null; then
        python3 -c "
import os
try:
    import psycopg2
    conn = psycopg2.connect(
        host='/cloudsql/$PROJECT_ID:us-central1:$INSTANCE_NAME',
        database='$DB_NAME',
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD']
    )
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
" 2>&1 || echo "⚠️  Connection test skipped (dependencies not available)"
    else
        echo "⚠️  Python not available, connection test skipped"
    fi
fi
echo ""

# Test 3: Check database exists
echo "3. Verifying Database Existence..."
echo "-------------------------------------"
DB_EXISTS=$(gcloud sql databases list \
  --instance=$INSTANCE_NAME \
  --project=$PROJECT_ID \
  --format="value(name)" | grep -c "^$DB_NAME$" || echo "0")

if [ "$DB_EXISTS" -gt 0 ]; then
    echo "✅ Database '$DB_NAME' exists"
else
    echo "❌ Database '$DB_NAME' not found"
fi
echo ""

# Test 4: Connection pooling info
echo "4. Cloud SQL Connection Info..."
echo "-------------------------------------"
gcloud sql instances describe $INSTANCE_NAME \
  --project=$PROJECT_ID \
  --format="table(connectionName,databaseVersion,settings.tier,settings.dataDiskSizeGb)" 2>&1
echo ""

echo "========================================="
echo "✅ Database validation complete"
echo "========================================="

