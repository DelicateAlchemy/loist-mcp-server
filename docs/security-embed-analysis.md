# Embed Implementation Security Analysis & Action Plan

**Date**: 2025-01-09  
**Analysis**: Embed endpoint security vulnerabilities  
**Priority**: HIGH

## Executive Summary

The current embed implementation (`/embed/{audioId}`) has several security vulnerabilities that could expose private content and enable abuse. This analysis identifies the issues and provides an actionable remediation plan.

---

## ✅ Current Security Measures (Working)

1. **UUID Validation**: Validation function exists (`src/storage/manager.py`)
2. **Signed URLs**: GCS signed URLs with 15-minute expiration
3. **Error Handling**: Proper 404 responses for non-existent audio
4. **Content-Type**: Proper MIME type handling

---

## 🚨 Security Vulnerabilities Identified

### **HIGH SEVERITY**

#### 1. **UUID Enumeration Attack Risk**
- **Issue**: No UUID validation on embed endpoint (`src/server.py:678`)
- **Risk**: Attackers can enumerate UUIDs to discover private content
- **Impact**: Unauthorized access to audio files
- **Current Behavior**: Any string accepted as audioId parameter

#### 2. **No Rate Limiting**
- **Issue**: Unlimited requests to embed endpoint
- **Risk**: 
  - UUID enumeration attacks
  - Resource exhaustion (DDoS)
  - Signed URL generation abuse
- **Impact**: Service degradation, increased costs

#### 3. **No Access Control**
- **Issue**: Completely public endpoint - no authentication/authorization
- **Risk**: Anyone can access any audio by guessing UUID
- **Impact**: Privacy violations, content piracy

$$CRITICAL$$: Currently, ALL audio files are publicly accessible by anyone who knows the UUID.

#### 4. **Security Headers Misconfiguration**
- **Issue**: Lines 788-789 in `src/server.py`:
  ```python
  response.headers["X-Frame-Options"] = "ALLOWALL"
  response.headers["Content-Security-Policy"] = "frame-ancestors *"
  ```
- **Risk**: Allows embedding on ANY website (including malicious sites)
- **Impact**: Clickjacking, phishing attacks

#### 5. **Signed URL Exposure**
- **Issue**: Signed URLs exposed in HTML source (templates/embed.html)
- **Risk**: URLs can be scraped and used outside of context
- **Impact**: Direct access without visiting embed page
- **Mitigation**: URLs expire in 15 minutes, but still a concern

### **MEDIUM SEVERITY**

#### 6. **Error Information Disclosure**
- **Issue**: Stack traces exposed in error responses (line 796)
- **Risk**: Reveals internal structure/information
- **Impact**: Aids attackers in understanding system

#### 7. **No Request Validation**
- **Issue**: UUID not validated before database query
- **Risk**: Potential injection attacks (though mitigated by PostgreSQL)
- **Impact**: Unnecessary database load

---

## 📋 Action Plan

### **Phase 1: Immediate Fixes (Today)**

#### 1.1 Add UUID Validation
**File**: `src/server.py`  
**Location**: Line 678 (after extracting audioId)

```python
# Extract audioId from path parameters
audioId = request.path_params['audioId']

# Validate UUID format
from src.storage.manager import FilenameGenerator
filename_gen = FilenameGenerator()
if not filename_gen.validate_uuid(audioId):
    logger.warning(f"Invalid UUID format: {audioId}")
    return HTMLResponse(
        content="<h1>Invalid Request</グラ><p>The requested audio ID is invalid.</p>",
        status_code=400
    )
```

#### 1.2 Add Rate Limiting
**Approach**: Implement per-IP rate limiting using middleware

**Option A**: Use Starlette's built-in rate limiting
```python
from starlette.middleware import Middleware
from starlette.middleware.rate_limit import RateLimitMiddleware

app.add_middleware(
    RateLimitMiddleware,
    rate_limit_function=lambda request: "10/minute",  # Per IP
    key_function=lambda request: request.client.host
)
```

**Option B**: Custom rate limiting for embed endpoint
```python
from collections import defaultdict
from datetime import datetime, timedelta

# In-memory rate limiter (move to Redis for production)
rate_limiter = defaultdict(list)

def check_rate_limit(client_ip: str, limit: int = 20, window: int = 60) -> bool:
    """Check if client exceeded rate limit"""
    now = datetime.now()
    minute_ago = now - timedelta(seconds=window)
    
    # Clean old entries
    rate_limiter[client_ip] = [
        ts for ts in rate_limiter[client_ip] if ts > minute_ago
    ]
    
    # Check limit
    if len(rate_limiter[client_ip]) >= limit:
        return False
    
    # Add current request
    rate_limiter[client_ip].append(now)
    return True
```

**Usage in embed endpoint**:
```python
# At start of embed_page function
client_ip = request.client.host
if not check_rate_limit(client_ip, limit=20, window=60):
    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
    return HTMLResponse(
        content="<h1>Rate Limit Exceeded</h1><p>Too many requests. Please try again later.</p>",
        status_code=429
    )
```

#### 1.3 Improve Security Headers
**File**: `src/server.py:788-789`

