# A2A Integration Guide

This guide provides comprehensive instructions for integrating with the Loist Music Library A2A (Agent-to-Agent) service, which implements the A2A v0.3 specification for agent discovery and task coordination.

## Overview

The Loist Music Library A2A service enables other AI agents to discover and interact with audio processing capabilities programmatically. The service provides:

- **Agent Discovery**: A2A v0.3 compliant agent card at `/.well-known/agent-card.json`
- **JSON-RPC API**: Standard protocol for task submission and status polling
- **Audio Processing**: Full pipeline from URL ingestion to metadata extraction
- **Background Tasks**: Asynchronous processing with status tracking

## Agent Discovery

### Agent Card Endpoint

All A2A integration starts with discovering the agent's capabilities through the standard discovery endpoint:

```bash
curl https://a2a-staging-7de5nxpr4q-uc.a.run.app/.well-known/agent-card.json
```

**Response Format**:
```json
{
  "name": "Loist Music Library Processor",
  "description": "Audio processing and metadata extraction service",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "url": "https://a2a-staging-7de5nxpr4q-uc.a.run.app",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "defaultInputModes": ["application/json", "text/plain"],
  "defaultOutputModes": ["application/json"],
  "security": [{"BearerAuth": []}],
  "securitySchemes": {
    "BearerAuth": {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "JWT"
    }
  },
  "skills": [
    {
      "id": "process_audio_complete",
      "name": "Process audio (full)",
      "description": "Process audio file from URL and extract complete metadata including waveform, artwork, and tags",
      "tags": ["audio", "ingestion", "metadata", "waveform"]
    },
    {
      "id": "search_library",
      "name": "Search library",
      "description": "Search processed music library with text queries and metadata filters",
      "tags": ["search", "query", "metadata"]
    },
    {
      "id": "get_audio_metadata",
      "name": "Get metadata",
      "description": "Retrieve complete metadata for a processed audio track by ID",
      "tags": ["metadata", "retrieval"]
    },
    {
      "id": "update_metadata",
      "name": "Update metadata",
      "description": "Update metadata fields for an existing audio track",
      "tags": ["metadata", "update", "editing"]
    },
    {
      "id": "delete_audio",
      "name": "Delete audio",
      "description": "Remove an audio track from the library and delete associated files",
      "tags": ["deletion", "cleanup"]
    },
    {
      "id": "get_embed_url",
      "name": "Get embed URL",
      "description": "Generate embeddable player URLs for audio tracks with waveform visualization",
      "tags": ["embed", "player", "waveform"]
    }
  ]
}
```

## Environment Endpoints

### Staging Environment
- **URL**: `https://a2a-staging-7de5nxpr4q-uc.a.run.app`
- **Purpose**: Integration testing and QA
- **Features**: All capabilities available
- **Auto-deploy**: Triggered by pushes to `dev` branch
- **Status**: ✅ Deployed and operational

### Production Environment
- **URL**: `https://a2a-prod-{PROJECT_ID}.us-central1.run.app` (not yet deployed)
- **Purpose**: Live production usage
- **Features**: All capabilities available
- **Auto-deploy**: Triggered by pushes to `main` branch
- **Status**: ⚠️ Not yet deployed (trigger configured, awaiting first push to `main`)

## Authentication

**Current Status**: Authentication is **disabled** for MVP (`AUTH_ENABLED=false`)

When authentication is enabled in future releases:
```bash
curl -H "Authorization: Bearer your-token-here" \
  https://a2a-staging-7de5nxpr4q-uc.a.run.app/.well-known/agent-card.json
```

## JSON-RPC API

The service implements the JSON-RPC 2.0 specification for agent-to-agent communication.

### Common Headers

All requests should include:
```http
Content-Type: application/json
Accept: application/json
```

### Task Submission: `message/send`

Submit audio processing tasks using the `message/send` method (note: this is `message/send`, not `tasks/send`):

```bash
curl -X POST https://a2a-staging-7de5nxpr4q-uc.a.run.app/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-123",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {
            "type": "text",
            "text": "Process: https://example.com/track.mp3"
          }
        ]
      }
    }
  }'
```

