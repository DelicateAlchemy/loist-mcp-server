# Quick Guide: Testing oEmbed Endpoint Locally

## Prerequisites

1. Docker and Docker Compose installed
2. `service-account-key.json` present in project root (for GCS signed URLs)
3. Optionally: GCS bucket name set in environment (defaults to `loist-mvp-audio-files`)

## Quick Start

### 1. Start Docker Services

```bash
# Start PostgreSQL and MCP server
docker-compose up -d

# Watch logs (optional)
docker-compose logs -f mcp-server
```

The server will be available at `http://localhost:8080`

### 2. Verify Server is Running

```bash
# Health check
curl http://localhost:8080/mcp/health_check

# Expected: JSON with status "healthy"
```

### 3. Test oEmbed Endpoint

**Note**: You need a valid audio ID from your database. If you don't have one yet, process an audio file first or use an existing ID.

```bash
# Basic oEmbed request
curl "http://localhost:8080/oembed?url=https://loist.io/embed/YOUR_AUDIO_ID"

# With custom dimensions
curl "http://localhost:8080/oembed?url=https://loist.io/embed/YOUR_AUDIO_ID&maxwidth=800&maxheight=300"

# Pretty print JSON response
curl -s "http://localhost:8080/oembed?url=https://loist.io/embed/YOUR_AUDIO_ID" | jq .
```

### 4. Test Error Cases

```bash
# Missing url parameter (should return 400)
curl http://localhost:8080/oembed

# Invalid URL format (should return 400)
curl "http://localhost:8080/oembed?url=https://example.com/invalid"

# Non-existent audio ID (should return 404)
curl "http://localhost:8080/oembed?url=https://loist.io/embed/00000000-0000-0000-0000-000000000000"
```

### 5. Test Embed Page (Bonus)

```bash
# Visit in browser or curl
curl http://localhost:8080/embed/YOUR_AUDIO_ID

# Or open in browser:
# http://localhost:8080/embed/YOUR_AUDIO_ID
```

## Expected oEmbed Response

```json
{
  "version": "1.0",
  "type": "rich",
  "provider_name": "Loist Music Library",
  "provider_url": "https://loist.io",
  "title": "Track Title",
  "author_name": "Artist Name",
  "html": "<iframe src='https://loist.io/embed/YOUR_AUDIO_ID' width='500' height='200' frameborder='0' allow='autoplay' style='border-radius: 12px;'></iframe>",
  "width": 500,
  "height": 200,
  "thumbnail_url": "https://storage.googleapis.com/...",
  "thumbnail_width": 500,
  "thumbnail_height": 500,
  "cache_age": 3600
}
```

## Troubleshooting

### Server won't start
```bash
# Check logs
docker-compose logs mcp-server

# Rebuild if needed
docker-compose up --build -d
```

### Template not found errors
- Verify `templates/` directory exists and is mounted
- Check: `docker-compose exec mcp-server ls -la /app/templates/`

### GCS credential errors
- Verify `service-account-key.json` exists
- Check: `ls -la service-account-key.json`
- Verify GCS_BUCKET_NAME is set if using custom bucket

### Database connection errors
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres
```

## Next Steps

1. Test with a real audio ID (process audio first if needed)
2. Verify embed page works in browser
3. Test with Notion or other oEmbed consumers
4. Check mobile responsiveness

## Stopping Services

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

