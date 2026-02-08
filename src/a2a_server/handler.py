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
from collections.abc import AsyncGenerator

from a2a.server.request_handlers import RequestHandler
from a2a.server.context import ServerCallContext
from a2a.server.events.event_queue import Event
from a2a.types import (
    MessageSendParams,
    TaskQueryParams,
    Task,
    Message,
    TaskState,
    TaskStatus,
    TaskIdParams,
    TaskPushNotificationConfig,
    GetTaskPushNotificationConfigParams,
    ListTaskPushNotificationConfigParams,
    DeleteTaskPushNotificationConfigParams,
    UnsupportedOperationError,
    TaskNotFoundError,
    TaskNotCancelableError,
    TaskStatusUpdateEvent,
)
from a2a.utils.errors import ServerError

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
        push_config_store=None,
        exception_handler: Optional[ExceptionHandler] = None
    ):
        """
        Initialize the request handler.

        Args:
            task_store: DatabaseTaskStore instance for task persistence
            push_config_store: Optional PushConfigStore instance for push notifications
            exception_handler: Exception handler for consistent error handling
        
        Note: Audio processing is now handled by shared business logic
        (src/business/audio_processor.py) instead of an injected processor.
        """
        self.task_store = task_store
        self.push_config_store = push_config_store

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
        context: ServerCallContext | None = None
    ) -> Task | Message:
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
                
                # Mark task as completed and store results in metadata
                task.status = TaskStatus(state=TaskState.completed)
                # Store audio processing results in task metadata (SDK-compliant approach)
                task.metadata = {
                    "audio_track_id": result.audio_id,
                    "processing_result": result.model_dump() if hasattr(result, 'model_dump') else result
                }
                logger.info(f"✅ Audio processing completed for task {task.id}, audio_id: {result.audio_id}")
                
            except SharedAudioProcessingError as e:
                # Handle shared processing errors
                logger.error(f"❌ Audio processing failed for task {task.id}: {e.message}")
                task.status = TaskStatus(state=TaskState.failed)
                task.metadata = {"error": e.to_dict() if hasattr(e, 'to_dict') else {"message": str(e)}}

            except Exception as e:
                # Handle unexpected errors
                logger.exception(f"❌ Unexpected error processing task {task.id}: {e}")
                task.status = TaskStatus(state=TaskState.failed)
                task.metadata = {"error": {"message": str(e), "type": type(e).__name__}}

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
        context: ServerCallContext | None = None
    ) -> Optional[Task]:
        """
        Handle tasks/get JSON-RPC requests.

        Retrieves task status and results by task ID.

        Args:
            params: TaskQueryParams containing the task ID
            context: Server call context (optional)

        Returns:
            Task: Task object if found

        Raises:
            TaskNotFoundError: If task is not found
        """
        task_id = params.id
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
                return task
            else:
                logger.info(f"📋 Task {task_id} not found")
                # Raise TaskNotFoundError as expected by A2A SDK
                raise TaskNotFoundError()
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

    # Required abstract method implementations (Phase 2)
    async def on_cancel_task(
        self,
        params: TaskIdParams,
        context: ServerCallContext | None = None,
    ) -> Task | None:
        """
        Handle tasks/cancel JSON-RPC requests.
        
        Cancels a running task by marking it as canceled in the database.
        Note: This implementation marks the intent to cancel but cannot
        interrupt in-flight audio processing (no background task registry).
        
        Args:
            params: TaskIdParams containing the task ID
            context: Server call context (optional)
        
        Returns:
            Task: Updated task with canceled status, or None if not found
        
        Raises:
            ServerError: If task not found or cannot be canceled
        """
        task_id = params.id
        logger.info(f"🚫 Processing tasks/cancel request for task {task_id}")
        
        exc_context = ExceptionContext(
            operation="cancel_task",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            task = await self.task_store.get(task_id)
            if not task:
                logger.warning(f"⚠️ Task {task_id} not found for cancellation")
                raise ServerError(error=TaskNotFoundError())
            
            # Check if task is in a terminal state (cannot be canceled)
            if task.status.state in self._terminal_states:
                logger.warning(f"⚠️ Task {task_id} is in terminal state {task.status.state}, cannot cancel")
                raise ServerError(
                    error=TaskNotCancelableError(
                        message=f"Task cannot be canceled - current state: {task.status.state.value}"
                    )
                )
            
            # Mark task as canceled
            task.status = TaskStatus(state=TaskState.canceled)
            await self.task_store.save(task)
            logger.info(f"✅ Task {task_id} marked as canceled")
            
            return task
        
        except ServerError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to cancel task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    async def on_message_send_stream(
        self,
        params: MessageSendParams,
        context: ServerCallContext | None = None,
    ) -> AsyncGenerator[Event]:
        """
        Handle message/stream JSON-RPC requests (streaming).
        
        Sends a message and yields events as they occur during processing.
        This is a simplified implementation that yields status updates
        during the audio processing workflow.
        
        Args:
            params: MessageSendParams containing the message to process
            context: Server call context (optional)
        
        Yields:
            Event: Task status updates and final task result
        """
        logger.info("📡 Processing message/stream request")
        
        exc_context = ExceptionContext(
            operation="send_message_stream",
            component="a2a.handler",
            operation_type=OperationType.AUDIO_PROCESSING,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            # Extract audio URL from message
            audio_url = self._extract_audio_url(params.message)
            
            if not audio_url:
                raise ValueError("No audio URL found in message. Please provide a valid audio file URL.")
            
            # Create new task with submitted status
            task = await self._create_task_from_message(params, TaskState.submitted)
            logger.info(f"✅ Created task {task.id} for streaming audio URL: {audio_url}")
            
            # Save task with submitted status
            await self.task_store.save(task)
            
            # Yield submitted status event
            # Note: Event structure from SDK - simplified implementation
            # Event is expected to wrap TaskStatusUpdateEvent for streaming
            status_update = TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.submitted),
                final=False
            )
            # For now, yield the status update directly
            # TODO: Verify Event construction pattern during testing
            yield status_update  # type: ignore
            
            # Transition to working status
            task.status = TaskStatus(state=TaskState.working)
            await self.task_store.save(task)
            
            # Yield working status event
            status_update = TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False
            )
            yield status_update  # type: ignore
            
            # Process audio (existing logic)
            try:
                from src.business import (
                    process_audio_shared,
                    AudioProcessingRequest,
                    SharedAudioProcessingError,
                )
                
                shared_request = AudioProcessingRequest(
                    url=audio_url,
                    a2a_task_id=task.id
                )
                
                logger.info(f"🎵 Calling shared audio processing for task {task.id}")
                result = await process_audio_shared(shared_request)
                
                # Mark task as completed
                task.status = TaskStatus(state=TaskState.completed)
                task.metadata = {
                    "audio_track_id": result.audio_id,
                    "processing_result": result.model_dump() if hasattr(result, 'model_dump') else result
                }
                logger.info(f"✅ Audio processing completed for task {task.id}")
                
            except SharedAudioProcessingError as e:
                logger.error(f"❌ Audio processing failed for task {task.id}: {e.message}")
                task.status = TaskStatus(state=TaskState.failed)
                task.metadata = {"error": e.to_dict() if hasattr(e, 'to_dict') else {"message": str(e)}}
            
            except Exception as e:
                logger.exception(f"❌ Unexpected error processing task {task.id}: {e}")
                task.status = TaskStatus(state=TaskState.failed, message=f"Unexpected error: {str(e)}")
                task.metadata = {"error": {"message": str(e), "type": type(e).__name__}}
            
            # Save final task state
            await self.task_store.save(task)
            
            # Yield final status update with final=True
            final_status_update = TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=task.status,
                final=True
            )
            yield final_status_update
            
            # Yield final task result
            # TODO: Verify Event construction pattern during testing
            yield task  # type: ignore
        
        except Exception as e:
            logger.error(f"❌ Failed to send streaming message: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    async def on_resubscribe_to_task(
        self,
        params: TaskIdParams,
        context: ServerCallContext | None = None,
    ) -> AsyncGenerator[Event]:
        """
        Handle tasks/resubscribe JSON-RPC requests.
        
        Allows a client to resubscribe to a running task's event stream.
        This implementation returns UnsupportedOperationError as it requires
        EventQueue infrastructure that is not yet implemented.
        
        Args:
            params: TaskIdParams containing the task ID
            context: Server call context (optional)
        
        Yields:
            Event: Task updates (not implemented)
        
        Raises:
            ServerError: UnsupportedOperationError (not yet implemented)
        """
        logger.info(f"🔄 Processing tasks/resubscribe request for task {params.id}")
        raise ServerError(error=UnsupportedOperationError())

    async def on_set_task_push_notification_config(
        self,
        params: TaskPushNotificationConfig,
        context: ServerCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        """
        Handle tasks/pushNotificationConfig/set JSON-RPC requests.
        
        Sets or updates push notification configuration for a task.
        
        Args:
            params: TaskPushNotificationConfig containing task_id and config
            context: Server call context (optional)
        
        Returns:
            TaskPushNotificationConfig: The provided configuration
        
        Raises:
            ServerError: If push notifications not supported or task not found
        """
        task_id = params.task_id
        logger.info(f"📬 Processing push notification config set for task {task_id}")
        
        if not self.push_config_store:
            raise ServerError(error=UnsupportedOperationError())
        
        exc_context = ExceptionContext(
            operation="set_push_notification_config",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            # Validate task exists
            task = await self.task_store.get(task_id)
            if not task:
                raise ServerError(error=TaskNotFoundError())
            
            # Store push notification config
            await self.push_config_store.set_info(
                task_id,
                params.push_notification_config
            )
            
            logger.info(f"✅ Push notification config set for task {task_id}")
            return params
        
        except ServerError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to set push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    async def on_get_task_push_notification_config(
        self,
        params: TaskIdParams | GetTaskPushNotificationConfigParams,
        context: ServerCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        """
        Handle tasks/pushNotificationConfig/get JSON-RPC requests.
        
        Retrieves push notification configuration for a task.
        
        Args:
            params: TaskIdParams or GetTaskPushNotificationConfigParams
            context: Server call context (optional)
        
        Returns:
            TaskPushNotificationConfig: The configuration for the task
        
        Raises:
            ServerError: If push notifications not supported, task not found, or config not found
        """
        task_id = params.id
        logger.info(f"📬 Processing push notification config get for task {task_id}")
        
        if not self.push_config_store:
            raise ServerError(error=UnsupportedOperationError())
        
        exc_context = ExceptionContext(
            operation="get_push_notification_config",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            # Validate task exists
            task = await self.task_store.get(task_id)
            if not task:
                raise ServerError(error=TaskNotFoundError())
            
            # Get push notification configs
            configs = await self.push_config_store.get_info(task_id)
            
            if not configs or not configs[0]:
                raise ServerError(
                    error=TaskNotFoundError(
                        message="Push notification config not found"
                    )
                )
            
            # Return first config (or specific one if config_id provided)
            config_id, push_config = configs[0]
            
            # If params has config_id, find matching config
            if hasattr(params, 'config_id') and params.config_id:
                matching = next((c for cid, c in configs if cid == params.config_id), None)
                if matching:
                    config_id, push_config = params.config_id, matching
            
            return TaskPushNotificationConfig(
                task_id=task_id,
                push_notification_config=push_config
            )
        
        except ServerError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to get push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    async def on_list_task_push_notification_config(
        self,
        params: ListTaskPushNotificationConfigParams,
        context: ServerCallContext | None = None,
    ) -> list[TaskPushNotificationConfig]:
        """
        Handle tasks/pushNotificationConfig/list JSON-RPC requests.
        
        Lists all push notification configurations for a task.
        
        Args:
            params: ListTaskPushNotificationConfigParams containing task_id
            context: Server call context (optional)
        
        Returns:
            list[TaskPushNotificationConfig]: List of configurations for the task
        
        Raises:
            ServerError: If push notifications not supported or task not found
        """
        task_id = params.id
        logger.info(f"📬 Processing push notification config list for task {task_id}")
        
        if not self.push_config_store:
            raise ServerError(error=UnsupportedOperationError())
        
        exc_context = ExceptionContext(
            operation="list_push_notification_config",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            # Validate task exists
            task = await self.task_store.get(task_id)
            if not task:
                raise ServerError(error=TaskNotFoundError())
            
            # Get all push notification configs
            configs = await self.push_config_store.get_info(task_id)
            
            # Convert to TaskPushNotificationConfig list
            result = [
                TaskPushNotificationConfig(
                    task_id=task_id,
                    push_notification_config=push_config
                )
                for config_id, push_config in configs
            ]
            
            logger.info(f"✅ Retrieved {len(result)} push notification config(s) for task {task_id}")
            return result
        
        except ServerError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to list push notification configs for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

    async def on_delete_task_push_notification_config(
        self,
        params: DeleteTaskPushNotificationConfigParams,
        context: ServerCallContext | None = None,
    ) -> None:
        """
        Handle tasks/pushNotificationConfig/delete JSON-RPC requests.
        
        Deletes a push notification configuration for a task.
        
        Args:
            params: DeleteTaskPushNotificationConfigParams containing task_id and config_id
            context: Server call context (optional)
        
        Raises:
            ServerError: If push notifications not supported or task not found
        """
        task_id = params.id
        config_id = getattr(params, 'push_notification_config_id', None)
        logger.info(f"📬 Processing push notification config delete for task {task_id}, config_id {config_id}")
        
        if not self.push_config_store:
            raise ServerError(error=UnsupportedOperationError())
        
        exc_context = ExceptionContext(
            operation="delete_push_notification_config",
            component="a2a.handler",
            operation_type=OperationType.DATABASE_QUERY,
            request_id=getattr(context, 'request_id', None) if context else None,
        )
        
        try:
            # Validate task exists
            task = await self.task_store.get(task_id)
            if not task:
                raise ServerError(error=TaskNotFoundError())
            
            # Delete push notification config
            await self.push_config_store.delete_info(task_id, config_id)
            
            logger.info(f"✅ Push notification config deleted for task {task_id}")
        
        except ServerError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to delete push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)

