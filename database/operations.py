"""
Database operations for audio metadata management.

Provides functions for CRUD operations on audio tracks with full-text search,
transaction management, and comprehensive error handling.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import pytz
import psycopg2.extras
from psycopg2 import DatabaseError, IntegrityError

from .pool import get_connection
from src.exceptions import (
    StorageError,
    ValidationError,
    DatabaseOperationError,
    ResourceNotFoundError,
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
        # XMP fields
        'composer': metadata.get('composer'),
        'publisher': metadata.get('publisher'),
        'record_label': metadata.get('record_label'),
        'isrc': metadata.get('isrc'),
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
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc
                    ) VALUES (
                        %(id)s, %(status)s, %(artist)s, %(title)s, %(album)s,
                        %(genre)s, %(year)s, %(duration_seconds)s, %(channels)s,
                        %(sample_rate)s, %(bitrate)s, %(format)s, %(file_size_bytes)s,
                        %(audio_gcs_path)s, %(thumbnail_gcs_path)s,
                        %(composer)s, %(publisher)s, %(record_label)s, %(isrc)s
                    )
                    RETURNING
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc,
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


def _extract_year(year_value: Any) -> Optional[int]:
    """Extract and validate year value."""
    if year_value is not None:
        try:
            year_int = int(year_value)
            if year_int < 1800 or year_int > 2100:
                raise ValidationError(f"Year must be between 1800 and 2100, got: {year_int}")
            return year_int
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid year value: {year_value}")
    return None


def _extract_channels(channels_value: Any) -> Optional[int]:
    """Extract and validate channels value."""
    if channels_value is not None:
        try:
            channels_int = int(channels_value)
            if channels_int < 1 or channels_int > 16:
                raise ValidationError(f"Channels must be between 1 and 16, got: {channels_int}")
            return channels_int
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid channels value: {channels_value}")
    return None


def _validate_audio_metadata(
    metadata: Dict[str, Any],
    audio_gcs_path: Optional[str],
    thumbnail_gcs_path: Optional[str] = None,
    track_id: Optional[str] = None
) -> None:
    """
    Validate audio metadata and paths.

    Args:
        metadata: Audio metadata dictionary
        audio_gcs_path: GCS path to audio file
        thumbnail_gcs_path: Optional GCS path to thumbnail
        track_id: Optional track UUID

    Raises:
        ValidationError: If validation fails
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

    # Validate track_id if provided
    if track_id is not None:
        try:
            uuid.UUID(track_id)
        except ValueError:
            raise ValidationError(f"Invalid track_id format: {track_id}")


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

    # Validate all records first and prepare data
    validated_records = []
    for idx, record in enumerate(metadata_list):
        try:
            metadata = record.get('metadata', {})
            audio_gcs_path = record.get('audio_gcs_path')
            thumbnail_gcs_path = record.get('thumbnail_gcs_path')
            track_id = record.get('track_id')

            # Use the same validation logic as single insert
            _validate_audio_metadata(
                metadata=metadata,
                audio_gcs_path=audio_gcs_path,
                thumbnail_gcs_path=thumbnail_gcs_path,
                track_id=track_id
            )

            # Generate track ID if not provided
            if track_id is None:
                track_id = str(uuid.uuid4())

            # Extract validated metadata fields
            year = _extract_year(metadata.get('year'))
            channels = _extract_channels(metadata.get('channels'))

            validated_records.append({
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
            })

            track_ids.append(track_id)

        except Exception as e:
            error_msg = f"Record {idx}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Validation error for record {idx}: {e}")
            raise ValidationError(f"Batch validation failed: {error_msg}")

    # Perform optimized multi-row insert
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build multi-row INSERT query
                insert_query = """
                    INSERT INTO audio_tracks (
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc
                    ) VALUES
                """

                # Build VALUES clause for all records
                values_clauses = []
                params = []

                for record in validated_records:
                    values_clauses.append("""
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """)
                    params.extend([
                        record['id'], record['status'], record['artist'], record['title'],
                        record['album'], record['genre'], record['year'], record['duration_seconds'],
                        record['channels'], record['sample_rate'], record['bitrate'],
                        record['format'], record['file_size_bytes'], record['audio_gcs_path'],
                        record['thumbnail_gcs_path'], record['composer'], record['publisher'],
                        record['record_label'], record['isrc']
                    ])

                insert_query += ", ".join(values_clauses)
                insert_query += """
                    RETURNING id
                """

                # Execute the multi-row insert
                cur.execute(insert_query, params)
                results = cur.fetchall()

                # Verify all records were inserted
                inserted_count = len(results)
                if inserted_count != len(validated_records):
                    raise DatabaseOperationError(
                        f"Batch insert incomplete: expected {len(validated_records)}, got {inserted_count}"
                    )

                # Commit the transaction
                conn.commit()

                logger.info(f"Successfully saved batch of {inserted_count} audio metadata records (optimized multi-row insert)")

        return {
            'success': True,
            'inserted_count': inserted_count,
            'track_ids': track_ids,
            'errors': []
        }

    except Exception as e:
        logger.error(f"Batch metadata save failed: {e}")
        return {
            'success': False,
            'inserted_count': 0,
            'track_ids': [],
            'errors': errors or [str(e)]
        }


# ============================================================================
# Time Filtering Helpers
# ============================================================================

def get_time_period_range(time_period: str, timezone: str = "UTC") -> tuple[datetime, datetime]:
    """
    Convert a time period string to a date range tuple (start_date, end_date).

    Args:
        time_period: Time period string ('today', 'yesterday', 'this_week', etc.)
        timezone: IANA timezone name for date interpretation

    Returns:
        Tuple of (start_datetime, end_datetime) in UTC

    Raises:
        ValueError: If time_period is invalid or timezone is not recognized
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown timezone: {timezone}")

    # Get current time in the specified timezone
    now = datetime.now(tz)

    if time_period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif time_period == "yesterday":
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
    elif time_period == "this_week":
        # Monday of current week
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif time_period == "last_week":
        # Monday of last week
        last_week_start = now - timedelta(days=now.weekday() + 7)
        start = last_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif time_period == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    elif time_period == "last_month":
        if now.month == 1:
            start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif time_period == "this_year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1)
    elif time_period == "last_year":
        start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(year=now.year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unknown time period: {time_period}")

    # Convert to UTC for database storage
    start_utc = start.astimezone(pytz.UTC)
    end_utc = end.astimezone(pytz.UTC)

    return start_utc, end_utc


def parse_custom_date(date_str: str, timezone: str = "UTC") -> datetime:
    """
    Parse a custom date string into a datetime object.

    Args:
        date_str: Date string in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        timezone: IANA timezone name

    Returns:
        Datetime object in UTC

    Raises:
        ValueError: If date format is invalid
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown timezone: {timezone}")

    try:
        # Try parsing with time
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            # Assume it's in the specified timezone
            dt = tz.localize(dt)
        return dt.astimezone(pytz.UTC)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")


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
# Full-Text Search Operations
# ============================================================================

