#!/bin/bash
# Setup Cloud Monitoring for Cloud Run service
# This script creates dashboards and alerting policies for the loist-mcp-server

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

# Create notification channel for email alerts
echo "📧 Creating notification channel..."
NOTIFICATION_CHANNEL=$(gcloud alpha monitoring channels create \
    --display-name="Loist MCP Server Alerts" \
    --type=email \
    --channel-labels=email_address="$NOTIFICATION_EMAIL" \
    --format="value(name)" 2>/dev/null || echo "")

if [ -z "$NOTIFICATION_CHANNEL" ]; then
    echo "⚠️  Could not create notification channel. Please create one manually in Cloud Console."
    echo "   Go to: https://console.cloud.google.com/monitoring/alerting/notifications"
    NOTIFICATION_CHANNEL="projects/$PROJECT_ID/notificationChannels/placeholder"
fi

echo "📊 Creating Cloud Run monitoring dashboard..."

# Create dashboard JSON
cat > dashboard.json << EOF
{
  "displayName": "Loist MCP Server - Cloud Run Monitoring",
  "mosaicLayout": {
    "columns": 12,
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "Request Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.service_name"]
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
        "width": 6,
        "height": 4,
        "xPos": 6,
        "widget": {
          "title": "Request Latency (p95)",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_DELTA",
                      "crossSeriesReducer": "REDUCE_PERCENTILE_95",
                      "groupByFields": ["resource.labels.service_name"]
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
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Error Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.service_name", "metric.labels.response_code_class"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Errors/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "Container Instances",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Instances",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 8,
        "widget": {
          "title": "CPU Utilization",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "CPU %",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 8,
        "widget": {
          "title": "Memory Utilization",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Memory %",
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
echo "📊 Creating monitoring dashboard..."
gcloud monitoring dashboards create --config-from-file=dashboard.json

# Create alerting policies
echo "🚨 Creating alerting policies..."

# High Error Rate Alert
cat > error-rate-policy.json << EOF
{
  "displayName": "Loist MCP Server - High Error Rate",
  "documentation": {
    "content": "Alert when error rate exceeds 5% for 5 minutes",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Error rate > 5%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.05,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM",
            "groupByFields": ["resource.labels.service_name"]
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

# High Latency Alert
cat > latency-policy.json << EOF
{
  "displayName": "Loist MCP Server - High Latency",
  "documentation": {
    "content": "Alert when p95 latency exceeds 2 seconds for 5 minutes",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "P95 latency > 2s",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 2000,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_DELTA",
            "crossSeriesReducer": "REDUCE_PERCENTILE_95",
            "groupByFields": ["resource.labels.service_name"]
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

# Low Instance Count Alert
cat > instance-policy.json << EOF
{
  "displayName": "Loist MCP Server - Low Instance Count",
  "documentation": {
    "content": "Alert when instance count drops below 1 for 2 minutes",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Instance count < 1",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/container/instance_count\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 1,
        "duration": "120s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.service_name"]
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

# High CPU Usage Alert
cat > cpu-policy.json << EOF
{
  "displayName": "Loist MCP Server - High CPU Usage",
  "documentation": {
    "content": "Alert when CPU usage exceeds 80% for 5 minutes",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "CPU usage > 80%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/container/cpu/utilizations\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.8,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.service_name"]
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

# Create alerting policies
echo "🚨 Creating error rate alert policy..."
gcloud alpha monitoring policies create --policy-from-file=error-rate-policy.json

echo "🚨 Creating latency alert policy..."
gcloud alpha monitoring policies create --policy-from-file=latency-policy.json

echo "🚨 Creating instance count alert policy..."
gcloud alpha monitoring policies create --policy-from-file=instance-policy.json

echo "🚨 Creating CPU usage alert policy..."
gcloud alpha monitoring policies create --policy-from-file=cpu-policy.json

# Clean up temporary files
rm -f dashboard.json error-rate-policy.json latency-policy.json instance-policy.json cpu-policy.json

echo "✅ Cloud Monitoring setup complete!"
echo ""
echo "📊 Dashboard: https://console.cloud.google.com/monitoring/dashboards"
echo "🚨 Alerts: https://console.cloud.google.com/monitoring/alerting/policies"
echo "📧 Notification Channel: $NOTIFICATION_CHANNEL"
echo ""
echo "🔍 To test monitoring:"
echo "  1. Visit the dashboard to see current metrics"
echo "  2. Check alert policies are active"
echo "  3. Test health endpoints:"
echo "     - https://loist-mcp-server-7de5nxpr4q-uc.a.run.app/health"
echo "     - https://loist-mcp-server-7de5nxpr4q-uc.a.run.app/ready"
echo ""
echo "📝 Next steps:"
echo "  - Set up uptime checks for external monitoring"
echo "  - Configure log-based metrics if needed"
echo "  - Test alert notifications"
