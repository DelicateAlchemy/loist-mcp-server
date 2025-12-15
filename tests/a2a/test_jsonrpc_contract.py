"""
A2A JSON-RPC Contract Tests

Tests the exact JSON-RPC contract surface exposed by A2AFastAPIApplication.
Validates message/send, tasks/get methods and JSON-RPC 2.0 error handling.

Author: Task Master AI
Created: $(date)
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

import httpx

# Set up import path before attempting A2A imports
import sys
import os

# Ensure site-packages is in path (as suggested in debugging guide)
site_packages = '/usr/local/lib/python3.11/site-packages'
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)
    print(f"[DEBUG] Added {site_packages} to sys.path")

# Also ensure /app is in path
if '/app' not in sys.path:
    sys.path.insert(0, '/app')
    print(f"[DEBUG] Added /app to sys.path")

print(f"[DEBUG] sys.path[0] = {sys.path[0]}")
print(f"[DEBUG] PYTHONPATH = {os.environ.get('PYTHONPATH', 'NOT SET')}")

# Try to import a2a types, skip tests if not available
print(f"\n[DEBUG] Starting A2A import attempt in pytest context")
try:
    print(f"[DEBUG] Attempting: import a2a")
    import a2a
    print(f"[DEBUG] ✓ import a2a succeeded")

    print(f"[DEBUG] Attempting: from a2a.types import Message")
    from a2a.types import Message
    print(f"[DEBUG] ✓ from a2a.types import Message succeeded")

    print(f"[DEBUG] Attempting: full A2A imports")
    from a2a.types import (
        MessageSendParams,
        TaskQueryParams,
        Task,
        TaskState,
        TaskStatus,
        Message,
        TextPart,
    )
    from a2a.server.tasks import DatabaseTaskStore
    from a2a.server.apps import A2AFastAPIApplication
    from src.a2a_server.app import create_a2a_app
    from src.a2a_server.agent_card import create_agent_card
    from src.a2a_server.handler import LoistRequestHandler
    A2A_AVAILABLE = True
    print(f"[DEBUG] ✓ All A2A imports succeeded, A2A_AVAILABLE = True")
except ImportError as e:
    A2A_AVAILABLE = False
    print(f"[DEBUG] ✗ A2A import failed: {e}")
    # Create dummy types for pytest collection
    MessageSendParams = None
    TaskQueryParams = None
    Task = None
    TaskState = None
    TaskStatus = None
    Message = None
    TextPart = None
    DatabaseTaskStore = None
    A2AFastAPIApplication = None
    create_a2a_app = None
    create_agent_card = None
    LoistRequestHandler = None

print(f"[DEBUG] Final A2A_AVAILABLE = {A2A_AVAILABLE}")

# Try to import business types, skip tests if not available
try:
    from src.business import AudioProcessingResult, AudioProcessingRequest
    from src.business.audio_processor import AudioMetadata, ProductMetadata, FormatMetadata, AudioResources
    BUSINESS_AVAILABLE = True
except ImportError:
    BUSINESS_AVAILABLE = False
    AudioProcessingResult = None
    AudioProcessingRequest = None
    AudioMetadata = None
    ProductMetadata = None
    FormatMetadata = None
    AudioResources = None


# Skip marker for all test methods - temporarily disabled for debugging
# pytestmark = pytest.mark.skipif(not A2A_AVAILABLE, reason="A2A SDK not available (a2a-sdk package not installed)")


@pytest.fixture
def mock_task_store():
    """Create a mock DatabaseTaskStore for testing."""
    store = AsyncMock(spec=DatabaseTaskStore)
    store.save = AsyncMock()
    store.get = AsyncMock()
    return store


@pytest.fixture
def mock_audio_processing_result():
    """Create a mock AudioProcessingResult for successful processing."""
    if not BUSINESS_AVAILABLE:
        pytest.skip("Business module not available")
    return AudioProcessingResult(
        success=True,
        audio_id=str(uuid.uuid4()),
        metadata=AudioMetadata(
            product=ProductMetadata(
                artist="Test Artist",
                title="Test Track",
                album="Test Album",
            ),
            format=FormatMetadata(
                duration=180.5,
                channels=2,
                sample_rate=44100,
                bitrate=320000,
                format="MP3"
            ),
            url_embed_link="https://loist.io/embed/test-id"
        ),
        resources=AudioResources(
            audio_url="music-library://audio/test-id/stream",
            thumbnail_url=None,
            waveform_url=None
        ),
        processing_time=2.5
    )


@pytest.fixture
async def a2a_app(mock_task_store, mock_audio_processing_result):
    """Create A2A FastAPI app with mocked dependencies."""
    if not A2A_AVAILABLE:
        # Temporarily raise error instead of skip to see what's happening
        raise RuntimeError(f"A2A SDK not available (A2A_AVAILABLE={A2A_AVAILABLE})")

    # Create agent card
    agent_card = create_agent_card()

    # Create handler with mock task store
    handler = LoistRequestHandler(task_store=mock_task_store)

    # Create A2A app
    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=handler
    )

    # Build FastAPI app
    app = a2a_app.build()

    # Store mock references for test access
    app.state.mock_task_store = mock_task_store

    # Mock the audio processing where it's imported in the handler
    with patch('src.a2a_server.handler.process_audio_shared', return_value=mock_audio_processing_result):
        yield app


@pytest.fixture
async def client(a2a_app):
    """HTTP client for testing the A2A FastAPI app."""
    async with httpx.AsyncClient(app=a2a_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_message():
    """Create a sample A2A message with audio URL."""
    if not A2A_AVAILABLE:
        pytest.skip("A2A SDK not available")
    return Message(
        id=str(uuid.uuid4()),
        role="user",
        parts=[
            TextPart(type="text", text="Please process this audio: https://example.com/test.mp3")
        ]
    )


def _create_jsonrpc_request(method: str, params: dict, request_id: str = "req-123") -> dict:
    """Helper to create a JSON-RPC 2.0 request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    }


