#!/usr/bin/env python3
"""
Test script using MCP client to test staging deployment and EMBED_BASE_URL fix
"""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("❌ MCP client not available. Install with: pip install mcp")
    sys.exit(1)

async def test_staging_server():
    """Test the staging MCP server using the MCP client"""

    print("=========================================")
    print(" Testing Staging MCP Server with Client")
    print("=========================================")
    print()

    # For HTTP transport, we need to use the HTTP client
    # But the MCP library might not have direct HTTP client support
    # Let's try a simpler approach using requests to make HTTP calls

    import requests
    import json

    staging_url = "https://music-library-mcp-staging-7de5nxpr4q-uc.a.run.app/mcp"

    print(f"Testing MCP server at: {staging_url}")
    print()

    # First, initialize the connection
    print("1. Initializing MCP connection...")
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    try:
        response = requests.post(
            staging_url,
            json=init_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            },
            stream=True,
            timeout=10
        )

        if response.status_code == 200:
            # Read SSE response
            init_result = None
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = line_str[6:]  # Remove 'data: ' prefix
                        try:
                            message = json.loads(data)
                            if 'result' in message:
                                init_result = message
                                break
                        except json.JSONDecodeError:
                            continue

            if init_result:
                print("✅ MCP connection initialized successfully")
                server_info = init_result.get('result', {}).get('serverInfo', {})
                print(f"   Server: {server_info.get('name', 'Unknown')}")
                print(f"   Version: {server_info.get('version', 'Unknown')}")
            else:
                print("❌ Failed to get initialization response")
                return False
        else:
            print(f"❌ Initialization failed with status: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Initialization error: {e}")
        return False

    print()

    # Now test health check
    print("2. Testing health_check tool...")
    health_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "health_check",
            "arguments": {}
        }
    }

    try:
        # For tool calls, we might need to establish a proper session
        # Let's try a direct HTTP call first
        response = requests.post(
            staging_url,
            json=health_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            timeout=30
        )

        if response.status_code == 200:
            try:
                result = response.json()
                if 'result' in result:
                    print("✅ Health check passed!")
                    return True
                elif 'error' in result:
                    print(f"❌ Health check failed: {result['error'].get('message', 'Unknown error')}")
                    return False
                else:
                    print(f"❌ Unexpected response: {result}")
                    return False
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON response: {response.text[:200]}...")
                return False
        else:
            print(f"❌ Health check failed with status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

async def main():
    """Main test function"""
    success = await test_staging_server()

    if success:
        print()
        print("=========================================")
        print(" 🎉 MCP SERVER TEST PASSED!")
        print("=========================================")
        print()
        print("The staging MCP server is running correctly.")
        print("Next step: Test EMBED_BASE_URL with process_audio_complete")
    else:
        print()
        print("❌ MCP SERVER TEST FAILED")
        print()
        print("The staging server may not be working properly.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
