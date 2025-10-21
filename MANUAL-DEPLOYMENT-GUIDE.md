# Manual Cloud Run Deployment Guide

Since the service account doesn't have deployment permissions, you'll need to deploy manually using user authentication.

## Option 1: Manual gcloud Commands (Recommended)

### Step 1: Authenticate with Your User Account
```bash
gcloud auth login
```

### Step 2: Enable Required APIs
Go to Google Cloud Console and enable these APIs:
- https://console.cloud.google.com/apis/library/run.googleapis.com
- https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com
- https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com

Or run these commands (if you have permission):
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### Step 3: Deploy to Cloud Run
```bash
# Set your project
gcloud config set project loist-music-library

# Deploy from source (simplest method)
gcloud run deploy loist-mcp-server \
    --source="." \
    --region="us-central1" \
    --platform="managed" \
    --allow-unauthenticated \
    --memory="2Gi" \
    --timeout="600s" \
    --set-env-vars="SERVER_TRANSPORT=http,ENABLE_CORS=true,CORS_ORIGINS=https://loist.io"
```

### Step 4: Get Service URL
```bash
gcloud run services describe loist-mcp-server \
    --region="us-central1" \
    --format="value(status.url)"
```

## Option 2: Google Cloud Console Deployment

### Step 1: Enable APIs
1. Go to: https://console.cloud.google.com/apis/library
2. Enable these APIs:
   - Cloud Run API
   - Cloud Build API
   - Artifact Registry API

### Step 2: Deploy via Console
1. Go to: https://console.cloud.google.com/run
2. Click "Create Service"
3. Choose "Deploy one revision from a source repository"
4. Select "Cloud Source Repositories" or "GitHub"
5. Connect your repository
6. Configure service:
   - Service name: `loist-mcp-server`
   - Region: `us-central1`
   - Memory: `2 GiB`
   - Timeout: `600 seconds`
   - Allow unauthenticated invocations: ✅ Yes

### Step 3: Environment Variables
Add these environment variables:
- `SERVER_TRANSPORT=http`
- `ENABLE_CORS=true`
- `CORS_ORIGINS=https://loist.io`

## After Deployment

Once deployed, you'll get a service URL like:
`https://loist-mcp-server-xxxxx-uc.a.run.app`

### Test the Service
```bash
curl https://loist-mcp-server-xxxxx-uc.a.run.app/health
```

### Domain Mapping Process
1. Go to your Cloud Run service in the console
2. Click "Manage Custom Domains"
3. Add domain: `api.loist.io`
4. Follow the DNS setup instructions

## DNS Record to Add (After Domain Mapping)
```
Type: CNAME
Name: api
Value: ghs.googlehosted.com
TTL: 3600
```

## Troubleshooting

### If APIs are not enabled:
- Go to Google Cloud Console → APIs & Services → Library
- Enable the required APIs manually

### If deployment fails:
- Check that you have the "Cloud Run Admin" role
- Verify your project has billing enabled
- Make sure the source code is accessible

### If domain mapping fails:
- Ensure the Cloud Run service is deployed and accessible
- Check that the domain is verified in Google Search Console
- Wait for DNS propagation (up to 24 hours)



