"""
Query/retrieval tools for Loist Music Library MCP Server.

This module acts as a thin wrapper around the audio service layer,
adapting the service's functionality to the MCP tool protocol. It handles
MCP-specific input validation and error response formatting.
"""

import logging
from typing import Dict, Any
import time

# MCP-specific schemas for input validation and output formatting
from .query_schemas import (
    GetAudioMetadataInput,
    GetAudioMetadataOutput,
    SearchLibraryInput,
    SearchLibraryOutput,
    QueryException,
    QueryErrorCode,
    DeleteAudioInput,
    DeleteAudioOutput,
    DeleteException,
)

# Core business logic is in the service layer
from src.services import audio_service
from src.exceptions import ResourceNotFoundError, DatabaseOperationError

logger = logging.getLogger(__name__)


# ============================================================================
# Main Tool Functions
# ============================================================================

async def get_audio_metadata(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool to retrieve metadata for a previously processed audio track.
    
    Validates MCP input and calls the audio service to fetch data.
    """
    logger.info("Tool: Retrieving audio metadata")
    
    try:
        # 1. Validate MCP input
        try:
            validated_input = GetAudioMetadataInput(**input_data)
        except Exception as e:
            raise QueryException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid input: {str(e)}",
            )
        
        audio_id = validated_input.audio_id
        
        # 2. Call the service layer for business logic
        service_result = await audio_service.get_audio_metadata(audio_id)
        
        # 3. Format the successful response for the MCP client
        response = GetAudioMetadataOutput(
            success=True,
            audio_id=service_result["audio_id"],
            metadata=service_result["metadata"],
            resources=service_result["resources"],
        )
        return response.model_dump()
        
    except (ResourceNotFoundError, DatabaseOperationError) as e:
        logger.warning(f"Service error getting metadata: {e}")
        error_code = (
            QueryErrorCode.RESOURCE_NOT_FOUND
            if isinstance(e, ResourceNotFoundError)
            else QueryErrorCode.DATABASE_ERROR
        )
        raise QueryException(error_code=error_code, message=str(e))

    except QueryException as e:
        logger.error(f"Query error: {e.message}")
        return e.to_error_response().model_dump()
        
    except Exception as e:
        logger.exception(f"Unexpected error retrieving metadata: {e}")
        return QueryException(
            error_code=QueryErrorCode.DATABASE_ERROR,
            message=f"Unexpected error: {str(e)}",
        ).to_error_response().model_dump()


async def search_library(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool to search across all processed audio in the library.

    Validates MCP input and calls the audio service to perform the search.
    """
    logger.info("Tool: Searching audio library")
    start_time = time.time()
    
    try:
        # 1. Validate MCP input
        try:
            validated_input = SearchLibraryInput(**input_data)
        except Exception as e:
            raise QueryException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid search input: {str(e)}",
            )
        
        # 2. Call the service layer
        service_result = await audio_service.search_audio_library(
            query=validated_input.query,
            limit=validated_input.limit,
            offset=validated_input.offset,
            filters=validated_input.filters,
        )
        
        # 3. Format successful MCP response
        response = SearchLibraryOutput(
            success=True,
            results=service_result["results"],
            total=service_result["total"],
            limit=service_result["limit"],
            offset=service_result["offset"],
            has_more=service_result["has_more"],
            facets=service_result["facets"],
        )
        
        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.3f}s: {len(response.results)} results")
        
        return response.model_dump()
        
    except DatabaseOperationError as e:
        logger.error(f"Service error during search: {e}")
        raise QueryException(
            error_code=QueryErrorCode.DATABASE_ERROR,
            message=f"Search failed: {str(e)}",
        )

    except QueryException as e:
        logger.error(f"Query error: {e.message}")
        return e.to_error_response().model_dump()
        
    except Exception as e:
        logger.exception(f"Unexpected error during search: {e}")
        return QueryException(
            error_code=QueryErrorCode.DATABASE_ERROR,
            message=f"Unexpected error: {str(e)}",
        ).to_error_response().model_dump()


async def delete_audio(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool to delete a previously processed audio track.

    Validates MCP input and calls the audio service to perform the deletion.
    """
    logger.info("Tool: Deleting audio track")

    try:
        # 1. Validate MCP input
        try:
            validated_input = DeleteAudioInput(**input_data)
        except Exception as e:
            raise DeleteException(
                error_code=QueryErrorCode.INVALID_QUERY,
                message=f"Invalid input: {str(e)}",
            )

        audio_id = validated_input.audio_id
        
        # 2. Call the service layer
        success = await audio_service.delete_audio_track_and_files(audio_id)
        
        # 3. Format successful MCP response
        response = DeleteAudioOutput(
            success=True,
            audio_id=audio_id,
            deleted=success,
        )
        return response.model_dump()

    except (ResourceNotFoundError, DatabaseOperationError) as e:
        logger.warning(f"Service error deleting track: {e}")
        error_code = (
            QueryErrorCode.RESOURCE_NOT_FOUND
            if isinstance(e, ResourceNotFoundError)
            else QueryErrorCode.DELETE_FAILED
        )
        raise DeleteException(error_code=error_code, message=str(e))
    
    except DeleteException as e:
        logger.error(f"Delete error: {e.message}")
        return e.to_error_response().model_dump()

    except Exception as e:
        logger.exception(f"Unexpected error deleting audio track: {e}")
        return DeleteException(
            error_code=QueryErrorCode.DELETE_FAILED,
            message=f"Unexpected error: {str(e)}",
        ).to_error_response().model_dump()