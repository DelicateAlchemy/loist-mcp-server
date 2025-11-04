# Custom Domain Mapping with HTTPS for Cloud Run Services

## Overview

This guide provides a comprehensive implementation for setting up custom domain mapping with automatic HTTPS certificate provisioning for Google Cloud Run services using the recommended Global External Application Load Balancer approach.

## Current Status and Issues

### Service Readiness Issues
- **Production Service**: `music-library-mcp` failing to start (404 responses)
- **Staging Service**: `music-library-mcp-staging` also failing (404 responses)
- **Root Causes**:
  - Production service using incorrect image: `gcr.io/loist-music-library/mcp-music-library:latest` (doesn't exist)
  - Production service using default compute service account instead of `mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com`
  - MCP server application not starting properly on PORT=8080

### Domain Configuration Issues
- **mcp.loist.io**: Currently resolves to `ghs.googlehosted.com` (Google Sites) instead of Cloud Run
- **Domain Mapping**: Using preview Cloud Run domain mapping (not recommended for production)
- **Status**: Domain mapping shows "RouteNotReady" due to service issues

## Recommended Architecture: Global External Application Load Balancer

Based on Google Cloud documentation (November 2025), the **Global External Application Load Balancer** is the recommended approach for production custom domain mapping with Cloud Run services.

### Architecture Benefits
- ✅ **Production Ready**: General availability, no preview limitations
- ✅ **Superior Performance**: No latency issues reported with preview domain mapping
- ✅ **Advanced Features**: Cloud CDN, Cloud Armor, custom SSL policies
- ✅ **Scalability**: Global distribution, automatic failover
- ✅ **Security**: Advanced DDoS protection, custom SSL configurations

### Architecture Components
```
Internet → Global External ALB → Serverless NEG → Cloud Run Service
                              ↓
                       Google-Managed SSL Certificates
                              ↓
                       Custom Domain (mcp.loist.io)
```

## Implementation Prerequisites

### 1. Service Readiness (MUST BE COMPLETED FIRST)
Before implementing domain mapping, ensure the Cloud Run service is healthy:

```bash
# Check service status
gcloud run services describe music-library-mcp --region=us-central1

# Test service accessibility
curl -X POST https://music-library-mcp-872391508675.us-central1.run.app/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'
```

**Expected Response**: Valid MCP protocol response (not 404)

### 2. Domain Ownership Verification
Verify domain ownership in Google Cloud Console:

```bash
# Verify domain ownership
gcloud domains verify loist.io

# Check verification status
gcloud domains list --filter="domain=loist.io"
```

### 3. Required IAM Permissions
Ensure the service account has necessary permissions:

```bash
# Check service account permissions
gcloud projects add-iam-policy-binding loist-music-library \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Verify secret access
gcloud secrets add-iam-policy-binding mcp-bearer-token \
  --member="serviceAccount:mcp-music-library-sa@loist-music-library.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Step-by-Step Implementation Guide

### Step 1: Create Serverless Network Endpoint Group (NEG)

```bash
# Create serverless NEG for the Cloud Run service
gcloud compute network-endpoint-groups create music-library-mcp-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=music-library-mcp
```

### Step 2: Create Backend Service

```bash
# Create backend service
gcloud compute backend-services create music-library-mcp-backend \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --global

# Add NEG to backend service
gcloud compute backend-services add-backend music-library-mcp-backend \
  --network-endpoint-group=music-library-mcp-neg \
  --network-endpoint-group-region=us-central1 \
  --global
```

### Step 3: Create SSL Certificate

```bash
# Create Google-managed SSL certificate
gcloud compute ssl-certificates create music-library-mcp-cert \
  --domains=mcp.loist.io \
  --global
```

### Step 4: Create HTTPS Target Proxy

```bash
# Create target HTTPS proxy
gcloud compute target-https-proxies create music-library-mcp-proxy \
  --ssl-certificates=music-library-mcp-cert \
  --url-map=music-library-mcp-url-map
```

### Step 5: Create URL Map

```bash
# Create URL map
gcloud compute url-maps create music-library-mcp-url-map \
  --default-service=music-library-mcp-backend
```

### Step 6: Create Global Address

```bash
# Reserve global IP address
gcloud compute addresses create music-library-mcp-ip \
  --network-tier=PREMIUM \
  --ip-version=IPV4 \
  --global

# Get the allocated IP address
gcloud compute addresses describe music-library-mcp-ip \
  --format="get(address)" \
  --global
```

### Step 7: Create Forwarding Rule

```bash
# Create forwarding rule
gcloud compute forwarding-rules create music-library-mcp-forwarding-rule \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --network-tier=PREMIUM \
  --address=music-library-mcp-ip \
  --target-https-proxy=music-library-mcp-proxy \
  --ports=443 \
  --global
```

### Step 8: Configure HTTP to HTTPS Redirect (Optional)

```bash
# Create HTTP target proxy for redirects
gcloud compute target-http-proxies create music-library-mcp-http-proxy \
  --url-map=music-library-mcp-url-map

# Create HTTP forwarding rule
gcloud compute forwarding-rules create music-library-mcp-http-forwarding-rule \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --network-tier=PREMIUM \
  --address=music-library-mcp-ip \
  --target-http-proxy=music-library-mcp-http-proxy \
  --ports=80 \
  --global
```

### Step 9: Update DNS Records

```bash
# Get the load balancer IP address
LB_IP=$(gcloud compute addresses describe music-library-mcp-ip \
  --format="get(address)" \
  --global)

# Update DNS A record for mcp.loist.io to point to load balancer IP
# In your domain registrar (GoDaddy, Namecheap, etc.):
# Type: A
# Name: mcp
# Value: $LB_IP
# TTL: 300 (5 minutes)
```

## Verification and Testing

### 1. DNS Propagation Check

```bash
# Verify DNS resolution
dig mcp.loist.io

# Expected: A record pointing to load balancer IP
# Expected output should show:
# mcp.loist.io.    300 IN A <load-balancer-ip>
```

### 2. Certificate Provisioning Status

```bash
# Check SSL certificate status
gcloud compute ssl-certificates describe music-library-mcp-cert \
  --global \
  --format="value(managed.status)"

# Expected: ACTIVE (after 15 minutes to 24 hours)
```

### 3. HTTPS Connectivity Test

```bash
# Test HTTPS connection
curl -I https://mcp.loist.io

# Expected: HTTP/2 200 or valid response
# Should NOT redirect or show certificate errors
```

### 4. HTTP to HTTPS Redirect Test

```bash
# Test HTTP redirect (if configured)
curl -I http://mcp.loist.io

# Expected: HTTP 301 redirect to https://mcp.loist.io
```

### 5. MCP Protocol Test

```bash
# Test MCP protocol over custom domain
curl -X POST https://mcp.loist.io/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'

# Expected: Valid MCP protocol response
```

## Troubleshooting

### Certificate Provisioning Issues

```bash
# Check certificate status
gcloud compute ssl-certificates describe music-library-mcp-cert \
  --global \
  --format="value(managed.status, managed.domainStatus)"

# If FAILED_NOT_VISIBLE:
# 1. Verify DNS points to load balancer IP
# 2. Wait for DNS propagation (up to 72 hours)
# 3. Check domain ownership verification
```

### DNS Resolution Issues

```bash
# Verify DNS configuration
dig mcp.loist.io

# Check load balancer IP
gcloud compute addresses describe music-library-mcp-ip \
  --format="get(address)" \
  --global
```

### Service Accessibility Issues

```bash
# Check backend service health
gcloud compute backend-services get-health music-library-mcp-backend \
  --global

# Verify NEG configuration
gcloud compute network-endpoint-groups describe music-library-mcp-neg \
  --region=us-central1
```

## Cost Considerations

### Load Balancer Costs
- **Forwarding Rules**: $0.025/hour (~$18/month)
- **Data Processing**: $0.12/GB internet egress
- **SSL Certificates**: Free (Google-managed)
- **IP Address**: $0.018/hour (~$13/month) for global premium

### Estimated Monthly Cost
- Base infrastructure: ~$31/month
- Data transfer: Variable based on traffic
- No additional SSL certificate costs

## Migration from Preview Domain Mapping

### Current State
- `mcp.loist.io` → Cloud Run domain mapping (FAILING)
- DNS: `mcp.loist.io CNAME ghs.googlehosted.com`

### Migration Steps
1. **Complete load balancer setup** (Steps 1-8 above)
2. **Update DNS records** to point to load balancer IP
3. **Wait for DNS propagation** (5-30 minutes)
4. **Verify certificate provisioning** (15 minutes - 24 hours)
5. **Test functionality** over custom domain
6. **Remove old domain mapping** (optional)

```bash
# Remove old Cloud Run domain mapping (after migration)
gcloud beta run domain-mappings delete --domain=mcp.loist.io --region=us-central1
```

## Automation Script

Create `scripts/setup-custom-domain.sh`:

```bash
#!/bin/bash

# Configuration
PROJECT_ID="loist-music-library"
SERVICE_NAME="music-library-mcp"
DOMAIN="mcp.loist.io"
REGION="us-central1"

# Create NEG
gcloud compute network-endpoint-groups create ${SERVICE_NAME}-neg \
  --region=${REGION} \
  --network-endpoint-type=serverless \
  --cloud-run-service=${SERVICE_NAME}

# Create backend service
gcloud compute backend-services create ${SERVICE_NAME}-backend \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --global

# Add backend
gcloud compute backend-services add-backend ${SERVICE_NAME}-backend \
  --network-endpoint-group=${SERVICE_NAME}-neg \
  --network-endpoint-group-region=${REGION} \
  --global

# Create SSL certificate
gcloud compute ssl-certificates create ${SERVICE_NAME}-cert \
  --domains=${DOMAIN} \
  --global

# Create URL map
gcloud compute url-maps create ${SERVICE_NAME}-url-map \
  --default-service=${SERVICE_NAME}-backend

# Create HTTPS proxy
gcloud compute target-https-proxies create ${SERVICE_NAME}-proxy \
  --ssl-certificates=${SERVICE_NAME}-cert \
  --url-map=${SERVICE_NAME}-url-map

# Create global IP
gcloud compute addresses create ${SERVICE_NAME}-ip \
  --network-tier=PREMIUM \
  --ip-version=IPV4 \
  --global

# Get IP address
LB_IP=$(gcloud compute addresses describe ${SERVICE_NAME}-ip \
  --format="get(address)" \
  --global)

# Create forwarding rule
gcloud compute forwarding-rules create ${SERVICE_NAME}-forwarding-rule \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --network-tier=PREMIUM \
  --address=${SERVICE_NAME}-ip \
  --target-https-proxy=${SERVICE_NAME}-proxy \
  --ports=443 \
  --global

echo "Load balancer setup complete!"
echo "IP Address: ${LB_IP}"
echo "Update DNS A record for ${DOMAIN} to point to ${LB_IP}"
```

## Security Considerations

### SSL/TLS Configuration
- Google-managed certificates support TLS 1.2+ (TLS 1.0/1.1 disabled)
- Automatic certificate renewal (30 days before expiration)
- Domain validation through DNS CAA records (optional)

### Access Control
- Cloud Run IAM for service invocation
- Load balancer firewall rules (if needed)
- Cloud Armor for advanced protection (optional)

### Monitoring and Alerting
```bash
# Set up monitoring
gcloud monitoring alert-policies create \
  --display-name="SSL Certificate Expiry Alert" \
  --condition="certificate_expires_soon"

# Monitor request latency
gcloud monitoring alert-policies create \
  --display-name="High Latency Alert" \
  --condition="request_latency_threshold"
```

## Next Steps

1. **Fix service readiness issues** (highest priority)
2. **Implement load balancer setup** using this guide
3. **Update DNS records** to point to load balancer
4. **Verify HTTPS functionality** and certificate validity
5. **Test end-to-end functionality** with MCP protocol
6. **Monitor performance** and costs

## References

- [Google Cloud Load Balancing Documentation](https://docs.cloud.google.com/load-balancing/docs/https/setup-global-ext-https-serverless)
- [Google-Managed SSL Certificates](https://docs.cloud.google.com/load-balancing/docs/ssl-certificates/google-managed-certs)
- [Cloud Run Domain Mapping](https://docs.cloud.google.com/run/docs/mapping-custom-domains)
- [Custom Domain Verification](https://cloud.google.com/identity/docs/verify-domain)

---

**Last Updated**: November 4, 2025
**Status**: Ready for implementation pending service fix
