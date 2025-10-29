# Embed Link Implementation Status

## Executive Summary

**Status**: ✅ **IMPLEMENTED IN PRODUCTION** ⚠️ **NOT IN LOCAL DOCKER MCP SERVER**

The embed link `https://loist.io/embed/{audio_id}` **does have a functional server-side implementation** running in production at `loist.io`. However, the local Docker MCP server in this repository does NOT include embed page functionality.

**Key Finding**: When accessing `https://loist.io/embed/c7fd6016-8d62-4e1f-9f8f-4f8cdc3f8080`, you get "audio not found" (not a 404), which proves:
- ✅ Production embed server exists and is functional
- ❌ Audio ingested locally via Docker is NOT in production database/storage
- ⚠️ This local MCP server codebase does NOT contain the embed implementation

## Current State

### Production Environment (loist.io):
✅ **FULLY IMPLEMENTED**
- Live embed server serving `https://loist.io/embed/{id}` pages
- Returns proper error messages (not 404) proving functionality exists
- Likely includes: HTML templates, oEmbed endpoint, player UI
- **Note**: Production embed server codebase is separate from this MCP server repository

### Local Docker MCP Server (This Repository):
⚠️ **EMBED FUNCTIONALITY NOT INCLUDED**

#### What EXISTS in this repo:

1. **Embed URL Generation**: ✅
   - Generated in `src/tools/process_audio.py` (line 382)
   - Generated in `src/tools/query_tools.py` (line 66)
   - Returns format: `https://loist.io/embed/{audio_id}`

2. **MCP Resources**: ✅
   - `music-library://audio/{id}/stream` - Returns signed URL for audio
   - `music-library://audio/{id}/thumbnail` - Returns signed URL for artwork
   - Used by MCP clients, not web browsers

3. **Documentation**: ✅
   - Detailed specs in `mcp.md` (lines 740-788)
   - Requirements for oEmbed, Open Graph tags, HTML structure

#### What's MISSING in this repo:

1. **HTTP Route Handler**: ❌
   - No route at `/embed/{id}` to serve HTML pages
   - No HTML template for audio player
   - No static HTML generation

2. **oEmbed Endpoint**: ❌
   - No `/oembed` endpoint for rich previews
   - Required for Notion, Slack, Discord integration

3. **Web Server Mode**: ❌
   - Server only runs in STDIO mode (for MCP)
   - No HTTP mode implementation for embed pages
   - `create_http_app()` exists but only sets up MCP endpoints

4. **Player UI**: ❌
   - No HTML5 audio player component
   - No metadata display
   - No artwork rendering
   - No keyboard controls

### Why "Audio Not Found" Error?
The audio track `c7fd6016-8d62-4e1f-9f8f-4f8cdc3f8080` was ingested using the **local Docker MCP server**, which stores audio in:
- Local PostgreSQL database (`localhost:5432`)
- GCS bucket: `loist-mvp-audio-files`

The **production embed server** at `loist.io` queries a **different database/storage** where this audio doesn't exist, hence the "audio not found" error.

## Research Findings

### Best Practices for Audio Embeds

From recent research (October 2024):

1. **HTML Structure**:
   ```html
   <audio controls>
     <source src="audio.mp3" type="audio/mpeg">
     Your browser does not support the audio element.
   </audio>
   ```

2. **Required Meta Tags**:
   - oEmbed discovery link
   - Open Graph tags (`og:type`, `og:audio`, `og:image`)
   - Twitter Card tags
   - Viewport for mobile responsiveness

3. **Platform Compatibility**:
   - **Notion**: Supports iframe embeds ✅
   - **Slack**: Limited iframe support, prefers links ❌
   - **Discord**: No iframe support, uses bots instead ❌

4. **CORS Headers**: Critical for iframe embedding
   - Already configured in existing code ✅

## Implementation Requirements

To make embed links functional, implement:

### 1. HTTP Mode (High Priority)

Add HTTP transport support alongside STDIO:

```python
# src/server.py
if __name__ == "__main__":
    # Run in HTTP mode when SERVER_TRANSPORT=http
    if config.server_transport == "http":
        # FastMCP already supports this
        mcp.run(transport="http", host="0.0.0.0", port=8080)
    else:
        # STDIO mode for MCP
        mcp.run(transport="stdio")
```

### 2. Embed Page Route (High Priority)

Create `/embed/{id}` endpoint:

```python
# src/resources/embed.py
from fastmcp import FastMCP
from starlette.responses import HTMLResponse

app = FastMCP()

@app.route("/embed/{audio_id}")
async def serve_embed_page(audio_id: str):
    # Fetch metadata
    metadata = get_audio_metadata_by_id(audio_id)
    
    # Generate signed URLs
    audio_url = generate_signed_url(...)
    thumbnail_url = generate_signed_url(...)
    
    # Render HTML template
    html = render_embed_html(metadata, audio_url, thumbnail_url)
    return HTMLResponse(html)
```

### 3. HTML Template (High Priority)

