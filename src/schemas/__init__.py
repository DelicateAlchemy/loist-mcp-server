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
]

