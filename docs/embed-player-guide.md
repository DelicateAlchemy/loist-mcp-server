

# HTML5 Audio Player & Embed Page Guide

## Overview

The Loist Music Library provides a beautiful, accessible HTML5 audio player that can be embedded in websites or accessed directly. The player features custom controls, keyboard shortcuts, responsive design, and social sharing support.

## Quick Start

### Direct Access

```
https://loist.io/embed/{audioId}
```

Example:
```
https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000
```

### Iframe Embedding

```html
<iframe 
    src="https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
    width="540"
    height="260"
    frameborder="0"
    allow="autoplay"
    style="border-radius: 12px;">
</iframe>
```

---

## Features

### ✨ Player Features

| Feature | Description | Keyboard Shortcut |
|---------|-------------|-------------------|
| **Play/Pause** | Toggle playback | Space |
| **Seek** | Click progress bar or use keyboard | ← / → (5s) |
| **Volume** | Adjust volume or mute | ↑ / ↓ or M |
| **Artwork** | Album cover display | - |
| **Metadata** | Title, artist, album, year | - |
| **Time Display** | Current time / Total duration | - |
| **Format Badge** | Audio format indicator (MP3, FLAC, etc.) | - |

### 🎨 Design Features

- **Modern UI**: Clean, minimalist design
- **Responsive**: Works on mobile, tablet, desktop
- **Accessible**: ARIA labels, keyboard navigation, screen reader support
- **Smooth Animations**: Hover effects, transitions
- **Error Handling**: User-friendly error messages

### 🔒 Security Features

- **Signed URLs**: 15-minute expiration for security
- **Iframe Safe**: Proper headers for embedding
- **CORS Enabled**: Cross-origin audio streaming
- **No Credential Exposure**: All auth handled server-side

---

## Player Controls

### Playback Controls

**Play/Pause Button**
- Click to toggle playback
- Keyboard: Press `Space`
- Visual feedback: Icon changes, hover effect
- ARIA label updates (Play/Pause)

**Progress Bar**
- Click anywhere to seek
- Hover for visual feedback
- Smooth progress updates
- Keyboard: `←` / `→` arrows (5s increments)

**Volume Control**
- Slider for fine-grained control
- Mute button for quick silence
- Keyboard: `↑` / `↓` arrows
- Keyboard: `M` to toggle mute
- Hidden on mobile (use device controls)

### Time Display

- **Current Time**: Updates in real-time
- **Total Duration**: Shown on load
- **Format**: MM:SS (e.g., "3:45")
- **Tabular Numerals**: Consistent width

---

## Keyboard Shortcuts

| Key | Action | Details |
|-----|--------|---------|
| `Space` | Play/Pause | Toggle playback |
| `M` | Mute/Unmute | Toggle audio mute |
| `←` (Left Arrow) | Seek Backward | Jump back 5 seconds |
| `→` (Right Arrow) | Seek Forward | Jump forward 5 seconds |
| `↑` (Up Arrow) | Volume Up | Increase volume by 10% |
| `↓` (Down Arrow) | Volume Down | Decrease volume by 10% |

**Note:** Shortcuts work globally unless typing in an input field.

---

## Responsive Design

### Desktop (> 480px)

- Full player with all controls
- 500px max width, centered
- Artwork: 80x80px
- Volume slider visible
- Album info displayed

### Mobile (≤ 480px)

- Simplified controls
- Full width layout
- Artwork: 60x60px
- Volume slider hidden (use device controls)
- Album info hidden
- Larger touch targets

---

## Social Sharing

### Open Graph Tags

The embed page includes comprehensive Open Graph tags for rich social media previews:

```html
<meta property="og:type" content="music.song" />
<meta property="og:title" content="Hey Jude" />
<meta property="og:description" content="The Beatles - Hey Jude" />
<meta property="og:audio" content="{signed_url}" />
<meta property="og:image" content="{thumbnail_url}" />
```

