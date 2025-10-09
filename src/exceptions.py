"""
Custom exceptions for Music Library MCP Server
Provides a hierarchy of exceptions for different error scenarios
"""
from typing import Optional


class MusicLibraryError(Exception):
    """Base exception for all music library errors"""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AudioProcessingError(MusicLibraryError):
    """
    Raised when audio file processing fails
    
    Examples:
    - Invalid audio format
    - Corrupted file
    - Unsupported codec
    - Metadata extraction failure
    """
    pass


class StorageError(MusicLibraryError):
    """
    Raised when storage operations fail
    
    Examples:
    - GCS upload/download failure
    - Insufficient storage space
    - Network connectivity issues
    - Permission denied
    """
    pass


class ValidationError(MusicLibraryError):
    """
    Raised when input validation fails
    
    Examples:
    - Invalid URL format
    - Missing required fields
    - Schema validation failure
    - Type mismatch
    """
    pass


class ResourceNotFoundError(MusicLibraryError):
    """
    Raised when a requested resource doesn't exist
    
    Examples:
    - Audio track not found by UUID
    - File missing from storage
    - Database record not found
    """
    pass


class TimeoutError(MusicLibraryError):
    """
    Raised when an operation exceeds time limit
    
    Examples:
    - File download timeout
    - Processing timeout (Cloud Run 10min limit)
    - Database query timeout
    - External API timeout
    """
    pass


class AuthenticationError(MusicLibraryError):
    """
    Raised when authentication fails
    
    Examples:
    - Invalid bearer token
    - Missing authorization header
    - Token expired
    """
    pass


class RateLimitError(MusicLibraryError):
    """
    Raised when rate limit is exceeded
    
    Examples:
    - Too many requests from client
    - API quota exceeded
    """
    pass


class ExternalServiceError(MusicLibraryError):
    """
    Raised when external service fails
    
    Examples:
    - PostgreSQL connection failure
    - GCS API error
    - MusicBrainz API unavailable (Phase 2)
    """
    pass


# Error code mapping for MCP protocol
ERROR_CODES = {
    AudioProcessingError: "AUDIO_PROCESSING_FAILED",
    StorageError: "STORAGE_ERROR",
    ValidationError: "VALIDATION_ERROR",
    ResourceNotFoundError: "RESOURCE_NOT_FOUND",
    TimeoutError: "TIMEOUT",
    AuthenticationError: "AUTHENTICATION_FAILED",
    RateLimitError: "RATE_LIMIT_EXCEEDED",
    ExternalServiceError: "EXTERNAL_SERVICE_ERROR",
    MusicLibraryError: "INTERNAL_ERROR",
}


def get_error_code(exception: Exception) -> str:
    """Get the error code for an exception"""
    for exc_class, code in ERROR_CODES.items():
        if isinstance(exception, exc_class):
            return code
    return "UNKNOWN_ERROR"

