"""
Database utility functions for common operations.

Provides helper functions for querying, inserting, updating, and managing
audio track metadata in PostgreSQL.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
import psycopg2.extras
from .pool import get_connection

logger = logging.getLogger(__name__)


class AudioTrackDB:
    """Database operations for audio tracks."""
    
    @staticmethod
    def insert_track(
        track_id: UUID,
        title: str,
        audio_path: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        year: Optional[int] = None,
        duration: Optional[float] = None,
        channels: Optional[int] = None,
        sample_rate: Optional[int] = None,
        bitrate: Optional[int] = None,
        format: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert a new audio track record.
        
        Args:
            track_id: Unique track identifier
            title: Track title (required)
            audio_path: GCS path to audio file (required)
            artist: Artist name
            album: Album name
            genre: Genre
            year: Release year
            duration: Duration in seconds
            channels: Number of audio channels
            sample_rate: Sample rate in Hz
            bitrate: Bitrate in kbps
            format: Audio format (mp3, flac, etc.)
            thumbnail_path: GCS path to thumbnail
        
        Returns:
            Inserted track record as dictionary
        """
        query = """
            INSERT INTO audio_tracks (
                id, title, audio_path, artist, album, genre, year,
                duration, channels, sample_rate, bitrate, format, thumbnail_path,
                status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                'COMPLETED', NOW(), NOW()
            )
            RETURNING *
        """
        
        params = (
            str(track_id), title, audio_path, artist, album, genre, year,
            duration, channels, sample_rate, bitrate, format, thumbnail_path
        )
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                conn.commit()
                
                logger.info(f"Inserted track: {track_id} - {title}")
                return dict(result)
    
    @staticmethod
    def get_track_by_id(track_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a track by its ID.
        
        Args:
            track_id: Track UUID
        
        Returns:
            Track record as dictionary or None if not found
        """
        query = "SELECT * FROM audio_tracks WHERE id = %s"
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (str(track_id),))
                result = cur.fetchone()
                return dict(result) if result else None
    
    @staticmethod
    def search_tracks(
        search_term: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        year: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search for tracks using various filters.
        
        Args:
            search_term: Full-text search across artist, title, album, genre
            artist: Filter by artist (exact match)
            album: Filter by album (exact match)
            genre: Filter by genre (exact match)
            year: Filter by year
            status: Filter by status
            limit: Maximum number of results
            offset: Result offset for pagination
        
        Returns:
            List of track records
        """
        query = "SELECT * FROM audio_tracks WHERE 1=1"
        params = []
        
        if search_term:
            query += " AND search_vector @@ plainto_tsquery('english', %s)"
            params.append(search_term)
        
        if artist:
            query += " AND artist = %s"
            params.append(artist)
        
        if album:
            query += " AND album = %s"
            params.append(album)
        
        if genre:
            query += " AND genre = %s"
            params.append(genre)
        
        if year:
            query += " AND year = %s"
            params.append(year)
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                results = cur.fetchall()
                return [dict(row) for row in results]
    
    @staticmethod
    def fuzzy_search_tracks(
        search_term: str,
        similarity_threshold: float = 0.3,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fuzzy search for tracks using trigram similarity.
        
        Args:
            search_term: Search term
            similarity_threshold: Minimum similarity (0-1)
            limit: Maximum number of results
        
        Returns:
            List of track records with similarity scores
        """
        query = """
            SELECT *,
                   similarity(COALESCE(artist, '') || ' ' || title, %s) as sim_score
            FROM audio_tracks
            WHERE similarity(COALESCE(artist, '') || ' ' || title, %s) > %s
            ORDER BY sim_score DESC
            LIMIT %s
        """
        
        params = (search_term, search_term, similarity_threshold, limit)
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(row) for row in results]
    
    @staticmethod
    def update_track_status(track_id: UUID, status: str) -> bool:
        """
        Update the status of a track.
        
        Args:
            track_id: Track UUID
            status: New status (PENDING, PROCESSING, COMPLETED, FAILED)
        
        Returns:
            True if updated, False if not found
        """
        query = """
            UPDATE audio_tracks
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id
        """
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, str(track_id)))
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    logger.info(f"Updated track {track_id} status to {status}")
                    return True
                return False
    
    @staticmethod
    def delete_track(track_id: UUID) -> bool:
        """
        Delete a track record.
        
        Args:
            track_id: Track UUID
        
        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM audio_tracks WHERE id = %s RETURNING id"
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (str(track_id),))
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    logger.info(f"Deleted track: {track_id}")
                    return True
                return False
    
    @staticmethod
    def get_track_count(status: Optional[str] = None) -> int:
        """
        Get the total number of tracks.
        
        Args:
            status: Optional status filter
        
        Returns:
            Number of tracks
        """
        if status:
            query = "SELECT COUNT(*) FROM audio_tracks WHERE status = %s"
            params = (status,)
        else:
            query = "SELECT COUNT(*) FROM audio_tracks"
            params = None
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return result[0] if result else 0
    
    @staticmethod
    def list_tracks(
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_dir: str = "DESC"
    ) -> List[Dict[str, Any]]:
        """
        List tracks with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Result offset
            order_by: Column to sort by
            order_dir: Sort direction (ASC or DESC)
        
        Returns:
            List of track records
        """
        # Validate order_by to prevent SQL injection
        allowed_columns = [
            "created_at", "updated_at", "artist", "title",
            "album", "genre", "year", "duration"
        ]
        if order_by not in allowed_columns:
            order_by = "created_at"
        
        if order_dir.upper() not in ["ASC", "DESC"]:
            order_dir = "DESC"
        
        query = f"""
            SELECT * FROM audio_tracks
            ORDER BY {order_by} {order_dir}
            LIMIT %s OFFSET %s
        """
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (limit, offset))
                results = cur.fetchall()
                return [dict(row) for row in results]


def execute_raw_query(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """
    Execute a raw SQL query and return results.
    
    Args:
        query: SQL query
        params: Query parameters
    
    Returns:
        List of results as dictionaries
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            return [dict(row) for row in results]


def execute_raw_command(query: str, params: tuple = None, commit: bool = True) -> None:
    """
    Execute a raw SQL command (INSERT, UPDATE, DELETE).
    
    Args:
        query: SQL command
        params: Query parameters
        commit: Whether to commit the transaction
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if commit:
                conn.commit()


def check_database_availability() -> Dict[str, Any]:
    """
    Check database connectivity and health.

    Returns:
        Dict with availability status, connection type, response time, and error info
    """
    import time
    from .config import get_db_manager

    start_time = time.time()
    error_message = None

    try:
        db_manager = get_db_manager()

        # Try to get a connection and run a simple query
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()

                # Check if we got a valid result
                if result and result[0] == 1:
                    response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
                    db_manager.return_connection(conn)

                    return {
                        "available": True,
                        "connection_type": "postgresql_pool",
                        "response_time_ms": response_time,
                        "error": None
                    }
                else:
                    error_message = "Invalid response from database"

        except Exception as e:
            error_message = str(e)
        finally:
            if conn:
                db_manager.return_connection(conn)

    except Exception as e:
        error_message = str(e)

    # Return failure status
    response_time = int((time.time() - start_time) * 1000)
    return {
        "available": False,
        "connection_type": "postgresql_pool",
        "response_time_ms": response_time,
        "error": error_message
    }