def search_audio_tracks(
    query: str,
    limit: int = 20,
    offset: int = 0,
    min_rank: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Search audio tracks using PostgreSQL full-text search.
    
    Uses the search_vector column (auto-populated via trigger) with
    tsvector/tsquery for fast, indexed searching across metadata fields.
    Results are ranked by relevance using ts_rank.
    
    Args:
        query: Search query string (e.g., "queen bohemian rhapsody")
            - Multiple words treated as AND search
            - Use operators: & (AND), | (OR), ! (NOT), <-> (phrase)
        limit: Maximum number of results (default: 20, max: 100)
        offset: Number of results to skip for pagination
        min_rank: Minimum relevance score (0.0-1.0, default: 0.0)
    
    Returns:
        List of track dictionaries ordered by relevance (highest first):
            - All track metadata fields
            - rank: Relevance score (float)
    
    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails
    
    Example:
        >>> results = search_audio_tracks("queen bohemian")
        >>> for track in results:
        ...     print(f"{track['title']} by {track['artist']} (score: {track['rank']:.3f})")
        
        >>> # Phrase search
        >>> results = search_audio_tracks("'night' & 'opera'")
        
        >>> # OR search
        >>> results = search_audio_tracks("queen | beatles")
    """
    # Validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")
    
    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")
    
    if offset < 0:
        raise ValidationError("Offset must be non-negative")
    
    if min_rank < 0.0 or min_rank > 1.0:
        raise ValidationError("min_rank must be between 0.0 and 1.0")
    
    # Sanitize and prepare query
    # Convert spaces to AND operator for multi-word queries
    query_sanitized = query.strip()
    
    # If query doesn't contain operators, treat words as AND
    if not any(op in query_sanitized for op in ['&', '|', '!', '<->']):
        # Split on whitespace and join with &
        words = query_sanitized.split()
        tsquery_string = ' & '.join(words)
    else:
        tsquery_string = query_sanitized
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Full-text search with ranking
                search_query = """
                    SELECT 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at,
                        ts_rank(search_vector, to_tsquery('english', %s)) as rank
                    FROM audio_tracks
                    WHERE search_vector @@ to_tsquery('english', %s)
                        AND ts_rank(search_vector, to_tsquery('english', %s)) >= %s
                    ORDER BY rank DESC, created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cur.execute(
                    search_query,
                    (tsquery_string, tsquery_string, tsquery_string, min_rank, limit, offset)
                )
                results = cur.fetchall()
                
                logger.info(
                    f"Full-text search for '{query}' returned {len(results)} results "
                    f"(limit={limit}, offset={offset}, min_rank={min_rank})"
                )
                
                return [dict(row) for row in results]
    
    except DatabaseError as e:
        # Handle specific tsquery syntax errors
        if "syntax error" in str(e).lower():
            raise ValidationError(f"Invalid search query syntax: {query}")
        
        logger.error(f"Database error during search: {e}")
        raise DatabaseOperationError(
            f"Search operation failed: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}")
        raise DatabaseOperationError(
            f"Search operation failed: {str(e)}"
        )


def search_audio_tracks_advanced(
    query: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    format_filter: Optional[str] = None,
    min_rank: float = 0.0,
    rank_normalization: int = 1
) -> Dict[str, Any]:
    """
    Advanced full-text search with additional filters and ranking options.
    
    Combines full-text search with structured filters for precise results.
    Supports rank normalization methods for better relevance scoring.
    
    Args:
        query: Search query string
        limit: Maximum results (1-100, default: 20)
        offset: Pagination offset
        status_filter: Filter by status ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
        year_min: Minimum year (inclusive)
        year_max: Maximum year (inclusive)
        format_filter: Filter by audio format (e.g., 'MP3', 'FLAC')
        min_rank: Minimum relevance score (0.0-1.0)
        rank_normalization: ts_rank normalization method:
            - 0: Default (no normalization)
            - 1: Divides by 1 + log(document length)
            - 2: Divides by document length
            - 4: Divides by mean harmonic distance
            - 8: Divides by unique word count
            - 16: Divides by 1 + log(unique word count)
            - 32: Divides by rank + 1
    
    Returns:
        Dictionary containing:
            - tracks: List of matching tracks with relevance scores
            - total_matches: Approximate total matching tracks
            - query: Original query string
            - filters: Applied filters
            - limit/offset: Pagination info
    
    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails
    
    Example:
        >>> result = search_audio_tracks_advanced(
        ...     query="rock",
        ...     status_filter="COMPLETED",
        ...     year_min=1970,
        ...     year_max=1989,
        ...     format_filter="FLAC",
        ...     min_rank=0.1
        ... )
        >>> print(f"Found {result['total_matches']} matching tracks")
        >>> for track in result['tracks']:
        ...     print(f"{track['year']}: {track['title']} ({track['rank']:.3f})")
    """
    # Reuse basic validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")
    
    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")
    
    if offset < 0:
        raise ValidationError("Offset must be non-negative")
    
    if min_rank < 0.0 or min_rank > 1.0:
        raise ValidationError("min_rank must be between 0.0 and 1.0")
    
    # Validate additional filters
    valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
    if status_filter and status_filter not in valid_statuses:
        raise ValidationError(f"Invalid status filter. Must be one of: {valid_statuses}")
    
    if year_min is not None and (year_min < 1800 or year_min > 2100):
        raise ValidationError("year_min must be between 1800 and 2100")
    
    if year_max is not None and (year_max < 1800 or year_max > 2100):
        raise ValidationError("year_max must be between 1800 and 2100")
    
    if year_min and year_max and year_min > year_max:
        raise ValidationError("year_min cannot be greater than year_max")
    
    valid_normalizations = [0, 1, 2, 4, 8, 16, 32]
    if rank_normalization not in valid_normalizations:
        raise ValidationError(
            f"Invalid rank_normalization. Must be one of: {valid_normalizations}"
        )
    
    # Prepare tsquery
    query_sanitized = query.strip()
    if not any(op in query_sanitized for op in ['&', '|', '!', '<->']):
        words = query_sanitized.split()
        tsquery_string = ' & '.join(words)
    else:
        tsquery_string = query_sanitized
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build dynamic WHERE clause
                where_conditions = ["search_vector @@ to_tsquery('english', %s)"]
                params = [tsquery_string]
                
                # Add rank filter
                where_conditions.append(f"ts_rank(search_vector, to_tsquery('english', %s), {rank_normalization}) >= %s")
                params.extend([tsquery_string, min_rank])
                
                # Add optional filters
                if status_filter:
                    where_conditions.append("status = %s")
                    params.append(status_filter)
                
                if year_min is not None:
                    where_conditions.append("year >= %s")
                    params.append(year_min)
                
                if year_max is not None:
                    where_conditions.append("year <= %s")
                    params.append(year_max)
                
                if format_filter:
                    where_conditions.append("UPPER(format) = UPPER(%s)")
                    params.append(format_filter)
                
                where_clause = " AND ".join(where_conditions)
                
                # Count total matches
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM audio_tracks
                    WHERE {where_clause}
                """
                
                cur.execute(count_query, params)
                total_matches = cur.fetchone()['total']
                
                # Get ranked results
                search_query = f"""
                    SELECT 
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at,
                        ts_rank(search_vector, to_tsquery('english', %s), {rank_normalization}) as rank
                    FROM audio_tracks
                    WHERE {where_clause}
                    ORDER BY rank DESC, created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                # Add tsquery param for rank calculation in SELECT, plus limit/offset
                search_params = [tsquery_string] + params + [limit, offset]
                
                cur.execute(search_query, search_params)
                results = cur.fetchall()
                
                logger.info(
                    f"Advanced search for '{query}' returned {len(results)}/{total_matches} results "
                    f"(filters: status={status_filter}, year={year_min}-{year_max}, "
                    f"format={format_filter}, normalization={rank_normalization})"
                )
                
                return {
                    'tracks': [dict(row) for row in results],
                    'total_matches': total_matches,
                    'query': query,
                    'filters': {
                        'status': status_filter,
                        'year_min': year_min,
                        'year_max': year_max,
                        'format': format_filter,
                        'min_rank': min_rank,
                        'rank_normalization': rank_normalization,
                    },
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + len(results)) < total_matches
                }
    
    except DatabaseError as e:
        if "syntax error" in str(e).lower():
            raise ValidationError(f"Invalid search query syntax: {query}")
        
        logger.error(f"Database error during advanced search: {e}")
        raise DatabaseOperationError(
            f"Advanced search operation failed: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during advanced search: {e}")
        raise DatabaseOperationError(
            f"Advanced search operation failed: {str(e)}"
        )


