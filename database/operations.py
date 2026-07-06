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
    a2a_task_id: Optional[str] = None,
    work_id: Optional[str] = None,
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
            - original_filename: str (optional, for download filename preservation)
        audio_gcs_path: Full GCS path (gs://bucket/path) to audio file
        thumbnail_gcs_path: Optional GCS path to thumbnail/artwork
        track_id: Optional UUID string for the track (generates new if None)
        a2a_task_id: Optional A2A task ID (UUID) for linking audio track to A2A task.
            Must be a valid UUID format. Links to SDK-managed a2a_tasks table.
            No foreign key constraint exists - referential integrity enforced at
            application level. Only populated for audio tracks processed via A2A endpoints.
        work_id: Optional work ID (UUID) for linking audio track to a work/composition.
            If not provided, automatically creates a stub work with the same title and
            status 'draft' (audio-first workflow). Must be a valid UUID format if provided.

    Returns:
        Dictionary containing the saved track information:
            - id: Track UUID
            - work_id: Work UUID (created or provided)
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

    # Validate a2a_task_id UUID format if provided
    if a2a_task_id is not None:
        try:
            uuid.UUID(a2a_task_id)
        except ValueError:
            raise ValidationError(f"Invalid a2a_task_id format: {a2a_task_id}")

    # Validate work_id UUID format if provided
    if work_id is not None:
        try:
            uuid.UUID(work_id)
        except ValueError:
            raise ValidationError(f"Invalid work_id format: {work_id}")

    # Auto-create work if not provided (audio-first workflow)
    if work_id is None:
        try:
            work_result = create_work({
                'title': metadata.get('title', 'Untitled'),
                'status': 'draft'
            })
            work_id = work_result['id']
            logger.debug(f"Auto-created work {work_id} for track {track_id or 'new'}")
        except Exception as e:
            logger.error(f"Failed to auto-create work for track: {e}")
            raise DatabaseOperationError(f"Failed to auto-create work: {str(e)}")

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
        # Filename preservation
        'original_filename': metadata.get('original_filename'),
        # A2A task linking
        'a2a_task_id': a2a_task_id,
        # Work linking (required after migration 010)
        'work_id': work_id,
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
                        composer, publisher, record_label, isrc, original_filename, a2a_task_id, work_id
                    ) VALUES (
                        %(id)s, %(status)s, %(artist)s, %(title)s, %(album)s,
                        %(genre)s, %(year)s, %(duration_seconds)s, %(channels)s,
                        %(sample_rate)s, %(bitrate)s, %(format)s, %(file_size_bytes)s,
                        %(audio_gcs_path)s, %(thumbnail_gcs_path)s,
                        %(composer)s, %(publisher)s, %(record_label)s, %(isrc)s,
                        %(original_filename)s, %(a2a_task_id)s, %(work_id)s
                    )
                    RETURNING
                        id, status, artist, title, album, genre, year,
                        duration_seconds, channels, sample_rate, bitrate,
                        format, file_size_bytes, audio_gcs_path, thumbnail_gcs_path,
                        composer, publisher, record_label, isrc, original_filename, a2a_task_id, work_id,
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
            - work_id: Optional UUID for the work (auto-created if not provided)

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
            work_id = record.get('work_id')

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

            # Validate work_id UUID format if provided
            if work_id is not None:
                try:
                    uuid.UUID(work_id)
                except ValueError:
                    raise ValidationError(f"Invalid work_id format: {work_id}")

            # Auto-create work if not provided (audio-first workflow)
            if work_id is None:
                try:
                    work_result = create_work({
                        'title': metadata.get('title', 'Untitled'),
                        'status': 'draft'
                    })
                    work_id = work_result['id']
                    logger.debug(f"Auto-created work {work_id} for track {track_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-create work for track {track_id}: {e}")
                    raise DatabaseOperationError(f"Failed to auto-create work: {str(e)}")

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
                # XMP fields
                'composer': metadata.get('composer'),
                'publisher': metadata.get('publisher'),
                'record_label': metadata.get('record_label'),
                'isrc': metadata.get('isrc'),
                # Filename preservation
                'original_filename': metadata.get('original_filename'),
                # Work linking (required after migration 010)
                'work_id': work_id,
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
                        composer, publisher, record_label, isrc, original_filename, work_id
                    ) VALUES
                """

                # Build VALUES clause for all records
                values_clauses = []
                params = []

                for record in validated_records:
                    values_clauses.append("""
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """)
                    params.extend([
                        record['id'], record['status'], record['artist'], record['title'],
                        record['album'], record['genre'], record['year'], record['duration_seconds'],
                        record['channels'], record['sample_rate'], record['bitrate'],
                        record['format'], record['file_size_bytes'], record['audio_gcs_path'],
                        record['thumbnail_gcs_path'], record['composer'], record['publisher'],
                        record['record_label'], record['isrc'], record['original_filename'],
                        record['work_id']
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
            - original_filename: Original filename from ingestion (for downloads)
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
                        original_filename, created_at, updated_at, error_message, retry_count, last_processed_at
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
                        original_filename, created_at, updated_at, error_message, retry_count, last_processed_at
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
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor):
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
# Delete Operations
# ============================================================================

def delete_audio_track(track_id: str) -> Dict[str, Any]:
    """
    Delete an audio track from the database.

    Returns the deleted track's GCS paths for cleanup.

    Args:
        track_id: UUID of the track to delete

    Returns:
        Dict with deleted track info including GCS paths:
        {
            'id': str,
            'audio_gcs_path': str,
            'thumbnail_gcs_path': str | None,
            'waveform_gcs_path': str | None
        }

    Raises:
        ValidationError: If track_id format is invalid
        ResourceNotFoundError: If track doesn't exist
        DatabaseOperationError: If deletion fails

    Example:
        >>> result = delete_audio_track('123e4567-e89b-12d3-a456-426614174000')
        >>> print(f"Deleted track, audio was at: {result['audio_gcs_path']}")
    """
    # Validate UUID format
    try:
        uuid.UUID(track_id)
    except ValueError:
        raise ValidationError(f"Invalid track_id format: {track_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Delete and return GCS paths in single query
                delete_query = """
                    DELETE FROM audio_tracks
                    WHERE id = %s
                    RETURNING
                        id,
                        audio_gcs_path,
                        thumbnail_gcs_path,
                        waveform_gcs_path
                """

                cur.execute(delete_query, (track_id,))
                result = cur.fetchone()

                if not result:
                    # Track doesn't exist
                    raise ResourceNotFoundError(
                        f"Audio track not found: {track_id}",
                        details={'track_id': track_id}
                    )

                # Commit transaction
                conn.commit()

                logger.info(f"Successfully deleted audio track: {track_id}")

                return dict(result)

    except ResourceNotFoundError:
        # Re-raise resource not found
        raise

    except DatabaseError as e:
        logger.error(f"Database error deleting track {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to delete audio track: database error - {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error deleting track {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to delete audio track: {str(e)}"
        )


# ============================================================================
# Metadata Update Operations
# ============================================================================

def update_audio_metadata(
    track_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update metadata fields for an audio track.

    Uses JSON Merge Patch semantics:
    - Only updates fields that are present in the metadata dict
    - Omitted fields remain unchanged
    - Existing database triggers handle updated_at and search_vector

    Args:
        track_id: UUID of the track to update
        metadata: Dict with fields to update (pre-validated by Pydantic)
                  Allowed fields: artist, title, album, genre, year,
                                  composer, publisher, record_label, isrc,
                                  original_filename

    Returns:
        Full updated track record as dict

    Raises:
        ValidationError: If track_id format is invalid or no valid fields provided
        ResourceNotFoundError: If track doesn't exist
        DatabaseOperationError: If update fails

    Example:
        >>> result = update_audio_metadata(
        ...     '123e4567-e89b-12d3-a456-426614174000',
        ...     {'artist': 'The Beatles', 'year': 1968}
        ... )
        >>> print(f"Updated track: {result['title']} by {result['artist']}")
    """
    # Validate UUID format
    try:
        uuid.UUID(track_id)
    except ValueError:
        raise ValidationError(f"Invalid track_id format: {track_id}")

    if not metadata:
        raise ValidationError("No metadata fields to update")

    # Allowed editable fields (whitelist for safety)
    allowed_fields = {
        'artist', 'title', 'album', 'genre', 'year',
        'composer', 'publisher', 'record_label', 'isrc',
        'original_filename'
    }

    # Filter to only allowed fields
    updates = {k: v for k, v in metadata.items() if k in allowed_fields}

    if not updates:
        raise ValidationError(
            f"No valid fields to update. Allowed fields: {', '.join(sorted(allowed_fields))}"
        )

    # Validate title is not empty if provided
    if 'title' in updates and not updates['title']:
        raise ValidationError("Title cannot be empty")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build dynamic UPDATE query with parameterized values
                set_clauses = [f"{field} = %s" for field in updates.keys()]
                params = list(updates.values())
                params.append(track_id)  # For WHERE clause

                update_query = f"""
                    UPDATE audio_tracks
                    SET {', '.join(set_clauses)}
                    WHERE id = %s::uuid
                    RETURNING *
                """
                # Note: updated_at and search_vector are handled by existing triggers

                cur.execute(update_query, params)
                result = cur.fetchone()

                if not result:
                    raise ResourceNotFoundError(
                        f"Track not found: {track_id}",
                        details={'track_id': track_id}
                    )

                # Commit transaction
                conn.commit()

                logger.info(
                    f"Successfully updated metadata for track {track_id}: "
                    f"fields={list(updates.keys())}"
                )

                return dict(result)

    except ResourceNotFoundError:
        # Re-raise resource not found
        raise

    except ValidationError:
        # Re-raise validation errors
        raise

    except DatabaseError as e:
        logger.error(f"Database error updating track {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update audio metadata: database error - {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error updating track {track_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update audio metadata: {str(e)}"
        )


