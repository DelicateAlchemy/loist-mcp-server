"""
Tests for audio format validation.

Tests verify:
- File signature (magic number) validation
- Format detection from signatures
- Extension vs. signature mismatch detection
- Corrupted file detection
- Supported format checking
"""

import pytest
from pathlib import Path
import tempfile

from src.metadata.format_validator import (
    FormatValidator,
    FormatValidationError,
    validate_audio_format,
    AUDIO_SIGNATURES,
)


class TestFormatValidatorImports:
    """Test that format validator imports correctly."""
    
    def test_imports(self):
        """Test module imports."""
        from src.metadata import FormatValidator, FormatValidationError, validate_audio_format
        
        assert FormatValidator is not None
        assert FormatValidationError is not None
        assert validate_audio_format is not None


class TestFileSignatureReading:
    """Test file signature reading."""
    
    def test_read_file_signature(self):
        """Test reading file signature."""
        # Create file with known signature
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            signature = FormatValidator.read_file_signature(temp_path)
            
            assert signature[:3] == b'ID3'
        finally:
            temp_path.unlink()
    
    def test_read_file_signature_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FormatValidationError, match="Could not read"):
            FormatValidator.read_file_signature(Path("/nonexistent/file.mp3"))


class TestSignatureValidation:
    """Test signature validation for different formats."""
    
    def test_validate_mp3_id3_signature(self):
        """Test MP3 file with ID3 signature."""
        # Create file with ID3v2 signature
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".mp3")
            
            assert detected == ".mp3"
        finally:
            temp_path.unlink()
    
    def test_validate_mp3_mpeg_signature(self):
        """Test MP3 file with MPEG signature."""
        # Create file with MPEG frame signature
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'\xff\xfb\x90\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".mp3")
            
            assert detected == ".mp3"
        finally:
            temp_path.unlink()
    
    def test_validate_flac_signature(self):
        """Test FLAC file signature."""
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            f.write(b'fLaC\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".flac")
            
            assert detected == ".flac"
        finally:
            temp_path.unlink()
    
    def test_validate_wav_signature(self):
        """Test WAV file signature."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'RIFF\x00\x00\x00\x00WAVE')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".wav")
            
            assert detected == ".wav"
        finally:
            temp_path.unlink()
    
    def test_validate_ogg_signature(self):
        """Test OGG file signature."""
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(b'OggS\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".ogg")
            
            assert detected == ".ogg"
        finally:
            temp_path.unlink()
    
    def test_validate_m4a_signature(self):
        """Test M4A file signature."""
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as f:
            f.write(b'\x00\x00\x00\x20ftyp')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path, ".m4a")
            
            assert detected == ".m4a"
        finally:
            temp_path.unlink()
    
    def test_validate_incorrect_signature(self):
        """Test that incorrect signature is rejected."""
        # Create file with wrong signature
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'NOTMP3\x00\x00')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(FormatValidationError, match="signature does not match"):
                FormatValidator.validate_signature(temp_path, ".mp3")
        finally:
            temp_path.unlink()


class TestFormatDetection:
    """Test automatic format detection."""
    
    def test_detect_mp3_format(self):
        """Test auto-detecting MP3 format."""
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path)
            
            assert detected == ".mp3"
        finally:
            temp_path.unlink()
    
    def test_detect_flac_format(self):
        """Test auto-detecting FLAC format."""
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'fLaC\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            detected = FormatValidator.validate_signature(temp_path)
            
            assert detected == ".flac"
        finally:
            temp_path.unlink()
    
    def test_detect_unknown_format(self):
        """Test detecting unknown format."""
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'UNKNOWN\x00\x00')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(FormatValidationError, match="Unknown or unsupported"):
                FormatValidator.validate_signature(temp_path)
        finally:
            temp_path.unlink()


class TestComprehensiveValidation:
    """Test comprehensive file validation."""
    
    def test_validate_file_success(self):
        """Test successful file validation."""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            result = FormatValidator.validate_file(temp_path)
            
            assert result['valid'] is True
            assert result['extension'] == '.mp3'
            assert result['detected_format'] == '.mp3'
            assert result['matches_extension'] is True
            assert result['file_size'] > 0
        finally:
            temp_path.unlink()
    
    def test_validate_file_not_found(self):
        """Test validation when file doesn't exist."""
        with pytest.raises(FormatValidationError, match="File not found"):
            FormatValidator.validate_file("/nonexistent/file.mp3")
    
    def test_validate_empty_file(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            # File is empty
        
        try:
            with pytest.raises(FormatValidationError, match="File is empty"):
                FormatValidator.validate_file(temp_path)
        finally:
            temp_path.unlink()
    
    def test_validate_unsupported_extension(self):
        """Test validation of unsupported extension."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'Some text content')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(FormatValidationError, match="Unsupported file extension"):
                FormatValidator.validate_file(temp_path)
        finally:
            temp_path.unlink()
    
    def test_validate_extension_signature_mismatch(self):
        """Test validation when extension doesn't match signature."""
        # Create file with .mp3 extension but FLAC signature
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'fLaC\x00\x00\x00')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(FormatValidationError, match="signature does not match"):
                FormatValidator.validate_file(temp_path)
        finally:
            temp_path.unlink()


class TestSupportedFormatCheck:
    """Test supported format checking."""
    
    def test_is_supported_format_mp3(self):
        """Test MP3 is supported."""
        assert FormatValidator.is_supported_format("song.mp3") is True
    
    def test_is_supported_format_flac(self):
        """Test FLAC is supported."""
        assert FormatValidator.is_supported_format("song.flac") is True
    
    def test_is_supported_format_unsupported(self):
        """Test unsupported format is rejected."""
        assert FormatValidator.is_supported_format("document.pdf") is False


class TestConvenienceFunction:
    """Test convenience validation function."""
    
    def test_validate_audio_format_function(self):
        """Test validate_audio_format convenience function."""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'ID3\x03\x00\x00')
            temp_path = Path(f.name)
        
        try:
            result = validate_audio_format(temp_path)
            
            assert result['valid'] is True
            assert result['extension'] == '.mp3'
        finally:
            temp_path.unlink()


class TestAudioSignatures:
    """Test audio signature configuration."""
    
    def test_signatures_configured(self):
        """Test audio signatures are configured."""
        assert len(AUDIO_SIGNATURES) > 0
        assert ".mp3" in AUDIO_SIGNATURES
        assert ".flac" in AUDIO_SIGNATURES
        assert ".wav" in AUDIO_SIGNATURES
    
    def test_mp3_has_multiple_signatures(self):
        """Test MP3 has multiple signature options."""
        assert len(AUDIO_SIGNATURES[".mp3"]) >= 2  # ID3 and MPEG signatures


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