**Current**:
```python
response.headers["X-Frame-Options"] = "ALLOWALL"
response.headers["Content-Security-Policy"] = "frame-ancestors *"
```

**Updated** (Restrict to specific domains OR make configurable):
```python
# Option 1: Restrict to trusted domains
allowed_domains = config.get("ALLOWED_EMBED_DOMAINS", "*").split(",")
response.headers["Content-Security-Policy"] = f"frame-ancestors {' '.join(allowed_domains)}"

# Option 2: Make it configurable via environment variable
# EMBED_ALLOWED_DOMAINS=https://example.com,https://trusted-site.com
```

#### 1.4 Sanitize Error Messages
**File**: `src/server.py:796`

**Current**:
```python
return HTMLResponse(
    content=f"<h1>Error</h1><p>An unexpected error occurred: {str(e)}</p>",
    status_code=500
)
```

**Updated**:
```python
logger.exception(f"Error rendering embed page: {e}")
return HTMLResponse(
    content="<h1>Error</h1><p>An unexpected error occurred. Please try again later.</p>",
    status_code=500
)
```

### **Phase 2: Access Control (Next Sprint)**

#### 2.1 Add Private/Public Flag to Database
```sql
ALTER TABLE audio_tracks ADD COLUMN is_public BOOLEAN DEFAULT true;
CREATE INDEX idx_audio_tracks_is_public ON audio_tracks(is_public);
```

#### 2.2 Implement Access Check
```python
# After getting metadata
if not metadata.get("is_public", True):
    # Check authentication
    if not request.user.is_authenticated:
        return HTMLResponse(
            content="<h1>Access Denied</h1><p>This content is private.</p>",
            status_code=403
        )
    # Check user permissions
    # ... additional logic for authorized users
```

#### 2.3 Add Authentication Middleware
For private tracks, require authentication token in query parameter or header:
```python
# Accept either query param or header
auth_token = request.query_params.get('token') or request.headers.get('Authorization')
```

### **Phase 3: Enhanced Security (Future)**

#### 3.1 Move to Redis for Rate Limiting
- Current in-memory solution won't work across multiple instances
- Use Redis for distributed rate limiting

#### 3.2 Implement Referrer Checking
- Verify that embed requests come from allowed domains
- Use `Origin` or `Referer` header validation

#### 3.3 Add Request Signing
- Generate signed embed URLs that expire
- Prevents URL sharing/bot abuse

#### 3.4 Monitoring & Alerting
- Log all failed UUID attempts
- Alert on suspicious patterns (enumeration attacks)
- Track signed URL generation rate

---

## 🎯 Recommended Implementation Order

### **Priority 1** (Today - Critical Security)
1. ✅ Add UUID validation (5 minutes)
2. ✅ Sanitize error messages (2 minutes)
3. ⚠️ Add basic rate limiting (30 minutes)
4. ⚠️ Improve security headers (10 minutes)

### **Priority 2** (This Week)
5. Add private/public flag to database
6. Implement access control check
7. Add comprehensive logging

### **Priority 3** (Next Sprint)
8. Move to Redis rate limiting
9. Add referrer checking
10. Implement request signing

---

## 📊 Testing Checklist

- [ ] UUID validation rejects invalid formats
- [ ] Rate limiting blocks excessive requests
- [ ] Private tracks return 403 for unauthenticated users
- [ ] Security headers restrict iframe embedding appropriately
- [ ] Error messages don't leak sensitive information
- [ ] Signed URLs expire after 15 minutes
- [ ] Monitoring logs suspicious activity

---

## 🔒 Security Best Practices Summary

1. **Never trust user input** - Always validate UUIDs
2. **Limit exposure** - Rate limit public endpoints
3. **Control access** - Implement authentication for private content
4. **Monitor abuse** - Log and alert on suspicious patterns
5. **Principle of least privilege** - Only expose what's necessary
6. **Defense in depth** - Multiple layers of security
7. **Fail securely** - Don't leak information in errors

---

## 📝 Implementation Notes

### UUID Validation Function Location
- File: `src/storage/manager.py:150`
- Function: `validate_uuid(audio_id: str) -> bool`
- Should be imported and used in embed endpoint

### Current UUID Format
- Standard UUID v4: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`
- Length: 36 characters
- Regex: `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`

### Signed URL Expiration
- Current: 15 minutes (`url_expiration_minutes=15`)
- Consider: Reducing to 5 minutes for tighter security
- Trade-off: User experience vs security

---

## 🚀 Quick Start Implementation

Run these commands to implement Priority 1 fixes:

```bash
# 1. Make changes to src/server.py
# 2. Test locally
docker exec music-library-mcp python3 -c "
import asyncio
from src.server import embed_page
# Test with invalid UUID
# Test with valid UUID
"

# 3. Commit changes
git add src/server.py
git commit -m "security: Add UUID validation and rate limiting to embed endpoint"
```

---

**Report Generated**: 2025-01-09  
**Next Review**: After Priority 1 implementation  
**Status**: AWAITING APPROVAL FOR IMPLEMENTATION


