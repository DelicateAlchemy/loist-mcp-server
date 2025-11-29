#!/usr/bin/env python3
"""
Smoke test script for search_library tool enhancements.

This script provides basic testing of the new RSQL filters, cursor pagination,
and sparse field selection features. It can be run against a test database
or with mocked components.

Usage:
    python scripts/search_library_smoke_test.py

Environment:
    Requires database connection and test data.
    Set up environment variables for database connection.

Cleanup:
    This script only performs read operations and does not modify data.
    No cleanup is required.
"""

import asyncio
import logging
import sys
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, '/Users/Gareth/loist-mcp-server/src')

from tools.query_tools import search_library

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_basic_search():
    """Test basic search functionality"""
    logger.info("Testing basic search...")
    try:
        result = await search_library({
            "query": "test",
            "limit": 5
        })
        logger.info(f"Basic search successful: {len(result['results'])} results")
        return True
    except Exception as e:
        logger.error(f"Basic search failed: {e}")
        return False


async def test_rsql_filters():
    """Test RSQL filter parsing"""
    logger.info("Testing RSQL filters...")
    try:
        # Test with year range filter
        result = await search_library({
            "query": "music",
            "filter": "year>=1960,year<=1980",
            "limit": 5
        })
        logger.info(f"RSQL filter search successful: {len(result['results'])} results")
        return True
    except Exception as e:
        logger.error(f"RSQL filter search failed: {e}")
        return False


async def test_sparse_fields():
    """Test sparse field selection"""
    logger.info("Testing sparse field selection...")
    try:
        result = await search_library({
            "query": "test",
            "fields": "id,title,score",
            "limit": 3
        })
        logger.info(f"Sparse fields search successful: {len(result['results'])} results")
        return True
    except Exception as e:
        logger.error(f"Sparse fields search failed: {e}")
        return False


async def test_cursor_pagination():
    """Test cursor-based pagination"""
    logger.info("Testing cursor pagination...")
    try:
        # First page
        result1 = await search_library({
            "query": "test",
            "limit": 2
        })

        if result1['nextCursor'] and result1['hasMore']:
            # Second page using cursor
            result2 = await search_library({
                "query": "test",
                "cursor": result1['nextCursor'],
                "limit": 2
            })
            logger.info(f"Cursor pagination successful: Page 1 ({len(result1['results'])} results), Page 2 ({len(result2['results'])} results)")
            return True
        else:
            logger.info("Cursor pagination test skipped: No cursor returned (possibly no test data)")
            return True
    except Exception as e:
        logger.error(f"Cursor pagination failed: {e}")
        return False


async def test_error_handling():
    """Test error handling with invalid inputs"""
    logger.info("Testing error handling...")
    try:
        # Test invalid filter syntax
        result = await search_library({
            "query": "test",
            "filter": "invalid=filter=syntax",
            "limit": 5
        })

        if result.get('success') == False:
            logger.info("Error handling successful: Invalid filter rejected")
            return True
        else:
            logger.error("Error handling failed: Invalid filter was accepted")
            return False
    except Exception as e:
        logger.error(f"Error handling test failed: {e}")
        return False


async def run_smoke_tests():
    """Run all smoke tests"""
    logger.info("Starting search_library smoke tests...")

    tests = [
        ("Basic Search", test_basic_search),
        ("RSQL Filters", test_rsql_filters),
        ("Sparse Fields", test_sparse_fields),
        ("Cursor Pagination", test_cursor_pagination),
        ("Error Handling", test_error_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        if await test_func():
            passed += 1
            logger.info(f"✅ {test_name} PASSED")
        else:
            logger.error(f"❌ {test_name} FAILED")

    logger.info(f"\n--- Test Results ---")
    logger.info(f"Passed: {passed}/{total}")

    if passed == total:
        logger.info("🎉 All smoke tests passed!")
        return True
    else:
        logger.error("❌ Some smoke tests failed")
        return False


def main():
    """Main entry point"""
    try:
        success = asyncio.run(run_smoke_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Smoke tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Smoke tests failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
