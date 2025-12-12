"""
Shared Business Logic Layer for Loist Music Library

This package contains transport-agnostic business logic that can be
called by both MCP tools and A2A handlers, ensuring consistent behavior
across different interfaces.

Architecture:
- audio_processor.py: Core audio processing orchestration
- Shared request/result/error types using canonical snake_case naming
- No FastMCP or A2A SDK dependencies (transport-agnostic)
"""

from .audio_processor import (
    process_audio_shared,
    AudioProcessingRequest,
    AudioProcessingResult,
    AudioProcessingError as SharedAudioProcessingError,
)

__all__ = [
    "process_audio_shared",
    "AudioProcessingRequest",
    "AudioProcessingResult",
    "SharedAudioProcessingError",
]

