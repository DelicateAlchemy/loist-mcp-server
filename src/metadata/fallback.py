"""
Composer to Artist Fallback Logic

Provides fallback logic to populate the artist field with composer information
when the artist field is blank/missing but composer metadata is available.

This is common in classical music, film scores, and professional audio production
where composer information is rich but artist tags may be absent.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def apply_artist_composer_fallback(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply composer→artist fallback when artist is blank.

    Rules:
    - Only applies when artist is truly blank/empty (None, "", whitespace-only)
    - One-way operation: composer → artist (never artist → composer)
    - Preserves original composer field
    - Returns new dict (doesn't mutate input)

    Args:
        metadata: Metadata dictionary with 'artist' and 'composer' fields

    Returns:
        New metadata dictionary with fallback applied if needed
    """
    # Create a copy to avoid mutating input
    result = metadata.copy()

    # Get artist and composer values
    artist = result.get("artist")
    composer = result.get("composer")

    # Check if artist is truly blank (None, empty string, or whitespace-only)
    artist_is_blank = not artist or (isinstance(artist, str) and not artist.strip())

    # Check if composer exists and is non-empty
    composer_exists = composer and (isinstance(composer, str) and composer.strip())

    # Apply fallback: composer → artist (only when artist is blank)
    if artist_is_blank and composer_exists:
        result["artist"] = composer.strip()
        logger.info(f"Applied composer→artist fallback: '{composer}' → artist field")

    return result
