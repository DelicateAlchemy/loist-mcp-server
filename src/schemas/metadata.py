"""
Pydantic schemas for core data models like audio metadata.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProductMetadata(BaseModel):
    """Product-level metadata (artist, title, album, etc.)"""
    artist: str = Field(default="", description="Artist name")
    title: str = Field(default="Untitled", description="Track title")
    album: Optional[str] = Field(default=None, description="Album name")
    mbid: Optional[str] = Field(default=None, description="MusicBrainz ID (null in MVP)")
    genre: List[str] = Field(default_factory=list, description="Genre tags")
    year: Optional[int] = Field(default=None, ge=1900, le=2100, description="Release year")
    isrc: Optional[str] = Field(
        default=None,
        max_length=15,
        description="International Standard Recording Code (ISRC), if known",
    )


class FormatMetadata(BaseModel):
    """Technical format metadata (duration, bitrate, etc.)"""
    duration: Optional[float] = Field(default=None, ge=0, description="Duration in seconds (may be null if not extracted)")
    channels: Optional[int] = Field(default=None, ge=1, le=16, description="Number of audio channels")
    sample_rate: Optional[int] = Field(default=None, ge=8000, description="Sample rate in Hz")
    bitrate: Optional[int] = Field(default=None, ge=0, description="Bitrate in bits per second")
    format: str = Field(description="Audio format (e.g., 'MP3', 'FLAC')")

    model_config = ConfigDict(
        populate_by_name=True, # Allow both "SampleRate" and "sample_rate"
        json_by_alias=True
    )


class AudioMetadata(BaseModel):
    """Complete audio metadata including product and format information"""
    product: ProductMetadata
    format: FormatMetadata
    url_embed_link: str = Field(description="Embed URL for audio player")


class AudioResources(BaseModel):
    """Resource URIs for audio, thumbnail, and waveform"""
    audio_url: str = Field(description="URI for audio stream")
    thumbnail_url: Optional[str] = Field(default=None, description="URI for thumbnail image")
    waveform_url: Optional[str] = Field(default=None, description="URI for waveform (null in MVP)")