# ============================================================================
# Song Publishing Operations
# ============================================================================

# ============================================================================
# Party Operations
# ============================================================================

def create_party(party_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new party (person or organization).

    Inserts a party into the parties table with validation and error handling.
    Supports both persons and organizations with optional industry identifiers.

    Args:
        party_data: Dictionary containing party fields:
            - name: str (required) - Display name
            - party_type: str (required) - 'person' or 'organization'
            - legal_name: str (optional) - Legal/contract name
            - ipi_cae_number: str (optional) - CAE/IPI number for PRO registration
            - isni: str (optional) - International Standard Name Identifier
            - society_affiliation: str (optional) - PRO affiliation (PRS, BMI, etc.)
            - email: str (optional) - Contact email
            - notes: str (optional) - Freeform notes
            - id: str (optional) - UUID (generated if not provided)

    Returns:
        Dictionary containing the created party information with all fields

    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> party = create_party({
        ...     'name': 'John Smith',
        ...     'party_type': 'person',
        ...     'ipi_cae_number': '12345678901',
        ...     'society_affiliation': 'PRS'
        ... })
        >>> print(party['id'])
    """
    # Validate required fields
    if not party_data.get('name'):
        raise ValidationError("Name is required for party")

    party_type = party_data.get('party_type', 'person')
    if party_type not in ('person', 'organization'):
        raise ValidationError(f"Invalid party_type '{party_type}'. Must be 'person' or 'organization'")

    # Generate UUID if not provided
    party_id = party_data.get('id')
    if party_id:
        try:
            uuid.UUID(party_id)
        except ValueError:
            raise ValidationError(f"Invalid party_id format: {party_id}")
    else:
        party_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO parties (
                        id, party_type, name, legal_name, ipi_cae_number, isni,
                        society_affiliation, email, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, party_type, name, legal_name, ipi_cae_number, isni,
                        society_affiliation, email, notes, created_at, updated_at
                """

                cur.execute(insert_query, (
                    party_id,
                    party_type,
                    party_data.get('name'),
                    party_data.get('legal_name'),
                    party_data.get('ipi_cae_number'),
                    party_data.get('isni'),
                    party_data.get('society_affiliation'),
                    party_data.get('email'),
                    party_data.get('notes')
                ))

                result = cur.fetchone()
                conn.commit()

                logger.info(f"Successfully created party: {party_id}")
                return dict(result)

    except IntegrityError as e:
        error_str = str(e)
        if 'idx_parties_ipi_unique' in error_str:
            raise ValidationError(f"IPI/CAE number already exists: {party_data.get('ipi_cae_number')}")
        elif 'idx_parties_isni_unique' in error_str:
            raise ValidationError(f"ISNI already exists: {party_data.get('isni')}")
        logger.error(f"Integrity error creating party: {e}")
        raise DatabaseOperationError(f"Failed to create party: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error creating party: {e}")
        raise DatabaseOperationError(f"Failed to create party: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error creating party: {e}")
        raise DatabaseOperationError(f"Failed to create party: {str(e)}")


def _get_party_works_as_writer(cur, party_id: str) -> List[Dict[str, Any]]:
    """Helper function to get works where party is a writer."""
    query = """
        SELECT
            ww.work_id,
            w.title AS work_title,
            ww.split_percentage,
            ww.split_status
        FROM work_writers ww
        INNER JOIN works w ON ww.work_id = w.id
        WHERE ww.party_id = %s
        ORDER BY w.title
    """
    cur.execute(query, (party_id,))
    return [dict(row) for row in cur.fetchall()]


def _get_party_works_as_publisher(cur, party_id: str) -> List[Dict[str, Any]]:
    """Helper function to get works where party is a publisher."""
    query = """
        SELECT
            wp.work_id,
            w.title AS work_title,
            wp.split_percentage,
            wp.split_status
        FROM work_publishers wp
        INNER JOIN works w ON wp.work_id = w.id
        WHERE wp.party_id = %s
        ORDER BY w.title
    """
    cur.execute(query, (party_id,))
    return [dict(row) for row in cur.fetchall()]


def _get_party_recordings_as_artist(cur, party_id: str) -> List[Dict[str, Any]]:
    """Helper function to get recordings where party is an artist."""
    query = """
        SELECT
            ra.audio_track_id,
            at.title AS track_title,
            ra.is_primary
        FROM recording_artists ra
        INNER JOIN audio_tracks at ON ra.audio_track_id = at.id
        WHERE ra.party_id = %s
        ORDER BY at.title
    """
    cur.execute(query, (party_id,))
    return [dict(row) for row in cur.fetchall()]


def get_party_by_id(party_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve party by ID with works involvement.

    Returns party details including all works where the party is involved
    as a writer, publisher, or recording artist.

    Args:
        party_id: UUID string of the party to retrieve

    Returns:
        Dictionary with party information and involvement:
            - All party fields (id, name, party_type, etc.)
            - works_as_writer: List of works with split info
            - works_as_publisher: List of works with split info
            - recordings_as_artist: List of recordings with is_primary flag
        Returns None if party not found

    Raises:
        ValidationError: If party_id format is invalid
        DatabaseOperationError: If database query fails

    Example:
        >>> party = get_party_by_id('123e4567-e89b-12d3-a456-426614174000')
        >>> if party:
        ...     print(f"Found: {party['name']}")
        ...     print(f"Works as writer: {len(party['works_as_writer'])}")
    """
    # Validate UUID format
    try:
        uuid.UUID(party_id)
    except ValueError:
        raise ValidationError(f"Invalid party_id format: {party_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get party base data
                query = """
                    SELECT
                        id, party_type, name, legal_name, ipi_cae_number, isni,
                        society_affiliation, email, notes, created_at, updated_at
                    FROM parties
                    WHERE id = %s
                """

                cur.execute(query, (party_id,))
                result = cur.fetchone()

                if not result:
                    logger.debug(f"Party not found: {party_id}")
                    return None

                party = dict(result)

                # Get works involvement
                party['works_as_writer'] = _get_party_works_as_writer(cur, party_id)
                party['works_as_publisher'] = _get_party_works_as_publisher(cur, party_id)
                party['recordings_as_artist'] = _get_party_recordings_as_artist(cur, party_id)

                logger.debug(f"Retrieved party with involvement: {party_id}")
                return party

    except DatabaseError as e:
        logger.error(f"Database error retrieving party {party_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve party: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error retrieving party {party_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve party: {str(e)}")


def search_parties(query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Search parties by name using ILIKE pattern matching.

    Uses trigram index for efficient partial name matching.
    Returns basic party information (not full involvement details).

    Args:
        query: Search query string (matched against name field)
        limit: Maximum number of results (1-100, default: 20)
        offset: Number of results to skip for pagination (>=0)

    Returns:
        List of party dictionaries ordered by name ASC

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails

    Example:
        >>> results = search_parties("Smith", limit=10)
        >>> for party in results:
        ...     print(f"{party['name']} ({party['party_type']})")
    """
    # Validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                search_query = """
                    SELECT
                        id, party_type, name, legal_name, ipi_cae_number, isni,
                        society_affiliation, email, notes, created_at, updated_at
                    FROM parties
                    WHERE name ILIKE %s
                    ORDER BY name ASC
                    LIMIT %s OFFSET %s
                """

                pattern = f"%{query.strip()}%"
                cur.execute(search_query, (pattern, limit, offset))
                results = cur.fetchall()

                logger.debug(f"Found {len(results)} parties matching '{query}'")
                return [dict(row) for row in results]

    except DatabaseError as e:
        logger.error(f"Database error searching parties: {e}")
        raise DatabaseOperationError(f"Failed to search parties: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error searching parties: {e}")
        raise DatabaseOperationError(f"Failed to search parties: {str(e)}")


# ============================================================================
# Work Operations
# ============================================================================

def create_work(work_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new work (composition).

    Inserts a work into the works table with validation and error handling.
    Works represent compositions, separate from recordings.

    Args:
        work_data: Dictionary containing work fields:
            - title: str (required) - Canonical title
            - iswc: str (optional) - International Standard Musical Work Code
            - language: str (optional) - ISO 639-1 language code (e.g., 'en', 'es')
            - status: str (optional) - Workflow status (default: 'draft')
                Valid: 'draft', 'splits_pending', 'splits_disputed', 'ready', 'registered'
            - notes: str (optional) - Freeform notes
            - id: str (optional) - UUID (generated if not provided)

    Returns:
        Dictionary containing the created work information with all fields

    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> work = create_work({
        ...     'title': 'Bohemian Rhapsody',
        ...     'language': 'en',
        ...     'status': 'draft'
        ... })
        >>> print(work['id'])
    """
    # Validate required fields
    if not work_data.get('title'):
        raise ValidationError("Title is required for work")

    # Validate status if provided
    status = work_data.get('status', 'draft')
    valid_statuses = ('draft', 'splits_pending', 'splits_disputed', 'ready', 'registered')
    if status not in valid_statuses:
        raise ValidationError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    # Generate UUID if not provided
    work_id = work_data.get('id')
    if work_id:
        try:
            uuid.UUID(work_id)
        except ValueError:
            raise ValidationError(f"Invalid work_id format: {work_id}")
    else:
        work_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO works (
                        id, title, iswc, language, status, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, title, iswc, language, status, notes, created_at, updated_at
                """

                cur.execute(insert_query, (
                    work_id,
                    work_data.get('title'),
                    work_data.get('iswc'),
                    work_data.get('language'),
                    status,
                    work_data.get('notes')
                ))

                result = cur.fetchone()
                conn.commit()

                logger.info(f"Successfully created work: {work_id}")
                return dict(result)

    except IntegrityError as e:
        error_str = str(e)
        if 'idx_works_iswc_unique' in error_str:
            raise ValidationError(f"ISWC already exists: {work_data.get('iswc')}")
        logger.error(f"Integrity error creating work: {e}")
        raise DatabaseOperationError(f"Failed to create work: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error creating work: {e}")
        raise DatabaseOperationError(f"Failed to create work: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error creating work: {e}")
        raise DatabaseOperationError(f"Failed to create work: {str(e)}")


def _get_work_base(cur, work_id: str) -> Optional[Dict[str, Any]]:
    """Helper function to get work base data."""
    query = """
        SELECT
            id, title, iswc, language, status, notes, created_at, updated_at
        FROM works
        WHERE id = %s
    """
    cur.execute(query, (work_id,))
    result = cur.fetchone()
    return dict(result) if result else None


def _get_work_writers(cur, work_id: str) -> List[Dict[str, Any]]:
    """Helper function to get writers for a work."""
    query = """
        SELECT
            ww.party_id,
            p.name AS party_name,
            ww.split_percentage,
            ww.split_status,
            ww.notes
        FROM work_writers ww
        INNER JOIN parties p ON ww.party_id = p.id
        WHERE ww.work_id = %s
        ORDER BY p.name
    """
    cur.execute(query, (work_id,))
    return [dict(row) for row in cur.fetchall()]


def _get_work_publishers(cur, work_id: str) -> List[Dict[str, Any]]:
    """Helper function to get publishers for a work."""
    query = """
        SELECT
            wp.party_id,
            p.name AS party_name,
            wp.split_percentage,
            wp.split_status,
            wp.notes
        FROM work_publishers wp
        INNER JOIN parties p ON wp.party_id = p.id
        WHERE wp.work_id = %s
        ORDER BY p.name
    """
    cur.execute(query, (work_id,))
    return [dict(row) for row in cur.fetchall()]


def _get_work_alt_titles(cur, work_id: str) -> List[Dict[str, Any]]:
    """Helper function to get alternative titles for a work."""
    query = """
        SELECT
            id, title, title_type, language
        FROM work_alternative_titles
        WHERE work_id = %s
        ORDER BY title
    """
    cur.execute(query, (work_id,))
    return [dict(row) for row in cur.fetchall()]


def _get_work_recordings(cur, work_id: str) -> List[Dict[str, Any]]:
    """Helper function to get recordings linked to a work."""
    query = """
        SELECT
            id, title, artist, isrc
        FROM audio_tracks
        WHERE work_id = %s
        ORDER BY title
    """
    cur.execute(query, (work_id,))
    return [dict(row) for row in cur.fetchall()]


def get_work_by_id(work_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve work by ID with all related data and warnings.

    Returns work details including writers, publishers, alternative titles,
    recordings, and split warnings.

    Args:
        work_id: UUID string of the work to retrieve

    Returns:
        Dictionary with work information and all relations:
            - All work fields (id, title, iswc, etc.)
            - writers: List of writers with split info
            - publishers: List of publishers with split info
            - alternative_titles: List of alternative titles
            - recordings: List of linked audio tracks
            - warnings: List of split warning strings
        Returns None if work not found

    Raises:
        ValidationError: If work_id format is invalid
        DatabaseOperationError: If database query fails

    Example:
        >>> work = get_work_by_id('123e4567-e89b-12d3-a456-426614174000')
        >>> if work:
        ...     print(f"Found: {work['title']}")
        ...     print(f"Writers: {len(work['writers'])}")
        ...     print(f"Warnings: {work['warnings']}")
    """
    # Validate UUID format
    try:
        uuid.UUID(work_id)
    except ValueError:
        raise ValidationError(f"Invalid work_id format: {work_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. Get work base data
                work = _get_work_base(cur, work_id)
                if not work:
                    logger.debug(f"Work not found: {work_id}")
                    return None

                # 2. Get writers
                work['writers'] = _get_work_writers(cur, work_id)

                # 3. Get publishers
                work['publishers'] = _get_work_publishers(cur, work_id)

                # 4. Get alternative titles
                work['alternative_titles'] = _get_work_alt_titles(cur, work_id)

                # 5. Get recordings
                work['recordings'] = _get_work_recordings(cur, work_id)

                # 6. Calculate warnings (using internal helper to reuse cursor)
                work['warnings'] = _calculate_split_warnings(cur, work_id)

                logger.debug(f"Retrieved work with all relations: {work_id}")
                return work

    except DatabaseError as e:
        logger.error(f"Database error retrieving work {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve work: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error retrieving work {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve work: {str(e)}")


def search_works(query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Search works by title using ILIKE pattern matching.

    Uses trigram index for efficient partial title matching.
    Returns basic work information (not full details with relations).

    Args:
        query: Search query string (matched against title field)
        limit: Maximum number of results (1-100, default: 20)
        offset: Number of results to skip for pagination (>=0)

    Returns:
        List of work dictionaries ordered by title ASC

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails

    Example:
        >>> results = search_works("Bohemian", limit=10)
        >>> for work in results:
        ...     print(f"{work['title']} ({work['status']})")
    """
    # Validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                search_query = """
                    SELECT
                        id, title, iswc, language, status, notes, created_at, updated_at
                    FROM works
                    WHERE title ILIKE %s
                    ORDER BY title ASC
                    LIMIT %s OFFSET %s
                """

                pattern = f"%{query.strip()}%"
                cur.execute(search_query, (pattern, limit, offset))
                results = cur.fetchall()

                logger.debug(f"Found {len(results)} works matching '{query}'")
                return [dict(row) for row in results]

    except DatabaseError as e:
        logger.error(f"Database error searching works: {e}")
        raise DatabaseOperationError(f"Failed to search works: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error searching works: {e}")
        raise DatabaseOperationError(f"Failed to search works: {str(e)}")


# ============================================================================
# Junction Table Batch Operations
# ============================================================================

def replace_work_writers(work_id: str, writers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Replace all writers for a work using batch replace pattern.

    Atomically deletes all existing writers and inserts new ones in a transaction.
    To add a writer: include existing + new in the list.
    To remove: exclude from list.
    To update: change the values in the list.

    Args:
        work_id: UUID of the work
        writers: List of writer dictionaries, each containing:
            - party_id: str (required) - UUID of the party
            - split_percentage: float (optional) - Percentage (0-200 or None)
            - split_status: str (required) - 'proposed', 'confirmed', 'disputed', 'unknown'
            - notes: str (optional) - Freeform notes

    Returns:
        Dictionary with:
            - replaced_count: Number of writers replaced
            - work_id: The work ID

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> replace_work_writers('work-id', [
        ...     {'party_id': 'party-1', 'split_percentage': 50.0, 'split_status': 'confirmed'},
        ...     {'party_id': 'party-2', 'split_percentage': 50.0, 'split_status': 'confirmed'}
        ... ])
    """
    # Validate work_id
    try:
        uuid.UUID(work_id)
    except ValueError:
        raise ValidationError(f"Invalid work_id format: {work_id}")

    # Validate writers list
    if not isinstance(writers, list):
        raise ValidationError("Writers must be a list")

    # Validate each writer
    valid_statuses = ('proposed', 'confirmed', 'disputed', 'unknown')
    for idx, writer in enumerate(writers):
        if not isinstance(writer, dict):
            raise ValidationError(f"Writer at index {idx} must be a dictionary")

        # Validate party_id
        party_id = writer.get('party_id')
        if not party_id:
            raise ValidationError(f"Writer at index {idx} missing required field: party_id")
        try:
            uuid.UUID(party_id)
        except ValueError:
            raise ValidationError(f"Writer at index {idx} has invalid party_id format: {party_id}")

        # Validate split_status
        split_status = writer.get('split_status')
        if not split_status:
            raise ValidationError(f"Writer at index {idx} missing required field: split_status")
        if split_status not in valid_statuses:
            raise ValidationError(f"Writer at index {idx} has invalid split_status '{split_status}'. Must be one of: {valid_statuses}")

        # Validate split_percentage if provided
        split_percentage = writer.get('split_percentage')
        if split_percentage is not None:
            try:
                split_float = float(split_percentage)
                if split_float < 0 or split_float > 200:
                    raise ValidationError(f"Writer at index {idx} has invalid split_percentage {split_float}. Must be between 0 and 200")
            except (ValueError, TypeError):
                raise ValidationError(f"Writer at index {idx} has invalid split_percentage: {split_percentage}")

    try:
        with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    # Verify work exists (better error message than FK constraint)
                    cur.execute("SELECT id FROM works WHERE id = %s", (work_id,))
                    if not cur.fetchone():
                        raise ResourceNotFoundError(f"Work not found: {work_id}")

                    # DELETE existing writers
                    cur.execute("DELETE FROM work_writers WHERE work_id = %s", (work_id,))
                    deleted_count = cur.rowcount

                    # INSERT new writers
                    insert_query = """
                        INSERT INTO work_writers (
                            work_id, party_id, split_percentage, split_status, notes, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, NOW(), NOW()
                        )
                    """

                    for writer in writers:
                        cur.execute(insert_query, (
                            work_id,
                            writer['party_id'],
                            writer.get('split_percentage'),
                            writer['split_status'],
                            writer.get('notes')
                        ))

                    conn.commit()  # Explicit commit

                    logger.info(f"Replaced {len(writers)} writers for work {work_id} (deleted {deleted_count} existing)")
                    return {
                        "replaced_count": len(writers),
                        "work_id": work_id
                    }
            except Exception:
                conn.rollback()
                raise

    except IntegrityError as e:
        error_str = str(e)
        if 'work_writers_work_id_party_id_key' in error_str:
            raise ValidationError("Duplicate party_id in writers list")
        logger.error(f"Integrity error replacing writers: {e}")
        raise DatabaseOperationError(f"Failed to replace writers: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error replacing writers: {e}")
        raise DatabaseOperationError(f"Failed to replace writers: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error replacing writers: {e}")
        raise DatabaseOperationError(f"Failed to replace writers: {str(e)}")


def replace_work_publishers(work_id: str, publishers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Replace all publishers for a work using batch replace pattern.

    Atomically deletes all existing publishers and inserts new ones in a transaction.
    To add a publisher: include existing + new in the list.
    To remove: exclude from list.
    To update: change the values in the list.

    Args:
        work_id: UUID of the work
        publishers: List of publisher dictionaries, each containing:
            - party_id: str (required) - UUID of the party
            - split_percentage: float (optional) - Percentage (0-200 or None)
            - split_status: str (required) - 'proposed', 'confirmed', 'disputed', 'unknown'
            - notes: str (optional) - Freeform notes

    Returns:
        Dictionary with:
            - replaced_count: Number of publishers replaced
            - work_id: The work ID

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> replace_work_publishers('work-id', [
        ...     {'party_id': 'publisher-1', 'split_percentage': 50.0, 'split_status': 'confirmed'}
        ... ])
    """
    # Validate work_id
    try:
        uuid.UUID(work_id)
    except ValueError:
        raise ValidationError(f"Invalid work_id format: {work_id}")

    # Validate publishers list
    if not isinstance(publishers, list):
        raise ValidationError("Publishers must be a list")

    # Validate each publisher
    valid_statuses = ('proposed', 'confirmed', 'disputed', 'unknown')
    for idx, publisher in enumerate(publishers):
        if not isinstance(publisher, dict):
            raise ValidationError(f"Publisher at index {idx} must be a dictionary")

        # Validate party_id
        party_id = publisher.get('party_id')
        if not party_id:
            raise ValidationError(f"Publisher at index {idx} missing required field: party_id")
        try:
            uuid.UUID(party_id)
        except ValueError:
            raise ValidationError(f"Publisher at index {idx} has invalid party_id format: {party_id}")

        # Validate split_status
        split_status = publisher.get('split_status')
        if not split_status:
            raise ValidationError(f"Publisher at index {idx} missing required field: split_status")
        if split_status not in valid_statuses:
            raise ValidationError(f"Publisher at index {idx} has invalid split_status '{split_status}'. Must be one of: {valid_statuses}")

        # Validate split_percentage if provided
        split_percentage = publisher.get('split_percentage')
        if split_percentage is not None:
            try:
                split_float = float(split_percentage)
                if split_float < 0 or split_float > 200:
                    raise ValidationError(f"Publisher at index {idx} has invalid split_percentage {split_float}. Must be between 0 and 200")
            except (ValueError, TypeError):
                raise ValidationError(f"Publisher at index {idx} has invalid split_percentage: {split_percentage}")

    try:
        with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    # Verify work exists (better error message than FK constraint)
                    cur.execute("SELECT id FROM works WHERE id = %s", (work_id,))
                    if not cur.fetchone():
                        raise ResourceNotFoundError(f"Work not found: {work_id}")

                    # DELETE existing publishers
                    cur.execute("DELETE FROM work_publishers WHERE work_id = %s", (work_id,))
                    deleted_count = cur.rowcount

                    # INSERT new publishers
                    insert_query = """
                        INSERT INTO work_publishers (
                            work_id, party_id, split_percentage, split_status, notes, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, NOW(), NOW()
                        )
                    """

                    for publisher in publishers:
                        cur.execute(insert_query, (
                            work_id,
                            publisher['party_id'],
                            publisher.get('split_percentage'),
                            publisher['split_status'],
                            publisher.get('notes')
                        ))

                    conn.commit()  # Explicit commit

                    logger.info(f"Replaced {len(publishers)} publishers for work {work_id} (deleted {deleted_count} existing)")
                    return {
                        "replaced_count": len(publishers),
                        "work_id": work_id
                    }
            except Exception:
                conn.rollback()
                raise

    except IntegrityError as e:
        error_str = str(e)
        if 'work_publishers_work_id_party_id_key' in error_str:
            raise ValidationError("Duplicate party_id in publishers list")
        logger.error(f"Integrity error replacing publishers: {e}")
        raise DatabaseOperationError(f"Failed to replace publishers: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error replacing publishers: {e}")
        raise DatabaseOperationError(f"Failed to replace publishers: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error replacing publishers: {e}")
        raise DatabaseOperationError(f"Failed to replace publishers: {str(e)}")


# ============================================================================
# Split Warning Calculation
# ============================================================================

def _calculate_split_warnings(cur, work_id: str) -> List[str]:
    """
    Internal helper to calculate split warnings using an existing cursor.

    Args:
        cur: Database cursor
        work_id: UUID of the work

    Returns:
        List of warning strings (empty list if no warnings)
    """
    warnings = []

    # Get writer split totals and disputes
    writer_query = """
        SELECT
            COALESCE(SUM(split_percentage), 0) as total_split,
            COUNT(*) as writer_count,
            COUNT(CASE WHEN split_status = 'disputed' THEN 1 END) as disputed_count
        FROM work_writers
        WHERE work_id = %s
    """
    cur.execute(writer_query, (work_id,))
    writer_result = cur.fetchone()

    if writer_result:
        writer_count = int(writer_result['writer_count'] or 0)
        total_writer_split = float(writer_result['total_split'] or 0)
        disputed_writer_count = int(writer_result['disputed_count'] or 0)

        # Only warn if there are writers (avoid noisy warnings for empty works)
        if writer_count > 0:
            if total_writer_split < 100:
                warnings.append(f"Writer splits only add up to {total_writer_split:.2f}%")
            elif total_writer_split > 100:
                warnings.append(f"Writer splits exceed 100% ({total_writer_split:.2f}%)")

            if disputed_writer_count > 0:
                warnings.append("One or more writer splits are disputed")

    # Get publisher split totals and disputes
    publisher_query = """
        SELECT
            COALESCE(SUM(split_percentage), 0) as total_split,
            COUNT(*) as publisher_count,
            COUNT(CASE WHEN split_status = 'disputed' THEN 1 END) as disputed_count
        FROM work_publishers
        WHERE work_id = %s
    """
    cur.execute(publisher_query, (work_id,))
    publisher_result = cur.fetchone()

    if publisher_result:
        publisher_count = int(publisher_result['publisher_count'] or 0)
        total_publisher_split = float(publisher_result['total_split'] or 0)
        disputed_publisher_count = int(publisher_result['disputed_count'] or 0)

        # Only warn if there are publishers (avoid noisy warnings for empty works)
        if publisher_count > 0:
            if total_publisher_split < 100:
                warnings.append(f"Publisher splits only add up to {total_publisher_split:.2f}%")
            elif total_publisher_split > 100:
                warnings.append(f"Publisher splits exceed 100% ({total_publisher_split:.2f}%)")

            if disputed_publisher_count > 0:
                warnings.append("One or more publisher splits are disputed")

    return warnings


def calculate_split_warnings(work_id: str) -> List[str]:
    """
    Calculate split warnings for a work.

    Checks writer and publisher splits for completeness, over-claiming, and disputes.
    Warnings are informational only - the schema allows incomplete/disputed splits.

    Args:
        work_id: UUID of the work

    Returns:
        List of warning strings (empty list if no warnings)

    Raises:
        ValidationError: If work_id format is invalid
        DatabaseOperationError: If query fails

    Example:
        >>> warnings = calculate_split_warnings('work-id')
        >>> for warning in warnings:
        ...     print(warning)
    """
    # Validate UUID format
    try:
        uuid.UUID(work_id)
    except ValueError:
        raise ValidationError(f"Invalid work_id format: {work_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                return _calculate_split_warnings(cur, work_id)

    except DatabaseError as e:
        logger.error(f"Database error calculating split warnings for {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to calculate split warnings: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error calculating split warnings for {work_id}: {e}")
        raise DatabaseOperationError(f"Failed to calculate split warnings: {str(e)}")


# ============================================================================
# Recording Artist Operations
# ============================================================================

def link_artist_to_recording(
    audio_track_id: str,
    party_id: str,
    is_primary: bool = True,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Link an artist (party) to a recording (audio_track).

    Creates a relationship in the recording_artists junction table.

    Args:
        audio_track_id: UUID of the audio track
        party_id: UUID of the party (artist)
        is_primary: Whether this is the primary artist (default: True)
        notes: Optional notes about the artist's involvement

    Returns:
        Dictionary containing the created recording_artist relationship

    Raises:
        ValidationError: If parameters are invalid or duplicate link exists
        DatabaseOperationError: If operation fails

    Example:
        >>> link_artist_to_recording('track-id', 'party-id', is_primary=True)
    """
    # Validate UUIDs
    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    try:
        uuid.UUID(party_id)
    except ValueError:
        raise ValidationError(f"Invalid party_id format: {party_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO recording_artists (
                        audio_track_id, party_id, is_primary, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, audio_track_id, party_id, is_primary, notes, created_at, updated_at
                """

                cur.execute(insert_query, (audio_track_id, party_id, is_primary, notes))
                result = cur.fetchone()
                conn.commit()

                logger.info(f"Linked artist {party_id} to recording {audio_track_id}")
                return dict(result)

    except IntegrityError as e:
        error_str = str(e)
        if 'recording_artists_audio_track_id_party_id_key' in error_str:
            raise ValidationError(f"Artist {party_id} is already linked to recording {audio_track_id}")
        logger.error(f"Integrity error linking artist: {e}")
        raise DatabaseOperationError(f"Failed to link artist: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error linking artist: {e}")
        raise DatabaseOperationError(f"Failed to link artist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error linking artist: {e}")
        raise DatabaseOperationError(f"Failed to link artist: {str(e)}")


def unlink_artist_from_recording(audio_track_id: str, party_id: str) -> bool:
    """
    Unlink an artist (party) from a recording (audio_track).

    Removes the relationship from the recording_artists junction table.

    Args:
        audio_track_id: UUID of the audio track
        party_id: UUID of the party (artist)

    Returns:
        True if deleted, False if not found (graceful handling)

    Raises:
        ValidationError: If UUID formats are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> unlink_artist_from_recording('track-id', 'party-id')
    """
    # Validate UUIDs
    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    try:
        uuid.UUID(party_id)
    except ValueError:
        raise ValidationError(f"Invalid party_id format: {party_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                delete_query = """
                    DELETE FROM recording_artists
                    WHERE audio_track_id = %s AND party_id = %s
                """

                cur.execute(delete_query, (audio_track_id, party_id))
                deleted = cur.rowcount > 0
                conn.commit()

                if deleted:
                    logger.info(f"Unlinked artist {party_id} from recording {audio_track_id}")
                else:
                    logger.debug(f"Artist {party_id} not linked to recording {audio_track_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error unlinking artist: {e}")
        raise DatabaseOperationError(f"Failed to unlink artist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error unlinking artist: {e}")
        raise DatabaseOperationError(f"Failed to unlink artist: {str(e)}")


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

# ============================================================================

def create_album(album_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new album.

    Inserts an album into the albums table with validation and error handling.

    Args:
        album_data: Dictionary containing album fields:
            - name: str (required) - Album name
            - artist: str (optional) - Album artist
            - release_date: date (optional) - Release date
            - genre: str (optional) - Primary genre
            - label: str (optional) - Record label
            - catalog_number: str (optional) - Catalog number
            - total_discs: int (optional) - Number of discs (default: 1)
            - status: str (optional) - Status (default: 'draft')
                Valid: 'draft', 'pending_review', 'ready', 'published'
            - notes: str (optional) - Freeform notes
            - id: str (optional) - UUID (generated if not provided)

    Returns:
        Dictionary containing the created album information with all fields

    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> album = create_album({
        ...     'name': 'Abbey Road',
        ...     'artist': 'The Beatles',
        ...     'status': 'published'
        ... })
        >>> print(album['id'])
    """
    # Validate required fields
    if not album_data.get('name'):
        raise ValidationError("Name is required for album")

    # Validate status if provided
    status = album_data.get('status', 'draft')
    valid_statuses = ('draft', 'pending_review', 'ready', 'published')
    if status not in valid_statuses:
        raise ValidationError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    # Generate UUID if not provided
    album_id = album_data.get('id')
    if album_id:
        try:
            uuid.UUID(album_id)
        except ValueError:
            raise ValidationError(f"Invalid album_id format: {album_id}")
    else:
        album_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO albums (
                        id, name, artist, release_date, genre, label, catalog_number,
                        total_discs, status, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, name, artist, release_date, genre, label, catalog_number,
                        total_discs, status, notes, created_at, updated_at
                """

                cur.execute(insert_query, (
                    album_id,
                    album_data.get('name'),
                    album_data.get('artist'),
                    album_data.get('release_date'),
                    album_data.get('genre'),
                    album_data.get('label'),
                    album_data.get('catalog_number'),
                    album_data.get('total_discs', 1),
                    status,
                    album_data.get('notes')
                ))

                result = cur.fetchone()
                conn.commit()

                logger.info(f"Successfully created album: {album_id}")
                return dict(result)

    except IntegrityError as e:
        logger.error(f"Integrity error creating album: {e}")
        raise DatabaseOperationError(f"Failed to create album: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error creating album: {e}")
        raise DatabaseOperationError(f"Failed to create album: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error creating album: {e}")
        raise DatabaseOperationError(f"Failed to create album: {str(e)}")


def get_album_by_id(album_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an album by ID with nested track details.

    Returns album base information plus all associated tracks with their metadata.

    Args:
        album_id: UUID of the album to retrieve

    Returns:
        Dictionary containing album info, tracks list, and track_count.
        Returns None if album not found.

    Raises:
        ValidationError: If album_id format is invalid
        DatabaseOperationError: If retrieval fails

    Example:
        >>> album = get_album_by_id('123e4567-e89b-12d3-a456-426614174000')
        >>> print(f"Album: {album['name']} - {album['track_count']} tracks")
    """
    # Validate UUID format
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get album base info
                album_query = """
                    SELECT
                        id, name, artist, release_date, genre, label, catalog_number,
                        total_discs, status, notes, created_at, updated_at
                    FROM albums
                    WHERE id = %s
                """

                cur.execute(album_query, (album_id,))
                album_result = cur.fetchone()

                if not album_result:
                    logger.debug(f"Album not found: {album_id}")
                    return None

                album = dict(album_result)

                # Get tracks with JOIN
                tracks_query = """
                    SELECT
                        at.id, at.title, at.artist, at.album, at.duration_seconds,
                        at.format, at.status, at.created_at, at.updated_at,
                        alt.position, alt.disc_number
                    FROM album_tracks alt
                    LEFT JOIN audio_tracks at ON alt.audio_track_id = at.id
                    WHERE alt.album_id = %s
                    ORDER BY alt.disc_number ASC, alt.position ASC
                """

                cur.execute(tracks_query, (album_id,))
                tracks_results = cur.fetchall()

                album['tracks'] = [dict(row) for row in tracks_results]
                album['track_count'] = len(album['tracks'])

                logger.debug(f"Retrieved album {album_id} with {album['track_count']} tracks")
                return album

    except DatabaseError as e:
        logger.error(f"Database error retrieving album {album_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve album: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error retrieving album {album_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve album: {str(e)}")


def update_album(album_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an album's metadata.

    Uses JSON Merge Patch semantics - only updates provided fields.

    Args:
        album_id: UUID of the album to update
        update_data: Dict with fields to update
                     Allowed fields: name, artist, release_date, genre, label,
                                     catalog_number, total_discs, status, notes

    Returns:
        Full updated album record as dict

    Raises:
        ValidationError: If album_id format is invalid or no valid fields provided
        ResourceNotFoundError: If album doesn't exist
        DatabaseOperationError: If update fails

    Example:
        >>> result = update_album(
        ...     '123e4567-e89b-12d3-a456-426614174000',
        ...     {'status': 'published', 'notes': 'Final release'}
        ... )
    """
    # Validate UUID format
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    if not update_data:
        raise ValidationError("No fields to update")

    # Allowed editable fields (whitelist for safety)
    allowed_fields = {
        'name', 'artist', 'release_date', 'genre', 'label',
        'catalog_number', 'total_discs', 'status', 'notes'
    }

    # Filter to only allowed fields
    updates = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not updates:
        raise ValidationError(
            f"No valid fields to update. Allowed fields: {', '.join(sorted(allowed_fields))}"
        )

    # Validate status if provided
    if 'status' in updates:
        valid_statuses = ('draft', 'pending_review', 'ready', 'published')
        if updates['status'] not in valid_statuses:
            raise ValidationError(f"Invalid status '{updates['status']}'. Must be one of: {valid_statuses}")

    # Validate name is not empty if provided
    if 'name' in updates and not updates['name']:
        raise ValidationError("Name cannot be empty")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build dynamic UPDATE query with parameterized values
                set_clauses = [f"{field} = %s" for field in updates.keys()]
                params = list(updates.values())
                params.append(album_id)  # For WHERE clause

                update_query = f"""
                    UPDATE albums
                    SET {', '.join(set_clauses)}
                    WHERE id = %s::uuid
                    RETURNING *
                """

                cur.execute(update_query, params)
                result = cur.fetchone()

                if not result:
                    raise ResourceNotFoundError(
                        f"Album not found: {album_id}",
                        details={'album_id': album_id}
                    )

                # Commit transaction
                conn.commit()

                logger.info(
                    f"Successfully updated album {album_id}: "
                    f"fields={list(updates.keys())}"
                )

                return dict(result)

    except ResourceNotFoundError:
        raise

    except ValidationError:
        raise

    except DatabaseError as e:
        logger.error(f"Database error updating album {album_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update album: database error - {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error updating album {album_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update album: {str(e)}"
        )


def delete_album(album_id: str) -> bool:
    """
    Delete an album by ID.

    CASCADE foreign key handles deletion of album_tracks junction records.

    Args:
        album_id: UUID of the album to delete

    Returns:
        True if deleted, False if not found

    Raises:
        ValidationError: If album_id format is invalid
        DatabaseOperationError: If deletion fails

    Example:
        >>> deleted = delete_album('123e4567-e89b-12d3-a456-426614174000')
    """
    # Validate UUID format
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                delete_query = """
                    DELETE FROM albums
                    WHERE id = %s
                """

                cur.execute(delete_query, (album_id,))
                deleted = cur.rowcount > 0
                conn.commit()

                if deleted:
                    logger.info(f"Deleted album {album_id}")
                else:
                    logger.debug(f"Album not found for deletion: {album_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error deleting album: {e}")
        raise DatabaseOperationError(f"Failed to delete album: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error deleting album: {e}")
        raise DatabaseOperationError(f"Failed to delete album: {str(e)}")


def search_albums(
    query: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search albums by name using ILIKE pattern matching.

    Args:
        query: Search query string (matched against name field)
        limit: Maximum number of results (1-100, default: 20)
        offset: Number of results to skip for pagination (>=0)
        status: Optional status filter

    Returns:
        List of album dictionaries with track_count, ordered by name ASC

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails

    Example:
        >>> results = search_albums("Abbey", limit=10, status='published')
        >>> for album in results:
        ...     print(f"{album['name']} - {album['track_count']} tracks")
    """
    # Validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    if status:
        valid_statuses = ('draft', 'pending_review', 'ready', 'published')
        if status not in valid_statuses:
            raise ValidationError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build query with optional status filter
                base_query = """
                    SELECT
                        a.id, a.name, a.artist, a.release_date, a.genre, a.label,
                        a.catalog_number, a.total_discs, a.status, a.notes,
                        a.created_at, a.updated_at,
                        (SELECT COUNT(*) FROM album_tracks WHERE album_id = a.id) AS track_count
                    FROM albums a
                    WHERE a.name ILIKE %s
                """

                params = [f"%{query.strip()}%"]

                if status:
                    base_query += " AND a.status = %s"
                    params.append(status)

                base_query += " ORDER BY a.name ASC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(base_query, params)
                results = cur.fetchall()

                logger.debug(f"Found {len(results)} albums matching '{query}'")
                return [dict(row) for row in results]

    except DatabaseError as e:
        logger.error(f"Database error searching albums: {e}")
        raise DatabaseOperationError(f"Failed to search albums: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error searching albums: {e}")
        raise DatabaseOperationError(f"Failed to search albums: {str(e)}")


def add_track_to_album(
    album_id: str,
    audio_track_id: str,
    position: Optional[int] = None,
    disc_number: int = 1
) -> Dict[str, Any]:
    """
    Add a track to an album at a specific position.

    If position is None, auto-assigns next available position for the disc.

    Args:
        album_id: UUID of the album
        audio_track_id: UUID of the audio track
        position: Track position on disc (auto-assigned if None)
        disc_number: Disc number (default: 1)

    Returns:
        Dictionary containing the created album_tracks relationship

    Raises:
        ValidationError: If parameters are invalid or duplicate link exists
        DatabaseOperationError: If operation fails

    Example:
        >>> add_track_to_album('album-id', 'track-id', position=1)
    """
    # Validate UUIDs
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    if disc_number < 1:
        raise ValidationError("Disc number must be >= 1")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Auto-assign position if not provided
                if position is None:
                    position_query = """
                        SELECT COALESCE(MAX(position), 0) + 1 AS next_position
                        FROM album_tracks
                        WHERE album_id = %s AND disc_number = %s
                    """
                    cur.execute(position_query, (album_id, disc_number))
                    position = cur.fetchone()['next_position']

                insert_query = """
                    INSERT INTO album_tracks (
                        album_id, audio_track_id, position, disc_number, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, album_id, audio_track_id, position, disc_number, created_at, updated_at
                """

                cur.execute(insert_query, (album_id, audio_track_id, position, disc_number))
                result = cur.fetchone()
                conn.commit()

                logger.info(f"Added track {audio_track_id} to album {album_id} at position {position}")
                return dict(result)

    except IntegrityError as e:
        error_str = str(e)
        if 'album_tracks_album_id_audio_track_id_key' in error_str:
            raise ValidationError(f"Track {audio_track_id} is already in album {album_id}")
        logger.error(f"Integrity error adding track to album: {e}")
        raise DatabaseOperationError(f"Failed to add track to album: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error adding track to album: {e}")
        raise DatabaseOperationError(f"Failed to add track to album: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error adding track to album: {e}")
        raise DatabaseOperationError(f"Failed to add track to album: {str(e)}")


def remove_track_from_album(album_id: str, audio_track_id: str) -> bool:
    """
    Remove a track from an album and renumber remaining positions.

    Deletes the album_tracks entry and renumbers remaining tracks on same disc
    to maintain contiguous positions.

    Args:
        album_id: UUID of the album
        audio_track_id: UUID of the audio track

    Returns:
        True if deleted, False if not found

    Raises:
        ValidationError: If UUID formats are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> remove_track_from_album('album-id', 'track-id')
    """
    # Validate UUIDs
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get disc_number before deletion for renumbering
                disc_query = """
                    SELECT disc_number FROM album_tracks
                    WHERE album_id = %s AND audio_track_id = %s
                """
                cur.execute(disc_query, (album_id, audio_track_id))
                disc_result = cur.fetchone()

                if not disc_result:
                    logger.debug(f"Track {audio_track_id} not in album {album_id}")
                    return False

                disc_number = disc_result[0]

                # Delete the track
                delete_query = """
                    DELETE FROM album_tracks
                    WHERE album_id = %s AND audio_track_id = %s
                """
                cur.execute(delete_query, (album_id, audio_track_id))
                deleted = cur.rowcount > 0

                # Renumber remaining positions on the same disc
                if deleted:
                    renumber_query = """
                        UPDATE album_tracks
                        SET position = subquery.new_position
                        FROM (
                            SELECT
                                id,
                                ROW_NUMBER() OVER (ORDER BY position ASC) AS new_position
                            FROM album_tracks
                            WHERE album_id = %s AND disc_number = %s
                        ) AS subquery
                        WHERE album_tracks.id = subquery.id
                    """
                    cur.execute(renumber_query, (album_id, disc_number))

                conn.commit()

                if deleted:
                    logger.info(f"Removed track {audio_track_id} from album {album_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error removing track from album: {e}")
        raise DatabaseOperationError(f"Failed to remove track from album: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error removing track from album: {e}")
        raise DatabaseOperationError(f"Failed to remove track from album: {str(e)}")


def reorder_album_tracks(album_id: str, track_order: List[str]) -> Dict[str, Any]:
    """
    Reorder tracks in an album.

    Uses two-pass update to avoid constraint violations during reordering:
    1. Set all positions to negative values
    2. Set final positive positions

    Args:
        album_id: UUID of the album
        track_order: List of audio_track_ids in desired order

    Returns:
        Dictionary with count of updated tracks

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If reordering fails

    Example:
        >>> result = reorder_album_tracks('album-id', ['track1', 'track2', 'track3'])
        >>> print(f"Reordered {result['updated_count']} tracks")
    """
    # Validate album_id
    try:
        uuid.UUID(album_id)
    except ValueError:
        raise ValidationError(f"Invalid album_id format: {album_id}")

    if not track_order:
        raise ValidationError("Track order list cannot be empty")

    # Validate all track IDs
    for track_id in track_order:
        try:
            uuid.UUID(track_id)
        except ValueError:
            raise ValidationError(f"Invalid audio_track_id format: {track_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # First pass: set all to negative positions
                for idx, track_id in enumerate(track_order):
                    negative_position = -1 * (idx + 1)
                    update_query = """
                        UPDATE album_tracks
                        SET position = %s
                        WHERE album_id = %s AND audio_track_id = %s
                    """
                    cur.execute(update_query, (negative_position, album_id, track_id))

                # Second pass: set final positive positions
                updated_count = 0
                for idx, track_id in enumerate(track_order):
                    final_position = idx + 1
                    update_query = """
                        UPDATE album_tracks
                        SET position = %s
                        WHERE album_id = %s AND audio_track_id = %s
                    """
                    cur.execute(update_query, (final_position, album_id, track_id))
                    updated_count += cur.rowcount

                conn.commit()

                logger.info(f"Reordered {updated_count} tracks in album {album_id}")
                return {'updated_count': updated_count}

    except DatabaseError as e:
        logger.error(f"Database error reordering album tracks: {e}")
        raise DatabaseOperationError(f"Failed to reorder album tracks: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error reordering album tracks: {e}")
        raise DatabaseOperationError(f"Failed to reorder album tracks: {str(e)}")


# ============================================================================
# Playlist Operations
# ============================================================================

def create_playlist(playlist_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new playlist.

    Inserts a playlist into the playlists table with validation and error handling.

    Args:
        playlist_data: Dictionary containing playlist fields:
            - name: str (required) - Playlist name
            - description: str (optional) - Playlist description
            - is_public: bool (optional) - Public visibility (default: False)
            - owner_id: str (optional) - UUID of the owner user
            - notes: str (optional) - Freeform notes
            - id: str (optional) - UUID (generated if not provided)

    Returns:
        Dictionary containing the created playlist information with all fields

    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseOperationError: If database operation fails

    Example:
        >>> playlist = create_playlist({
        ...     'name': 'My Favorites',
        ...     'is_public': True
        ... })
        >>> print(playlist['id'])
    """
    # Validate required fields
    if not playlist_data.get('name'):
        raise ValidationError("Name is required for playlist")

    # Generate UUID if not provided
    playlist_id = playlist_data.get('id')
    if playlist_id:
        try:
            uuid.UUID(playlist_id)
        except ValueError:
            raise ValidationError(f"Invalid playlist_id format: {playlist_id}")
    else:
        playlist_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO playlists (
                        id, name, description, is_public, owner_id, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    RETURNING
                        id, name, description, is_public, owner_id, notes, created_at, updated_at
                """

                cur.execute(insert_query, (
                    playlist_id,
                    playlist_data.get('name'),
                    playlist_data.get('description'),
                    playlist_data.get('is_public', False),
                    playlist_data.get('owner_id'),
                    playlist_data.get('notes')
                ))

                result = cur.fetchone()
                conn.commit()

                logger.info(f"Successfully created playlist: {playlist_id}")
                return dict(result)

    except IntegrityError as e:
        logger.error(f"Integrity error creating playlist: {e}")
        raise DatabaseOperationError(f"Failed to create playlist: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error creating playlist: {e}")
        raise DatabaseOperationError(f"Failed to create playlist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error creating playlist: {e}")
        raise DatabaseOperationError(f"Failed to create playlist: {str(e)}")


def get_playlist_by_id(playlist_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a playlist by ID with nested tracks and collaborators.

    Returns playlist base information plus all associated tracks and collaborators.

    Args:
        playlist_id: UUID of the playlist to retrieve

    Returns:
        Dictionary containing playlist info, tracks list, and collaborators list.
        Returns None if playlist not found.

    Raises:
        ValidationError: If playlist_id format is invalid
        DatabaseOperationError: If retrieval fails

    Example:
        >>> playlist = get_playlist_by_id('123e4567-e89b-12d3-a456-426614174000')
        >>> print(f"Playlist: {playlist['name']} - {len(playlist['tracks'])} tracks")
    """
    # Validate UUID format
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get playlist base info
                playlist_query = """
                    SELECT
                        id, name, description, is_public, owner_id, notes, created_at, updated_at
                    FROM playlists
                    WHERE id = %s
                """

                cur.execute(playlist_query, (playlist_id,))
                playlist_result = cur.fetchone()

                if not playlist_result:
                    logger.debug(f"Playlist not found: {playlist_id}")
                    return None

                playlist = dict(playlist_result)

                # Get tracks with JOIN
                tracks_query = """
                    SELECT
                        at.id, at.title, at.artist, at.album, at.duration_seconds,
                        at.format, at.status, at.created_at, at.updated_at,
                        pt.position, pt.added_by, pt.added_at
                    FROM playlist_tracks pt
                    LEFT JOIN audio_tracks at ON pt.audio_track_id = at.id
                    WHERE pt.playlist_id = %s
                    ORDER BY pt.position ASC
                """

                cur.execute(tracks_query, (playlist_id,))
                tracks_results = cur.fetchall()
                playlist['tracks'] = [dict(row) for row in tracks_results]

                # Get collaborators
                collaborators_query = """
                    SELECT
                        id, playlist_id, user_id, role, created_at, updated_at
                    FROM playlist_collaborators
                    WHERE playlist_id = %s
                    ORDER BY created_at ASC
                """

                cur.execute(collaborators_query, (playlist_id,))
                collaborators_results = cur.fetchall()
                playlist['collaborators'] = [dict(row) for row in collaborators_results]

                logger.debug(
                    f"Retrieved playlist {playlist_id} with {len(playlist['tracks'])} tracks "
                    f"and {len(playlist['collaborators'])} collaborators"
                )
                return playlist

    except DatabaseError as e:
        logger.error(f"Database error retrieving playlist {playlist_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve playlist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error retrieving playlist {playlist_id}: {e}")
        raise DatabaseOperationError(f"Failed to retrieve playlist: {str(e)}")


def update_playlist(playlist_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a playlist's metadata.

    Uses JSON Merge Patch semantics - only updates provided fields.

    Args:
        playlist_id: UUID of the playlist to update
        update_data: Dict with fields to update
                     Allowed fields: name, description, is_public, owner_id, notes

    Returns:
        Full updated playlist record as dict

    Raises:
        ValidationError: If playlist_id format is invalid or no valid fields provided
        ResourceNotFoundError: If playlist doesn't exist
        DatabaseOperationError: If update fails

    Example:
        >>> result = update_playlist(
        ...     '123e4567-e89b-12d3-a456-426614174000',
        ...     {'is_public': True, 'description': 'Best tracks'}
        ... )
    """
    # Validate UUID format
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    if not update_data:
        raise ValidationError("No fields to update")

    # Allowed editable fields (whitelist for safety)
    allowed_fields = {'name', 'description', 'is_public', 'owner_id', 'notes'}

    # Filter to only allowed fields
    updates = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not updates:
        raise ValidationError(
            f"No valid fields to update. Allowed fields: {', '.join(sorted(allowed_fields))}"
        )

    # Validate name is not empty if provided
    if 'name' in updates and not updates['name']:
        raise ValidationError("Name cannot be empty")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build dynamic UPDATE query with parameterized values
                set_clauses = [f"{field} = %s" for field in updates.keys()]
                params = list(updates.values())
                params.append(playlist_id)  # For WHERE clause

                update_query = f"""
                    UPDATE playlists
                    SET {', '.join(set_clauses)}
                    WHERE id = %s::uuid
                    RETURNING *
                """

                cur.execute(update_query, params)
                result = cur.fetchone()

                if not result:
                    raise ResourceNotFoundError(
                        f"Playlist not found: {playlist_id}",
                        details={'playlist_id': playlist_id}
                    )

                # Commit transaction
                conn.commit()

                logger.info(
                    f"Successfully updated playlist {playlist_id}: "
                    f"fields={list(updates.keys())}"
                )

                return dict(result)

    except ResourceNotFoundError:
        raise

    except ValidationError:
        raise

    except DatabaseError as e:
        logger.error(f"Database error updating playlist {playlist_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update playlist: database error - {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error updating playlist {playlist_id}: {e}")
        raise DatabaseOperationError(
            f"Failed to update playlist: {str(e)}"
        )


def delete_playlist(playlist_id: str) -> bool:
    """
    Delete a playlist by ID.

    CASCADE foreign key handles deletion of playlist_tracks and playlist_collaborators.

    Args:
        playlist_id: UUID of the playlist to delete

    Returns:
        True if deleted, False if not found

    Raises:
        ValidationError: If playlist_id format is invalid
        DatabaseOperationError: If deletion fails

    Example:
        >>> deleted = delete_playlist('123e4567-e89b-12d3-a456-426614174000')
    """
    # Validate UUID format
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                delete_query = """
                    DELETE FROM playlists
                    WHERE id = %s
                """

                cur.execute(delete_query, (playlist_id,))
                deleted = cur.rowcount > 0
                conn.commit()

                if deleted:
                    logger.info(f"Deleted playlist {playlist_id}")
                else:
                    logger.debug(f"Playlist not found for deletion: {playlist_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error deleting playlist: {e}")
        raise DatabaseOperationError(f"Failed to delete playlist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error deleting playlist: {e}")
        raise DatabaseOperationError(f"Failed to delete playlist: {str(e)}")


def search_playlists(
    query: str,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Search playlists by name using ILIKE pattern matching.

    Args:
        query: Search query string (matched against name field)
        limit: Maximum number of results (1-100, default: 20)
        offset: Number of results to skip for pagination (>=0)

    Returns:
        List of playlist dictionaries with track_count, ordered by name ASC

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If search fails

    Example:
        >>> results = search_playlists("Favorites", limit=10)
        >>> for playlist in results:
        ...     print(f"{playlist['name']} - {playlist['track_count']} tracks")
    """
    # Validation
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    if limit < 1 or limit > 100:
        raise ValidationError("Limit must be between 1 and 100")

    if offset < 0:
        raise ValidationError("Offset must be non-negative")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                search_query = """
                    SELECT
                        p.id, p.name, p.description, p.is_public, p.owner_id, p.notes,
                        p.created_at, p.updated_at,
                        (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = p.id) AS track_count
                    FROM playlists p
                    WHERE p.name ILIKE %s
                    ORDER BY p.name ASC
                    LIMIT %s OFFSET %s
                """

                pattern = f"%{query.strip()}%"
                cur.execute(search_query, (pattern, limit, offset))
                results = cur.fetchall()

                logger.debug(f"Found {len(results)} playlists matching '{query}'")
                return [dict(row) for row in results]

    except DatabaseError as e:
        logger.error(f"Database error searching playlists: {e}")
        raise DatabaseOperationError(f"Failed to search playlists: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error searching playlists: {e}")
        raise DatabaseOperationError(f"Failed to search playlists: {str(e)}")


def add_track_to_playlist(
    playlist_id: str,
    audio_track_id: str,
    position: Optional[int] = None,
    added_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a track to a playlist at a specific position.

    If position is None, auto-assigns next available position.

    Args:
        playlist_id: UUID of the playlist
        audio_track_id: UUID of the audio track
        position: Track position (auto-assigned if None)
        added_by: UUID of user who added the track (optional)

    Returns:
        Dictionary containing the created playlist_tracks relationship

    Raises:
        ValidationError: If parameters are invalid or duplicate link exists
        DatabaseOperationError: If operation fails

    Example:
        >>> add_track_to_playlist('playlist-id', 'track-id', added_by='user-id')
    """
    # Validate UUIDs
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    if added_by:
        try:
            uuid.UUID(added_by)
        except ValueError:
            raise ValidationError(f"Invalid added_by format: {added_by}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Auto-assign position if not provided
                if position is None:
                    position_query = """
                        SELECT COALESCE(MAX(position), 0) + 1 AS next_position
                        FROM playlist_tracks
                        WHERE playlist_id = %s
                    """
                    cur.execute(position_query, (playlist_id,))
                    position = cur.fetchone()['next_position']

                insert_query = """
                    INSERT INTO playlist_tracks (
                        playlist_id, audio_track_id, position, added_by, added_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), NOW(), NOW()
                    )
                    RETURNING
                        id, playlist_id, audio_track_id, position, added_by, added_at, created_at, updated_at
                """

                cur.execute(insert_query, (playlist_id, audio_track_id, position, added_by))
                result = cur.fetchone()
                conn.commit()

                logger.info(f"Added track {audio_track_id} to playlist {playlist_id} at position {position}")
                return dict(result)

    except IntegrityError as e:
        error_str = str(e)
        if 'playlist_tracks_playlist_id_audio_track_id_key' in error_str:
            raise ValidationError(f"Track {audio_track_id} is already in playlist {playlist_id}")
        logger.error(f"Integrity error adding track to playlist: {e}")
        raise DatabaseOperationError(f"Failed to add track to playlist: constraint violation - {str(e)}")

    except DatabaseError as e:
        logger.error(f"Database error adding track to playlist: {e}")
        raise DatabaseOperationError(f"Failed to add track to playlist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error adding track to playlist: {e}")
        raise DatabaseOperationError(f"Failed to add track to playlist: {str(e)}")


def remove_track_from_playlist(playlist_id: str, audio_track_id: str) -> bool:
    """
    Remove a track from a playlist and renumber remaining positions.

    Deletes the playlist_tracks entry and renumbers remaining tracks
    to maintain contiguous positions.

    Args:
        playlist_id: UUID of the playlist
        audio_track_id: UUID of the audio track

    Returns:
        True if deleted, False if not found

    Raises:
        ValidationError: If UUID formats are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> remove_track_from_playlist('playlist-id', 'track-id')
    """
    # Validate UUIDs
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        uuid.UUID(audio_track_id)
    except ValueError:
        raise ValidationError(f"Invalid audio_track_id format: {audio_track_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Delete the track
                delete_query = """
                    DELETE FROM playlist_tracks
                    WHERE playlist_id = %s AND audio_track_id = %s
                """
                cur.execute(delete_query, (playlist_id, audio_track_id))
                deleted = cur.rowcount > 0

                # Renumber remaining positions
                if deleted:
                    renumber_query = """
                        UPDATE playlist_tracks
                        SET position = subquery.new_position
                        FROM (
                            SELECT
                                id,
                                ROW_NUMBER() OVER (ORDER BY position ASC) AS new_position
                            FROM playlist_tracks
                            WHERE playlist_id = %s
                        ) AS subquery
                        WHERE playlist_tracks.id = subquery.id
                    """
                    cur.execute(renumber_query, (playlist_id,))

                conn.commit()

                if deleted:
                    logger.info(f"Removed track {audio_track_id} from playlist {playlist_id}")
                else:
                    logger.debug(f"Track {audio_track_id} not in playlist {playlist_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error removing track from playlist: {e}")
        raise DatabaseOperationError(f"Failed to remove track from playlist: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error removing track from playlist: {e}")
        raise DatabaseOperationError(f"Failed to remove track from playlist: {str(e)}")


def reorder_playlist_tracks(playlist_id: str, track_order: List[str]) -> Dict[str, Any]:
    """
    Reorder tracks in a playlist.

    Uses two-pass update to avoid constraint violations during reordering:
    1. Set all positions to negative values
    2. Set final positive positions

    Args:
        playlist_id: UUID of the playlist
        track_order: List of audio_track_ids in desired order

    Returns:
        Dictionary with count of updated tracks

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If reordering fails

    Example:
        >>> result = reorder_playlist_tracks('playlist-id', ['track1', 'track2', 'track3'])
        >>> print(f"Reordered {result['updated_count']} tracks")
    """
    # Validate playlist_id
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    if not track_order:
        raise ValidationError("Track order list cannot be empty")

    # Validate all track IDs
    for track_id in track_order:
        try:
            uuid.UUID(track_id)
        except ValueError:
            raise ValidationError(f"Invalid audio_track_id format: {track_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # First pass: set all to negative positions
                for idx, track_id in enumerate(track_order):
                    negative_position = -1 * (idx + 1)
                    update_query = """
                        UPDATE playlist_tracks
                        SET position = %s
                        WHERE playlist_id = %s AND audio_track_id = %s
                    """
                    cur.execute(update_query, (negative_position, playlist_id, track_id))

                # Second pass: set final positive positions
                updated_count = 0
                for idx, track_id in enumerate(track_order):
                    final_position = idx + 1
                    update_query = """
                        UPDATE playlist_tracks
                        SET position = %s
                        WHERE playlist_id = %s AND audio_track_id = %s
                    """
                    cur.execute(update_query, (final_position, playlist_id, track_id))
                    updated_count += cur.rowcount

                conn.commit()

                logger.info(f"Reordered {updated_count} tracks in playlist {playlist_id}")
                return {'updated_count': updated_count}

    except DatabaseError as e:
        logger.error(f"Database error reordering playlist tracks: {e}")
        raise DatabaseOperationError(f"Failed to reorder playlist tracks: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error reordering playlist tracks: {e}")
        raise DatabaseOperationError(f"Failed to reorder playlist tracks: {str(e)}")


def add_playlist_collaborator(
    playlist_id: str,
    user_id: str,
    role: str = 'viewer'
) -> Dict[str, Any]:
    """
    Add a collaborator to a playlist.

    If user is already a collaborator, updates their role.

    Args:
        playlist_id: UUID of the playlist
        user_id: UUID of the user to add
        role: Collaborator role ('viewer', 'editor', 'admin')

    Returns:
        Dictionary containing the created/updated playlist_collaborators record

    Raises:
        ValidationError: If parameters are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> add_playlist_collaborator('playlist-id', 'user-id', role='editor')
    """
    # Validate UUIDs
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        uuid.UUID(user_id)
    except ValueError:
        raise ValidationError(f"Invalid user_id format: {user_id}")

    # Validate role
    valid_roles = ('viewer', 'editor', 'admin')
    if role not in valid_roles:
        raise ValidationError(f"Invalid role '{role}'. Must be one of: {valid_roles}")

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                insert_query = """
                    INSERT INTO playlist_collaborators (
                        playlist_id, user_id, role, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, NOW(), NOW()
                    )
                    ON CONFLICT (playlist_id, user_id)
                    DO UPDATE SET role = EXCLUDED.role, updated_at = NOW()
                    RETURNING
                        id, playlist_id, user_id, role, created_at, updated_at
                """

                cur.execute(insert_query, (playlist_id, user_id, role))
                result = cur.fetchone()
                conn.commit()

                logger.info(f"Added/updated collaborator {user_id} to playlist {playlist_id} with role {role}")
                return dict(result)

    except DatabaseError as e:
        logger.error(f"Database error adding playlist collaborator: {e}")
        raise DatabaseOperationError(f"Failed to add playlist collaborator: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error adding playlist collaborator: {e}")
        raise DatabaseOperationError(f"Failed to add playlist collaborator: {str(e)}")


def remove_playlist_collaborator(playlist_id: str, user_id: str) -> bool:
    """
    Remove a collaborator from a playlist.

    Args:
        playlist_id: UUID of the playlist
        user_id: UUID of the user to remove

    Returns:
        True if deleted, False if not found

    Raises:
        ValidationError: If UUID formats are invalid
        DatabaseOperationError: If operation fails

    Example:
        >>> remove_playlist_collaborator('playlist-id', 'user-id')
    """
    # Validate UUIDs
    try:
        uuid.UUID(playlist_id)
    except ValueError:
        raise ValidationError(f"Invalid playlist_id format: {playlist_id}")

    try:
        uuid.UUID(user_id)
    except ValueError:
        raise ValidationError(f"Invalid user_id format: {user_id}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                delete_query = """
                    DELETE FROM playlist_collaborators
                    WHERE playlist_id = %s AND user_id = %s
                """

                cur.execute(delete_query, (playlist_id, user_id))
                deleted = cur.rowcount > 0
                conn.commit()

                if deleted:
                    logger.info(f"Removed collaborator {user_id} from playlist {playlist_id}")
                else:
                    logger.debug(f"User {user_id} not a collaborator on playlist {playlist_id}")

                return deleted

    except DatabaseError as e:
        logger.error(f"Database error removing playlist collaborator: {e}")
        raise DatabaseOperationError(f"Failed to remove playlist collaborator: database error - {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error removing playlist collaborator: {e}")
        raise DatabaseOperationError(f"Failed to remove playlist collaborator: {str(e)}")


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

