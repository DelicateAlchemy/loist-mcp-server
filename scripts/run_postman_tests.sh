#!/bin/bash
# Run Postman collection tests using Newman CLI
# Usage: ./scripts/run_postman_tests.sh [local|staging|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT=${1:-local}

# Validate environment parameter
if [[ ! "$ENVIRONMENT" =~ ^(local|staging|prod)$ ]]; then
    echo -e "${RED}❌ Error: Invalid environment '${ENVIRONMENT}'. Must be one of: local, staging, prod${NC}"
    echo -e "${YELLOW}Usage: $0 [local|staging|prod]${NC}"
    exit 1
fi

# Determine environment file based on environment name
case $ENVIRONMENT in
    local)
        ENV_FILE="postman/a2a-env-local.json"
        ;;
    staging)
        ENV_FILE="postman/a2a-env-staging.json"
        ;;
    prod)
        ENV_FILE="postman/a2a-env-prod.json"
        ;;
    *)
        echo -e "${RED}❌ Error: Unknown environment '${ENVIRONMENT}'${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}🧪 Running A2A Postman Tests (Environment: ${ENVIRONMENT})${NC}"

# Check if we're in the project root
if [ ! -f "postman/a2a-collection.json" ]; then
    echo -e "${RED}❌ Error: postman/a2a-collection.json not found. Please run from project root.${NC}"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: $ENV_FILE not found. Please run from project root.${NC}"
    exit 1
fi

# Check if Newman is installed
if ! command -v newman &> /dev/null; then
    echo -e "${YELLOW}📦 Newman CLI not found. Installing via npm...${NC}"

    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ Error: npm not found. Please install Node.js and npm first.${NC}"
        echo -e "${YELLOW}Visit: https://nodejs.org/${NC}"
        exit 1
    fi

    # Install Newman globally
    npm install -g newman

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: Failed to install Newman CLI${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Newman CLI installed successfully${NC}"
else
    echo -e "${GREEN}✅ Newman CLI is available${NC}"
fi

# Create reports directory
mkdir -p reports/postman

# Set timestamp for report files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_BASE="reports/postman/a2a_${ENVIRONMENT}_${TIMESTAMP}"

echo -e "${BLUE}🚀 Running Postman collection...${NC}"
echo -e "${BLUE}   Collection: postman/a2a-collection.json${NC}"
echo -e "${BLUE}   Environment: ${ENV_FILE}${NC}"
echo -e "${BLUE}   Reports: ${REPORT_BASE}.*${NC}"
echo ""

# Run Newman with comprehensive reporting
newman run postman/a2a-collection.json \
    --environment "$ENV_FILE" \
    --reporters cli,json,html,junit \
    --reporter-json-export "${REPORT_BASE}.json" \
    --reporter-html-export "${REPORT_BASE}.html" \
    --reporter-junit-export "${REPORT_BASE}.xml" \
    --timeout 30000 \
    --delay-request 1000 \
    --verbose \
    --color on

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All Postman tests passed!${NC}"
    echo -e "${GREEN}📊 Reports generated:${NC}"
    echo -e "   JSON: ${REPORT_BASE}.json"
    echo -e "   HTML: ${REPORT_BASE}.html"
    echo -e "   JUnit: ${REPORT_BASE}.xml"
else
    echo -e "${RED}❌ Some Postman tests failed (exit code: $EXIT_CODE)${NC}"
    echo -e "${YELLOW}📊 Check reports for details:${NC}"
    echo -e "   JSON: ${REPORT_BASE}.json"
    echo -e "   HTML: ${REPORT_BASE}.html"
    echo -e "   JUnit: ${REPORT_BASE}.xml"
fi

exit $EXIT_CODE
