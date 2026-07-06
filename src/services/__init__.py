"""
Service layer module.

Provides business logic services for audio, party, and work operations.
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
]

