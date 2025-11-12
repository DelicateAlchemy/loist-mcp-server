"""
Local task queue simulator for development.

Provides an in-memory task queue that simulates Cloud Tasks behavior
for local development without requiring GCP infrastructure.
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from queue import PriorityQueue
import heapq

logger = logging.getLogger(__name__)


@dataclass(order=True)
class LocalTask:
    """Represents a local task with priority and timing."""
    execute_at: float  # Unix timestamp for execution
    task_id: str
    payload: Dict[str, Any]
    target_url: str
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3

    def __post_init__(self):
        # Ensure task_id is unique
        if not self.task_id:
            self.task_id = str(uuid.uuid4())


class LocalTaskQueue:
    """
    In-memory task queue simulator.

    Mimics Cloud Tasks behavior for local development:
    - Asynchronous task execution
    - Retry logic with exponential backoff
    - Task deduplication
    - Statistics tracking
    """

    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self._queue: List[LocalTask] = []
        self._active_tasks: Dict[str, LocalTask] = {}
        self._completed_tasks: Dict[str, LocalTask] = {}
        self._failed_tasks: Dict[str, LocalTask] = {}
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "tasks_enqueued": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "avg_processing_time": 0.0,
            "total_processing_time": 0.0
        }

        # Worker management
        self._workers: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
        self._start_workers()

        logger.info(f"Local task queue initialized with {max_workers} workers")

    def _start_workers(self) -> None:
        """Start worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"LocalTaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)

    def _worker_loop(self) -> None:
        """Main worker loop that processes tasks."""
        while not self._shutdown_event.is_set():
            try:
                # Get next task to execute
                task = self._get_next_task()

                if task:
                    self._execute_task(task)
                else:
                    # No tasks available, wait a bit
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Worker error: {e}")

    def _get_next_task(self) -> Optional[LocalTask]:
        """Get the next task that should be executed."""
        with self._lock:
            current_time = time.time()

            # Find the first task that's ready to execute
            for i, task in enumerate(self._queue):
                if task.execute_at <= current_time:
                    # Remove from queue and mark as active
                    self._queue.pop(i)
                    self._active_tasks[task.task_id] = task
                    return task

            return None

    def _execute_task(self, task: LocalTask) -> None:
        """Execute a task asynchronously."""
        try:
            # Import here to avoid circular imports
            from src.tasks.local_handler import handle_local_task

            start_time = time.time()

            # Execute the task
            result = asyncio.run(handle_local_task(task.payload))

            processing_time = time.time() - start_time

            # Update statistics
            with self._lock:
                self._stats["tasks_completed"] += 1
                self._stats["total_processing_time"] += processing_time
                self._stats["avg_processing_time"] = (
                    self._stats["total_processing_time"] / self._stats["tasks_completed"]
                )

                # Mark task as completed
                del self._active_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task

            logger.info(
                f"Local task {task.task_id} completed successfully in {processing_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Local task {task.task_id} failed: {e}")

            with self._lock:
                self._stats["tasks_failed"] += 1

                # Handle retry logic
                task.attempts += 1
                if task.attempts < task.max_attempts:
                    # Schedule retry with exponential backoff
                    retry_delay = 2 ** task.attempts  # Exponential backoff
                    task.execute_at = time.time() + retry_delay
                    task.payload["_retry_attempt"] = task.attempts

                    # Re-queue the task
                    heapq.heappush(self._queue, task)
                    self._stats["tasks_retried"] += 1

                    logger.warning(
                        f"Local task {task.task_id} failed (attempt {task.attempts}/{task.max_attempts}), "
                        f"retrying in {retry_delay}s"
                    )
                else:
                    # Mark as permanently failed
                    del self._active_tasks[task.task_id]
                    self._failed_tasks[task.task_id] = task
                    logger.error(
                        f"Local task {task.task_id} permanently failed after {task.max_attempts} attempts"
                    )

    def enqueue_task(
        self,
        payload: Dict[str, Any],
        target_url: str = "http://localhost:8080/tasks/waveform",
        delay_seconds: int = 0
    ) -> str:
        """
        Enqueue a task for local execution.

        Args:
            payload: Task payload dictionary
            target_url: Target URL (for compatibility, not used in local mode)
            delay_seconds: Delay before execution

        Returns:
            Task ID string
        """
        execute_at = time.time() + delay_seconds

        task = LocalTask(
            execute_at=execute_at,
            task_id=str(uuid.uuid4()),
            payload=payload,
            target_url=target_url
        )

        with self._lock:
            heapq.heappush(self._queue, task)
            self._stats["tasks_enqueued"] += 1

        logger.info(
            f"Enqueued local task {task.task_id} for execution "
            f"{'immediately' if delay_seconds == 0 else f'in {delay_seconds}s'}"
        )

        return task.task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.

        Args:
            task_id: Task ID to check

        Returns:
            Task status dictionary or None if not found
        """
        with self._lock:
            if task_id in self._active_tasks:
                task = self._active_tasks[task_id]
                return {
                    "task_id": task_id,
                    "status": "running",
                    "created_at": task.created_at,
                    "attempts": task.attempts
                }
            elif task_id in self._completed_tasks:
                task = self._completed_tasks[task_id]
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "created_at": task.created_at,
                    "completed_at": task.execute_at,
                    "attempts": task.attempts
                }
            elif task_id in self._failed_tasks:
                task = self._failed_tasks[task_id]
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "created_at": task.created_at,
                    "failed_at": task.execute_at,
                    "attempts": task.attempts
                }

            # Check if it's still in queue
            for task in self._queue:
                if task.task_id == task_id:
                    return {
                        "task_id": task_id,
                        "status": "queued",
                        "created_at": task.created_at,
                        "execute_at": task.execute_at
                    }

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                **self._stats,
                "queue_size": len(self._queue),
                "active_tasks": len(self._active_tasks),
                "completed_tasks": len(self._completed_tasks),
                "failed_tasks": len(self._failed_tasks)
            }

    def shutdown(self, timeout: float = 5.0) -> None:
        """Shutdown the task queue gracefully."""
        logger.info("Shutting down local task queue...")

        self._shutdown_event.set()

        # Wait for workers to finish
        for worker in self._workers:
            worker.join(timeout=timeout)

        logger.info("Local task queue shutdown complete")


# Global queue instance
_local_queue: Optional[LocalTaskQueue] = None
_queue_lock = threading.Lock()


def get_local_queue(max_workers: int = 2) -> LocalTaskQueue:
    """
    Get or create the global local task queue instance.

    Args:
        max_workers: Maximum number of worker threads

    Returns:
        LocalTaskQueue instance
    """
    global _local_queue

    with _queue_lock:
        if _local_queue is None:
            _local_queue = LocalTaskQueue(max_workers=max_workers)

        return _local_queue


def enqueue_local_task(
    payload: Dict[str, Any],
    target_url: str = "http://localhost:8080/tasks/waveform",
    delay_seconds: int = 0
) -> str:
    """
    Convenience function to enqueue a task in the local queue.

    Args:
        payload: Task payload
        target_url: Target URL (for compatibility)
        delay_seconds: Delay before execution

    Returns:
        Task ID
    """
    queue = get_local_queue()
    return queue.enqueue_task(payload, target_url, delay_seconds)


def get_local_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a local task.

    Args:
        task_id: Task ID

    Returns:
        Task status or None
    """
    queue = get_local_queue()
    return queue.get_task_status(task_id)


def shutdown_local_queue() -> None:
    """Shutdown the local task queue."""
    global _local_queue

    with _queue_lock:
        if _local_queue:
            _local_queue.shutdown()
            _local_queue = None
