#!/usr/bin/env python3
"""
Simple test to generate Open Graph and Twitter Card HTML directly
"""
import asyncio
import sys
from pathlib import Path
import uuid

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def generate_embed_html(metadata, audio_id, stream_url, thumbnail_url):
    """Generate embed HTML with Open Graph and Twitter Card tags"""
    
    # Extract metadata
    title = metadata.get("title", "Untitled")
    artist = metadata.get("artist", "Unknown Artist")
    album = metadata.get("album", "")
    year = metadata.get("year", "")
    genre = metadata.get("genre", "")
    duration = metadata.get("duration_seconds", 0)
    
    # Format duration
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    duration_str = f"{minutes}:{seconds:02d}" if duration > 0 else "Unknown"
    
    # Generate description
    description = f"Listen to {title} by {artist}"
    if album:
        description += f" from the album {album}"
    
    # Twitter description (shorter)
    twitter_description = f"{artist}"
    if album:
        twitter_description += f" - {album}"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} by {artist} - Loist Music Library</title>
    
    <!-- oEmbed Discovery -->
    <link rel="alternate" type="application/json+oembed" 
          href="https://loist.io/oembed?url=https://loist.io/embed/{audio_id}&format=json" 
          title="{title}" />
    
    <!-- Open Graph Meta Tags -->
    <meta property="og:type" content="music.song" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:audio" content="{stream_url}" />
    <meta property="og:audio:type" content="audio/mpeg" />
    <meta property="og:url" content="https://loist.io/embed/{audio_id}" />
    <meta property="og:site_name" content="Loist Music Library" />
    {f'<meta property="og:image" content="{thumbnail_url}" />' if thumbnail_url else ''}
    
    <!-- Twitter Card Meta Tags -->
    <meta name="twitter:card" content="player" />
    <meta name="twitter:title" content="{title}" />
    <meta name="twitter:description" content="{twitter_description}" />
    {f'<meta name="twitter:image" content="{thumbnail_url}" />' if thumbnail_url else ''}
    
    <!-- Additional Meta Tags -->
    <meta name="description" content="{description}" />
    <meta name="author" content="{artist}" />
    <meta name="music:musician" content="{artist}" />
    <meta name="music:album" content="{album}" />
    <meta name="music:release_date" content="{year}" />
    <meta name="music:duration" content="{int(duration)}" />
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 600px;
            text-align: center;
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .title {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }}
        .artist {{
            font-size: 1.5em;
            margin-bottom: 20px;
            opacity: 0.9;
        }}
        .album {{
            font-size: 1.2em;
            margin-bottom: 10px;
            opacity: 0.8;
        }}
        .meta {{
            font-size: 1em;
            margin-bottom: 30px;
            opacity: 0.7;
        }}
        .player {{
            margin: 30px 0;
        }}
        audio {{
            width: 100%;
            height: 50px;
        }}
        .info {{
            font-size: 0.9em;
            opacity: 0.6;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="title">{title}</h1>
        <p class="artist">{artist}</p>
        {f'<p class="album">{album}</p>' if album else ''}
        <div class="meta">
            {f'<span>{year}</span> • ' if year else ''}
            {f'<span>{genre}</span> • ' if genre else ''}
            <span>{duration_str}</span>
        </div>
        
        <div class="player">
            <audio controls preload="metadata">
                <source src="{stream_url}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
        
        <div class="info">
            <p>Powered by <strong>Loist Music Library</strong></p>
            <p>Share this track: <a href="https://loist.io/embed/{audio_id}" style="color: #fff;">https://loist.io/embed/{audio_id}</a></p>
        </div>
    </div>
</body>
</html>"""
    
    return html

async def test_embed_html_generation():
    """Test Open Graph and Twitter Card HTML generation"""
    try:
        from database import save_audio_metadata
        
        # Create test metadata
        test_uuid = str(uuid.uuid4())
        print(f"🎵 Testing Open Graph and Twitter Card HTML generation")
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
        
        # Generate mock URLs
        stream_url = f"https://storage.googleapis.com/loist-music-library-audio/audio/{test_uuid}/test.mp3"
        thumbnail_url = f"https://storage.googleapis.com/loist-music-library-audio/audio/{test_uuid}/artwork.jpg"
        
        # Generate HTML
        print("🎨 Generating HTML with Open Graph and Twitter Card tags...")
        html_content = generate_embed_html(test_metadata, test_uuid, stream_url, thumbnail_url)
        
        # Extract and display meta tags
        print("\n🔍 Open Graph and Twitter Card Meta Tags:")
        print("=" * 80)
        
        lines = html_content.split('\n')
        meta_tags = []
        for line in lines:
            if 'og:' in line or 'twitter:' in line or 'property=' in line or 'name=' in line:
                meta_tags.append(line.strip())
        
        for tag in meta_tags:
            print(tag)
        
        print("=" * 80)
        
        # Save the HTML for inspection
        with open("/tmp/test_embed_simple_output.html", "w") as f:
            f.write(html_content)
        print("💾 Full HTML saved to: /tmp/test_embed_simple_output.html")
        
        return html_content
        
    except Exception as e:
        print(f"❌ Error generating HTML: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main test function"""
    print("🚀 Starting Open Graph and Twitter Card HTML generation test...")
    
    await test_embed_html_generation()
    
    print("\n✅ Test completed!")
    print("\n📋 Next steps:")
    print("1. Check the generated HTML file for meta tags")
    print("2. Open the HTML file in a browser")
    print("3. Use browser dev tools to inspect the meta tags")
    print("4. Test with social media preview tools")
    print("5. Copy the HTML file locally: docker cp music-library-mcp:/tmp/test_embed_simple_output.html .")

if __name__ == "__main__":
    asyncio.run(main())
