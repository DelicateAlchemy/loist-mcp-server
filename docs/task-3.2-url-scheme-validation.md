# URL Scheme Validation - Subtask 3.2

## Overview

This document covers the URL scheme validation implementation for the Loist Music Library MCP Server. It provides comprehensive security validation to prevent dangerous protocol usage and ensure only safe HTTP/HTTPS downloads.

## Table of Contents

- [Security Model](#security-model)
- [Validation Components](#validation-components)
- [Allowed Schemes](#allowed-schemes)
- [Blocked Schemes](#blocked-schemes)
- [Usage](#usage)
- [Testing](#testing)
- [Security Considerations](#security-considerations)

## Security Model

### Threat Prevention

The URL scheme validation protects against:

1. **Local File Access**: Prevents `file://` URLs from accessing server filesystem
2. **Protocol Smuggling**: Blocks non-HTTP protocols
3. **Code Execution**: Prevents `javascript:` and `vbscript:` schemes
4. **Data Exfiltration**: Blocks protocols that could leak data

### Defense in Depth

URL validation is the **first line of defense** in our security model:

```
Request → URL Scheme Validation → SSRF Protection → Download
  ↓              ↓                      ↓               ↓
Block       Block dangerous       Block private    Safe download
malformed   protocols             IPs              with limits
```

## Validation Components

### 1. URLSchemeValidator Class

Main validation class with comprehensive checks:

```python
from src.downloader.validators import URLSchemeValidator

# Validate scheme only
URLSchemeValidator.validate_scheme(url)

# Validate hostname
URLSchemeValidator.validate_hostname(url)

# Normalize URL
normalized = URLSchemeValidator.normalize_url(url)

# Complete validation
validated = URLSchemeValidator.validate(url)
```

### 2. Convenience Function

```python
from src.downloader import validate_url

# Simple validation
url = validate_url("https://example.com/audio.mp3")
```

## Allowed Schemes

Only these schemes are permitted:

| Scheme | Use Case | Example |
|--------|----------|---------|
| `http` | Unencrypted HTTP | `http://example.com/audio.mp3` |
| `https` | Encrypted HTTP (preferred) | `https://example.com/audio.mp3` |

**Total Allowed:** 2 schemes

## Blocked Schemes

These schemes are explicitly blocked for security:

| Scheme | Reason | Risk |
|--------|--------|------|
| `file` | Local filesystem access | Server compromise |
| `ftp` / `ftps` | Non-HTTP protocols | Bypass security controls |
| `data` | Inline data URLs | Resource exhaustion |
| `javascript` | Code execution | XSS/code injection |
| `vbscript` | Code execution | XSS/code injection |
| `about` | Browser internal | Undefined behavior |
| `chrome` | Browser internal | Undefined behavior |
| `jar` | Java archives | Code execution |
| `ws` / `wss` | WebSocket | Not for file downloads |
| `ssh` | SSH protocol | Unauthorized access |
| `telnet` | Telnet protocol | Unauthorized access |
| `ldap` | LDAP protocol | Information disclosure |
| `dict` | Dictionary protocol | Information disclosure |
| `gopher` | Gopher protocol | Deprecated, insecure |

**Total Blocked:** 14+ dangerous schemes

## Usage

### Basic Validation

```python
from src.downloader import validate_url, URLValidationError

try:
    # Validate URL before downloading
    validated_url = validate_url("https://example.com/audio.mp3")
    print(f"Valid URL: {validated_url}")
    
except URLValidationError as e:
    print(f"Invalid URL: {e}")
```

### Validation with HTTPDownloader

The HTTPDownloader automatically validates URLs:

```python
from src.downloader import HTTPDownloader, URLValidationError

downloader = HTTPDownloader()

try:
    # Validation happens automatically
    file_path = downloader.download("https://example.com/audio.mp3")
    
except URLValidationError as e:
    print(f"URL validation failed: {e}")
```

### Manual Validation Steps

```python
from src.downloader.validators import URLSchemeValidator

url = "HTTPS://EXAMPLE.COM:443/path/to/audio.mp3"

# Step 1: Normalize URL
normalized = URLSchemeValidator.normalize_url(url)
print(normalized)  # https://example.com/path/to/audio.mp3

# Step 2: Validate scheme
URLSchemeValidator.validate_scheme(normalized)

# Step 3: Validate hostname
URLSchemeValidator.validate_hostname(normalized)

# Or do all at once
validated = URLSchemeValidator.validate(url)
```

## Testing

### Run URL Validation Tests

```bash
# All URL validation tests
pytest tests/test_url_validators.py -v

# Specific test classes
pytest tests/test_url_validators.py::TestURLSchemeValidation -v
pytest tests/test_url_validators.py::TestHostnameValidation -v
pytest tests/test_url_validators.py::TestURLNormalization -v
```

### Test Coverage

The test suite includes:
- ✅ Allowed scheme validation (HTTP, HTTPS)
- ✅ Blocked scheme detection (14+ dangerous schemes)
- ✅ Hostname validation (format, characters, localhost)
- ✅ URL normalization (case, ports, whitespace)
- ✅ Complete validation flow
- ✅ Error message verification
- ✅ Integration with HTTPDownloader
- ✅ Edge cases (credentials, fragments, IPv6)

**Total: 40+ comprehensive tests**

## Security Considerations

### Attack Scenarios Prevented

#### 1. Local File Access

**Attack:**
```python
# Attacker tries to read /etc/passwd
download_from_url("file:///etc/passwd")
```

**Protection:**
```
❌ Blocked by scheme validator
→ URLValidationError: "Blocked URL scheme 'file'"
```

#### 2. FTP Protocol Bypass

**Attack:**
```python
# Attacker tries to use FTP
download_from_url("ftp://internal-server.local/secret.mp3")
```

**Protection:**
```
❌ Blocked by scheme validator
→ URLValidationError: "Blocked URL scheme 'ftp'"
```

#### 3. JavaScript Code Injection

**Attack:**
```python
# Attacker tries to inject JavaScript
download_from_url("javascript:alert('xss')")
```

**Protection:**
```
❌ Blocked by scheme validator
→ URLValidationError: "Blocked URL scheme 'javascript'"
```

#### 4. Data URL Resource Exhaustion

**Attack:**
```python
# Attacker provides huge base64 data URL
download_from_url("data:audio/mp3;base64," + "A" * 1000000)
```

**Protection:**
```
❌ Blocked by scheme validator
→ URLValidationError: "Blocked URL scheme 'data'"
```

### Best Practices

#### ✅ DO:

1. **Always Validate Before Download**:
   ```python
   validated_url = validate_url(user_input)
   download_from_url(validated_url)
   ```

2. **Log Validation Failures**:
   ```python
   try:
       validate_url(url)
   except URLValidationError as e:
       logger.warning(f"Invalid URL blocked: {url} - {e}")
   ```

3. **Use Normalized URLs**:
   ```python
   url = validate_url(url, normalize=True)
   # Now safe to use and compare
   ```

4. **Validate User Input**:
   ```python
   @server.tool()
   async def download_audio(url: str):
       # Validate before processing
       validated_url = validate_url(url)
       return download_from_url(validated_url)
   ```

#### ❌ DON'T:

1. **Don't Skip Validation**:
   ```python
   # BAD: Trusting user input
   download_from_url(user_input)
   
   # GOOD: Always validate
   validated = validate_url(user_input)
   download_from_url(validated)
   ```

2. **Don't Add Dangerous Schemes**:
   ```python
   # BAD: Adding FTP support
   ALLOWED_SCHEMES.add("ftp")  # NO!
   
   # GOOD: Only HTTP/HTTPS
   # Keep ALLOWED_SCHEMES unchanged
   ```

3. **Don't Bypass Validation**:
   ```python
   # BAD: Direct download without validation
   requests.get(user_url)
   
   # GOOD: Use HTTPDownloader (validates automatically)
   downloader.download(user_url)
   ```

## Examples

### Valid URLs

These URLs pass validation:

```python
valid_urls = [
    "https://example.com/audio.mp3",
    "http://cdn.example.com/track.mp3",
    "https://api.example.com:8080/audio",
    "http://192.168.1.1/local.mp3",  # Localhost (logged)
    "https://user:pass@example.com/auth.mp3",
    "https://example.com/audio.mp3?token=abc",
]

for url in valid_urls:
    validated = validate_url(url)
    print(f"✓ {validated}")
```

### Invalid URLs

These URLs fail validation:

```python
invalid_urls = [
    "file:///etc/passwd",                    # Local file
    "ftp://example.com/file.mp3",           # FTP protocol
    "javascript:alert('xss')",              # Code execution
    "data:text/plain,hello",                # Data URL
    "ws://example.com/socket",              # WebSocket
    "example.com/audio.mp3",                # Missing scheme
    "https://",                             # Missing hostname
    "https://invalid_host/file.mp3",        # Invalid hostname
]

for url in invalid_urls:
    try:
        validate_url(url)
        print(f"✗ Should have failed: {url}")
    except URLValidationError as e:
        print(f"✓ Blocked: {url} - {e}")
```

## Integration with Downloader

The URL validator is automatically integrated:

```python
from src.downloader import download_from_url

# Automatic validation and normalization
file_path = download_from_url("HTTPS://EXAMPLE.COM/audio.mp3")

# URL is validated and normalized before download:
# HTTPS://EXAMPLE.COM/audio.mp3 → https://example.com/audio.mp3
```

## Next Steps

After completing URL scheme validation:

1. ✅ **Subtask 3.3** - Apply SSRF Protection (ready!)
2. **Subtask 3.4** - Handle File Size Validation (mostly complete)
3. **Subtask 3.5** - Manage Timeout and Retry Logic (mostly complete)
4. **Subtask 3.6** - Temporary File Management (mostly complete)
5. **Subtask 3.7** - Implement Progress Tracking (mostly complete)

## References

- [URL Specification (RFC 3986)](https://www.rfc-editor.org/rfc/rfc3986)
- [OWASP URL Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html#url-validation)
- [Protocol Handlers Security](https://developer.mozilla.org/en-US/docs/Web/Security)

---

**Subtask 3.2 Status**: Complete ✅  
**Date**: 2025-10-09  
**Allowed Schemes**: HTTP, HTTPS  
**Blocked Schemes**: 14+ dangerous protocols

