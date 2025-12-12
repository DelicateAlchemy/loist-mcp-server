"""
A2A Request Handler for Loist Music Library

Implements the A2A SDK RequestHandler interface to provide audio processing
capabilities via JSON-RPC endpoints.

Author: Task Master AI
Created: $(date)
"""

import logging
from typing import Optional

from a2a.server.request_handlers import RequestHandler
from a2a.types import (
    MessageSendParams,
    TaskQueryParams,
    Task,
    Message,
    TaskState,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class LoistRequestHandler(RequestHandler):
    """
    A2A Request Handler for Loist Music Library audio processing.

    Handles JSON-RPC requests for audio processing tasks via the A2A SDK.
    Implements the RequestHandler interface to integrate with A2AFastAPIApplication.
    """

    def __init__(self, task_store, audio_processor=None):
        """
        Initialize the request handler.

        Args:
            task_store: DatabaseTaskStore instance for task persistence
            audio_processor: Audio processing service (will be implemented in T5)
        """
        self.task_store = task_store
        self.audio_processor = audio_processor

        # Terminal states - tasks in these states cannot be modified
        self._terminal_states = {
            TaskState.completed,
            TaskState.canceled,
            TaskState.failed,
            TaskState.rejected
        }

        logger.info("🔧 LoistRequestHandler initialized")

    async def on_message_send(
        self,
        params: MessageSendParams,
        context=None
    ) -> Task:
        """
        Handle tasks/send JSON-RPC requests.

        Creates a new audio processing task from the message content.

        Args:
            params: MessageSendParams containing the message to process
            context: Server call context (optional)

        Returns:
            Task: Created task object with processing status

        Raises:
            ValueError: If message doesn't contain a valid audio URL
        """
        logger.info("📨 Processing tasks/send request")

        # Extract audio URL from message (placeholder - will be implemented in T6)
        audio_url = self._extract_audio_url(params.message)

        if not audio_url:
            raise ValueError("No audio URL found in message. Please provide a valid audio file URL.")

        # Create new task with working status
        task = await self._create_task_from_message(params, TaskState.working)
        logger.info(f"✅ Created task {task.id} for audio URL: {audio_url}")

        # TODO: Implement actual audio processing in T7
        # For now, create a placeholder task that will be processed later
        if self.audio_processor:
            try:
                # This will be implemented when we have the shared business logic (T5)
                logger.warning("⚠️ Audio processor available but processing logic not yet implemented")
            except Exception as e:
                logger.error(f"❌ Audio processing failed: {e}")
                task.status = TaskStatus(state=TaskState.failed, message=str(e))

        # Save task to database
        await self.task_store.save(task)
        logger.info(f"💾 Task {task.id} saved to database")

        return task

    async def on_get_task(
        self,
        params: TaskQueryParams,
        context=None
    ) -> Optional[Task]:
        """
        Handle tasks/get JSON-RPC requests.

        Retrieves task status and results by task ID.

        Args:
            params: TaskQueryParams containing the task ID
            context: Server call context (optional)

        Returns:
            Task or None: Task object if found, None otherwise
        """
        task_id = params.task_id
        logger.info(f"📋 Processing tasks/get request for task {task_id}")

        try:
            task = await self.task_store.get(task_id)
            if task:
                logger.info(f"✅ Found task {task_id} with status {task.status.state}")
            else:
                logger.warning(f"⚠️ Task {task_id} not found")
            return task
        except Exception as e:
            logger.error(f"❌ Failed to retrieve task {task_id}: {e}")
            raise

    def _extract_audio_url(self, message: Message) -> Optional[str]:
        """
        Extract audio URL from message content.

        This is a placeholder implementation. The full message parsing
        will be implemented in Task 6.

        Args:
            message: A2A Message object

        Returns:
            str or None: Audio URL if found, None otherwise
        """
        # Placeholder implementation - will be replaced in T6
        # For now, just return None to indicate no URL found
        logger.debug("🔍 Audio URL extraction not yet implemented (Task 6)")
        return None

    async def _create_task_from_message(
        self,
        params: MessageSendParams,
        initial_state: TaskState
    ) -> Task:
        """
        Create a new task from message send parameters.

        Args:
            params: MessageSendParams from the request
            initial_state: Initial task state

        Returns:
            Task: Newly created task object
        """
        # Create task using SDK's Task constructor
        # The SDK will generate the ID and set up the basic structure
        task = Task(
            context_id=params.message.id if hasattr(params.message, 'id') else "unknown",
            kind="task",
            status=TaskStatus(state=initial_state),
            artifacts=[],
            history=[params.message],  # Store the original message in history
            metadata={}  # Can be used for audio track linking later
        )

        return task
