"""
Pydantic schemas for work (composition) data model.

Works represent musical compositions, separate from recordings. They include
writers, publishers, and linked recordings.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from decimal import Decimal
import uuid


# ============================================================================
# Enums
# ============================================================================

class WorkStatus(str, Enum):
    """Workflow status for a musical work/composition"""
    DRAFT = "draft"
    SPLITS_PENDING = "splits_pending"
    SPLITS_DISPUTED = "splits_disputed"
    READY = "ready"
    REGISTERED = "registered"


class SplitStatus(str, Enum):
    """Status of a split (writer or publisher share)"""
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


# ============================================================================
# Nested Output Schemas
# ============================================================================

class WorkWriterOutput(BaseModel):
    """
    Writer information for a work, including split details.
    
    Example:
        {
            "party_id": "550e8400-e29b-41d4-a716-446655440000",
            "party_name": "John Smith",
            "split_percentage": 50.0,
            "split_status": "confirmed",
            "notes": null
        }
    """
    party_id: str = Field(description="UUID of the writer party")
    party_name: str = Field(description="Name of the writer party")
    split_percentage: Optional[Decimal] = Field(
        default=None,
        description="Writer share percentage (0-200, null if unknown)"
    )
    split_status: SplitStatus = Field(description="Status of this split")
    notes: Optional[str] = Field(default=None, description="Negotiation notes, context for disputes, etc.")


class WorkPublisherOutput(BaseModel):
    """
    Publisher information for a work, including split details.
    
    Example:
        {
            "party_id": "660e8400-e29b-41d4-a716-446655440001",
            "party_name": "EMI Music Publishing",
            "split_percentage": 100.0,
            "split_status": "confirmed",
            "notes": null
        }
    """
    party_id: str = Field(description="UUID of the publisher party")
    party_name: str = Field(description="Name of the publisher party")
    split_percentage: Optional[Decimal] = Field(
        default=None,
        description="Publisher share percentage (0-200, null if unknown)"
    )
    split_status: SplitStatus = Field(description="Status of this split")
    notes: Optional[str] = Field(default=None, description="Negotiation notes, context for disputes, etc.")


class RecordingOutput(BaseModel):
    """
    Recording linked to a work, including both structured party details
    and raw artist string for fallback display.
    
    Example:
        {
            "audio_track_id": "770e8400-e29b-41d4-a716-446655440002",
            "title": "Hey Jude",
            "party_id": "880e8400-e29b-41d4-a716-446655440003",
            "party_name": "The Beatles",
            "artist": "The Beatles"
        }
    """
    audio_track_id: str = Field(description="UUID of the audio track/recording")
    title: str = Field(description="Title of the recording")
    # Structured party details (from recording_artists junction table)
    party_id: Optional[str] = Field(default=None, description="UUID of the artist party (if linked)")
    party_name: Optional[str] = Field(default=None, description="Name of the artist party (if linked)")
    # Raw artist string (from audio_tracks.artist) - always included as fallback
    artist: Optional[str] = Field(default=None, description="Raw artist name from audio track metadata")


# ============================================================================
# Work Output Schema
# ============================================================================

class WorkOutput(BaseModel):
    """
    Complete work output with writers, publishers, recordings, and warnings.
    
    Includes split validation warnings calculated at the service layer.
    
    Example:
        {
            "id": "990e8400-e29b-41d4-a716-446655440004",
            "title": "Hey Jude",
            "status": "splits_pending",
            "writers": [...],
            "publishers": [...],
            "recordings": [...],
            "warnings": ["Writer splits only add up to 80%"]
        }
    """
    id: str = Field(description="Unique work ID (UUID)")
    title: str = Field(description="Canonical title of the work")
    iswc: Optional[str] = Field(default=None, description="International Standard Musical Work Code")
    language: Optional[str] = Field(default=None, description="ISO 639-1 language code (e.g., en, es, fr)")
    status: WorkStatus = Field(description="Workflow status")
    notes: Optional[str] = Field(default=None, description="Freeform notes for WIP context")
    created_at: str = Field(description="Creation timestamp (ISO format)")
    updated_at: str = Field(description="Last update timestamp (ISO format)")
    
    # Related entities
    writers: List[WorkWriterOutput] = Field(
        default_factory=list,
        description="List of writers on this work with split information"
    )
    publishers: List[WorkPublisherOutput] = Field(
        default_factory=list,
        description="List of publishers on this work with split information"
    )
    recordings: List[RecordingOutput] = Field(
        default_factory=list,
        description="List of recordings linked to this work"
    )
    
    # Split validation warnings (calculated at service layer)
    warnings: List[str] = Field(
        default_factory=list,
        description="Split validation warnings (e.g., 'Writer splits only add up to 80%', 'One or more writer splits are disputed')"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "990e8400-e29b-41d4-a716-446655440004",
                    "title": "Hey Jude",
                    "iswc": None,
                    "language": "en",
                    "status": "splits_pending",
                    "notes": None,
                    "created_at": "2024-12-22T10:00:00Z",
                    "updated_at": "2024-12-22T10:00:00Z",
                    "writers": [
                        {
                            "party_id": "550e8400-e29b-41d4-a716-446655440000",
                            "party_name": "John Lennon",
                            "split_percentage": 50.0,
                            "split_status": "confirmed",
                            "notes": None
                        }
                    ],
                    "publishers": [],
                    "recordings": [
                        {
                            "audio_track_id": "770e8400-e29b-41d4-a716-446655440002",
                            "title": "Hey Jude",
                            "party_id": "880e8400-e29b-41d4-a716-446655440003",
                            "party_name": "The Beatles",
                            "artist": "The Beatles"
                        }
                    ],
                    "warnings": []
                }
            ]
        }
    }


# ============================================================================
# Search Input/Output Schemas
# ============================================================================

class SearchWorksInput(BaseModel):
    """
    Input schema for searching works by title (ILIKE search).
    
    Example:
        {
            "query": "Hey Jude",
            "limit": 20,
            "offset": 0
        }
    """
    query: str = Field(
        ...,
        description="Search query (searches work titles using ILIKE)",
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

    @field_validator('query')
    @classmethod
    def validate_query_not_empty(cls, v):
        """Ensure search query is not just whitespace"""
        if not v.strip():
            raise ValueError("Search query cannot be empty or contain only whitespace")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "Hey Jude",
                    "limit": 20,
                    "offset": 0
                },
                {
                    "query": "Beatles",
                    "limit": 50
                }
            ]
        }
    }


class WorkSearchResult(BaseModel):
    """Individual work search result"""
    id: str = Field(description="Unique work ID (UUID)")
    title: str = Field(description="Title of the work")
    status: WorkStatus = Field(description="Workflow status")
    iswc: Optional[str] = Field(default=None, description="International Standard Musical Work Code")
    created_at: str = Field(description="Creation timestamp (ISO format)")


class SearchWorksOutput(BaseModel):
    """
    Output schema for work search results with pagination.
    
    Example:
        {
            "success": true,
            "results": [...],
            "total": 42,
            "limit": 20,
            "offset": 0,
            "has_more": true
        }
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[WorkSearchResult] = Field(description="List of matching works")
    total: int = Field(ge=0, description="Total number of matching works")
    limit: int = Field(description="Number of results requested")
    offset: int = Field(description="Number of results skipped")
    has_more: bool = Field(description="Whether more results are available")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "results": [
                        {
                            "id": "990e8400-e29b-41d4-a716-446655440004",
                            "title": "Hey Jude",
                            "status": "splits_pending",
                            "iswc": None,
                            "created_at": "2024-12-22T10:00:00Z"
                        }
                    ],
                    "total": 42,
                    "limit": 20,
                    "offset": 0,
                    "has_more": True
                }
            ]
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def validate_work_id(work_id: str) -> str:
    """
    Validate and normalize UUID format for work_id.
    
    Args:
        work_id: Raw work ID from input
        
    Returns:
        str: Validated and normalized UUID (lowercase)
        
    Raises:
        ValueError: If UUID format is invalid
    """
    try:
        parsed_uuid = uuid.UUID(work_id)
        return str(parsed_uuid).lower()
    except ValueError:
        raise ValueError(
            f"work_id must be a valid UUID format "
            f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {work_id[:50]}"
        )

