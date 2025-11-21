# Iframe Embedding Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: Ngrok Security Warning Blocking Iframes

**Problem:** If you're using ngrok, it may show a security warning page that blocks iframe embedding.

**Solution:**
1. Visit the ngrok URL directly in your browser first: `https://857daa7fb123.ngrok-free.app/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45`
2. Accept the security warning if prompted
3. After accepting, iframes should load properly

**Alternative:** Use `localhost` instead of ngrok for local testing:
```html
<iframe src="http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45"></iframe>
```

### Issue 2: Mixed Content (HTTP vs HTTPS)

**Problem:** If your page is served over HTTPS but the embed URL is HTTP (or vice versa), browsers will block the iframe.

**Solution:**
- Ensure both the parent page and embed URL use the same protocol
- For local testing, use HTTP for both: `http://localhost:8080`
- For production, use HTTPS for both: `https://loist.io`

### Issue 3: CORS Issues with Audio Stream

**Problem:** The audio stream from Google Cloud Storage might not have proper CORS headers.

**Solution:**
- Signed URLs from GCS should include CORS headers
- If issues persist, check GCS bucket CORS configuration
- Verify that the signed URL includes proper `Origin` header handling

### Issue 4: Iframe Not Rendering Content

**Problem:** The iframe loads but shows blank content or error message.

**Diagnosis:**
1. Check browser console (F12) for errors
2. Verify the embed URL returns 200 OK status
3. Check if X-Frame-Options header is set correctly: `X-Frame-Options: ALLOWALL`
4. Verify Content-Security-Policy: `Content-Security-Policy: frame-ancestors *`

**Solution:**
- Ensure the embed endpoint is returning proper HTML
- Check that JavaScript is executing in iframe context
- Verify audio element is being created properly

## Testing Iframe Embedding

### Test Page Setup

1. **Create test HTML file:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Iframe Embed Test</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        iframe { width: 100%; height: 250px; border: 2px solid #4A90E2; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Audio Player Iframe Test</h1>
    
    <!-- Standard Player -->
    <h2>Standard Player</h2>
    <iframe src="http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45"
            allow="autoplay; encrypted-media"></iframe>
    
    <!-- Waveform Player (Query Parameter) -->
    <h2>Waveform Player (Query Parameter)</h2>
    <iframe src="http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45?template=waveform"
            allow="autoplay; encrypted-media"></iframe>
    
    <!-- Waveform Player (Separate Endpoint) -->
    <h2>Waveform Player (Separate Endpoint)</h2>
    <iframe src="http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45/waveform"
            allow="autoplay; encrypted-media"></iframe>
</body>
</html>
```

2. **Serve via HTTP server:**
```bash
# From project root
python3 -m http.server 8000

# Open in browser
open http://localhost:8000/test_embed_iframes.html
```

### Verification Checklist

- [ ] Embed URL returns 200 OK status
- [ ] HTML content is returned (not error page)
- [ ] X-Frame-Options header is set to `ALLOWALL`
- [ ] Content-Security-Policy allows frame-ancestors
- [ ] Audio element is present in HTML
- [ ] JavaScript console shows no errors
- [ ] Audio stream URL is accessible
- [ ] Iframe loads without security warnings

## Debugging Steps

### Step 1: Check Embed URL Directly

```bash
# Test standard embed
curl -I http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45

# Check headers
curl -v http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45 2>&1 | grep -i "x-frame\|cors\|content-security"
```

**Expected Headers:**
```
X-Frame-Options: ALLOWALL
Content-Security-Policy: frame-ancestors *
```

### Step 2: Check Browser Console

1. Open browser developer tools (F12)
2. Navigate to Console tab
3. Look for errors related to:
   - CORS violations
   - Mixed content warnings
   - Network errors
   - JavaScript errors

### Step 3: Check Network Tab

1. Open browser developer tools (F12)
2. Navigate to Network tab
3. Reload the page with iframes
4. Check if embed URLs return 200 OK
5. Verify response headers are correct

### Step 4: Test Direct Link

1. Open embed URL directly in browser (not in iframe)
2. Verify player loads and works correctly
3. If it works directly but not in iframe, check:
   - CORS headers
   - X-Frame-Options
   - Content-Security-Policy
   - JavaScript execution context

## Common Error Messages

### "Refused to display in a frame because it set 'X-Frame-Options' to 'deny'"
**Solution:** Verify server returns `X-Frame-Options: ALLOWALL` header

### "Mixed Content: The page was loaded over HTTPS, but requested an insecure resource"
**Solution:** Use HTTPS for both parent page and embed URL

### "Access to audio from origin 'X' has been blocked by CORS policy"
**Solution:** Check GCS bucket CORS configuration and signed URL generation

### "Failed to load resource: net::ERR_BLOCKED_BY_CLIENT"
**Solution:** Check browser extensions or ad blockers that might block iframes

## Production Considerations

### For Production Deployment

1. **Use HTTPS:** Ensure both parent page and embed URL use HTTPS
2. **Proper CORS:** Configure GCS bucket with proper CORS headers
3. **CDN:** Consider using CDN for embed endpoint for better performance
4. **Caching:** Set appropriate cache headers for embed HTML
5. **Security:** Review and test security headers regularly

### GCS CORS Configuration

Ensure your GCS bucket has proper CORS configuration:

```json
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Range", "Accept-Ranges"],
    "maxAgeSeconds": 3600
  }
]
```

## Quick Test Script

Run this to test iframe embedding:

```bash
# Start HTTP server
python3 -m http.server 8000 &

# Open test page
open http://localhost:8000/test_embed_iframes.html

# Or use curl to test
curl -I http://localhost:8080/embed/02ceadb6-ed7c-45d8-976a-a2bfc9222d45
```

## Additional Resources

- [MDN: X-Frame-Options](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options)
- [MDN: Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)
- [MDN: CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Google Cloud Storage CORS](https://cloud.google.com/storage/docs/configuring-cors)