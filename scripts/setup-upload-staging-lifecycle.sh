#!/usr/bin/env bash
# Configure a lifecycle rule so abandoned browser uploads (LOI-45) are
# auto-deleted from the staging prefix after 1 day.
#
# The upload flow stages files at uploads/{upload_id}/{filename}; successful
# processing deletes the staging object itself, so anything older than a day
# under uploads/ is an abandoned or failed upload safe to remove.
#
# Usage: ./scripts/setup-upload-staging-lifecycle.sh <bucket-name>
# Requires: gcloud CLI authenticated with storage.buckets.update permission.

set -euo pipefail

BUCKET="${1:?Usage: $0 <bucket-name>}"

TMP_RULE="$(mktemp)"
trap 'rm -f "$TMP_RULE"' EXIT

cat > "$TMP_RULE" <<'JSON'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 1,
        "matchesPrefix": ["uploads/"]
      }
    }
  ]
}
JSON

echo "Applying 1-day delete lifecycle rule for uploads/ prefix on gs://${BUCKET}"
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file="$TMP_RULE"
echo "Done. Current lifecycle config:"
gcloud storage buckets describe "gs://${BUCKET}" --format="json(lifecycle_config)"
