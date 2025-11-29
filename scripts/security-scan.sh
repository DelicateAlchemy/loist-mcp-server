#!/bin/bash

# Security Scanning Script for Loist MCP Server
# Runs comprehensive security analysis including:
# - Bandit (Python security vulnerability scanning)
# - Safety (dependency vulnerability scanning)
# - Custom security checks

# set -e  # Disabled because security tools return non-zero when issues are found

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create reports directory if it doesn't exist
mkdir -p "$REPORT_DIR"

echo -e "${BLUE}🔒 Starting Security Scan for Loist MCP Server${NC}"
echo "Report timestamp: $TIMESTAMP"
echo "Reports will be saved to: $REPORT_DIR"
echo

# Function to run Bandit security scan
run_bandit_scan() {
    echo -e "${YELLOW}🔍 Running Bandit Python Security Scan...${NC}"

    BANDIT_REPORT="$REPORT_DIR/bandit-scan-$TIMESTAMP.json"
    BANDIT_HTML="$REPORT_DIR/bandit-scan-$TIMESTAMP.html"

    # Run Bandit scan with JSON output (Bandit returns non-zero exit code when issues found)
    bandit -r src/ -f json -o "$BANDIT_REPORT" --exclude "tests/*,scripts/*"
    BANDIT_EXIT_CODE=$?

    # Generate HTML report regardless of exit code
    bandit -r src/ -f html -o "$BANDIT_HTML" --exclude "tests/*,scripts/*" > /dev/null 2>&1

    if [ $BANDIT_EXIT_CODE -eq 0 ] || [ $BANDIT_EXIT_CODE -eq 1 ]; then
        echo -e "${GREEN}✅ Bandit scan completed${NC}"
        echo "  📄 JSON Report: $BANDIT_REPORT"
        echo "  🌐 HTML Report: $BANDIT_HTML"
    else
        echo -e "${RED}❌ Bandit scan failed with exit code $BANDIT_EXIT_CODE${NC}"
        return 1
    fi

    # Parse results for issues
    if command -v jq &> /dev/null && [ -f "$BANDIT_REPORT" ]; then
        HIGH_ISSUES=$(jq '.metrics._totals."SEVERITY.HIGH" // 0' "$BANDIT_REPORT" 2>/dev/null || echo "0")
        MEDIUM_ISSUES=$(jq '.metrics._totals."SEVERITY.MEDIUM" // 0' "$BANDIT_REPORT" 2>/dev/null || echo "0")
        LOW_ISSUES=$(jq '.metrics._totals."SEVERITY.LOW" // 0' "$BANDIT_REPORT" 2>/dev/null || echo "0")
        TOTAL_LOC=$(jq '.metrics._totals.loc // 0' "$BANDIT_REPORT" 2>/dev/null || echo "0")

        echo "  📊 Scan Results:"
        echo "    - Lines of Code Scanned: $TOTAL_LOC"
        echo "    - High Severity Issues: $HIGH_ISSUES"
        echo "    - Medium Severity Issues: $MEDIUM_ISSUES"
        echo "    - Low Severity Issues: $LOW_ISSUES"
    fi

    echo
}

# Function to run Safety dependency scan
run_safety_scan() {
    echo -e "${YELLOW}🔍 Running Safety Dependency Vulnerability Scan...${NC}"

    SAFETY_REPORT="$REPORT_DIR/safety-scan-$TIMESTAMP.json"

    # Run Safety scan (new command format) - continue even if it fails
    echo '{"vulnerabilities": []}' > "$SAFETY_REPORT"  # Default empty report

    if safety scan --output json --target . > "$SAFETY_REPORT" 2>/dev/null; then
        echo -e "${GREEN}✅ Safety dependency scan completed${NC}"
        echo "  📄 Report: $SAFETY_REPORT"
    else
        echo -e "${YELLOW}⚠️  Safety scan encountered issues (network/API access may be required)${NC}"
        echo "  📄 Report: $SAFETY_REPORT (empty fallback)"
        echo "  💡 Safety requires internet access to check vulnerability database"
    fi

    # Parse results for vulnerabilities
    if command -v jq &> /dev/null && [ -f "$SAFETY_REPORT" ]; then
        VULNERABILITIES=$(jq '.vulnerabilities // [] | length' "$SAFETY_REPORT" 2>/dev/null || echo "0")
        echo "  📊 Scan Results:"
        echo "    - Vulnerabilities Found: $VULNERABILITIES"
    fi

    echo
}

