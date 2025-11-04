# Iframe Embedding Troubleshooting Guide

## Overview

This document explains the iframe embedding issues encountered during local development and provides solutions for testing iframe functionality in the Loist Music Library.

## Root Cause: Browser Security Restrictions

### The Problem

When testing iframe embedding locally, developers often encounter issues where iframes fail to load content, showing either:
- Broken embed icons
- "You are about to visit" security warnings
- Blank iframe content

### Why This Happens

**File Protocol Restrictions**: Browsers block iframe loading when the parent page is served via `file://` protocol due to Same-Origin Policy security restrictions. This cannot be bypassed with CORS headers or CSP policies.

**Ngrok Domain Trust Issues**: Ngrok URLs are treated as untrusted domains by browsers, triggering additional security warnings.

## Technical Investigation Results

### Headers Verification ✅

The server correctly sends iframe-friendly headers:
```
X-Frame-Options: ALLOWALL
Content-Security-Policy: frame-ancestors *
```

### CORS Configuration ✅

CORS is properly configured for cross-origin requests with permissive settings for local development.

### Browser Behavior Analysis

**File:// Protocol**: All major browsers (Chrome, Firefox, Safari) block iframe loading from file:// protocol.

**HTTP Protocol**: Iframes load successfully when served via HTTP/HTTPS protocols.

## Solutions

### 1. Use Local Web Server (Recommended)

Instead of opening HTML files directly, serve them via a local web server:

```bash
# Start local web server
python3 -m http.server 8000

# Access test file via HTTP
# Open: http://localhost:8000/test_iframe_http.html
```

**Benefits:**
- ✅ Iframes load successfully
- ✅ Same-origin policy allows embedding
- ✅ Realistic testing environment
- ✅ No browser security restrictions

### 2. Browser Security Flags (Development Only)

For testing purposes only, you can disable web security (NOT recommended for production):

**Chrome:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --disable-web-security --user-data-dir=/tmp/chrome_dev
```

**Firefox:**
```bash
firefox --new-instance --safe-mode
# Then disable relevant security settings
```

**⚠️ WARNING**: This approach is insecure and should never be used for production or regular browsing.

### 3. Ngrok Alternative Testing

Test iframe embedding using different approaches:

**Localhost Direct**: `http://localhost:8080/embed/{id}`
**Ngrok Tunnel**: `https://{ngrok-url}.ngrok-free.app/embed/{id}`
**Production URL**: When deployed

## Testing Files

### Available Test Files

1. **`test_iframe.html`** - File protocol test (shows the problem)
2. **`test_iframe_http.html`** - HTTP server test (working solution)
3. **`test_iframe_browser_behavior.sh`** - Automated testing script

### Test Script Usage

```bash
# Run comprehensive iframe behavior test
./test_iframe_browser_behavior.sh
```

This script verifies:
- Server responsiveness
- Correct iframe headers
- HTTP vs file protocol behavior

## Implementation Verification

### Current Server Configuration

The embed endpoints are properly configured with:

```python
# Security headers for iframe embedding
response.headers["X-Frame-Options"] = "ALLOWALL"
response.headers["Content-Security-Policy"] = "frame-ancestors *"
```

### CORS Middleware

```python
CORSMiddleware,
allow_origins=config.cors_origins_list,
allow_credentials=config.cors_allow_credentials,
allow_methods=config.cors_allow_methods_list,
allow_headers=config.cors_allow_headers_list,
expose_headers=config.cors_expose_headers_list,
```

## Browser-Specific Behavior

### Chrome
- Strictest Same-Origin Policy enforcement
- File protocol completely blocks iframes
- Clear console errors for blocked content

### Firefox
- Similar restrictions to Chrome
- May show more detailed security warnings
- Sometimes allows localhost iframes

### Safari
- Most restrictive iframe policies
- Additional App Transport Security (ATS) restrictions
- May block ngrok URLs entirely

## Best Practices for Testing

### 1. Development Workflow

```bash
# 1. Start Docker environment
docker-compose up -d

# 2. Start local web server for testing
python3 -m http.server 8000

# 3. Test iframe embedding
open http://localhost:8000/test_iframe_http.html

# 4. Verify oEmbed endpoints
curl "https://your-ngrok-url.ngrok-free.app/oembed?url=https://your-ngrok-url.ngrok-free.app/embed/{audio_id}"
```

### 2. Integration Testing Checklist

- [ ] Local web server serving test files
- [ ] Docker containers running (MCP server + database)
- [ ] Ngrok tunnel active and accessible
- [ ] Iframes load without security warnings
- [ ] Compact and full player views functional
- [ ] oEmbed endpoint returns correct JSON
- [ ] Open Graph tags render properly

### 3. Cross-Platform Testing

Test iframe embedding across:
- [ ] Chrome (desktop)
- [ ] Firefox (desktop)
- [ ] Safari (desktop)
- [ ] Mobile browsers (iOS Safari, Chrome Android)

## Troubleshooting

### Common Issues

#### Iframes Still Not Loading

1. **Check Protocol**: Ensure test files are served via `http://`, not `file://`
2. **Verify Server**: Confirm MCP server is running and responding
3. **Check URLs**: Ensure ngrok URLs are current and accessible
4. **Browser Cache**: Clear browser cache and try incognito mode

#### CORS Errors in Console

1. **Check Origins**: Verify CORS_ORIGINS in docker-compose.yml
2. **Server Restart**: Restart containers after configuration changes
3. **Headers**: Use browser dev tools to inspect response headers

#### Ngrok Connection Issues

1. **Tunnel Status**: Verify ngrok tunnel is active (`ngrok status`)
2. **URL Updates**: Update EMBED_BASE_URL when ngrok URL changes
3. **Firewall**: Ensure ngrok ports are not blocked

### Debug Commands

```bash
# Check server headers
curl -I https://your-ngrok-url.ngrok-free.app/embed/{audio_id}

# Test oEmbed endpoint
curl "https://your-ngrok-url.ngrok-free.app/oembed?url=https://your-ngrok-url.ngrok-free.app/embed/{audio_id}"

# Verify local server
curl -I http://localhost:8080/embed/{audio_id}

# Check Docker containers
docker-compose ps
```

## Production Considerations

### Security Headers

In production, consider more restrictive headers:

```python
# More restrictive CSP for production
response.headers["Content-Security-Policy"] = "frame-ancestors https://trusted-site.com https://another-trusted-site.com"
```

### CORS Configuration

Use specific origins instead of wildcard in production:

```yaml
CORS_ORIGINS: "https://yoursite.com,https://embed-consumer.com"
```

### Domain Validation

Implement domain whitelisting for iframe embedding requests.

## Conclusion

The iframe embedding issues are primarily caused by browser security policies that cannot be bypassed. The solution is to use proper HTTP serving for testing rather than file protocol. The server configuration is correct, and iframes will work properly in production environments.

**Key Takeaway**: Always test iframe embedding using a local web server, not file:// protocol.
