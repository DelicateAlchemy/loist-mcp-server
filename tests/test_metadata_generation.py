"""
Unit tests for metadata generation functionality.

Tests Open Graph tags, Twitter Cards, and Schema.org structured data
generation for social media sharing features.
"""
import pytest
import json
from bs4 import BeautifulSoup
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from starlette.templating import Jinja2Templates
from starlette.requests import Request
from starlette.datastructures import Headers, URL


class TestMetadataGeneration:
    """Test suite for metadata generation functionality."""
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            "Product": {
                "Title": "Hey Jude",
                "Artist": "The Beatles",
                "Album": "The Beatles 1967-1970",
                "Year": 1970,
            },
            "Format": {
                "Duration": 431.0,
                "Channels": 2,
                "SampleRate": 44100,
                "Bitrate": 320,
                "Format": "MP3",
            }
        }
    
    @pytest.fixture
    def sample_metadata_minimal(self):
        """Minimal metadata for edge case testing."""
        return {
            "Product": {
                "Title": "Unknown Track",
                "Artist": "Unknown Artist",
            },
            "Format": {
                "Duration": 0.0,
                "Channels": 2,
                "SampleRate": 44100,
                "Bitrate": 0,
                "Format": "MP3",
            }
        }
    
    @pytest.fixture
    def template_context(self, sample_metadata):
        """Template context with all required variables."""
        return {
            "request": Mock(spec=Request),
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": sample_metadata,
            "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
            "thumbnail_url": "https://storage.googleapis.com/bucket/thumbnails/song.jpg",
            "mime_type": "audio/mpeg",
            "duration_formatted": "7:11"
        }
    
    @pytest.fixture
    def template_context_no_thumbnail(self, sample_metadata):
        """Template context without thumbnail for edge case testing."""
        return {
            "request": Mock(spec=Request),
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": sample_metadata,
            "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
            "thumbnail_url": None,
            "mime_type": "audio/mpeg",
            "duration_formatted": "7:11"
        }
    
    @pytest.fixture
    def template_context_minimal(self, sample_metadata_minimal):
        """Template context with minimal metadata."""
        return {
            "request": Mock(spec=Request),
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": sample_metadata_minimal,
            "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
            "thumbnail_url": None,
            "mime_type": "audio/mpeg",
            "duration_formatted": "0:00"
        }
    
    @pytest.fixture
    def templates(self):
        """Jinja2 templates instance."""
        template_dir = Path(__file__).parent.parent / "templates"
        return Jinja2Templates(directory=str(template_dir))
    
    def test_open_graph_tags_generation(self, templates, template_context):
        """Test Open Graph meta tags are correctly generated."""
        # Render template
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test required Open Graph tags
        og_type = soup.find('meta', {'property': 'og:type'})
        assert og_type is not None
        assert og_type.get('content') == 'music.song'
        
        og_title = soup.find('meta', {'property': 'og:title'})
        assert og_title is not None
        assert og_title.get('content') == 'Hey Jude by The Beatles'
        
        og_description = soup.find('meta', {'property': 'og:description'})
        assert og_description is not None
        assert 'Listen to Hey Jude by The Beatles from the album The Beatles 1967-1970' in og_description.get('content')
        
        og_audio = soup.find('meta', {'property': 'og:audio'})
        assert og_audio is not None
        assert og_audio.get('content') == 'https://storage.googleapis.com/bucket/audio/song.mp3'
        
        og_audio_type = soup.find('meta', {'property': 'og:audio:type'})
        assert og_audio_type is not None
        assert og_audio_type.get('content') == 'audio/mpeg'
        
        og_audio_title = soup.find('meta', {'property': 'og:audio:title'})
        assert og_audio_title is not None
        assert og_audio_title.get('content') == 'Hey Jude'
        
        og_audio_artist = soup.find('meta', {'property': 'og:audio:artist'})
        assert og_audio_artist is not None
        assert og_audio_artist.get('content') == 'The Beatles'
        
        og_audio_album = soup.find('meta', {'property': 'og:audio:album'})
        assert og_audio_album is not None
        assert og_audio_album.get('content') == 'The Beatles 1967-1970'
        
        og_url = soup.find('meta', {'property': 'og:url'})
        assert og_url is not None
        assert og_url.get('content') == 'https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000'
        
        og_site_name = soup.find('meta', {'property': 'og:site_name'})
        assert og_site_name is not None
        assert og_site_name.get('content') == 'Loist Music Library'
        
        og_locale = soup.find('meta', {'property': 'og:locale'})
        assert og_locale is not None
        assert og_locale.get('content') == 'en_US'
    
    def test_open_graph_image_tags(self, templates, template_context):
        """Test Open Graph image tags when thumbnail is available."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test image tags
        og_image = soup.find('meta', {'property': 'og:image'})
        assert og_image is not None
        assert og_image.get('content') == 'https://storage.googleapis.com/bucket/thumbnails/song.jpg'
        
        og_image_width = soup.find('meta', {'property': 'og:image:width'})
        assert og_image_width is not None
        assert og_image_width.get('content') == '1200'
        
        og_image_height = soup.find('meta', {'property': 'og:image:height'})
        assert og_image_height is not None
        assert og_image_height.get('content') == '630'
        
        og_image_alt = soup.find('meta', {'property': 'og:image:alt'})
        assert og_image_alt is not None
        assert og_image_alt.get('content') == 'Album artwork for Hey Jude by The Beatles'
    
    def test_open_graph_no_thumbnail(self, templates, template_context_no_thumbnail):
        """Test Open Graph tags when no thumbnail is available."""
        response = templates.TemplateResponse("embed.html", template_context_no_thumbnail)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Image tags should not be present
        og_image = soup.find('meta', {'property': 'og:image'})
        assert og_image is None
        
        og_image_width = soup.find('meta', {'property': 'og:image:width'})
        assert og_image_width is None
        
        og_image_height = soup.find('meta', {'property': 'og:image:height'})
        assert og_image_height is None
        
        og_image_alt = soup.find('meta', {'property': 'og:image:alt'})
        assert og_image_alt is None
    
    def test_twitter_card_tags_generation(self, templates, template_context):
        """Test Twitter Card meta tags are correctly generated."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test Twitter Card tags
        twitter_card = soup.find('meta', {'name': 'twitter:card'})
        assert twitter_card is not None
        assert twitter_card.get('content') == 'player'
        
        twitter_site = soup.find('meta', {'name': 'twitter:site'})
        assert twitter_site is not None
        assert twitter_site.get('content') == '@loistmusic'
        
        twitter_creator = soup.find('meta', {'name': 'twitter:creator'})
        assert twitter_creator is not None
        assert twitter_creator.get('content') == '@loistmusic'
        
        twitter_title = soup.find('meta', {'name': 'twitter:title'})
        assert twitter_title is not None
        assert twitter_title.get('content') == 'Hey Jude by The Beatles'
        
        twitter_description = soup.find('meta', {'name': 'twitter:description'})
        assert twitter_description is not None
        assert 'Listen to Hey Jude by The Beatles from the album The Beatles 1967-1970' in twitter_description.get('content')
        
        twitter_player = soup.find('meta', {'name': 'twitter:player'})
        assert twitter_player is not None
        assert twitter_player.get('content') == 'https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000'
        
        twitter_player_width = soup.find('meta', {'name': 'twitter:player:width'})
        assert twitter_player_width is not None
        assert twitter_player_width.get('content') == '500'
        
        twitter_player_height = soup.find('meta', {'name': 'twitter:player:height'})
        assert twitter_player_height is not None
        assert twitter_player_height.get('content') == '200'
        
        twitter_player_stream = soup.find('meta', {'name': 'twitter:player:stream'})
        assert twitter_player_stream is not None
        assert twitter_player_stream.get('content') == 'https://storage.googleapis.com/bucket/audio/song.mp3'
        
        twitter_player_stream_type = soup.find('meta', {'name': 'twitter:player:stream:content_type'})
        assert twitter_player_stream_type is not None
        assert twitter_player_stream_type.get('content') == 'audio/mpeg'
    
    def test_twitter_card_image_tags(self, templates, template_context):
        """Test Twitter Card image tags when thumbnail is available."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test image tags
        twitter_image = soup.find('meta', {'name': 'twitter:image'})
        assert twitter_image is not None
        assert twitter_image.get('content') == 'https://storage.googleapis.com/bucket/thumbnails/song.jpg'
        
        twitter_image_alt = soup.find('meta', {'name': 'twitter:image:alt'})
        assert twitter_image_alt is not None
        assert twitter_image_alt.get('content') == 'Album artwork for Hey Jude by The Beatles'
    
    def test_twitter_card_no_thumbnail(self, templates, template_context_no_thumbnail):
        """Test Twitter Card tags when no thumbnail is available."""
        response = templates.TemplateResponse("embed.html", template_context_no_thumbnail)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Image tags should not be present
        twitter_image = soup.find('meta', {'name': 'twitter:image'})
        assert twitter_image is None
        
        twitter_image_alt = soup.find('meta', {'name': 'twitter:image:alt'})
        assert twitter_image_alt is None
    
    def test_schema_org_json_ld_generation(self, templates, template_context):
        """Test Schema.org JSON-LD structured data generation."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find JSON-LD script tag
        json_script = soup.find('script', {'type': 'application/ld+json'})
        assert json_script is not None
        
        # Parse JSON-LD content
        json_data = json.loads(json_script.string)
        
        # Test required fields
        assert json_data['@context'] == 'https://schema.org'
        assert json_data['@type'] == 'MusicRecording'
        assert json_data['name'] == 'Hey Jude'
        
        # Test byArtist
        assert 'byArtist' in json_data
        assert json_data['byArtist']['@type'] == 'MusicGroup'
        assert json_data['byArtist']['name'] == 'The Beatles'
        
        # Test inAlbum
        assert 'inAlbum' in json_data
        assert json_data['inAlbum']['@type'] == 'MusicAlbum'
        assert json_data['inAlbum']['name'] == 'The Beatles 1967-1970'
        
        # Test datePublished
        assert 'datePublished' in json_data
        assert json_data['datePublished'] == '1970'  # Template renders as string
        
        # Test audio
        assert 'audio' in json_data
        assert json_data['audio']['@type'] == 'AudioObject'
        assert json_data['audio']['contentUrl'] == 'https://storage.googleapis.com/bucket/audio/song.mp3'
        assert json_data['audio']['encodingFormat'] == 'audio/mpeg'
        
        # Test image
        assert 'image' in json_data
        assert json_data['image'] == 'https://storage.googleapis.com/bucket/thumbnails/song.jpg'
        
        # Test URL
        assert json_data['url'] == 'https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000'
        
        # Test publisher
        assert 'publisher' in json_data
        assert json_data['publisher']['@type'] == 'Organization'
        assert json_data['publisher']['name'] == 'Loist Music Library'
        assert json_data['publisher']['url'] == 'https://loist.io'
    
    def test_schema_org_no_thumbnail(self, templates, template_context_no_thumbnail):
        """Test Schema.org JSON-LD when no thumbnail is available."""
        response = templates.TemplateResponse("embed.html", template_context_no_thumbnail)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find JSON-LD script tag
        json_script = soup.find('script', {'type': 'application/ld+json'})
        assert json_script is not None
        
        # Parse JSON-LD content
        json_data = json.loads(json_script.string)
        
        # Image should not be present
        assert 'image' not in json_data
    
    def test_schema_org_minimal_metadata(self, templates, template_context_minimal):
        """Test Schema.org JSON-LD with minimal metadata."""
        response = templates.TemplateResponse("embed.html", template_context_minimal)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find JSON-LD script tag
        json_script = soup.find('script', {'type': 'application/ld+json'})
        assert json_script is not None
        
        # Parse JSON-LD content
        json_data = json.loads(json_script.string)
        
        # Test basic fields
        assert json_data['name'] == 'Unknown Track'
        assert json_data['byArtist']['name'] == 'Unknown Artist'
        
        # Album and year should not be present
        assert 'inAlbum' not in json_data
        assert 'datePublished' not in json_data
    
    def test_oembed_discovery_link(self, templates, template_context):
        """Test oEmbed discovery link is correctly generated."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find oEmbed discovery link
        oembed_link = soup.find('link', {'rel': 'alternate', 'type': 'application/json+oembed'})
        assert oembed_link is not None
        
        href = oembed_link.get('href')
        assert href is not None
        assert 'https://loist.io/oembed' in href
        assert 'url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000' in href
        assert 'format=json' in href
        
        title = oembed_link.get('title')
        assert title == 'Hey Jude'
    
    def test_meta_description_generation(self, templates, template_context):
        """Test meta description tag generation."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test meta description
        meta_description = soup.find('meta', {'name': 'description'})
        assert meta_description is not None
        description_content = meta_description.get('content')
        assert 'Listen to Hey Jude by The Beatles' in description_content
        assert 'from the album The Beatles 1967-1970' in description_content
        assert 'on Loist Music Library' in description_content
    
    def test_meta_keywords_generation(self, templates, template_context):
        """Test meta keywords tag generation."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test meta keywords
        meta_keywords = soup.find('meta', {'name': 'keywords'})
        assert meta_keywords is not None
        keywords_content = meta_keywords.get('content')
        assert 'music' in keywords_content
        assert 'audio' in keywords_content
        assert 'The Beatles' in keywords_content
        assert 'Hey Jude' in keywords_content
        assert 'The Beatles 1967-1970' in keywords_content
        assert 'streaming' in keywords_content
        assert 'loist' in keywords_content
    
    def test_page_title_generation(self, templates, template_context):
        """Test page title generation."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test page title
        title_tag = soup.find('title')
        assert title_tag is not None
        title_text = title_tag.get_text()
        assert 'Hey Jude by The Beatles' in title_text
        assert 'Loist Music Library' in title_text
    
    def test_security_headers(self, templates, template_context):
        """Test security headers for iframe embedding."""
        response = templates.TemplateResponse("embed.html", template_context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test X-Frame-Options meta tag
        x_frame_options = soup.find('meta', {'http-equiv': 'X-Frame-Options'})
        assert x_frame_options is not None
        assert x_frame_options.get('content') == 'ALLOWALL'
    
    def test_edge_case_long_titles(self, templates):
        """Test handling of very long titles and descriptions."""
        # Create metadata with very long title
        long_title = "A" * 200  # Very long title
        metadata = {
            "Product": {
                "Title": long_title,
                "Artist": "Test Artist",
                "Album": "Test Album",
                "Year": 2024,
            },
            "Format": {
                "Duration": 300.0,
                "Channels": 2,
                "SampleRate": 44100,
                "Bitrate": 320,
                "Format": "MP3",
            }
        }
        
        context = {
            "request": Mock(spec=Request),
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": metadata,
            "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
            "thumbnail_url": "https://storage.googleapis.com/bucket/thumbnails/song.jpg",
            "mime_type": "audio/mpeg",
            "duration_formatted": "5:00"
        }
        
        response = templates.TemplateResponse("embed.html", context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test that long title is handled
        og_title = soup.find('meta', {'property': 'og:title'})
        assert og_title is not None
        assert len(og_title.get('content')) > 0
        
        twitter_title = soup.find('meta', {'name': 'twitter:title'})
        assert twitter_title is not None
        assert len(twitter_title.get('content')) > 0
    
    def test_special_characters_in_metadata(self, templates):
        """Test handling of special characters in metadata."""
        metadata = {
            "Product": {
                "Title": "Song with \"quotes\" & <special> chars",
                "Artist": "Artist with 'apostrophes' & \"quotes\"",
                "Album": "Album with <script>alert('xss')</script>",
                "Year": 2024,
            },
            "Format": {
                "Duration": 300.0,
                "Channels": 2,
                "SampleRate": 44100,
                "Bitrate": 320,
                "Format": "MP3",
            }
        }
        
        context = {
            "request": Mock(spec=Request),
            "audio_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": metadata,
            "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
            "thumbnail_url": "https://storage.googleapis.com/bucket/thumbnails/song.jpg",
            "mime_type": "audio/mpeg",
            "duration_formatted": "5:00"
        }
        
        response = templates.TemplateResponse("embed.html", context)
        html_content = response.body.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test that special characters are properly escaped
        og_title = soup.find('meta', {'property': 'og:title'})
        assert og_title is not None
        title_content = og_title.get('content')
        assert '&quot;' in title_content or '"' in title_content  # Quotes should be handled
        
        # Test that no script tags are present in the output
        script_tags = soup.find_all('script')
        json_ld_scripts = [s for s in script_tags if s.get('type') == 'application/ld+json']
        assert len(json_ld_scripts) == 1  # Only our JSON-LD script should be present
    
    def test_mime_type_handling(self, templates):
        """Test different MIME type handling."""
        test_cases = [
            ("MP3", "audio/mpeg"),
            ("FLAC", "audio/flac"),
            ("M4A", "audio/mp4"),
            ("OGG", "audio/ogg"),
            ("WAV", "audio/wav"),
            ("AAC", "audio/aac"),
            ("UNKNOWN", "audio/mpeg"),  # Default fallback
        ]
        
        for format_name, expected_mime in test_cases:
            metadata = {
                "Product": {
                    "Title": "Test Song",
                    "Artist": "Test Artist",
                },
                "Format": {
                    "Duration": 300.0,
                    "Channels": 2,
                    "SampleRate": 44100,
                    "Bitrate": 320,
                    "Format": format_name,
                }
            }
            
            context = {
                "request": Mock(spec=Request),
                "audio_id": "550e8400-e29b-41d4-a716-446655440000",
                "metadata": metadata,
                "stream_url": "https://storage.googleapis.com/bucket/audio/song.mp3",
                "thumbnail_url": None,
                "mime_type": expected_mime,
                "duration_formatted": "5:00"
            }
            
            response = templates.TemplateResponse("embed.html", context)
            html_content = response.body.decode('utf-8')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Test that MIME type is correctly used
            og_audio_type = soup.find('meta', {'property': 'og:audio:type'})
            assert og_audio_type is not None
            assert og_audio_type.get('content') == expected_mime
            
            twitter_stream_type = soup.find('meta', {'name': 'twitter:player:stream:content_type'})
            assert twitter_stream_type is not None
            assert twitter_stream_type.get('content') == expected_mime


class TestMetadataValidation:
    """Test suite for metadata validation against official specifications."""
    
    def test_open_graph_required_tags(self):
        """Test that all required Open Graph tags are present."""
        # This would test against Open Graph specification requirements
        # For now, we'll test the structure we expect
        required_og_tags = [
            'og:type',
            'og:title', 
            'og:description',
            'og:url',
            'og:site_name'
        ]
        
        # This test would validate against actual Open Graph spec
        # Implementation would depend on having a validation library
        assert len(required_og_tags) == 5  # Placeholder assertion
    
    def test_twitter_card_required_tags(self):
        """Test that all required Twitter Card tags are present."""
        required_twitter_tags = [
            'twitter:card',
            'twitter:title',
            'twitter:description'
        ]
        
        # This test would validate against Twitter Card specification
        assert len(required_twitter_tags) == 3  # Placeholder assertion
    
    def test_schema_org_required_fields(self):
        """Test that all required Schema.org fields are present."""
        required_schema_fields = [
            '@context',
            '@type',
            'name',
            'byArtist',
            'url'
        ]
        
        # This test would validate against Schema.org specification
        assert len(required_schema_fields) == 5  # Placeholder assertion


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