**Success Response**:
```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "result": {
    "id": "task-uuid-here",
    "status": {
      "state": "submitted"
    },
    "createdAt": "2025-12-17T10:30:00Z",
    "contextId": "context-uuid"
  }
}
```

### Task Status Polling: `tasks/get`

Check task progress using the `tasks/get` method:

```bash
curl -X POST https://a2a-staging-7de5nxpr4q-uc.a.run.app/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-456",
    "method": "tasks/get",
    "params": {
      "id": "task-uuid-here"
    }
  }'
```

**Completed Task Response**:
```json
{
  "jsonrpc": "2.0",
  "id": "req-456",
  "result": {
    "id": "task-uuid-here",
    "status": {
      "state": "completed"
    },
    "createdAt": "2025-12-17T10:30:00Z",
    "updatedAt": "2025-12-17T10:32:15Z",
    "contextId": "context-uuid",
    "metadata": {
      "audio_track_id": "550e8400-e29b-41d4-a716-446655440000",
      "processing_result": {
        "success": true,
        "audio_id": "550e8400-e29b-41d4-a716-446655440000",
        "processing_time": 42.5,
        "metadata": {
          "title": "Sample Track",
          "artist": "Sample Artist",
          "duration": 180.5,
          "bitrate": 320,
          "format": "mp3"
        }
      }
    }
  }
}
```

### Task States

Tasks progress through these states:
- `submitted` → Initial state when task is created
- `working` → Audio processing in progress
- `completed` → Successfully finished (terminal state)
- `failed` → Error occurred (terminal state)
- `canceled` → User canceled (terminal state)
- `rejected` → Task rejected (terminal state)

## Error Handling

All errors follow JSON-RPC 2.0 error format:

```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "details": "No audio URL found in message"
    }
  }
}
```

### Common Error Codes

| Code | Meaning | Description |
|------|---------|-------------|
| -32600 | Invalid Request | Malformed JSON-RPC request |
| -32601 | Method not found | Unknown method called |
| -32602 | Invalid params | Invalid or missing parameters |
| -32603 | Internal error | Server-side error |
| -32001 | Task not found | Referenced task doesn't exist |
| -32002 | Task not cancelable | Task cannot be canceled in current state |

### Audio Processing Errors

Processing failures include detailed error information:

```json
{
  "jsonrpc": "2.0",
  "id": "req-456",
  "result": {
    "id": "task-uuid-here",
    "status": {
      "state": "failed",
      "message": "Audio processing failed"
    },
    "metadata": {
      "error": {
        "code": "FETCH_FAILED",
        "message": "Failed to download audio file",
        "details": {
          "url": "https://example.com/invalid.mp3",
          "http_status": 404,
          "retryable": true
        }
      }
    }
  }
}
```

## Integration Workflow

### Step 1: Discover Agent

```bash
# Get agent capabilities
AGENT_CARD=$(curl -s https://a2a-staging-7de5nxpr4q-uc.a.run.app/.well-known/agent-card.json)

# Verify required skills are available
echo $AGENT_CARD | jq '.skills[].id'
```

### Step 2: Submit Processing Task

```bash
# Submit audio URL for processing
RESPONSE=$(curl -s -X POST https://a2a-staging-7de5nxpr4q-uc.a.run.app/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "process-001",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {
            "type": "text",
            "text": "Process: https://example.com/audio.mp3"
          }
        ]
      }
    }
  }')

# Extract task ID
TASK_ID=$(echo $RESPONSE | jq -r '.result.id')
```

### Step 3: Poll for Completion

```bash
# Poll until completion (with exponential backoff)
while true; do
  STATUS=$(curl -s -X POST https://a2a-staging-7de5nxpr4q-uc.a.run.app/ \
    -H "Content-Type: application/json" \
    -d "{
      \"jsonrpc\": \"2.0\",
      \"id\": \"status-001\",
      \"method\": \"tasks/get\",
      \"params\": {\"id\": \"$TASK_ID\"}
    }")

  STATE=$(echo $STATUS | jq -r '.result.status.state')

  case $STATE in
    "completed")
      echo "✅ Processing completed"
      AUDIO_ID=$(echo $STATUS | jq -r '.result.metadata.audio_track_id')
      break
      ;;
    "failed")
      echo "❌ Processing failed"
      ERROR=$(echo $STATUS | jq -r '.result.metadata.error.message')
      echo "Error: $ERROR"
      break
      ;;
    "working"|"submitted")
      echo "⏳ Task $STATE, waiting..."
      sleep 5
      ;;
    *)
      echo "Unknown state: $STATE"
      break
      ;;
  esac
done
```

