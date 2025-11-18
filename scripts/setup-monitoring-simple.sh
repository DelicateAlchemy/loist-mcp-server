#!/bin/bash
# Simplified Cloud Monitoring setup for Cloud Run service
# This script creates basic monitoring for the loist-mcp-server

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-loist-music-library}"
SERVICE_NAME="loist-mcp-server"
REGION="us-central1"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-admin@loist.io}"

echo "🔍 Setting up Cloud Monitoring for $SERVICE_NAME in project $PROJECT_ID"

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com

echo "📊 Creating basic monitoring dashboard..."

# Create a simple dashboard using gcloud command
cat > simple-dashboard.json << EOF
{
  "displayName": "Loist MCP Server - Basic Monitoring",
  "mosaicLayout": {
    "columns": 12,
    "tiles": [
      {
        "width": 12,
        "height": 4,
        "widget": {
          "title": "Request Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Requests/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 12,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Request Latency",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"run.googleapis.com/request_latencies\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_DELTA",
                      "crossSeriesReducer": "REDUCE_PERCENTILE_95"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Latency (ms)",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF

# Create the dashboard
gcloud monitoring dashboards create --config-from-file=simple-dashboard.json

# Clean up
rm -f simple-dashboard.json

echo "✅ Basic monitoring dashboard created!"
echo ""
echo "📊 Dashboard: https://console.cloud.google.com/monitoring/dashboards"
echo ""
echo "🔍 To test monitoring:"
echo "  1. Visit the dashboard to see current metrics"
echo "  2. Test health endpoints:"
echo "     - https://loist-mcp-server-7de5nxpr4q-uc.a.run.app/health"
echo "     - https://loist-mcp-server-7de5nxpr4q-uc.a.run.app/ready"
echo ""
echo "📝 Next steps:"
echo "  - Set up uptime checks for external monitoring"
echo "  - Configure alerting policies manually in Cloud Console"
echo "  - Test alert notifications"
