# Perplexity Research Prompt: JSON-RPC/MCP API Naming Conventions

## Copy-Paste Ready Prompt

```
What is the standard naming convention (camelCase vs snake_case) for JSON-RPC and MCP (Model Context Protocol) API responses in 2025?

Specifically:
1. What naming convention do JSON-RPC 2.0 specifications recommend or commonly use for response field names?
2. What naming convention do MCP (Model Context Protocol) servers typically use for tool responses?
3. Are there any FastMCP (Python library) best practices or conventions for field naming?
4. How do Pydantic models handle field name serialization in JSON-RPC contexts - should we use aliases to convert snake_case to camelCase?
5. What do popular MCP servers (like Anthropic's reference implementations) use for their response field names?

Context: We're building a Python-based MCP server using FastMCP and Pydantic. Our Python code naturally uses snake_case (audio_id, waveform_available), but we're seeing inconsistencies with frontend/Postman tests that expect camelCase (audioId, waveformAvailable). We need to decide whether to:
- Keep snake_case (Python convention)
- Convert to camelCase (JavaScript convention)
- Support both via aliases

Please provide:
- Official specifications or recommendations
- Real-world examples from popular MCP servers
- Best practices for Python/JavaScript interop in JSON-RPC APIs
- Performance considerations for using Pydantic aliases
- Any breaking changes or migration considerations
```

## What to Look For

1. **Official Standards**: JSON-RPC 2.0 spec, MCP protocol docs
2. **Real Examples**: GitHub repos of MCP servers, their response formats
3. **FastMCP Docs**: Any guidance from FastMCP library documentation
4. **Pydantic Patterns**: Common patterns for JSON-RPC serialization
5. **Performance**: Impact of using `by_alias=True` in `model_dump()`

## Expected Research Areas

- JSON-RPC 2.0 specification (RFC 4627, JSON-RPC 2.0 spec)
- MCP protocol documentation (Anthropic's MCP docs)
- FastMCP GitHub repository and documentation
- Pydantic v2 serialization best practices
- Python/JavaScript API interop patterns

## How to Use Results

After getting research results:
1. Compare findings with our current implementation
2. Update `naming-convention-analysis.md` with research findings
3. Make final decision on naming convention
4. Update implementation plan accordingly

