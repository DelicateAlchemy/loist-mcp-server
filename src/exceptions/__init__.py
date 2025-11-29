"""
Exception Classes for Music Library MCP Server

This module provides the core exception classes used throughout the application.
These are imported from the main exceptions.py file to avoid circular dependencies.
"""

# Import exception classes from the parent directory's exceptions.py file
# We need to be careful to avoid circular imports by importing the module by file path

import importlib.util
import os

# Load the exceptions.py file directly
_exceptions_file = os.path.join(os.path.dirname(__file__), '..', 'exceptions.py')
spec = importlib.util.spec_from_file_location("exceptions_module", _exceptions_file)
_exceptions_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_exceptions_module)

# Import the specific classes and functions
MusicLibraryError = _exceptions_module.MusicLibraryError
AudioProcessingError = _exceptions_module.AudioProcessingError
StorageError = _exceptions_module.StorageError
ValidationError = _exceptions_module.ValidationError
ResourceNotFoundError = _exceptions_module.ResourceNotFoundError
TimeoutError = _exceptions_module.TimeoutError
AuthenticationError = _exceptions_module.AuthenticationError
RateLimitError = _exceptions_module.RateLimitError
ExternalServiceError = _exceptions_module.ExternalServiceError
DatabaseOperationError = _exceptions_module.DatabaseOperationError
ERROR_CODES = _exceptions_module.ERROR_CODES
get_error_code = _exceptions_module.get_error_code

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
