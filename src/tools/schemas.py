"""
Pydantic schemas for MCP tool input/output validation.

Implements strict validation for the process_audio_complete tool following
FastMCP best practices and API contract specifications.
"""

from typing import Optional, Dict, List, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum


# ============================================================================
# Enums for type safety
# ============================================================================

class SourceType(str, Enum):
    """Supported source types for audio ingestion"""
    HTTP_URL = "http_url"
    # Future: YOUTUBE = "youtube", SPOTIFY = "spotify", etc.


class ErrorCode(str, Enum):
    """Standardized error codes for API responses"""
    SIZE_EXCEEDED = "SIZE_EXCEEDED"
    INVALID_FORMAT = "INVALID_FORMAT"
    FETCH_FAILED = "FETCH_FAILED"
    TIMEOUT = "TIMEOUT"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"
    DATABASE_FAILED = "DATABASE_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class ProcessingStatus(str, Enum):
    """Processing status values"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================================================
# Input Schemas
# ============================================================================

class AudioSource(BaseModel):
    """
    Audio source specification for ingestion.
    
    Attributes:
        type: Source type (currently only http_url supported)
        url: HTTP/HTTPS URL to audio file
        headers: Optional HTTP headers for authentication
        filename: Optional override for filename (inferred from URL if not provided)
        mimeType: Optional MIME type (detected if not provided)
    """
    type: SourceType = Field(
        ...,
        description="Source type for audio ingestion"
    )
    url: HttpUrl = Field(
        ...,
        description="HTTP/HTTPS URL to audio file"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional HTTP headers (e.g., authentication)"
    )
    filename: Optional[str] = Field(
        default=None,
        description="Optional filename override",
        max_length=255
    )
    mimeType: Optional[str] = Field(
        default=None,
        description="Optional MIME type",
        pattern=r"^audio/.*$"
    )

    @field_validator('url')
    @classmethod
    def validate_url_scheme(cls, v):
        """Ensure URL uses http or https scheme"""
        if not str(v).startswith(('http://', 'https://')):
            raise ValueError("URL must use http or https scheme")
        return v


class ProcessingOptions(BaseModel):
    """
    Processing options for audio ingestion.
    
    Attributes:
        maxSizeMB: Maximum file size in megabytes (default: 100MB)
        timeout: Download timeout in seconds (default: 300s)
        validateFormat: Whether to validate audio format (default: True)
    """
    maxSizeMB: float = Field(
        default=100.0,
        ge=1.0,
        le=500.0,
        description="Maximum file size in MB"
    )
    timeout: int = Field(
        default=300,
        ge=10,
        le=600,
        description="Download timeout in seconds"
    )
    validateFormat: bool = Field(
        default=True,
        description="Whether to validate audio format"
    )


class ProcessAudioInput(BaseModel):
    """
    Complete input schema for process_audio_complete tool.
    
    Example:
        {
            "source": {
                "type": "http_url",
                "url": "https://example.com/audio.mp3"
            },
            "options": {
                "maxSizeMB": 100
            }
        }
    """
    source: AudioSource = Field(
        ...,
        description="Audio source specification"
    )
    options: ProcessingOptions = Field(
        default_factory=ProcessingOptions,
        description="Processing options"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": {
                        "type": "http_url",
                        "url": "https://example.com/song.mp3"
                    },
                    "options": {
                        "maxSizeMB": 100
                    }
                }
            ]
        }
    }


# ============================================================================
# Output Schemas
# ============================================================================

class ProductMetadata(BaseModel):
    """Product-level metadata (artist, title, album, etc.)"""
    Artist: str = Field(default="", description="Artist name")
    Title: str = Field(default="Untitled", description="Track title")
    Album: str = Field(default="", description="Album name")
    MBID: Optional[str] = Field(default=None, description="MusicBrainz ID (null in MVP)")
    Genre: List[str] = Field(default_factory=list, description="Genre tags")
    Year: Optional[int] = Field(default=None, ge=1900, le=2100, description="Release year")


class FormatMetadata(BaseModel):
    """Technical format metadata (duration, bitrate, etc.)"""
    Duration: float = Field(ge=0, description="Duration in seconds")
    Channels: int = Field(ge=1, le=16, description="Number of audio channels")
    SampleRate: int = Field(alias="Sample rate", ge=8000, description="Sample rate in Hz")
    Bitrate: int = Field(ge=0, description="Bitrate in bits per second")
    Format: str = Field(description="Audio format (e.g., 'MP3', 'FLAC')")

    model_config = {
        "populate_by_name": True  # Allow both "SampleRate" and "Sample rate"
    }


class AudioMetadata(BaseModel):
    """Complete audio metadata including product and format information"""
    Product: ProductMetadata
    Format: FormatMetadata
    urlEmbedLink: str = Field(description="Embed URL for audio player")


class AudioResources(BaseModel):
    """Resource URIs for audio, thumbnail, and waveform"""
    audio: str = Field(description="URI for audio stream")
    thumbnail: Optional[str] = Field(default=None, description="URI for thumbnail image")
    waveform: Optional[str] = Field(default=None, description="URI for waveform (null in MVP)")


class ProcessAudioOutput(BaseModel):
    """
    Success output schema for process_audio_complete tool.
    
    Example:
        {
            "success": true,
            "audioId": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": {...},
            "resources": {...},
            "processingTime": 2.45
        }
    """
    success: Literal[True] = Field(description="Processing success indicator")
    audioId: str = Field(description="Unique audio track ID (UUID)")
    metadata: AudioMetadata = Field(description="Complete audio metadata")
    resources: AudioResources = Field(description="Resource URIs")
    processingTime: float = Field(ge=0, description="Processing time in seconds")

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
                    },
                    "processingTime": 2.45
                }
            ]
        }
    }


class ProcessAudioError(BaseModel):
    """
    Error output schema for process_audio_complete tool.
    
    Example:
        {
            "success": false,
            "error": "SIZE_EXCEEDED",
            "message": "Audio file exceeds maximum size limit",
            "details": {"max_size_mb": 100, "actual_size_mb": 150}
        }
    """
    success: Literal[False] = Field(description="Processing failure indicator")
    error: ErrorCode = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict] = Field(
        default=None,
        description="Additional error context"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": "SIZE_EXCEEDED",
                    "message": "Audio file exceeds maximum size limit of 100 MB",
                    "details": {
                        "max_size_mb": 100,
                        "actual_size_mb": 150
                    }
                },
                {
                    "success": False,
                    "error": "INVALID_FORMAT",
                    "message": "Unsupported audio format",
                    "details": {
                        "detected_format": "video/mp4"
                    }
                }
            ]
        }
    }


# ============================================================================
# Exception Classes
# ============================================================================

class ProcessAudioException(Exception):
    """Base exception for audio processing errors"""
    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_error_response(self) -> ProcessAudioError:
        """Convert exception to error response"""
        return ProcessAudioError(
            success=False,
            error=self.error_code,
            message=self.message,
            details=self.details if self.details else None
        )

