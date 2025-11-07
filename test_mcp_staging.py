#!/usr/bin/env python3
"""
Test script for MCP staging server with proper session management.
"""
import asyncio
import json
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STAGING_URL = "https://staging.loist.io/mcp"

async def test_mcp_session():
    """Test MCP session management and tool calls."""

    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Initialize session
            logger.info("Initializing MCP session...")
            init_payload = {
                "jsonrpc": "2.0",
                "id": "init-1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }

            async with session.post(STAGING_URL, json=init_payload,
                                  headers={"Content-Type": "application/json"}) as response:
                if response.status != 200:
                    logger.error(f"Init failed with status {response.status}")
                    text = await response.text()
                    logger.error(f"Response: {text}")
                    return

                init_response = await response.json()
                logger.info(f"Init response: {json.dumps(init_response, indent=2)}")

                if "error" in init_response:
                    logger.error(f"Init error: {init_response['error']}")
                    return

            # Step 2: Get session ID from headers or response
            session_id = None
            if 'x-mcp-session-id' in response.headers:
                session_id = response.headers['x-mcp-session-id']
                logger.info(f"Got session ID from headers: {session_id}")

            # Step 3: Try health check
            logger.info("Testing health check...")
            health_payload = {
                "jsonrpc": "2.0",
                "id": "health-1",
                "method": "tools/call",
                "params": {
                    "name": "health_check"
                }
            }

            headers = {"Content-Type": "application/json"}
            if session_id:
                headers["x-mcp-session-id"] = session_id

            async with session.post(STAGING_URL, json=health_payload, headers=headers) as response:
                health_response = await response.json()
                logger.info(f"Health check response: {json.dumps(health_response, indent=2)}")

                if "error" in health_response:
                    logger.error(f"Health check error: {health_response['error']}")
                    return

            # Step 4: Try process audio complete
            logger.info("Testing process_audio_complete...")
            audio_payload = {
                "jsonrpc": "2.0",
                "id": "audio-1",
                "method": "tools/call",
                "params": {
                    "name": "process_audio_complete",
                    "arguments": {
                        "source": {
                            "type": "http_url",
                            "url": "https://tmpfiles.org/dl/7305873/xcd397_04_3yourtaxi_instrumental30seconds.mp3"
                        }
                    }
                }
            }

            async with session.post(STAGING_URL, json=audio_payload, headers=headers) as response:
                audio_response = await response.json()
                logger.info(f"Audio processing response: {json.dumps(audio_response, indent=2)}")

        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_mcp_session())
