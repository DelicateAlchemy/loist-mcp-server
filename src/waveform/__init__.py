"""
Waveform generation module for Loist Music Library MCP Server.

Provides functionality for generating DAW-style SVG waveforms from audio files
using FFmpeg for amplitude extraction and Python for SVG generation.
"""

from .generator import (
    extract_waveform_data,
    create_svg_waveform,
    generate_waveform_svg,
    WaveformGenerationError,
)

__all__ = [
    "extract_waveform_data",
    "create_svg_waveform",
    "generate_waveform_svg",
    "WaveformGenerationError",
]
