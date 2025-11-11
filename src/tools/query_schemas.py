"""
Pydantic schemas for query/retrieval MCP tools.

Implements validation for get_audio_metadata and search_library tools
following best practices from research on read-only APIs.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re


# ============================================================================
# Enums for type safety
# ============================================================================

class AudioFormat(str, Enum):
    """Supported audio formats for filtering"""
    MP3 = "MP3"
    FLAC = "FLAC"
    M4A = "M4A"
    OGG = "OGG"
    WAV = "WAV"
    AAC = "AAC"


class SortField(str, Enum):
    """Available fields for sorting search results"""
    RELEVANCE = "relevance"
    TITLE = "title"
    ARTIST = "artist"
    YEAR = "year"
    DURATION = "duration"
    CREATED_AT = "created_at"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


# ============================================================================
# Input Schemas - get_audio_metadata
# ============================================================================

class GetAudioMetadataInput(BaseModel):
    """
    Input schema for get_audio_metadata tool.
    
    Retrieves metadata for a previously processed audio track.
    
    Example:
        {
            "audioId": "550e8400-e29b-41d4-a716-446655440000"
        }
    """
    audioId: str = Field(
        ...,
        description="UUID of the audio track",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=36,
        max_length=36
    )

    @field_validator('audioId')
    @classmethod
    def validate_uuid_format(cls, v):
        """Ensure audioId is a valid UUID format"""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError("audioId must be a valid UUID format")
        return v.lower()  # Normalize to lowercase

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audioId": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }


# ============================================================================
# Input Schemas - search_library
# ============================================================================

class YearFilter(BaseModel):
    """Year range filter"""
    min: Optional[int] = Field(None, ge=1900, le=2100, description="Minimum year")
    max: Optional[int] = Field(None, ge=1900, le=2100, description="Maximum year")

    @model_validator(mode='after')
    def validate_year_range(self):
        """Ensure min is less than or equal to max"""
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError("min year must be less than or equal to max year")
        return self


class DurationFilter(BaseModel):
    """Duration range filter in seconds"""
    min: Optional[float] = Field(None, ge=0, description="Minimum duration in seconds")
    max: Optional[float] = Field(None, ge=0, description="Maximum duration in seconds")

    @model_validator(mode='after')
    def validate_duration_range(self):
        """Ensure min is less than or equal to max"""
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError("min duration must be less than or equal to max duration")
        return self


class SearchFilters(BaseModel):
    """
    Advanced filters for search_library tool.
    
    All filters are optional and can be combined using AND logic.
    """
    genre: Optional[List[str]] = Field(
        default=None,
        description="List of genres to filter by (OR logic)",
        max_length=10
    )
    year: Optional[YearFilter] = Field(
        default=None,
        description="Year range filter"
    )
    duration: Optional[DurationFilter] = Field(
        default=None,
        description="Duration range filter in seconds"
    )
    format: Optional[List[AudioFormat]] = Field(
        default=None,
        description="List of audio formats to filter by (OR logic)",
        max_length=10
    )
    artist: Optional[str] = Field(
        default=None,
        description="Filter by artist name (case-insensitive partial match)",
        max_length=255
    )
    album: Optional[str] = Field(
        default=None,
        description="Filter by album name (case-insensitive partial match)",
        max_length=255
    )


class SearchLibraryInput(BaseModel):
    """
    Input schema for search_library tool.
    
    Performs full-text search across audio library with optional filters.
    
    Example:
        {
            "query": "hey jude",
            "filters": {
                "genre": ["Rock"],
                "year": {"min": 1960, "max": 1970}
            },
            "limit": 20,
            "offset": 0,
            "sortBy": "relevance",
            "sortOrder": "desc"
        }
    """
    query: str = Field(
        ...,
        description="Search query (searches across title, artist, album, genre)",
        min_length=1,
        max_length=500
    )
    filters: Optional[SearchFilters] = Field(
        default=None,
        description="Optional filters to narrow results"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (max: 100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip (for pagination)"
    )
    sortBy: SortField = Field(
        default=SortField.RELEVANCE,
        description="Field to sort results by"
    )
    sortOrder: SortOrder = Field(
        default=SortOrder.DESC,
        description="Sort order (asc or desc)"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v):
        """
        Sanitize search query to prevent injection attacks.
        
        Removes potentially dangerous characters while preserving search functionality.
        """
        # Remove null bytes and control characters
        v = ''.join(char for char in v if ord(char) >= 32 or char in ('\n', '\t'))
        
        # Strip leading/trailing whitespace
        v = v.strip()
        
        if not v:
            raise ValueError("Query cannot be empty after sanitization")
        
        return v

    @field_validator('offset')
    @classmethod
    def validate_pagination(cls, v):
        """Prevent excessively large offset values (deep pagination)"""
        if v > 10000:
            raise ValueError("offset cannot exceed 10000 (use cursor-based pagination for deep results)")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "beatles",
                    "limit": 20,
                    "offset": 0
                },
                {
                    "query": "rock music",
                    "filters": {
                        "genre": ["Rock", "Classic Rock"],
                        "year": {"min": 1960, "max": 1980},
                        "duration": {"min": 180, "max": 360}
                    },
                    "limit": 50,
                    "offset": 0,
                    "sortBy": "year",
                    "sortOrder": "desc"
                }
            ]
        }
    }


# ============================================================================
# Output Schemas - Shared Components
# ============================================================================

# Reuse Product and Format metadata from process_audio schemas
from .schemas import ProductMetadata, FormatMetadata, AudioMetadata, AudioResources


class GetAudioMetadataOutput(BaseModel):
    """
    Success output for get_audio_metadata tool.
    
    Returns complete metadata for a single audio track.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    audioId: str = Field(description="UUID of the audio track")
    metadata: AudioMetadata = Field(description="Complete audio metadata")
    resources: AudioResources = Field(description="Resource URIs")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "audioId": "550e8400-e29b-41d4-a716-446655440000",
                    "metadata": {
                        "Product": {
                            "Artist": "The Beatles",
                            "Title": "Hey Jude",
                            "Album": "Hey Jude",
                            "MBID": None,
                            "Genre": ["Rock"],
                            "Year": 1968
                        },
                        "Format": {
                            "Duration": 431.0,
                            "Channels": 2,
                            "Sample rate": 44100,
                            "Bitrate": 320000,
                            "Format": "MP3"
                        },
                        "urlEmbedLink": "http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000"
                    },
                    "resources": {
                        "audio": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
                        "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
                        "waveform": None
                    }
                }
            ]
        }
    }


