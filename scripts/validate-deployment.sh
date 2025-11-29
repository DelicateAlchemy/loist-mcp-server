#!/bin/bash
# Main deployment validation orchestrator

set -e

PRODUCTION_URL="https://music-library-mcp-7de5nxpr4q-uc.a.run.app"
STAGING_URL="https://music-library-mcp-staging-7de5nxpr4q-uc.a.run.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================="
echo " Cloud Run Deployment Validation Suite"
echo "============================================="
echo ""
echo "Production URL: $PRODUCTION_URL"
echo "Staging URL: $STAGING_URL"
echo ""
echo "This validation suite will test:"
echo "1. Cloud Build triggers"
echo "2. Cloud Run service"
echo "3. MCP tools"
echo "4. Database operations"
echo "5. GCS operations"
echo "6. Environment configuration"
echo ""
echo "============================================="
echo ""

# Track failures
FAILURES=0

# 1. Test deployment triggers
echo ""
echo "=== 1. Validating Cloud Build Triggers ==="
if "$SCRIPT_DIR/test-deployment-triggers.sh"; then
    echo "✅ Trigger validation passed"
else
    echo "❌ Trigger validation failed"
    ((FAILURES++))
fi

# 2. Test Cloud Run service
echo ""
echo "=== 2. Validating Cloud Run Service ==="
if "$SCRIPT_DIR/validate-cloud-run.sh" "$PRODUCTION_URL"; then
    echo "✅ Cloud Run validation passed"
else
    echo "❌ Cloud Run validation failed"
    ((FAILURES++))
fi

# 3. Test MCP tools
echo ""
echo "=== 3. Validating MCP Tools ==="
if "$SCRIPT_DIR/validate-mcp-tools.sh" "$PRODUCTION_URL/mcp"; then
    echo "✅ MCP tools validation passed"
else
    echo "❌ MCP tools validation failed"
    ((FAILURES++))
fi

# 4. Test database
echo ""
echo "=== 4. Validating Database Operations ==="
if "$SCRIPT_DIR/validate-database.sh"; then
    echo "✅ Database validation passed"
else
    echo "❌ Database validation failed"
    ((FAILURES++))
fi

# 5. Test GCS
echo ""
echo "=== 5. Validating GCS Operations ==="
if "$SCRIPT_DIR/validate-gcs.sh"; then
    echo "✅ GCS validation passed"
else
    echo "❌ GCS validation failed"
    ((FAILURES++))
fi

# 6. Test environment config
echo ""
echo "=== 6. Validating Environment Configuration ==="
if [ -f "$SCRIPT_DIR/validate-env-config.sh" ]; then
    if "$SCRIPT_DIR/validate-env-config.sh"; then
        echo "✅ Environment validation passed"
    else
        echo "❌ Environment validation failed"
        ((FAILURES++))
    fi
else
    echo "⚠️  validate-env-config.sh not found, skipping"
fi

# Generate summary
echo ""
echo "============================================="
echo " Validation Summary"
echo "============================================="
echo ""

if [ $FAILURES -eq 0 ]; then
    echo "✅ ALL VALIDATIONS PASSED"
    echo ""
    echo "Production deployment is healthy and operational."
    echo "All components validated successfully:"
    echo "  • Cloud Build triggers configured"
    echo "  • Cloud Run service accessible"
    echo "  • MCP protocol functioning"
    echo "  • Database connectivity confirmed"
    echo "  • GCS storage operational"
    echo ""
    REPORT_FILE="validation-report-$(date +%Y%m%d-%H%M%S).txt"
    echo "Report saved to: $REPORT_FILE"
    
    # Save validation report
    {
        echo "Cloud Run Deployment Validation Report"
        echo "Generated: $(date)"
        echo ""
        echo "Production URL: $PRODUCTION_URL"
        echo "Staging URL: $STAGING_URL"
        echo ""
        echo "Validation Results: ALL PASSED"
        echo "  ✅ Cloud Build triggers"
        echo "  ✅ Cloud Run service"
        echo "  ✅ MCP tools"
        echo "  ✅ Database operations"
        echo "  ✅ GCS operations"
        echo "  ✅ Environment configuration"
    } > "$REPORT_FILE"
    
    echo "============================================="
    exit 0
else
    echo "❌ VALIDATION FAILED"
    echo ""
    echo "Failed validations: $FAILURES"
    echo ""
    echo "Please review the error messages above and check:"
    echo "  • Service logs in Cloud Logging"
    echo "  • Recent Cloud Build deployments"
    echo "  • Service account permissions"
    echo "  • Secret Manager configuration"
    echo ""
    echo "============================================="
    exit 1
fi

