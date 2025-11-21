#!/usr/bin/env python3
"""
Direct test of the embed page endpoint with mock data
"""
import asyncio
import sys
from pathlib import Path
import uuid

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_embed_page_direct():
    """Test the embed page endpoint directly"""
    try:
        # Import the embed page function
        from server import embed_page
        from starlette.requests import Request
        from starlette.responses import HTMLResponse
        
        # Create a mock request
        test_uuid = str(uuid.uuid4())
        print(f"🆔 Testing with UUID: {test_uuid}")
        
        # Create a mock request object
        class MockRequest:
            def __init__(self, audio_id):
                self.path_params = {'audioId': audio_id}
        
        mock_request = MockRequest(test_uuid)
        
        print("🌐 Testing embed page endpoint...")
        
        # Call the embed page function
        response = await embed_page(mock_request)
        
        if isinstance(response, HTMLResponse):
            print("✅ Embed page function executed successfully!")
            print(f"📄 Response status: {response.status_code}")
            
            # Get the HTML content
            html_content = response.body.decode('utf-8')
            
            # Extract and display meta tags
            print("\n🔍 Open Graph and Twitter Card Meta Tags:")
            print("-" * 60)
            
            lines = html_content.split('\n')
            for line in lines:
                if 'og:' in line or 'twitter:' in line:
                    print(line.strip())
            
            print("-" * 60)
            
            # Save the HTML for inspection (to /tmp which is writable)
            with open("/tmp/test_embed_direct_output.html", "w") as f:
                f.write(html_content)
            print("💾 Full HTML saved to: /tmp/test_embed_direct_output.html")
            
            return html_content
        else:
            print(f"❌ Unexpected response type: {type(response)}")
            return None
            
    except Exception as e:
        print(f"❌ Error testing embed page: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_with_real_metadata():
    """Test with real metadata from the Charli XCX file"""
    try:
        # First, let's add some test data to the database
        from database import save_audio_metadata
        
        test_uuid = str(uuid.uuid4())
        print(f"\n🎵 Adding test data to database with UUID: {test_uuid}")
        
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
            thumbnail_gcs_path=None,
            track_id=test_uuid
        )
        print("✅ Test metadata saved to database")
        
        # Now test the embed page with this real data
        from server import embed_page
        from starlette.responses import HTMLResponse
        
        class MockRequest:
            def __init__(self, audio_id):
                self.path_params = {'audioId': audio_id}
        
        mock_request = MockRequest(test_uuid)
        
        print("🌐 Testing embed page with real metadata...")
        response = await embed_page(mock_request)
        
        if hasattr(response, 'status_code'):  # Check if it's a response object
            print("✅ Embed page with real data executed successfully!")
            
            html_content = response.body.decode('utf-8')
            
            # Extract and display meta tags
            print("\n🔍 Open Graph and Twitter Card Meta Tags (Real Data):")
            print("-" * 60)
            
            lines = html_content.split('\n')
            for line in lines:
                if 'og:' in line or 'twitter:' in line:
                    print(line.strip())
            
            print("-" * 60)
            
            # Save the HTML for inspection (to /tmp which is writable)
            with open("/tmp/test_embed_real_data_output.html", "w") as f:
                f.write(html_content)
            print("💾 Full HTML saved to: /tmp/test_embed_real_data_output.html")
            
            return html_content
        else:
            print(f"❌ Unexpected response type: {type(response)}")
            return None
            
    except Exception as e:
        print(f"❌ Error testing with real metadata: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main test function"""
    print("🚀 Starting direct embed page tests...")
    
    # Test 1: Embed page with no data (should return 404)
    print("\n📋 Test 1: Embed page with non-existent UUID")
    await test_embed_page_direct()
    
    # Test 2: Embed page with real metadata
    print("\n📋 Test 2: Embed page with real Charli XCX metadata")
    await test_with_real_metadata()
    
    print("\n✅ All tests completed!")
    print("\n📋 Next steps:")
    print("1. Check the generated HTML files for meta tags")
    print("2. Open the HTML files in a browser")
    print("3. Use browser dev tools to inspect the meta tags")
    print("4. Test with social media preview tools")

if __name__ == "__main__":
    asyncio.run(main())
