"""
HTTP API parameter validation schemas.

This module provides Pydantic schemas for validating HTTP REST API endpoints,
ensuring consistent parameter validation and error handling across all endpoints.

These schemas align with MCP tool validation patterns but are tailored for HTTP
REST API query parameters and path parameters.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, ValidationError as PydanticValidationError
from src.exceptions import ValidationError


# ============================================================================
# Error Codes for HTTP API
# ============================================================================

class ErrorCode(str):
    """Error codes for HTTP API validation errors"""
    INVALID_QUERY = "INVALID_QUERY"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONVERSION_TIMEOUT = "CONVERSION_TIMEOUT"
    CONVERSION_FAILED = "CONVERSION_FAILED"
    TRACK_NOT_FOUND = "TRACK_NOT_FOUND"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    SEARCH_FAILED = "SEARCH_FAILED"


# ============================================================================
# Search Endpoint Schemas
# ============================================================================

class SearchQueryParams(BaseModel):
    """
    Query parameters for the search endpoint (/api/search).

    Provides strict validation for search parameters, rejecting invalid values
    instead of silently correcting them (aligns with MCP tool patterns).

    Example:
        {
            "q": "rock music",
            "limit": 20,
            "offset": 0,
            "genre": "Rock,Classic Rock"
        }
    """
    q: str = Field(
        ...,
        description="Search query string",
        min_length=1,
        max_length=500
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
    )
    genre: Optional[str] = Field(
        default=None,
        description="Comma-separated list of genres to filter by",
        max_length=500
    )

    @field_validator('q')
    @classmethod
    def validate_query_not_empty(cls, v):
        """Ensure search query is not just whitespace"""
        if not v.strip():
            raise ValueError("Search query cannot be empty or contain only whitespace")
        return v.strip()

    @field_validator('genre')
    @classmethod
    def validate_genre_format(cls, v):
        """
        Validate genre parameter format.

        Allows comma-separated values, strips whitespace, rejects empty strings.
        """
        if v is None:
            return v

        # Split by comma and clean up
        genres = [g.strip() for g in v.split(',') if g.strip()]

        # Reject if any genre is empty after stripping
        if not genres:
            raise ValueError("Genre parameter cannot be empty when provided")

        # Rejoin cleaned genres
        return ','.join(genres)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "q": "rock music",
                    "limit": 20,
                    "offset": 0,
                    "genre": "Rock,Classic Rock"
                },
                {
                    "q": "jazz",
                    "limit": 50,
                    "offset": 10
                },
                {
                    "q": "classical",
                    "limit": 10,
                    "offset": 0,
                    "genre": "Classical"
                }
            ]
        }
    }


# ============================================================================
# UUID Path Parameter Validation
# ============================================================================

class UUIDPathParams(BaseModel):
    """
    Path parameters containing UUID values.

    Used for endpoints like /api/tracks/{audioId} to ensure
    audioId is a valid UUID format.
    """
    audio_id: str = Field(
        ...,
        description="UUID of the audio track"
        # UUID format validation handled by custom validator
    )

    @field_validator('audio_id')
    @classmethod
    def validate_and_normalize_uuid(cls, v):
        """Validate UUID format and normalize to lowercase"""
        import uuid
        try:
            # Use Python's uuid.UUID for robust validation
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()  # Normalize to lowercase hyphenated format
        except ValueError:
            raise ValueError(
                f"audio_id must be a valid UUID format "
                f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {v[:50]}"
            )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audio_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }


# ============================================================================
# Download Endpoint Schemas
# ============================================================================

class DownloadQueryParams(BaseModel):
    """
    Query parameters for the download endpoint (/api/tracks/{audioId}/download).

    Validates format and preset parameters for audio conversion downloads.
    """
    format: str = Field(
        ...,
        description="Target audio format (mp3, wav, flac, aac, ogg)"
    )
    preset: Optional[str] = Field(
        default=None,
        description="Quality preset for the target format"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "mp3",
                    "preset": "high"
                },
                {
                    "format": "flac",
                    "preset": "lossless"
                }
            ]
        }
    }


# ============================================================================
# Helper Functions for Schema Integration
# ============================================================================

def validate_search_params(query_params: dict) -> SearchQueryParams:
    """
    Validate and parse search query parameters.

    Args:
        query_params: Raw query parameters from request

    Returns:
        SearchQueryParams: Validated parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    try:
        return SearchQueryParams(**query_params)
    except PydanticValidationError as e:
        # Extract the first validation error for a user-friendly message
        error_details = e.errors()[0] if e.errors() else {}
        field = error_details.get('loc', ['unknown'])[0] if error_details.get('loc') else 'unknown'
        message = error_details.get('msg', str(e))

        # Create user-friendly error messages
        if field == 'limit':
            if 'greater_than_equal' in message or 'ge=' in str(e):
                raise ValidationError("Limit must be between 1 and 100")
            elif 'less_than_equal' in message or 'le=' in str(e):
                raise ValidationError("Limit must be between 1 and 100")
        elif field == 'offset' and 'greater_than_equal' in message:
            raise ValidationError("Offset must be 0 or greater")
        elif field == 'offset' and 'greater_than_equal' in message:
            raise ValidationError("Offset must be 0 or greater")
        elif field == 'q':
            raise ValidationError("Search query is required and cannot be empty")

        # Generic validation error
        raise ValidationError(f"Invalid search parameter '{field}': {message}")


def validate_uuid_path(audio_id: str) -> str:
    """
    Validate and normalize UUID path parameter.

    Args:
        audio_id: Raw audio ID from path

    Returns:
        str: Validated and normalized UUID

    Raises:
        ValidationError: If UUID is invalid
    """
    try:
        params = UUIDPathParams(audio_id=audio_id)
        return params.audio_id
    except PydanticValidationError as e:
        # Extract the specific validation error message from the schema validator
        error_details = e.errors()[0] if e.errors() else {}
        error_msg = error_details.get('msg', 'Invalid audio ID format')
        raise ValidationError(error_msg)


def validate_download_params(format_param: str, preset_param: Optional[str] = None) -> tuple[str, Optional[str]]:
    """
    Validate download parameters.

    Args:
        format_param: Raw format parameter
        preset_param: Raw preset parameter (optional)

    Returns:
        tuple: (format, preset) - validated and normalized

    Raises:
        ValidationError: If parameters are invalid
    """
    if not format_param:
        raise ValidationError("Format parameter is required")

    try:
        params = DownloadQueryParams(format=format_param, preset=preset_param)

        # Additional validation for format and preset
        from src.converter import validate_format, validate_preset
        if not validate_format(params.format):
            raise ValidationError(f"Unsupported format: {params.format}")

        if params.preset and not validate_preset(params.format, params.preset):
            raise ValidationError(f"Invalid preset '{params.preset}' for format '{params.format}'")

        return params.format.lower(), params.preset.lower() if params.preset else None
    except PydanticValidationError as e:
        error_details = e.errors()[0] if e.errors() else {}
        field = error_details.get('loc', ['unknown'])[0] if error_details.get('loc') else 'unknown'
        raise ValidationError(f"Invalid download parameter '{field}': {error_details.get('msg', str(e))}")


__all__ = [
    "ErrorCode",
    "SearchQueryParams",
    "UUIDPathParams",
    "DownloadQueryParams",
    "validate_search_params",
    "validate_uuid_path",
    "validate_download_params",
]
