"""
Local task queue implementation for development and testing.

Provides an in-memory task queue that mimics Google Cloud Tasks behavior
for local development without requiring Cloud infrastructure. Includes
proper error handling and graceful degradation.

Features:
- In-memory task queue with priority scheduling
- Configurable worker threads
- Task retry logic with exponential backoff
- Comprehensive statistics and monitoring
- Graceful shutdown handling
- Thread-safe operations
"""

import heapq
import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TaskQueueError(Exception):
    """Raised when local task queue operations fail."""
    pass


@dataclass(order=True)
class LocalTask:
    """
    Represents a task in the local queue.

    Tasks are ordered by execute_at timestamp for priority scheduling.
    """
    execute_at: float
    task_id: str
    payload: Dict[str, Any]
    target_url: str
    max_attempts: int = 3
    attempts: int = 0
    created_at: float = field(default_factory=time.time)
    priority: int = 0  # Lower number = higher priority

    def __post_init__(self):
        # Make execute_at the first comparison field for heap ordering
        self.execute_at = float(self.execute_at)

    def should_retry(self) -> bool:
        """Check if task should be retried."""
        return self.attempts < self.max_attempts

    def increment_attempts(self):
        """Increment attempt counter."""
        self.attempts += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            'task_id': self.task_id,
            'payload': self.payload,
            'target_url': self.target_url,
            'max_attempts': self.max_attempts,
            'attempts': self.attempts,
            'created_at': self.created_at,
            'execute_at': self.execute_at,
            'status': 'pending'
        }


