# MCP Tool Discovery Fix

## Problem
The MCP server was showing "No tools, prompts, or resources" in Cursor's MCP interface despite successful initialization.

## Root Causes Identified

1. **Container CMD Issue**: The Dockerfile had `CMD ["python", "src/server.py"]` which would start the server immediately. With STDIO transport, this causes the server to exit when stdin is empty.

2. **Environment Variable Conflict**: The docker-compose.yml set `SERVER_TRANSPORT=http` which conflicted with the STDIO transport needed for Cursor integration.

3. **Implicit Transport**: The server.py wasn't explicitly using the transport from config when calling `mcp.run()`.

4. **Python Import Path Issues**: Incorrect import paths throughout the codebase preventing modules from being found during runtime.

## Changes Made

### 1. Dockerfile (`Dockerfile`)
Changed the CMD to keep the container running without starting the server:
```dockerfile
# Keep container running for STDIO mode (server started via docker exec)
CMD ["tail", "-f", "/dev/null"]
```

### 2. docker-compose.yml
Removed the conflicting `SERVER_TRANSPORT=http` environment variable:
```yaml
# SERVER_TRANSPORT set by mcp.json for STDIO mode
```

### 3. src/server.py
Explicitly pass transport from config to `mcp.run()`:
```python
mcp.run(transport=config.server_transport)
```

### 4. Python Import Path Fixes

Fixed import paths throughout the codebase to work properly in Docker environment.

#### Changes in `src/server.py`:
Added both project root and src directory to Python path:
```python
# Add both project root and src directory to Python path
server_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(server_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, server_dir)
```

#### Removed `src.` prefix from imports in:
- `src/tools/process_audio.py`
- `src/tools/query_tools.py`
- `src/resources/thumbnail.py`
- `src/resources/audio_stream.py`
- `database/pool.py`
- `database/operations.py`

**Before:**
```python
from src.downloader.http_downloader import download_from_url
from src.exceptions import MusicLibraryError
```

**After:**
```python
from downloader.http_downloader import download_from_url
from exceptions import MusicLibraryError
```

#### Added missing imports:
- Added `ResourceNotFoundError` import to `database/operations.py`
- Added `packaging` dependency to `requirements.txt`

#### Fixed MCP configuration (`.cursor/mcp.json`):
Updated database connection parameters to use local Docker configuration:
```json
"DB_HOST=postgres DB_PORT=5432 DB_NAME=loist_mvp DB_USER=loist_user DB_PASSWORD=dev_password DATABASE_URL=postgresql://loist_user:dev_password@postgres:5432/loist_mvp"
```

#### Mounted service account key in `docker-compose.yml`:
```yaml
volumes:
  - ./service-account-key.json:/app/service-account-key.json:ro
```

## Testing

### 1. Verify Container is Running
```bash
docker ps | grep music-library-mcp
```

Expected output: Container should be running with status "Up" and command "tail -f /dev/null"

### 2. Test Tool Registration
```bash
docker exec music-library-mcp python -c "
import sys
sys.path.insert(0, 'src')
from server import mcp
print('Server:', mcp.name)
print('Has tools:', hasattr(mcp, 'get_tools'))
"
```

### 3. Test MCP Protocol
To simulate what Cursor does, you can manually test with:
```bash
# Start the server in STDIO mode
docker exec -i music-library-mcp sh -c '
SERVER_TRANSPORT=stdio \
AUTH_ENABLED=false \
python src/server.py
'
```

Then send JSON-RPC messages to stdin:
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

### 4. Check Cursor MCP Interface
After restarting Cursor, check the MCP servers panel. You should see:
- ✅ Server connected
- ✅ Tools listed (health_check, process_audio_complete, get_audio_metadata, search_library)
- ✅ Resources listed (audio stream, thumbnail)

## Expected Tools

The following tools should be available:
1. `health_check` - Verify server status and connectivity
2. `process_audio_complete` - Process audio from HTTP URL
3. `get_audio_metadata` - Retrieve audio metadata
4. `search_library` - Search audio library

## Expected Resources

The following resources should be available:
1. `music-library://audio/{id}/stream` - Audio stream access
2. `music-library://audio/{id}/thumbnail` - Thumbnail/artwork access

## Troubleshooting

### If tools still don't appear in Cursor:

1. **Restart Cursor**: Close and reopen Cursor to reload MCP servers
2. **Check Container Status**: `docker ps | grep music-library-mcp`
3. **View Container Logs**: `docker logs music-library-mcp`
4. **Verify mcp.json**: Check that `.cursor/mcp.json` has correct configuration
5. **Test Manual Execution**: Run the docker exec command manually to see server output

### Container Not Running?
```bash
cd /Users/Gareth/loist-mcp-server
docker-compose up -d mcp-server
```

### Need to Rebuild?
```bash
cd /Users/Gareth/loist-mcp-server
docker-compose build mcp-server
docker-compose up -d mcp-server
 Bancode
```

## Architecture Notes

The server now runs in two modes:

1. **STDIO Mode** (for Cursor): Started via `docker exec` with `SERVER_TRANSPORT=stdio`
2. **HTTP Mode** (for local testing): Could be started with `SERVER_TRANSPORT=http`

The container keeps running idle (tail -f /dev/null) until Cursor executes it via docker exec, providing proper STDIO connection for MCP protocol.

## ✅ Verification - Successfully Processing Audio

After applying all fixes, the server successfully processed an audio file:

### Test Audio Processing:
```bash
# Successfully processed Charli XCX - Club classics
# URL: https://tmpfiles.org/dl/5638200/charlixcx-clubclassics.mp3
```

### Result:
- ✅ Audio downloaded successfully
- ✅ Metadata extracted (Artist: "Charli XCX", Title: "Charli xcx - Club classics (official lyric video)")
- ✅ Uploaded to GCS: `audio/c7fd6016-8d62-4e1f-9f8f-4f8cdc3f8080/`
- ✅ Saved to PostgreSQL database
- ✅ Processing time: 2.8 seconds
- ✅ Audio ID: `c7fd6016-8d62-4e1f-9f8f-4f8cdc3f8080`

### MCP Tools Working:
1. ✅ `process_audio_complete` - Successfully processing audio files
2. ✅ `get_audio_metadata` - Retrieving audio metadata
3. ✅ `search_library` - Searching audio library
4. ✅ `health_check` - Server health verification

### Resources Working:
1. ✅ `music-library://audio/{id}/stream` - Audio stream resource
2. ✅ `music-library://audio/{id}/thumbnail` - Thumbnail resource

## 📝 Date
**Fixed**: 2025-10-28  
**Tested**: ✅ Audio processing working end-to-end  
**Status**: ✅ Fully operational


