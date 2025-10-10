"""
Database operations for audio metadata management.

Provides functions for CRUD operations on audio tracks with full-text search,
transaction management, and comprehensive error handling.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import psycopg2.extras
from psycopg2 import DatabaseError, IntegrityError

from .pool import get_connection
from src.exceptions import (
    StorageError,
    ValidationError,
    DatabaseOperationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Save Metadata Operations
# ============================================================================

def save_audio_metadata(
    metadata: Dict[str, Any],
    audio_gcs_path: str,
    thumbnail_gcs_path: Optional[str] = None,
    track_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save audio metadata to PostgreSQL database.
    
    Implements transaction management, input validation, and comprehensive
    error handling following PostgreSQL best practices.
    
    Args:
        metadata: Dictionary containing audio metadata fields:
            - artist: str (optional)
            - title: str (required)
            - album: str (optional)
            - genre: str (optional)
            - year: int (optional, 1800-2100)
            - duration_seconds: float (optional)
            - channels: int (optional, 1-16)
            - sample_rate: int (optional, Hz)
            - bitrate: int (optional, bits per second)
            - format: str (required, e.g., 'MP3', 'FLAC')
            - file_size_bytes: int (optional)
        audio_gcs_path: Full GCS path (gs://bucket/path) to audio file
        thumbnail_gcs_path: Optional GCS path to thumbnail/artwork
        track_id: Optional UUID string for the track (generates new if None)
    
    Returns:
        Dictionary containing the saved track information:
            - id: Track UUID
            - status: Processing status
            - created_at: Timestamp
            - All metadata fields
    
    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseOperationError: If database operation fails
    
    Example:
        >>> metadata = {
        ...     'title': 'Bohemian Rhapsody',
        ...     'artist': 'Queen',
        ...     'album': 'A Night at the Opera',
        ...     'format': 'MP3',
        ...     'duration_seconds': 354.5,
        ...     'sample_rate': 44100,
        ...     'bitrate': 320000,
        ...     'channels': 2
        ... }
        >>> result = save_audio_metadata(
        ...     metadata,
        ...     'gs://loist-audio/tracks/bohemian-rhapsody.mp3',
        ...     'gs://loist-audio/thumbnails/bohemian-rhapsody.jpg'
        ... )
        >>> print(result['id'])
    """
    # Validate required fields
    if not metadata.get('title'):
        raise ValidationError("Title is required for audio metadata")
    
    if not metadata.get('format'):
        raise ValidationError("Format is required for audio metadata")
    
    if not audio_gcs_path or not audio_gcs_path.startswith('gs://'):
        raise ValidationError(
            f"Invalid audio_gcs_path: must start with 'gs://', got: {audio_gcs_path}"
        )
    
    if thumbnail_gcs_path and not thumbnail_gcs_path.startswith('gs://'):
        raise ValidationError(
            f"Invalid thumbnail_gcs_path: must start with 'gs://', got: {thumbnail_gcs_path}"
        )
    
    # Validate year range if provided
    year = metadata.get('year')
    if year is not None:
        try:
            year_int = int(year)
            if year_int < 1800 or year_int > 2100:
                raise ValidationError(f"Year must be between 1800 and 2100, got: {year_int}")
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid year value: {year}")
    
    # Validate channels if provided
    channels = metadata.get('channels')
    if channels is not None:
        try:
            channels_int = int(channels)
            if channels_int < 1 or channels_int > 16:
                raise ValidationError(f"Channels must be between 1 and 16, got: {channels_int}")
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid channels value: {channels}")
    
    # Generate track ID if not provided
    if track_id is None:
        track_id = str(uuid.uuid4())
    else:
        # Validate UUID format
        try:
            uuid.UUID(track_id)
        except ValueError:
            raise ValidationError(f"Invalid track_id format: {track_id}")
    
    # Prepare data for insertion
    insert_data = {
        'id': track_id,
        'status': 'COMPLETED',
        'artist': metadata.get('artist'),
        'title': metadata.get('title'),
        'album': metadata.get('album'),
        'genre': metadata.get('genre'),
        'year': year,
        'duration_seconds': metadata.get('duration_seconds'),
        'channels': channels,
        'sample_rate': metadata.get('sample_rate'),
        'bitrate': metadata.get('bitrate'),
        'format': metadata.get('format'),
        'file_size_bytes': metadata.get('file_size_bytes'),
        'audio_gcs_path': audio_gcs_path,
        'thumbnail_gcs_path': thumbnail_gcs_path,
    }
    
    # Execute insert with transaction management
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Use parameterized query to prevent SQL injection
                insert_query = """
                    INSERT INTO audio_tracks (
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path
                    ) VALUES (
                        %(id)s, %(status)s, %(artist)s, %(title)s, %(album)s,
                        %(genre)s, %(year)s, %(duration_seconds)s, %(channels)s,
                        %(sample_rate)s, %(bitrate)s, %(format)s, %(file_size_bytes)s,
                        %(audio_gcs_path)s, %(thumbnail_gcs_path)s
                    )
                    RETURNING 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at
                """
                
                cur.execute(insert_query, insert_data)
                result = cur.fetchone()
                
                # Commit transaction
                conn.commit()
                
                logger.info(f"Successfully saved audio metadata for track: {track_id}")
                
                # Convert result to regular dict and ensure proper types
                return dict(result)
    
    except IntegrityError as e:
        # Handle duplicate key or constraint violations
        logger.error(f"Integrity error saving metadata for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to save metadata: constraint violation - {str(e)}"
        )
    
    except DatabaseError as e:
        # Handle general database errors
        logger.error(f"Database error saving metadata for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to save metadata: database error - {str(e)}"
        )
    
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error saving metadata for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to save metadata: {str(e)}"
        )