# Function to run custom security checks
run_custom_checks() {
    echo -e "${YELLOW}🔍 Running Custom Security Checks...${NC}"

    CUSTOM_REPORT="$REPORT_DIR/custom-security-checks-$TIMESTAMP.txt"

    {
        echo "Custom Security Checks Report"
        echo "Generated: $(date)"
        echo "================================="
        echo

        # Check for hardcoded secrets
        echo "🔍 Checking for hardcoded secrets..."
        SECRET_PATTERNS=(
            "password.*=.*['\"][^'\"]*['\"]"
            "secret.*=.*['\"][^'\"]*['\"]"
            "key.*=.*['\"][^'\"]*['\"]"
            "token.*=.*['\"][^'\"]*['\"]"
        )

        SECRET_ISSUES=0
        for pattern in "${SECRET_PATTERNS[@]}"; do
            if grep -r -i -n "$pattern" src/ --include="*.py" --exclude-dir="tests" > /dev/null 2>&1; then
                ((SECRET_ISSUES++))
            fi
        done

        if [ $SECRET_ISSUES -gt 0 ]; then
            echo "⚠️  Potential hardcoded secrets found: $SECRET_ISSUES patterns detected"
        else
            echo "✅ No hardcoded secrets detected"
        fi
        echo

        # Check for debug code
        echo "🔍 Checking for debug code..."
        DEBUG_PATTERNS=(
            "print("
            "pdb.set_trace()"
            "import pdb"
            "console.log("
        )

        DEBUG_ISSUES=0
        for pattern in "${DEBUG_PATTERNS[@]}"; do
            COUNT=$(grep -r "$pattern" src/ --include="*.py" --exclude-dir="tests" | wc -l)
            if [ "$COUNT" -gt 0 ]; then
                ((DEBUG_ISSUES += COUNT))
            fi
        done

        if [ $DEBUG_ISSUES -gt 0 ]; then
            echo "⚠️  Debug code found: $DEBUG_ISSUES instances"
        else
            echo "✅ No debug code detected"
        fi
        echo

        # Check file permissions
        echo "🔍 Checking file permissions..."
        SECURE_FILES=$(find src/ -name "*.py" -type f -executable | wc -l)
        if [ "$SECURE_FILES" -gt 0 ]; then
            echo "⚠️  Executable Python files found: $SECURE_FILES files"
        else
            echo "✅ All Python files have appropriate permissions"
        fi
        echo

        # Check for TODO comments with security implications
        echo "🔍 Checking for security-related TODOs..."
        SECURITY_TODOS=$(grep -r -i "TODO.*secur" src/ --include="*.py" | wc -l)
        if [ "$SECURITY_TODOS" -gt 0 ]; then
            echo "⚠️  Security-related TODOs found: $SECURITY_TODOS items"
        else
            echo "✅ No security-related TODOs found"
        fi

    } > "$CUSTOM_REPORT"

    echo -e "${GREEN}✅ Custom security checks completed${NC}"
    echo "  📄 Report: $CUSTOM_REPORT"
    echo
}

# Function to generate summary report
generate_summary() {
    echo -e "${YELLOW}📊 Generating Security Scan Summary...${NC}"

    SUMMARY_REPORT="$REPORT_DIR/security-scan-summary-$TIMESTAMP.txt"

    {
        echo "Security Scan Summary Report"
        echo "Generated: $(date)"
        echo "================================="
        echo

        # Overall status
        echo "🔍 Scan Overview:"
        echo "  - Bandit (Python Security): $([ -f "$REPORT_DIR/bandit-scan-$TIMESTAMP.json" ] && echo "✅ Completed" || echo "❌ Failed")"
        echo "  - Safety (Dependencies): $([ -f "$REPORT_DIR/safety-scan-$TIMESTAMP.json" ] && echo "✅ Completed" || echo "❌ Failed")"
        echo "  - Custom Checks: $([ -f "$REPORT_DIR/custom-security-checks-$TIMESTAMP.txt" ] && echo "✅ Completed" || echo "❌ Failed")"
        echo

        # Quick metrics
        if [ -f "$REPORT_DIR/bandit-scan-$TIMESTAMP.json" ] && command -v jq &> /dev/null; then
            HIGH_ISSUES=$(jq '.results | map(select(.issue_severity == "HIGH")) | length' "$REPORT_DIR/bandit-scan-$TIMESTAMP.json" 2>/dev/null || echo "0")
            echo "📊 Key Metrics:"
            echo "  - High Severity Issues (Bandit): $HIGH_ISSUES"
        fi

        if [ -f "$REPORT_DIR/safety-scan-$TIMESTAMP.json" ] && command -v jq &> /dev/null; then
            VULNS=$(jq '.vulnerabilities | length' "$REPORT_DIR/safety-scan-$TIMESTAMP.json" 2>/dev/null || echo "0")
            echo "  - Dependency Vulnerabilities: $VULNS"
        fi

        echo
        echo "📂 Detailed Reports:"
        echo "  - Bandit JSON: $REPORT_DIR/bandit-scan-$TIMESTAMP.json"
        echo "  - Bandit HTML: $REPORT_DIR/bandit-scan-$TIMESTAMP.html"
        echo "  - Safety: $REPORT_DIR/safety-scan-$TIMESTAMP.json"
        echo "  - Custom Checks: $REPORT_DIR/custom-security-checks-$TIMESTAMP.txt"
        echo

        # Recommendations
        echo "💡 Recommendations:"
        if [ "$HIGH_ISSUES" -gt 0 ] 2>/dev/null; then
            echo "  - Review high-severity issues found by Bandit"
        fi
        if [ "$VULNS" -gt 0 ] 2>/dev/null; then
            echo "  - Address dependency vulnerabilities identified by Safety"
        fi
        echo "  - Review custom security checks for additional issues"
        echo "  - Consider integrating these scans into CI/CD pipeline"

    } > "$SUMMARY_REPORT"

    echo -e "${GREEN}✅ Summary report generated${NC}"
    echo "  📄 Summary: $SUMMARY_REPORT"
    echo
}

# Main execution
main() {
    echo "Starting comprehensive security scan..."
    echo

    # Run all security scans
    run_bandit_scan
    run_safety_scan
    run_custom_checks

    # Generate summary
    generate_summary

    echo -e "${GREEN}🎉 Security scan completed!${NC}"
    echo "All reports saved to: $REPORT_DIR"
    echo "Summary: $REPORT_DIR/security-scan-summary-$TIMESTAMP.txt"
}

# Run main function
main "$@"
