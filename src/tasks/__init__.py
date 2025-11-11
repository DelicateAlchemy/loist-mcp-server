"""
Task queue management for async audio processing.

Provides Cloud Tasks integration for background processing of audio files,
including waveform generation, MusicBrainz lookups, and AI analysis.

Features:
- Generic task queue with extensible task types
- Cloud Tasks integration with retry logic
- Async processing for CPU-intensive audio operations
- Extensible for future audio processing tasks
"""

from .queue import (
    enqueue_waveform_generation,
    TaskQueueError,
)

__all__ = [
    "enqueue_waveform_generation",
    "TaskQueueError",
]
