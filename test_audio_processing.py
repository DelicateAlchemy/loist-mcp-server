#!/usr/bin/env python3
"""
Test script to process audio using the MCP server tools directly
"""
import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_audio_processing():
    """Test the process_audio_complete tool directly"""
    try:
        # Import the tool function directly
        from tools.process_audio import process_audio_complete
        
        # Test data
        test_data = {
            "source": {
                "type": "http_url",
                "url": "https://tmpfiles.org/dl/4474926/charlixcx-clubclassics.mp3"
            },
            "options": {
                "maxSizeMB": 100,
                "timeout": 300
            }
        }
        
        print("🎵 Processing Charli XCX audio file...")
        print(f"📡 URL: {test_data['source']['url']}")
        
        # Call the tool
        result = await process_audio_complete(test_data)
        
        print("✅ Processing completed!")
        print(f"🎯 Audio ID: {result.get('audioId')}")
        print(f"📊 Status: {result.get('status')}")
        
        if result.get('metadata'):
            metadata = result['metadata']
            print(f"🎤 Artist: {metadata.get('artist')}")
            print(f"🎵 Title: {metadata.get('title')}")
            print(f"💿 Album: {metadata.get('album')}")
            print(f"📅 Year: {metadata.get('year')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error processing audio: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_embed_page(audio_id: str):
    """Test the embed page with the processed audio"""
    try:
        from database import get_audio_metadata_by_id
        
        print(f"\n🔍 Testing embed page for audio ID: {audio_id}")
        
        # Get metadata
        metadata = get_audio_metadata_by_id(audio_id)
        
        if metadata:
            print("✅ Metadata found in database")
            print(f"🎤 Artist: {metadata.get('artist')}")
            print(f"🎵 Title: {metadata.get('title')}")
            
            # Test embed URL
            embed_url = f"http://localhost:8080/embed/{audio_id}"
            print(f"🌐 Embed URL: {embed_url}")
            print("📋 Open this URL in a browser to test Open Graph tags")
            
        else:
            print("❌ No metadata found in database")
            
    except Exception as e:
        print(f"❌ Error testing embed page: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting audio processing test...")
    
    # Test audio processing
    result = await test_audio_processing()
    
    if result and result.get('audioId'):
        # Test embed page
        await test_embed_page(result['audioId'])
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(main())

