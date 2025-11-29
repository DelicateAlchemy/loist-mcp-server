"""
Unified Exception Handling Framework for Music Library MCP Server

This module provides a comprehensive exception handling system that:
- Consolidates multiple error handling approaches into a single framework
- Provides consistent error responses across all endpoints
- Enables dependency injection for testing
- Supports recovery strategies and retry logic
- Integrates cleanly with FastMCP without workarounds
"""

# Temporarily disable new framework imports to resolve circular dependencies
# TODO: Re-enable after fixing circular import issues

# Import new unified framework
from .handler import ExceptionHandler, ExceptionConfig
from .context import ExceptionContext
from .recovery import RecoveryStrategy, DatabaseRecoveryStrategy
from .fastmcp_integration import FastMCPExceptionMiddleware

__all__ = [
    # New unified framework
    'ExceptionHandler',
    'ExceptionConfig',
    'ExceptionContext',
    'RecoveryStrategy',
    'DatabaseRecoveryStrategy',
    'FastMCPExceptionMiddleware',
]