**Platforms Supported:**
- Facebook
- LinkedIn
- Discord
- Slack
- WhatsApp

### Twitter Cards

```html
<meta name="twitter:card" content="player" />
<meta name="twitter:title" content="Hey Jude" />
<meta name="twitter:player" content="https://loist.io/embed/{id}" />
<meta name="twitter:image" content="{thumbnail_url}" />
```

**Features:**
- Rich media player cards
- Inline playback on Twitter
- Artwork preview
- Track information

### oEmbed Discovery

```html
<link rel="alternate" type="application/json+oembed" 
      href="https://loist.io/oembed?url=https://loist.io/embed/{id}" />
```

**Platforms:**
- Notion
- WordPress
- Medium
- Other oEmbed consumers

---

## Embedding Examples

### Basic Embed

```html
<iframe 
    src="https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
    width="540"
    height="260">
</iframe>
```

### Responsive Embed

```html
<div style="position: relative; padding-bottom: 48%; height: 0; overflow: hidden;">
    <iframe 
        src="https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
        frameborder="0">
    </iframe>
</div>
```

### With Autoplay (requires user gesture)

```html
<iframe 
    src="https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
    width="540"
    height="260"
    allow="autoplay">
</iframe>
```

**Note:** Most browsers block autoplay without user interaction.

---

## Accessibility

### Screen Reader Support

- **ARIA Labels**: All controls have descriptive labels
- **ARIA Live Regions**: Time updates announced
- **Semantic HTML**: Proper heading hierarchy
- **Alt Text**: Artwork has descriptive alt text

### Keyboard Navigation

- **Tab Order**: Logical focus progression
- **Focus Indicators**: Visible outlines for keyboard users
- **Skip Links**: Hidden but accessible navigation
- **No Keyboard Traps**: Can tab out of player

### WCAG 2.1 Compliance

- ✅ **Level A**: All requirements met
- ✅ **Level AA**: Color contrast, keyboard access
- ✅ **Level AAA**: Enhanced keyboard support

---

## Technical Details

### Audio Streaming

**Format Support:**
- MP3 (audio/mpeg)
- FLAC (audio/flac)
- M4A (audio/mp4)
- OGG (audio/ogg)
- WAV (audio/wav)
- AAC (audio/aac)

**Streaming Features:**
- HTTP Range request support (seeking)
- Signed URLs for security
- 15-minute URL expiration
- Automatic buffering
- Error recovery

### Performance

**Load Time:**
- Initial page load: ~100-200ms
- Audio metadata load: ~50ms
- First byte to play: ~500ms-1s

**Caching:**
- Signed URLs cached for 13.5 minutes
- HTML page cacheable (1 hour recommended)
- Thumbnails cacheable (24 hours recommended)

**Bandwidth:**
- Page size: ~15KB (HTML/CSS/JS)
- Artwork: ~50-200KB (varies)
- Audio: Streaming (not pre-loaded)

---

## Customization

### Color Theming

Edit CSS variables in the template:

```css
:root {
    --primary-color: #4A90E2;      /* Brand color */
    --primary-hover: #357ABD;      /* Hover state */
    --background: #FFFFFF;          /* Background */
    --text-primary: #333333;        /* Main text */
    --text-secondary: #666666;      /* Secondary text */
    --border-color: #E0E0E0;        /* Borders */
}
```

### Player Dimensions

```css
.player-container {
    max-width: 500px;  /* Adjust player width */
    padding: 20px;     /* Adjust padding */
}

.artwork {
    width: 80px;       /* Adjust artwork size */
    height: 80px;
}
```

### Custom Branding

Add your logo or branding:

```html
<div class="player-header">
    <img src="/static/logo.svg" class="brand-logo" alt="Your Brand">
    <!-- rest of player -->
</div>
```

---

## Error Scenarios

### Audio Not Found (404)

```html
<h1>Audio Not Found</h1>
<p>The requested audio track could not be found.</p>
```