def search_audio_tracks_cursor(
    query: str,
    limit: int = 20,
    cursor_data: Optional[Tuple[float, str, str]] = None,
    status_filter: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    format_filter: Optional[str] = None,
    min_rank: float = 0.0,
    rank_normalization: int = 1
) -> Dict[str, Any]:
    """
    Cursor-based full-text search with keyset pagination.

    Uses cursor-based pagination for consistent performance and stable results.
    Cursor encodes (score, created_at, id) for stable ordering.

    Args:
        query: Search query string
        limit: Maximum results (1-100, default: 20)
        cursor_data: Tuple of (score, created_at, id) from previous page, or None for first page
        status_filter: Filter by status ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
        year_min: Minimum year (inclusive)
        year_max: Maximum year (inclusive)
        format_filter: Filter by audio format (e.g., 'MP3', 'FLAC')
        min_rank: Minimum relevance score (0.0-1.0)
        rank_normalization: ts_rank normalization method (0, 1, 2, 4, 8, 16, 32)

    Returns:
        Dictionary containing:
            - tracks: List of matching tracks with relevance scores
            - query: Original query string
            - filters: Applied filters
            - limit: Requested limit

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails

    Example:
        >>> # First page
        >>> result = search_audio_tracks_cursor(query="rock", limit=20)
        >>>
        >>> # Next page using cursor from last result
        >>> cursor = encode_cursor(result['tracks'][-1]['rank'],
        ...                       result['tracks'][-1]['created_at'],
        ...                       result['tracks'][-1]['id'])
        >>> next_result = search_audio_tracks_cursor(query="rock", limit=20, cursor_data=decode_cursor(cursor))
    """
    # Reuse basic validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if min_rank < 0.0 or min_rank > 1.0:
        raise ValidationError("min_rank must be between 0.0 and 1.0")

    # Validate additional filters
    valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
    if status_filter and status_filter not in valid_statuses:
        raise ValidationError(f"Invalid status filter. Must be one of: {valid_statuses}")

    if year_min is not None and (year_min < 1800 or year_min > 2100):
        raise ValidationError("year_min must be between 1800 and 2100")

    if year_max is not None and (year_max < 1800 or year_max > 2100):
        raise ValidationError("year_max must be between 1800 and 2100")

    if year_min and year_max and year_min > year_max:
        raise ValidationError("year_min cannot be greater than year_max")

    valid_normalizations = [0, 1, 2, 4, 8, 16, 32]
    if rank_normalization not in valid_normalizations:
        raise ValidationError(
            f"Invalid rank_normalization. Must be one of: {valid_normalizations}"
        )

    # Prepare tsquery
    query_sanitized = query.strip()
    if not any(op in query_sanitized for op in ['&', '|', '!', '<->']):
        words = query_sanitized.split()
        tsquery_string = ' & '.join(words)
    else:
        tsquery_string = query_sanitized

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build WHERE clause
                where_conditions = ["search_vector @@ to_tsquery('english', %s)"]
                params = [tsquery_string]

                # Add rank filter
                where_conditions.append(f"ts_rank(search_vector, to_tsquery('english', %s), {rank_normalization}) >= %s")
                params.extend([tsquery_string, min_rank])

                # Add cursor conditions for keyset pagination
                if cursor_data:
                    cursor_score, cursor_created_at, cursor_id = cursor_data
                    # Use tuple comparison for stable ordering: (score DESC, created_at DESC, id DESC)
                    where_conditions.append("""
                        (ts_rank(search_vector, to_tsquery('english', %s), %s) < %s OR
                         (ts_rank(search_vector, to_tsquery('english', %s), %s) = %s AND created_at < %s) OR
                         (ts_rank(search_vector, to_tsquery('english', %s), %s) = %s AND created_at = %s AND id > %s))
                    """)
                    params.extend([
                        tsquery_string, rank_normalization, cursor_score,
                        tsquery_string, rank_normalization, cursor_score, cursor_created_at,
                        tsquery_string, rank_normalization, cursor_score, cursor_created_at, cursor_id
                    ])

                # Add optional filters
                if status_filter:
                    where_conditions.append("status = %s")
                    params.append(status_filter)

                if year_min is not None:
                    where_conditions.append("year >= %s")
                    params.append(year_min)

                if year_max is not None:
                    where_conditions.append("year <= %s")
                    params.append(year_max)

                if format_filter:
                    where_conditions.append("UPPER(format) = UPPER(%s)")
                    params.append(format_filter)

                where_clause = " AND ".join(where_conditions)

                # Get ranked results with stable ordering
                search_query = f"""
                    SELECT
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        created_at, updated_at,
                        ts_rank(search_vector, to_tsquery('english', %s), %s) as rank
                    FROM audio_tracks
                    WHERE {where_clause}
                    ORDER BY rank DESC, created_at DESC, id DESC
                    LIMIT %s
                """

                # Add tsquery params for rank calculation, plus limit
                search_params = [tsquery_string, rank_normalization] + params + [limit]

                cur.execute(search_query, search_params)
                results = cur.fetchall()

                logger.info(
                    f"Cursor search for '{query}' returned {len(results)} results "
                    f"(limit={limit}, cursor={'present' if cursor_data else 'none'})"
                )

                return {
                    'tracks': [dict(row) for row in results],
                    'query': query,
                    'filters': {
                        'status': status_filter,
                        'year_min': year_min,
                        'year_max': year_max,
                        'format': format_filter,
                        'min_rank': min_rank,
                        'rank_normalization': rank_normalization,
                        'cursor_data': cursor_data,
                    },
                    'limit': limit,
                }

    except DatabaseError as e:
        if "syntax error" in str(e).lower():
            raise ValidationError(f"Invalid search query syntax: {query}")

        logger.error(f"Database error during cursor search: {e}")
        raise DatabaseOperationError(
            f"Cursor search operation failed: database error - {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error during cursor search: {e}")
        raise DatabaseOperationError(
            f"Cursor search operation failed: {str(e)}"
        )


