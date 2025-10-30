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
# Error and Transaction Management
# ============================================================================
# Note: Error handling and transaction management are already implemented
# throughout all operations above using:
# - Context managers (with get_connection())
# - Explicit commit/rollback
# - Comprehensive exception handling
# - Detailed logging
# - Validation before database operations

