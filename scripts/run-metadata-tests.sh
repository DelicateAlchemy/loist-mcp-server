#!/bin/bash

# Metadata Generation Test Runner
# Usage: ./scripts/run-metadata-tests.sh [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PYTHON_VERSION="3.12"
TEST_TYPE="all"
VERBOSE=false
COVERAGE=true
HTML_REPORT=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --python-version)
      PYTHON_VERSION="$2"
      shift 2
      ;;
    --test-type)
      TEST_TYPE="$2"
      shift 2
      ;;
    --verbose|-v)
      VERBOSE=true
      shift
      ;;
    --no-coverage)
      COVERAGE=false
      shift
      ;;
    --no-html)
      HTML_REPORT=false
      shift
      ;;
    --help|-h)
      echo "Metadata Generation Test Runner"
      echo ""
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --python-version VERSION  Python version to use (default: 3.12)"
      echo "  --test-type TYPE          Type of tests to run: all, unit, integration (default: all)"
      echo "  --verbose, -v             Verbose output"
      echo "  --no-coverage             Disable coverage reporting"
      echo "  --no-html                 Disable HTML report generation"
      echo "  --help, -h                Show this help message"
      echo ""
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}🧪 Metadata Generation Test Runner${NC}"
echo "=================================="
echo "Python Version: $PYTHON_VERSION"
echo "Test Type: $TEST_TYPE"
echo "Verbose: $VERBOSE"
echo "Coverage: $COVERAGE"
echo "HTML Report: $HTML_REPORT"
echo ""

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ Virtual environment detected: $VIRTUAL_ENV${NC}"
else
    echo -e "${YELLOW}⚠️  No virtual environment detected. Consider using a venv for isolation.${NC}"
fi

# Check Python version
echo -e "${BLUE}🐍 Checking Python version...${NC}"
python_version=$(python --version 2>&1 | cut -d' ' -f2)
echo "Current Python version: $python_version"

# Install dependencies if needed
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install --upgrade pip
pip install pytest pytest-asyncio beautifulsoup4 pytest-html pytest-cov jinja2 starlette

# Create reports directory
mkdir -p reports

# Build pytest command
PYTEST_CMD="python -m pytest tests/test_metadata_generation.py"

# Add verbosity
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
else
    PYTEST_CMD="$PYTEST_CMD -q"
fi

# Add coverage
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=xml:reports/coverage.xml"
fi

# Add HTML report
if [ "$HTML_REPORT" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --html=reports/pytest_report.html --self-contained-html"
fi

# Add JUnit XML for CI
PYTEST_CMD="$PYTEST_CMD --junitxml=reports/junit.xml"

# Add test type filtering
case $TEST_TYPE in
    "unit")
        PYTEST_CMD="$PYTEST_CMD -k 'not integration'"
        ;;
    "integration")
        PYTEST_CMD="$PYTEST_CMD -k 'integration'"
        ;;
    "all")
        # Run all tests
        ;;
    *)
        echo -e "${RED}❌ Invalid test type: $TEST_TYPE${NC}"
        echo "Valid options: all, unit, integration"
        exit 1
        ;;
esac

echo -e "${BLUE}🚀 Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

# Run the tests
if eval $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    
    if [ "$HTML_REPORT" = true ]; then
        echo -e "${GREEN}📊 HTML report generated: reports/pytest_report.html${NC}"
    fi
    
    if [ "$COVERAGE" = true ]; then
        echo -e "${GREEN}📈 Coverage report generated: reports/coverage.xml${NC}"
    fi
    
    echo -e "${GREEN}📁 JUnit XML report: reports/junit.xml${NC}"
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed!${NC}"
    echo -e "${YELLOW}Check the output above for details.${NC}"
    exit 1
fi