# ============================================================================
# Status Update Operations
# ============================================================================

def update_processing_status(
    track_id: str,
    status: str,
    error_message: Optional[str] = None,
    increment_retry: bool = False
) -> Dict[str, Any]:
    """
    Update the processing status of an audio track.
    
    Atomically updates status, timestamps, and related fields.
    Supports retry counting and error message logging for failed processing.
    
    Args:
        track_id: UUID of the track to update
        status: New status value ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
        error_message: Optional error description (typically used with 'FAILED' status)
        increment_retry: If True, increments retry_count (typically used with 'FAILED')
    
    Returns:
        Dictionary with updated track information:
            - id: Track UUID
            - status: New status
            - retry_count: Current retry count
            - last_processed_at: Timestamp of this update
            - updated_at: Timestamp of last modification
    
    Raises:
        ValidationError: If track_id or status is invalid
        ResourceNotFoundError: If track doesn't exist
        DatabaseOperationError: If update fails
    
    Example:
        >>> # Mark as processing
        >>> update_processing_status('123e4567...', 'PROCESSING')
        
        >>> # Mark as failed with error
        >>> update_processing_status(
        ...     '123e4567...',
        ...     'FAILED',
        ...     error_message='Invalid audio format',
        ...     increment_retry=True
        ... )
        
        >>> # Mark as completed
        >>> update_processing_status('123e4567...', 'COMPLETED')
    """
    # Validate UUID format
    try:
        uuid.UUID(track_id)
    except ValueError:
        raise ValidationError(f"Invalid track_id format: {track_id}")
    
    # Validate status
    valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
    if status not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {valid_statuses}"
        )
    
    # Validate error_message length (PostgreSQL TEXT type has large limit but be reasonable)
    if error_message and len(error_message) > 10000:
        error_message = error_message[:10000]  # Truncate
        logger.warning(f"Error message truncated to 10000 characters for track {track_id}")
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build update query
                if increment_retry:
                    update_query = """
                        UPDATE audio_tracks
                        SET 
                            status = %s,
                            error_message = %s,
                            retry_count = retry_count + 1,
                            last_processed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING 
                            id, status, retry_count, last_processed_at, updated_at
                    """
                    params = (status, error_message, track_id)
                else:
                    update_query = """
                        UPDATE audio_tracks
                        SET 
                            status = %s,
                            error_message = %s,
                            last_processed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING 
                            id, status, retry_count, last_processed_at, updated_at
                    """
                    params = (status, error_message, track_id)
                
                cur.execute(update_query, params)
                result = cur.fetchone()
                
                if not result:
                    # Track doesn't exist
                    raise ResourceNotFoundError(
                        f"Track not found: {track_id}",
                        details={'track_id': track_id}
                    )
                
                # Commit transaction
                conn.commit()
                
                logger.info(
                    f"Updated status for track {track_id}: {status} "
                    f"(retry_count={result['retry_count']})"
                )
                
                return dict(result)
    
    except ResourceNotFoundError:
        # Re-raise resource not found
        raise
    
    except DatabaseError as e:
        logger.error(f"Database error updating status for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update status: database error - {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error updating status for {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update status: {str(e)}"
        )


