"""
Pydantic schemas for party (person/organization) data model.

Parties represent people and organizations involved in music creation and rights
(writers, publishers, artists, labels).
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator
from enum import Enum
import uuid


# ============================================================================
# Enums
# ============================================================================

class PartyType(str, Enum):
    """Type of party (person or organization)"""
    PERSON = "person"
    ORGANIZATION = "organization"


# ============================================================================
# Input Schemas
# ============================================================================

class CreatePartyInput(BaseModel):
    """
    Input schema for creating a new party.
    
    Example:
        {
            "name": "John Smith",
            "party_type": "person",
            "ipi_cae_number": "12345678901",
            "society_affiliation": "PRS"
        }
    """
    name: str = Field(
        ...,
        description="Display name for the party",
        min_length=1,
        max_length=500
    )
    party_type: PartyType = Field(
        default=PartyType.PERSON,
        description="Type of party: person or organization"
    )
    legal_name: Optional[str] = Field(
        default=None,
        description="Legal/contract name if different from display name",
        max_length=500
    )
    ipi_cae_number: Optional[str] = Field(
        default=None,
        description="CAE/IPI number for PRO registration",
        max_length=20
    )
    isni: Optional[str] = Field(
        default=None,
        description="International Standard Name Identifier",
        max_length=20
    )
    society_affiliation: Optional[str] = Field(
        default=None,
        description="PRO affiliation (PRS, BMI, ASCAP, SESAC, SOCAN, etc.)",
        max_length=50
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Contact email address"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Freeform notes for WIP context, disputes, etc."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "John Smith",
                    "party_type": "person",
                    "ipi_cae_number": "12345678901",
                    "society_affiliation": "PRS",
                    "email": "john@example.com"
                },
                {
                    "name": "EMI Music Publishing",
                    "party_type": "organization",
                    "legal_name": "EMI Music Publishing Ltd.",
                    "society_affiliation": "PRS"
                }
            ]
        }
    }


class SearchPartiesInput(BaseModel):
    """
    Input schema for searching parties by name (ILIKE search).
    
    Example:
        {
            "query": "John",
            "limit": 20,
            "offset": 0
        }
    """
    query: str = Field(
        ...,
        description="Search query (searches party names using ILIKE)",
        min_length=1,
        max_length=500
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
    )

    @field_validator('query')
    @classmethod
    def validate_query_not_empty(cls, v):
        """Ensure search query is not just whitespace"""
        if not v.strip():
            raise ValueError("Search query cannot be empty or contain only whitespace")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "John",
                    "limit": 20,
                    "offset": 0
                },
                {
                    "query": "EMI",
                    "limit": 50
                }
            ]
        }
    }


# ============================================================================
# Output Schemas
# ============================================================================

class PartyOutput(BaseModel):
    """
    Output schema for party details, including involvement counts.
    
    Always includes involvement counts (works_as_writer, works_as_publisher,
    recordings_as_artist) to match SQL view pattern.
    
    Example:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "party_type": "person",
            "name": "John Smith",
            "ipi_cae_number": "12345678901",
            "works_as_writer": 5,
            "works_as_publisher": 0,
            "recordings_as_artist": 3
        }
    """
    id: str = Field(description="Unique party ID (UUID)")
    party_type: PartyType = Field(description="Type of party: person or organization")
    name: str = Field(description="Display name for the party")
    legal_name: Optional[str] = Field(default=None, description="Legal/contract name if different from display name")
    ipi_cae_number: Optional[str] = Field(default=None, description="CAE/IPI number for PRO registration")
    isni: Optional[str] = Field(default=None, description="International Standard Name Identifier")
    society_affiliation: Optional[str] = Field(default=None, description="PRO affiliation (PRS, BMI, ASCAP, etc.)")
    email: Optional[str] = Field(default=None, description="Contact email address")
    notes: Optional[str] = Field(default=None, description="Freeform notes for WIP context")
    created_at: str = Field(description="Creation timestamp (ISO format)")
    updated_at: str = Field(description="Last update timestamp (ISO format)")
    
    # Involvement counts (always included)
    works_as_writer: int = Field(
        default=0,
        ge=0,
        description="Number of works this party is credited as writer"
    )
    works_as_publisher: int = Field(
        default=0,
        ge=0,
        description="Number of works this party is credited as publisher"
    )
    recordings_as_artist: int = Field(
        default=0,
        ge=0,
        description="Number of recordings this party is credited as artist"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "party_type": "person",
                    "name": "John Smith",
                    "legal_name": None,
                    "ipi_cae_number": "12345678901",
                    "isni": None,
                    "society_affiliation": "PRS",
                    "email": "john@example.com",
                    "notes": None,
                    "created_at": "2024-12-22T10:00:00Z",
                    "updated_at": "2024-12-22T10:00:00Z",
                    "works_as_writer": 5,
                    "works_as_publisher": 0,
                    "recordings_as_artist": 3
                }
            ]
        }
    }


class SearchPartiesOutput(BaseModel):
    """
    Output schema for party search results with pagination.
    
    Example:
        {
            "success": true,
            "results": [...],
            "total": 42,
            "limit": 20,
            "offset": 0,
            "has_more": true
        }
    """
    success: Literal[True] = Field(description="Operation success indicator")
    results: List[PartyOutput] = Field(description="List of matching parties")
    total: int = Field(ge=0, description="Total number of matching parties")
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
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "party_type": "person",
                            "name": "John Smith",
                            "works_as_writer": 5,
                            "works_as_publisher": 0,
                            "recordings_as_artist": 3
                        }
                    ],
                    "total": 42,
                    "limit": 20,
                    "offset": 0,
                    "has_more": True
                }
            ]
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def validate_party_id(party_id: str) -> str:
    """
    Validate and normalize UUID format for party_id.
    
    Args:
        party_id: Raw party ID from input
        
    Returns:
        str: Validated and normalized UUID (lowercase)
        
    Raises:
        ValueError: If UUID format is invalid
    """
    try:
        parsed_uuid = uuid.UUID(party_id)
        return str(parsed_uuid).lower()
    except ValueError:
        raise ValueError(
            f"party_id must be a valid UUID format "
            f"(e.g., 550e8400-e29b-41d4-a716-446655440000), got: {party_id[:50]}"
        )

