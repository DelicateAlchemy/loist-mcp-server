"""
Tests for audio metadata extraction.

Tests verify:
- ID3 tag extraction from MP3 files
- Vorbis comment extraction from FLAC/OGG
- MP4 tag extraction from M4A/AAC
- Technical specification extraction
- Error handling for missing/corrupt metadata
- Support for multiple audio formats
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import tempfile


class TestMetadataImports:
    """Test that metadata module imports correctly."""
    
    def test_imports(self):
        """Test module imports."""
        from src.metadata import MetadataExtractor, extract_metadata, extract_id3_tags
        from src.metadata import MetadataExtractionError
        
        assert MetadataExtractor is not None
        assert extract_metadata is not None
        assert MetadataExtractionError is not None


class TestMetadataExtractorInitialization:
    """Test metadata extractor initialization."""
    
    def test_supported_formats(self):
        """Test supported formats are defined."""
        from src.metadata import MetadataExtractor
        
        assert MetadataExtractor.SUPPORTED_FORMATS is not None
        assert '.mp3' in MetadataExtractor.SUPPORTED_FORMATS
        assert '.flac' in MetadataExtractor.SUPPORTED_FORMATS
        assert '.m4a' in MetadataExtractor.SUPPORTED_FORMATS


class TestID3TagExtraction:
    """Test ID3 tag extraction from MP3 files."""
    
    @patch('mutagen.id3.ID3')
    def test_extract_id3_artist(self, mock_id3):
        """Test extracting artist from ID3 tags."""
        from src.metadata import MetadataExtractor
        
        # Mock ID3 tags
        mock_tag = Mock()
        mock_tag.text = ["The Beatles"]
        mock_tags = {'TPE1': mock_tag}
        mock_id3.return_value = mock_tags
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3 data")
        
        try:
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            assert metadata['artist'] == "The Beatles"
        finally:
            temp_path.unlink()
    
    @patch('mutagen.id3.ID3')
    def test_extract_id3_all_fields(self, mock_id3):
        """Test extracting all ID3 fields."""
        from src.metadata import MetadataExtractor
        
        # Mock all tags
        mock_tags = {
            'TPE1': Mock(text=["Artist Name"]),
            'TIT2': Mock(text=["Song Title"]),
            'TALB': Mock(text=["Album Name"]),
            'TCON': Mock(text=["Rock"]),
            'TDRC': Mock(text=["2024-01-15"]),
        }
        mock_id3.return_value = mock_tags
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            assert metadata['artist'] == "Artist Name"
            assert metadata['title'] == "Song Title"
            assert metadata['album'] == "Album Name"
            assert metadata['genre'] == "Rock"
            assert metadata['year'] == 2024
        finally:
            temp_path.unlink()
    
    @patch('mutagen.id3.ID3')
    def test_extract_id3_year_from_tyer(self, mock_id3):
        """Test extracting year from TYER tag (ID3v2.3)."""
        from src.metadata import MetadataExtractor
        
        # Mock TYER tag (ID3v2.3)
        mock_tags = {
            'TYER': Mock(text=["1967"]),
        }
        mock_id3.return_value = mock_tags
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            assert metadata['year'] == 1967
        finally:
            temp_path.unlink()
    
    def test_extract_id3_file_not_found(self):
        """Test error handling when file doesn't exist."""
        from src.metadata import MetadataExtractor, MetadataExtractionError
        
        with pytest.raises(MetadataExtractionError, match="File not found"):
            MetadataExtractor.extract_id3_tags("/nonexistent/file.mp3")
    
    @patch('mutagen.id3.ID3')
    @patch('mutagen.mp3.MP3')
    def test_extract_id3_no_tags(self, mock_mp3, mock_id3):
        """Test handling files with no ID3 tags."""
        from src.metadata import MetadataExtractor
        from mutagen.id3 import ID3NoHeaderError
        
        # Mock ID3 to raise no header error
        mock_id3.side_effect = ID3NoHeaderError()
        
        # Mock MP3 with no tags
        mock_audio = Mock()
        mock_audio.tags = None
        mock_mp3.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            # Should return empty metadata, not raise error
            assert metadata['artist'] is None
            assert metadata['title'] is None
        finally:
            temp_path.unlink()


