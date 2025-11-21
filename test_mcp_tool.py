#!/usr/bin/env python3
"""
Test MCP tools directly by importing and calling them
"""
import asyncio
import sys
import os
from pathlib import Path

# Setup paths
project_root = Path.cwd()
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(project_root))

async def test_mcp_tools():
    try:
        print("Testing MCP tools directly...")
        
        # Import the MCP server module to access the tools
        from src import server
        
        # Test health check
        print("\n1. Testing health_check tool...")
        result = server.health_check()
        print(f"Health check result: {result}")
        
        # Test process_audio_complete
        print("\n2. Testing process_audio_complete tool...")
        result = await server.process_audio_complete({
            'source': {
                'type': 'http_url',
                'url': 'https://tmpfiles.org/dl/8203556/xcd227_12_1popasquat_30seconds.mp3'
            },
            'options': {
                'maxSizeMB': 10,
                'timeout': 30
            }
        })
        print(f"Process audio result: {result}")
        
        print("\n✅ All MCP tools are working!")
        
    except Exception as e:
        print(f"❌ Error testing MCP tools: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_tools())
