"""
Audio processing orchestration tool for Loist Music Library MCP Server.

Implements the process_audio_complete MCP tool that orchestrates:
1. HTTP download
2. Metadata extraction
3. GCS storage
4. Database persistence

Follows best practices for:
- Transaction management across services
- Automatic cleanup of temporary files
- Status tracking and rollback
- Comprehensive error handling
"""

import logging
from typing import Dict, Any

from .schemas import (
    ProcessAudioInput,
    ProcessAudioError,
    ProcessAudioException,
    ErrorCode,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Main Processing Function
# ============================================================================

async def process_audio_complete(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool adapter for audio processing (wraps shared business logic).
    
    This function is a thin adapter that:
    1. Validates MCP input schema
    2. Converts to shared AudioProcessingRequest
    3. Calls process_audio_shared() (transport-agnostic business logic)
    4. Formats output in MCP's expected shape
    5. Maps shared errors to MCP error format
    
    The actual processing logic lives in src/business/audio_processor.py
    so both MCP and A2A can share the same implementation.
    
    Args:
        input_data: Dictionary containing source and options
        
    Returns:
        Dictionary containing success response or error
        
    Example:
        >>> result = await process_audio_complete({
        ...     "source": {
        ...         "type": "http_url",
        ...         "url": "https://example.com/song.mp3"
        ...     }
        ... })
        >>> print(result["audio_id"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    # Import shared business logic
    from src.business import process_audio_shared, AudioProcessingRequest, SharedAudioProcessingError
    
    try:
        # ====================================================================
        # MCP Adapter: Input Validation
        # ====================================================================
        logger.info("Starting MCP audio processing (calling shared business logic)")
        
        # Validate input schema using Pydantic
        try:
            validated_input = ProcessAudioInput(**input_data)
        except Exception as e:
            logger.error(f"MCP input validation failed: {e}")
            raise ProcessAudioException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid input: {str(e)}",
                details={"validation_errors": str(e)}
            )
        
        source = validated_input.source
        options = validated_input.options
        
        # ====================================================================
        # MCP Adapter: Convert to Shared Request Format
        # ====================================================================
        shared_request = AudioProcessingRequest(
            url=str(source.url),
            headers=source.headers,
            filename=getattr(source, 'filename', None),
            mime_type=getattr(source, 'mime_type', None),
            max_size_mb=options.max_size_mb,
            timeout=options.timeout,
            validate_format=options.validate_format,
            # audio_id is generated inside shared function by default
        )
        
        # ====================================================================
        # MCP Adapter: Call Shared Business Logic
        # ====================================================================
        logger.info(f"Calling shared audio processing for URL: {source.url}")
        
        # Call shared business logic (transport-agnostic)
        result = await process_audio_shared(shared_request)
        
        # ====================================================================
        # MCP Adapter: Format Response
        # ====================================================================
        # The shared result already uses the same snake_case structure as
        # ProcessAudioOutput, so we can just convert to dict and return
        logger.info(f"MCP processing completed for audio_id: {result.audio_id}")
        return result.model_dump()
        
    except SharedAudioProcessingError as e:
        # ====================================================================
        # MCP Adapter: Map Shared Errors to MCP Format
        # ====================================================================
        logger.error(f"Shared processing error: {e.message}")
        
        # Convert shared error to MCP error format
        error_response = ProcessAudioError(
            success=False,
            error=e.code,  # ErrorCode enum is shared
            message=e.message,
            details=e.details if e.details else None
        )
        return error_response.model_dump()
    
    except ProcessAudioException as e:
        # ====================================================================
        # MCP Adapter: Handle Legacy MCP Exceptions (from validation)
        # ====================================================================
        logger.error(f"MCP processing failed: {e.message}")
        
        # Return error response
        error_response = e.to_error_response()
        return error_response.model_dump()
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in MCP adapter: {e}")
        
        # Return generic error
        error_response = ProcessAudioError(
            success=False,
            error=ErrorCode.FETCH_FAILED,
            message=f"Unexpected error: {str(e)}",
            details={"exception_type": type(e).__name__}
        )
        return error_response.model_dump()


# ============================================================================
# Synchronous Wrapper for FastMCP (if needed)
# ============================================================================

def process_audio_complete_sync(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for process_audio_complete.
    
    FastMCP supports async tools, so this is only needed if you encounter
    issues with async support.
    """
    import asyncio
    return asyncio.run(process_audio_complete(input_data))
