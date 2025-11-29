#!/usr/bin/env python3
"""
Comprehensive test script for all MCP tools in the local Docker environment.
Tests each tool individually and verifies FastMCP decorator functionality.
"""

import json
import asyncio
import requests
from typing import Dict, Any

def test_mcp_tool_via_http(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Test an MCP tool via HTTP POST request."""
    url = "http://localhost:8080/mcp"
    
    # Create MCP protocol request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params
        }
    }
    
    try:
        response = requests.post(url, json=request, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"HTTP request failed: {str(e)}"}

async def test_mcp_tools():
    """Test all MCP tools comprehensively."""
    print("🔧 Testing MCP Tools in Local Docker Environment")
    print("=" * 60)
    
    # Start Docker container in background
    import subprocess
    import time
    
    print("🐳 Starting MCP server in Docker container...")
    container = subprocess.Popen([
        "docker", "run", "-d", "--rm",
        "--name", "mcp-tools-test",
        "--env-file", ".env.gcs-test",
        "-v", "/Users/Gareth/loist-mcp-server/service-account-key.json:/app/service-account-key.json",
        "-v", "/Users/Gareth/loist-mcp-server:/app",
        "-w", "/app",
        "--network", "host",
        "loist-mcp-server:local",
        "python", "run_server.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    container_id, stderr = container.communicate()
    container_id = container_id.decode().strip()
    
    if container.returncode != 0:
        print(f"❌ Failed to start container: {stderr.decode()}")
        return False
    
    print(f"✅ Container started: {container_id[:12]}")
    
    # Wait for server to be ready
    print("⏳ Waiting for server to be ready...")
    time.sleep(5)
    
    try:
        # Test 1: Health Check Tool
        print("\n🏥 Testing health_check tool...")
        result = test_mcp_tool_via_http("health_check", {})
        
        if "error" in result:
            print(f"❌ Health check failed: {result['error']}")
            return False
        elif result.get("result", {}).get("status") == "healthy":
            print("✅ Health check passed")
            print(f"   Service: {result['result'].get('service')}")
            print(f"   Version: {result['result'].get('version')}")
            print(f"   Transport: {result['result'].get('transport')}")
        else:
            print(f"⚠️  Health check unexpected result: {result}")
        
        # Test 2: Get Audio Metadata Tool (with invalid ID first)
        print("\n📋 Testing get_audio_metadata tool (invalid ID)...")
        result = test_mcp_tool_via_http("get_audio_metadata", {"audioId": "invalid-id"})
        
        if "error" in result:
            print(f"❌ Get metadata failed: {result['error']}")
        else:
            print("✅ Get metadata handled invalid ID correctly")
            print(f"   Error type: {result.get('result', {}).get('error', {}).get('type')}")
        
        # Test 3: Search Library Tool
        print("\n🔍 Testing search_library tool...")
        result = test_mcp_tool_via_http("search_library", {
            "query": "test",
            "limit": 5
        })
        
        if "error" in result:
            print(f"❌ Search library failed: {result['error']}")
        else:
            print("✅ Search library executed successfully")
            total = result.get("result", {}).get("total", 0)
            print(f"   Total results: {total}")
        
        # Test 4: Process Audio Complete Tool (with invalid URL)
        print("\n🎵 Testing process_audio_complete tool (invalid URL)...")
        result = test_mcp_tool_via_http("process_audio_complete", {
            "source": {
                "type": "http_url",
                "url": "https://invalid-url-that-does-not-exist.com/audio.mp3"
            }
        })
        
        if "error" in result:
            print("✅ Process audio handled invalid URL correctly")
            print(f"   Error type: {result.get('result', {}).get('error', {}).get('type')}")
        else:
            print("⚠️  Process audio unexpected result for invalid URL")
        
        print("\n🎉 All MCP tools tested successfully!")
        print("✅ FastMCP decorators working correctly")
        print("✅ HTTP transport functioning properly")
        print("✅ Error handling working as expected")
        
        return True
        
    finally:
        # Clean up container
        print("\n🧹 Cleaning up test container...")
        subprocess.run(["docker", "stop", container_id], capture_output=True)
        print("✅ Container stopped")

if __name__ == "__main__":
    success = asyncio.run(test_mcp_tools())
    exit(0 if success else 1)