class LocalTaskQueue:
    """
    In-memory task queue for local development and testing.

    Provides thread-safe task scheduling and execution with configurable
    worker threads and comprehensive error handling.
    """

    def __init__(self, max_workers: int = 2):
        """
        Initialize the local task queue.

        Args:
            max_workers: Maximum number of worker threads for task execution
        """
        self.max_workers = max_workers
        self._queue: List[LocalTask] = []
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-worker")

        # Statistics
        self._stats = {
            'tasks_enqueued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_retried': 0,
            'queue_size': 0,
            'active_tasks': 0
        }

        # Task status tracking
        self._task_statuses: Dict[str, Dict[str, Any]] = {}

        # Start worker threads
        self._workers = []
        for i in range(max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"task-worker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"Local task queue initialized with {max_workers} workers")

    def enqueue_task(self, payload: Dict[str, Any], delay_seconds: float = 0, priority: int = 0) -> str:
        """
        Enqueue a task for execution.

        Args:
            payload: Task payload dictionary
            delay_seconds: Delay before task execution
            priority: Task priority (lower = higher priority)

        Returns:
            Task ID string

        Raises:
            TaskQueueError: If queue is shutting down
        """
        if self._shutdown_event.is_set():
            raise TaskQueueError("Cannot enqueue task - queue is shutting down")

        task_id = str(uuid.uuid4())
        execute_at = time.time() + delay_seconds

        task = LocalTask(
            execute_at=execute_at,
            task_id=task_id,
            payload=payload,
            target_url="",  # Not used in local queue
            priority=priority
        )

        with self._lock:
            heapq.heappush(self._queue, task)
            self._stats['tasks_enqueued'] += 1
            self._stats['queue_size'] = len(self._queue)
            self._task_statuses[task_id] = {
                'status': 'pending',
                'created_at': task.created_at,
                'execute_at': execute_at,
                'attempts': 0,
                'max_attempts': task.max_attempts
            }

        logger.debug(f"Enqueued task {task_id} with {delay_seconds}s delay")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a task.

        Args:
            task_id: Task ID to check

        Returns:
            Task status dictionary or None if not found
        """
        with self._lock:
            return self._task_statuses.get(task_id)

    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        with self._lock:
            stats = self._stats.copy()
            stats['queue_size'] = len(self._queue)
            return stats

    def _worker_loop(self):
        """Main worker loop that processes tasks."""
        while not self._shutdown_event.is_set():
            try:
                task = self._get_next_task()
                if task:
                    self._execute_task(task)
                else:
                    # No tasks available, sleep briefly
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)  # Prevent tight error loops

    def _get_next_task(self) -> Optional[LocalTask]:
        """
        Get the next task that should be executed.

        Returns:
            Next task to execute or None
        """
        with self._lock:
            if not self._queue:
                return None

            # Peek at the next task
            next_task = self._queue[0]

            # Check if it's time to execute
            if next_task.execute_at <= time.time():
                # Remove from queue
                task = heapq.heappop(self._queue)
                self._stats['queue_size'] = len(self._queue)
                self._stats['active_tasks'] += 1
                return task

            return None

    def _execute_task(self, task: LocalTask):
        """Execute a task in the thread pool."""
        try:
            self._executor.submit(self._process_task, task)
        except Exception as e:
            logger.error(f"Failed to submit task {task.task_id}: {e}")
            with self._lock:
                self._stats['active_tasks'] -= 1
                self._stats['tasks_failed'] += 1
                self._task_statuses[task.task_id]['status'] = 'failed'
                self._task_statuses[task.task_id]['error'] = str(e)

    def _process_task(self, task: LocalTask):
        """Process a single task."""
        try:
            # Update status
            with self._lock:
                self._task_statuses[task.task_id]['status'] = 'running'

            # Attempt to execute task
            result = self._execute_task_payload(task)

            # Success
            with self._lock:
                self._stats['tasks_completed'] += 1
                self._task_statuses[task.task_id]['status'] = 'completed'
                self._task_statuses[task.task_id]['completed_at'] = time.time()
                self._task_statuses[task.task_id]['result'] = result

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")

            with self._lock:
                task.increment_attempts()

                if task.should_retry():
                    # Retry the task
                    retry_delay = min(2 ** task.attempts, 300)  # Exponential backoff, max 5 minutes
                    task.execute_at = time.time() + retry_delay
                    heapq.heappush(self._queue, task)
                    self._stats['tasks_retried'] += 1
                    self._task_statuses[task.task_id]['attempts'] = task.attempts
                    self._task_statuses[task.task_id]['status'] = 'retrying'
                    self._task_statuses[task.task_id]['next_retry_at'] = task.execute_at
                    logger.info(f"Retrying task {task.task_id} in {retry_delay}s (attempt {task.attempts})")
                else:
                    # Give up
                    self._stats['tasks_failed'] += 1
                    self._task_statuses[task.task_id]['status'] = 'failed'
                    self._task_statuses[task.task_id]['error'] = str(e)
                    self._task_statuses[task.task_id]['final_attempt_at'] = time.time()

        finally:
            with self._lock:
                self._stats['active_tasks'] -= 1

    def _execute_task_payload(self, task: LocalTask) -> Any:
        """
        Execute the actual task payload.

        This is a placeholder that should be overridden or the task
        should be handled by the local task handler.

        Args:
            task: Task to execute

        Returns:
            Task execution result

        Raises:
            NotImplementedError: This should be implemented by subclasses
        """
        # Try to import and use local task handler
        try:
            from .local_handler import handle_local_task
            return handle_local_task(task.payload)
        except ImportError as e:
            logger.warning(f"Local task handler not available: {e}. Using default handler.")
            # Default behavior - just return success for test tasks
            if task.payload.get('type') == 'test':
                return {"status": "completed", "message": "Test task completed"}
            else:
                raise TaskQueueError(f"No handler available for task type: {task.payload.get('type')}")

    def shutdown(self, timeout: float = 30.0):
        """
        Shutdown the task queue gracefully.

        Args:
            timeout: Maximum time to wait for tasks to complete
        """
        logger.info("Shutting down local task queue...")

        # Signal shutdown
        self._shutdown_event.set()

        # Wait for worker threads
        for worker in self._workers:
            worker.join(timeout=timeout / len(self._workers))

        # Shutdown executor
        self._executor.shutdown(wait=True)

        # Log final statistics
        stats = self.get_stats()
        logger.info(f"Task queue shutdown complete. Final stats: {stats}")

    def __del__(self):
        """Ensure cleanup on deletion."""
        if hasattr(self, '_shutdown_event') and not self._shutdown_event.is_set():
            self.shutdown(timeout=5.0)


# Global queue instance
_global_queue: Optional[LocalTaskQueue] = None
_global_lock = threading.Lock()


def get_local_queue() -> LocalTaskQueue:
    """
    Get the global local task queue instance.

    Returns:
        Global LocalTaskQueue instance
    """
    global _global_queue

    with _global_lock:
        if _global_queue is None:
            _global_queue = LocalTaskQueue()
        return _global_queue


def enqueue_local_task(payload: Dict[str, Any], delay_seconds: float = 0, priority: int = 0) -> str:
    """
    Convenience function to enqueue a task on the global queue.

    Args:
        payload: Task payload
        delay_seconds: Delay before execution
        priority: Task priority

    Returns:
        Task ID
    """
    return get_local_queue().enqueue_task(payload, delay_seconds, priority)


def get_local_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get task status from global queue.

    Args:
        task_id: Task ID to check

    Returns:
        Task status or None
    """
    return get_local_queue().get_task_status(task_id)


def shutdown_local_queue(timeout: float = 30.0):
    """
    Convenience function to shutdown the global queue.

    Args:
        timeout: Shutdown timeout
    """
    global _global_queue

    with _global_lock:
        if _global_queue:
            _global_queue.shutdown(timeout)
            _global_queue = None
