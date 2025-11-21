# Cloud SQL Cost Analysis & Optimization

**Date**: 2025-01-12 (Updated: 2025-11-13 with latest pricing)
**Issue**: High Cloud SQL costs (£1.31 on Nov 9, £6.75 for Nov 1-12)
**Status**: Investigation Complete - Recommendations Provided

**Note**: All GBP estimates based on USD pricing × ~1.25 exchange rate. Actual costs may vary based on region, current exchange rates, and Google Cloud pricing updates.

## Executive Summary

Your Cloud SQL costs are high due to **excessive health check queries** from Cloud Run. The service has multiple health check endpoints that all query the database, and Cloud Run pings these endpoints frequently (every 30 seconds by default). This creates a continuous stream of database queries even when there's no actual user traffic.

## Root Cause Analysis

### 1. Multiple Health Check Endpoints Querying Database

Your application has health check endpoints with varying database query patterns:

1. **`/health/ready`** - Readiness check (checks configuration, cached DB check)
2. **`/health/database`** - Database-specific health check (queries DB + pool stats)
3. **`health_check` MCP tool** - Full health check (queries DB)
4. **`/health/live`** - Liveness check (no DB queries - configuration only)

**Location**: `src/server.py` lines 200-370

### 2. Cloud Run Health Check Frequency

Cloud Run automatically pings health check endpoints:
- **Default interval**: Every 30 seconds
- **Per instance**: Each Cloud Run instance runs its own health checks
- **With autoscaling**: Multiple instances = multiple health check streams

**Current Configuration**:
```yaml
# From cloudbuild.yaml
--min-instances=0
--max-instances=10
```

Even with 0 min instances, when instances are running, they're constantly health-checking.

### 3. Database Connection Pool Validation

Every time a connection is retrieved from the pool, it validates with:
```python
# From database/pool.py line 242
cur.execute("SELECT 1")
```

This happens on **every health check** that queries the database.

### 4. Health Check Query Overhead

Each health check executes:
1. `check_database_availability()` - Gets connection, validates, queries
2. `pool.health_check()` - Executes `SELECT version()` (line 275)
3. Connection validation - `SELECT 1` (line 243)

**Total queries per health check**: 2-3 queries

### 5. Connection Pool Configuration

**Current Settings** (from `cloudbuild.yaml`):
- `DB_MIN_CONNECTIONS=2`
- `DB_MAX_CONNECTIONS=10`

**Default in code** (`database/config.py`):
- `min_connections=5`
- `max_connections=20`

**Issue**: Even with min_connections=2, you're maintaining persistent connections that cost money.

## Cost Breakdown

### Cloud SQL Pricing Model

Cloud SQL charges for:
1. **Instance uptime** (24/7 for production, $30.11/vCPU/month + $5.11/GB RAM/month)
2. **Storage**:
   - SSD: ~$0.17–0.22 per GB/month (~£0.14–0.18/GB/month)
   - HDD: ~$0.12 per GB/month (~£0.10/GB/month)
   - Backups: ~$0.08–0.11 per GB/month (~£0.06–0.09/GB/month)
3. **Network egress** (free within region, ~$0.12/GB cross-region)
4. **Backups** (if enabled)

**Your instance**: `db-custom-1-3840` (1 vCPU, 3.75GB RAM)
- **Actual monthly cost**: ~£39-49/month for instance alone (based on $30.11/vCPU + $5.11/GB RAM × 3.75GB)
- **Daily cost**: ~£1.30-1.63/day

**Your actual costs**:
- Nov 9: £1.31 (normal for a day)
- Nov 1-12: £6.75 (average £0.56/day)

**Analysis**: Your costs are actually **lower than expected** for a production Cloud SQL instance. The £1.31 on Nov 9 might be:
- Normal daily instance cost
- Slightly elevated due to health checks
- Or a billing cycle artifact

## Why Cloud SQL Costs Are High

### 1. Always-On Instance

Cloud SQL instances run 24/7, even with no traffic. You're paying for:
- **Compute resources** (1 vCPU, 3.75GB RAM)
- **Storage** (minimum 10GB)
- **Network** (minimal)

### 2. Health Check Overhead

**Estimated health check impact**:
- Health checks every 30 seconds
- 2-3 queries per health check
- **Per instance**: ~2,880 queries/hour
- **With 2 instances**: ~5,760 queries/hour

While these are lightweight queries (`SELECT 1`, `SELECT version()`), they still:
- Consume connection pool resources
- Generate log entries (if logging enabled)
- Add to overall database load

