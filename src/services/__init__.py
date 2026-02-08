"""
Service layer module.

Provides business logic services for audio, party, work, album, and playlist operations.
"""

from .audio_service import (
    get_audio_metadata,
    search_audio_library,
    delete_audio_track_and_files,
)
from .party_service import (
    get_party,
    create_party,
    search_parties,
)
from .work_service import (
    get_work,
    create_work,
    search_works,
    update_work_writers,
    update_work_publishers,
)
from .album_service import (
    get_album,
    create_album,
    update_album,
    delete_album,
    search_albums,
    add_track_to_album,
    remove_track_from_album,
    reorder_album_tracks,
)
from .playlist_service import (
    get_playlist,
    create_playlist,
    update_playlist,
    delete_playlist,
    search_playlists,
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist_tracks,
    add_collaborator,
    remove_collaborator,
)

__all__ = [
    # Audio service
    "get_audio_metadata",
    "search_audio_library",
    "delete_audio_track_and_files",
    # Party service
    "get_party",
    "create_party",
    "search_parties",
    # Work service
    "get_work",
    "create_work",
    "search_works",
    "update_work_writers",
    "update_work_publishers",
    # Album service
    "get_album",
    "create_album",
    "update_album",
    "delete_album",
    "search_albums",
    "add_track_to_album",
    "remove_track_from_album",
    "reorder_album_tracks",
    # Playlist service
    "get_playlist",
    "create_playlist",
    "update_playlist",
    "delete_playlist",
    "search_playlists",
    "add_track_to_playlist",
    "remove_track_from_playlist",
    "reorder_playlist_tracks",
    "add_collaborator",
    "remove_collaborator",
]