def _create_task(task_id: str, state):
    """Helper to create a test Task object."""
    if not A2A_AVAILABLE:
        raise RuntimeError("A2A SDK required")
    return Task(
        id=task_id,
        context_id="test-context",
        kind="task",
        status=TaskStatus(state=state),
        artifacts=[],
        history=[],
        metadata={}
    )


class TestMessageSendHappyPath:
    """Test message/send JSON-RPC method happy path."""

    @pytest.mark.asyncio
    async def test_message_send_creates_task_with_submitted_status(
        self, client, a2a_app, mock_task_store, sample_message
    ):
        """Test that message/send creates a task with submitted status."""
        # Configure mock to return None (task not found initially)
        mock_task_store.get.return_value = None

        # Create JSON-RPC request
        request = _create_jsonrpc_request(
            method="message/send",
            params={"message": sample_message.model_dump()},
            request_id="test-1"
        )

        # Make request (should fail at audio processing but we can check task creation)
        with patch.object(a2a_app.state, 'mock_process_audio_shared', side_effect=Exception("Test error")):
            response = await client.post("/", json=request)

        # Verify response is JSON-RPC 2.0 format (even on error)
        assert response.status_code == 200
        response_data = response.json()
        assert "jsonrpc" in response_data
        assert "id" in response_data
        assert response_data["id"] == "test-1"

        # Verify task was saved with submitted status
        assert mock_task_store.save.call_count >= 1
        saved_task = mock_task_store.save.call_args_list[0][0][0]
        assert saved_task.status.state == TaskState.submitted

    @pytest.mark.asyncio
    async def test_message_send_advances_to_working_status(
        self, client, a2a_app, mock_task_store, sample_message, mock_audio_processing_result
    ):
        """Test that message/send advances task to working status during processing."""
        # Configure mocks
        mock_task_store.get.return_value = None
        a2a_app.state.mock_process_audio_shared.return_value = mock_audio_processing_result

        # Create JSON-RPC request
        request = _create_jsonrpc_request(
            method="message/send",
            params={"message": sample_message.model_dump()},
            request_id="test-2"
        )

        # Make request
        response = await client.post("/", json=request)

        # Verify success response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["jsonrpc"] == "2.0"
        assert "result" in response_data
        assert "id" in response_data["result"]

        # Verify task transitioned through states
        save_calls = mock_task_store.save.call_args_list
        assert len(save_calls) >= 2

        # First save: submitted status
        first_task = save_calls[0][0][0]
        assert first_task.status.state == TaskState.submitted

        # Second save: working status
        second_task = save_calls[1][0][0]
        assert second_task.status.state == TaskState.working

    @pytest.mark.asyncio
    async def test_message_send_completes_with_artifacts(
        self, client, a2a_app, mock_task_store, sample_message, mock_audio_processing_result
    ):
        """Test that message/send completes task with artifacts on success."""
        # Configure mocks
        mock_task_store.get.return_value = None
        a2a_app.state.mock_process_audio_shared.return_value = mock_audio_processing_result

        # Create JSON-RPC request
        request = _create_jsonrpc_request(
            method="message/send",
            params={"message": sample_message.model_dump()},
            request_id="test-3"
        )

        # Make request
        response = await client.post("/", json=request)

        # Verify success response
        assert response.status_code == 200
        response_data = response.json()
        assert "result" in response_data
        task = response_data["result"]
        assert task["status"]["state"] == "completed"
        assert len(task["artifacts"]) == 1
        assert task["artifacts"][0]["type"] == "audio_processing_result"