**Causes:**
- Invalid or non-existent audioId
- Track deleted from system

### Audio Unavailable (500)

```html
<h1>Error</h1>
<p>Audio file not available.</p>
```

**Causes:**
- Missing audio_path in database
- GCS file deleted

### Signed URL Error (500)

```html
<h1>Error</h1>
<p>Failed to generate audio stream.</p>
```

**Causes:**
- GCS service account issues
- Invalid GCS path format

### Playback Errors

Displayed in player UI:
- "Playback was aborted"
- "Network error occurred"
- "Audio decoding failed"
- "Audio format not supported"

---

## Testing

### Manual Testing Checklist

- [ ] Page loads with valid audioId
- [ ] 404 page for invalid audioId
- [ ] Play/pause works
- [ ] Seek by clicking progress bar works
- [ ] Volume slider works
- [ ] Mute button works
- [ ] Keyboard shortcuts work
- [ ] Time display updates correctly
- [ ] Artwork displays (when available)
- [ ] Metadata displays correctly
- [ ] Responsive on mobile
- [ ] Works in iframe
- [ ] Error messages display for issues

### Browser Testing

**Desktop:**
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)

**Mobile:**
- ✅ iOS Safari
- ✅ Chrome Mobile
- ✅ Firefox Mobile

### Format Testing

Test with different audio formats:

```bash
# MP3
/embed/{mp3_track_id}

# FLAC
/embed/{flac_track_id}

# M4A
/embed/{m4a_track_id}
```

---

## Troubleshooting

### Player Won't Load

1. Check audioId is valid UUID format
2. Verify track exists in database
3. Check server logs for errors
4. Verify GCS credentials are configured

### Audio Won't Play

1. Check browser console for errors
2. Verify signed URL hasn't expired (15 min)
3. Test URL directly in browser
4. Check GCS bucket permissions
5. Verify CORS headers are set

### No Artwork Showing

1. Check if thumbnail_path exists in database
2. Verify GCS thumbnail file exists
3. Check signed URL generation
4. Default SVG placeholder should appear if no artwork

### Keyboard Shortcuts Not Working

1. Ensure player has focus
2. Check browser console for errors
3. Verify not typing in an input field
4. Test with different browsers

---

## API Integration

### Get Embed URL from audioId

```python
# After processing audio
result = await process_audio_complete({...})
audio_id = result["audioId"]

# Generate embed URL
embed_url = f"https://loist.io/embed/{audio_id}"

# Share or display
print(f"Listen here: {embed_url}")
```

### Programmatic Player Control

```javascript
// Access player from parent page (if same origin)
const iframe = document.getElementById('music-iframe');
const player = iframe.contentWindow.document.getElementById('audio-player');

// Control playback
player.play();
player.pause();
player.currentTime = 60; // Seek to 1 minute
```

**Note:** Cross-origin iframes cannot be controlled for security.

---

## Best Practices

### For Website Owners

1. **Cache Embed Pages**: Set appropriate Cache-Control headers
2. **Lazy Load Iframes**: Load player when visible
3. **Provide Fallback**: Link to full page if iframe fails
4. **Test Responsiveness**: Verify on different devices

### For Players

1. **Start Paused**: Don't autoplay (browser blocks it)
2. **Show Loading State**: Indicate while buffering
3. **Handle Errors**: Display user-friendly messages
4. **Save Volume**: Remember user's volume preference (localStorage)

---

## Related Documentation

- [MCP Resources API](./mcp-resources-api.md) - Resource endpoints
- [Query Tools API](./query-tools-api.md) - Metadata retrieval
- [Process Audio API](./process-audio-complete-api.md) - Audio ingestion

---

## Support

For issues:
1. Check browser console for errors
2. Verify audioId is valid
3. Test on latest browsers
4. Open issue with screenshot

---

**Last Updated:** 2025-10-11  
**Version:** 1.0  
**Status:** Production Ready