def update_processing_status_batch(
    updates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update processing status for multiple tracks in a single transaction.
    
    Provides atomic batch updates with rollback on any failure.
    All updates succeed together or all fail together.
    
    Args:
        updates: List of dictionaries, each containing:
            - track_id: str (required)
            - status: str (required)
            - error_message: str (optional)
            - increment_retry: bool (optional, default: False)
    
    Returns:
        Dictionary with:
            - success: bool
            - updated_count: int
            - track_ids: List[str] of updated track IDs
            - errors: List of error messages (if any)
    
    Example:
        >>> updates = [
        ...     {
        ...         'track_id': '123e4567...',
        ...         'status': 'COMPLETED'
        ...     },
        ...     {
        ...         'track_id': '223e4567...',
        ...         'status': 'FAILED',
        ...         'error_message': 'Timeout',
        ...         'increment_retry': True
        ...     }
        ... ]
        >>> result = update_processing_status_batch(updates)
        >>> print(f"Updated {result['updated_count']} tracks")
    """
    if not updates:
        return {
            'success': True,
            'updated_count': 0,
            'track_ids': [],
            'errors': []
        }
    
    track_ids = []
    errors = []
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                for idx, update in enumerate(updates):
                    try:
                        track_id = update.get('track_id')
                        status = update.get('status')
                        error_message = update.get('error_message')
                        increment_retry = update.get('increment_retry', False)
                        
                        if not track_id or not status:
                            error_msg = f"Update {idx}: Missing required fields (track_id and status)"
                            errors.append(error_msg)
                            raise ValidationError(error_msg)
                        
                        # Perform update
                        result = update_processing_status(
                            track_id=track_id,
                            status=status,
                            error_message=error_message,
                            increment_retry=increment_retry
                        )
                        
                        track_ids.append(result['id'])
                    
                    except Exception as e:
                        error_msg = f"Update {idx} ({update.get('track_id', 'unknown')}): {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"Batch status update error: {error_msg}")
                        # Rollback entire batch on any error
                        conn.rollback()
                        raise
                
                # Commit entire batch
                conn.commit()
                
                logger.info(f"Successfully updated status for batch of {len(track_ids)} tracks")
        
        return {
            'success': True,
            'updated_count': len(track_ids),
            'track_ids': track_ids,
            'errors': []
        }
    
    except Exception as e:
        logger.error(f"Batch status update failed: {e}")
        return {
            'success': False,
            'updated_count': 0,
            'track_ids': track_ids,
            'errors': errors or [str(e)]
        }


def mark_as_failed(
    track_id: str,
    error_message: str,
    increment_retry: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to mark a track as FAILED.
    
    Automatically increments retry count and logs error message.
    
    Args:
        track_id: UUID of the track
        error_message: Description of the failure
        increment_retry: Whether to increment retry counter (default: True)
    
    Returns:
        Updated track information
    
    Example:
        >>> mark_as_failed(
        ...     '123e4567...',
        ...     'Network timeout during download'
        ... )
    """
    return update_processing_status(
        track_id=track_id,
        status='FAILED',
        error_message=error_message,
        increment_retry=increment_retry
    )


def mark_as_completed(track_id: str) -> Dict[str, Any]:
    """
    Convenience function to mark a track as COMPLETED.
    
    Clears any previous error message.
    
    Args:
        track_id: UUID of the track
    
    Returns:
        Updated track information
    
    Example:
        >>> mark_as_completed('123e4567...')
    """
    return update_processing_status(
        track_id=track_id,
        status='COMPLETED',
        error_message=None,
        increment_retry=False
    )


def create_processing_record(track_id: str, status: str = 'PROCESSING') -> Dict[str, Any]:
    """
    Create a minimal processing record for tracking status.
    
    This function creates a database record with minimal required fields
    to track processing status. The full metadata will be saved later.
    
    Args:
        track_id: UUID of the track
        status: Initial status (default: 'PROCESSING')
    
    Returns:
        Created record information
    
    Raises:
        ValidationError: If track_id format is invalid
        DatabaseOperationError: If creation fails
    
    Example:
        >>> create_processing_record('123e4567...', 'PROCESSING')
    """
    # Validate UUID format
    try:
        uuid.UUID(track_id)
    except ValueError:
        raise ValidationError(f"Invalid track_id format: {track_id}")
    
    # Validate status
    valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
    if status not in valid_statuses:
        raise ValidationError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Create minimal record with required fields
                insert_query = """
                    INSERT INTO audio_tracks (
                        id, status, title, format, created_at, updated_at
                    ) VALUES (
                        %s, %s, 'Processing...', 'Unknown', NOW(), NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id, status, created_at, updated_at
                """
                
                cur.execute(insert_query, (track_id, status))
                result = cur.fetchone()
                
                # Commit transaction
                conn.commit()
                
                logger.info(f"Created/updated processing record for track: {track_id}")
                return dict(result)
    
    except DatabaseError as e:
        logger.error(f"Database error creating processing record for {track_id}: {e}")
        raise DatabaseOperationError(f"Failed to create processing record: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error creating processing record for {track_id}: {e}")
        raise DatabaseOperationError(f"Failed to create processing record: {str(e)}")


def mark_as_processing(track_id: str) -> Dict[str, Any]:
    """
    Convenience function to mark a track as PROCESSING.

    Typically called when beginning to process a track.

    Args:
        track_id: UUID of the track

    Returns:
        Updated track information

    Example:
        >>> mark_as_processing('123e4567...')
    """
    return update_processing_status(
        track_id=track_id,
        status='PROCESSING',
        error_message=None,
        increment_retry=False
    )


# ============================================================================
# Multi-Field Filtering Operations
# ============================================================================

def filter_audio_tracks_xmp(
    composer_filter: Optional[str] = None,
    publisher_filter: Optional[str] = None,
    record_label_filter: Optional[str] = None,
    isrc_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_by: str = 'created_at',
    order_direction: str = 'DESC'
) -> Dict[str, Any]:
    """
    Efficiently filter audio tracks by XMP metadata fields.

    Supports multi-field filtering with AND logic for professional music metadata.
    Uses composite indexes for optimal performance.

    Args:
        composer_filter: Exact or partial match for composer field
        publisher_filter: Exact or partial match for publisher field
        record_label_filter: Exact or partial match for record label field
        isrc_filter: Exact match for ISRC field (case-insensitive)
        limit: Maximum results (1-200, default: 50)
        offset: Pagination offset
        order_by: Sort field ('created_at', 'title', 'artist', 'composer', 'year')
        order_direction: 'ASC' or 'DESC'

    Returns:
        Dictionary with tracks and pagination info

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If query fails

    Example:
        >>> result = filter_audio_tracks_xmp(
        ...     composer_filter="ROB JAGER",
        ...     publisher_filter="EXTREME MUSIC",
        ...     limit=20
        ... )
        >>> print(f"Found {len(result['tracks'])} tracks")
    """
    # Validation
    if limit < 1 or limit > 200:
        raise ValidationError("Limit must be between 1 and 200")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    valid_order_fields = ['created_at', 'updated_at', 'title', 'artist', 'album', 'year', 'composer', 'publisher']
    if order_by not in valid_order_fields:
        raise ValidationError(f"Invalid order_by field. Must be one of: {valid_order_fields}")

    if order_direction not in ['ASC', 'DESC']:
        raise ValidationError("order_direction must be 'ASC' or 'DESC'")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build WHERE conditions
                where_conditions = ["status = 'COMPLETED'"]  # Only completed tracks
                params = []

                # Add XMP field filters
                if composer_filter:
                    where_conditions.append("composer ILIKE %s")
                    params.append(f"%{composer_filter}%")

                if publisher_filter:
                    where_conditions.append("publisher ILIKE %s")
                    params.append(f"%{publisher_filter}%")

                if record_label_filter:
                    where_conditions.append("record_label ILIKE %s")
                    params.append(f"%{record_label_filter}%")

                if isrc_filter:
                    where_conditions.append("UPPER(isrc) = UPPER(%s)")
                    params.append(isrc_filter)

                where_clause = " AND ".join(where_conditions)

                # Get total count
                count_query = f"SELECT COUNT(*) FROM audio_tracks WHERE {where_clause}"
                cur.execute(count_query, params)
                total_count = cur.fetchone()['count']

                # Get filtered results
                query = f"""
                    SELECT
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc,
                        created_at, updated_at
                    FROM audio_tracks
                    WHERE {where_clause}
                    ORDER BY {order_by} {order_direction}
                    LIMIT %s OFFSET %s
                """

                cur.execute(query, params + [limit, offset])
                results = cur.fetchall()

                logger.debug(
                    f"XMP filter query returned {len(results)} results "
                    f"(total: {total_count}, filters: composer={composer_filter}, "
                    f"publisher={publisher_filter}, label={record_label_filter}, isrc={isrc_filter})"
                )

                return {
                    'tracks': [dict(row) for row in results],
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + len(results)) < total_count,
                    'filters_applied': {
                        'composer': composer_filter,
                        'publisher': publisher_filter,
                        'record_label': record_label_filter,
                        'isrc': isrc_filter
                    }
                }

    except DatabaseError as e:
        logger.error(f"Database error in XMP filtering: {e}")
        raise DatabaseOperationError(f"XMP filtering failed: database error - {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in XMP filtering: {e}")
        raise DatabaseOperationError(f"XMP filtering failed: {str(e)}")


