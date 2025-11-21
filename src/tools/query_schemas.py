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


class TimePeriod(str, Enum):
    """Time period options for filtering by creation date"""
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"


class FacetType(str, Enum):
    """Types of facets available for search"""
    COMPOSERS = "composers"
    PUBLISHERS = "publishers"
    RECORD_LABELS = "record_labels"


# ============================================================================
# XMP Filtering Schemas
# ============================================================================

class TimeFilters(BaseModel):
    """
    Time-based filters for creation date filtering.

    Supports both relative time periods and custom date ranges.
    """
    period: Optional[TimePeriod] = Field(
        default=None,
        description="Relative time period (today, yesterday, this_week, etc.)"
    )
    dateFrom: Optional[str] = Field(
        default=None,
        description="Custom start date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$"
    )
    dateTo: Optional[str] = Field(
        default=None,
        description="Custom end date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$"
    )
    timezone: Optional[str] = Field(
        default="UTC",
        description="Timezone for date interpretation (IANA timezone name, e.g., 'America/New_York', 'Europe/London')",
        pattern=r"^[A-Za-z][A-Za-z0-9/_+-]+$"
    )

    @model_validator(mode='after')
    def validate_time_filters(self) -> 'TimeFilters':
        """Validate that either period or date range is specified, but not both"""
        has_period = self.period is not None
        has_date_range = self.dateFrom is not None or self.dateTo is not None

        if has_period and has_date_range:
            raise ValueError("Cannot specify both 'period' and custom date range ('dateFrom'/'dateTo')")

        if not has_period and not has_date_range:
            # This is okay - no time filtering
            pass

        return self


class XMPFilters(BaseModel):
    """
    Filters for XMP metadata fields (composer, publisher, record_label, isrc).

    All filters support partial matching except ISRC which requires exact match.
    """
    composer: Optional[str] = Field(
        default=None,
        description="Filter by composer (partial match)",
        max_length=200
    )
    publisher: Optional[str] = Field(
        default=None,
        description="Filter by publisher (partial match)",
        max_length=200
    )
    record_label: Optional[str] = Field(
        default=None,
        description="Filter by record label (partial match)",
        max_length=200
    )
    isrc: Optional[str] = Field(
        default=None,
        description="Filter by ISRC code (exact match)",
        pattern=r"^[A-Z]{2}-[A-Z0-9]{3}-\d{2}-\d{5}$",
        max_length=12
    )


class FacetRequest(BaseModel):
    """
    Request for facet information to support faceted search UIs.
    """
    composer_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum composer facets to return"
    )
    publisher_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum publisher facets to return"
    )
    record_label_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum record label facets to return"
    )
    min_count: int = Field(
        default=1,
        ge=1,
        description="Minimum frequency for facet inclusion"
    )


class FacetData(BaseModel):
    """
    Facet information for search filters.
    """
    name: str = Field(description="Facet value name")
    count: int = Field(description="Number of tracks with this value")


class SearchFacets(BaseModel):
    """
    Complete facet response for search.
    """
    composers: List[FacetData] = Field(description="Composer facets")
    publishers: List[FacetData] = Field(description="Publisher facets")
    record_labels: List[FacetData] = Field(description="Record label facets")


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

# ============================================================================
# Cursor and Field Validation Helpers
# ============================================================================

def validate_cursor(cursor: Optional[str]) -> Optional[str]:
    """
    Validate cursor format.

    Cursors are base64-encoded JSON with score, created_at, id fields.
    """
    if not cursor:
        return cursor

    try:
        import base64
        import json

        # Decode and parse cursor
        decoded = base64.b64decode(cursor, validate=True)
        data = json.loads(decoded)

        # Validate required fields
        required_fields = ['score', 'created_at', 'id']
        if not all(field in data for field in required_fields):
            raise ValueError("Cursor missing required fields")

        # Basic type validation
        if not isinstance(data['score'], (int, float)):
            raise ValueError("Invalid score in cursor")
        if not isinstance(data['created_at'], str):
            raise ValueError("Invalid created_at in cursor")
        if not isinstance(data['id'], str):
            raise ValueError("Invalid id in cursor")

        return cursor

    except Exception as e:
        raise ValueError(f"Invalid cursor format: {str(e)}")


def validate_fields(fields: Optional[str]) -> Optional[str]:
    """
    Validate comma-separated field list.

    Allowed fields: id, title, score, artist, album, genre, year, duration, channels, sampleRate, bitrate, format, embedLink
    """
    if not fields:
        return fields

    allowed_fields = {
        'id', 'title', 'score', 'artist', 'album', 'genre', 'year',
        'duration', 'channels', 'sampleRate', 'bitrate', 'format', 'embedLink'
    }

    requested_fields = [f.strip() for f in fields.split(',') if f.strip()]

    if not requested_fields:
        raise ValueError("Fields list cannot be empty")

    invalid_fields = set(requested_fields) - allowed_fields
    if invalid_fields:
        raise ValueError(f"Invalid fields: {', '.join(invalid_fields)}. Allowed: {', '.join(allowed_fields)}")

    return fields


class SearchLibraryInput(BaseModel):
    """
    Input schema for search_library tool.

    Performs full-text search across audio library with XMP metadata filters and cursor pagination.

    Example:
        {
            "query": "hey jude",
            "filters": {
                "genre": ["Rock"],
                "year": {"min": 1960, "max": 1980},
                "composer": "JOHN LENNON",
                "publisher": "EMI"
            },
            "limit": 20,
            "offset": 0,
            "sortBy": "relevance",
            "sortOrder": "desc"
        }
    """
    query: str = Field(
        ...,
        description="Search query (searches across title, artist, album, genre, composer, publisher)",
        min_length=1,
        max_length=500
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Advanced filters including XMP metadata fields and time filters"
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
        description="Number of results to skip for pagination"
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
                        "time": {
                            "period": "this_week",
                            "timezone": "America/New_York"
                        }
                    },
                    "limit": 50,
                    "offset": 0,
                    "sortBy": "year",
                    "sortOrder": "desc"
                },
                {
                    "query": "jazz",
                    "filters": {
                        "time": {
                            "dateFrom": "2025-11-01",
                            "dateTo": "2025-11-30",
                            "timezone": "Europe/London"
                        }
                    },
                    "limit": 20
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

    Returns list of matching audio tracks with facets and pagination metadata.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[SearchResult] = Field(
        description="List of matching audio tracks with relevance scores"
    )
    total: int = Field(description="Total number of matching tracks")
    limit: int = Field(description="Number of results requested")
    offset: int = Field(description="Number of results skipped")
    hasMore: bool = Field(
        description="Whether more results are available"
    )
    facets: Optional[SearchFacets] = Field(
        default=None,
        description="Facet information for search filters"
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
                    "limit": 20,
                    "hasMore": True,
                    "nextCursor": "eyJzY29yZSI6MC45NSwiY3JlYXRlZF9hdCI6IjIwMjQtMTEtMTJUMTI6MzQ6NTYuMDAwWiIsImlkIjoiNTUwZTg0MDAtZTJiYi00MWQ0LWE3MTYtNDQ2NjU1NDQwMDAwIn0="
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



