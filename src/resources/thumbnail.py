"""
Thumbnail resource for MCP server.

Provides access to artwork/thumbnails for audio tracks stored in GCS.
Includes fallback to default image when no artwork is available.
"""

import logging
from typing import Optional
from pathlib import Path
from starlette.responses import Response, FileResponse

from storage.gcs_client import generate_signed_url, create_gcs_client
from database.operations import get_audio_metadata_by_id
from exceptions import ResourceNotFoundError, StorageError

logger = logging.getLogger(__name__)


async def serve_thumbnail(audio_id: str, request) -> Response:
    """
    Serve thumbnail/artwork image for an audio track.
    
    This MCP resource provides access to artwork images stored in GCS.
    Falls back to a default image if no artwork is available.
    
    Args:
        audio_id: UUID of the audio track
        request: Starlette request object
    
    Returns:
        Response with image data or redirect to signed URL
    
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
        
        # Get thumbnail GCS path
        thumbnail_gcs_path = track_metadata.get('thumbnail_gcs_path')
        
        if thumbnail_gcs_path:
            # Extract blob name from GCS path (gs://bucket/path -> path)
            if not thumbnail_gcs_path.startswith('gs://'):
                raise StorageError(f"Invalid GCS path format: {thumbnail_gcs_path}")
            
            blob_name = thumbnail_gcs_path[5:]  # Remove 'gs://' prefix
            bucket_name = blob_name.split('/')[0]
            blob_path = '/'.join(blob_name.split('/')[1:])
            
            logger.info(f"Serving thumbnail for {audio_id}: {blob_path}")
            
            # Generate signed URL for thumbnail
            signed_url = generate_signed_url(
                blob_name=blob_path,
                bucket_name=bucket_name,
                expiration_minutes=60,  # 1 hour for thumbnails
                method="GET"
            )
            
            # Determine content type from file extension
            file_extension = Path(blob_path).suffix.lower()
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            content_type = content_type_map.get(file_extension, 'image/jpeg')
            
            # Redirect to signed URL with proper headers
            return Response(
                status_code=302,
                headers={
                    'Location': signed_url,
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                }
            )
        
        else:
            # No thumbnail available - serve default image
            logger.info(f"No thumbnail available for {audio_id}, serving default")
            return await serve_default_thumbnail()
    
    except ResourceNotFoundError:
        logger.warning(f"Thumbnail not found: {audio_id}")
        return await serve_default_thumbnail()
    
    except StorageError as e:
        logger.error(f"Storage error serving thumbnail {audio_id}: {e}")
        return await serve_default_thumbnail()
    
    except Exception as e:
        logger.exception(f"Unexpected error serving thumbnail {audio_id}: {e}")
        return await serve_default_thumbnail()


async def serve_default_thumbnail() -> Response:
    """
    Serve a default thumbnail image when no artwork is available.
    
    Returns:
        Response with default image data
    """
    # Create a simple SVG default thumbnail
    default_svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="300" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
  <rect width="300" height="300" fill="#f0f0f0"/>
  <circle cx="150" cy="120" r="40" fill="#d0d0d0"/>
  <rect x="110" y="180" width="80" height="40" rx="5" fill="#d0d0d0"/>
  <text x="150" y="250" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#666">
    No Artwork
  </text>
</svg>'''
    
    return Response(
        content=default_svg,
        media_type='image/svg+xml',
        headers={
            'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
        }
    )


async def get_thumbnail_info(audio_id: str) -> dict:
    """
    Get information about a thumbnail resource.
    
    Args:
        audio_id: UUID of the audio track
    
    Returns:
        Dictionary with thumbnail information
    """
    try:
        # Get audio metadata from database
        track_metadata = get_audio_metadata_by_id(audio_id)
        if not track_metadata:
            raise ResourceNotFoundError(f"Audio track not found: {audio_id}")
        
        thumbnail_gcs_path = track_metadata.get('thumbnail_gcs_path')
        
        return {
            'audio_id': audio_id,
            'title': track_metadata.get('title', 'Unknown'),
            'artist': track_metadata.get('artist', 'Unknown'),
            'album': track_metadata.get('album', ''),
            'thumbnail_url': f"music-library://audio/{audio_id}/thumbnail",
            'has_artwork': bool(thumbnail_gcs_path),
            'available': track_metadata.get('status') == 'COMPLETED'
        }
    
    except Exception as e:
        logger.error(f"Error getting thumbnail info for {audio_id}: {e}")
        return {
            'audio_id': audio_id,
            'error': str(e),
            'has_artwork': False,
            'available': False
        }