def filter_audio_tracks_combined(
    query: Optional[str] = None,
    composer_filter: Optional[str] = None,
    publisher_filter: Optional[str] = None,
    record_label_filter: Optional[str] = None,
    isrc_filter: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    format_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    min_rank: float = 0.0,
    time_period: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    timezone: str = "UTC"
) -> Dict[str, Any]:
    """
    Combined full-text search and structured filtering for optimal music discovery.

    Supports full-text search across all metadata combined with XMP field filters and time-based filtering.
    Uses both search vector and structured indexes for maximum performance.

    Args:
        query: Full-text search query (optional)
        composer_filter: Filter by composer
        publisher_filter: Filter by publisher
        record_label_filter: Filter by record label
        isrc_filter: Filter by ISRC
        year_min/year_max: Year range filters
        format_filter: Audio format filter
        limit: Maximum results (1-100, default: 50)
        offset: Pagination offset
        min_rank: Minimum relevance score for search (0.0-1.0)
        time_period: Relative time period filter ('today', 'yesterday', 'this_week', etc.)
        date_from: Custom start date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        date_to: Custom end date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        timezone: Timezone for date interpretation (IANA timezone name, default: UTC)

    Returns:
        Dictionary with filtered tracks, total count, and applied filters

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If query fails

    Example:
        >>> result = filter_audio_tracks_combined(
        ...     query="rock music",
        ...     composer_filter="JOHN DOE",
        ...     time_period="this_week",
        ...     timezone="America/New_York",
        ...     limit=25
        ... )
        >>> print(f"Found {result['total_count']} matching tracks")
    """
    # Validation
    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    if min_rank < 0.0 or min_rank > 1.0:
        raise ValidationError("min_rank must be between 0.0 and 1.0")

    if year_min is not None and (year_min < 1800 or year_min > 2100):
        raise ValidationError("year_min must be between 1800 and 2100")

    if year_max is not None and (year_max < 1800 or year_max > 2100):
        raise ValidationError("year_max must be between 1800 and 2100")

    if year_min and year_max and year_min > year_max:
        raise ValidationError("year_min cannot be greater than year_max")

    # Time filtering validation
    created_at_min = None
    created_at_max = None

    if time_period:
        try:
            created_at_min, created_at_max = get_time_period_range(time_period, timezone)
        except ValueError as e:
            raise ValidationError(str(e))

    if date_from:
        try:
            created_at_min = parse_custom_date(date_from, timezone)
        except ValueError as e:
            raise ValidationError(str(e))

    if date_to:
        try:
            created_at_max = parse_custom_date(date_to, timezone)
        except ValueError as e:
            raise ValidationError(str(e))

    if created_at_min and created_at_max and created_at_min > created_at_max:
        raise ValidationError("date_from cannot be greater than date_to")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build WHERE conditions
                where_conditions = ["status = 'COMPLETED'"]
                params = []

                # Full-text search condition
                tsquery_string = None
                if query and query.strip():
                    query_sanitized = query.strip()
                    if not any(op in query_sanitized for op in ['&', '|', '!', '<->']):
                        words = query_sanitized.split()
                        tsquery_string = ' & '.join(words)
                    else:
                        tsquery_string = query_sanitized

                    where_conditions.append("search_vector @@ to_tsquery('english', %s)")
                    params.append(tsquery_string)

                    where_conditions.append("ts_rank(search_vector, to_tsquery('english', %s)) >= %s")
                    params.extend([tsquery_string, min_rank])

                # XMP field filters
                if composer_filter:
                    where_conditions.append("composer ILIKE %s")
                    params.append(f"%{composer_filter}%")

                if publisher_filter:
                    where_conditions.append("publisher ILIKE %s")
                    params.append(f"%{publisher_filter}%")

                if record_label_filter:
                    where_conditions.append("record_label ILIKE %s")
                    params.append(f"%{record_label_filter}%")

                if isrc_filter:
                    where_conditions.append("UPPER(isrc) = UPPER(%s)")
                    params.append(isrc_filter)

                # Structured filters
                if year_min is not None:
                    where_conditions.append("year >= %s")
                    params.append(year_min)

                if year_max is not None:
                    where_conditions.append("year <= %s")
                    params.append(year_max)

                # Time-based filters
                if created_at_min is not None:
                    where_conditions.append("created_at >= %s")
                    params.append(created_at_min)

                if created_at_max is not None:
                    where_conditions.append("created_at < %s")
                    params.append(created_at_max)

                if format_filter:
                    where_conditions.append("UPPER(format) = UPPER(%s)")
                    params.append(format_filter)

                where_clause = " AND ".join(where_conditions)

                # Get total count
                count_query = f"SELECT COUNT(*) FROM audio_tracks WHERE {where_clause}"
                cur.execute(count_query, params)
                total_count = cur.fetchone()['count']

                # Get filtered results with ranking if search was used
                if tsquery_string:
                    query_sql = f"""
                        SELECT
                            id, status, artist, title, album, genre, year,
                            duration_seconds, channels, sample_rate, bitrate,
                            format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                            composer, publisher, record_label, isrc,
                            created_at, updated_at,
                            ts_rank(search_vector, to_tsquery('english', %s)) as rank
                        FROM audio_tracks
                        WHERE {where_clause}
                        ORDER BY rank DESC, created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    search_params = [tsquery_string] + params + [limit, offset]
                else:
                    query_sql = f"""
                        SELECT
                            id, status, artist, title, album, genre, year,
                            duration_seconds, channels, sample_rate, bitrate,
                            format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                            composer, publisher, record_label, isrc,
                            created_at, updated_at,
                            NULL as rank
                        FROM audio_tracks
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    search_params = params + [limit, offset]

                cur.execute(query_sql, search_params)
                results = cur.fetchall()

                logger.debug(
                    f"Combined filter query returned {len(results)} results "
                    f"(total: {total_count}, query='{query}', filters applied)"
                )

                return {
                    'tracks': [dict(row) for row in results],
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + len(results)) < total_count,
                    'query': query,
                    'filters_applied': {
                        'composer': composer_filter,
                        'publisher': publisher_filter,
                        'record_label': record_label_filter,
                        'isrc': isrc_filter,
                        'year_min': year_min,
                        'year_max': year_max,
                        'format': format_filter,
                        'min_rank': min_rank
                    }
                }

    except DatabaseError as e:
        logger.error(f"Database error in combined filtering: {e}")
        raise DatabaseOperationError(f"Combined filtering failed: database error - {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in combined filtering: {e}")
        raise DatabaseOperationError(f"Combined filtering failed: {str(e)}")


