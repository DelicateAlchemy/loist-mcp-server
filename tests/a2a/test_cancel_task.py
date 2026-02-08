"""
Tests for A2A task cancellation (tasks/cancel).

Tests the on_cancel_task implementation including:
- Successful cancellation of running tasks
- Error handling for terminal states
- Error handling for non-existent tasks
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

import httpx

# Try to import a2a types, skip tests if not available
try:
    from a2a.types import (
        TaskIdParams,
        Task,
        TaskState,
        TaskStatus,
        TaskNotFoundError,
        TaskNotCancelableError,
    )
    from a2a.server.tasks import DatabaseTaskStore
    from a2a.server.apps import A2AFastAPIApplication
    from src.a2a_server.app import create_a2a_app
    from src.a2a_server.agent_card import create_agent_card
    from src.a2a_server.handler import LoistRequestHandler
    from a2a.utils.errors import ServerError
    A2A_AVAILABLE = True
except ImportError as e:
    A2A_AVAILABLE = False
    TaskIdParams = None
    Task = None
    TaskState = None
    TaskStatus = None
    TaskNotFoundError = None
    TaskNotCancelableError = None
    DatabaseTaskStore = None
    A2AFastAPIApplication = None
    create_a2a_app = None
    create_agent_card = None
    LoistRequestHandler = None
    ServerError = None


@pytest.fixture
def mock_task_store():
    """Create a mock DatabaseTaskStore for testing."""
    if not A2A_AVAILABLE or DatabaseTaskStore is None:
        pytest.skip("A2A SDK not available")
    store = AsyncMock(spec=DatabaseTaskStore)
    store.save = AsyncMock()
    store.get = AsyncMock()
    return store


@pytest.fixture
async def a2a_app(mock_task_store):
    """Create A2A FastAPI app with mocked dependencies."""
    if not A2A_AVAILABLE:
        pytest.skip("A2A SDK not available")

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
    app.state.mock_task_store = mock_task_store

    yield app


@pytest.fixture
async def client(a2a_app):
    """HTTP client for testing the A2A FastAPI app."""
    transport = httpx.ASGITransport(app=a2a_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _create_jsonrpc_request(method: str, params: dict, request_id: str = "req-123") -> dict:
    """Helper to create a JSON-RPC 2.0 request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    }


def _create_task(task_id: str, state: TaskState):
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


class TestCancelTask:
    """Test task cancellation scenarios."""

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, client, mock_task_store):
        """Test successful task cancellation."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id, TaskState.working)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/cancel",
            params={"id": task_id},
            request_id="test-cancel-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "result" in response_data
        assert response_data["result"]["status"]["state"] == "canceled"
        assert response_data["result"]["id"] == task_id

        # Verify task was saved with canceled status
        mock_task_store.save.assert_called_once()
        saved_task = mock_task_store.save.call_args[0][0]
        assert saved_task.status.state == TaskState.canceled

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, client, mock_task_store):
        """Test cancellation of non-existent task."""
        task_id = str(uuid.uuid4())
        mock_task_store.get.return_value = None

        request = _create_jsonrpc_request(
            method="tasks/cancel",
            params={"id": task_id},
            request_id="test-cancel-2"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"]["code"] != 0  # Error code

    @pytest.mark.asyncio
    async def test_cancel_task_already_completed(self, client, mock_task_store):
        """Test cancellation of already completed task."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id, TaskState.completed)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/cancel",
            params={"id": task_id},
            request_id="test-cancel-3"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data
        # Should return error indicating task cannot be canceled

    @pytest.mark.asyncio
    async def test_cancel_task_already_canceled(self, client, mock_task_store):
        """Test cancellation of already canceled task."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id, TaskState.canceled)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/cancel",
            params={"id": task_id},
            request_id="test-cancel-4"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_cancel_task_already_failed(self, client, mock_task_store):
        """Test cancellation of failed task."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id, TaskState.failed)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/cancel",
            params={"id": task_id},
            request_id="test-cancel-5"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data