class SearchResult(BaseModel):
    """Individual search result with metadata and relevance score"""
    audioId: str = Field(description="UUID of the audio track")
    metadata: AudioMetadata = Field(description="Complete audio metadata")
    score: float = Field(
        ge=0.0,
        description="Relevance score (higher is more relevant)"
    )


class SearchLibraryOutput(BaseModel):
    """
    Success output for search_library tool.
    
    Returns list of matching audio tracks with pagination metadata.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[SearchResult] = Field(
        description="List of matching audio tracks with relevance scores"
    )
    total: int = Field(
        ge=0,
        description="Total number of matching results (may be more than returned)"
    )
    limit: int = Field(description="Number of results requested")
    offset: int = Field(description="Number of results skipped")
    hasMore: bool = Field(
        description="Whether more results are available"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "results": [
                        {
                            "audioId": "550e8400-e29b-41d4-a716-446655440000",
                            "metadata": {
                                "Product": {
                                    "Artist": "The Beatles",
                                    "Title": "Hey Jude",
                                    "Album": "Hey Jude",
                                    "MBID": None,
                                    "Genre": ["Rock"],
                                    "Year": 1968
                                },
                                "Format": {
                                    "Duration": 431.0,
                                    "Channels": 2,
                                    "Sample rate": 44100,
                                    "Bitrate": 320000,
                                    "Format": "MP3"
                                },
                                "urlEmbedLink": "http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000"
                            },
                            "score": 0.95
                        }
                    ],
                    "total": 150,
                    "limit": 20,
                    "offset": 0,
                    "hasMore": True
                }
            ]
        }
    }


# ============================================================================
# Error Schemas
# ============================================================================

class QueryErrorCode(str, Enum):
    """Error codes specific to query operations"""
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INVALID_QUERY = "INVALID_QUERY"
    INVALID_FILTER = "INVALID_FILTER"
    PAGINATION_ERROR = "PAGINATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    DELETE_FAILED = "DELETE_FAILED"


class QueryError(BaseModel):
    """
    Error output for query tools.
    
    Example:
        {
            "success": false,
            "error": "RESOURCE_NOT_FOUND",
            "message": "Audio track not found",
            "details": {"audioId": "invalid-uuid"}
        }
    """
    success: Literal[False] = Field(description="Operation failure indicator")
    error: QueryErrorCode = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": "RESOURCE_NOT_FOUND",
                    "message": "Audio track with the specified ID was not found",
                    "details": {
                        "audioId": "550e8400-e29b-41d4-a716-446655440000"
                    }
                },
                {
                    "success": False,
                    "error": "INVALID_QUERY",
                    "message": "Search query contains invalid characters",
                    "details": {
                        "query": "test'; DROP TABLE--"
                    }
                }
            ]
        }
    }


# ============================================================================
# Delete Track Schemas
# ============================================================================

class DeleteAudioInput(BaseModel):
    """
    Input schema for delete_audio tool.

    Deletes a previously processed audio track by its UUID.

    Example:
        {
            "audioId": "550e8400-e29b-41d4-a716-446655440000"
            # "userId": "uuid-for-auth"  # TODO: Add when auth is implemented
        }
    """
    audioId: str = Field(
        ...,
        description="UUID of the audio track to delete",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        min_length=36,
        max_length=36
    )
    # TODO: Add user_id for authorization when auth is implemented
    # userId: Optional[str] = Field(
    #     default=None,
    #     description="User ID for authorization (future feature)",
    #     pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    # )

    @field_validator('audioId')
    @classmethod
    def validate_uuid_format(cls, v):
        """Ensure audioId is a valid UUID format"""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError("audioId must be a valid UUID format")
        return v.lower()  # Normalize to lowercase

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audioId": "550e8400-e29b-41d4-a716-446655440000"
                    # "userId": "user-uuid-here"  # TODO: Add when auth implemented
                }
            ]
        }
    }


class DeleteAudioOutput(BaseModel):
    """
    Success output for delete_audio tool.

    Confirms successful deletion of an audio track.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    audioId: str = Field(description="UUID of the deleted audio track")
    deleted: bool = Field(description="Whether the track was actually deleted")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "audioId": "550e8400-e29b-41d4-a716-446655440000",
                    "deleted": True
                }
            ]
        }
    }


