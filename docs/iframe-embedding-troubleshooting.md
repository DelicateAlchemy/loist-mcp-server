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

### Issue 3: CORS Issues with Audio Stream or Waveform SVGs

**Problem:** The audio stream or waveform SVG from Google Cloud Storage might not have proper CORS headers.

**Solution:**
- Signed URLs from GCS should include CORS headers
- If issues persist, check GCS bucket CORS configuration
- Verify that the signed URL includes proper `Origin` header handling
- For waveform SVGs, ensure CORS is configured on the GCS bucket

**CORS Configuration:**
The GCS bucket must have CORS configured to allow browser access to waveform SVGs. Use the provided scripts:

```bash
# Shell script
./scripts/configure-gcs-cors.sh

# Python script
python scripts/configure_gcs_cors.py
```

**Verify CORS Configuration:**
```bash
gsutil cors get gs://loist-mvp-audio-files
```

**Common CORS Errors:**
- `Access to fetch at 'https://storage.googleapis.com/...' from origin '...' has been blocked by CORS policy`
- `No 'Access-Control-Allow-Origin' header is present on the requested resource`
- `Failed to load resource: net::ERR_FAILED`

**Solutions:**
1. Configure CORS on the GCS bucket (see above)
2. Clear browser cache or do hard refresh (Ctrl+Shift+R)
3. Verify signed URL is generated correctly
4. Check that waveform SVG exists in GCS
5. Verify CORS headers are present in response

### Issue 4: Iframe Not Rendering Content

**Problem:** The iframe loads but shows blank content or error message.

**Diagnosis:**
1. Check browser console (F12) for errors
2. Verify the embed URL returns 200 OK status
3. Verify Content-Security-Policy: `Content-Security-Policy: frame-ancestors *`
4. Check for CORS errors when loading waveform SVGs
5. Verify JavaScript is executing in iframe context

**Solution:**
- Ensure the embed endpoint is returning proper HTML
- Check that JavaScript is executing in iframe context
- Verify audio element is being created properly
- For waveform players, check if waveform SVG is loading correctly
- Verify CORS is configured on GCS bucket for waveform SVGs

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
- [ ] Content-Security-Policy allows frame-ancestors (`frame-ancestors *`)
- [ ] Audio element is present in HTML
- [ ] JavaScript console shows no errors
- [ ] Audio stream URL is accessible
- [ ] Iframe loads without security warnings
- [ ] For waveform players: CORS is configured on GCS bucket
- [ ] For waveform players: Waveform SVG loads without CORS errors
- [ ] For waveform players: Waveform SVG displays correctly

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
Content-Security-Policy: frame-ancestors *
```

**Note:** We use `Content-Security-Policy: frame-ancestors *` instead of `X-Frame-Options` as it's the modern standard and provides better control over iframe embedding.

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
3. For waveform players, verify waveform SVG loads correctly
4. If it works directly but not in iframe, check:
   - CORS headers (for waveform SVGs)
   - Content-Security-Policy (frame-ancestors *)
   - JavaScript execution context
   - Browser console for errors

## Common Error Messages

### "Refused to display in a frame because it set 'X-Frame-Options' to 'deny'"
**Solution:** Verify server returns `Content-Security-Policy: frame-ancestors *` header (we use CSP instead of X-Frame-Options)

### "Mixed Content: The page was loaded over HTTPS, but requested an insecure resource"
**Solution:** Use HTTPS for both parent page and embed URL

### "Access to audio from origin 'X' has been blocked by CORS policy"
**Solution:** Check GCS bucket CORS configuration and signed URL generation

### "Access to fetch at 'https://storage.googleapis.com/...' from origin '...' has been blocked by CORS policy"
**Solution:** 
1. Configure CORS on the GCS bucket (see CORS Configuration section)
2. Clear browser cache or do hard refresh (Ctrl+Shift+R)
3. Verify signed URL is generated correctly
4. Check that waveform SVG exists in GCS
5. Verify CORS headers are present in response

### "No 'Access-Control-Allow-Origin' header is present on the requested resource"
**Solution:** 
1. Configure CORS on the GCS bucket
2. Verify CORS configuration includes the correct origin
3. Check that signed URL includes proper headers
4. Clear browser cache and retry

### "Failed to load resource: net::ERR_FAILED"
**Solution:** 
1. Check if resource exists in GCS
2. Verify signed URL is valid and not expired
3. Check CORS configuration on GCS bucket
4. Check browser console for detailed error messages
5. Verify network connectivity

### "Failed to load resource: net::ERR_BLOCKED_BY_CLIENT"
**Solution:** Check browser extensions or ad blockers that might block iframes or CORS requests

## Production Considerations

### For Production Deployment

1. **Use HTTPS:** Ensure both parent page and embed URL use HTTPS
2. **Proper CORS:** Configure GCS bucket with proper CORS headers
3. **CDN:** Consider using CDN for embed endpoint for better performance
4. **Caching:** Set appropriate cache headers for embed HTML
5. **Security:** Review and test security headers regularly

### GCS CORS Configuration

Ensure your GCS bucket has proper CORS configuration for waveform SVGs:

```json
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "OPTIONS"],
    "responseHeader": [
      "Content-Type",
      "Content-Length",
      "Content-Range",
      "Accept-Ranges",
      "Range",
      "Cache-Control",
      "Access-Control-Allow-Origin",
      "Access-Control-Allow-Methods",
      "Access-Control-Allow-Headers"
    ],
    "maxAgeSeconds": 3600
  }
]
```

**Configuration Details:**
- **Origin**: `*` (allows requests from any origin)
- **Methods**: `GET`, `HEAD`, `OPTIONS` (for CORS preflight)
- **Response Headers**: Allows all necessary headers for browser access
- **Max Age**: 3600 seconds (1 hour) for CORS preflight caching

**Configure CORS:**
```bash
# Use the provided scripts
./scripts/configure-gcs-cors.sh
# or
python scripts/configure_gcs_cors.py

# Or manually with gsutil
gsutil cors set cors-config.json gs://loist-mvp-audio-files
```

**Verify CORS Configuration:**
```bash
gsutil cors get gs://loist-mvp-audio-files
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