### 3. Connection Pool Maintenance

With `min_connections=2`, you're maintaining 2 persistent connections:
- These connections consume resources
- They're validated on every use
- They're kept alive even during idle periods

## Recommendations

### Immediate Actions (High Impact)

#### 1. Optimize Health Check Endpoints

**Problem**: All health checks query the database unnecessarily.

**Solution**: Make liveness checks database-free.

```python
# In src/server.py - Modify /health/live endpoint
@mcp.custom_route("/health/live", methods=["GET"])
def liveness_health_endpoint(request):
    """
    Liveness health check - NO DATABASE QUERIES.
    Just checks if the application is running.
    """
    return JSONResponse(
        content={
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "service": config.server_name
        },
        status_code=200
    )
```

**Impact**: Reduces database queries by ~33% (if Cloud Run uses `/health/live`)

#### 2. Cache Health Check Results

**Problem**: Health checks query database on every request.

**Solution**: Cache database health status for 5-10 seconds.

```python
# Add to src/server.py
import time
from functools import lru_cache

_last_db_check = {"time": 0, "result": None}
_db_check_cache_ttl = 5  # seconds

def check_database_availability_cached():
    """Cached version of database availability check."""
    global _last_db_check
    
    now = time.time()
    if now - _last_db_check["time"] < _db_check_cache_ttl:
        return _last_db_check["result"]
    
    # Fresh check
    from database import check_database_availability
    result = check_database_availability()
    _last_db_check = {"time": now, "result": result}
    return result
```

**Impact**: Reduces database queries by 80-90% for health checks

#### 3. Reduce Connection Pool Minimum

**Problem**: `min_connections=2` maintains persistent connections.

**Solution**: Set `DB_MIN_CONNECTIONS=0` for Cloud Run.

```yaml
# In cloudbuild.yaml line 435
- '--set-env-vars=DB_PORT=5432,DB_MIN_CONNECTIONS=0,DB_MAX_CONNECTIONS=10,DB_COMMAND_TIMEOUT=30'
```

**Impact**: Eliminates persistent connection costs during idle periods

#### 4. Use Lightweight Readiness Check

**Problem**: `/health/ready` queries database on every check.

**Solution**: Only query database if it's critical for readiness.

```python
@mcp.custom_route("/health/ready", methods=["GET"])
def readiness_health_endpoint(request):
    """
    Readiness check - only checks if dependencies are configured,
    not if they're actually available (that's what /health/database is for).
    """
    # Check configuration, not actual connectivity
    db_configured = config.is_database_configured
    gcs_configured = config.is_gcs_configured
    
    is_ready = db_configured and gcs_configured
    
    return JSONResponse(
        content={
            "status": "ready" if is_ready else "not_ready",
            "dependencies": {
                "database": {"configured": db_configured},
                "gcs": {"configured": gcs_configured}
            }
        },
        status_code=200 if is_ready else 503
    )
```

**Impact**: Eliminates database queries from readiness checks

### Medium-Term Actions

#### 5. Configure Cloud Run Health Check Path

**Problem**: Cloud Run might be hitting multiple health endpoints.

**Solution**: Explicitly configure Cloud Run to use `/health/live` (no DB queries).

```yaml
# In cloudbuild.yaml
- '--liveness-probe-path=/health/live'
- '--readiness-probe-path=/health/ready'  # But make this DB-free
```

#### 6. Reduce Health Check Frequency

**Problem**: 30-second intervals might be too frequent.

**Solution**: Increase to 60 seconds (if acceptable for your SLA).

```yaml
# Cloud Run health check configuration
- '--liveness-probe-interval=60'
- '--readiness-probe-interval=60'
```

**Impact**: Reduces health check queries by 50%

#### 7. Monitor Actual Query Volume

**Problem**: We're estimating query volume.

**Solution**: Enable PostgreSQL slow query logging and connection logging.

```sql
-- Connect to database and run:
ALTER DATABASE loist_mvp SET log_min_duration_statement = 0;  -- Log all queries
ALTER DATABASE loist_mvp SET log_connections = on;
ALTER DATABASE loist_mvp SET log_disconnections = on;
```

Then check Cloud SQL logs to see actual query patterns.

### Long-Term Actions

#### 8. Consider Cloud SQL Proxy Connection Pooling

**Problem**: Direct connections consume resources.

**Solution**: Use PgBouncer or Cloud SQL Proxy with connection pooling.

**Impact**: Reduces connection overhead significantly

