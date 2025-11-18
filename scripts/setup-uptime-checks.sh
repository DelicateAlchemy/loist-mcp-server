#!/bin/bash
# Setup uptime checks for Cloud Run service
# This script creates uptime checks to monitor service availability

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-loist-music-library}"
SERVICE_URL="${SERVICE_URL:-https://loist-mcp-server-7de5nxpr4q-uc.a.run.app}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-admin@loist.io}"

echo "🔍 Setting up uptime checks for $SERVICE_URL in project $PROJECT_ID"

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable monitoring.googleapis.com

# Create notification channel for email alerts
echo "📧 Creating notification channel for uptime checks..."
NOTIFICATION_CHANNEL=$(gcloud alpha monitoring channels create \
    --display-name="Loist MCP Server Uptime Alerts" \
    --type=email \
    --channel-labels=email_address="$NOTIFICATION_EMAIL" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -z "$NOTIFICATION_CHANNEL" ]; then
    echo "⚠️  Could not create notification channel. Please create one manually in Cloud Console."
    echo "   Go to: https://console.cloud.google.com/monitoring/alerting/notifications"
    NOTIFICATION_CHANNEL="projects/$PROJECT_ID/notificationChannels/placeholder"
fi

# Create uptime check for health endpoint
echo "🏥 Creating health endpoint uptime check..."
cat > health-uptime-check.json << EOF
{
  "displayName": "Loist MCP Server - Health Endpoint",
  "monitoredResource": {
    "type": "uptime_url",
    "labels": {
      "host": "$(echo $SERVICE_URL | sed 's|https\?://||' | cut -d'/' -f1)",
      "project_id": "$PROJECT_ID"
    }
  },
  "httpCheck": {
    "requestMethod": "GET",
    "path": "/health",
    "port": 443,
    "useSsl": true,
    "validateSsl": true,
    "headers": {
      "User-Agent": "Google-Cloud-Monitoring-Uptime-Check"
    }
  },
  "timeout": "10s",
  "period": "60s",
  "contentMatchers": [
    {
      "content": "\"status\":\"healthy\"",
      "matcher": "CONTAINS_STRING"
    }
  ],
  "selectedRegions": [
    "USA_OREGON",
    "USA_IOWA", 
    "USA_SOUTH_CAROLINA",
    "EUROPE_IRELAND",
    "ASIA_PACIFIC_SINGAPORE"
  ],
  "checkerType": "STATIC_IP_CHECKERS"
}
EOF

# Create uptime check for readiness endpoint
echo "✅ Creating readiness endpoint uptime check..."
cat > ready-uptime-check.json << EOF
{
  "displayName": "Loist MCP Server - Readiness Endpoint",
  "monitoredResource": {
    "type": "uptime_url",
    "labels": {
      "host": "$(echo $SERVICE_URL | sed 's|https\?://||' | cut -d'/' -f1)",
      "project_id": "$PROJECT_ID"
    }
  },
  "httpCheck": {
    "requestMethod": "GET",
    "path": "/ready",
    "port": 443,
    "useSsl": true,
    "validateSsl": true,
    "headers": {
      "User-Agent": "Google-Cloud-Monitoring-Uptime-Check"
    }
  },
  "timeout": "10s",
  "period": "60s",
  "contentMatchers": [
    {
      "content": "\"status\":\"ready\"",
      "matcher": "CONTAINS_STRING"
    }
  ],
  "selectedRegions": [
    "USA_OREGON",
    "USA_IOWA", 
    "USA_SOUTH_CAROLINA",
    "EUROPE_IRELAND",
    "ASIA_PACIFIC_SINGAPORE"
  ],
  "checkerType": "STATIC_IP_CHECKERS"
}
EOF

# Create uptime check for oEmbed endpoint
echo "🔗 Creating oEmbed endpoint uptime check..."
cat > oembed-uptime-check.json << EOF
{
  "displayName": "Loist MCP Server - oEmbed Endpoint",
  "monitoredResource": {
    "type": "uptime_url",
    "labels": {
      "host": "$(echo $SERVICE_URL | sed 's|https\?://||' | cut -d'/' -f1)",
      "project_id": "$PROJECT_ID"
    }
  },
  "httpCheck": {
    "requestMethod": "GET",
    "path": "/.well-known/oembed.json",
    "port": 443,
    "useSsl": true,
    "validateSsl": true,
    "headers": {
      "User-Agent": "Google-Cloud-Monitoring-Uptime-Check"
    }
  },
  "timeout": "10s",
  "period": "300s",
  "contentMatchers": [
    {
      "content": "\"provider_name\":\"Loist Music Library\"",
      "matcher": "CONTAINS_STRING"
    }
  ],
  "selectedRegions": [
    "USA_OREGON",
    "USA_IOWA", 
    "USA_SOUTH_CAROLINA",
    "EUROPE_IRELAND",
    "ASIA_PACIFIC_SINGAPORE"
  ],
  "checkerType": "STATIC_IP_CHECKERS"
}
EOF

# Create the uptime checks
echo "🔍 Creating uptime checks..."
gcloud monitoring uptime create --configuration=health-uptime-check.json
gcloud monitoring uptime create --configuration=ready-uptime-check.json
gcloud monitoring uptime create --configuration=oembed-uptime-check.json

# Create alerting policy for uptime check failures
echo "🚨 Creating uptime check alert policy..."
cat > uptime-alert-policy.json << EOF
{
  "displayName": "Loist MCP Server - Uptime Check Failures",
  "documentation": {
    "content": "Alert when uptime checks fail for 2 minutes",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Uptime check failure",
      "conditionThreshold": {
        "filter": "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 1,
        "duration": "120s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.host"]
          }
        ]
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "1800s"
  },
  "notificationChannels": ["$NOTIFICATION_CHANNEL"]
}
EOF

gcloud alpha monitoring policies create --policy-from-file=uptime-alert-policy.json

# Clean up temporary files
rm -f health-uptime-check.json ready-uptime-check.json oembed-uptime-check.json uptime-alert-policy.json

echo "✅ Uptime checks setup complete!"
echo ""
echo "🔍 Uptime Checks: https://console.cloud.google.com/monitoring/uptime"
echo "🚨 Alert Policies: https://console.cloud.google.com/monitoring/alerting/policies"
echo ""
echo "📊 Test endpoints:"
echo "  - Health: $SERVICE_URL/health"
echo "  - Readiness: $SERVICE_URL/ready"
echo "  - oEmbed Discovery: $SERVICE_URL/.well-known/oembed.json"
echo ""
echo "📝 Next steps:"
echo "  - Verify uptime checks are running"
echo "  - Test alert notifications"
echo "  - Monitor dashboard for metrics"