def save_audio_metadata_batch(
    metadata_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Save multiple audio metadata records in a single transaction.
    
    Provides atomic batch insertion with rollback on any failure.
    
    Args:
        metadata_list: List of dictionaries, each containing:
            - metadata: Dict with audio metadata fields
            - audio_gcs_path: GCS path to audio file
            - thumbnail_gcs_path: Optional GCS path to thumbnail
            - track_id: Optional UUID for the track
    
    Returns:
        Dictionary with:
            - success: bool
            - inserted_count: int
            - track_ids: List[str] of inserted track IDs
            - errors: List of error messages (if any)
    
    Example:
        >>> records = [
        ...     {
        ...         'metadata': {'title': 'Song 1', 'format': 'MP3'},
        ...         'audio_gcs_path': 'gs://bucket/song1.mp3'
        ...     },
        ...     {
        ...         'metadata': {'title': 'Song 2', 'format': 'FLAC'},
        ...         'audio_gcs_path': 'gs://bucket/song2.flac'
        ...     }
        ... ]
        >>> result = save_audio_metadata_batch(records)
    """
    if not metadata_list:
        return {
            'success': True,
            'inserted_count': 0,
            'track_ids': [],
            'errors': []
        }
    
    track_ids = []
    errors = []
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                for idx, record in enumerate(metadata_list):
                    try:
                        metadata = record.get('metadata', {})
                        audio_gcs_path = record.get('audio_gcs_path')
                        thumbnail_gcs_path = record.get('thumbnail_gcs_path')
                        track_id = record.get('track_id')
                        
                        # Validate and insert
                        result = save_audio_metadata(
                            metadata=metadata,
                            audio_gcs_path=audio_gcs_path,
                            thumbnail_gcs_path=thumbnail_gcs_path,
                            track_id=track_id
                        )
                        
                        track_ids.append(result['id'])
                    
                    except Exception as e:
                        error_msg = f"Record {idx}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"Batch insert error for record {idx}: {e}")
                        # Rollback entire batch on any error
                        conn.rollback()
                        raise
                
                # Commit entire batch
                conn.commit()
                
                logger.info(f"Successfully saved batch of {len(track_ids)} audio metadata records")
        
        return {
            'success': True,
            'inserted_count': len(track_ids),
            'track_ids': track_ids,
            'errors': []
        }
    
    except Exception as e:
        logger.error(f"Batch metadata save failed: {e}")
        return {
            'success': False,
            'inserted_count': 0,
            'track_ids': track_ids,
            'errors': errors or [str(e)]
        }


# ============================================================================
# Placeholder sections for remaining operations
# ============================================================================
# These will be implemented in subsequent subtasks

# Retrieve Metadata Operations (Subtask 6.2)
# - get_audio_metadata_by_id()
# - get_audio_metadata_by_ids()

# Full-Text Search Operations (Subtask 6.3)
# - search_audio_tracks()
# - search_audio_tracks_advanced()

# Status Update Operations (Subtask 6.4)
# - update_processing_status()
# - update_processing_status_batch()

# Error and Transaction Management (Subtask 6.5)
# - Already implemented in save operations above
# - Additional utilities as needed

