#!/usr/bin/env python3
"""
Test embed page with mocked GCS responses to see Open Graph and Twitter Card tags
"""
import asyncio
import sys
from pathlib import Path
import uuid

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_embed_with_mock_gcs():
    """Test embed page with mocked GCS responses"""
    try:
        from database import save_audio_metadata
        from server import embed_page
        from starlette.responses import HTMLResponse
        
        # Create test metadata
        test_uuid = str(uuid.uuid4())
        print(f"🎵 Testing embed page with mocked GCS responses")
        print(f"🆔 UUID: {test_uuid}")
        
        # Create test metadata based on the Charli XCX file
        test_metadata = {
            "artist": "Charli XCX",
            "title": "Charli xcx - Club classics (official lyric video)",
            "album": "Charli xcx - Club classics (official lyric video)",
            "year": 2024,
            "genre": "Music",
            "duration_seconds": 158.72,
            "channels": 2,
            "sample_rate": 44100,
            "bitrate": 128000,
            "format": "MP3",
        }
        
        # Save to database
        saved_record = save_audio_metadata(
            metadata=test_metadata,
            audio_gcs_path=f"gs://loist-music-library-audio/audio/{test_uuid}/test.mp3",
            thumbnail_gcs_path=f"gs://loist-music-library-audio/audio/{test_uuid}/artwork.jpg",
            track_id=test_uuid
        )
        print("✅ Test metadata saved to database")
        
        # Mock the GCS client to return fake signed URLs
        import unittest.mock
        
        with unittest.mock.patch('src.storage.gcs_client.generate_signed_url') as mock_gcs:
            # Mock the signed URL generation
            mock_gcs.return_value = "https://storage.googleapis.com/loist-music-library-audio/audio/test-signed-url.mp3"
            
            # Mock the cache to return our fake URL
            with unittest.mock.patch('src.resources.cache.get_cache') as mock_cache:
                mock_cache_instance = unittest.mock.MagicMock()
                mock_cache_instance.get.return_value = "https://storage.googleapis.com/loist-music-library-audio/audio/test-signed-url.mp3"
                mock_cache.return_value = mock_cache_instance
                
                # Create a mock request
                class MockRequest:
                    def __init__(self, audio_id):
                        self.path_params = {'audioId': audio_id}
                
                mock_request = MockRequest(test_uuid)
                
                print("🌐 Testing embed page with mocked GCS...")
                response = await embed_page(mock_request)
                
                if hasattr(response, 'status_code'):
                    print("✅ Embed page with mocked GCS executed successfully!")
                    print(f"📄 Response status: {response.status_code}")
                    
                    html_content = response.body.decode('utf-8')
                    
                    # Extract and display meta tags
                    print("\n🔍 Open Graph and Twitter Card Meta Tags:")
                    print("=" * 80)
                    
                    lines = html_content.split('\n')
                    meta_tags = []
                    for line in lines:
                        if 'og:' in line or 'twitter:' in line or 'property=' in line:
                            meta_tags.append(line.strip())
                    
                    if meta_tags:
                        for tag in meta_tags:
                            print(tag)
                    else:
                        print("❌ No meta tags found in HTML")
                        print("\n📄 First 20 lines of HTML:")
                        for i, line in enumerate(lines[:20]):
                            print(f"{i+1:2d}: {line}")
                    
                    print("=" * 80)
                    
                    # Save the HTML for inspection
                    with open("/tmp/test_embed_mock_gcs_output.html", "w") as f:
                        f.write(html_content)
                    print("💾 Full HTML saved to: /tmp/test_embed_mock_gcs_output.html")
                    
                    return html_content
                else:
                    print(f"❌ Unexpected response type: {type(response)}")
                    return None
                    
    except Exception as e:
        print(f"❌ Error testing embed page: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main test function"""
    print("🚀 Starting embed page test with mocked GCS...")
    
    await test_embed_with_mock_gcs()
    
    print("\n✅ Test completed!")
    print("\n📋 Next steps:")
    print("1. Check the generated HTML file for meta tags")
    print("2. Open the HTML file in a browser")
    print("3. Use browser dev tools to inspect the meta tags")
    print("4. Test with social media preview tools")

if __name__ == "__main__":
    asyncio.run(main())
