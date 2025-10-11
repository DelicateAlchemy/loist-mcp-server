# Database Migrations - Subtask 2.6

## Overview

This document covers the database migration system for the Loist Music Library MCP Server. It provides a robust, version-controlled approach to schema changes with rollback capabilities and comprehensive testing.

## Table of Contents

- [Architecture](#architecture)
- [Migration Files](#migration-files)
- [Usage](#usage)
- [CLI Commands](#cli-commands)
- [Rollback Procedures](#rollback-procedures)
- [Testing](#testing)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Architecture

### Components

1. **DatabaseMigrator** (`database/migrate.py`):
   - Core migration engine
   - Tracks applied migrations
   - Handles transaction management
   - Provides rollback support

2. **Migration Files** (`database/migrations/*.sql`):
   - Version-controlled schema changes
   - Forward migrations (up)
   - Rollback migrations (down)

3. **CLI Interface** (`database/cli.py`):
   - User-friendly command interface
   - Migration management
   - Health checks
   - Data utilities

4. **Schema Tracking** (`schema_migrations` table):
   - Records applied migrations
   - Stores checksums for integrity
   - Tracks execution times

### Migration Flow

```
1. Read pending migrations from migrations/ directory
   ↓
2. Check schema_migrations table for applied versions
   ↓
3. Execute pending migrations in order
   ↓
4. Wrap each migration in a transaction
   ↓
5. Record successful migrations in schema_migrations
   ↓
6. Commit or rollback on error
```

## Migration Files

### File Naming Convention

```
{version}_{description}.sql
```

**Examples:**
- `001_initial_schema.sql`
- `002_add_user_preferences.sql`
- `003_add_playlist_feature.sql`

**Rollback Files:**
- `001_initial_schema_rollback.sql`
- `002_add_user_preferences_rollback.sql`

### Migration Structure

**Forward Migration:**

```sql
-- Migration: 001_initial_schema.sql
-- Description: Create initial database schema
-- Author: Your Name
-- Date: 2025-10-09

BEGIN;

-- Create tables
CREATE TABLE audio_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    -- ... more columns
);

-- Create indexes
CREATE INDEX idx_audio_tracks_title ON audio_tracks(title);

-- Create triggers
CREATE TRIGGER update_timestamp
    BEFORE UPDATE ON audio_tracks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;
```

**Rollback Migration:**

```sql
-- Rollback: 001_initial_schema_rollback.sql
-- WARNING: Destructive operation!

BEGIN;

DROP TRIGGER IF EXISTS update_timestamp ON audio_tracks;
DROP INDEX IF EXISTS idx_audio_tracks_title;
DROP TABLE IF EXISTS audio_tracks;

DELETE FROM schema_migrations WHERE version = '001_initial_schema';

COMMIT;
```

## Usage

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Set database configuration
export DB_CONNECTION_NAME="loist-music-library:us-central1:loist-music-library-db"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"

# Or use direct connection
export DB_HOST="34.121.42.105"
export DB_PORT="5432"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"
```

### Apply Migrations

**Method 1: Using CLI (Recommended)**

```bash
# Check migration status
python3 -m database.cli migrate status

# Apply all pending migrations
python3 -m database.cli migrate up

# Check migration status again
python3 -m database.cli migrate status
```

**Method 2: Using migrate.py directly**

```bash
# Apply migrations
python3 database/migrate.py --action=up

# Check status
python3 database/migrate.py --action=status

# Rollback specific migration
python3 database/migrate.py --action=down --migration=001_initial_schema
```

**Method 3: Using Python API**

```python
from database.migrate import DatabaseMigrator

# Create migrator
migrator = DatabaseMigrator()

# Apply migrations
success = migrator.migrate_up()

# Check status
migrator.get_status()
```

## CLI Commands

### Migration Commands

#### Status

Check which migrations are applied and pending:

```bash
python3 -m database.cli migrate status
```

Output:
```
=== Migration Status ===
Applied migrations: 1
  ✅ 001_initial_schema

Pending migrations: 0
```

#### Up

Apply all pending migrations:

```bash
python3 -m database.cli migrate up
```

Output:
```
2025-10-09 15:00:00 - INFO - Starting migration up
2025-10-09 15:00:00 - INFO - Found 1 pending migrations
2025-10-09 15:00:00 - INFO - Applying migration 001_initial_schema
2025-10-09 15:00:02 - INFO - Migration 001_initial_schema applied successfully in 1843ms
2025-10-09 15:00:02 - INFO - All migrations applied successfully
```

#### Down (Rollback)

Rollback a specific migration:

```bash
python3 -m database.cli migrate down --version=001_initial_schema
```

**⚠️ WARNING**: This removes the migration record but requires manual execution of rollback SQL!

### Health Check Commands

#### Test Connection

Test database connectivity:

```bash
python3 -m database.cli test-connection
```

Output:
```
✅ Connection successful
Database: music_library
User: music_library_user
Version: PostgreSQL 15.3 on x86_64-pc-linux-gnu
```

#### Health Check

Comprehensive health check:

```bash
python3 -m database.cli health
```

Output:
```
✅ Database is healthy
Database Version: PostgreSQL 15.3...
Min Connections: 2
Max Connections: 10
Connections Created: 2
Queries Executed: 5
```

#### Pool Statistics

View connection pool statistics:

```bash
python3 -m database.cli stats
```

Output:
```
=== Connection Pool Statistics ===
Connections Created: 10
Connections Closed: 8
Connections Failed: 0
Queries Executed: 152
Last Health Check: 2025-10-09 15:30:45
```

### Data Utilities

#### Create Sample Data

Generate test data:

```bash
# Create 100 sample tracks
python3 -m database.cli create-sample-data --count=100

# Create 1000 sample tracks
python3 -m database.cli create-sample-data --count=1000
```

## Rollback Procedures

### Standard Rollback Process

1. **Assess Impact**:
   ```sql
   -- Check how much data will be affected
   SELECT COUNT(*) FROM audio_tracks;
   ```

2. **Backup Data** (if needed):
   ```bash
   pg_dump -h 34.121.42.105 -U music_library_user -d music_library -t audio_tracks > backup.sql
   ```

3. **Execute Rollback SQL**:
   ```bash
   psql -h 34.121.42.105 -U music_library_user -d music_library -f database/migrations/001_initial_schema_rollback.sql
   ```

4. **Verify Rollback**:
   ```sql
   -- Check table no longer exists
   SELECT table_name FROM information_schema.tables WHERE table_name = 'audio_tracks';
   ```

5. **Remove Migration Record**:
   ```bash
   python3 -m database.cli migrate down --version=001_initial_schema
   ```

### Emergency Rollback

If a migration fails mid-execution:

```sql
-- Check schema_migrations table
SELECT * FROM schema_migrations;

-- If migration is recorded but failed
BEGIN;

-- Manual rollback (example)
DROP TABLE IF EXISTS audio_tracks;

-- Remove migration record
DELETE FROM schema_migrations WHERE version = '001_initial_schema';

COMMIT;
```

## Testing

### Unit Tests

Run migration tests:

```bash
# All migration tests
pytest tests/test_migrations.py -v

# Specific test
pytest tests/test_migrations.py::TestMigrationSystem::test_migrator_initialization -v
```

### Integration Tests

Test against real database:

```bash
# Set test database
export DB_NAME="music_library_test"

# Run migrations
python3 -m database.cli migrate up

# Run tests
pytest tests/test_migrations.py::TestMigrationOperations -v

# Rollback
python3 -m database.cli migrate down --version=001_initial_schema
```

### Manual Testing

```bash
# 1. Check current status
python3 -m database.cli migrate status

# 2. Apply migrations
python3 -m database.cli migrate up

# 3. Verify schema
psql -h 34.121.42.105 -U music_library_user -d music_library -c "\dt"

# 4. Test data operations
python3 -m database.cli create-sample-data --count=10

# 5. Query data
psql -h 34.121.42.105 -U music_library_user -d music_library -c "SELECT COUNT(*) FROM audio_tracks;"
```

## Best Practices

### ✅ DO:

1. **Version Control Migrations**:
   - Always commit migration files
   - Never modify applied migrations
   - Create new migrations for changes

2. **Use Transactions**:
   ```sql
   BEGIN;
   -- All DDL statements
   COMMIT;
   ```

3. **Test Before Production**:
   - Test on staging database first
   - Verify rollback procedures
   - Check performance impact

4. **Write Descriptive Names**:
   ```
   ✅ 002_add_user_preferences.sql
   ❌ 002_changes.sql
   ```

5. **Include Rollback Scripts**:
   - Always create corresponding rollback
   - Test rollback before production
   - Document any data loss

6. **Check for Existing Objects**:
   ```sql
   CREATE TABLE IF NOT EXISTS audio_tracks (...);
   CREATE INDEX IF NOT EXISTS idx_name ON table(column);
   DROP TABLE IF EXISTS old_table;
   ```

### ❌ DON'T:

1. **Don't Modify Applied Migrations**:
   - Create a new migration instead
   - Never change migration checksums

2. **Don't Skip Migrations**:
   - Always apply in order
   - Don't manually mark as applied

3. **Don't Ignore Errors**:
   - Fix issues immediately
   - Don't proceed with broken migrations

4. **Don't Forget Indexes**:
   - Add indexes for foreign keys
   - Include indexes for common queries

5. **Don't Make Large Changes**:
   - Break into smaller migrations
   - Easier to rollback and debug

## Troubleshooting

### Migration Failed to Apply

**Symptom:**
```
ERROR - Migration 002_add_feature failed: relation already exists
```

**Solution:**
```bash
# Check current database state
psql -h HOST -U USER -d DB -c "\dt"

# Check schema_migrations
psql -h HOST -U USER -d DB -c "SELECT * FROM schema_migrations;"

# If migration partially applied:
# 1. Manually rollback changes
# 2. Remove migration record
# 3. Fix migration SQL
# 4. Reapply
```

### Checksum Mismatch

**Symptom:**
```
WARNING - Migration checksum changed for 001_initial_schema
```

**Solution:**
```bash
# Never modify applied migrations!
# Instead:

# 1. Revert file to original
git checkout database/migrations/001_initial_schema.sql

# 2. Create new migration for changes
# 3. Apply new migration
```

### Connection Timeout

**Symptom:**
```
ERROR - Failed to connect to database: timeout expired
```

**Solution:**
```bash
# Check database is running
gcloud sql instances describe loist-music-library-db

# Check Cloud SQL Proxy
ps aux | grep cloud_sql_proxy

# Restart proxy if needed
./cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432

# Test connection
python3 -m database.cli test-connection
```

### Permission Denied

**Symptom:**
```
ERROR - permission denied for schema public
```

**Solution:**
```sql
-- Grant necessary permissions
GRANT ALL ON SCHEMA public TO music_library_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO music_library_user;
```

## Migration Checklist

Before applying migrations to production:

- [ ] Migration tested on development database
- [ ] Migration tested on staging database
- [ ] Rollback script created and tested
- [ ] Performance impact assessed
- [ ] Data backup created
- [ ] Team notified of maintenance window
- [ ] Monitoring alerts configured
- [ ] Rollback plan documented
- [ ] Migration reviewed by team
- [ ] Dependencies updated in requirements.txt

## Next Steps

After completing migrations:

1. ✅ **Task 2 Complete** - All database and storage infrastructure is ready!
2. Move on to **Task 3** - Implement audio processing features
3. Begin integration with MCP server tools

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Database Migration Best Practices](https://www.postgresql.org/docs/current/ddl-alter.html)
- [Transaction Management](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [Schema Versioning Strategies](https://martinfowler.com/articles/evodb.html)

---

**Subtask 2.6 Status**: Complete ✅  
**Date**: 2025-10-09  
**Migrations**: 1 initial schema  
**System**: Transaction-based with rollback support

