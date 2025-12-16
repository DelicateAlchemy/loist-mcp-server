"""
A2A End-to-End Tests (Pytest Version)

Structured pytest-based E2E tests that validate the complete A2A task workflow
against real docker-compose environments. Provides better test organization,
error reporting, and CI integration than shell scripts.

Run with: docker-compose exec mcp-server pytest tests/e2e/test_a2a_docker_compose.py -v
"""

import pytest
import httpx
import asyncio
import time
import subprocess
import json
from typing import Optional, Dict, Any
import os


@pytest.fixture(scope="session")
def test_audio_url():
    """Test audio URL for processing."""
    return "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav"


@pytest.fixture(scope="session")
def docker_compose_status():
    """Check if docker-compose is running and healthy."""
    try:
        # Check if containers are running
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            pytest.skip("docker-compose not available or containers not running")

        if "Up" not in result.stdout:
            pytest.skip("No docker-compose containers are running")

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("docker-compose command not available")


@pytest.fixture(scope="session")
async def server_readiness(docker_compose_status):
    """Ensure both MCP and A2A servers are ready."""
    a2a_url = "http://localhost:8081"
    mcp_url = "http://localhost:8080"
    max_wait = 60

    async with httpx.AsyncClient() as client:
        # Wait for MCP server
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = await client.get(f"{mcp_url}/health/ready", timeout=5.0)
                if response.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            await asyncio.sleep(2)
        else:
            pytest.fail("MCP server did not become ready within 60 seconds")

        # Wait for A2A server
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = await client.get(f"{a2a_url}/.well-known/agent-card.json", timeout=5.0)
                if response.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            await asyncio.sleep(2)
        else:
            pytest.fail("A2A server did not become ready within 60 seconds")

    return {"a2a_url": a2a_url, "mcp_url": mcp_url}


@pytest.fixture
async def a2a_client(server_readiness):
    """HTTP client for A2A server."""
    async with httpx.AsyncClient(
        base_url=server_readiness["a2a_url"],
        timeout=30.0
    ) as client:
        yield client


