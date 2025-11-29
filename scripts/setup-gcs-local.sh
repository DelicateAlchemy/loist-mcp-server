#!/bin/bash
# Google Cloud Storage Setup for Local Development
# This script sets up GCS for local Docker testing

set -e

# Configuration
PROJECT_ID="loist-music-library"  # Change this to your project ID
BUCKET_NAME="loist-mvp-audio-files"
SERVICE_ACCOUNT_NAME="loist-dev-sa"
REGION="us-central1"

echo "🚀 Setting up Google Cloud Storage for local development..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
echo "📋 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable storage.googleapis.com
gcloud services enable storage-api.googleapis.com

# Create service account for local development
echo "👤 Creating service account for local development..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
    --display-name="Loist Development Service Account" \
    --description="Service account for local development testing" \
    --quiet || echo "Service account may already exist"

# Grant minimal required permissions
echo "🔐 Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin" \
    --quiet

# Create and download service account key
echo "🔑 Creating service account key..."
gcloud iam service-accounts keys create ./service-account-key.json \
    --iam-account=$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com \
    --quiet

# Create bucket with appropriate settings
echo "🪣 Creating GCS bucket..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME || echo "Bucket may already exist"

# Set bucket permissions for public read access (for streaming)
echo "🌐 Setting bucket permissions..."
gsutil iam ch allUsers:objectViewer gs://$BUCKET_NAME

# Configure lifecycle policy for cost optimization
echo "💰 Setting up lifecycle policy..."
cat > lifecycle.json << EOF
{
  "rule": [
    {
      "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
      "condition": {"age": 30}
    },
    {
      "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
      "condition": {"age": 90}
    }
  ]
}
EOF

gsutil lifecycle set lifecycle.json gs://$BUCKET_NAME
rm lifecycle.json

# Create environment file
echo "📝 Creating environment configuration..."
cat > .env.gcs << EOF
# Google Cloud Storage Configuration
GCS_BUCKET_NAME=$BUCKET_NAME
GCS_PROJECT_ID=$PROJECT_ID
GCS_REGION=$REGION
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json

# Database Configuration (for local testing)
DATABASE_URL=postgresql://loist_user:dev_password@localhost:5432/loist_mvp

# Server Configuration
SERVER_TRANSPORT=http
SERVER_PORT=8080
AUTH_ENABLED=false
ENABLE_CORS=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:5173
EOF

echo "✅ GCS setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update your docker-compose.yml with GCS configuration"
echo "2. Start your services: docker-compose up"
echo "3. Test audio processing with: python3 test_audio_processing.py"
echo ""
echo "🔧 Configuration files created:"
echo "   - service-account-key.json (GCS credentials)"
echo "   - .env.gcs (environment variables)"
echo ""
echo "⚠️  Remember to add service-account-key.json to .gitignore!"
