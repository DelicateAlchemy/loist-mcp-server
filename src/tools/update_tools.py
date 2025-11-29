"""
Update tools for Loist Music Library MCP Server.

Implements update_metadata MCP tool for editing track metadata
following JSON Merge Patch semantics.

Pattern follows query_tools.py:
- Input validation with Pydantic
- Proper error handling
- Structured success/error responses
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
from database import update_audio_metadata
from src.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    DatabaseOperationError,
)

logger = logging.getLogger(__name__)


async def update_metadata(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata for a previously processed audio track.
    
    Uses JSON Merge Patch semantics:
    - Omit a field → unchanged
    - Provide a value → update it
    
    Args:
        input_data: Dict containing:
            - audioId: UUID of the track to update
            - metadata: Dict with fields to update
    
    Returns:
        Dict with success status, updated fields list, and full metadata
        
    Error codes:
        - VALIDATION_ERROR: Invalid input or empty metadata
        - RESOURCE_NOT_FOUND: Track doesn't exist
        - DATABASE_ERROR: Database operation failed
    """
    logger.info("Processing update_metadata request")
    
    try:
        # Validate audioId
        validated = UpdateMetadataInput(**input_data)
        audio_id = validated.audioId
        
        # Get metadata from input
        raw_metadata = input_data.get("metadata", {})
        
        if not raw_metadata:
            logger.warning(f"Empty metadata provided for track {audio_id}")
            return UpdateMetadataError(
                success=False,
                error=UpdateErrorCode.VALIDATION_ERROR,
                message="No metadata fields provided to update"
            ).model_dump()
        
        # Parse and validate metadata fields
        metadata_update = TrackMetadataUpdate(**raw_metadata)
        
        # Get only fields that were explicitly provided (exclude_unset!)
        # This is the key pattern for JSON Merge Patch semantics
        update_data = metadata_update.model_dump(exclude_unset=True)
        
        if not update_data:
            logger.warning(f"No valid fields after parsing for track {audio_id}")
            return UpdateMetadataError(
                success=False,
                error=UpdateErrorCode.VALIDATION_ERROR,
                message="No valid fields provided to update"
            ).model_dump()
        
        # Title can't be empty string if provided
        if "title" in update_data and not update_data["title"]:
            logger.warning(f"Empty title rejected for track {audio_id}")
            return UpdateMetadataError(
                success=False,
                error=UpdateErrorCode.VALIDATION_ERROR,
                message="Title cannot be empty"
            ).model_dump()
        
        logger.info(
            f"Updating track {audio_id} with fields: {list(update_data.keys())}"
        )
        
        # Perform update via database layer
        updated_track = update_audio_metadata(audio_id, update_data)
        
        logger.info(f"Successfully updated track {audio_id}")
        
        return UpdateMetadataOutput(
            success=True,
            audioId=audio_id,
            updatedFields=list(update_data.keys()),
            metadata=updated_track
        ).model_dump()
        
    except ValidationError as e:
        logger.warning(f"Validation error in update_metadata: {e}")
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.VALIDATION_ERROR,
            message=str(e)
        ).model_dump()
        
    except ResourceNotFoundError as e:
        logger.warning(f"Track not found in update_metadata: {e}")
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.RESOURCE_NOT_FOUND,
            message="Audio track not found"
        ).model_dump()
        
    except DatabaseOperationError as e:
        logger.error(f"Database error in update_metadata: {e}")
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.DATABASE_ERROR,
            message="Database operation failed"
        ).model_dump()
        
    except Exception as e:
        logger.exception(f"Unexpected error in update_metadata: {e}")
        return UpdateMetadataError(
            success=False,
            error=UpdateErrorCode.DATABASE_ERROR,
            message="Failed to update metadata"
        ).model_dump()

