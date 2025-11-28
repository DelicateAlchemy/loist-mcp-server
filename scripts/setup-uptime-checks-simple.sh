#!/bin/bash
# Simplified uptime checks for Cloud Run service
# This script creates basic uptime checks to monitor service availability

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-loist-music-library}"
SERVICE_URL="${SERVICE_URL:-https://music-library-mcp-7de5nxpr4q-uc.a.run.app}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-admin@loist.io}"

echo "🔍 Setting up uptime checks for $SERVICE_URL in project $PROJECT_ID"

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable monitoring.googleapis.com

echo "🏥 Creating health endpoint uptime check..."
gcloud monitoring uptime create "Loist MCP Server - Health Check" \
    --synthetic-target="$SERVICE_URL/health" \
    --period=1 \
    --timeout=10 \

echo "✅ Creating readiness endpoint uptime check..."
gcloud monitoring uptime create "Loist MCP Server - Readiness Check" \
    --synthetic-target="$SERVICE_URL/ready" \
    --period=1 \
    --timeout=10 \

echo "🔗 Creating oEmbed endpoint uptime check..."
gcloud monitoring uptime create "Loist MCP Server - oEmbed Check" \
    --synthetic-target="$SERVICE_URL/.well-known/oembed.json" \
    --period=5 \
    --timeout=10 \

echo "✅ Uptime checks setup complete!"
echo ""
echo "🔍 Uptime Checks: https://console.cloud.google.com/monitoring/uptime"
echo ""
echo "📊 Test endpoints:"
echo "  - Health: $SERVICE_URL/health"
echo "  - Readiness: $SERVICE_URL/ready"
echo "  - oEmbed Discovery: $SERVICE_URL/.well-known/oembed.json"
echo ""
echo "📝 Next steps:"
echo "  - Verify uptime checks are running"
echo "  - Set up alerting policies manually in Cloud Console"
echo "  - Monitor dashboard for metrics"