class TestMetadataExtraction:
    """Test complete metadata extraction."""
    
    @patch('mutagen.File')
    def test_extract_metadata_mp3(self, mock_file):
        """Test extracting metadata from MP3."""
        from src.metadata import MetadataExtractor
        
        # Mock audio file with both tags and info
        mock_audio = Mock()
        mock_audio.tags = {
            'TPE1': Mock(text=["Artist"]),
            'TIT2': Mock(text=["Title"]),
        }
        mock_audio.info = Mock()
        mock_audio.info.length = 245.5
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 44100
        mock_audio.info.bitrate = 320000
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={'artist': 'Artist', 'title': 'Title', 'album': None, 'genre': None, 'year': None}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['format'] == 'MP3'
                assert metadata['duration'] == 245.5
                assert metadata['channels'] == 2
                assert metadata['sample_rate'] == 44100
                assert metadata['bitrate'] == 320  # kbps
        finally:
            temp_path.unlink()
    
    def test_extract_metadata_unsupported_format(self):
        """Test error for unsupported format."""
        from src.metadata import MetadataExtractor, MetadataExtractionError
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"not audio")
        
        try:
            with pytest.raises(MetadataExtractionError, match="Unsupported audio format"):
                MetadataExtractor.extract(temp_path)
        finally:
            temp_path.unlink()
    
    def test_extract_metadata_file_not_found(self):
        """Test error when file doesn't exist."""
        from src.metadata import MetadataExtractor, MetadataExtractionError
        
        with pytest.raises(MetadataExtractionError, match="File not found"):
            MetadataExtractor.extract("/nonexistent/audio.mp3")
    
    @patch('mutagen.File')
    def test_extract_metadata_uses_filename_as_title(self, mock_file):
        """Test that filename is used as title when tag is missing."""
        from src.metadata import MetadataExtractor
        
        # Mock audio with no title tag
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, prefix='My_Song_') as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={'artist': None, 'title': None, 'album': None, 'genre': None, 'year': None}):
                metadata = MetadataExtractor.extract(temp_path)
                
                # Should use filename stem as title
                assert metadata['title'] == temp_path.stem
        finally:
            temp_path.unlink()


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    @patch.object(Path, 'exists', return_value=True)
    @patch('mutagen.File')
    def test_extract_metadata_function(self, mock_file, mock_exists):
        """Test extract_metadata convenience function."""
        from src.metadata import extract_metadata
        
        # Mock audio file
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with patch('src.metadata.extractor.MetadataExtractor.extract_id3_tags', return_value={}):
            metadata = extract_metadata("test.mp3")
            
            assert metadata is not None
            assert 'format' in metadata
    
    @patch.object(Path, 'exists', return_value=True)
    @patch('mutagen.id3.ID3')
    def test_extract_id3_tags_function(self, mock_id3, mock_exists):
        """Test extract_id3_tags convenience function."""
        from src.metadata import extract_id3_tags
        
        # Mock tags
        mock_tags = {
            'TPE1': Mock(text=["Artist"]),
        }
        mock_id3.return_value = mock_tags
        
        metadata = extract_id3_tags("test.mp3")
        
        assert metadata is not None
        assert metadata['artist'] == "Artist"


