# GCS + Embed Player Setup Guide

Complete guide for setting up Google Cloud Storage and testing the embed player functionality for local Docker development.

## 🚀 Quick Start

### 1. Run GCS Setup Script
```bash
# Make script executable and run
chmod +x scripts/setup-gcs-local.sh
./scripts/setup-gcs-local.sh
```

**Note**: Update the `PROJECT_ID` in the script to match your Google Cloud project.

### 2. Start Services
```bash
# Start database and MCP server
docker-compose up -d postgres
docker-compose up mcp-server
```

### 3. Run Complete Test Suite
```bash
# Test the full pipeline with the provided audio file
python3 test_gcs_embed_complete.py
```

## 📋 What This Tests

The test suite validates:

1. **GCS Connection** - Verifies bucket access and permissions
2. **Audio Processing** - Downloads, processes, and uploads audio to GCS
3. **Database Integration** - Saves metadata to PostgreSQL
4. **GCS Signed URLs** - Generates secure streaming URLs
5. **Embed Player** - Tests HTML5 audio player with custom UI
6. **oEmbed Functionality** - Tests platform embedding support

## 🎵 Test Audio

The test uses this temporary audio file:
```
http://tmpfiles.org/dl/4845257/dcd082_07herotolerance.mp3
```

**Note**: This is a temporary link that will expire. Replace with your own audio file for testing.

## 🔧 Configuration Files

### Environment Variables
The setup creates `.env.gcs` with:
```bash
GCS_BUCKET_NAME=loist-mvp-audio-files
GCS_PROJECT_ID=loist-mvp-dev
GCS_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

### Docker Configuration
Updated `docker-compose.yml` with:
- GCS environment variables
- Service account key mounting
- CORS configuration for embed testing

## 🌐 Testing URLs

After successful setup, you can test:

### Embed Player
```
http://localhost:8080/embed/{audio_id}
```

### oEmbed Discovery
```
http://localhost:8080/.well-known/oembed.json
```

### oEmbed Endpoint
```
http://localhost:8080/oembed?url=https://loist.io/embed/{audio_id}
```

### Health Checks
```
http://localhost:8080/health
http://localhost:8080/ready
```

## 🎯 Expected Results

### Successful Test Output
```
🧪 GCS + Embed Player Complete Test Suite
============================================================
🎵 Test Audio: http://tmpfiles.org/dl/4845257/dcd082_07herotolerance.mp3

📋 Step 1: Testing GCS Connection
----------------------------------------
✅ GCS client created for bucket: loist-mvp-audio-files
✅ Bucket loist-mvp-audio-files exists and is accessible
📁 Found 0 existing audio files in bucket

📋 Step 2: Testing Audio Processing Pipeline
----------------------------------------
🎵 Processing audio from: http://tmpfiles.org/dl/4845257/dcd082_07herotolerance.mp3
✅ Audio processing successful!
   📝 Audio ID: 550e8400-e29b-41d4-a716-446655440000
   🎵 Title: Hero Tolerance
   🎤 Artist: DCD082
   ⏱️  Duration: 180.5s

📋 Step 3: Testing Database Integration
----------------------------------------
✅ Audio metadata found in database
   🎵 Title: Hero Tolerance
   🎤 Artist: DCD082
   💿 Album: Unknown
   📅 Year: Unknown
   ⏱️  Duration: 180.5s
   🎧 Format: MP3
   📁 Audio Path: audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3
   🖼️  Thumbnail Path: None

📋 Step 4: Testing GCS Signed URLs
----------------------------------------
✅ Generated signed URL for audio stream
   🔗 URL: https://storage.googleapis.com/loist-mvp-audio-files/audio/550e8400-e29b-41d4-a716-446655440000/audio.mp3?X-Goog-Algorithm=...
   ✅ Audio stream URL is accessible
   📊 Content-Type: audio/mpeg
   📏 Content-Length: 2897152 bytes