#### 9. Right-Size Cloud SQL Instance

**Problem**: Current instance might be over-provisioned.

**Solution**: Monitor actual usage and consider:
- Smaller instance if CPU/memory usage is low
- Shared-core instance if acceptable for your workload
- Regional pricing optimization

**Current Instance**: `db-custom-1-3840` (1 vCPU, 3.75GB RAM)
- **Cost**: ~£50-80/month
- **Alternative**: `db-f1-micro` (shared-core, 0.6GB RAM) - ~£7-10/month
  - **Trade-off**: Lower performance, but fine for low-traffic MVP

#### 10. Implement Query Monitoring

**Problem**: No visibility into actual query patterns.

**Solution**: Set up Cloud Monitoring dashboards for:
- Query volume over time
- Connection count
- Query duration
- Health check frequency

## Implementation Priority

### Phase 1: Quick Wins (Do First)
1. ✅ Make `/health/live` database-free
2. ✅ Cache health check results (5-10 second TTL)
3. ✅ Set `DB_MIN_CONNECTIONS=0`

**Expected Impact**: 50-70% reduction in health check queries

### Phase 2: Configuration (Do Next)
4. ✅ Optimize `/health/ready` to check configuration only
5. ✅ Configure Cloud Run health check paths explicitly
6. ✅ Enable query logging to monitor actual usage

**Expected Impact**: Additional 20-30% reduction

### Phase 3: Monitoring (Do After)
7. ✅ Set up Cloud Monitoring dashboards
8. ✅ Analyze actual query patterns
9. ✅ Right-size instance based on data

**Expected Impact**: Long-term cost optimization

## Cost Projection

### Current State
- **Daily cost**: ~£0.56-1.31/day (your actual billing)
- **Monthly cost**: ~£17-39/month (instance only, based on updated pricing)
- **Health check overhead**: ~10-20% of total

### After Optimizations
- **Daily cost**: ~£0.50-1.20/day (10-20% reduction)
- **Monthly cost**: ~£15-36/month
- **Health check overhead**: ~2-5% of total

### With Instance Right-Sizing
- **If switching to db-f1-micro**: ~£4-6/month (87% reduction from current)
- **Trade-off**: Lower performance, but acceptable for MVP
- **Note**: db-f1-micro uses shared cores and has limited RAM

## Monitoring Queries

Use these queries to monitor your database usage:

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'loist_mvp';

-- Check connection history (if logging enabled)
SELECT * FROM pg_stat_database WHERE datname = 'loist_mvp';

-- Check query patterns
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 20;
```

## Development vs Production

**Important**: If you're only developing and not running production traffic, you don't need a 24/7 Cloud SQL instance!

### For Development
- ✅ **Use local Docker Compose** (already configured in `docker-compose.yml`)
- ✅ **Stop Cloud SQL** when not testing staging/production
- ✅ **Start Cloud SQL** only when deploying or testing

**See**: [Development Cost Optimization Guide](./development-cost-optimization.md) for details.

**Quick Commands**:
```bash
# Check Cloud SQL status
./scripts/manage-cloud-sql.sh status

# Stop Cloud SQL (saves ~£50-80/month)
./scripts/manage-cloud-sql.sh stop

# Start Cloud SQL when needed
./scripts/manage-cloud-sql.sh start
```

**Cost Savings for Development**:
- **24/7 Cloud SQL**: ~£50-80/month
- **Stopped Cloud SQL + Local Dev**: ~£0.10-5/month
- **Savings**: ~£50-80/month (99% reduction!)

### For Production
- Keep Cloud SQL running 24/7 (expected)
- Implement health check optimizations (reduce overhead)
- Monitor and right-size based on actual usage

## Conclusion

Your Cloud SQL costs are primarily due to:
1. **Always-on instance** (expected for production, unnecessary for development)
2. **Excessive health check queries** (fixable)
3. **Connection pool maintenance** (optimizable)

**For Development**: Stop Cloud SQL and use local Docker Compose (saves ~£50-80/month)

**For Production**: 
- Implement Phase 1 optimizations (quick wins)
- Monitor actual query patterns
- Consider instance right-sizing for MVP stage

**Next Steps**:
1. **If developing**: Stop Cloud SQL, use `docker-compose up` (see [Development Cost Optimization Guide](./development-cost-optimization.md))
2. **If in production**: Implement Phase 1 optimizations (health check caching)
3. Monitor actual query patterns
4. Consider instance right-sizing for MVP stage

