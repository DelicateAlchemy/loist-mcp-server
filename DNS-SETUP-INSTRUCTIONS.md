# DNS Setup Instructions for api.loist.io

## Overview
You need to add DNS records to verify domain ownership and map the subdomain to Cloud Run.

## Step 1: Domain Verification (Required First)

### Option A: Google Cloud Console Domain Verification (Recommended)
1. Go to: https://console.cloud.google.com/security/domain-verification
2. Click "Add Domain" and enter: `loist.io`
3. Choose "DNS TXT record" verification method
4. Google will provide a TXT record like:
   ```
   google-site-verification=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
   ```

### DNS Record to Add for Verification:
```
Type: TXT
Name: @ (or loist.io)
Value: [The verification string Google provides]
TTL: 3600 (or default)
```

## Step 2: Domain Mapping (After Verification)

### For Cloud Run Domain Mapping (Preview Feature):
```
Type: CNAME
Name: api
Value: ghs.googlehosted.com
TTL: 3600 (or default)
```

### Alternative: For Application Load Balancer (Production Recommended):
```
Type: A
Name: api
Value: [IPv4 addresses from Cloud Run domain mapping]
TTL: 3600 (or default)

Type: AAAA
Name: api  
Value: [IPv6 addresses from Cloud Run domain mapping]
TTL: 3600 (or default)
```

## Step 3: Additional Records (Optional but Recommended)

### Redirect www to main domain:
```
Type: CNAME
Name: www
Value: loist.io
TTL: 3600 (or default)
```

### Redirect api.www to api:
```
Type: CNAME
Name: www.api (or api.www depending on your DNS provider)
Value: api.loist.io
TTL: 3600 (or default)
```

## DNS Provider Specific Instructions

### If using Cloudflare:
1. Go to DNS tab in Cloudflare dashboard
2. Click "Add record"
3. Set Type, Name, and Content as specified above
4. Set TTL to "Auto" or 3600
5. Click "Save"

### If using Google Domains:
1. Go to DNS section
2. Click "Manage custom records"
3. Add the records as specified above

### If using Route 53 (AWS):
1. Go to Route 53 console
2. Select your hosted zone for loist.io
3. Click "Create record"
4. Set the record values as specified above

## Verification Steps

### 1. Check Domain Verification:
```bash
# Test TXT record
dig TXT loist.io
# Should show the Google verification record
```

### 2. Check Subdomain Resolution:
```bash
# Test CNAME record
dig CNAME api.loist.io
# Should show ghs.googlehosted.com
```

### 3. Test HTTPS Access:
```bash
# Test HTTPS (after Cloud Run deployment)
curl -I https://api.loist.io/health
# Should return 200 OK with valid SSL certificate
```

## Important Notes

1. **DNS Propagation**: Changes can take up to 24 hours to propagate globally
2. **Verification First**: Domain verification must be completed before mapping
3. **SSL Certificate**: Google-managed certificates are automatically provisioned after domain mapping
4. **TTL Values**: Lower TTL (300-600) for faster testing, higher TTL (3600+) for production

## Troubleshooting

### If domain verification fails:
- Double-check the TXT record value (no extra spaces)
- Wait up to 24 hours for DNS propagation
- Try alternative verification methods (HTML file, Google Analytics)

### If subdomain mapping fails:
- Ensure domain verification is complete
- Check CNAME record points to correct value
- Verify Cloud Run service is deployed and accessible

### If HTTPS doesn't work:
- Wait up to 24 hours for SSL certificate provisioning
- Check that HTTP redirects to HTTPS
- Verify certificate is valid in browser

## Next Steps After DNS Setup

1. ✅ Complete domain verification
2. ✅ Add CNAME record for api.loist.io
3. 🚀 Deploy Cloud Run service
4. 🌐 Map domain to Cloud Run service
5. 🔒 Wait for SSL certificate provisioning
6. ✅ Test HTTPS access
7. 🧪 Test Open Graph tags with real domain