def get_xmp_field_facets(
    composer_limit: int = 20,
    publisher_limit: int = 20,
    record_label_limit: int = 20,
    min_count: int = 1
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get facet counts for XMP metadata fields to support faceted search.

    Returns the most common values for composer, publisher, and record_label
    fields with their frequencies, useful for building filter UIs.

    Args:
        composer_limit: Max composer facets to return
        publisher_limit: Max publisher facets to return
        record_label_limit: Max record label facets to return
        min_count: Minimum frequency for inclusion

    Returns:
        Dictionary with facet lists for each XMP field

    Raises:
        DatabaseOperationError: If query fails

    Example:
        >>> facets = get_xmp_field_facets(composer_limit=10, min_count=2)
        >>> for composer in facets['composers']:
        ...     print(f"{composer['name']}: {composer['count']} tracks")
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get composer facets
                composer_query = """
                    SELECT composer as name, COUNT(*) as count
                    FROM audio_tracks
                    WHERE status = 'COMPLETED' AND composer IS NOT NULL
                    GROUP BY composer
                    HAVING COUNT(*) >= %s
                    ORDER BY count DESC, name ASC
                    LIMIT %s
                """

                # Get publisher facets
                publisher_query = """
                    SELECT publisher as name, COUNT(*) as count
                    FROM audio_tracks
                    WHERE status = 'COMPLETED' AND publisher IS NOT NULL
                    GROUP BY publisher
                    HAVING COUNT(*) >= %s
                    ORDER BY count DESC, name ASC
                    LIMIT %s
                """

                # Get record label facets
                record_label_query = """
                    SELECT record_label as name, COUNT(*) as count
                    FROM audio_tracks
                    WHERE status = 'COMPLETED' AND record_label IS NOT NULL
                    GROUP BY record_label
                    HAVING COUNT(*) >= %s
                    ORDER BY count DESC, name ASC
                    LIMIT %s
                """

                # Execute all facet queries
                facets = {}

                cur.execute(composer_query, (min_count, composer_limit))
                facets['composers'] = [dict(row) for row in cur.fetchall()]

                cur.execute(publisher_query, (min_count, publisher_limit))
                facets['publishers'] = [dict(row) for row in cur.fetchall()]

                cur.execute(record_label_query, (min_count, record_label_limit))
                facets['record_labels'] = [dict(row) for row in cur.fetchall()]

                logger.debug(
                    f"Retrieved XMP facets: {len(facets['composers'])} composers, "
                    f"{len(facets['publishers'])} publishers, "
                    f"{len(facets['record_labels'])} record labels"
                )

                return facets

    except DatabaseError as e:
        logger.error(f"Database error retrieving XMP facets: {e}")
        raise DatabaseOperationError(f"XMP facets retrieval failed: database error - {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving XMP facets: {e}")
        raise DatabaseOperationError(f"XMP facets retrieval failed: {str(e)}")


def filter_audio_tracks_cursor_xmp(
    composer_filter: Optional[str] = None,
    publisher_filter: Optional[str] = None,
    record_label_filter: Optional[str] = None,
    isrc_filter: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    format_filter: Optional[str] = None,
    limit: int = 50,
    cursor_data: Optional[Tuple[str, str]] = None
) -> Dict[str, Any]:
    """
    Cursor-based pagination for XMP field filtering with stable ordering.

    Uses keyset pagination for consistent performance and stable results
    when filtering by XMP metadata fields. Cursor encodes (created_at, id)
    for reliable pagination.

    Args:
        composer_filter: Filter by composer (partial match)
        publisher_filter: Filter by publisher (partial match)
        record_label_filter: Filter by record label (partial match)
        isrc_filter: Filter by ISRC (exact match)
        year_min/year_max: Year range filters
        format_filter: Audio format filter
        limit: Maximum results (1-100, default: 50)
        cursor_data: Tuple of (created_at, id) from previous page, or None for first page

    Returns:
        Dictionary with tracks and pagination info

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If query fails

    Example:
        >>> # First page
        >>> result = filter_audio_tracks_cursor_xmp(
        ...     composer_filter="ROB JAGER",
        ...     limit=20
        ... )
        >>>
        >>> # Next page using cursor
        >>> next_result = filter_audio_tracks_cursor_xmp(
        ...     composer_filter="ROB JAGER",
        ...     limit=20,
        ...     cursor_data=(result['tracks'][-1]['created_at'], result['tracks'][-1]['id'])
        ... )
    """
    # Validation
    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if year_min is not None and (year_min < 1800 or year_min > 2100):
        raise ValidationError("year_min must be between 1800 and 2100")

    if year_max is not None and (year_max < 1800 or year_max > 2100):
        raise ValidationError("year_max must be between 1800 and 2100")

    if year_min and year_max and year_min > year_max:
        raise ValidationError("year_min cannot be greater than year_max")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build WHERE conditions
                where_conditions = ["status = 'COMPLETED'"]
                params = []

                # Add XMP field filters
                if composer_filter:
                    where_conditions.append("composer ILIKE %s")
                    params.append(f"%{composer_filter}%")

                if publisher_filter:
                    where_conditions.append("publisher ILIKE %s")
                    params.append(f"%{publisher_filter}%")

                if record_label_filter:
                    where_conditions.append("record_label ILIKE %s")
                    params.append(f"%{record_label_filter}%")

                if isrc_filter:
                    where_conditions.append("UPPER(isrc) = UPPER(%s)")
                    params.append(isrc_filter)

                # Add structured filters
                if year_min is not None:
                    where_conditions.append("year >= %s")
                    params.append(year_min)

                if year_max is not None:
                    where_conditions.append("year <= %s")
                    params.append(year_max)

                if format_filter:
                    where_conditions.append("UPPER(format) = UPPER(%s)")
                    params.append(format_filter)

                # Add cursor conditions for keyset pagination
                if cursor_data:
                    cursor_created_at, cursor_id = cursor_data
                    where_conditions.append("(created_at < %s OR (created_at = %s AND id < %s))")
                    params.extend([cursor_created_at, cursor_created_at, cursor_id])

                where_clause = " AND ".join(where_conditions)

                # Get results with stable ordering
                query = f"""
                    SELECT
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc,
                        created_at, updated_at
                    FROM audio_tracks
                    WHERE {where_clause}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                """

                cur.execute(query, params + [limit])
                results = cur.fetchall()

                logger.debug(
                    f"Cursor XMP filter returned {len(results)} results "
                    f"(filters: composer={composer_filter}, publisher={publisher_filter}, "
                    f"cursor={'present' if cursor_data else 'none'})"
                )

                # Determine if there are more results
                has_more = len(results) == limit
                next_cursor = None
                if has_more and results:
                    last_result = results[-1]
                    next_cursor = (str(last_result['created_at']), last_result['id'])

                return {
                    'tracks': [dict(row) for row in results],
                    'limit': limit,
                    'has_more': has_more,
                    'next_cursor': next_cursor,
                    'cursor_data': cursor_data,
                    'filters_applied': {
                        'composer': composer_filter,
                        'publisher': publisher_filter,
                        'record_label': record_label_filter,
                        'isrc': isrc_filter,
                        'year_min': year_min,
                        'year_max': year_max,
                        'format': format_filter
                    }
                }

    except DatabaseError as e:
        logger.error(f"Database error in cursor XMP filtering: {e}")
        raise DatabaseOperationError(f"Cursor XMP filtering failed: database error - {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in cursor XMP filtering: {e}")
        raise DatabaseOperationError(f"Cursor XMP filtering failed: {str(e)}")


def encode_cursor(created_at: str, track_id: str) -> str:
    """
    Encode cursor data into a base64 string for URL-safe pagination.

    Args:
        created_at: ISO timestamp string
        track_id: UUID string

    Returns:
        Base64 encoded cursor string

    Raises:
        ValidationError: If inputs are invalid
    """
    import base64
    import json

    try:
        cursor_data = {
            'created_at': created_at,
            'id': track_id
        }
        json_str = json.dumps(cursor_data, separators=(',', ':'))
        return base64.urlsafe_b64encode(json_str.encode()).decode()
    except Exception as e:
        raise ValidationError(f"Failed to encode cursor: {str(e)}")


def decode_cursor(cursor: str) -> Tuple[str, str]:
    """
    Decode cursor string back to (created_at, track_id) tuple.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Tuple of (created_at, track_id)

    Raises:
        ValidationError: If cursor is invalid
    """
    import base64
    import json

    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        cursor_data = json.loads(json_str)
        return (cursor_data['created_at'], cursor_data['id'])
    except Exception as e:
        raise ValidationError(f"Failed to decode cursor: {str(e)}")


# ============================================================================
# Waveform Metadata Operations
# ============================================================================

def update_waveform_metadata(
    audio_id: str,
    waveform_gcs_path: str,
    source_hash: str
) -> None:
    """
    Update waveform metadata for an audio track.

    Sets the waveform GCS path, generation timestamp, and source audio hash
    for cache invalidation. Uses atomic update with proper transaction handling.

    Args:
        audio_id: UUID of the audio track
        waveform_gcs_path: Full GCS path to the waveform SVG file
        source_hash: SHA-256 hash of the source audio file

    Raises:
        ValidationError: If audio_id is invalid or waveform_gcs_path format is wrong
        DatabaseOperationError: If database operation fails

    Example:
        >>> update_waveform_metadata(
        ...     '123e4567-e89b-12d3-a456-426614174000',
        ...     'gs://bucket/waveforms/123e4567/abc123.svg',
        ...     'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'
        ... )
    """
    if not audio_id:
        raise ValidationError("audio_id is required")

    if not waveform_gcs_path or not waveform_gcs_path.startswith('gs://'):
        raise ValidationError("waveform_gcs_path must be a valid gs:// URL")

    if not source_hash or len(source_hash) != 64:
        raise ValidationError("source_hash must be a valid 64-character SHA-256 hash")

    query = """
    UPDATE audio_tracks
    SET waveform_gcs_path = %s,
        waveform_generated_at = NOW(),
        source_audio_hash = %s,
        updated_at = NOW()
    WHERE id = %s::uuid
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (waveform_gcs_path, source_hash, audio_id))

                if cur.rowcount == 0:
                    logger.warning(f"No audio track found with ID: {audio_id}")
                    raise ResourceNotFoundError(f"Audio track not found: {audio_id}")

                # Commit transaction
                conn.commit()

                logger.info(f"Updated waveform metadata for audio track: {audio_id}")

    except DatabaseError as e:
        logger.error(f"Database error updating waveform metadata for {audio_id}: {e}")
        raise DatabaseOperationError(f"Failed to update waveform metadata: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error updating waveform metadata for {audio_id}: {e}")
        raise DatabaseOperationError(f"Failed to update waveform metadata: {str(e)}")


def get_waveform_metadata(audio_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve waveform metadata for an audio track.

    Returns waveform GCS path, generation timestamp, and source hash if available.

    Args:
        audio_id: UUID of the audio track

    Returns:
        Dict with waveform metadata, or None if no waveform exists:
        {
            'waveform_gcs_path': str,
            'waveform_generated_at': datetime,
            'source_audio_hash': str
        }

    Raises:
        ValidationError: If audio_id is invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> metadata = get_waveform_metadata('123e4567-e89b-12d3-a456-426614174000')
        >>> if metadata:
        ...     print(f"Waveform available at: {metadata['waveform_gcs_path']}")
    """
    if not audio_id:
        raise ValidationError("audio_id is required")

    query = """
    SELECT waveform_gcs_path, waveform_generated_at, source_audio_hash
    FROM audio_tracks
    WHERE id = %s::uuid AND waveform_gcs_path IS NOT NULL
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (audio_id,))
                result = cur.fetchone()

                if result:
                    # Convert datetime to string for JSON serialization
                    metadata = dict(result)
                    if metadata.get('waveform_generated_at'):
                        metadata['waveform_generated_at'] = metadata['waveform_generated_at'].isoformat()
                    return metadata

                return None

    except DatabaseError as e:
        logger.error(f"Database error retrieving waveform metadata for {audio_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve waveform metadata: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error retrieving waveform metadata for {audio_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve waveform metadata: {str(e)}")


def check_waveform_cache(audio_id: str, source_hash: str) -> Optional[str]:
    """
    Check if a waveform exists and matches the source audio hash.

    Used for cache validation - returns the GCS path if a waveform exists
    and was generated from the same source audio (matching hash).

    Args:
        audio_id: UUID of the audio track
        source_hash: SHA-256 hash of the current source audio file

    Returns:
        GCS path string if cache hit, None if cache miss or no waveform exists

    Raises:
        ValidationError: If audio_id or source_hash are invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> path = check_waveform_cache('123e4567...', 'a665a459...')
        >>> if path:
        ...     print(f"Cache hit: {path}")
        ... else:
        ...     print("Cache miss - generate new waveform")
    """
    if not audio_id:
        raise ValidationError("audio_id is required")

    if not source_hash or len(source_hash) != 64:
        raise ValidationError("source_hash must be a valid 64-character SHA-256 hash")

    metadata = get_waveform_metadata(audio_id)

    if metadata and metadata.get('source_audio_hash') == source_hash:
        logger.debug(f"Waveform cache hit for audio_id: {audio_id}")
        return metadata['waveform_gcs_path']

    logger.debug(f"Waveform cache miss for audio_id: {audio_id}")
    return None


# ============================================================================
# Error and Transaction Management
# ============================================================================
# Note: Error handling and transaction management are already implemented
# throughout all operations above using:
# - Context managers (with get_connection())
# - Explicit commit/rollback
# - Comprehensive exception handling
# - Detailed logging
# - Validation before database operations

