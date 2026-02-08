# Edit Metadata Endpoint - Implementation Guide

> **Document Purpose**: Context for implementing "edit metadata" for the Loist Music Library MCP Server. Designed for an LLM agent to implement without additional exploration.
>
> **MVP Mindset**: Keep it simple. Single endpoint, partial updates, minimal validation.

---

## Executive Summary

The Loist Music Library currently supports:
- ✅ **Creating** metadata (via `process_audio_complete`)
- ✅ **Reading** metadata (via `get_audio_metadata`, `search_library`)
- ✅ **Deleting** tracks (via `delete_audio`)
- ❌ **Updating** metadata (NOT YET IMPLEMENTED)

**Recommendation**: Single `update_metadata` MCP tool with JSON Merge Patch-style semantics:
- Omit a field → leave it unchanged
- Provide a value → update it
- (MVP: don't worry about `null` to clear fields yet)

---

## Current Architecture Overview

### Database Schema

The `audio_tracks` table contains these field categories:

```sql
-- EDITABLE Product Metadata (from ID3/XMP tags)
artist VARCHAR(500)        -- Can be edited
title VARCHAR(500) NOT NULL -- Can be edited (required)
album VARCHAR(500)         -- Can be edited
genre VARCHAR(100)         -- Can be edited
year INTEGER               -- Can be edited (1800-2100 range)

-- EDITABLE XMP Metadata (from migration 004)
composer VARCHAR(500)      -- Can be edited
publisher VARCHAR(500)     -- Can be edited
record_label VARCHAR(500)  -- Can be edited
isrc VARCHAR(20)          -- Can be edited (format: CC-XXX-YY-NNNNN)

-- READ-ONLY Technical Metadata (derived from audio file)
duration_seconds NUMERIC(10, 3)  -- Should NOT be edited
channels SMALLINT                 -- Should NOT be edited
sample_rate INTEGER               -- Should NOT be edited
bitrate INTEGER                   -- Should NOT be edited
format VARCHAR(20)                -- Should NOT be edited
file_size_bytes BIGINT            -- Should NOT be edited

-- SYSTEM-MANAGED Fields
id UUID PRIMARY KEY              -- Never edited
created_at TIMESTAMP             -- Never edited
updated_at TIMESTAMP             -- Auto-updated by trigger
status VARCHAR(20)               -- Managed by status tools
audio_gcs_path TEXT              -- Should NOT be edited
thumbnail_gcs_path TEXT          -- Should NOT be edited
search_vector TSVECTOR           -- Auto-updated by trigger
```

### Key Database Features

1. **Search Vector Auto-Update**: A trigger automatically rebuilds `search_vector` when `artist`, `title`, `album`, `genre`, `composer`, `publisher`, or `record_label` are updated.

2. **Timestamp Auto-Update**: The `updated_at` field is automatically set to `NOW()` on any update via trigger.

3. **Validation Constraints**: Year must be 1800-2100, ISRC follows specific pattern, etc.

### Repository Pattern

```
src/repositories/audio_repository.py
├── AudioRepositoryInterface (abstract)
│   ├── save_metadata()
│   ├── get_metadata_by_id()
│   ├── search_tracks()
│   └── update_status()  ← Only status updates exist currently
└── PostgresAudioRepository (implementation)
```

### Existing Tool Patterns

All tools follow this structure:

```
src/tools/
├── __init__.py           -- Exports all tools
├── schemas.py            -- ProcessAudioInput/Output schemas
├── query_schemas.py      -- Query tool schemas (GetAudioMetadataInput, etc.)
├── process_audio.py      -- process_audio_complete implementation
└── query_tools.py        -- get_audio_metadata, search_library, delete_audio
```

---

## Recommended Implementation

### Single `update_metadata` Endpoint ✅

This is what Spotify and SoundCloud do. One endpoint, partial updates, simple.

```python
# Tool signature
async def update_metadata(audioId: str, metadata: dict) -> dict:
    """
    Update metadata for a previously processed audio track.
    
    JSON Merge Patch semantics:
    - Omit a field = leave unchanged
    - Provide a value = update it
    
    Editable fields: artist, title, album, genre, year,
                     composer, publisher, record_label, isrc
    
    Returns:
        dict: {success, audioId, updatedFields, metadata}
    """
```

**Why not multiple endpoints?** (e.g., `update_title`, `update_artist`)
- More routes to maintain
- Clients need multiple calls to change several fields
- Doesn't match industry patterns

---

## Implementation Checklist

### 1. Database Layer (`database/operations.py`)

Create a new function:

```python
def update_audio_metadata(
    track_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update metadata fields for an audio track.
    
    Only updates fields that are present in the metadata dict.
    Validates field values and raises ValidationError for invalid data.
    
    Args:
        track_id: UUID of the track to update
        metadata: Dict with fields to update (only provided fields change)
    
    Returns:
        Updated track record with all fields
    
    Raises:
        ValidationError: Invalid field values
        ResourceNotFoundError: Track not found
        DatabaseOperationError: Database error
    """
```

**Key implementation details**:
- Use parameterized SQL to prevent injection
- Only update fields present in metadata dict (partial update)
- Validate year range (1800-2100)
- Validate ISRC format if provided
- Title cannot be set to empty/null
- Return full updated record after UPDATE ... RETURNING *

### 2. Repository Layer (`src/repositories/audio_repository.py`)

Add to interface and implementation:

```python
# In AudioRepositoryInterface
@abstractmethod
def update_metadata(self, track_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update track metadata."""
    pass

# In PostgresAudioRepository
def update_metadata(self, track_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update track metadata."""
    return update_audio_metadata(track_id, metadata)
```

### 3. Pydantic Schemas (`src/tools/update_schemas.py` - NEW FILE)

**Key pattern**: Use `model_dump(exclude_unset=True)` to get only fields that were explicitly provided. This is different from `exclude_none=True` which would exclude fields set to `None`.

```python
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class TrackMetadataUpdate(BaseModel):
    """
    Partial update model - all fields optional.
    
    MVP: Simple validation, no complex ISRC regex.
    Fields not provided = leave unchanged (use exclude_unset=True).
    """
    artist: Optional[str] = Field(default=None, max_length=500)
    title: Optional[str] = Field(default=None, max_length=500)  # Can't be empty if provided
    album: Optional[str] = Field(default=None, max_length=500)
    genre: Optional[str] = Field(default=None, max_length=100)
    year: Optional[int] = Field(default=None, ge=1800, le=2100)
    composer: Optional[str] = Field(default=None, max_length=500)
    publisher: Optional[str] = Field(default=None, max_length=500)
    record_label: Optional[str] = Field(default=None, max_length=500)
    isrc: Optional[str] = Field(default=None, max_length=20)


class UpdateMetadataInput(BaseModel):
    """Input schema for update_metadata tool."""
    audioId: str = Field(
        ...,
        description="UUID of the audio track to update",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    # Note: metadata validated separately via TrackMetadataUpdate


class UpdateMetadataOutput(BaseModel):
    """Success output for update_metadata tool."""
    success: Literal[True]
    audioId: str
    updatedFields: list[str]  # List of field names that were updated
    metadata: Dict[str, Any]  # Full updated metadata

class UpdateErrorCode(str, Enum):
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

class UpdateMetadataError(BaseModel):
    """Error output for update_metadata tool."""
    success: Literal[False]
    error: UpdateErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
```

**Critical Pydantic v2 Pattern**:
```python
# Parse incoming JSON into partial model
patch = TrackMetadataUpdate(**request_body)

# Get ONLY fields that were explicitly set (not just non-None)
update_data = patch.model_dump(exclude_unset=True)

# This means:
# {"artist": "Beatles"}           → {"artist": "Beatles"}       ✓ Update artist
# {"artist": "Beatles", "year": None} → {"artist": "Beatles", "year": None}  ✓ Clear year if allowed
# {}                              → {}                          ✗ No changes - reject
```

### 4. Tool Implementation (`src/tools/update_tools.py` - NEW FILE)

**MVP Implementation** - Keep it simple, follow existing patterns in `query_tools.py`.

```python
"""
Update tools for Loist Music Library MCP Server.
"""

import logging
from typing import Dict, Any

from .update_schemas import (
    UpdateMetadataInput,
    TrackMetadataUpdate,
    UpdateMetadataOutput,
    UpdateMetadataError,
    UpdateErrorCode,
)
from database.operations import update_audio_metadata
from src.exceptions import ValidationError, ResourceNotFoundError

logger = logging.getLogger(__name__)


async def update_metadata(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata for a previously processed audio track.
    
    Uses JSON Merge Patch semantics:
    - Omit a field → unchanged
    - Provide a value → update it
    """
    logger.info("Updating audio metadata")
    
    try:
        # Validate input structure
        validated = UpdateMetadataInput(**input_data)
        audio_id = validated.audioId
        
        # Parse and validate metadata fields
        metadata_update = TrackMetadataUpdate(**input_data.get("metadata", {}))
        
        # Get only fields that were explicitly provided (exclude_unset!)
        update_data = metadata_update.model_dump(exclude_unset=True)
        
        if not update_data:
            return UpdateMetadataError(
                success=False,
                error=UpdateErrorCode.VALIDATION_ERROR,
                message="No fields provided to update"
            ).model_dump()
        
        # Title can't be empty string if provided
        if "title" in update_data and not update_data["title"]:
            return UpdateMetadataError(
                success=False,
                error=UpdateErrorCode.VALIDATION_ERROR,
                message="Title cannot be empty"
            ).model_dump()
        
        # Perform update
        updated_track = update_audio_metadata(audio_id, update_data)
        
        return UpdateMetadataOutput(
            success=True,
            audioId=audio_id,
            updatedFields=list(update_data.keys()),
            metadata=updated_track
        ).model_dump()
        
    except ValidationError as e:
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.VALIDATION_ERROR,
            message=str(e)
        ).model_dump()
        
    except ResourceNotFoundError:
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.RESOURCE_NOT_FOUND,
            message="Audio track not found"
        ).model_dump()
        
    except Exception as e:
        logger.exception(f"Failed to update metadata: {e}")
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.DATABASE_ERROR,
            message="Failed to update metadata"
        ).model_dump()
```

### 5. Server Registration (`src/server.py`)

Add near the other tools (around line 600, after `delete_audio`):

```python
# ============================================================================
# Edit Metadata Tool
# ============================================================================

@mcp.tool()
async def update_metadata(audioId: str, metadata: dict) -> dict:
    """
    Update metadata for a previously processed audio track.
    
    Editable fields: artist, title, album, genre, year,
                     composer, publisher, record_label, isrc
    
    Args:
        audioId: UUID of the audio track
        metadata: Fields to update (omit fields to leave unchanged)

    Returns:
        dict: {success, audioId, updatedFields, metadata}

    Example:
        >>> result = await update_metadata(
        ...     audioId="550e8400-...",
        ...     metadata={"artist": "The Beatles", "year": 1968}
        ... )
    """
    from src.error_utils import handle_tool_error
    from src.tools.update_tools import update_metadata as update_func
    
    try:
        return await update_func({"audioId": audioId, "metadata": metadata})
    except Exception as e:
        error_response = handle_tool_error(e, "update_metadata")
        logger.error(f"Update metadata failed for {audioId}: {error_response}")
        return error_response
```

### 6. HTTP API Endpoint (Optional - Post-MVP)

If you want HTTP access in addition to MCP, add to `src/http_api.py`:

```python
@mcp.custom_route("/api/tracks/{audioId}", methods=["PATCH"])
async def update_track(request: Request) -> JSONResponse:
    """PATCH /api/tracks/{audioId} - Update track metadata."""
    from src.tools.update_tools import update_metadata as update_func
    
    audio_id = request.path_params.get("audioId")
    body = await request.json()
    
    result = await update_func({"audioId": audio_id, "metadata": body})
    
    status = 200 if result.get("success") else (404 if result.get("error") == "RESOURCE_NOT_FOUND" else 400)
    return JSONResponse(result, status_code=status)
```

**Skip this for MVP** - The MCP tool is sufficient.

### 7. Export Updates (`src/tools/__init__.py`)

```python
# Add new imports
from .update_tools import update_metadata

# Add to __all__
__all__ = [
    # Existing
    "process_audio_complete",
    "get_audio_metadata", 
    "search_library",
    "delete_audio",
    # New
    "update_metadata",
]
```

---

## SQL Implementation for Database Layer

Add to `database/operations.py` (near other update functions around line 1359):

```python
def update_audio_metadata(
    track_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update metadata fields for an audio track.
    
    MVP: Simple implementation, minimal validation (Pydantic handles most of it).
    
    Args:
        track_id: UUID of the track
        metadata: Dict with fields to update (pre-validated by Pydantic)
    
    Returns:
        Full updated track record
        
    Raises:
        ResourceNotFoundError: Track doesn't exist
        DatabaseOperationError: Database error
    """
    from psycopg2.extras import RealDictCursor
    
    if not metadata:
        raise ValidationError("No metadata fields to update")
    
    # Allowed fields (safety check - Pydantic should have already filtered)
    allowed = {'artist', 'title', 'album', 'genre', 'year',
               'composer', 'publisher', 'record_label', 'isrc'}
    
    updates = {k: v for k, v in metadata.items() if k in allowed}
    
    if not updates:
        raise ValidationError("No valid fields to update")
    
    # Build dynamic UPDATE query (parameterized for safety)
    set_clauses = [f"{field} = %s" for field in updates.keys()]
    params = list(updates.values())
    params.append(track_id)
    
    query = f"""
        UPDATE audio_tracks
        SET {', '.join(set_clauses)}
        WHERE id = %s::uuid
        RETURNING *
    """
    # Note: updated_at is handled by existing trigger
    
    pool = get_connection_pool()
    with pool.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            result = cur.fetchone()
            
            if not result:
                raise ResourceNotFoundError(f"Track not found: {track_id}")
            
            conn.commit()
            
            # Convert to dict and handle any special types
            return dict(result)
```

**Note**: The existing database triggers will automatically:
- Update `updated_at` timestamp
- Rebuild `search_vector` for full-text search

---

## Test Cases (MVP)

### Unit Tests (`tests/test_update_metadata.py`)

**Keep tests simple for MVP** - focus on happy path and critical error cases.

```python
import pytest
from src.tools.update_tools import update_metadata

class TestUpdateMetadata:
    """Tests for update_metadata tool."""
    
    @pytest.mark.asyncio
    async def test_update_single_field(self, sample_track_id):
        """Test updating a single field."""
        result = await update_metadata({
            "audioId": sample_track_id,
            "metadata": {"artist": "New Artist"}
        })
        assert result["success"] is True
        assert "artist" in result["updatedFields"]
    
    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, sample_track_id):
        """Test updating multiple fields at once."""
        result = await update_metadata({
            "audioId": sample_track_id,
            "metadata": {"artist": "New Artist", "year": 2024}
        })
        assert result["success"] is True
        assert len(result["updatedFields"]) == 2
    
    @pytest.mark.asyncio
    async def test_empty_metadata_rejected(self, sample_track_id):
        """Test that empty metadata is rejected."""
        result = await update_metadata({
            "audioId": sample_track_id,
            "metadata": {}
        })
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_track_not_found(self):
        """Test handling of non-existent track."""
        result = await update_metadata({
            "audioId": "00000000-0000-0000-0000-000000000000",
            "metadata": {"artist": "Test"}
        })
        assert result["success"] is False
        assert result["error"] == "RESOURCE_NOT_FOUND"
```

**Note**: Additional edge case tests can be added post-MVP.

---

## Postman Collection Updates

Add these requests to the existing collection:

```json
{
  "name": "Update Track Metadata",
  "request": {
    "method": "PATCH",
    "url": "{{baseUrl}}/api/tracks/{{audioId}}",
    "header": [
      {
        "key": "Content-Type",
        "value": "application/json"
      }
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"artist\": \"Updated Artist\",\n  \"year\": 2024\n}"
    }
  }
}
```

---

## Research References

This design is informed by:

1. **Spotify Web API** - Uses generic "update resource" endpoints with partial object semantics
2. **SoundCloud API** - `PUT /tracks/:id` accepts only properties to update
3. **FastAPI Tutorial** - Body updates with `exclude_unset=True` pattern
4. **Pydantic v2 Docs** - `model_dump()` and `model_copy()` for partial updates

Key insight from research: Use `exclude_unset=True` (not `exclude_none=True`) to distinguish between "field not provided" vs "field explicitly set to null".

---

## Summary - MVP Implementation

| Component | Action | File | Priority |
|-----------|--------|------|----------|
| Database | Add `update_audio_metadata()` | `database/operations.py` | **Required** |
| Schemas | Create update schemas | `src/tools/update_schemas.py` (NEW) | **Required** |
| Tool | Create update_metadata impl | `src/tools/update_tools.py` (NEW) | **Required** |
| Server | Register `@mcp.tool()` | `src/server.py` | **Required** |
| Exports | Update module exports | `src/tools/__init__.py` | **Required** |
| Tests | Basic test coverage | `tests/test_update_metadata.py` (NEW) | **Required** |
| HTTP API | Add PATCH endpoint | `src/http_api.py` | Optional |
| Repository | Add to interface | `src/repositories/audio_repository.py` | Optional (skip for MVP) |
| Postman | Add PATCH request | Collection JSON | Optional |

### Key Design Decisions (Spotify/SoundCloud-style)

1. **Single PATCH-style endpoint** - Industry standard, used by Spotify and SoundCloud
2. **JSON Merge Patch semantics** - Omit field = unchanged, provide value = update
3. **`exclude_unset=True`** - Critical Pydantic v2 pattern for partial updates
4. **Skip repository layer for MVP** - Call `database/operations.py` directly from tool
5. **Existing triggers handle side effects** - `search_vector` and `updated_at` auto-update

### What We're NOT Doing (MVP)

- ❌ Complex ISRC validation regex
- ❌ Separate `/tracks/{id}/artwork` endpoint (future)
- ❌ Audit logging of changes (future)
- ❌ Batch update endpoint (future)
- ❌ `null` to explicitly clear fields (future - just don't send the field)

---

## Appendix A: Codebase Statistics

```
=== PROJECT STRUCTURE ===
Total Python Files: 136
Total Lines of Code: ~45,000

=== FILES BY DIRECTORY ===
  33 ./tests               # Test suite
  24 ./                    # Root level (test scripts, conftest)
  11 ./src                 # Core source modules
   8 ./database            # Database layer
   8 ./src/exceptions      # Exception classes
   7 ./scripts             # Utility scripts
   6 ./src/tools           # MCP tool implementations ← EDIT HERE
   5 ./src/tasks           # Async task handlers
   5 ./src/storage         # GCS storage layer
   5 ./src/resources       # MCP resource handlers
   5 ./src/metadata        # Metadata extraction
   4 ./src/downloader      # Audio downloader
   2 ./src/repositories    # Repository pattern ← EDIT HERE
   2 ./src/waveform        # Waveform generation
   2 ./src/auth            # Authentication

=== KEY FILES (by size) ===
  2,686 lines  ./database/operations.py      ← ADD update_audio_metadata() HERE
  2,129 lines  ./src/server.py               ← ADD @mcp.tool() registration HERE
  1,369 lines  ./src/metadata/extractor.py
    929 lines  ./src/storage/gcs_client.py
    754 lines  ./src/tools/query_schemas.py  ← PATTERN TO FOLLOW for schemas
    590 lines  ./src/tools/query_tools.py    ← PATTERN TO FOLLOW for tools
    308 lines  ./src/repositories/audio_repository.py ← ADD update_metadata() HERE
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client (Cursor, etc.)                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      src/server.py                              │
│   @mcp.tool() decorators for: process_audio, get_audio_metadata │
│   search_library, delete_audio, [UPDATE_METADATA - NEW]         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      src/tools/                                 │
│   - query_tools.py (get, search, delete implementations)        │
│   - query_schemas.py (Pydantic validation)                      │
│   - [update_tools.py - NEW]                                     │
│   - [update_schemas.py - NEW]                                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               src/repositories/audio_repository.py              │
│   Repository pattern with interface + PostgreSQL implementation │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    database/operations.py                       │
│   Raw SQL operations with connection pool                       │
│   - save_audio_metadata()                                       │
│   - get_audio_metadata_by_id()                                  │
│   - search_audio_tracks()                                       │
│   - [update_audio_metadata() - NEW]                             │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                           │
│   audio_tracks table with triggers for:                         │
│   - search_vector auto-update                                   │
│   - updated_at timestamp auto-update                            │
└─────────────────────────────────────────────────────────────────┘
```

---

*Document generated: November 29, 2025*
*For implementation by: LLM Agent*
*Confidence Level: 🟢 High (based on thorough codebase analysis)*

