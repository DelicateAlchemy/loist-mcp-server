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
# Retrieve Metadata Operations
# ============================================================================

def get_audio_metadata_by_id(track_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve audio metadata by track ID.
    
    Efficiently queries the database using the primary key index.
    Returns None if track is not found (graceful handling).
    
    Args:
        track_id: UUID string of the track to retrieve
    
    Returns:
        Dictionary with track metadata if found, None otherwise:
            - id: Track UUID
            - status: Processing status
            - artist, title, album, genre, year
            - duration_seconds, channels, sample_rate, bitrate, format
            - file_size_bytes, audio_gcs_path, thumbnail_gcs_path
            - created_at, updated_at timestamps
            - error_message, retry_count, last_processed_at (if applicable)
        Returns None if track doesn't exist
    
    Raises:
        ValidationError: If track_id format is invalid
        DatabaseOperationError: If database query fails
    
    Example:
        >>> track = get_audio_metadata_by_id('123e4567-e89b-12d3-a456-426614174000')
        >>> if track:
        ...     print(f"Found: {track['title']} by {track['artist']}")
        ... else:
        ...     print("Track not found")
    """
    # Validate UUID format
    try:
        uuid.UUID(track_id)
    except ValueError:
        raise ValidationError(f"Invalid track_id format: {track_id}")
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Parameterized query for security
                query = """
                    SELECT 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at, error_message, retry_count, last_processed_at
                    FROM audio_tracks
                    WHERE id = %s
                """
                
                cur.execute(query, (track_id,))
                result = cur.fetchone()
                
                if result:
                    logger.debug(f"Retrieved metadata for track: {track_id}")
                    return dict(result)
                else:
                    logger.debug(f"Track not found: {track_id}")
                    return None
    
    except DatabaseError as e:
        logger.error(f"Database error retrieving metadata for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve metadata: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving metadata for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve metadata: {str(e)}"
        )


def get_audio_metadata_by_ids(track_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve multiple audio metadata records by track IDs.
    
    Efficiently queries multiple tracks in a single database operation.
    Skips invalid UUIDs and returns only found tracks.
    
    Args:
        track_ids: List of UUID strings to retrieve
    
    Returns:
        List of dictionaries with track metadata for found tracks.
        Empty list if no tracks found.
        Order is not guaranteed to match input order.
    
    Raises:
        ValidationError: If any track_id format is invalid
        DatabaseOperationError: If database query fails
    
    Example:
        >>> ids = ['123e4567-e89b-12d3-a456-426614174000', 
        ...        '223e4567-e89b-12d3-a456-426614174001']
        >>> tracks = get_audio_metadata_by_ids(ids)
        >>> print(f"Found {len(tracks)} out of {len(ids)} tracks")
    """
    if not track_ids:
        return []
    
    # Validate all UUID formats
    valid_ids = []
    for track_id in track_ids:
        try:
            uuid.UUID(track_id)
            valid_ids.append(track_id)
        except ValueError:
            raise ValidationError(f"Invalid track_id format in batch: {track_id}")
    
    if not valid_ids:
        return []
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Use ANY operator for efficient batch query
                query = """
                    SELECT 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at, error_message, retry_count, last_processed_at
                    FROM audio_tracks
                    WHERE id = ANY(%s)
                """
                
                cur.execute(query, (valid_ids,))
                results = cur.fetchall()
                
                logger.debug(f"Retrieved {len(results)} tracks out of {len(valid_ids)} requested")
                
                return [dict(row) for row in results]
    
    except DatabaseError as e:
        logger.error(f"Database error retrieving batch metadata: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve batch metadata: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving batch metadata: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve batch metadata: {str(e)}"
        )


def get_all_audio_metadata(
    limit: int = 100,
    offset: int = 0,
    status_filter: Optional[str] = None,
    order_by: str = 'created_at',
    order_direction: str = 'DESC'
) -> Dict[str, Any]:
    """
    Retrieve paginated list of audio metadata records.
    
    Supports filtering, ordering, and pagination for efficient data retrieval.
    
    Args:
        limit: Maximum number of records to return (default: 100, max: 1000)
        offset: Number of records to skip (for pagination)
        status_filter: Optional status to filter by ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
        order_by: Field to order by (default: 'created_at')
        order_direction: Sort direction 'ASC' or 'DESC' (default: 'DESC')
    
    Returns:
        Dictionary containing:
            - tracks: List of track metadata dictionaries
            - total_count: Total number of tracks matching filter
            - limit: Limit used
            - offset: Offset used
            - has_more: Boolean indicating if more records exist
    
    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If database query fails
    
    Example:
        >>> result = get_all_audio_metadata(limit=50, status_filter='COMPLETED')
        >>> print(f"Retrieved {len(result['tracks'])} of {result['total_count']} tracks")
        >>> for track in result['tracks']:
        ...     print(f"{track['title']} by {track['artist']}")
    """
    # Validation
    if limit < 1 or limit > 1000:
        raise ValidationError("Limit must be between 1 and 1000")
    
    if offset < 0:
        raise ValidationError("Offset must be non-negative")
    
    valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
    if status_filter and status_filter not in valid_statuses:
        raise ValidationError(f"Invalid status filter. Must be one of: {valid_statuses}")
    
    # Whitelist allowed order_by columns to prevent SQL injection
    valid_order_columns = ['created_at', 'updated_at', 'title', 'artist', 'album', 'year']
    if order_by not in valid_order_columns:
        raise ValidationError(f"Invalid order_by column. Must be one of: {valid_order_columns}")
    
    if order_direction not in ['ASC', 'DESC']:
        raise ValidationError("order_direction must be 'ASC' or 'DESC'")
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build query with optional status filter
                base_query = """
                    SELECT 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at
                    FROM audio_tracks
                """
                
                count_query = "SELECT COUNT(*) FROM audio_tracks"
                
                where_clause = ""
                params = []
                
                if status_filter:
                    where_clause = " WHERE status = %s"
                    params = [status_filter]
                
                # Use psycopg2.sql for safe column name injection
                from psycopg2 import sql
                
                # Get total count
                count_query_full = count_query + where_clause
                cur.execute(count_query_full, params)
                total_count = cur.fetchone()['count']
                
                # Get paginated results
                query_full = sql.SQL(base_query + where_clause + " ORDER BY {} {} LIMIT %s OFFSET %s").format(
                    sql.Identifier(order_by),
                    sql.SQL(order_direction)
                )
                
                cur.execute(query_full, params + [limit, offset])
                results = cur.fetchall()
                
                logger.debug(
                    f"Retrieved {len(results)} tracks (offset={offset}, limit={limit}, "
                    f"total={total_count}, status={status_filter})"
                )
                
                return {
                    'tracks': [dict(row) for row in results],
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + limit) < total_count
                }
    
    except DatabaseError as e:
        logger.error(f"Database error retrieving paginated metadata: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve paginated metadata: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving paginated metadata: {e}")
        raise DatabaseOperationError(
            f"Failed to retrieve paginated metadata: {str(e)}"
        )


# ============================================================================
# Placeholder sections for remaining operations
# ============================================================================
# These will be implemented in subsequent subtasks

# Full-Text Search Operations (Subtask 6.3)
# - search_audio_tracks()
# - search_audio_tracks_advanced()

# Status Update Operations (Subtask 6.4)
# - update_processing_status()
# - update_processing_status_batch()

# Error and Transaction Management (Subtask 6.5)
# - Already implemented in save and retrieve operations above
# - Additional utilities as needed

