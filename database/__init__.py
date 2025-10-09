"""
Database module for Loist Music Library MCP Server.

Provides connection pooling, query utilities, and database management
for PostgreSQL interactions.
"""

from .pool import (
    DatabasePool,
    get_connection_pool,
    get_connection,
    close_pool,
)

__all__ = [
    "DatabasePool",
    "get_connection_pool",
    "get_connection",
    "close_pool",
]

