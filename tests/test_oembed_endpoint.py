"""
Test suite for oEmbed endpoint functionality.

Tests the oEmbed endpoint implementation including:
- Valid URL parameter handling
- Invalid URL parameter handling
- maxwidth/maxheight parameter processing
- Response format validation
- Error handling
"""

import pytest
import json
from unittest.mock import Mock, patch
from starlette.testclient import TestClient
from starlette.responses import JSONResponse

# Import the server module to test
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from server import mcp


class TestOEmbedEndpoint:
    """Test cases for oEmbed endpoint functionality."""
    
    def setup_method(self):
        """Set up test client and mock data."""
        self.client = TestClient(mcp.http_app())
        
        # Mock metadata for testing
        self.mock_metadata = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "thumbnail_path": "gs://test-bucket/thumbnails/test-thumb.jpg",
            "audio_path": "gs://test-bucket/audio/test-song.mp3"
        }
    
    @patch('server.get_audio_metadata_by_id')
    @patch('server.get_cache')
    def test_oembed_valid_url(self, mock_get_cache, mock_get_metadata):
        """Test oEmbed endpoint with valid URL."""
        # Mock the database call
        mock_get_metadata.return_value = self.mock_metadata
        
        # Mock the cache for thumbnail URL generation
        mock_cache = Mock()
        mock_cache.get.return_value = "https://signed-url.com/thumbnail.jpg"
        mock_get_cache.return_value = mock_cache
        
        # Test request
        url = "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
        response = self.client.get(f"/oembed?url={url}")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["version"] == "1.0"
        assert data["type"] == "rich"
        assert data["title"] == "Test Song"
        assert data["author_name"] == "Test Artist"
        assert data["provider_name"] == "Loist Music Library"
        assert data["provider_url"] == "https://loist.io"
        assert "iframe" in data["html"]
        assert "550e8400-e29b-41d4-a716-446655440000" in data["html"]
        assert data["width"] == 500
        assert data["height"] == 200
        assert data["thumbnail_url"] == "https://signed-url.com/thumbnail.jpg"
        assert data["thumbnail_width"] == 600
        assert data["thumbnail_height"] == 600
    
    def test_oembed_invalid_url_missing(self):
        """Test oEmbed endpoint with missing URL parameter."""
        response = self.client.get("/oembed")
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid URL parameter" in data["error"]
    
    def test_oembed_invalid_url_format(self):
        """Test oEmbed endpoint with invalid URL format."""
        url = "https://example.com/not-loist"
        response = self.client.get(f"/oembed?url={url}")
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid URL parameter" in data["error"]
    
    def test_oembed_invalid_uuid(self):
        """Test oEmbed endpoint with invalid UUID in URL."""
        url = "https://loist.io/embed/invalid-uuid"
        response = self.client.get(f"/oembed?url={url}")
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid URL format" in data["error"]
    
    @patch('server.get_audio_metadata_by_id')
    def test_oembed_audio_not_found(self, mock_get_metadata):
        """Test oEmbed endpoint when audio is not found."""
        # Mock database call to return None
        mock_get_metadata.return_value = None
        
        url = "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
        response = self.client.get(f"/oembed?url={url}")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "Audio not found" in data["error"]
    
    @patch('server.get_audio_metadata_by_id')
    @patch('server.get_cache')
    def test_oembed_maxwidth_maxheight(self, mock_get_cache, mock_get_metadata):
        """Test oEmbed endpoint with maxwidth and maxheight parameters."""
        # Mock the database call
        mock_get_metadata.return_value = self.mock_metadata
        
        # Mock the cache
        mock_cache = Mock()
        mock_get_cache.return_value = mock_cache
        
        # Test with custom dimensions
        url = "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
        response = self.client.get(f"/oembed?url={url}&maxwidth=300&maxheight=150")
        
        assert response.status_code == 200
        data = response.json()
        assert data["width"] == 300
        assert data["height"] == 150
    
    @patch('server.get_audio_metadata_by_id')
    @patch('server.get_cache')
    def test_oembed_no_thumbnail(self, mock_get_cache, mock_get_metadata):
        """Test oEmbed endpoint when no thumbnail is available."""
        # Mock metadata without thumbnail
        metadata_no_thumb = self.mock_metadata.copy()
        metadata_no_thumb.pop("thumbnail_path")
        mock_get_metadata.return_value = metadata_no_thumb
        
        # Mock the cache
        mock_cache = Mock()
        mock_get_cache.return_value = mock_cache
        
        url = "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
        response = self.client.get(f"/oembed?url={url}")
        
        assert response.status_code == 200
        data = response.json()
        assert "thumbnail_url" not in data
        assert "thumbnail_width" not in data
        assert "thumbnail_height" not in data
    
    def test_oembed_discovery_endpoint(self):
        """Test oEmbed discovery endpoint."""
        response = self.client.get("/.well-known/oembed.json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["provider_name"] == "Loist Music Library"
        assert data["provider_url"] == "https://loist.io"
        assert "endpoints" in data
        assert len(data["endpoints"]) == 1
        
        endpoint = data["endpoints"][0]
        assert endpoint["url"] == "https://loist.io/oembed"
        assert "json" in endpoint["formats"]
        assert endpoint["discovery"] is True


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
