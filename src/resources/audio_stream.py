"""
Audio stream resource for MCP server.

Provides streaming access to audio files stored in GCS with proper
HTTP headers for audio playback and range request support.
"""

import logging
from typing import Optional
from pathlib import Path
from starlette.responses import StreamingResponse, Response
from starlette.requests import Request

from storage.gcs_client import generate_signed_url, create_gcs_client
from database.operations import get_audio_metadata_by_id
from exceptions import ResourceNotFoundError, StorageError

logger = logging.getLogger(__name__)


async def serve_audio_stream(audio_id: str, request: Request) -> Response:
    """
    Serve audio file as streaming resource with range support.
    
    This MCP resource provides streaming access to audio files stored in GCS.
    Supports HTTP range requests for efficient audio playback and seeking.
    
    Args:
        audio_id: UUID of the audio track
        request: Starlette request object (for range headers)
    
    Returns:
        StreamingResponse with audio data and proper headers
    
    Raises:
        ResourceNotFoundError: If audio track doesn't exist
        StorageError: If GCS access fails
    """
    try:
        # Get audio metadata from database
        track_metadata = get_audio_metadata_by_id(audio_id)
        if not track_metadata:
            raise ResourceNotFoundError(f"Audio track not found: {audio_id}")
        
        # Check if track is completed
        if track_metadata.get('status') != 'COMPLETED':
            raise ResourceNotFoundError(f"Audio track not ready: {audio_id}")
        
        # Get GCS path
        audio_gcs_path = track_metadata.get('audio_gcs_path')
        if not audio_gcs_path:
            raise ResourceNotFoundError(f"No audio file found for track: {audio_id}")
        
        # Extract blob name from GCS path (gs://bucket/path -> path)
        if not audio_gcs_path.startswith('gs://'):
            raise StorageError(f"Invalid GCS path format: {audio_gcs_path}")
        
        blob_name = audio_gcs_path[5:]  # Remove 'gs://' prefix
        bucket_name = blob_name.split('/')[0]
        blob_path = '/'.join(blob_name.split('/')[1:])
        
        logger.info(f"Serving audio stream for {audio_id}: {blob_path}")
        
        # Generate signed URL for streaming
        signed_url = generate_signed_url(
            blob_name=blob_path,
            bucket_name=bucket_name,
            expiration_minutes=15,  # 15 minutes for streaming
            method="GET"
        )
        
        # Determine content type from file extension
        file_extension = Path(blob_path).suffix.lower()
        content_type_map = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
        }
        content_type = content_type_map.get(file_extension, 'audio/mpeg')
        
        # Create streaming response with proper headers
        headers = {
            'Content-Type': content_type,
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Range',
            'Access-Control-Expose-Headers': 'Content-Range, Accept-Ranges, Content-Length',
        }
        
        # For range requests, we need to proxy the request to GCS
        # This is a simplified implementation - in production you might want
        # to implement proper range request handling
        range_header = request.headers.get('Range')
        
        if range_header:
            # Handle range request
            logger.debug(f"Range request for {audio_id}: {range_header}")
            # For now, redirect to signed URL with range header
            # In production, you'd want to proxy the range request properly
            return Response(
                status_code=302,
                headers={
                    'Location': signed_url,
                    **headers
                }
            )
        else:
            # Full file request - redirect to signed URL
            return Response(
                status_code=302,
                headers={
                    'Location': signed_url,
                    **headers
                }
            )
    
    except ResourceNotFoundError:
        logger.warning(f"Audio stream not found: {audio_id}")
        return Response(
            status_code=404,
            content="Audio track not found",
            headers={'Content-Type': 'text/plain'}
        )
    
    except StorageError as e:
        logger.error(f"Storage error serving audio stream {audio_id}: {e}")
        return Response(
            status_code=500,
            content="Storage error",
            headers={'Content-Type': 'text/plain'}
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error serving audio stream {audio_id}: {e}")
        return Response(
            status_code=500,
            content="Internal server error",
            headers={'Content-Type': 'text/plain'}
        )


async def get_audio_stream_info(audio_id: str) -> dict:
    """
    Get information about an audio stream resource.
    
    Args:
        audio_id: UUID of the audio track
    
    Returns:
        Dictionary with stream information
    """
    try:
        # Get audio metadata from database
        track_metadata = get_audio_metadata_by_id(audio_id)
        if not track_metadata:
            raise ResourceNotFoundError(f"Audio track not found: {audio_id}")
        
        return {
            'audio_id': audio_id,
            'title': track_metadata.get('title', 'Unknown'),
            'artist': track_metadata.get('artist', 'Unknown'),
            'album': track_metadata.get('album', ''),
            'duration': track_metadata.get('duration_seconds', 0),
            'format': track_metadata.get('format', ''),
            'status': track_metadata.get('status', 'UNKNOWN'),
            'stream_url': f"music-library://audio/{audio_id}/stream",
            'available': track_metadata.get('status') == 'COMPLETED'
        }
    
    except Exception as e:
        logger.error(f"Error getting audio stream info for {audio_id}: {e}")
        return {
            'audio_id': audio_id,
            'error': str(e),
            'available': False
        }
