"""
Repository Module

Provides clean data access abstraction for audio, party, and work operations.
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
from .party_repository import (
    PartyRepositoryInterface,
    PostgresPartyRepository,
    get_party_repository,
    set_party_repository,
)
from .work_repository import (
    WorkRepositoryInterface,
    PostgresWorkRepository,
    get_work_repository,
    set_work_repository,
)

__all__ = [
    # Audio repository
    "AudioRepositoryInterface",
    "PostgresAudioRepository",
    "get_audio_repository",
    "set_audio_repository",
    "save_metadata",
    "save_metadata_batch",
    "get_metadata_by_id",
    "search_tracks",
    "update_track_status",
    # Party repository
    "PartyRepositoryInterface",
    "PostgresPartyRepository",
    "get_party_repository",
    "set_party_repository",
    # Work repository
    "WorkRepositoryInterface",
    "PostgresWorkRepository",
    "get_work_repository",
    "set_work_repository",
]
