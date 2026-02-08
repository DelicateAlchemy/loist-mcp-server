"""
Pydantic schemas for update/edit MCP tools.

Implements validation for update_metadata tool following JSON Merge Patch semantics:
- Omit a field = leave unchanged
- Provide a value = update it

Key pattern: Use model_dump(exclude_unset=True) to distinguish between
"field not provided" vs "field explicitly set to null".
"""

from typing import Optional, Dict, Any, Literal, List
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# Enums for type safety
# ============================================================================

class UpdateErrorCode(str, Enum):
    """Error codes for update operations"""
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


# ============================================================================
# Partial Update Model
# ============================================================================

class TrackMetadataUpdate(BaseModel):
    """
    Partial update model for track metadata - all fields optional.

    MVP: Simple validation, no complex ISRC regex.
    Fields not provided = leave unchanged (use exclude_unset=True).

    Editable fields match the database schema:
    - Product metadata: artist, title, album, genre, year
    - XMP metadata: composer, publisher, record_label, isrc
    - Filename: original_filename
    """
    artist: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Track artist name"
    )
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Track title (cannot be empty if provided)"
    )
    album: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Album name"
    )
    genre: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Music genre"
    )
    year: Optional[int] = Field(
        default=None,
        ge=1800,
        le=2100,
        description="Release year (1800-2100)"
    )
    composer: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Composer name"
    )
    publisher: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Publisher name"
    )
    record_label: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Record label name"
    )
    isrc: Optional[str] = Field(
        default=None,
        max_length=20,
        description="ISRC code (format: CC-XXX-YY-NNNNN)"
    )
    original_filename: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Original filename for downloads (e.g., 'My Song.mp3')"
    )


# ============================================================================
# Input/Output Schemas
# ============================================================================

class UpdateMetadataInput(BaseModel):
    """Input schema for update_metadata tool."""
    audio_id: str = Field(
        ...,
        description="UUID of the audio track to update",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    # Note: metadata validated separately via TrackMetadataUpdate


class UpdateMetadataOutput(BaseModel):
    """Success output for update_metadata tool."""
    success: Literal[True]
    audio_id: str = Field(..., description="UUID of the updated track")
    updated_fields: List[str] = Field(
        ...,
        description="List of field names that were updated"
    )
    metadata: Dict[str, Any] = Field(
        ...,
        description="Full updated metadata record"
    )


class UpdateMetadataError(BaseModel):
    """Error output for update_metadata tool."""
    success: Literal[False]
    error: UpdateErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )

