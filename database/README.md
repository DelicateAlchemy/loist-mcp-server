# Database Schema and Migrations

This directory contains the PostgreSQL database schema, migrations, and configuration for the Loist MVP audio metadata service.

## Overview

The database is designed to store audio file metadata with optimal performance for:
- Full-text search across metadata fields
- Fuzzy matching for artist/title searches
- Status tracking for processing pipeline
- Technical audio specifications
- Google Cloud Storage path management

## Performance Targets

- **Query Performance**: Sub-200ms for 100K+ tracks
- **Search Capability**: Full-text search with fuzzy matching
- **Scalability**: Designed to handle millions of tracks
- **Reliability**: ACID compliance with proper constraints

## Schema Design

### Core Table: `audio_tracks`

The main table stores all audio metadata and technical specifications:

```sql
-- Key fields
id UUID PRIMARY KEY                    -- Unique identifier
status VARCHAR(20)                     -- Processing state
artist VARCHAR(500)                    -- Artist name
title VARCHAR(500) NOT NULL            -- Track title (required)
album VARCHAR(500)                     -- Album name
genre VARCHAR(100)                     -- Music genre
year INTEGER                           -- Release year
duration_seconds NUMERIC(10,3)        -- Precise duration
channels SMALLINT                      -- Audio channels
sample_rate INTEGER                    -- Sample rate in Hz
bitrate INTEGER                        -- Bitrate in bps
format VARCHAR(20)                     -- Audio format
file_size_bytes BIGINT                 -- File size
audio_gcs_path TEXT                    -- GCS path to audio file
thumbnail_gcs_path TEXT                -- GCS path to artwork
search_vector TSVECTOR                 -- Full-text search vector
```

### Key Design Decisions

1. **Single Table Design**: Denormalized for MVP simplicity, avoids JOIN complexity
2. **UUID Primary Keys**: Better for distributed systems, no collision risk
3. **Precise Duration**: NUMERIC(10,3) for millisecond accuracy
4. **Weighted Search**: Title/artist highest priority, album medium, genre lower
5. **Partial Indexes**: Exclude completed tracks for status filtering

## Indexes

### Performance Indexes
- `idx_audio_tracks_search_vector`: GIN index for full-text search
- `idx_audio_tracks_status`: Partial index for status filtering
- `idx_audio_tracks_created_at`: Timestamp-based queries
- `idx_audio_tracks_artist_album`: Composite index for common queries

### Fuzzy Search Indexes
- `idx_audio_tracks_artist`: Trigram index for fuzzy artist matching
- `idx_audio_tracks_title`: Trigram index for fuzzy title matching
- `idx_audio_tracks_album`: Trigram index for fuzzy album matching

## Extensions

- **uuid-ossp**: UUID generation functions
- **pg_trgm**: Trigram matching for fuzzy search

## Files

### Migrations
- `migrations/001_initial_schema.sql`: Initial schema creation
- `migrate.py`: Migration runner with rollback support

### Configuration
- `config.py`: Database connection and pool management
- `test_queries.sql`: Performance and functionality tests

### Documentation
- `README.md`: This file

## Usage

### Running Migrations

```bash
# Apply all pending migrations
python migrate.py --action=up --database-url=postgresql://user:pass@host:port/db

# Check migration status
python migrate.py --action=status --database-url=postgresql://user:pass@host:port/db

# Rollback specific migration (manual rollback required)
python migrate.py --action=down --migration=001 --database-url=postgresql://user:pass@host:port/db
```

### Environment Variables

```bash
# Database connection
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=loist_mvp
export DB_USER=loist_user
export DB_PASSWORD=your_password

# Connection pool settings
export DB_MIN_CONNECTIONS=5
export DB_MAX_CONNECTIONS=20

# Performance settings
export DB_STATEMENT_TIMEOUT=30000
export DB_IDLE_TIMEOUT=60000
```

### Testing Schema

```bash
# Run test queries to validate performance
psql -d loist_mvp -f test_queries.sql
```

## Example Queries

### Full-Text Search
```sql
SELECT id, artist, title, album, 
       ts_rank(search_vector, to_tsquery('english', 'rock & music')) AS rank
FROM audio_tracks
WHERE search_vector @@ to_tsquery('english', 'rock & music')
  AND status = 'COMPLETED'
ORDER BY rank DESC
LIMIT 20;
```

### Fuzzy Artist Search
```sql
SELECT id, artist, title, album, similarity(artist, 'beatles') AS similarity_score
FROM audio_tracks
WHERE artist % 'beatles'
  AND status = 'COMPLETED'
ORDER BY similarity_score DESC
LIMIT 20;
```

### Status Filtering
```sql
SELECT id, title, artist, created_at
FROM audio_tracks
WHERE status = 'PENDING'
ORDER BY created_at ASC
LIMIT 50;
```

## Monitoring

### Table Statistics
```sql
SELECT 
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
WHERE tablename = 'audio_tracks';
```

### Index Usage
```sql
SELECT 
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'audio_tracks'
ORDER BY idx_tup_read DESC;
```

## Security Considerations

- **Input Validation**: CHECK constraints prevent invalid data
- **Path Validation**: GCS paths must start with `gs://`
- **SQL Injection**: Use parameterized queries
- **Connection Pooling**: Limits concurrent connections
- **Timeouts**: Prevents long-running queries

## Backup and Recovery

### Backup
```bash
# Full database backup
pg_dump -h localhost -U loist_user -d loist_mvp > backup.sql

# Schema only
pg_dump -h localhost -U loist_user -d loist_mvp --schema-only > schema.sql
```

### Recovery
```bash
# Restore from backup
psql -h localhost -U loist_user -d loist_mvp < backup.sql
```

## Performance Tuning

### PostgreSQL Configuration
```sql
-- Memory settings
SET work_mem = '256MB';
SET shared_buffers = '256MB';

-- Query optimization
SET random_page_cost = 1.1;
SET effective_cache_size = '1GB';
```

### Index Maintenance
```sql
-- Analyze tables for query planner
ANALYZE audio_tracks;

-- Reindex if needed
REINDEX INDEX idx_audio_tracks_search_vector;
```

## Troubleshooting

### Common Issues

1. **Slow Queries**: Check index usage with `EXPLAIN ANALYZE`
2. **Connection Errors**: Verify connection pool settings
3. **Search Issues**: Ensure `pg_trgm` extension is installed
4. **UUID Errors**: Ensure `uuid-ossp` extension is installed

### Debug Queries
```sql
-- Check active connections
SELECT * FROM pg_stat_activity WHERE datname = 'loist_mvp';

-- Check lock waits
SELECT * FROM pg_locks WHERE NOT granted;

-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

## Future Enhancements

### Phase 2 Improvements
- **Normalization**: Separate artists, albums, genres tables
- **Partitioning**: Partition by year or status for large datasets
- **Advanced Search**: Elasticsearch integration for complex queries
- **Caching**: Redis cache for frequently accessed data
- **Analytics**: Time-series data for usage patterns

### Performance Optimizations
- **Materialized Views**: Pre-computed search results
- **Partial Indexes**: More granular status filtering
- **Connection Pooling**: PgBouncer for production
- **Read Replicas**: Separate read/write workloads
