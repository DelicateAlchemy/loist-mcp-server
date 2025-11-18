#!/usr/bin/env python3
"""
Simplified test script to process audio metadata without GCS upload
"""
import asyncio
import sys
from pathlib import Path
import uuid

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_audio_metadata_extraction():
    """Test metadata extraction without GCS upload"""
    try:
        # Import the metadata extraction function
        from metadata.extractor import extract_metadata
        
        # Test with the Charli XCX file
        test_url = "https://tmpfiles.org/dl/4474926/charlixcx-clubclassics.mp3"
        
        print("🎵 Testing metadata extraction from Charli XCX file...")
        print(f"📡 URL: {test_url}")
        
        # First, let's download the file locally
        from src.downloader import download_from_url
        
        print("📥 Downloading file...")
        temp_file = download_from_url(
            url=test_url,
            max_size_mb=100,
            timeout_seconds=300
        )
        print(f"✅ Downloaded to: {temp_file}")
        
        # Extract metadata
        print("🔍 Extracting metadata...")
        metadata = extract_metadata(str(temp_file))
        
        print("✅ Metadata extraction completed!")
        print(f"🎤 Artist: {metadata.get('artist', 'Unknown')}")
        print(f"🎵 Title: {metadata.get('title', 'Unknown')}")
        print(f"💿 Album: {metadata.get('album', 'Unknown')}")
        print(f"📅 Year: {metadata.get('year', 'Unknown')}")
        print(f"🎼 Genre: {metadata.get('genre', 'Unknown')}")
        print(f"⏱️ Duration: {metadata.get('duration', 0)} seconds")
        print(f"🎧 Format: {metadata.get('format', 'Unknown')}")
        print(f"🖼️ Has artwork: {'Yes' if metadata.get('artwork_path') else 'No'}")
        
        # Generate a test UUID
        test_uuid = str(uuid.uuid4())
        print(f"🆔 Generated test UUID: {test_uuid}")
        
        # Test embed URL
        embed_url = f"http://localhost:8080/embed/{test_uuid}"
        print(f"🌐 Test embed URL: {embed_url}")
        
        return {
            "audio_id": test_uuid,
            "metadata": metadata,
            "embed_url": embed_url
        }
        
    except Exception as e:
        print(f"❌ Error in metadata extraction: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_embed_page_with_metadata():
    """Test the embed page template with extracted metadata"""
    try:
        from starlette.templating import Jinja2Templates
        from pathlib import Path
        
        # Load the embed template
        templates = Jinja2Templates(directory="/app/templates")
        
        # Mock metadata (using the extracted data, matching template structure)
        mock_metadata = {
            "Product": {
                "Title": "Charli xcx - Club classics (official lyric video)",
                "Artist": "Charli XCX",
                "Album": "Charli xcx - Club classics (official lyric video)",
                "Year": 2024,
                "Genre": ["Music"],
                "Duration": 158.72
            }
        }
        
        # Mock signed thumbnail URL
        mock_thumbnail_url = "https://example.com/thumbnail.jpg"
        
        # Render the template
        template = templates.get_template("embed.html")
        html_content = template.render(
            metadata=mock_metadata,
            audio_id="test-uuid-123",
            stream_url="https://example.com/stream.mp3",
            mime_type="audio/mpeg",
            thumbnail_url=mock_thumbnail_url
        )
        
        print("\n🎨 Testing embed page template...")
        print("📄 Generated HTML preview:")
        print("-" * 50)
        
        # Extract and display the meta tags
        lines = html_content.split('\n')
        for line in lines:
            if 'og:' in line or 'twitter:' in line:
                print(line.strip())
        
        print("-" * 50)
        
        # Save the HTML for inspection
        with open("test_embed_output.html", "w") as f:
            f.write(html_content)
        print("💾 Full HTML saved to: test_embed_output.html")
        
        return html_content
        
    except Exception as e:
        print(f"❌ Error testing embed page: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main test function"""
    print("🚀 Starting simplified audio metadata test...")
    
    # Test metadata extraction
    result = await test_audio_metadata_extraction()
    
    if result:
        # Test embed page template
        await test_embed_page_with_metadata()
    
    print("\n✅ Test completed!")
    print("\n📋 Next steps:")
    print("1. Open test_embed_output.html in a browser")
    print("2. Check the meta tags in the HTML source")
    print("3. Test with social media preview tools")

if __name__ == "__main__":
    asyncio.run(main())
