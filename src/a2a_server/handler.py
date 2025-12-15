"""
A2A Request Handler for Loist Music Library

Implements the A2A SDK RequestHandler interface to provide audio processing
capabilities via JSON-RPC endpoints.

Author: Task Master AI
Created: $(date)
"""

import logging
import uuid
from typing import Optional, Protocol

from a2a.server.request_handlers import RequestHandler
from a2a.types import (
    MessageSendParams,
    TaskQueryParams,
    Task,
    Message,
    TaskState,
    TaskStatus,
)

# Import exception framework
from src.exceptions.handler import ExceptionHandler
from src.exceptions.config import ExceptionConfig
from src.exceptions.context import ExceptionContext, OperationType

logger = logging.getLogger(__name__)


# Audio processing is now handled by the shared business logic layer
# (src/business/audio_processor.py) instead of a protocol.
# The handler imports and calls process_audio_shared() directly.


class LoistRequestHandler(RequestHandler):
    """
    A2A Request Handler for Loist Music Library audio processing.

    Handles JSON-RPC requests for audio processing tasks via the A2A SDK.
    Implements the RequestHandler interface to integrate with A2AFastAPIApplication.

    Task Linking Design:
    - Bidirectional linking between A2A tasks and audio_tracks:
      1. audio_tracks.a2a_task_id: Links audio track to A2A task (database column)
      2. task.metadata['audio_track_id']: Links A2A task to audio track (JSON field)
    - No foreign key constraint: a2a_tasks table is SDK-managed, so we enforce
      referential integrity at the application level (UUID validation).
    - Status transitions: submitted → working → completed/failed, with explicit
      saves at each step for task polling support.
    """

    def __init__(
        self,
        task_store,
        exception_handler: Optional[ExceptionHandler] = None
    ):
        """
        Initialize the request handler.

        Args:
            task_store: DatabaseTaskStore instance for task persistence
            exception_handler: Exception handler for consistent error handling
        
        Note: Audio processing is now handled by shared business logic
        (src/business/audio_processor.py) instead of an injected processor.
        """
        self.task_store = task_store

        # Initialize exception handler
        self.exception_handler = exception_handler or ExceptionHandler(
            ExceptionConfig().for_development()  # Use dev config for now
        )

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
            Exception: If task creation or processing fails
        """
        logger.info("📨 Processing tasks/send request")

        # Create exception context for this operation
        exc_context = ExceptionContext(
            operation="send_message",
            component="a2a.handler",
            operation_type=OperationType.AUDIO_PROCESSING,
            request_id=getattr(context, 'request_id', None) if context else None,
        )

        try:
            # Extract audio URL from message (placeholder - will be implemented in T6)
            audio_url = self._extract_audio_url(params.message)

            if not audio_url:
                raise ValueError("No audio URL found in message. Please provide a valid audio file URL.")

            # Create new task with submitted status
            task = await self._create_task_from_message(params, TaskState.submitted)
            logger.info(f"✅ Created task {task.id} for audio URL: {audio_url}")

            # Save task immediately with submitted status
            try:
                await self.task_store.save(task)
                logger.info(f"💾 Task {task.id} saved with submitted status")
            except Exception as e:
                logger.error(f"❌ Failed to save task {task.id} with submitted status: {e}")
                raise  # Re-raise since we can't proceed without task creation

            # Transition to working status before processing
            task.status = TaskStatus(state=TaskState.working)
            try:
                await self.task_store.save(task)
                logger.info(f"🔄 Task {task.id} transitioned to working status")
            except Exception as e:
                logger.error(f"❌ Failed to save task {task.id} with working status: {e}")
                # Log but continue - processing can proceed even if status save fails
                # The final save will attempt to update the status again

            # Call shared business logic for audio processing
            try:
                # Import shared business logic
                from src.business import (
                    process_audio_shared,
                    AudioProcessingRequest,
                    SharedAudioProcessingError,
                )
                
                # Create shared request (using defaults for options)
                shared_request = AudioProcessingRequest(
                    url=audio_url,
                    # Use default options (max_size_mb=100, timeout=300, etc.)
                    a2a_task_id=task.id
                )
                
                logger.info(f"🎵 Calling shared audio processing for task {task.id}")
                result = await process_audio_shared(shared_request)
                
                # Mark task as completed with result artifact
                task.status = TaskStatus(state=TaskState.completed)
                task.artifacts = [self._create_success_artifact(result)]
                # Store bidirectional link: audio_track_id in task metadata
                task.metadata = {"audio_track_id": result.audio_id}
                logger.info(f"✅ Audio processing completed for task {task.id}, audio_id: {result.audio_id}")
                
            except SharedAudioProcessingError as e:
                # Handle shared processing errors
                logger.error(f"❌ Audio processing failed for task {task.id}: {e.message}")
                task.status = TaskStatus(state=TaskState.failed, message=e.message)
                task.artifacts = [self._create_error_artifact(e)]
                
            except Exception as e:
                # Handle unexpected errors
                logger.exception(f"❌ Unexpected error processing task {task.id}: {e}")
                task.status = TaskStatus(state=TaskState.failed, message=f"Unexpected error: {str(e)}")
                task.artifacts = [self._create_error_artifact(e)]

            # Save final task state with artifacts
            try:
                await self.task_store.save(task)
                logger.info(f"💾 Task {task.id} saved to database with final status: {task.status.state}")
            except Exception as e:
                logger.error(f"❌ Failed to save final task state for {task.id}: {e}")
                # Log error but don't fail the request - processing completed successfully
                # The task state may be inconsistent, but the audio track is saved
                # Consider implementing a retry mechanism or background job to sync task states

            return task

        except Exception as e:
            # Use exception framework for consistent error handling
            logger.error(f"❌ Failed to send message: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

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

        # Create exception context for this operation
        exc_context = ExceptionContext(
            operation="get_task",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )

        try:
            task = await self.task_store.get(task_id)
            if task:
                logger.info(f"✅ Found task {task_id} with status {task.status.state}")
            else:
                logger.warning(f"⚠️ Task {task_id} not found")
            return task
        except Exception as e:
            logger.error(f"❌ Failed to retrieve task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    def _extract_audio_url(self, message: Message) -> Optional[str]:
        """
        Extract audio URL from message content using message parser utilities.

        Args:
            message: A2A Message object

        Returns:
            str or None: Audio URL if found and valid, None otherwise

        Raises:
            ValueError: If URL is found but invalid/blocked
        """
        # Import message parser utilities
        from .message_parser import extract_audio_url, validate_audio_url

        # Extract URL from message
        audio_url = extract_audio_url(message)

        if audio_url:
            # Validate the extracted URL for security (raises ValueError if invalid)
            validate_audio_url(audio_url)
            logger.info(f"✅ Valid audio URL extracted: {audio_url}")
            return audio_url

        logger.debug("🔍 No audio URL found in message")
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
        # Generate UUID for task ID since it's required
        task = Task(
            id=str(uuid.uuid4()),
            context_id=params.message.id if hasattr(params.message, 'id') else "unknown",
            kind="task",
            status=TaskStatus(state=initial_state),
            artifacts=[],
            history=[params.message],  # Store the original message in history
            metadata={}  # Can be used for audio track linking later
        )

        return task

    # Required abstract method implementations (MVP stubs)
    async def on_cancel_task(self, task_id: str) -> None:
        """Cancel a task. MVP implementation - mark as canceled."""
        raise NotImplementedError("Task cancellation not implemented in MVP")

    async def on_delete_task_push_notification_config(self, task_id: str, config_id: str) -> None:
        """Delete push notification config for a task. MVP implementation."""
        raise NotImplementedError("Push notifications not implemented in MVP")

    async def on_get_task_push_notification_config(self, task_id: str, config_id: str) -> dict:
        """Get push notification config for a task. MVP implementation."""
        raise NotImplementedError("Push notifications not implemented in MVP")

    async def on_list_task_push_notification_config(self, task_id: str) -> list:
        """List push notification configs for a task. MVP implementation."""
        raise NotImplementedError("Push notifications not implemented in MVP")

    async def on_message_send_stream(self, params: MessageSendParams) -> None:
        """Send message with streaming. MVP implementation."""
        raise NotImplementedError("Message streaming not implemented in MVP")

    async def on_resubscribe_to_task(self, task_id: str) -> None:
        """Resubscribe to task updates. MVP implementation."""
        raise NotImplementedError("Task resubscription not implemented in MVP")

    async def on_set_task_push_notification_config(self, task_id: str, config: dict) -> str:
        """Set push notification config for a task. MVP implementation."""
        raise NotImplementedError("Push notifications not implemented in MVP")

    def _create_success_artifact(self, result) -> dict:
        """Create success artifact from processing result."""
        return {
            "type": "audio_processing_result",
            "audio_id": result.audio_id,
            "metadata": result.metadata.model_dump() if hasattr(result.metadata, 'model_dump') else result.metadata,
            "resources": result.resources.model_dump() if hasattr(result.resources, 'model_dump') else result.resources,
            "processing_time": result.processing_time
        }

    def _create_error_artifact(self, error: Exception) -> dict:
        """Create error artifact from exception."""
        if hasattr(error, 'to_dict'):
            return {"type": "audio_processing_error", **error.to_dict()}
        return {
            "type": "audio_processing_error",
            "message": str(error),
            "error_type": type(error).__name__
        }