📋 Step 5: Testing Embed Player
----------------------------------------
🌐 Testing embed page: http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000
✅ Embed page loads successfully
   ✅ HTML5 audio element
   ✅ Player controls
   ✅ Progress bar
   ✅ Volume control
   ✅ Social sharing
   ✅ Open Graph tags
   ✅ Twitter Card
   ✅ oEmbed discovery

📋 Step 6: Testing oEmbed Functionality
----------------------------------------
🔍 Testing oEmbed discovery: http://localhost:8080/.well-known/oembed.json
✅ oEmbed discovery endpoint working
   📝 Provider: Loist Music Library
🔗 Testing oEmbed endpoint: http://localhost:8080/oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000
✅ oEmbed endpoint working
   📝 Title: Hero Tolerance
   🎤 Author: DCD082
   📐 Dimensions: 500x200
   🖼️  Thumbnail: No

🧪 Test Results Summary
============================================================
📊 Tests Passed: 6/6
🎵 Audio ID: 550e8400-e29b-41d4-a716-446655440000
🌐 Embed URL: http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000
🔗 oEmbed URL: http://localhost:8080/oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000

📋 Detailed Results:
   gcs_connection: ✅ PASS
   audio_processing: ✅ PASS
   database_integration: ✅ PASS
   gcs_signed_urls: ✅ PASS
   embed_player: ✅ PASS
   oembed: ✅ PASS

🎉 All tests passed! Your GCS + Embed Player setup is working perfectly!

🚀 Next steps:
   1. Open embed player: http://localhost:8080/embed/550e8400-e29b-41d4-a716-446655440000
   2. Test oEmbed: http://localhost:8080/oembed?url=https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000
   3. Share on social media to test Open Graph/Twitter Cards
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. GCS Authentication Failed
```bash
# Check if service account key exists
ls -la service-account-key.json

# Verify gcloud authentication
gcloud auth list
gcloud config get-value project
```

#### 2. Database Connection Failed
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres
```

#### 3. Embed Player Not Loading
```bash
# Check if MCP server is running
docker-compose ps mcp-server

# Check server logs
docker-compose logs mcp-server

# Test health endpoint
curl http://localhost:8080/health
```

#### 4. CORS Issues
```bash
# Check CORS configuration in docker-compose.yml
# Ensure ENABLE_CORS=true and CORS_ORIGINS includes your domain
```

### Debug Commands

```bash
# Test GCS connection directly
python3 -c "
import sys; sys.path.insert(0, 'src')
from src.storage.gcs_client import create_gcs_client
client = create_gcs_client()
print('Bucket exists:', client.bucket.exists())
"

# Test database connection
python3 -c "
import sys; sys.path.insert(0, 'src')
from database.pool import get_connection_pool
pool = get_connection_pool()
print('Database healthy:', pool.health_check()['healthy'])
"

# Test audio processing
python3 -c "
import sys; sys.path.insert(0, 'src')
from src.tools.process_audio import process_audio_complete_sync
result = process_audio_complete_sync({
    'source': {'type': 'http_url', 'url': 'http://tmpfiles.org/dl/4845257/dcd082_07herotolerance.mp3'},
    'options': {'maxSizeMB': 100}
})
print('Success:', result.get('success'))
print('Audio ID:', result.get('track_id'))
"
```

## 🔒 Security Notes

1. **Service Account Key**: Never commit `service-account-key.json` to version control
2. **Bucket Permissions**: The setup grants public read access for streaming
3. **Signed URLs**: Audio files are served via time-limited signed URLs
4. **CORS**: Configured for local development only

## 📚 Next Steps

1. **Production Deployment**: Update bucket permissions and CORS for production
2. **Custom Audio**: Replace test audio with your own files
3. **Social Sharing**: Test Open Graph and Twitter Card functionality
4. **Performance**: Monitor GCS costs and optimize lifecycle policies
5. **Security**: Implement proper authentication for production use

## 🎉 Success!

Once all tests pass, you have a fully functional:
- ✅ Google Cloud Storage integration
- ✅ Audio processing pipeline
- ✅ HTML5 embed player
- ✅ oEmbed support
- ✅ Social media sharing
- ✅ Local Docker development environment

Your embed player is ready for integration into any website or application!