### Step 4: Retrieve Results

```bash
# Get complete metadata using MCP tools or A2A search
# (Implementation depends on your agent's preferred interface)
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to A2A endpoint
```bash
curl: (6) Could not resolve host
```

**Solutions**:
- Verify environment URL is correct
- Check if service is deployed (`gcloud run services list`)
- Confirm region (`us-central1`) is accessible

### Agent Card Not Found

**Problem**: 404 error on agent card endpoint
```json
{"error": "Not Found"}
```

**Solutions**:
- Verify endpoint path: `/.well-known/agent-card.json`
- Check service is running and healthy
- Confirm A2A server is deployed (not MCP server)

### Task Submission Errors

**Problem**: `message/send` returns invalid params error
```json
{
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {"details": "No audio URL found in message"}
  }
}
```

**Solutions**:
- Verify message format includes `role` and `parts`
- Ensure URL is in a text part
- Check URL format (must be http/https)

### Processing Failures

**Problem**: Task completes with `failed` status

**Common Causes**:
- Invalid or inaccessible audio URL
- Unsupported audio format
- Network timeout during download
- Storage quota exceeded

**Debugging**:
```bash
# Check detailed error in task metadata
curl -X POST https://a2a-staging-7de5nxpr4q-uc.a.run.app/ \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": \"debug\",
    \"method\": \"tasks/get\",
    \"params\": {\"id\": \"$TASK_ID\"}
  }" | jq '.result.metadata.error'
```

### Rate Limiting

**Problem**: Requests return HTTP 429

**Solutions**:
- Implement exponential backoff
- Reduce polling frequency (minimum 5 seconds)
- Check service quota limits

### Authentication Issues (Future)

When authentication is enabled:
```json
{
  "error": {
    "code": -32000,
    "message": "Authentication required"
  }
}
```

**Solutions**:
- Include `Authorization: Bearer <token>` header
- Verify token is valid and not expired
- Check token has required scopes

## Best Practices

### Error Handling

Always handle both JSON-RPC errors and HTTP errors:

```python
try:
    response = requests.post(endpoint, json=rpc_request)
    response.raise_for_status()  # Check HTTP status

    result = response.json()
    if 'error' in result:
        handle_jsonrpc_error(result['error'])
    else:
        process_result(result['result'])

except requests.RequestException as e:
    handle_connection_error(e)
```

### Polling Strategy

Implement exponential backoff for status polling:

```python
import time

def poll_task_status(task_id, max_attempts=30):
    base_delay = 2  # seconds
    max_delay = 60  # seconds

    for attempt in range(max_attempts):
        delay = min(base_delay * (2 ** attempt), max_delay)
        time.sleep(delay)

        status = get_task_status(task_id)
        if status['state'] in ['completed', 'failed', 'canceled']:
            return status

    raise TimeoutError("Task polling timeout")
```

### Input Validation

Validate inputs before submission:

```python
import re

def is_valid_audio_url(url):
    """Basic validation for audio URLs."""
    if not url.startswith(('http://', 'https://')):
        return False

    # Check for common audio extensions
    audio_extensions = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']
    return any(url.lower().endswith(ext) for ext in audio_extensions)
```

## Support

For integration issues or questions:

1. Check this documentation first
2. Review the [A2A v0.3 specification](https://a2a.how/)
3. Test with the staging environment first
4. Open an issue on the project repository

## Version History

- **v1.0.0**: Initial A2A v0.3 implementation
  - Agent discovery via `/.well-known/agent-card.json`
  - JSON-RPC task submission and polling
  - 6 core audio processing skills
  - Background task processing with status tracking

---

**Last Updated**: 2025-12-17
**Related Docs**:
- [README.md](../README.md) - High-level A2A overview
- [A2A MVP Tasks](a2a-mvp-tasks.md) - Implementation tracking
- [Cloud Build Triggers](cloud-build-triggers.md) - Deployment setup
