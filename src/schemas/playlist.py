"""
Pydantic schemas for playlist data model.

Playlists are user-created track collections with collaboration support.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid


# ============================================================================
# Enums
# ============================================================================

class PlaylistCollaboratorRole(str, Enum):
    """Collaboration role for a playlist"""
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


# ============================================================================
# Input Schemas
# ============================================================================

class CreatePlaylistInput(BaseModel):
    """
    Input schema for creating a new playlist.

    Example:
        {
            "name": "Chill Vibes",
            "description": "Relaxing tracks for focus"
        }
    """
    name: str = Field(
        ...,
        description="Playlist name",
        min_length=1,
        max_length=500,
    )
    description: Optional[str] = Field(
        default=None,
        description="Playlist description",
    )
    is_public: bool = Field(
        default=False,
        description="Whether playlist is publicly visible",
    )
    owner_id: Optional[str] = Field(
        default=None,
        description="UUID of the playlist owner (multi-tenancy prep)",
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
                    "name": "Chill Vibes",
                    "description": "Relaxing tracks for focus",
                    "is_public": False,
                },
                {
                    "name": "Party Mix",
                    "is_public": True,
                },
            ]
        }
    }


class UpdatePlaylistInput(BaseModel):
    """
    Input schema for updating playlist metadata (JSON Merge Patch).
    All fields are optional - only provided fields are updated.
    """
    name: Optional[str] = Field(
        default=None,
        description="Playlist name",
        min_length=1,
        max_length=500,
    )
    description: Optional[str] = Field(
        default=None,
        description="Playlist description",
    )
    is_public: Optional[bool] = Field(
        default=None,
        description="Whether playlist is publicly visible",
    )


class SearchPlaylistsInput(BaseModel):
    """
    Input schema for searching playlists by name.
    """
    query: str = Field(
        ...,
        description="Search query (searches playlist names using ILIKE)",
        min_length=1,
        max_length=500,
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
                {"query": "chill", "limit": 20, "offset": 0},
                {"query": "party", "limit": 50},
            ]
        }
    }


class AddPlaylistTrackInput(BaseModel):
    """Input schema for adding a track to a playlist."""
    playlist_id: str = Field(..., description="UUID of the playlist")
    audio_track_id: str = Field(..., description="UUID of the audio track to add")
    position: Optional[int] = Field(
        default=None,
        ge=1,
        description="Track position (1-based). If omitted, appends to end.",
    )
    added_by: Optional[str] = Field(
        default=None,
        description="UUID of user adding the track (multi-tenancy prep)",
    )


class RemovePlaylistTrackInput(BaseModel):
    """Input schema for removing a track from a playlist."""
    playlist_id: str = Field(..., description="UUID of the playlist")
    audio_track_id: str = Field(..., description="UUID of the audio track to remove")


class ReorderPlaylistTracksInput(BaseModel):
    """Input schema for reordering tracks in a playlist."""
    playlist_id: str = Field(..., description="UUID of the playlist")
    track_order: List[str] = Field(
        ...,
        description="Ordered list of audio_track_ids in desired order",
        min_length=1,
    )


class AddCollaboratorInput(BaseModel):
    """Input schema for adding a collaborator to a playlist."""
    playlist_id: str = Field(..., description="UUID of the playlist")
    user_id: str = Field(..., description="UUID of the user to add as collaborator")
    role: PlaylistCollaboratorRole = Field(
        default=PlaylistCollaboratorRole.VIEWER,
        description="Collaboration role",
    )


class RemoveCollaboratorInput(BaseModel):
    """Input schema for removing a collaborator from a playlist."""
    playlist_id: str = Field(..., description="UUID of the playlist")
    user_id: str = Field(..., description="UUID of the collaborator to remove")


# ============================================================================
# Output Schemas
# ============================================================================

class PlaylistTrackOutput(BaseModel):
    """Track information within a playlist context."""
    audio_track_id: str = Field(description="UUID of the audio track")
    title: Optional[str] = Field(default=None, description="Track title")
    artist: Optional[str] = Field(default=None, description="Track artist")
    position: int = Field(description="Track position within playlist")
    added_by: Optional[str] = Field(default=None, description="UUID of user who added this track")
    added_at: str = Field(description="When track was added (ISO format)")


class PlaylistCollaboratorOutput(BaseModel):
    """Collaborator information for a playlist."""
    user_id: str = Field(description="UUID of the collaborator")
    role: PlaylistCollaboratorRole = Field(description="Collaboration role")
    created_at: str = Field(description="When collaborator was added (ISO format)")


class PlaylistOutput(BaseModel):
    """
    Complete playlist output with tracks and collaborators.
    """
    id: str = Field(description="Unique playlist ID (UUID)")
    name: str = Field(description="Playlist name")
    description: Optional[str] = Field(default=None, description="Playlist description")
    is_public: bool = Field(description="Whether playlist is publicly visible")
    owner_id: Optional[str] = Field(default=None, description="Owner UUID")
    track_count: int = Field(default=0, ge=0, description="Number of tracks in playlist")
    created_at: str = Field(description="Creation timestamp (ISO format)")
    updated_at: str = Field(description="Last update timestamp (ISO format)")
    tracks: List[PlaylistTrackOutput] = Field(
        default_factory=list,
        description="Ordered list of tracks in the playlist",
    )
    collaborators: List[PlaylistCollaboratorOutput] = Field(
        default_factory=list,
        description="List of collaborators on this playlist",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "990e8400-e29b-41d4-a716-446655440004",
                    "name": "Chill Vibes",
                    "description": "Relaxing tracks for focus",
                    "is_public": False,
                    "owner_id": None,
                    "track_count": 3,
                    "created_at": "2024-12-22T10:00:00Z",
                    "updated_at": "2024-12-22T10:00:00Z",
                    "tracks": [],
                    "collaborators": [],
                }
            ]
        }
    }


class PlaylistSearchResult(BaseModel):
    """Individual playlist search result."""
    id: str = Field(description="Unique playlist ID (UUID)")
    name: str = Field(description="Playlist name")
    track_count: int = Field(default=0, ge=0, description="Number of tracks")
    is_public: bool = Field(description="Whether playlist is publicly visible")
    created_at: str = Field(description="Creation timestamp (ISO format)")


class SearchPlaylistsOutput(BaseModel):
    """
    Output schema for playlist search results with pagination.
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[PlaylistSearchResult] = Field(description="List of matching playlists")
    total: int = Field(ge=0, description="Total number of matching playlists")
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
                            "name": "Chill Vibes",
                            "track_count": 3,
                            "is_public": False,
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

def validate_playlist_id(playlist_id: str) -> str:
    """
    Validate and normalize UUID format for playlist_id.

    Args:
        playlist_id: Raw playlist ID from input

    Returns:
        str: Validated and normalized UUID (lowercase)

    Raises:
        ValueError: If UUID format is invalid
    """
    try:
        parsed_uuid = uuid.UUID(playlist_id)
        return str(parsed_uuid).lower()
    except ValueError:
        raise ValueError(
            f"playlist_id must be a valid UUID format "
            f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {playlist_id[:50]}"
        )