class TestA2AEndToEnd:
    """End-to-end tests for A2A task processing workflow."""

    @pytest.mark.asyncio
    async def test_message_send_creates_task(self, a2a_client, test_audio_url):
        """Test that message/send creates a task with proper structure."""
        request_id = f"test-{int(time.time())}"

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": request_id,
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "text": f"Process this audio: {test_audio_url}"
                        }
                    ]
                }
            }
        }

        response = await a2a_client.post("/", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Should not have error
        assert "error" not in data
        assert "result" in data

        # Extract task information
        result = data["result"]
        assert "id" in result
        assert isinstance(result["id"], str)
        assert len(result["id"]) > 0

        assert "status" in result
        assert "state" in result["status"]
        assert result["status"]["state"] in ["submitted", "working", "completed"]

        # Store task ID for subsequent tests
        self.task_id = result["id"]
        self.initial_status = result["status"]["state"]

    @pytest.mark.asyncio
    async def test_task_polling_until_completion(self, a2a_client):
        """Test that tasks/get polls correctly until terminal state."""
        assert hasattr(self, 'task_id'), "Task ID not set from previous test"

        max_attempts = 30
        poll_interval = 2
        total_wait = 0

        for attempt in range(max_attempts):
            request_id = f"poll-{int(time.time())}"

            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tasks/get",
                "params": {"id": self.task_id}
            }

            response = await a2a_client.post("/", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"] is not None

            task = data["result"]
            status = task["status"]["state"]

            terminal_states = ["completed", "failed", "canceled", "rejected"]

            if status in terminal_states:
                self.final_task_response = task
                self.final_status = status
                break

            # Wait before next poll (exponential backoff)
            wait_time = min(poll_interval * (2 ** min(attempt, 4)), 30)
            total_wait += wait_time
            await asyncio.sleep(wait_time)

        else:
            pytest.fail(f"Task did not reach terminal state within {total_wait}s ({max_attempts} attempts)")

        # Verify we got a successful completion
        assert self.final_status == "completed", f"Expected completed status, got {self.final_status}"

    @pytest.mark.asyncio
    async def test_task_metadata_contains_processing_result(self, a2a_client):
        """Test that completed task metadata contains expected audio processing results."""
        assert hasattr(self, 'final_task_response'), "Task response not available"

        task = self.final_task_response
        assert "metadata" in task, "Task metadata missing"

        # Check for audio_track_id
        assert "audio_track_id" in task["metadata"], "audio_track_id missing from task metadata"
        audio_track_id = task["metadata"]["audio_track_id"]
        assert audio_track_id is not None and audio_track_id != "", "audio_track_id is empty"
        
        # Store audio_id for database verification
        self.audio_id = audio_track_id

        # Check for processing_result
        assert "processing_result" in task["metadata"], "processing_result missing from task metadata"
        processing_result = task["metadata"]["processing_result"]

        # Check required fields in processing result
        required_fields = ["audio_id", "metadata", "resources", "processing_time", "success"]
        for field in required_fields:
            assert field in processing_result, f"Required field '{field}' missing from processing result"

        # Verify success is True
        assert processing_result["success"] is True, "Processing result success is not True"

        # Check metadata structure in processing result
        assert "metadata" in processing_result
        metadata = processing_result["metadata"]
        assert "product" in metadata, "metadata.product missing from processing result"
        assert "format" in metadata, "metadata.format missing from processing result"

        # Check product metadata
        product = metadata["product"]
        assert "title" in product, "Product metadata missing title"

        # Check format metadata
        format_data = metadata["format"]
        required_format_fields = ["duration", "channels", "sample_rate", "bitrate"]
        for field in required_format_fields:
            assert field in format_data, f"Format metadata missing {field}"

    @pytest.mark.asyncio
    async def test_database_linkage(self, docker_compose_status):
        """Test bidirectional database linkage between A2A tasks and audio tracks."""
        assert hasattr(self, 'task_id'), "Task ID not available"
        assert hasattr(self, 'audio_id'), "Audio ID not available"

        # Query audio_tracks.a2a_task_id
        psql_cmd = [
            "docker-compose", "exec", "-T", "postgres",
            "psql", "-U", "loist_user", "-d", "loist_mvp", "-t", "-c",
            f"SELECT a2a_task_id FROM audio_tracks WHERE id = '{self.audio_id}';"
        ]

        result = subprocess.run(psql_cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Database query failed: {result.stderr}"

        db_a2a_task_id = result.stdout.strip()
        assert db_a2a_task_id == self.task_id, \
            f"Database linkage mismatch: expected '{self.task_id}', got '{db_a2a_task_id}'"

        # Verify audio track exists and is completed
        count_cmd = [
            "docker-compose", "exec", "-T", "postgres",
            "psql", "-U", "loist_user", "-d", "loist_mvp", "-t", "-c",
            f"SELECT COUNT(*) FROM audio_tracks WHERE id = '{self.audio_id}' AND status = 'COMPLETED';"
        ]

        count_result = subprocess.run(count_cmd, capture_output=True, text=True)
        assert count_result.returncode == 0
        assert count_result.stdout.strip() == "1", \
            f"Audio track {self.audio_id} not found or not completed"

        # Verify metadata exists
        metadata_cmd = [
            "docker-compose", "exec", "-T", "postgres",
            "psql", "-U", "loist_user", "-d", "loist_mvp", "-t", "-c",
            f"SELECT CASE WHEN title IS NOT NULL AND duration_seconds IS NOT NULL THEN 'true' ELSE 'false' END FROM audio_tracks WHERE id = '{self.audio_id}';"
        ]

        metadata_result = subprocess.run(metadata_cmd, capture_output=True, text=True)
        assert metadata_result.returncode == 0
        assert metadata_result.stdout.strip() == "true", \
            f"Audio track {self.audio_id} missing required metadata"

    @pytest.mark.asyncio
    async def test_task_failure_handling(self, a2a_client):
        """Test that failed tasks are handled properly with error artifacts."""
        # This test would run with a URL that causes processing to fail
        # For now, we'll skip as we don't have a reliable failure case
        pytest.skip("Failure case testing requires specific failure-inducing audio URL")

    @pytest.mark.asyncio
    async def test_jsonrpc_error_handling(self, a2a_client):
        """Test JSON-RPC error responses for invalid requests."""
        # Test invalid method
        payload = {
            "jsonrpc": "2.0",
            "id": "error-test-1",
            "method": "invalid/method",
            "params": {}
        }

        response = await a2a_client.post("/", json=payload)
        assert response.status_code == 200  # JSON-RPC always returns 200

        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert data["error"]["code"] == -32601  # Method not found
