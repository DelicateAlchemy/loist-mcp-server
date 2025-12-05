#!/bin/bash
# Run tests with proper environment setup
# Usage: ./scripts/run-tests.sh [pytest arguments]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Setting up test environment...${NC}"

# Check if we're in the project root
if [ ! -f "pytest.ini" ]; then
    echo -e "${RED}❌ Error: pytest.ini not found. Please run from project root.${NC}"
    exit 1
fi

# Check if database is running
if ! docker-compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo -e "${YELLOW}📦 Starting PostgreSQL container...${NC}"
    docker-compose up -d postgres
    echo -e "${BLUE}⏳ Waiting for database to be ready...${NC}"
    sleep 3
else
    echo -e "${GREEN}✅ PostgreSQL container is running${NC}"
fi

# Check if dev dependencies are installed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing dev dependencies...${NC}"
    pip install -r requirements-dev.txt
else
    echo -e "${GREEN}✅ Dev dependencies installed${NC}"
fi

# Set environment variables (use defaults if not set)
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-loist_mvp}
export DB_USER=${DB_USER:-loist_user}
export DB_PASSWORD=${DB_PASSWORD:-dev_password}

# Set DATABASE_URL if not set
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
fi

# Set other test environment variables
export SERVER_TRANSPORT=${SERVER_TRANSPORT:-stdio}
export AUTH_ENABLED=${AUTH_ENABLED:-false}
export LOG_LEVEL=${LOG_LEVEL:-WARNING}

echo -e "${BLUE}🚀 Running tests...${NC}"
echo -e "${BLUE}   Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}${NC}"
echo ""

# Run pytest with provided arguments, or default to all tests
if [ $# -eq 0 ]; then
    pytest tests/ -v
else
    pytest "$@"
fi

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}❌ Some tests failed (exit code: $EXIT_CODE)${NC}"
fi

exit $EXIT_CODE

