# Development Cost Optimization Guide

**Goal**: Eliminate Cloud SQL costs during development by using local PostgreSQL and stopping Cloud SQL instances when not needed.

**Updated**: 2025-11-13 with latest Google Cloud pricing. All GBP estimates based on USD pricing × ~1.25 exchange rate. Actual costs may vary based on region, current exchange rates, and Google Cloud pricing updates.

## Current Setup Analysis

### ✅ What You Already Have (FREE)

1. **Local Development with Docker Compose** (`docker-compose.yml`)
   - Local PostgreSQL container (`postgres:16-alpine`)
   - **Cost**: $0 (runs on your machine)
   - **Status**: Already configured and working!

2. **Local Database Configuration**
   ```yaml
   # From docker-compose.yml
   postgres:
     image: postgres:16-alpine
     environment:
       - POSTGRES_DB=loist_mvp
       - POSTGRES_USER=loist_user
       - POSTGRES_PASSWORD=dev_password
   ```

### 💰 What's Costing Money

1. **Cloud SQL Instance** (`loist-music-library-db`)
   - **Type**: `db-custom-1-3840` (1 vCPU, 3.75GB RAM)
   - **Cost**: ~£39-49/month (~£1.30-1.63/day) based on $30.11/vCPU + $5.11/GB RAM × 3.75GB
   - **Status**: Running 24/7 even when you're not developing

2. **Cloud Run Services** (if running)
   - Staging: `music-library-mcp-staging`
   - Production: `music-library-mcp`
   - **Cost**: ~£0-11/month (scales to zero, generous free tier: 180,000 vCPU-seconds, 360,000 GiB-seconds RAM, 2 million requests/month)

## Solution: Use Local Development Only

### For Development Work

**Use your existing Docker Compose setup** - it's already perfect for development!

```bash
# Start local development environment
docker-compose up -d

# This gives you:
# - MCP server on http://localhost:8080
# - PostgreSQL on localhost:5432
# - All your code mounted for hot reload
# - Cost: $0
```

**Your `docker-compose.yml` is already configured correctly:**
- Uses local PostgreSQL (not Cloud SQL)
- Has all the right environment variables
- Includes database migrations
- Perfect for development!

### Stop Cloud SQL When Not Needed

When you're not actively testing staging/production deployments:

```bash
# Stop Cloud SQL instance (saves ~£1.67/day)
gcloud sql instances patch loist-music-library-db \
  --activation-policy=NEVER \
  --project=loist-music-library

# Start it again when needed (takes ~2-3 minutes)
gcloud sql instances patch loist-music-library-db \
  --activation-policy=ALWAYS \
  --project=loist-music-library
```

**Cost Impact**:
- **Stopped**: Only pay for storage (~£0.14-0.18/GB SSD/month, typically £0.10-0.20/month total)
- **Running**: Pay for compute + storage (~£39-49/month)
- **Savings**: ~£39-49/month when stopped

## Recommended Development Workflow

### Daily Development

1. **Use Local Docker Compose** (always)
   ```bash
   docker-compose up -d
   ```

2. **Keep Cloud SQL Stopped** (unless testing staging)
   ```bash
   # Check if instance is running
   gcloud sql instances describe loist-music-library-db \
     --format="value(state)" \
     --project=loist-music-library
   
   # If it's RUNNABLE, stop it:
   gcloud sql instances patch loist-music-library-db \
     --activation-policy=NEVER \
     --project=loist-music-library
   ```

3. **Work Locally**
   - All database operations use local PostgreSQL
   - No Cloud SQL costs
   - Fast iteration (no network latency)
   - Can work offline

### When You Need Staging/Production Testing

1. **Start Cloud SQL** (only when needed)
   ```bash
   gcloud sql instances patch loist-music-library-db \
     --activation-policy=ALWAYS \
     --project=loist-music-library
   
   # Wait 2-3 minutes for instance to start
   gcloud sql instances wait loist-music-library-db \
     --project=loist-music-library
   ```

2. **Deploy to Staging** (if needed)
   ```bash
   git push origin dev  # Triggers staging deployment
   ```

3. **Stop Cloud SQL After Testing**
   ```bash
   gcloud sql instances patch loist-music-library-db \
     --activation-policy=NEVER \
     --project=loist-music-library
   ```

## Cost Comparison

### Current Setup (24/7 Cloud SQL)
- **Cloud SQL**: ~£39-49/month
- **Cloud Run**: ~£0-5/month (scales to zero)
- **Total**: ~£39-54/month

### Optimized Setup (Local Dev + Stop Cloud SQL)
- **Local PostgreSQL**: £0 (Docker Compose)
- **Cloud SQL (stopped)**: ~£0.10-0.20/month (storage only)
- **Cloud Run**: ~£0-5/month (scales to zero)
- **Total**: ~£0.10-5/month

