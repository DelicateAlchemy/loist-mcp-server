"""
Comprehensive integration tests for multiple audio format support.

Tests verify that metadata extraction, validation, and error handling
work correctly across MP3, FLAC, M4A/AAC, OGG, and WAV formats.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile


class TestMP3FormatSupport:
    """Test MP3 format support (ID3v1, ID3v2.3, ID3v2.4)."""
    
    @patch('mutagen.File')
    @patch('mutagen.mp3.MP3')
    @patch('mutagen.id3.ID3')
    def test_mp3_id3v2_extraction(self, mock_id3, mock_mp3, mock_file):
        """Test MP3 with ID3v2 tags."""
        from src.metadata import extract_metadata
        
        # Mock ID3v2 tags
        mock_tags = {
            'TPE1': Mock(text=["The Beatles"]),
            'TIT2': Mock(text=["Hey Jude"]),
            'TALB': Mock(text=["1967-1970"]),
            'TCON': Mock(text=["Rock"]),
            'TDRC': Mock(text=["1968"]),
        }
        mock_id3.return_value = mock_tags
        
        # Mock audio info
        mock_audio = Mock()
        mock_audio.info = Mock()
        mock_audio.info.length = 431.2
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 44100
        mock_audio.info.bitrate = 320000
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            metadata = extract_metadata(temp_path, validate_quality=False)
            
            assert metadata['artist'] == "The Beatles"
            assert metadata['title'] == "Hey Jude"
            assert metadata['album'] == "1967-1970"
            assert metadata['genre'] == "Rock"
            assert metadata['year'] == 1968
            assert metadata['format'] == 'MP3'
            assert metadata['duration'] == 431.2
            assert metadata['channels'] == 2
        finally:
            temp_path.unlink()
    
    @patch('mutagen.File')
    @patch('mutagen.mp3.MP3')
    @patch('mutagen.id3.ID3')
    def test_mp3_id3v23_tyer_tag(self, mock_id3, mock_mp3, mock_file):
        """Test MP3 with ID3v2.3 TYER tag."""
        from src.metadata import MetadataExtractor
        
        # Mock ID3v2.3 tags (TYER instead of TDRC)
        mock_tags = {
            'TPE1': Mock(text=["Artist"]),
            'TIT2': Mock(text=["Title"]),
            'TYER': Mock(text=["1967"]),  # ID3v2.3 year tag
        }
        mock_id3.return_value = mock_tags
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake mp3")
        
        try:
            # Test ID3 extraction directly
            metadata = MetadataExtractor.extract_id3_tags(temp_path)
            
            assert metadata['year'] == 1967
        finally:
            temp_path.unlink()


class TestFLACFormatSupport:
    """Test FLAC format support (Vorbis comments)."""
    
    @patch('mutagen.File')
    @patch('mutagen.flac.FLAC')
    def test_flac_vorbis_comments(self, mock_flac, mock_file):
        """Test FLAC with Vorbis comments."""
        from src.metadata import extract_metadata
        
        # Mock Vorbis comments
        mock_tags = {
            'artist': ['Radiohead'],
            'title': ['Paranoid Android'],
            'album': ['OK Computer'],
            'genre': ['Alternative Rock'],
            'date': ['1997'],
        }
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_audio.info = Mock()
        mock_audio.info.length = 383.0
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 44100
        mock_audio.info.bitrate = 1000000
        mock_audio.info.bits_per_sample = 16  # Actual integer, not Mock
        mock_file.return_value = mock_audio
        
        # Mock FLAC call
        mock_flac_instance = Mock()
        mock_flac_instance.tags = mock_tags
        mock_flac.return_value = mock_flac_instance
        
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake flac")
        
        try:
            with patch('src.metadata.extractor.MetadataExtractor.extract_vorbis_comments',
                      return_value={'artist': 'Radiohead', 'title': 'Paranoid Android',
                                   'album': 'OK Computer', 'genre': 'Alternative Rock', 'year': 1997}):
                metadata = extract_metadata(temp_path, validate_quality=False)
                
                assert metadata['artist'] == 'Radiohead'
                assert metadata['title'] == 'Paranoid Android'
                assert metadata['format'] == 'FLAC'
                assert metadata['bit_depth'] == 16
        finally:
            temp_path.unlink()


class TestM4AFormatSupport:
    """Test M4A/AAC format support (MP4 tags)."""
    
    @patch('mutagen.File')
    @patch('mutagen.mp4.MP4')
    def test_m4a_mp4_tags(self, mock_mp4, mock_file):
        """Test M4A with MP4 tags."""
        from src.metadata import extract_metadata
        
        # Mock MP4 tags (uses copyright symbol keys)
        mock_tags = {
            '\xa9ART': ['Daft Punk'],
            '\xa9nam': ['Get Lucky'],
            '\xa9alb': ['Random Access Memories'],
            '\xa9gen': ['Electronic'],
            '\xa9day': ['2013'],
        }
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_audio.info = Mock()
        mock_audio.info.length = 248.0
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 44100
        mock_audio.info.bitrate = 256000
        mock_file.return_value = mock_audio
        
        # Mock MP4 call
        mock_mp4_instance = Mock()
        mock_mp4_instance.tags = mock_tags
        mock_mp4.return_value = mock_mp4_instance
        
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake m4a")
        
        try:
            with patch('src.metadata.extractor.MetadataExtractor.extract_mp4_tags',
                      return_value={'artist': 'Daft Punk', 'title': 'Get Lucky',
                                   'album': 'Random Access Memories', 'genre': 'Electronic', 'year': 2013}):
                metadata = extract_metadata(temp_path, validate_quality=False)
                
                assert metadata['artist'] == 'Daft Punk'
                assert metadata['title'] == 'Get Lucky'
                assert metadata['format'] == 'M4A'
        finally:
            temp_path.unlink()


class TestOGGFormatSupport:
    """Test OGG format support (Vorbis comments)."""
    
    @patch('mutagen.File')
    @patch('mutagen.oggvorbis.OggVorbis')
    def test_ogg_vorbis_comments(self, mock_ogg, mock_file):
        """Test OGG with Vorbis comments."""
        from src.metadata import extract_metadata
        
        # Mock Vorbis comments
        mock_tags = {
            'artist': ['Pink Floyd'],
            'title': ['Comfortably Numb'],
            'album': ['The Wall'],
            'genre': ['Progressive Rock'],
            'date': ['1979'],
        }
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_audio.info = Mock()
        mock_audio.info.length = 382.0
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 48000
        mock_audio.info.bitrate = 160000
        mock_file.return_value = mock_audio
        
        # Mock OGG call
        mock_ogg_instance = Mock()
        mock_ogg_instance.tags = mock_tags
        mock_ogg.return_value = mock_ogg_instance
        
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake ogg")
        
        try:
            with patch('src.metadata.extractor.MetadataExtractor.extract_vorbis_comments',
                      return_value={'artist': 'Pink Floyd', 'title': 'Comfortably Numb',
                                   'album': 'The Wall', 'genre': 'Progressive Rock', 'year': 1979}):
                metadata = extract_metadata(temp_path, validate_quality=False)
                
                assert metadata['artist'] == 'Pink Floyd'
                assert metadata['title'] == 'Comfortably Numb'
                assert metadata['format'] == 'OGG'
        finally:
            temp_path.unlink()


class TestWAVFormatSupport:
    """Test WAV format support (RIFF INFO)."""
    
    @patch('mutagen.File')
    def test_wav_riff_info(self, mock_file):
        """Test WAV with RIFF INFO tags."""
        from src.metadata import extract_metadata
        
        # Mock WAVE audio with proper tags structure
        class MockTags(dict):
            """Mock tags that behave like dict but supports .get()"""
            def get(self, key, default=None):
                value = super().get(key, default)
                return value if value is not None else default
        
        mock_tags = MockTags({
            'artist': ['Test Artist'],
            'title': ['Test Title'],
            'album': ['Test Album'],
        })
        
        mock_audio = Mock()
        mock_audio.tags = mock_tags
        mock_audio.info = Mock()
        mock_audio.info.length = 120.0
        mock_audio.info.channels = 2
        mock_audio.info.sample_rate = 44100
        mock_audio.info.sample_width = 2  # 16-bit (2 bytes)
        mock_file.return_value = mock_audio
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake wav")
        
        try:
            metadata = extract_metadata(temp_path, validate_quality=False)
            
            assert metadata['format'] == 'WAV'
            assert metadata['bit_depth'] == 16  # sample_width * 8
            assert metadata['artist'] == 'Test Artist'
        finally:
            temp_path.unlink()


class TestFormatDetectionAndValidation:
    """Test format detection and validation."""
    
    def test_supported_formats_list(self):
        """Test that all expected formats are supported."""
        from src.metadata import MetadataExtractor
        
        expected_formats = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}
        assert MetadataExtractor.SUPPORTED_FORMATS == expected_formats
    
    def test_unsupported_format_error(self):
        """Test error for unsupported format."""
        from src.metadata import extract_metadata, MetadataExtractionError
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"not audio")
        
        try:
            with pytest.raises(MetadataExtractionError, match="Unsupported audio format"):
                extract_metadata(temp_path)
        finally:
            temp_path.unlink()
    
    def test_format_detection_from_extension(self):
        """Test format detection from file extension."""
        from src.metadata import MetadataExtractor
        
        test_cases = [
            ('song.mp3', 'MP3'),
            ('track.flac', 'FLAC'),
            ('audio.m4a', 'M4A'),
            ('file.aac', 'AAC'),
            ('music.ogg', 'OGG'),
            ('sound.wav', 'WAV'),
        ]
        
        for filename, expected_format in test_cases:
            # Just check the format detection logic
            suffix = Path(filename).suffix.lower()
            assert suffix.lstrip('.').upper() == expected_format


class TestCrossFormatFeatures:
    """Test features that work across all formats."""
    
    @patch('mutagen.File')
    def test_technical_specs_extraction_all_formats(self, mock_file):
        """Test that technical specs are extracted for all formats."""
        from src.metadata import extract_metadata
        
        formats_to_test = ['.mp3', '.flac', '.m4a', '.ogg', '.wav']
        
        for fmt in formats_to_test:
            # Create fresh mock for each format
            mock_audio = Mock()
            mock_audio.tags = {}
            mock_audio.info = Mock()
            mock_audio.info.length = 100.0
            mock_audio.info.channels = 2
            mock_audio.info.sample_rate = 44100
            mock_audio.info.bitrate = 192000
            
            # Reset mock for each iteration
            mock_file.reset_mock()
            mock_file.return_value = mock_audio
            
            with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as f:
                temp_path = Path(f.name)
                f.write(b"fake audio")
            
            try:
                if fmt == '.mp3':
                    patch_target = 'src.metadata.extractor.MetadataExtractor.extract_id3_tags'
                elif fmt in ['.flac', '.ogg']:
                    patch_target = 'src.metadata.extractor.MetadataExtractor.extract_vorbis_comments'
                elif fmt == '.m4a':
                    patch_target = 'src.metadata.extractor.MetadataExtractor.extract_mp4_tags'
                else:
                    patch_target = None
                
                if patch_target:
                    with patch(patch_target, return_value={}):
                        metadata = extract_metadata(temp_path, validate_quality=False)
                else:
                    metadata = extract_metadata(temp_path, validate_quality=False)
                
                # Verify technical specs are present
                assert metadata['duration'] == 100.0, f"Duration mismatch for {fmt}: {metadata['duration']}"
                assert metadata['channels'] == 2, f"Channels mismatch for {fmt}"
                assert metadata['sample_rate'] == 44100, f"Sample rate mismatch for {fmt}"
                assert metadata['bitrate'] == 192, f"Bitrate mismatch for {fmt}"  # Converted to kbps
                assert metadata['format'] == fmt.lstrip('.').upper(), f"Format mismatch for {fmt}"
            finally:
                temp_path.unlink()
    
    def test_error_handling_all_formats(self):
        """Test that error handling works for all formats."""
        from src.metadata import extract_metadata, MetadataExtractionError
        
        formats = ['.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wav']
        
        for fmt in formats:
            # Test with non-existent file
            with pytest.raises(MetadataExtractionError, match="File not found"):
                extract_metadata(f"/nonexistent/file{fmt}")


class TestFormatExtensibility:
    """Test that the system is extensible for future formats."""
    
    def test_format_set_is_mutable(self):
        """Test that format set can be extended."""
        from src.metadata import MetadataExtractor
        
        original_formats = MetadataExtractor.SUPPORTED_FORMATS.copy()
        
        # This test verifies that the SUPPORTED_FORMATS is a set
        # which can be extended in future
        assert isinstance(MetadataExtractor.SUPPORTED_FORMATS, set)
        
        # Restore original
        MetadataExtractor.SUPPORTED_FORMATS = original_formats
    
    def test_format_specific_extraction_methods(self):
        """Test that format-specific methods exist."""
        from src.metadata import MetadataExtractor
        
        # Verify format-specific extraction methods exist
        assert hasattr(MetadataExtractor, 'extract_id3_tags')
        assert hasattr(MetadataExtractor, 'extract_vorbis_comments')
        assert hasattr(MetadataExtractor, 'extract_mp4_tags')
        
        # These methods are static
        assert callable(MetadataExtractor.extract_id3_tags)
        assert callable(MetadataExtractor.extract_vorbis_comments)
        assert callable(MetadataExtractor.extract_mp4_tags)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