class DeleteAudioError(BaseModel):
    """
    Error output for delete_audio tool.

    Example:
        {
            "success": false,
            "error": "RESOURCE_NOT_FOUND",
            "message": "Audio track not found",
            "details": {"audioId": "invalid-uuid"}
        }
    """
    success: Literal[False] = Field(description="Operation failure indicator")
    error: QueryErrorCode = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": "RESOURCE_NOT_FOUND",
                    "message": "Audio track with the specified ID was not found",
                    "details": {
                        "audioId": "550e8400-e29b-41d4-a716-446655440000"
                    }
                },
                {
                    "success": False,
                    "error": "DELETE_FAILED",
                    "message": "Failed to delete audio track",
                    "details": {
                        "audioId": "550e8400-e29b-41d4-a716-446655440000",
                        "reason": "Database transaction failed"
                    }
                }
            ]
        }
    }


# ============================================================================
# Exception Classes
# ============================================================================

class QueryException(Exception):
    """Base exception for query tool errors"""
    def __init__(self, error_code: QueryErrorCode, message: str, details: Optional[Dict] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_error_response(self) -> QueryError:
        """Convert exception to error response"""
        return QueryError(
            success=False,
            error=self.error_code,
            message=self.message,
            details=self.details if self.details else None
        )


class DeleteException(Exception):
    """Exception for delete audio tool errors"""
    def __init__(self, error_code: QueryErrorCode, message: str, details: Optional[Dict] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_error_response(self) -> DeleteAudioError:
        """Convert exception to delete error response"""
        return DeleteAudioError(
            success=False,
            error=self.error_code,
            message=self.message,
            details=self.details if self.details else None
        )



