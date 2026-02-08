"""
Unit tests for FFmpeg converter with metadata and artwork support.

Tests verify:
- Metadata parameter passing to FFmpeg commands
- Artwork parameter handling
- FFmpeg command construction with metadata flags
- Error handling for metadata operations
- Integration with metadata mapper
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import subprocess

from src.converter.ffmpeg_converter import (
    convert_audio,
    ConversionError,
    ConversionTimeoutError,
    _build_ffmpeg_command,
)
from src.converter.presets import get_preset_config


class TestConvertAudioWithMetadata:
    """Test convert_audio function with metadata parameters."""

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    def test_convert_with_metadata(self, mock_run):
        """Test conversion with metadata embedding."""
        # Setup mocks
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')

        # Test metadata
        metadata = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'

            # Create source file
            source_path.touch()

            result = convert_audio(
                source_path=source_path,
                output_path=output_path,
                target_format='mp3',
                metadata=metadata,
            )

            # Verify conversion succeeded
            assert result.success == True
            assert result.target_format == 'mp3'

            # Verify FFmpeg was called
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]  # First positional argument is cmd

            # Verify metadata arguments are present
            assert '-metadata' in cmd_args
            assert 'title=Test Song' in cmd_args
            assert 'artist=Test Artist' in cmd_args
            assert 'album=Test Album' in cmd_args

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    def test_convert_with_artwork(self, mock_run):
        """Test conversion with artwork embedding."""
        # Setup mocks
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'
            artwork_path = Path(temp_dir) / 'cover.jpg'

            # Create files
            source_path.touch()
            artwork_path.touch()

            result = convert_audio(
                source_path=source_path,
                output_path=output_path,
                target_format='mp3',
                artwork_path=artwork_path,
            )

            # Verify conversion succeeded
            assert result.success == True

            # Verify FFmpeg was called with artwork arguments
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]  # First positional argument is cmd

            # Verify artwork input and mapping
            assert '-i' in cmd_args
            assert str(artwork_path) in cmd_args
            assert '-map' in cmd_args
            assert '0:a' in cmd_args  # Audio stream
            assert '1:v' in cmd_args  # Video stream (artwork)

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    def test_convert_with_metadata_and_artwork(self, mock_run):
        """Test conversion with both metadata and artwork."""
        # Setup mocks
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')

        metadata = {
            'title': 'Test Song',
            'artist': 'Test Artist',
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'
            artwork_path = Path(temp_dir) / 'cover.jpg'

            # Create files
            source_path.touch()
            artwork_path.touch()

            result = convert_audio(
                source_path=source_path,
                output_path=output_path,
                target_format='mp3',
                metadata=metadata,
                artwork_path=artwork_path,
            )

            # Verify conversion succeeded
            assert result.success == True

            # Verify FFmpeg command includes both metadata and artwork
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]  # First positional argument is cmd

            # Check metadata
            assert 'title=Test Song' in cmd_args
            assert 'artist=Test Artist' in cmd_args

            # Check artwork
            assert str(artwork_path) in cmd_args
            assert '-map' in cmd_args
            assert '1:v' in cmd_args

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    def test_metadata_mapping_failure_handling(self, mock_run):
        """Test handling of metadata mapping failures."""
        # Setup mocks
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')

        # Invalid metadata (missing title)
        metadata = {
            'artist': 'Test Artist',
            # Missing title
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'

            # Create source file
            source_path.touch()

            # Should raise ValueError when title is missing from metadata
            with pytest.raises(ValueError, match="Title is required for metadata embedding"):
                convert_audio(
                    source_path=source_path,
                    output_path=output_path,
                    target_format='mp3',
                    metadata=metadata,
                )


class TestBuildFFmpegCommand:
    """Test FFmpeg command building with metadata."""

    def test_build_command_with_metadata(self):
        """Test building FFmpeg command with metadata arguments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'

            preset_config = get_preset_config('mp3', 'high')
            metadata = {
                'title': 'Test Song',
                'artist': 'Test Artist',
            }

            cmd = _build_ffmpeg_command(
                source_path=source_path,
                output_path=output_path,
                preset_config=preset_config,
                target_format='mp3',
                metadata=metadata,
            )

            # Verify command structure
            assert cmd[0] == 'ffmpeg'
            assert '-y' in cmd  # Overwrite flag
            assert str(source_path) in cmd
            assert str(output_path) in cmd

            # Verify metadata arguments
            assert '-metadata' in cmd
            assert 'title=Test Song' in cmd
            assert 'artist=Test Artist' in cmd

            # Verify MP3-specific flags
            assert '-id3v2_version' in cmd
            assert '3' in cmd
            assert '-write_id3v1' in cmd
            assert '1' in cmd

    def test_build_command_with_artwork(self):
        """Test building FFmpeg command with artwork arguments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'
            artwork_path = Path(temp_dir) / 'cover.jpg'

            # Create artwork file so it exists for the check
            artwork_path.touch()

            preset_config = get_preset_config('mp3', 'high')

            cmd = _build_ffmpeg_command(
                source_path=source_path,
                output_path=output_path,
                preset_config=preset_config,
                target_format='mp3',
                artwork_path=artwork_path,
            )

            # Verify artwork input
            assert '-i' in cmd
            assert str(artwork_path) in cmd

            # Verify stream mapping for MP3
            assert '-map' in cmd
            assert '0:a' in cmd  # Audio stream
            assert '1:v' in cmd  # Video stream

            # Verify codec settings
            assert '-codec:v' in cmd
            assert 'mjpeg' in cmd

    def test_build_command_wav_flags(self):
        """Test WAV-specific FFmpeg flags."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.wav'

            preset_config = get_preset_config('wav', 'broadcast')

            # Need metadata to trigger format-specific flags
            metadata = {'title': 'Test'}

            cmd = _build_ffmpeg_command(
                source_path=source_path,
                output_path=output_path,
                preset_config=preset_config,
                target_format='wav',
                metadata=metadata,
            )

            # Verify BWF bext flag
            assert '-write_bext' in cmd
            assert '1' in cmd

    def test_build_command_aac_flags(self):
        """Test AAC-specific FFmpeg flags."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.m4a'

            preset_config = get_preset_config('aac', 'high')

            # Need metadata to trigger format-specific flags
            metadata = {'title': 'Test'}

            cmd = _build_ffmpeg_command(
                source_path=source_path,
                output_path=output_path,
                preset_config=preset_config,
                target_format='aac',
                metadata=metadata,
            )

            # Verify iPod container flag
            assert '-f' in cmd
            assert 'ipod' in cmd


class TestErrorHandling:
    """Test error handling in converter with metadata."""

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    @patch('pathlib.Path.exists')
    def test_conversion_error_with_metadata(self, mock_exists, mock_run):
        """Test error handling when conversion fails with metadata."""
        # Setup mocks
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['ffmpeg'],
            stderr=b'FFmpeg error'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'

            with pytest.raises(ConversionError):
                convert_audio(
                    source_path=source_path,
                    output_path=output_path,
                    target_format='mp3',
                    metadata={'title': 'Test'},
                )

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    @patch('pathlib.Path.exists')
    def test_timeout_error_with_metadata(self, mock_exists, mock_run):
        """Test timeout error handling with metadata."""
        # Setup mocks
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=['ffmpeg'],
            timeout=300
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'

            with pytest.raises(ConversionTimeoutError):
                convert_audio(
                    source_path=source_path,
                    output_path=output_path,
                    target_format='mp3',
                    metadata={'title': 'Test'},
                )


class TestLogging:
    """Test logging in converter with metadata."""

    @patch('src.converter.ffmpeg_converter.subprocess.run')
    def test_logging_with_metadata(self, mock_run):
        """Test that conversion logs include metadata/artwork info."""
        # Setup mocks
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / 'source.wav'
            output_path = Path(temp_dir) / 'output.mp3'
            artwork_path = Path(temp_dir) / 'cover.jpg'

            # Create files
            source_path.touch()
            artwork_path.touch()

            with patch('src.converter.ffmpeg_converter.logger') as mock_logger:
                convert_audio(
                    source_path=source_path,
                    output_path=output_path,
                    target_format='mp3',
                    metadata={'title': 'Test Song'},
                    artwork_path=artwork_path,
                )

                # Verify logging includes metadata and artwork info
                # There should be at least 2 info calls: conversion start and completion
                assert mock_logger.info.call_count >= 2

                # Check the conversion start log (first info call)
                start_log_call = mock_logger.info.call_args_list[0][0][0]
                assert 'with metadata' in start_log_call
                assert 'with artwork' in start_log_call