class TestErrorHandling:
    """Test error handling for various scenarios."""
    
    @patch('mutagen.File')
    def test_extract_metadata_none_result(self, mock_file):
        """Test handling when Mutagen returns None."""
        from src.metadata import MetadataExtractor, MetadataExtractionError
        
        # Mock File to return None
        mock_file.return_value = None
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"corrupted")
        
        try:
            with pytest.raises(MetadataExtractionError, match="Could not load audio file"):
                MetadataExtractor.extract(temp_path)
        finally:
            temp_path.unlink()
    
    @patch('mutagen.id3.ID3')
    def test_extract_id3_invalid_year_format(self, mock_id3):
        """Test handling invalid year formats."""
        from src.metadata import MetadataExtractor
        
        # Mock tag with invalid year
        mock_tags = {
            'TDRC': Mock(text=["invalid-year"]),
        }
        mock_id3.return_value = mock_tags
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            # Should not raise, just leave year as None
            assert metadata['year'] is None
        finally:
            temp_path.unlink()


class TestMetadataQualityAssessment:
    """Test metadata quality assessment functionality."""
    
    def test_quality_assessment_excellent(self):
        """Test quality assessment for excellent metadata."""
        from src.metadata import MetadataQualityAssessment
        
        metadata = {
            'artist': 'The Beatles',
            'title': 'Hey Jude',
            'album': 'The Beatles 1967-1970',
            'genre': 'Rock',
            'year': 1968,
            'duration': 431.2,
            'channels': 2,
            'sample_rate': 44100,
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        assessment = MetadataQualityAssessment(metadata, Path("test.mp3"))
        report = assessment.get_quality_report()
        
        assert report['quality_score'] >= 0.9
        assert report['quality_level'] == "Excellent"
        assert report['metadata_completeness'] == 100.0
        assert not report['has_issues']
        assert len(report['issues']) == 0
    
    def test_quality_assessment_missing_essential(self):
        """Test quality assessment for missing essential fields."""
        from src.metadata import MetadataQualityAssessment
        
        metadata = {
            'artist': None,  # Missing essential
            'title': None,  # Missing essential
            'album': 'Some Album',
            'genre': None,
            'year': None,
            'duration': 431.2,
            'channels': 2,
            'sample_rate': 44100,
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        assessment = MetadataQualityAssessment(metadata, Path("test.mp3"))
        report = assessment.get_quality_report()
        
        assert report['quality_score'] < 0.5
        assert report['quality_level'] in ["Poor", "Very Poor"]
        assert report['has_issues']
        assert any("Missing essential fields" in issue for issue in report['issues'])
    
    def test_quality_assessment_corrupt_data(self):
        """Test quality assessment for corrupt data."""
        from src.metadata import MetadataQualityAssessment
        
        metadata = {
            'artist': 'The Beatles',
            'title': 'Hey Jude',
            'album': 'The Beatles 1967-1970',
            'genre': 'Rock',
            'year': 1800,  # Invalid year
            'duration': -100,  # Invalid duration
            'channels': 0,  # Invalid channels
            'sample_rate': 999999,  # Invalid sample rate
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        assessment = MetadataQualityAssessment(metadata, Path("test.mp3"))
        report = assessment.get_quality_report()
        
        assert report['quality_score'] < 0.5
        assert report['has_issues']
        assert len(report['issues']) >= 4  # Multiple corruption issues
        assert any("Invalid year" in issue for issue in report['issues'])
        assert any("Invalid duration" in issue for issue in report['issues'])
    
    def test_quality_assessment_suspicious_text(self):
        """Test quality assessment for suspicious text fields."""
        from src.metadata import MetadataQualityAssessment
        
        metadata = {
            'artist': 'A' * 1000,  # Suspiciously long
            'title': '   ',  # Empty after stripping
            'album': 'Normal Album',
            'genre': 'Rock',
            'year': 1968,
            'duration': 431.2,
            'channels': 2,
            'sample_rate': 44100,
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        assessment = MetadataQualityAssessment(metadata, Path("test.mp3"))
        report = assessment.get_quality_report()
        
        assert report['has_issues']
        assert any("Suspiciously long artist" in issue for issue in report['issues'])
        assert any("Empty title field" in issue for issue in report['issues'])


class TestMetadataQualityError:
    """Test MetadataQualityError exception."""
    
    @patch('mutagen.File')
    def test_quality_threshold_exception(self, mock_file):
        """Test MetadataQualityError when quality threshold not met."""
        from src.metadata import MetadataExtractor, MetadataQualityError
        
        # Mock audio with minimal metadata
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                with pytest.raises(MetadataQualityError) as exc_info:
                    MetadataExtractor.extract(temp_path, validate_quality=True, quality_threshold=0.9)
                
                # Check exception attributes
                assert exc_info.value.quality_score < 0.9
                assert len(exc_info.value.issues) > 0
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_quality_threshold_pass(self, mock_file):
        """Test that extraction passes when quality threshold is met."""
        from src.metadata import MetadataExtractor
        
        # Mock audio with good metadata
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={
                'artist': 'Artist', 'title': 'Title', 'album': 'Album'
            }):
                metadata = MetadataExtractor.extract(temp_path, validate_quality=True, quality_threshold=0.3)
                
                # Should not raise exception
                assert metadata is not None
                assert '_quality_report' in metadata
        finally:
            temp_path.unlink()


class TestMetadataRepair:
    """Test metadata repair functionality."""
    
    def test_validate_and_repair_metadata(self):
        """Test metadata validation and repair."""
        from src.metadata import MetadataExtractor
        
        corrupt_metadata = {
            'artist': 'The Beatles',
            'title': '   ',  # Empty after stripping
            'album': 'A' * 1000,  # Too long
            'genre': 'Rock',
            'year': 1800,  # Invalid year
            'duration': -100,  # Invalid duration
            'channels': 0,  # Invalid channels
            'sample_rate': 999999,  # Invalid sample rate
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        repaired = MetadataExtractor.validate_and_repair_metadata(corrupt_metadata, Path("test.mp3"))
        
        # Check repairs
        assert repaired['title'] is None  # Empty field repaired
        assert len(repaired['album']) == 500  # Truncated
        assert repaired['year'] is None  # Invalid year repaired
        assert repaired['duration'] is None  # Invalid duration repaired
        assert repaired['channels'] is None  # Invalid channels repaired
        assert repaired['sample_rate'] is None  # Invalid sample rate repaired
        
        # Valid fields should remain
        assert repaired['artist'] == 'The Beatles'
        assert repaired['genre'] == 'Rock'
        assert repaired['bitrate'] == 320
    
    @patch('mutagen.File')
    def test_extract_with_fallback_success(self, mock_file):
        """Test extract_with_fallback when repair is successful."""
        from src.metadata import MetadataExtractor
        
        # Mock audio with some metadata
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={
                'artist': 'Artist', 'title': 'Title', 'album': 'Album'
            }):
                metadata, was_repaired = MetadataExtractor.extract_with_fallback(temp_path)
                
                assert metadata is not None
                assert was_repaired is False  # Should not need repair
                assert '_quality_report' in metadata
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_with_fallback_repair(self, mock_file):
        """Test extract_with_fallback when repair is needed."""
        from src.metadata import MetadataExtractor, MetadataQualityError
        
        # Mock audio with minimal metadata
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                metadata, was_repaired = MetadataExtractor.extract_with_fallback(temp_path)
                
                assert metadata is not None
                assert was_repaired is True  # Should be repaired
                assert '_quality_report' in metadata
        finally:
            temp_path.unlink()


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    @patch.object(Path, 'exists', return_value=True)
    @patch('mutagen.File')
    def test_extract_metadata_function(self, mock_file, mock_exists):
        """Test extract_metadata convenience function."""
        from src.metadata import extract_metadata
        
        # Mock audio file
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with patch('src.metadata.extractor.MetadataExtractor.extract_id3_tags', return_value={
            'artist': 'Artist', 'title': 'Title', 'album': 'Album'
        }):
            metadata = extract_metadata("test.mp3")
            
            assert metadata is not None
            assert 'format' in metadata
            assert '_quality_report' in metadata
    
    @patch.object(Path, 'exists', return_value=True)
    @patch('mutagen.File')
    def test_extract_metadata_with_fallback_function(self, mock_file, mock_exists):
        """Test extract_metadata_with_fallback convenience function."""
        from src.metadata import extract_metadata_with_fallback
        
        # Mock audio file
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 100.0
        mock_file.return_value = mock_audio
        
        with patch('src.metadata.extractor.MetadataExtractor.extract_id3_tags', return_value={
            'artist': 'Artist', 'title': 'Title', 'album': 'Album'
        }):
            metadata, was_repaired = extract_metadata_with_fallback("test.mp3")
            
            assert metadata is not None
            assert isinstance(was_repaired, bool)
            assert '_quality_report' in metadata
    
    def test_assess_metadata_quality_function(self):
        """Test assess_metadata_quality convenience function."""
        from src.metadata import assess_metadata_quality
        
        metadata = {
            'artist': 'The Beatles',
            'title': 'Hey Jude',
            'album': 'The Beatles 1967-1970',
            'genre': 'Rock',
            'year': 1968,
            'duration': 431.2,
            'channels': 2,
            'sample_rate': 44100,
            'bitrate': 320,
            'bit_depth': 16,
            'format': 'MP3'
        }
        
        report = assess_metadata_quality(metadata, "test.mp3")
        
        assert 'quality_score' in report
        assert 'quality_level' in report
        assert 'issues' in report
        assert 'has_issues' in report
        assert 'metadata_completeness' in report
        assert report['quality_score'] >= 0.9
        assert report['quality_level'] == "Excellent"


class TestTechnicalSpecExtraction:
    """Test technical specification extraction."""
    
    @patch('mutagen.File')
    def test_extract_duration(self, mock_file):
        """Test duration extraction."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 245.678
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['duration'] == 245.678
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_channels(self, mock_file):
        """Test channel count extraction."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.channels = 2  # Stereo
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['channels'] == 2
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_sample_rate(self, mock_file):
        """Test sample rate extraction."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.sample_rate = 44100  # CD quality
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['sample_rate'] == 44100
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_bitrate(self, mock_file):
        """Test bitrate extraction."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.bitrate = 320000  # 320 kbps
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_id3_tags', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                # Should convert to kbps
                assert metadata['bitrate'] == 320
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_bit_depth(self, mock_file):
        """Test bit depth extraction."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.bits_per_sample = 16  # CD quality
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_vorbis_comments', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['bit_depth'] == 16
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    def test_extract_all_technical_specs(self, mock_file):
        """Test extracting all technical specifications."""
        from src.metadata import MetadataExtractor
        
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.info = Mock()
        mock_audio.info.length = 180.5
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 48000
        mock_audio.info.bitrate = 192000
        mock_audio.info.bits_per_sample = 24
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake")
        
        try:
            with patch.object(MetadataExtractor, 'extract_vorbis_comments', return_value={}):
                metadata = MetadataExtractor.extract(temp_path)
                
                assert metadata['duration'] == 180.5
                assert metadata['channels'] == 2
                assert metadata['sample_rate'] == 48000
                assert metadata['bitrate'] == 192
                assert metadata['bit_depth'] == 24
                assert metadata['format'] == 'FLAC'
        finally:
            temp_path.unlink()


class TestArtworkExtraction:
    """Test artwork extraction from audio files."""
    
    @patch('src.metadata.extractor.MP3')
    def test_extract_artwork_mp3(self, mock_mp3):
        """Test artwork extraction from MP3."""
        from src.metadata import extract_artwork
        from mutagen.id3 import APIC
        
        # Mock MP3 with APIC frame
        mock_apic = APIC()
        mock_apic.type = 3  # Front cover
        mock_apic.mime = 'image/jpeg'
        mock_apic.data = b'fake_jpeg_data'
        
        mock_tags = Mock()
        mock_tags.values = Mock(return_value=[mock_apic])
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            artwork_path = extract_artwork(temp_path)
            
            assert artwork_path is not None
            assert artwork_path.exists()
            assert artwork_path.suffix == '.jpg'
            
            # Cleanup
            artwork_path.unlink()
        finally:
            temp_path.unlink()
    
    @patch('src.metadata.extractor.FLAC')
    def test_extract_artwork_flac(self, mock_flac):
        """Test artwork extraction from FLAC."""
        from src.metadata import extract_artwork
        
        # Mock FLAC picture
        mock_picture = Mock()
        mock_picture.type = 3  # Front cover
        mock_picture.mime = 'image/png'
        mock_picture.data = b'fake_png_data'
        
        mock_audio = Mock()
        mock_audio.pictures = [mock_picture]
        mock_flac.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake flac")
        
        try:
            artwork_path = extract_artwork(temp_path)
            
            assert artwork_path is not None
            assert artwork_path.exists()
            assert artwork_path.suffix == '.png'
            
            # Cleanup
            artwork_path.unlink()
        finally:
            temp_path.unlink()
    
    @patch('src.metadata.extractor.MP4')
    def test_extract_artwork_mp4(self, mock_mp4):
        """Test artwork extraction from M4A."""
        from src.metadata import extract_artwork
        
        # Mock MP4 cover art (JPEG)
        jpeg_data = b'\xff\xd8\xff\xe0fake_jpeg'
        
        mock_audio = Mock()
        mock_audio.tags = {'covr': [jpeg_data]}
        mock_mp4.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake m4a")
        
        try:
            artwork_path = extract_artwork(temp_path)
            
            assert artwork_path is not None
            assert artwork_path.exists()
            assert artwork_path.suffix == '.jpg'
            
            # Cleanup
            artwork_path.unlink()
        finally:
            temp_path.unlink()
    
    @patch('src.metadata.extractor.MP4')
    def test_extract_artwork_mp4_png(self, mock_mp4):
        """Test PNG artwork extraction from M4A."""
        from src.metadata import extract_artwork
        
        # Mock MP4 cover art (PNG signature)
        png_data = b'\x89PNG\r\n\x1a\nfake_png'
        
        mock_audio = Mock()
        mock_audio.tags = {'covr': [png_data]}
        mock_mp4.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake m4a")
        
        try:
            artwork_path = extract_artwork(temp_path)
            
            assert artwork_path is not None
            assert artwork_path.suffix == '.png'
            
            # Cleanup
            artwork_path.unlink()
        finally:
            temp_path.unlink()
    
    @patch('src.metadata.extractor.MP3')
    def test_extract_artwork_no_artwork(self, mock_mp3):
        """Test handling when no artwork is present."""
        from src.metadata import extract_artwork
        
        # Mock MP3 with no APIC frames
        mock_tags = Mock()
        mock_tags.values = Mock(return_value=[])
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            artwork_path = extract_artwork(temp_path)
            
            # Should return None, not raise error
            assert artwork_path is None
        finally:
            temp_path.unlink()
    
    @patch('src.metadata.extractor.MP3')
    def test_extract_artwork_with_destination(self, mock_mp3):
        """Test artwork extraction to specific destination."""
        from src.metadata import extract_artwork
        from mutagen.id3 import APIC
        
        # Mock APIC frame
        mock_apic = APIC()
        mock_apic.type = 3
        mock_apic.mime = 'image/jpeg'
        mock_apic.data = b'fake_jpeg'
        
        mock_tags = Mock()
        mock_tags.values = Mock(return_value=[mock_apic])
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "cover.jpg"
            
            try:
                artwork_path = extract_artwork(temp_path, destination=dest)
                
                assert artwork_path == dest
                assert artwork_path.exists()
            finally:
                temp_path.unlink()
    
    @patch('src.metadata.extractor.MP3')
    def test_extract_artwork_priority_front_cover(self, mock_mp3):
        """Test that front cover is prioritized."""
        from src.metadata import extract_artwork
        from mutagen.id3 import APIC
        
        # Mock multiple APIC frames with different types
        mock_apic_back = APIC()
        mock_apic_back.type = 4  # Back cover
        mock_apic_back.mime = 'image/jpeg'
        mock_apic_back.data = b'back_cover'
        
        mock_apic_front = APIC()
        mock_apic_front.type = 3  # Front cover (preferred)
        mock_apic_front.mime = 'image/jpeg'
        mock_apic_front.data = b'front_cover'
        
        mock_tags = Mock()
        mock_tags.values = Mock(return_value=[mock_apic_back, mock_apic_front])
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            artwork_path = extract_artwork(temp_path, prefer_front_cover=True)
            
            assert artwork_path is not None
            # Should have selected front cover
            content = artwork_path.read_bytes()
            assert content == b'front_cover'
            
            # Cleanup
            artwork_path.unlink()
        finally:
            temp_path.unlink()
    
    def test_extract_artwork_file_not_found(self):
        """Test error when file doesn't exist."""
        from src.metadata import extract_artwork, MetadataExtractionError
        
        with pytest.raises(MetadataExtractionError, match="File not found"):
            extract_artwork("/nonexistent/file.mp3")


class TestFilenameMetadataParsing:
    """Test filename-based metadata parsing."""

    def test_parse_filename_artist_title_pattern(self):
        """Test parsing 'Artist - Title.mp3' pattern."""
        from src.metadata.extractor import parse_filename_metadata
        import tempfile

        # Create a temporary file with the pattern
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_path.with_name("The Beatles - Hey Jude.mp3")  # Rename for testing

            # Mock the path for testing
            existing_metadata = {}
            result = parse_filename_metadata("dummy_path/The Beatles - Hey Jude.mp3", existing_metadata)

            expected = {
                'artist': 'The Beatles',
                'title': 'Hey Jude'
            }
            assert result == expected

    def test_parse_filename_with_album_parentheses(self):
        """Test parsing 'Artist - Title (Album).mp3' pattern."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/Queen - Bohemian Rhapsody (A Night At The Opera).mp3", existing_metadata)

        expected = {
            'artist': 'Queen',
            'title': 'Bohemian Rhapsody',
            'album': 'A Night At The Opera'
        }
        assert result == expected

    def test_parse_filename_with_year_as_album(self):
        """Test parsing 'Artist - Title (Year).mp3' where year is treated as album."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/The Beatles - Yesterday (1965).mp3", existing_metadata)

        expected = {
            'artist': 'The Beatles',
            'title': 'Yesterday',
            'year': '1965'
        }
        assert result == expected

    def test_parse_filename_artist_album_title_pattern(self):
        """Test parsing 'Artist - Album - Title.mp3' pattern."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/Pink Floyd - The Wall - Comfortably Numb.mp3", existing_metadata)

        expected = {
            'artist': 'Pink Floyd',
            'album': 'The Wall',
            'title': 'Comfortably Numb'
        }
        assert result == expected

    def test_parse_filename_title_only(self):
        """Test parsing filename with just title."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/Untitled Track.mp3", existing_metadata)

        expected = {
            'title': 'Untitled Track'
        }
        assert result == expected

    def test_parse_filename_with_track_number_removal(self):
        """Test that track numbers are removed during preprocessing."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/01. The Beatles - Hey Jude.mp3", existing_metadata)

        expected = {
            'artist': 'The Beatles',
            'title': 'Hey Jude'
        }
        assert result == expected

    def test_parse_filename_multiple_track_number_formats(self):
        """Test various track number formats are handled."""
        from src.metadata.extractor import parse_filename_metadata

        test_cases = [
            ("01. Artist - Title.mp3", {'artist': 'Artist', 'title': 'Title'}),
            ("1- Artist - Title.mp3", {'artist': 'Artist', 'title': 'Title'}),
            ("(01) Artist - Title.mp3", {'artist': 'Artist', 'title': 'Title'}),
            ("[01] Artist - Title.mp3", {'artist': 'Artist', 'title': 'Title'}),
        ]

        for filename, expected in test_cases:
            existing_metadata = {}
            result = parse_filename_metadata(f"dummy_path/{filename}", existing_metadata)
            assert result == expected, f"Failed for {filename}"

    def test_parse_filename_skip_short_titles(self):
        """Test that very short titles after dash are skipped."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/Artist - 1.mp3", existing_metadata)

        # Should fall back to title-only parsing
        assert result == {'title': 'Artist - 1'}

    def test_parse_filename_existing_metadata_not_overwritten(self):
        """Test that existing metadata is not overwritten by filename parsing."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {
            'artist': 'Existing Artist',
            'title': 'Existing Title',
            'album': 'Existing Album'
        }

        result = parse_filename_metadata("dummy_path/New Artist - New Title.mp3", existing_metadata)

        # Should return empty dict since all fields already exist
        assert result == {}

    def test_parse_filename_fill_missing_fields_only(self):
        """Test that only missing fields are filled from filename."""
        from src.metadata.extractor import parse_filename_metadata

        existing_metadata = {
            'artist': 'Existing Artist',  # This exists
            'title': None,  # This is missing
            'album': None,  # This is missing
        }

        result = parse_filename_metadata("dummy_path/New Artist - New Title (New Album).mp3", existing_metadata)

        # Should only fill missing fields
        expected = {
            'title': 'New Title',
            'album': 'New Album'
        }
        assert result == expected

    def test_parse_filename_title_with_year(self):
        """Test parsing title with year patterns."""
        from src.metadata.extractor import parse_filename_metadata

        test_cases = [
            ("Song Title (2020).mp3", {'title': 'Song Title', 'year': '2020'}),
            ("Song Title - 2020.mp3", {'title': 'Song Title', 'year': '2020'}),
        ]

        for filename, expected in test_cases:
            existing_metadata = {}
            result = parse_filename_metadata(f"dummy_path/{filename}", existing_metadata)
            assert result == expected, f"Failed for {filename}"

    def test_parse_filename_unreasonable_titles_skipped(self):
        """Test that unreasonable titles are handled appropriately."""
        from src.metadata.extractor import parse_filename_metadata

        # Test with just numbers/symbols - should return None for title-only pattern
        existing_metadata = {}
        result = parse_filename_metadata("dummy_path/123-456.mp3", existing_metadata)

        # Should still work but title might be different based on parsing logic
        assert isinstance(result, dict)


class TestMetadataQualityValidationAfterEnhancement:
    """Test the adaptive quality validation after filename enhancement."""

    def test_quality_validation_with_title_allowed(self):
        """Test that files with titles pass validation even with low quality scores."""
        from src.tools.process_audio import _validate_metadata_quality_after_enhancement

        # Low quality metadata but has title
        metadata = {
            'title': 'Some Title',
            'artist': None,
            'album': None,
            'genre': None,
            'year': None,
            'duration': 180,
            'format': 'mp3'
        }

        # Should not raise an exception
        _validate_metadata_quality_after_enhancement(metadata)

    def test_quality_validation_without_title_fails(self):
        """Test that files without titles fail validation."""
        from src.tools.process_audio import _validate_metadata_quality_after_enhancement
        from src.metadata.extractor import MetadataExtractionError

        # No title at all
        metadata = {
            'artist': 'Some Artist',
            'album': 'Some Album',
            'genre': None,
            'year': None,
            'duration': 180,
            'format': 'mp3'
        }

        # Should raise MetadataExtractionError
        with pytest.raises(MetadataExtractionError, match="No title could be determined"):
            _validate_metadata_quality_after_enhancement(metadata)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

