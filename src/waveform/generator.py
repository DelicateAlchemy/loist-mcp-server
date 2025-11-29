"""
Waveform generation module for Loist Music Library MCP Server.

Generates DAW-style SVG waveforms from audio files using FFmpeg for amplitude
extraction and Python for scalable vector graphics creation.

Features:
- Stereo-to-mono conversion for summed waveform
- DAW-style black waveform on transparent background
- Scalable SVG with viewBox for responsive embed players
- Efficient amplitude sampling for visual representation
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import struct
import tempfile
import os

logger = logging.getLogger(__name__)


class WaveformGenerationError(Exception):
    """Raised when waveform generation fails."""
    pass


def extract_waveform_data(audio_path: Path, samples: int = 2000) -> List[float]:
    """
    Extract amplitude samples from audio file using FFmpeg.

    Converts stereo audio to mono and extracts amplitude values at regular
    intervals for waveform visualization.

    Args:
        audio_path: Path to the input audio file
        samples: Number of amplitude samples to extract (determines horizontal resolution)

    Returns:
        List of normalized amplitude values (-1.0 to 1.0)

    Raises:
        WaveformGenerationError: If FFmpeg fails or audio file is invalid
    """
    if not audio_path.exists():
        raise WaveformGenerationError(f"Audio file not found: {audio_path}")

    # Use FFmpeg to convert audio to mono PCM and extract samples
    # Command breakdown:
    # -i input.mp3: Input file
    # -ac 1: Convert to mono (sum stereo channels)
    # -f f32le: Output format (32-bit float, little endian)
    # -acodec pcm_f32le: Audio codec for PCM float
    # - : Output to stdout (pipe)
    cmd = [
        "ffmpeg",
        "-i", str(audio_path),
        "-ac", "1",  # Convert to mono
        "-f", "f32le",  # 32-bit float little-endian
        "-acodec", "pcm_f32le",
        "-"  # Output to stdout
    ]

    try:
        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=60  # 60 second timeout for FFmpeg
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode()}")
        raise WaveformGenerationError(f"FFmpeg processing failed: {e}") from e
    except subprocess.TimeoutExpired:
        raise WaveformGenerationError("FFmpeg processing timed out")

    # Parse the raw PCM float data
    pcm_data = result.stdout
    if len(pcm_data) == 0:
        raise WaveformGenerationError("FFmpeg produced no output data")

    # Convert bytes to float array
    # Each float is 4 bytes (32-bit)
    num_samples = len(pcm_data) // 4
    amplitudes = []
    for i in range(num_samples):
        # Unpack 4 bytes as little-endian float
        sample_bytes = pcm_data[i*4:(i+1)*4]
        if len(sample_bytes) == 4:
            amplitude = struct.unpack('<f', sample_bytes)[0]
            amplitudes.append(amplitude)

    if not amplitudes:
        raise WaveformGenerationError("No amplitude data extracted from audio")

    # Resample to desired number of samples for visualization
    if len(amplitudes) <= samples:
        # If we have fewer samples than requested, use all of them
        resampled = amplitudes
    else:
        # Downsample by taking every Nth sample
        step = len(amplitudes) / samples
        resampled = []
        for i in range(samples):
            idx = int(i * step)
            if idx < len(amplitudes):
                resampled.append(amplitudes[idx])

    logger.debug(f"Extracted {len(resampled)} amplitude samples from {len(amplitudes)} total")
    return resampled


def create_svg_waveform(amplitudes: List[float], width: int = 2000, height: int = 200) -> str:
    """
    Generate SVG waveform from amplitude data.

    Creates a DAW-style waveform with black stroke on transparent background,
    symmetric around the center line for professional appearance.

    Args:
        amplitudes: List of normalized amplitude values (-1.0 to 1.0)
        width: SVG width in pixels (default: 2000)
        height: SVG height in pixels (default: 200)

    Returns:
        SVG string with scalable waveform visualization
    """
    if not amplitudes:
        raise WaveformGenerationError("No amplitude data provided")

    # Calculate center line
    center_y = height / 2

    # Create SVG path data
    path_data = []
    num_samples = len(amplitudes)

    for i, amplitude in enumerate(amplitudes):
        # Map amplitude (-1.0 to 1.0) to vertical position
        # Scale amplitude and position around center line
        scaled_amplitude = amplitude * (height / 2) * 0.8  # 80% of height for visual margin
        y_pos = center_y - scaled_amplitude

        # Calculate x position
        x_pos = (i / max(1, num_samples - 1)) * width

        if i == 0:
            path_data.append(f"M{x_pos},{y_pos}")
        else:
            path_data.append(f"L{x_pos},{y_pos}")

    # Create symmetric waveform by mirroring the path
    # Start from the end and go backwards for the bottom half
    for i in range(num_samples - 1, -1, -1):
        amplitude = amplitudes[i]
        scaled_amplitude = amplitude * (height / 2) * 0.8
        y_pos = center_y + scaled_amplitude  # Mirror above center

        x_pos = (i / max(1, num_samples - 1)) * width

        path_data.append(f"L{x_pos},{y_pos}")

    # Close the path
    path_data.append("Z")

    # Generate SVG
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
  <path d="{' '.join(path_data)}" stroke="#000000" stroke-width="1" fill="none"/>
</svg>"""

    return svg_content


def generate_waveform_svg(
    audio_path: Path,
    output_path: Path,
    width: int = 2000,
    height: int = 200
) -> Dict[str, Any]:
    """
    Generate SVG waveform file from audio file.

    Complete workflow: extract amplitudes, create SVG, write to file.

    Args:
        audio_path: Path to input audio file
        output_path: Path where SVG file should be written
        width: SVG width in pixels (default: 2000)
        height: SVG height in pixels (default: 200)

    Returns:
        Dict containing:
        - processing_time_seconds: Time taken for generation
        - file_size_bytes: Size of generated SVG file
        - width: SVG width
        - height: SVG height
        - sample_count: Number of amplitude samples used

    Raises:
        WaveformGenerationError: If generation fails
    """
    start_time = time.time()

    try:
        # Extract amplitude data from audio
        logger.info(f"Extracting amplitude data from {audio_path}")
        amplitudes = extract_waveform_data(audio_path, samples=width)

        # Generate SVG content
        logger.info(f"Generating SVG waveform with {len(amplitudes)} samples")
        svg_content = create_svg_waveform(amplitudes, width, height)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write SVG file
        logger.info(f"Writing SVG to {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        # Calculate processing time and file size
        processing_time = time.time() - start_time
        file_size = output_path.stat().st_size

        result = {
            "processing_time_seconds": round(processing_time, 2),
            "file_size_bytes": file_size,
            "width": width,
            "height": height,
            "sample_count": len(amplitudes),
        }

        logger.info(f"Waveform generation completed in {processing_time:.2f}s, "
                   f"file size: {file_size} bytes, {len(amplitudes)} samples")

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Waveform generation failed after {processing_time:.2f}s: {e}")
        raise WaveformGenerationError(f"Failed to generate waveform: {e}") from e
