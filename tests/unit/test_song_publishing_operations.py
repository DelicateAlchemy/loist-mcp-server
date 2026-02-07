"""
Unit tests for song publishing database operations.

Tests cover:
- Party CRUD operations (create, get, search)
- Work CRUD operations (create, get, search)
- Junction table batch operations (replace writers, replace publishers)
- Split warning calculation
- Recording artist operations (link, unlink)
- Error handling and validation
- Edge cases (NULL splits, >100% splits, empty lists)
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from psycopg2 import IntegrityError, DatabaseError
from psycopg2.extras import RealDictCursor

pytestmark = pytest.mark.requires_db

from database.operations import (
    create_party,
    get_party_by_id,
    search_parties,
    create_work,
    get_work_by_id,
    search_works,
    replace_work_writers,
    replace_work_publishers,
    calculate_split_warnings,
    link_artist_to_recording,
    unlink_artist_from_recording,
)
from src.exceptions import ValidationError, DatabaseOperationError, ResourceNotFoundError


class TestPartyOperations:
    """Test party CRUD and search operations."""

    def test_create_party_person(self):
        """Test creating a person party."""
        party_data = {
            'name': 'John Smith',
            'party_type': 'person',
            'email': 'john@example.com',
        }
        result = create_party(party_data)
        
        assert result['name'] == 'John Smith'
        assert result['party_type'] == 'person'
        assert result['email'] == 'john@example.com'
        assert uuid.UUID(result['id'])  # Valid UUID

    def test_create_party_organization(self):
        """Test creating an organization party."""
        party_data = {
            'name': 'Sony Music',
            'party_type': 'organization',
            'legal_name': 'Sony Music Entertainment',
        }
        result = create_party(party_data)
        
        assert result['name'] == 'Sony Music'
        assert result['party_type'] == 'organization'
        assert result['legal_name'] == 'Sony Music Entertainment'

    def test_create_party_with_industry_ids(self):
        """Test creating party with IPI/CAE and ISNI."""
        party_data = {
            'name': 'Jane Doe',
            'party_type': 'person',
            'ipi_cae_number': '12345678901',
            'isni': '0000000123456789',
            'society_affiliation': 'PRS',
        }
        result = create_party(party_data)
        
        assert result['ipi_cae_number'] == '12345678901'
        assert result['isni'] == '0000000123456789'
        assert result['society_affiliation'] == 'PRS'

    def test_create_party_missing_name(self):
        """Test creating party without required name."""
        party_data = {'party_type': 'person'}
        with pytest.raises(ValidationError, match="Name is required"):
            create_party(party_data)

    def test_create_party_invalid_type(self):
        """Test creating party with invalid party_type."""
        party_data = {'name': 'Test', 'party_type': 'invalid'}
        with pytest.raises(ValidationError, match="Invalid party_type"):
            create_party(party_data)

    def test_create_party_duplicate_ipi(self):
        """Test creating party with duplicate IPI/CAE."""
        party_data1 = {
            'name': 'Person 1',
            'party_type': 'person',
            'ipi_cae_number': '12345678901',
        }
        create_party(party_data1)
        
        party_data2 = {
            'name': 'Person 2',
            'party_type': 'person',
            'ipi_cae_number': '12345678901',
        }
        with pytest.raises(ValidationError, match="IPI/CAE number already exists"):
            create_party(party_data2)

    def test_get_party_by_id(self):
        """Test retrieving party by ID."""
        party_data = {
            'name': 'Test Person',
            'party_type': 'person',
        }
        created = create_party(party_data)
        
        result = get_party_by_id(created['id'])
        
        assert result is not None
        assert result['id'] == created['id']
        assert result['name'] == 'Test Person'
        assert 'works_as_writer' in result
        assert 'works_as_publisher' in result
        assert 'recordings_as_artist' in result

    def test_get_party_by_id_not_found(self):
        """Test retrieving non-existent party."""
        fake_id = str(uuid.uuid4())
        result = get_party_by_id(fake_id)
        assert result is None

    def test_get_party_by_id_invalid_uuid(self):
        """Test retrieving party with invalid UUID."""
        with pytest.raises(ValidationError, match="Invalid party_id format"):
            get_party_by_id('not-a-uuid')

    def test_search_parties(self):
        """Test searching parties by name."""
        # Create test parties
        create_party({'name': 'John Smith', 'party_type': 'person'})
        create_party({'name': 'Jane Smith', 'party_type': 'person'})
        create_party({'name': 'Bob Jones', 'party_type': 'person'})
        
        results = search_parties('Smith')
        
        assert len(results) >= 2
        assert all('Smith' in party['name'] for party in results)

    def test_search_parties_empty_query(self):
        """Test search with empty query."""
        with pytest.raises(ValidationError, match="Search query cannot be empty"):
            search_parties('')

    def test_search_parties_invalid_limit(self):
        """Test search with invalid limit."""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            search_parties('test', limit=0)
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            search_parties('test', limit=101)

    def test_search_parties_invalid_offset(self):
        """Test search with invalid offset."""
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            search_parties('test', offset=-1)


class TestWorkOperations:
    """Test work CRUD and search operations."""

    def test_create_work(self):
        """Test creating a work."""
        work_data = {
            'title': 'Test Song',
            'language': 'en',
            'status': 'draft',
        }
        result = create_work(work_data)
        
        assert result['title'] == 'Test Song'
        assert result['language'] == 'en'
        assert result['status'] == 'draft'
        assert uuid.UUID(result['id'])  # Valid UUID

    def test_create_work_default_status(self):
        """Test creating work with default status."""
        work_data = {'title': 'Test Song'}
        result = create_work(work_data)
        assert result['status'] == 'draft'

    def test_create_work_with_iswc(self):
        """Test creating work with ISWC."""
        work_data = {
            'title': 'Test Song',
            'iswc': 'T-123456789-0',
        }
        result = create_work(work_data)
        assert result['iswc'] == 'T-123456789-0'

    def test_create_work_missing_title(self):
        """Test creating work without required title."""
        work_data = {'status': 'draft'}
        with pytest.raises(ValidationError, match="Title is required"):
            create_work(work_data)

    def test_create_work_invalid_status(self):
        """Test creating work with invalid status."""
        work_data = {'title': 'Test', 'status': 'invalid'}
        with pytest.raises(ValidationError, match="Invalid status"):
            create_work(work_data)

    def test_create_work_duplicate_iswc(self):
        """Test creating work with duplicate ISWC."""
        work_data1 = {'title': 'Song 1', 'iswc': 'T-123456789-0'}
        create_work(work_data1)
        
        work_data2 = {'title': 'Song 2', 'iswc': 'T-123456789-0'}
        with pytest.raises(ValidationError, match="ISWC already exists"):
            create_work(work_data2)

    def test_get_work_by_id(self):
        """Test retrieving work by ID with all relations."""
        work_data = {'title': 'Test Work'}
        created = create_work(work_data)
        
        result = get_work_by_id(created['id'])
        
        assert result is not None
        assert result['id'] == created['id']
        assert result['title'] == 'Test Work'
        assert 'writers' in result
        assert 'publishers' in result
        assert 'alternative_titles' in result
        assert 'recordings' in result
        assert 'warnings' in result
        assert isinstance(result['warnings'], list)

    def test_get_work_by_id_not_found(self):
        """Test retrieving non-existent work."""
        fake_id = str(uuid.uuid4())
        result = get_work_by_id(fake_id)
        assert result is None

    def test_get_work_by_id_invalid_uuid(self):
        """Test retrieving work with invalid UUID."""
        with pytest.raises(ValidationError, match="Invalid work_id format"):
            get_work_by_id('not-a-uuid')

    def test_search_works(self):
        """Test searching works by title."""
        create_work({'title': 'Bohemian Rhapsody'})
        create_work({'title': 'Bohemian Nights'})
        create_work({'title': 'Another Song'})
        
        results = search_works('Bohemian')
        
        assert len(results) >= 2
        assert all('Bohemian' in work['title'] for work in results)

    def test_search_works_empty_query(self):
        """Test search with empty query."""
        with pytest.raises(ValidationError, match="Search query cannot be empty"):
            search_works('')

    def test_search_works_invalid_limit(self):
        """Test search with invalid limit."""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            search_works('test', limit=0)


class TestJunctionTableOperations:
    """Test batch replace operations for writers and publishers."""

    def test_replace_work_writers(self):
        """Test replacing work writers."""
        # Create work and parties
        work = create_work({'title': 'Test Work'})
        party1 = create_party({'name': 'Writer 1', 'party_type': 'person'})
        party2 = create_party({'name': 'Writer 2', 'party_type': 'person'})
        
        writers = [
            {
                'party_id': party1['id'],
                'split_percentage': 50.0,
                'split_status': 'confirmed',
            },
            {
                'party_id': party2['id'],
                'split_percentage': 50.0,
                'split_status': 'confirmed',
            },
        ]
        
        result = replace_work_writers(work['id'], writers)
        
        assert result['replaced_count'] == 2
        assert result['work_id'] == work['id']
        
        # Verify writers were added
        work_result = get_work_by_id(work['id'])
        assert len(work_result['writers']) == 2

    def test_replace_work_writers_with_null_split(self):
        """Test replacing writers with NULL split percentage."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        writers = [
            {
                'party_id': party['id'],
                'split_percentage': None,
                'split_status': 'unknown',
            },
        ]
        
        result = replace_work_writers(work['id'], writers)
        assert result['replaced_count'] == 1

    def test_replace_work_writers_empty_list(self):
        """Test replacing with empty list (removes all writers)."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        # Add a writer first
        replace_work_writers(work['id'], [
            {'party_id': party['id'], 'split_percentage': 100.0, 'split_status': 'confirmed'}
        ])
        
        # Remove all writers
        result = replace_work_writers(work['id'], [])
        assert result['replaced_count'] == 0
        
        work_result = get_work_by_id(work['id'])
        assert len(work_result['writers']) == 0

    def test_replace_work_writers_nonexistent_work(self):
        """Test replacing writers for non-existent work."""
        fake_work_id = str(uuid.uuid4())
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        with pytest.raises(ResourceNotFoundError, match="Work not found"):
            replace_work_writers(fake_work_id, [
                {'party_id': party['id'], 'split_percentage': 100.0, 'split_status': 'confirmed'}
            ])

    def test_replace_work_writers_invalid_work_id(self):
        """Test with invalid work_id."""
        with pytest.raises(ValidationError, match="Invalid work_id format"):
            replace_work_writers('not-a-uuid', [])

    def test_replace_work_writers_missing_party_id(self):
        """Test with missing party_id."""
        work = create_work({'title': 'Test Work'})
        writers = [{'split_percentage': 100.0, 'split_status': 'confirmed'}]
        
        with pytest.raises(ValidationError, match="missing required field: party_id"):
            replace_work_writers(work['id'], writers)

    def test_replace_work_writers_invalid_split_status(self):
        """Test with invalid split_status."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        writers = [
            {'party_id': party['id'], 'split_percentage': 100.0, 'split_status': 'invalid'}
        ]
        
        with pytest.raises(ValidationError, match="invalid split_status"):
            replace_work_writers(work['id'], writers)

    def test_replace_work_writers_invalid_split_percentage(self):
        """Test with invalid split_percentage."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        # Test negative
        writers = [
            {'party_id': party['id'], 'split_percentage': -10.0, 'split_status': 'confirmed'}
        ]
        with pytest.raises(ValidationError, match="Must be between 0 and 200"):
            replace_work_writers(work['id'], writers)
        
        # Test > 200
        writers = [
            {'party_id': party['id'], 'split_percentage': 250.0, 'split_status': 'confirmed'}
        ]
        with pytest.raises(ValidationError, match="Must be between 0 and 200"):
            replace_work_writers(work['id'], writers)

    def test_replace_work_publishers(self):
        """Test replacing work publishers."""
        work = create_work({'title': 'Test Work'})
        publisher = create_party({'name': 'Publisher', 'party_type': 'organization'})
        
        publishers = [
            {
                'party_id': publisher['id'],
                'split_percentage': 50.0,
                'split_status': 'confirmed',
            },
        ]
        
        result = replace_work_publishers(work['id'], publishers)
        assert result['replaced_count'] == 1


class TestSplitWarnings:
    """Test split warning calculation."""

    def test_calculate_split_warnings_complete(self):
        """Test warnings for complete splits (100%)."""
        work = create_work({'title': 'Test Work'})
        party1 = create_party({'name': 'Writer 1', 'party_type': 'person'})
        party2 = create_party({'name': 'Writer 2', 'party_type': 'person'})
        
        replace_work_writers(work['id'], [
            {'party_id': party1['id'], 'split_percentage': 50.0, 'split_status': 'confirmed'},
            {'party_id': party2['id'], 'split_percentage': 50.0, 'split_status': 'confirmed'},
        ])
        
        warnings = calculate_split_warnings(work['id'])
        assert len(warnings) == 0  # No warnings for 100%

    def test_calculate_split_warnings_incomplete(self):
        """Test warnings for incomplete splits (< 100%)."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        replace_work_writers(work['id'], [
            {'party_id': party['id'], 'split_percentage': 50.0, 'split_status': 'confirmed'},
        ])
        
        warnings = calculate_split_warnings(work['id'])
        assert len(warnings) > 0
        assert any('only add up to' in w for w in warnings)

    def test_calculate_split_warnings_empty_writers(self):
        """Test that empty writers don't trigger warnings (draft state)."""
        work = create_work({'title': 'Test Work'})
        
        warnings = calculate_split_warnings(work['id'])
        # Should not warn about 0% when there are no writers (draft state)
        assert not any('only add up to 0.00%' in w for w in warnings)

    def test_calculate_split_warnings_over_100(self):
        """Test warnings for over-claimed splits (> 100%)."""
        work = create_work({'title': 'Test Work'})
        party1 = create_party({'name': 'Writer 1', 'party_type': 'person'})
        party2 = create_party({'name': 'Writer 2', 'party_type': 'person'})
        
        replace_work_writers(work['id'], [
            {'party_id': party1['id'], 'split_percentage': 60.0, 'split_status': 'confirmed'},
            {'party_id': party2['id'], 'split_percentage': 60.0, 'split_status': 'confirmed'},
        ])
        
        warnings = calculate_split_warnings(work['id'])
        assert len(warnings) > 0
        assert any('exceed 100%' in w for w in warnings)

    def test_calculate_split_warnings_disputed(self):
        """Test warnings for disputed splits."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        replace_work_writers(work['id'], [
            {'party_id': party['id'], 'split_percentage': 50.0, 'split_status': 'disputed'},
        ])
        
        warnings = calculate_split_warnings(work['id'])
        assert len(warnings) > 0
        assert any('disputed' in w for w in warnings)

    def test_calculate_split_warnings_null_splits(self):
        """Test warnings with NULL split percentages."""
        work = create_work({'title': 'Test Work'})
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        
        replace_work_writers(work['id'], [
            {'party_id': party['id'], 'split_percentage': None, 'split_status': 'unknown'},
        ])
        
        warnings = calculate_split_warnings(work['id'])
        # Should not error, but may have warnings about incomplete splits
        assert isinstance(warnings, list)

    def test_calculate_split_warnings_invalid_work_id(self):
        """Test with invalid work_id."""
        with pytest.raises(ValidationError, match="Invalid work_id format"):
            calculate_split_warnings('not-a-uuid')


class TestRecordingArtistOperations:
    """Test recording artist link/unlink operations."""

    def test_link_artist_to_recording(self):
        """Test linking artist to recording."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        # Create audio track (using existing function)
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work (migration 010 requires work_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        
        result = link_artist_to_recording(track['id'], party['id'], is_primary=True)
        
        assert result['audio_track_id'] == track['id']
        assert result['party_id'] == party['id']
        assert result['is_primary'] is True

    def test_link_artist_to_recording_featuring(self):
        """Test linking featuring artist."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Featuring Artist', 'party_type': 'person'})
        
        result = link_artist_to_recording(track['id'], party['id'], is_primary=False)
        assert result['is_primary'] is False

    def test_link_artist_duplicate(self):
        """Test linking same artist twice (should fail)."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        
        link_artist_to_recording(track['id'], party['id'])
        
        with pytest.raises(ValidationError, match="already linked"):
            link_artist_to_recording(track['id'], party['id'])

    def test_link_artist_invalid_track_id(self):
        """Test with invalid track_id."""
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        
        with pytest.raises(ValidationError, match="Invalid audio_track_id format"):
            link_artist_to_recording('not-a-uuid', party['id'])

    def test_unlink_artist_from_recording(self):
        """Test unlinking artist from recording."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        
        link_artist_to_recording(track['id'], party['id'])
        
        result = unlink_artist_from_recording(track['id'], party['id'])
        assert result is True

    def test_unlink_artist_not_linked(self):
        """Test unlinking artist that's not linked."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        
        result = unlink_artist_from_recording(track['id'], party['id'])
        assert result is False

    def test_unlink_artist_invalid_ids(self):
        """Test with invalid UUIDs."""
        with pytest.raises(ValidationError, match="Invalid audio_track_id format"):
            unlink_artist_from_recording('not-a-uuid', str(uuid.uuid4()))


class TestPartyWorksInvolvement:
    """Test party involvement in works (writers, publishers, recordings)."""

    def test_get_party_with_works_as_writer(self):
        """Test party with works as writer."""
        party = create_party({'name': 'Writer', 'party_type': 'person'})
        work = create_work({'title': 'Test Work'})
        
        replace_work_writers(work['id'], [
            {'party_id': party['id'], 'split_percentage': 100.0, 'split_status': 'confirmed'},
        ])
        
        result = get_party_by_id(party['id'])
        
        assert len(result['works_as_writer']) == 1
        assert result['works_as_writer'][0]['work_id'] == work['id']
        assert result['works_as_writer'][0]['work_title'] == 'Test Work'

    def test_get_party_with_works_as_publisher(self):
        """Test party with works as publisher."""
        party = create_party({'name': 'Publisher', 'party_type': 'organization'})
        work = create_work({'title': 'Test Work'})
        
        replace_work_publishers(work['id'], [
            {'party_id': party['id'], 'split_percentage': 50.0, 'split_status': 'confirmed'},
        ])
        
        result = get_party_by_id(party['id'])
        
        assert len(result['works_as_publisher']) == 1
        assert result['works_as_publisher'][0]['work_id'] == work['id']

    def test_get_party_with_recordings_as_artist(self):
        """Test party with recordings as artist."""
        # Create work first (required by migration 010)
        work = create_work({'title': 'Test Track'})
        
        from database.operations import save_audio_metadata
        from database.pool import get_connection
        track = save_audio_metadata(
            {'title': 'Test Track', 'format': 'MP3'},
            'gs://test/audio.mp3'
        )
        
        # Link track to work
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audio_tracks SET work_id = %s WHERE id = %s", (work['id'], track['id']))
                conn.commit()
        
        party = create_party({'name': 'Artist', 'party_type': 'person'})
        link_artist_to_recording(track['id'], party['id'])
        
        result = get_party_by_id(party['id'])
        
        assert len(result['recordings_as_artist']) == 1
        assert result['recordings_as_artist'][0]['audio_track_id'] == track['id']