class TestTasksGetPolling:
    """Test tasks/get JSON-RPC method for polling task status."""

    @pytest.mark.asyncio
    async def test_tasks_get_returns_task_when_found(self, client, mock_task_store):
        """Test that tasks/get returns task when found."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id, TaskState.completed)
        mock_task_store.get.return_value = task

        # Create JSON-RPC request
        request = _create_jsonrpc_request(
            method="tasks/get",
            params={"taskId": task_id},
            request_id="test-get-1"
        )

        # Make request
        response = await client.post("/", json=request)

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "result" in response_data
        assert response_data["result"]["id"] == task_id
        assert response_data["result"]["status"]["state"] == "completed"

        # Verify task store was called correctly
        mock_task_store.get.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_tasks_get_returns_null_when_task_not_found(self, client, mock_task_store):
        """Test that tasks/get returns null when task not found."""
        task_id = str(uuid.uuid4())
        mock_task_store.get.return_value = None

        # Create JSON-RPC request
        request = _create_jsonrpc_request(
            method="tasks/get",
            params={"taskId": task_id},
            request_id="test-get-2"
        )

        # Make request
        response = await client.post("/", json=request)

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["result"] is None

        # Verify task store was called correctly
        mock_task_store.get.assert_called_once_with(task_id)


class TestJsonRpcErrorFormat:
    """Test JSON-RPC error envelope format."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_parse_error(self, client):
        """Test that invalid JSON returns parse error with HTTP 200."""
        # Send invalid JSON
        response = await client.post("/", content="invalid json", headers={"Content-Type": "application/json"})

        # Should return HTTP 200 with JSON-RPC error
        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"]["code"] == -32700  # Parse error
        assert "jsonrpc" in response_data

    @pytest.mark.asyncio
    async def test_invalid_request_format_returns_error(self, client):
        """Test that invalid JSON-RPC request format returns error with HTTP 200."""
        # Missing required fields
        invalid_request = {"method": "test"}  # Missing jsonrpc, id

        response = await client.post("/", json=invalid_request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"]["code"] == -32600  # Invalid Request

    @pytest.mark.asyncio
    async def test_method_not_found_returns_error(self, client):
        """Test that unknown method returns method not found error."""
        request = _create_jsonrpc_request(
            method="nonexistent/method",
            params={},
            request_id="test-error-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"]["code"] == -32601  # Method not found


class TestJsonRpcErrorCodes:
    """Test specific JSON-RPC error codes."""

    @pytest.mark.asyncio
    async def test_parse_error_code(self, client):
        """Test parse error code (-32700)."""
        response = await client.post("/", content="{invalid", headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["error"]["code"] == -32700

    @pytest.mark.asyncio
    async def test_invalid_request_error_code(self, client):
        """Test invalid request error code (-32600)."""
        # Request missing jsonrpc field
        response = await client.post("/", json={"method": "test", "id": 1})

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_method_not_found_error_code(self, client):
        """Test method not found error code (-32601)."""
        request = _create_jsonrpc_request("unknown.method", {}, "test-method-not-found")

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_invalid_params_error_code(self, client):
        """Test invalid params error code (-32602)."""
        # tasks/get with invalid taskId
        request = _create_jsonrpc_request("tasks/get", {"taskId": "not-a-uuid"}, "test-invalid-params")

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["error"]["code"] == -32602


class TestNegativeTestCases:
    """Test negative/edge cases for A2A JSON-RPC methods."""

    @pytest.mark.asyncio
    async def test_message_send_with_invalid_message_structure(self, client):
        """Test message/send with invalid message structure."""
        request = _create_jsonrpc_request(
            method="message/send",
            params={"message": {"invalid": "structure"}},
            request_id="test-invalid-msg"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_tasks_get_with_invalid_task_id(self, client):
        """Test tasks/get with invalid task ID format."""
        request = _create_jsonrpc_request(
            method="tasks/get",
            params={"taskId": "definitely-not-a-uuid"},
            request_id="test-invalid-uuid"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_tasks_get_with_nonexistent_task(self, client, mock_task_store):
        """Test tasks/get with valid UUID but nonexistent task."""
        task_id = str(uuid.uuid4())
        mock_task_store.get.return_value = None

        request = _create_jsonrpc_request(
            method="tasks/get",
            params={"taskId": task_id},
            request_id="test-not-found"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["result"] is None  # Should return null, not error

        mock_task_store.get.assert_called_once_with(task_id)
