"""
Pydantic schemas for batch update operations on work writers, publishers, and recording artists.

These schemas support the batch replace pattern used in update_work_writers and
update_work_publishers tools, where the entire list is replaced in a single operation.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from src.schemas.work import SplitStatus
import uuid


# ============================================================================
# Writer Batch Update Schemas
# ============================================================================

class WriterInput(BaseModel):
    """
    Single writer entry for batch update operation.
    
    Used in update_work_writers to specify all writers on a work.
    The entire list replaces existing writers.
    
    Example:
        {
            "party_id": "550e8400-e29b-41d4-a716-446655440000",
            "split_percentage": 50.0,
            "split_status": "confirmed"
        }
    """
    party_id: str = Field(description="UUID of the writer party")
    split_percentage: Optional[Decimal] = Field(
        default=None,
        description="Writer share percentage (0-200, null if unknown)"
    )
    split_status: SplitStatus = Field(
        default=SplitStatus.PROPOSED,
        description="Status of this split"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Negotiation notes, context for disputes, etc."
    )

    @field_validator('party_id')
    @classmethod
    def validate_party_id(cls, v):
        """Validate UUID format for party_id"""
        try:
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()
        except ValueError:
            raise ValueError(
                f"party_id must be a valid UUID format, got: {v[:50]}"
            )

    @field_validator('split_percentage')
    @classmethod
    def validate_split_percentage(cls, v):
        """Validate split percentage is within valid range (0-200)"""
        if v is None:
            return v
        if v < Decimal('0') or v > Decimal('200'):
            raise ValueError(f"split_percentage must be between 0 and 200, got: {v}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "party_id": "550e8400-e29b-41d4-a716-446655440000",
                    "split_percentage": 50.0,
                    "split_status": "confirmed",
                    "notes": None
                },
                {
                    "party_id": "660e8400-e29b-41d4-a716-446655440001",
                    "split_percentage": None,
                    "split_status": "unknown",
                    "notes": "Split to be negotiated"
                }
            ]
        }
    }


class UpdateWorkWritersInput(BaseModel):
    """
    Input schema for update_work_writers tool.
    
    Replaces all writers on a work with the provided list. To add writers,
    include existing + new. To remove writers, exclude from list.
    
    Example:
        {
            "work_id": "990e8400-e29b-41d4-a716-446655440004",
            "writers": [
                {
                    "party_id": "550e8400-e29b-41d4-a716-446655440000",
                    "split_percentage": 50.0,
                    "split_status": "confirmed"
                }
            ]
        }
    """
    work_id: str = Field(description="UUID of the work to update")
    writers: List[WriterInput] = Field(description="Complete list of writers (replaces existing)")

    @field_validator('work_id')
    @classmethod
    def validate_work_id(cls, v):
        """Validate UUID format for work_id"""
        try:
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()
        except ValueError:
            raise ValueError(
                f"work_id must be a valid UUID format, got: {v[:50]}"
            )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "work_id": "990e8400-e29b-41d4-a716-446655440004",
                    "writers": [
                        {
                            "party_id": "550e8400-e29b-41d4-a716-446655440000",
                            "split_percentage": 50.0,
                            "split_status": "confirmed"
                        },
                        {
                            "party_id": "660e8400-e29b-41d4-a716-446655440001",
                            "split_percentage": 50.0,
                            "split_status": "confirmed"
                        }
                    ]
                }
            ]
        }
    }


# ============================================================================
# Publisher Batch Update Schemas
# ============================================================================

class PublisherInput(BaseModel):
    """
    Single publisher entry for batch update operation.
    
    Used in update_work_publishers to specify all publishers on a work.
    The entire list replaces existing publishers.
    
    Example:
        {
            "party_id": "770e8400-e29b-41d4-a716-446655440002",
            "split_percentage": 100.0,
            "split_status": "confirmed"
        }
    """
    party_id: str = Field(description="UUID of the publisher party")
    split_percentage: Optional[Decimal] = Field(
        default=None,
        description="Publisher share percentage (0-200, null if unknown)"
    )
    split_status: SplitStatus = Field(
        default=SplitStatus.PROPOSED,
        description="Status of this split"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Negotiation notes, context for disputes, etc."
    )

    @field_validator('party_id')
    @classmethod
    def validate_party_id(cls, v):
        """Validate UUID format for party_id"""
        try:
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()
        except ValueError:
            raise ValueError(
                f"party_id must be a valid UUID format, got: {v[:50]}"
            )

    @field_validator('split_percentage')
    @classmethod
    def validate_split_percentage(cls, v):
        """Validate split percentage is within valid range (0-200)"""
        if v is None:
            return v
        if v < Decimal('0') or v > Decimal('200'):
            raise ValueError(f"split_percentage must be between 0 and 200, got: {v}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "party_id": "770e8400-e29b-41d4-a716-446655440002",
                    "split_percentage": 100.0,
                    "split_status": "confirmed",
                    "notes": None
                }
            ]
        }
    }


class UpdateWorkPublishersInput(BaseModel):
    """
    Input schema for update_work_publishers tool.
    
    Replaces all publishers on a work with the provided list. To add publishers,
    include existing + new. To remove publishers, exclude from list.
    
    Example:
        {
            "work_id": "990e8400-e29b-41d4-a716-446655440004",
            "publishers": [
                {
                    "party_id": "770e8400-e29b-41d4-a716-446655440002",
                    "split_percentage": 100.0,
                    "split_status": "confirmed"
                }
            ]
        }
    """
    work_id: str = Field(description="UUID of the work to update")
    publishers: List[PublisherInput] = Field(description="Complete list of publishers (replaces existing)")

    @field_validator('work_id')
    @classmethod
    def validate_work_id(cls, v):
        """Validate UUID format for work_id"""
        try:
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()
        except ValueError:
            raise ValueError(
                f"work_id must be a valid UUID format, got: {v[:50]}"
            )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "work_id": "990e8400-e29b-41d4-a716-446655440004",
                    "publishers": [
                        {
                            "party_id": "770e8400-e29b-41d4-a716-446655440002",
                            "split_percentage": 100.0,
                            "split_status": "confirmed"
                        }
                    ]
                }
            ]
        }
    }


# ============================================================================
# Recording Artist Link Schema
# ============================================================================

class LinkArtistInput(BaseModel):
    """
    Input schema for link_artist_to_recording tool.
    
    Links an artist party to a recording (audio_track).
    
    Example:
        {
            "audio_track_id": "880e8400-e29b-41d4-a716-446655440003",
            "party_id": "550e8400-e29b-41d4-a716-446655440000",
            "is_primary": true,
            "notes": "Main artist"
        }
    """
    audio_track_id: str = Field(description="UUID of the audio track/recording")
    party_id: str = Field(description="UUID of the artist party")
    is_primary: bool = Field(
        default=True,
        description="True for primary/main artist, false for featuring/guest artists"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional context about artist involvement"
    )

    @field_validator('audio_track_id', 'party_id')
    @classmethod
    def validate_uuid_fields(cls, v):
        """Validate UUID format"""
        try:
            parsed_uuid = uuid.UUID(v)
            return str(parsed_uuid).lower()
        except ValueError:
            raise ValueError(
                f"Must be a valid UUID format, got: {v[:50]}"
            )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audio_track_id": "880e8400-e29b-41d4-a716-446655440003",
                    "party_id": "550e8400-e29b-41d4-a716-446655440000",
                    "is_primary": True,
                    "notes": "Main artist"
                },
                {
                    "audio_track_id": "880e8400-e29b-41d4-a716-446655440003",
                    "party_id": "660e8400-e29b-41d4-a716-446655440001",
                    "is_primary": False,
                    "notes": "Featuring artist"
                }
            ]
        }
    }

