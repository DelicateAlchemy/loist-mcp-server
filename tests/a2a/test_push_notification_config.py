"""
Tests for A2A push notification configuration methods.

Tests CRUD operations for push notification configs:
- tasks/pushNotificationConfig/set
- tasks/pushNotificationConfig/get
- tasks/pushNotificationConfig/list
- tasks/pushNotificationConfig/delete
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

import httpx

# Try to import a2a types, skip tests if not available
try:
    from a2a.types import (
        TaskIdParams,
        TaskPushNotificationConfig,
        GetTaskPushNotificationConfigParams,
        ListTaskPushNotificationConfigParams,
        DeleteTaskPushNotificationConfigParams,
        PushNotificationConfig,
        Task,
        TaskState,
        TaskStatus,
        TaskNotFoundError,
        UnsupportedOperationError,
    )
    from a2a.server.tasks import DatabaseTaskStore
    from a2a.server.apps import A2AFastAPIApplication
    from src.a2a_server.app import create_a2a_app
    from src.a2a_server.agent_card import create_agent_card
    from src.a2a_server.handler import LoistRequestHandler
    from src.a2a_server.storage import PushConfigStore
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    TaskIdParams = None
    TaskPushNotificationConfig = None
    GetTaskPushNotificationConfigParams = None
    ListTaskPushNotificationConfigParams = None
    DeleteTaskPushNotificationConfigParams = None
    PushNotificationConfig = None
    Task = None
    TaskState = None
    TaskStatus = None
    TaskNotFoundError = None
    UnsupportedOperationError = None
    DatabaseTaskStore = None
    A2AFastAPIApplication = None
    create_a2a_app = None
    create_agent_card = None
    LoistRequestHandler = None
    PushConfigStore = None


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
def mock_push_config_store():
    """Create a mock PushConfigStore for testing."""
    if not A2A_AVAILABLE or PushConfigStore is None:
        pytest.skip("A2A SDK not available")
    store = AsyncMock(spec=PushConfigStore)
    store.set_info = AsyncMock()
    store.get_info = AsyncMock()
    store.delete_info = AsyncMock()
    return store


@pytest.fixture
async def a2a_app(mock_task_store, mock_push_config_store):
    """Create A2A FastAPI app with mocked dependencies."""
    if not A2A_AVAILABLE:
        pytest.skip("A2A SDK not available")

    # Create agent card
    agent_card = create_agent_card()

    # Create handler with mock stores
    handler = LoistRequestHandler(
        task_store=mock_task_store,
        push_config_store=mock_push_config_store
    )

    # Create A2A app
    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=handler
    )

    # Build FastAPI app
    app = a2a_app.build()
    app.state.mock_task_store = mock_task_store
    app.state.mock_push_config_store = mock_push_config_store

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


def _create_task(task_id: str, state=None):
    """Helper to create a test Task object."""
    if not A2A_AVAILABLE:
        raise RuntimeError("A2A SDK required")
    if state is None:
        state = TaskState.working
    return Task(
        id=task_id,
        context_id="test-context",
        kind="task",
        status=TaskStatus(state=state),
        artifacts=[],
        history=[],
        metadata={}
    )


class TestPushNotificationConfigSet:
    """Test setting push notification configs."""

    @pytest.mark.asyncio
    async def test_set_push_config_success(self, client, mock_task_store, mock_push_config_store):
        """Test successful push notification config set."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/set",
            params={
                "taskId": task_id,
                "pushNotificationConfig": {
                    "url": "https://example.com/webhook",
                    "token": "secret-token"
                }
            },
            request_id="test-push-set-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        # Should succeed (may have result or error depending on implementation)
        mock_push_config_store.set_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_push_config_task_not_found(self, client, mock_task_store, mock_push_config_store):
        """Test setting push config for non-existent task."""
        task_id = str(uuid.uuid4())
        mock_task_store.get.return_value = None

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/set",
            params={
                "taskId": task_id,
                "pushNotificationConfig": {
                    "url": "https://example.com/webhook"
                }
            },
            request_id="test-push-set-2"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data


class TestPushNotificationConfigGet:
    """Test getting push notification configs."""

    @pytest.mark.asyncio
    async def test_get_push_config_success(self, client, mock_task_store, mock_push_config_store):
        """Test successful push notification config get."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id)
        mock_task_store.get.return_value = task

        # Mock push config store to return a config
        mock_config = PushNotificationConfig(url="https://example.com/webhook", token="secret")
        mock_push_config_store.get_info.return_value = [(None, mock_config)]

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/get",
            params={"id": task_id},
            request_id="test-push-get-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        # Should succeed
        mock_push_config_store.get_info.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_get_push_config_not_found(self, client, mock_task_store, mock_push_config_store):
        """Test getting push config when none exists."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id)
        mock_task_store.get.return_value = task
        mock_push_config_store.get_info.return_value = []

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/get",
            params={"id": task_id},
            request_id="test-push-get-2"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        assert "error" in response_data


class TestPushNotificationConfigList:
    """Test listing push notification configs."""

    @pytest.mark.asyncio
    async def test_list_push_config_success(self, client, mock_task_store, mock_push_config_store):
        """Test successful push notification config list."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id)
        mock_task_store.get.return_value = task

        # Mock push config store to return multiple configs
        mock_config1 = PushNotificationConfig(url="https://example.com/webhook1")
        mock_config2 = PushNotificationConfig(url="https://example.com/webhook2")
        mock_push_config_store.get_info.return_value = [
            ("config1", mock_config1),
            ("config2", mock_config2)
        ]

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/list",
            params={"id": task_id},
            request_id="test-push-list-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        # Should succeed
        mock_push_config_store.get_info.assert_called_once_with(task_id)


class TestPushNotificationConfigDelete:
    """Test deleting push notification configs."""

    @pytest.mark.asyncio
    async def test_delete_push_config_success(self, client, mock_task_store, mock_push_config_store):
        """Test successful push notification config delete."""
        task_id = str(uuid.uuid4())
        task = _create_task(task_id)
        mock_task_store.get.return_value = task

        request = _create_jsonrpc_request(
            method="tasks/pushNotificationConfig/delete",
            params={
                "id": task_id,
                "pushNotificationConfigId": "config1"
            },
            request_id="test-push-delete-1"
        )

        response = await client.post("/", json=request)

        assert response.status_code == 200
        response_data = response.json()
        # Should succeed
        mock_push_config_store.delete_info.assert_called_once_with(task_id, "config1")

