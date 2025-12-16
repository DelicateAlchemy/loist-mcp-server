"""
Exception Classes for Music Library MCP Server

This module provides the core exception classes used throughout the application.
These are imported from the exceptions_core.py module (renamed from exceptions.py
to avoid naming conflict with this package directory).
"""

# Import exception classes from the exceptions_core module
# The module was renamed from exceptions.py to exceptions_core.py to avoid
# the naming conflict with this exceptions/ package directory
from src.exceptions_core import (
    MusicLibraryError,
    AudioProcessingError,
    StorageError,
    ValidationError,
    ResourceNotFoundError,
    TimeoutError,
    AuthenticationError,
    RateLimitError,
    ExternalServiceError,
    DatabaseOperationError,
    ERROR_CODES,
    get_error_code,
)

# Re-export for backward compatibility and convenience
__all__ = [
    'MusicLibraryError',
    'AudioProcessingError',
    'StorageError',
    'ValidationError',
    'ResourceNotFoundError',
    'TimeoutError',
    'AuthenticationError',
    'RateLimitError',
    'ExternalServiceError',
    'DatabaseOperationError',
    'ERROR_CODES',
    'get_error_code',
]
