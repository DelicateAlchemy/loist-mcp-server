"""
Audio Repository Module

Provides clean data access abstraction for audio operations.
"""

from .audio_repository import (
    AudioRepositoryInterface,
    PostgresAudioRepository,
    get_audio_repository,
    set_audio_repository,
    save_metadata,
    save_metadata_batch,
    get_metadata_by_id,
    search_tracks,
    update_track_status,
)

__all__ = [
    "AudioRepositoryInterface",
    "PostgresAudioRepository",
    "get_audio_repository",
    "set_audio_repository",
    "save_metadata",
    "save_metadata_batch",
    "get_metadata_by_id",
    "search_tracks",
    "update_track_status",
]
