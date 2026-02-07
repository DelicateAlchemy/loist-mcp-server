"""
Pydantic schemas for data models and API validation.
"""

# Party schemas
from src.schemas.party import (
    PartyType,
    CreatePartyInput,
    SearchPartiesInput,
    PartyOutput,
    SearchPartiesOutput,
    validate_party_id,
)

# Work schemas
from src.schemas.work import (
    WorkStatus,
    SplitStatus,
    WorkWriterOutput,
    WorkPublisherOutput,
    RecordingOutput,
    WorkOutput,
    SearchWorksInput,
    WorkSearchResult,
    SearchWorksOutput,
    validate_work_id,
)

# Publishing schemas (batch updates)
from src.schemas.publishing import (
    WriterInput,
    UpdateWorkWritersInput,
    PublisherInput,
    UpdateWorkPublishersInput,
    LinkArtistInput,
)

# Album schemas
from src.schemas.album import (
    AlbumStatus,
    CreateAlbumInput,
    UpdateAlbumInput,
    SearchAlbumsInput,
    AddAlbumTrackInput,
    RemoveAlbumTrackInput,
    ReorderAlbumTracksInput,
    AlbumTrackOutput,
    AlbumOutput,
    AlbumSearchResult,
    SearchAlbumsOutput,
    validate_album_id,
)

# Playlist schemas
from src.schemas.playlist import (
    PlaylistCollaboratorRole,
    CreatePlaylistInput,
    UpdatePlaylistInput,
    SearchPlaylistsInput,
    AddPlaylistTrackInput,
    RemovePlaylistTrackInput,
    ReorderPlaylistTracksInput,
    AddCollaboratorInput,
    RemoveCollaboratorInput,
    PlaylistTrackOutput,
    PlaylistCollaboratorOutput,
    PlaylistOutput,
    PlaylistSearchResult,
    SearchPlaylistsOutput,
    validate_playlist_id,
)

__all__ = [
    # Party
    "PartyType",
    "CreatePartyInput",
    "SearchPartiesInput",
    "PartyOutput",
    "SearchPartiesOutput",
    "validate_party_id",
    # Work
    "WorkStatus",
    "SplitStatus",
    "WorkWriterOutput",
    "WorkPublisherOutput",
    "RecordingOutput",
    "WorkOutput",
    "SearchWorksInput",
    "WorkSearchResult",
    "SearchWorksOutput",
    "validate_work_id",
    # Publishing
    "WriterInput",
    "UpdateWorkWritersInput",
    "PublisherInput",
    "UpdateWorkPublishersInput",
    "LinkArtistInput",
    # Album
    "AlbumStatus",
    "CreateAlbumInput",
    "UpdateAlbumInput",
    "SearchAlbumsInput",
    "AddAlbumTrackInput",
    "RemoveAlbumTrackInput",
    "ReorderAlbumTracksInput",
    "AlbumTrackOutput",
    "AlbumOutput",
    "AlbumSearchResult",
    "SearchAlbumsOutput",
    "validate_album_id",
    # Playlist
    "PlaylistCollaboratorRole",
    "CreatePlaylistInput",
    "UpdatePlaylistInput",
    "SearchPlaylistsInput",
    "AddPlaylistTrackInput",
    "RemovePlaylistTrackInput",
    "ReorderPlaylistTracksInput",
    "AddCollaboratorInput",
    "RemoveCollaboratorInput",
    "PlaylistTrackOutput",
    "PlaylistCollaboratorOutput",
    "PlaylistOutput",
    "PlaylistSearchResult",
    "SearchPlaylistsOutput",
    "validate_playlist_id",
]
