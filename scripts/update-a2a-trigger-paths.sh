#!/bin/bash
# Remove path filters from A2A Cloud Build triggers
# A2A triggers should mirror MCP triggers and fire on ANY push to their branches,
# not just when A2A code changes. This supports branch merges (dev → main).

set -e

PROJECT_ID="loist-music-library"
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "🔧 Removing path filters from A2A triggers..."
echo "   (A2A triggers should fire on ANY push, mirroring MCP triggers)"
echo ""

# Update staging trigger
if gcloud beta builds triggers export a2a-staging-deployment \
  --project="$PROJECT_ID" \
  --destination="$TEMP_DIR/trigger-staging.yaml" 2>/dev/null; then
  
  # Remove includedFiles if present
  python3 << EOF
import yaml
import sys

with open("$TEMP_DIR/trigger-staging.yaml", "r") as f:
    trigger = yaml.safe_load(f)

# Remove includedFiles if present
trigger.pop('includedFiles', None)

# Remove fields that shouldn't be in import
for field in ['createTime', 'id', 'resourceName']:
    trigger.pop(field, None)

with open("$TEMP_DIR/trigger-staging.yaml", "w") as f:
    yaml.dump(trigger, f, default_flow_style=False, sort_keys=False)
EOF

  # Import updated trigger
  gcloud beta builds triggers import \
    --project="$PROJECT_ID" \
    --source="$TEMP_DIR/trigger-staging.yaml"
  
  echo "✅ A2A staging trigger updated (path filters removed)"
else
  echo "⚠️  A2A staging trigger not found, skipping"
fi

echo ""

# Update production trigger
if gcloud beta builds triggers export a2a-prod-deployment \
  --project="$PROJECT_ID" \
  --destination="$TEMP_DIR/trigger-prod.yaml" 2>/dev/null; then
  
  # Remove includedFiles if present
  python3 << EOF
import yaml
import sys

with open("$TEMP_DIR/trigger-prod.yaml", "r") as f:
    trigger = yaml.safe_load(f)

# Remove includedFiles if present
trigger.pop('includedFiles', None)

# Remove fields that shouldn't be in import
for field in ['createTime', 'id', 'resourceName']:
    trigger.pop(field, None)

with open("$TEMP_DIR/trigger-prod.yaml", "w") as f:
    yaml.dump(trigger, f, default_flow_style=False, sort_keys=False)
EOF

  # Import updated trigger
  gcloud beta builds triggers import \
    --project="$PROJECT_ID" \
    --source="$TEMP_DIR/trigger-prod.yaml"
  
  echo "✅ A2A production trigger updated (path filters removed)"
else
  echo "⚠️  A2A production trigger not found, skipping"
fi

echo ""
echo "📋 Verifying trigger configurations..."
echo ""
echo "A2A Staging Trigger:"
gcloud builds triggers describe a2a-staging-deployment \
  --project="$PROJECT_ID" \
  --format="yaml(github.push.branch,includedFiles)" 2>/dev/null || echo "  Trigger not found"

echo ""
echo "A2A Production Trigger:"
gcloud builds triggers describe a2a-prod-deployment \
  --project="$PROJECT_ID" \
  --format="yaml(github.push.branch,includedFiles)"

echo ""
echo "✅ Trigger path filters removed!"
echo ""
echo "Triggers now fire on ANY push to their branches:"
echo "  - a2a-staging-deployment: ANY push to dev branch"
echo "  - a2a-prod-deployment: ANY push to main branch"
echo ""
echo "This mirrors the MCP triggers and supports branch merges (dev → main)."