Create embed page template:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- oEmbed Discovery -->
    <link rel="alternate" type="application/json+oembed" 
          href="/oembed?url=/embed/{id}" />
    
    <!-- Open Graph -->
    <meta property="og:type" content="music.song" />
    <meta property="og:title" content="{title}" />
    <meta property="og:audio" content="{audio_url}" />
    <meta property="og:image" content="{thumbnail_url}" />
    
    <!-- Twitter Cards -->
    <meta name="twitter:card" content="player" />
    
    <title>{title} by {artist}</title>
    <style>
        /* Modern, clean audio player CSS */
    </style>
</head>
<body>
    <div class="audio-player">
        <img src="{thumbnail_url}" alt="{title}" />
        <div class="metadata">
            <h1>{title}</h1>
            <p>{artist}</p>
        </div>
        <audio controls>
            <source src="{audio_url}" type="audio/mpeg">
        </audio>
    </div>
</body>
</html>
```

### 4. oEmbed Endpoint (Medium Priority)

Create `/oembed` endpoint for rich previews:

```python
@app.route("/oembed")
async def oembed_endpoint(url: str, maxwidth: int = 500, maxheight: int = 200):
    # Parse audio_id from url
    audio_id = extract_id_from_url(url)
    
    # Get metadata
    metadata = get_audio_metadata_by_id(audio_id)
    
    # Return oEmbed JSON
    return {
        "version": "1.0",
        "type": "rich",
        "title": metadata["title"],
        "author_name": metadata["artist"],
        "html": f"<iframe src='{url}' width='100%' height='200'></iframe>",
        "width": maxwidth,
        "height": maxheight,
        "thumbnail_url": generate_thumbnail_url(audio_id)
    }
```

## Design Decision: Dual-Purpose URL

Current design (from `mcp.md` line 741):
> "Every processed audio track gets a shareable URL pattern: `https://loist.io/embed/{uuid}`. This single URL serves two purposes: when accessed by embedding platforms (Notion, Slack, Coda), it returns oEmbed JSON and Open Graph meta tags that enable rich previews with an embedded iframe player. When clicked directly (email, WhatsApp, markdown links), the same URL renders a full standalone player page in the browser."

**Status**: ✅ Design documented, ❌ Not implemented

## Recommendation

### Phase 1: Basic Embed Page (MVP)
- Implement HTTP route handler at `/embed/{id}`
- Create simple HTML5 audio player
- Display metadata (title, artist, artwork)
- Basic CSS styling
- **Estimated**: 4-6 hours

### Phase 2: Rich Previews
- Add oEmbed endpoint
- Add Open Graph meta tags
- Add Twitter Card tags
- Test with Notion embeds
- **Estimated**: 3-4 hours

### Phase 3: Advanced Features
- Keyboard shortcuts (space, arrow keys)
- Waveform visualization
- Mobile responsiveness
- Custom player controls
- **Estimated**: 8-12 hours

## Files That Need Creation

1. `src/resources/embed.py` - New file for embed page handler
2. `src/templates/embed.html` - New file for HTML template
3. `src/resources/oembed.py` - New file for oEmbed endpoint
4. Update `src/server.py` - Add HTTP mode and route registration

## Testing Requirements

1. **Unit Tests**: Template rendering, URL generation
2. **Integration Tests**: End-to-end embed page access
3. **Platform Tests**: Notion embed, Slack preview, Discord link
4. **CORS Tests**: Verify iframe embedding works
5. **Mobile Tests**: Responsive design verification

## References

- [oEmbed Specification](https://oembed.com/)
- [Open Graph Protocol](https://ogp.me/)
- [Twitter Cards](https://developer.twitter.com/en/docs/twitter-for-websites/cards/overview/abouts-cards)
- Research from Perplexity Search (October 2024)

## Conclusion

### Summary of Findings:

**Production (loist.io)**: ✅ Embed functionality IS implemented and working
- Production embed server exists and serves embed pages
- Returns proper error messages when audio not found (proves implementation exists)
- Separate from this local MCP server codebase

**Local Docker MCP Server (This Repo)**: ⚠️ Embed functionality NOT included
- This repository focuses on MCP protocol implementation
- Production embed pages are in a separate codebase/service
- URL generation exists, but no HTTP route handlers for embed pages

### To Add Embed Functionality to Local Server:

1. ✅ URL generation (already exists)
2. ❌ HTTP route handler (need to implement)
3. ❌ HTML template (need to create)
4. ❌ oEmbed endpoint (need to implement)
5. ❌ HTTP transport mode (need to enable)

**Why separate implementations?**
- **MCP Server**: Optimized for MCP protocol (STDIO mode) for IDE integration
- **Production Embed Server**: Separate web application for serving embed pages
- Different deployment targets: local Docker vs Cloud Run production

**Current Capability**: 
- MCP clients can access audio via `music-library://audio/{id}/stream` resources ✅
- Production web browsers can access `https://loist.io/embed/{id}` URLs ✅
- Local web browsers cannot access embed pages (not implemented in this repo) ❌

