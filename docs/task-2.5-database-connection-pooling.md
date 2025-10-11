# Database Connection Pooling - Subtask 2.5

## Overview

This document covers the database connection pooling implementation for the Loist Music Library MCP Server. It details the connection pool architecture, configuration, usage patterns, and best practices for PostgreSQL connectivity.

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Database Operations](#database-operations)
- [Performance Tuning](#performance-tuning)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Architecture

### Connection Pool Design

The implementation uses **psycopg2's ThreadedConnectionPool**, which provides:

- **Thread-safe connection management**
- **Automatic connection reuse**
- **Configurable min/max connections**
- **Connection validation and health checks**
- **Automatic retry logic**

### Components

1. **DatabasePool** (`database/pool.py`):
   - Main connection pool manager
   - Configuration and initialization
   - Connection lifecycle management
   - Health checks and statistics

2. **AudioTrackDB** (`database/utils.py`):
   - High-level database operations
   - Audio track CRUD operations
   - Search and query utilities

3. **Global Pool Instance**:
   - Singleton pattern for application-wide pool
   - Lazy initialization
   - Automatic cleanup

## Features

### ✅ Core Features

- **Connection Pooling**: Efficient reuse of database connections
- **Thread Safety**: Safe for concurrent access
- **Auto-Retry**: Automatic retry on transient failures
- **Health Checks**: Connection validation before use
- **Context Managers**: Safe connection handling with automatic cleanup
- **Statistics**: Connection and query metrics
- **Configuration**: Flexible configuration from multiple sources

### ✅ Advanced Features

- **Connection Validation**: Test connections before returning to pool
- **Retry Logic**: Configurable retry attempts with backoff
- **Error Handling**: Automatic rollback on exceptions
- **Monitoring**: Built-in statistics and metrics
- **Multiple Configurations**: Support for direct and Cloud SQL Proxy connections

## Configuration

### Environment Variables

```bash
# Direct Connection
export DB_HOST="34.121.42.105"
export DB_PORT="5432"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"

# Connection Pool Settings
export DB_MIN_CONNECTIONS="2"
export DB_MAX_CONNECTIONS="10"
export DB_COMMAND_TIMEOUT="30"

# Or Cloud SQL Proxy Connection
export DB_CONNECTION_NAME="loist-music-library:us-central1:loist-music-library-db"
export DB_NAME="music_library"
export DB_USER="music_library_user"
export DB_PASSWORD="<secure-password>"
```

### Application Config

Configuration is automatically loaded from `src/config.py`:

```python
from src.config import config

# Database connection settings
config.db_host              # Database host
config.db_port              # Database port (default: 5432)
config.db_name              # Database name
config.db_user              # Database user
config.db_password          # Database password
config.db_connection_name   # Cloud SQL connection name
config.db_min_connections   # Min connections (default: 2)
config.db_max_connections   # Max connections (default: 10)
config.db_command_timeout   # Command timeout in seconds (default: 30)

# Check if database is configured
print(config.is_database_configured)  # True/False

# Get connection URL
print(config.database_url)
# postgresql://user:pass@host:port/dbname
```

### Pool Configuration

```python
from database import DatabasePool

# Option 1: Use defaults from config
pool = DatabasePool()
pool.initialize()

# Option 2: Explicit configuration
pool = DatabasePool(
    min_connections=2,
    max_connections=10,
    database_url="postgresql://user:pass@host:5432/dbname"
)
pool.initialize()

# Option 3: Use global singleton
from database import get_connection_pool

pool = get_connection_pool()  # Auto-initializes
```

## Usage Examples

### Basic Connection Usage

```python
from database import get_connection

# Get a connection and execute a query
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM audio_tracks LIMIT 10")
        tracks = cur.fetchall()
        
        for track in tracks:
            print(f"Track: {track}")
```

### Using AudioTrackDB Utilities

#### Insert a Track

```python
from database.utils import AudioTrackDB
from uuid import uuid4

track_id = uuid4()
track = AudioTrackDB.insert_track(
    track_id=track_id,
    title="My Song",
    audio_path="audio/track-123.mp3",
    artist="Artist Name",
    album="Album Name",
    genre="Rock",
    year=2024,
    duration=240.5,
    channels=2,
    sample_rate=44100,
    bitrate=320,
    format="mp3",
    thumbnail_path="thumbnails/track-123.jpg"
)

print(f"Inserted track: {track['id']}")
```

#### Get Track by ID

```python
from uuid import UUID
from database.utils import AudioTrackDB

track_id = UUID("123e4567-e89b-12d3-a456-426614174000")
track = AudioTrackDB.get_track_by_id(track_id)

if track:
    print(f"Found: {track['artist']} - {track['title']}")
else:
    print("Track not found")
```

#### Search Tracks

```python
from database.utils import AudioTrackDB

# Full-text search
tracks = AudioTrackDB.search_tracks(
    search_term="beatles",
    limit=20
)

# Filter by artist and genre
tracks = AudioTrackDB.search_tracks(
    artist="The Beatles",
    genre="Rock",
    year=1967,
    limit=50
)

# Fuzzy search (typo-tolerant)
tracks = AudioTrackDB.fuzzy_search_tracks(
    search_term="beatls",  # Typo!
    similarity_threshold=0.3
)

for track in tracks:
    print(f"{track['artist']} - {track['title']}")
```

#### Update Track Status

```python
from uuid import UUID
from database.utils import AudioTrackDB

track_id = UUID("123e4567-e89b-12d3-a456-426614174000")

# Update status
success = AudioTrackDB.update_track_status(
    track_id=track_id,
    status="PROCESSING"
)

if success:
    print("Status updated")
```

#### List Tracks with Pagination

```python
from database.utils import AudioTrackDB

# Get first page (20 tracks)
tracks = AudioTrackDB.list_tracks(
    limit=20,
    offset=0,
    order_by="created_at",
    order_dir="DESC"
)

# Get second page
tracks = AudioTrackDB.list_tracks(
    limit=20,
    offset=20
)

# Get track count
total = AudioTrackDB.get_track_count()
print(f"Total tracks: {total}")
```

### Transaction Management

```python
from database import get_connection

with get_connection() as conn:
    try:
        with conn.cursor() as cur:
            # Start transaction
            cur.execute("BEGIN")
            
            # Multiple operations
            cur.execute("INSERT INTO audio_tracks (...) VALUES (...)")
            cur.execute("UPDATE audio_tracks SET status = 'COMPLETED' WHERE id = %s", (track_id,))
            
            # Commit transaction
            conn.commit()
            
    except Exception as e:
        # Automatic rollback on error
        conn.rollback()
        raise
```

### Raw Query Execution

```python
from database.utils import execute_raw_query, execute_raw_command

# Execute SELECT query
results = execute_raw_query(
    "SELECT artist, COUNT(*) as count FROM audio_tracks GROUP BY artist",
)

for row in results:
    print(f"{row['artist']}: {row['count']} tracks")

# Execute INSERT/UPDATE/DELETE
execute_raw_command(
    "UPDATE audio_tracks SET status = %s WHERE id = %s",
    params=("COMPLETED", track_id),
    commit=True
)
```

## Database Operations

### Audio Track Schema

```sql
CREATE TABLE audio_tracks (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  
  -- Metadata
  artist VARCHAR(255),
  title VARCHAR(255) NOT NULL,
  album VARCHAR(255),
  genre VARCHAR(255),
  year INTEGER,
  
  -- Technical specs
  duration NUMERIC(10,3),
  channels INTEGER,
  sample_rate INTEGER,
  bitrate INTEGER,
  format VARCHAR(20),
  
  -- Storage paths
  audio_path TEXT NOT NULL,
  thumbnail_path TEXT,
  
  -- Search vector
  search_vector TSVECTOR
);
```

### Available Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| **Create** | `AudioTrackDB.insert_track()` | Insert new track |
| **Read** | `AudioTrackDB.get_track_by_id()` | Get track by UUID |
| **Search** | `AudioTrackDB.search_tracks()` | Full-text search |
| **Fuzzy Search** | `AudioTrackDB.fuzzy_search_tracks()` | Typo-tolerant search |
| **Update** | `AudioTrackDB.update_track_status()` | Update status |
| **Delete** | `AudioTrackDB.delete_track()` | Delete track |
| **List** | `AudioTrackDB.list_tracks()` | List with pagination |
| **Count** | `AudioTrackDB.get_track_count()` | Get count |

## Performance Tuning

### Connection Pool Sizing

**Formula**: `max_connections = (core_count * 2) + effective_spindle_count`

**Recommendations**:

| Workload | Min Connections | Max Connections |
|----------|----------------|-----------------|
| Development | 1 | 5 |
| Low Traffic | 2 | 10 |
| Medium Traffic | 5 | 20 |
| High Traffic | 10 | 50 |

**Database Limits**:
- PostgreSQL default: `max_connections = 100`
- Our instance: `max_connections = 100`
- **Application pool should be < database max_connections**

### Connection Lifecycle

```python
# Default settings (from config)
min_connections = 2    # Always maintain 2 connections
max_connections = 10   # Never exceed 10 connections

# Connection timeout
command_timeout = 30   # Query timeout in seconds

# Pool behavior:
# - Starts with min_connections
# - Creates new connections on demand up to max_connections
# - Reuses idle connections
# - Validates connections before use
# - Closes excess connections over time
```

### Query Optimization

```python
# Use connection pooling for all database operations
from database import get_connection

# ✅ GOOD: Reuses connections
for i in range(100):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM audio_tracks WHERE id = %s", (track_id,))

# ❌ BAD: Creates new connection each time (without pooling)
import psycopg2
for i in range(100):
    conn = psycopg2.connect(database_url)  # Expensive!
    # ... use connection
    conn.close()
```

### Batch Operations

```python
from database import get_connection
import psycopg2.extras

# Bulk insert using execute_batch
with get_connection() as conn:
    with conn.cursor() as cur:
        tracks_data = [
            (uuid4(), "Track 1", "audio/1.mp3", "Artist 1"),
            (uuid4(), "Track 2", "audio/2.mp3", "Artist 2"),
            # ... more tracks
        ]
        
        psycopg2.extras.execute_batch(
            cur,
            "INSERT INTO audio_tracks (id, title, audio_path, artist) VALUES (%s, %s, %s, %s)",
            tracks_data
        )
        conn.commit()
```

## Monitoring

### Health Checks

```python
from database import get_connection_pool

pool = get_connection_pool()

# Perform health check
health = pool.health_check()

print(f"Healthy: {health['healthy']}")
print(f"Database Version: {health['database_version']}")
print(f"Min Connections: {health['min_connections']}")
print(f"Max Connections: {health['max_connections']}")

# Example output:
# {
#   "healthy": True,
#   "database_version": "PostgreSQL 15.3...",
#   "min_connections": 2,
#   "max_connections": 10,
#   "stats": {...},
#   "timestamp": 1696876543.21
# }
```

### Pool Statistics

```python
from database import get_connection_pool

pool = get_connection_pool()
stats = pool.get_stats()

print(f"Connections Created: {stats['connections_created']}")
print(f"Connections Closed: {stats['connections_closed']}")
print(f"Connections Failed: {stats['connections_failed']}")
print(f"Queries Executed: {stats['queries_executed']}")
print(f"Last Health Check: {stats['last_health_check']}")
```

### Logging

```python
import logging

# Enable debug logging for database operations
logging.getLogger("database").setLevel(logging.DEBUG)

# Logs include:
# - Connection pool initialization
# - Connection acquisition/release
# - Query execution
# - Errors and warnings
# - Health check results
```

## Troubleshooting

### Connection Errors

#### Error: "connection refused"

```python
# Symptom
psycopg2.OperationalError: could not connect to server

# Diagnosis
1. Check database is running
2. Verify host/port are correct
3. Check firewall rules
4. Verify Cloud SQL Proxy is running (if using)

# Solution
# For Cloud SQL Proxy:
./cloud_sql_proxy -instances=loist-music-library:us-central1:loist-music-library-db=tcp:5432

# Test connectivity:
psql -h localhost -p 5432 -U music_library_user -d music_library
```

#### Error: "too many connections"

```python
# Symptom
psycopg2.OperationalError: FATAL: too many connections

# Diagnosis
# Check current connections:
SELECT count(*) FROM pg_stat_activity;

# Check max connections:
SHOW max_connections;

# Solution
1. Reduce max_connections in pool
2. Increase PostgreSQL max_connections
3. Use connection pooler like PgBouncer
4. Investigate connection leaks
```

#### Error: "connection timeout"

```python
# Symptom
psycopg2.OperationalError: timeout expired

# Diagnosis
1. Check network latency
2. Verify query performance
3. Review connection timeout settings

# Solution
# Increase timeout
config.db_command_timeout = 60  # seconds

# Or per-query:
with get_connection() as conn:
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 60000")  # 60 seconds
```

### Pool Issues

#### Pool not initializing

```python
# Debug pool initialization
from database import DatabasePool

pool = DatabasePool(
    min_connections=1,
    max_connections=5,
    database_url="postgresql://user:pass@host:5432/dbname"
)

try:
    pool.initialize()
    print("Pool initialized successfully")
except Exception as e:
    print(f"Initialization failed: {e}")
    # Check:
    # 1. Database URL format
    # 2. Credentials
    # 3. Network connectivity
    # 4. PostgreSQL is running
```

#### Connection leaks

```python
# Monitor connections
from database import get_connection_pool

pool = get_connection_pool()
stats = pool.get_stats()

# If connections_created >> connections_closed:
# - Check for unclosed connections
# - Verify context managers are used
# - Look for exceptions preventing cleanup

# ✅ GOOD: Always use context managers
with get_connection() as conn:
    # Connection automatically released

# ❌ BAD: Manual connection management
conn = pool._pool.getconn()
# ... forgot to putconn()
```

## Best Practices

### ✅ DO:

1. **Use Context Managers**:
   ```python
   with get_connection() as conn:
       # Connection automatically released
   ```

2. **Reuse Connections**:
   ```python
   pool = get_connection_pool()  # Get once, use many times
   ```

3. **Handle Exceptions**:
   ```python
   try:
       with get_connection() as conn:
           # Database operations
   except psycopg2.Error as e:
       logger.error(f"Database error: {e}")
   ```

4. **Use Parameterized Queries**:
   ```python
   cur.execute("SELECT * FROM audio_tracks WHERE id = %s", (track_id,))
   ```

5. **Monitor Pool Health**:
   ```python
   health = pool.health_check()
   if not health["healthy"]:
       alert_operations_team()
   ```

### ❌ DON'T:

1. **Don't Create Multiple Pools**:
   ```python
   # BAD: Multiple pools compete for connections
   pool1 = DatabasePool()
   pool2 = DatabasePool()
   ```

2. **Don't Forget to Commit**:
   ```python
   # BAD: Changes not saved
   cur.execute("INSERT ...")
   # Needs: conn.commit()
   ```

3. **Don't Use String Formatting**:
   ```python
   # BAD: SQL injection risk!
   cur.execute(f"SELECT * FROM audio_tracks WHERE artist = '{artist}'")
   
   # GOOD: Use parameters
   cur.execute("SELECT * FROM audio_tracks WHERE artist = %s", (artist,))
   ```

4. **Don't Keep Connections Open**:
   ```python
   # BAD: Long-running connection
   conn = pool._pool.getconn()
   time.sleep(3600)  # Connection idle for an hour!
   ```

## Next Steps

After completing connection pooling:

1. ✅ **Subtask 2.6** - Develop Database Migration Scripts (ready!)
2. ✅ **Subtask 2.7** - Configure GCS Lifecycle Policies (complete in 2.3)
3. ✅ **Subtask 2.8** - Implement Signed URL Generation System (complete in 2.3)

## References

- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [Connection Pool Best Practices](https://wiki.postgresql.org/wiki/Number_Of_Database_Connections)
- [Cloud SQL Connection Pooling](https://cloud.google.com/sql/docs/postgres/manage-connections)

---

**Subtask 2.5 Status**: Complete ✅  
**Date**: 2025-10-09  
**Pool**: ThreadedConnectionPool (psycopg2)  
**Configuration**: Min 2, Max 10 connections

