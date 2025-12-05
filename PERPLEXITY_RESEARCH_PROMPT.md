# Perplexity Research Prompt - MCP Server Testing Plan Gaps

**Topic**: MCP Server Testing Infrastructure and Tools

**Research Areas with Medium/Low Confidence:**

## 1. MCP Inspector Installation & Setup
- Current installation methods for MCP Inspector (2025)
- Platform-specific setup (macOS, Linux, Windows)
- Version compatibility with FastMCP and current MCP protocol
- Configuration file format and location requirements

## 2. Newman CLI vs Postman Desktop
- Newman CLI capabilities for MCP server testing
- Differences in authentication/session handling
- Collection execution speed and reliability
- Integration with CI/CD pipelines
- Environment variable management in CLI vs GUI

## 3. HTTP Range Request Implementation
- Best practices for audio streaming Range request support
- Content-Range header formatting for partial audio content
- Accept-Ranges header implementation
- Performance implications of Range requests on GCS

## 4. Proxy Configuration for MCP Inspector
- Specific proxy settings required for MCP protocol
- Authorization header passthrough configuration
- WebSocket/streaming proxy requirements
- Common proxy server compatibility issues

## 5. Large File Download Handling
- FFmpeg memory usage patterns during audio conversion
- Temporary file cleanup strategies for large files
- Timeout handling for long-running conversions
- GCS signed URL expiration management

## 6. Performance Benchmarks
- Realistic response time expectations for audio metadata operations
- Search query performance baselines for PostgreSQL full-text search
- Audio streaming startup latency targets
- Concurrent request handling capacity

## 7. MCP Protocol Error Handling
- Standard MCP error response formats
- Session management and reconnection strategies
- Tool execution timeout handling
- Resource access failure scenarios

---

**Specific Questions:**

1. **MCP Inspector 2025**: What's the current recommended way to install and configure MCP Inspector for local development? Any breaking changes from 2024 versions?

2. **Newman CLI Testing**: Can Newman CLI effectively test MCP servers with session management and streaming responses? What are the limitations vs Postman Desktop?

3. **HTTP Range Requests**: What's the most efficient way to implement Range request support for audio streaming from Google Cloud Storage?

4. **Large Audio Files**: What are the memory and performance considerations when using FFmpeg to convert large audio files (100MB+) in a server environment?

5. **MCP Inspector Proxies**: What specific proxy configurations are needed for MCP Inspector to work through corporate proxies, especially for the Authorization header?

6. **Performance Targets**: What are realistic performance benchmarks for audio metadata APIs and search operations in a PostgreSQL-backed service?

---

**Context**: This is for testing a FastMCP-based audio processing server with HTTP REST API endpoints. Need to validate both MCP protocol compliance and HTTP API functionality.
