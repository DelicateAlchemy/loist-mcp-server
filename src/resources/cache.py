"""
Cache module for MCP resources.

This module re-exports the SignedURLCache and get_cache utilities
from the streaming_service module for backwards compatibility.
"""

from src.services.streaming_service import _SignedURLCache as SignedURLCache, get_cache

__all__ = [
    "SignedURLCache",
    "get_cache",
]

