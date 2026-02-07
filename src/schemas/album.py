"""
Pydantic schemas for album data model.

Albums represent flexible track groupings that can evolve from WIP projects
to structured drafts to released albums.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid


# ============================================================================
# Enums
# ============================================================================

class AlbumStatus(str, Enum):
    """Lifecycle status for an album"""
    PROJECT = "project"
    DRAFT = "draft"
    RELEASED = "released"


# ============================================================================
# Input Schemas
# ============================================================================

class CreateAlbumInput(BaseModel):
    """
    Input schema for creating a new album.

    Example:
        {
            "name": "Late Night Sessions",
            "description": "WIP tracks from studio session",
            "status": "project"
        }
    """
    name: str = Field(
        ...,
        description="Album name",
        min_length=1,
        max_length=500,
    )
    description: Optional[str] = Field(
        default=None,
        description="Album description or notes",
    )
    status: AlbumStatus = Field(
        default=AlbumStatus.PROJECT,
        description="Lifecycle status: project (WIP), draft (structured), released (final)",
    )
    cover_art_gcs_path: Optional[str] = Field(
        default=None,
        description="GCS path to cover art image (gs://bucket/path)",
    )
    owner_id: Optional[str] = Field(
        default=None,
        description="UUID of the album owner (multi-tenancy prep)",
    )

    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, v):
        if v is not None:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError("owner_id must be a valid UUID")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Late Night Sessions",
                    "description": "WIP tracks from studio session",
                    "status": "project",
                },
                {
                    "name": "Debut Album",
                    "status": "draft",
                    "cover_art_gcs_path": "gs://bucket/covers/debut.jpg",
                },
            ]
        }
    }


class UpdateAlbumInput(BaseModel):
    """
    Input schema for updating album metadata (JSON Merge Patch).
    All fields are optional - only provided fields are updated.
    """
    name: Optional[str] = Field(
        default=None,
        description="Album name",
        min_length=1,
        max_length=500,
    )
    description: Optional[str] = Field(
        default=None,
        description="Album description or notes",
    )
    status: Optional[AlbumStatus] = Field(
        default=None,
        description="Lifecycle status",
    )
    cover_art_gcs_path: Optional[str] = Field(
        default=None,
        description="GCS path to cover art image",
    )


class SearchAlbumsInput(BaseModel):
    """
    Input schema for searching albums by name.

    Example:
        {
            "query": "sessions",
            "limit": 20,
            "offset": 0
        }
    """
    query: str = Field(
        ...,
        description="Search query (searches album names using ILIKE)",
        min_length=1,
        max_length=500,
    )
    status: Optional[AlbumStatus] = Field(
        default=None,
        description="Filter by album status",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v):
        """Ensure search query is not just whitespace"""
        if not v.strip():
            raise ValueError("Search query cannot be empty or contain only whitespace")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "sessions", "limit": 20, "offset": 0},
                {"query": "album", "status": "released", "limit": 50},
            ]
        }
    }


class AddAlbumTrackInput(BaseModel):
    """Input schema for adding a track to an album."""
    album_id: str = Field(..., description="UUID of the album")
    audio_track_id: str = Field(..., description="UUID of the audio track to add")
    position: Optional[int] = Field(
        default=None,
        ge=1,
        description="Track position (1-based). If omitted, appends to end.",
    )
    disc_number: int = Field(
        default=1,
        ge=1,
        description="Disc number (default 1)",
    )


class RemoveAlbumTrackInput(BaseModel):
    """Input schema for removing a track from an album."""
    album_id: str = Field(..., description="UUID of the album")
    audio_track_id: str = Field(..., description="UUID of the audio track to remove")


class ReorderAlbumTracksInput(BaseModel):
    """Input schema for reordering tracks in an album."""
    album_id: str = Field(..., description="UUID of the album")
    track_order: List[str] = Field(
        ...,
        description="Ordered list of audio_track_ids in desired order",
        min_length=1,
    )


# ============================================================================
# Output Schemas
# ============================================================================

class AlbumTrackOutput(BaseModel):
    """Track information within an album context."""
    audio_track_id: str = Field(description="UUID of the audio track")
    title: Optional[str] = Field(default=None, description="Track title")
    artist: Optional[str] = Field(default=None, description="Track artist")
    position: int = Field(description="Track position within disc")
    disc_number: int = Field(description="Disc number")
    added_at: str = Field(description="When track was added (ISO format)")


class AlbumOutput(BaseModel):
    """
    Complete album output with tracks.

    Example:
        {
            "id": "990e8400-e29b-41d4-a716-446655440004",
            "name": "Late Night Sessions",
            "status": "project",
            "track_count": 5,
            "tracks": [...]
        }
    """
    id: str = Field(description="Unique album ID (UUID)")
    name: str = Field(description="Album name")
    description: Optional[str] = Field(default=None, description="Album description")
    status: AlbumStatus = Field(description="Lifecycle status")
    cover_art_gcs_path: Optional[str] = Field(
        default=None, description="GCS path to cover art"
    )
    owner_id: Optional[str] = Field(default=None, description="Owner UUID")
    track_count: int = Field(default=0, ge=0, description="Number of tracks in album")
    created_at: str = Field(description="Creation timestamp (ISO format)")
    updated_at: str = Field(description="Last update timestamp (ISO format)")
    tracks: List[AlbumTrackOutput] = Field(
        default_factory=list,
        description="Ordered list of tracks in the album",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "990e8400-e29b-41d4-a716-446655440004",
                    "name": "Late Night Sessions",
                    "description": "WIP tracks from studio session",
                    "status": "project",
                    "cover_art_gcs_path": None,
                    "owner_id": None,
                    "track_count": 2,
                    "created_at": "2024-12-22T10:00:00Z",
                    "updated_at": "2024-12-22T10:00:00Z",
                    "tracks": [
                        {
                            "audio_track_id": "770e8400-e29b-41d4-a716-446655440002",
                            "title": "Track One",
                            "artist": "Artist",
                            "position": 1,
                            "disc_number": 1,
                            "added_at": "2024-12-22T10:00:00Z",
                        }
                    ],
                }
            ]
        }
    }


class AlbumSearchResult(BaseModel):
    """Individual album search result."""
    id: str = Field(description="Unique album ID (UUID)")
    name: str = Field(description="Album name")
    status: AlbumStatus = Field(description="Lifecycle status")
    track_count: int = Field(default=0, ge=0, description="Number of tracks")
    created_at: str = Field(description="Creation timestamp (ISO format)")


class SearchAlbumsOutput(BaseModel):
    """
    Output schema for album search results with pagination.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[AlbumSearchResult] = Field(description="List of matching albums")
    total: int = Field(ge=0, description="Total number of matching albums")
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
                            "name": "Late Night Sessions",
                            "status": "project",
                            "track_count": 5,
                            "created_at": "2024-12-22T10:00:00Z",
                        }
                    ],
                    "total": 1,
                    "limit": 20,
                    "offset": 0,
                    "has_more": False,
                }
            ]
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def validate_album_id(album_id: str) -> str:
    """
    Validate and normalize UUID format for album_id.

    Args:
        album_id: Raw album ID from input

    Returns:
        str: Validated and normalized UUID (lowercase)

    Raises:
        ValueError: If UUID format is invalid
    """
    try:
        parsed_uuid = uuid.UUID(album_id)
        return str(parsed_uuid).lower()
    except ValueError:
        raise ValueError(
            f"album_id must be a valid UUID format "
            f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {album_id[:50]}"
        )