**Savings**: ~£39-49/month (97-99% reduction!)

## Quick Reference Commands

### Check Cloud SQL Status
```bash
gcloud sql instances describe loist-music-library-db \
  --format="table(name,state,settings.activationPolicy)" \
  --project=loist-music-library
```

### Stop Cloud SQL
```bash
gcloud sql instances patch loist-music-library-db \
  --activation-policy=NEVER \
  --project=loist-music-library
```

### Start Cloud SQL
```bash
gcloud sql instances patch loist-music-library-db \
  --activation-policy=ALWAYS \
  --project=loist-music-library

# Wait for it to be ready
gcloud sql instances wait loist-music-library-db \
  --project=loist-music-library
```

### Local Development
```bash
# Start local environment
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Stop local environment
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

## Alternative: Use Smaller Instance for Staging

If you need staging to be always available but want to save money:

### Option 1: Shared-Core Instance
```bash
# Create a smaller staging instance
gcloud sql instances create loist-music-library-db-staging \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --activation-policy=ALWAYS \
  --project=loist-music-library

# Cost: ~£4-6/month (vs £39-49/month for current instance)
```

### Option 2: Schedule Start/Stop
Use Cloud Scheduler to automatically stop Cloud SQL during off-hours:

```bash
# Stop at 6 PM daily
gcloud scheduler jobs create http stop-cloud-sql \
  --schedule="0 18 * * *" \
  --uri="https://sqladmin.googleapis.com/v1/projects/loist-music-library/instances/loist-music-library-db" \
  --http-method=PATCH \
  --message-body='{"settings":{"activationPolicy":"NEVER"}}' \
  --oauth-service-account-email=your-service-account@loist-music-library.iam.gserviceaccount.com

# Start at 9 AM daily
gcloud scheduler jobs create http start-cloud-sql \
  --schedule="0 9 * * *" \
  --uri="https://sqladmin.googleapis.com/v1/projects/loist-music-library/instances/loist-music-library-db" \
  --http-method=PATCH \
  --message-body='{"settings":{"activationPolicy":"ALWAYS"}}' \
  --oauth-service-account-email=your-service-account@loist-music-library.iam.gserviceaccount.com
```

**Savings**: ~50% if you only need it during business hours

## Best Practices

### ✅ DO

1. **Use local Docker Compose for all development**
2. **Stop Cloud SQL when not actively testing staging/production**
3. **Start Cloud SQL only when deploying or testing**
4. **Use Cloud SQL for staging/production only**

### ❌ DON'T

1. **Don't leave Cloud SQL running 24/7 during development**
2. **Don't use Cloud SQL for local development** (use Docker Compose)
3. **Don't forget to stop Cloud SQL after testing**

## Migration Strategy

### Step 1: Verify Local Setup Works
```bash
# Start local environment
docker-compose up -d

# Test database connection
docker-compose exec mcp-server python -c "
from database import get_connection_pool
pool = get_connection_pool()
health = pool.health_check()
print('Database health:', health['healthy'])
"
```

### Step 2: Stop Cloud SQL
```bash
gcloud sql instances patch loist-music-library-db \
  --activation-policy=NEVER \
  --project=loist-music-library
```

### Step 3: Verify Local Development
```bash
# Test your MCP server locally
curl http://localhost:8080/health/live

# Test database operations
# (your existing local tests should work)
```

### Step 4: Start Cloud SQL Only When Needed
```bash
# Only when deploying to staging/production
gcloud sql instances patch loist-music-library-db \
  --activation-policy=ALWAYS \
  --project=loist-music-library
```

## Monitoring Costs

### Check Current Costs
```bash
# View Cloud SQL costs
gcloud billing accounts list
gcloud billing projects describe loist-music-library

# View instance status
gcloud sql instances list \
  --format="table(name,state,settings.tier,settings.activationPolicy)" \
  --project=loist-music-library
```

### Set Up Billing Alerts
1. Go to [Google Cloud Console > Billing](https://console.cloud.google.com/billing)
2. Select your billing account
3. Create budget alert for Cloud SQL costs
4. Set threshold (e.g., £10/month)

## Summary

**For Development**:
- ✅ Use `docker-compose up` (local PostgreSQL - FREE)
- ✅ Stop Cloud SQL when not testing staging/production
- ✅ Start Cloud SQL only when deploying

**Expected Savings**:
- **Before**: ~£39-49/month (24/7 Cloud SQL)
- **After**: ~£0.10-5/month (stopped Cloud SQL + local dev)
- **Savings**: ~£39-49/month (97-99% reduction!)

**Your local Docker Compose setup is already perfect for development - just use it and stop Cloud SQL when you're not actively testing staging/production!**

