# tests/test_mcp_protocol.py

import pytest
from fastmcp import Client

@pytest.mark.asyncio
async def test_mcp_handshake():
    """Test the MCP handshake (initialize -> initialized)"""
    async with Client("http://localhost:8080/mcp") as client:
        assert client.is_connected()
        init_result = client.initialize_result
        assert init_result is not None
        assert init_result.serverInfo is not None
        assert init_result.serverInfo.name == "Music Library MCP"
