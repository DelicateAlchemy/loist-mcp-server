"""
Local task handler for development.

Provides local execution of tasks that would normally be handled by
Cloud Tasks HTTP endpoints, allowing for easier debugging and testing.
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def handle_local_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a task locally (equivalent to Cloud Tasks HTTP handler).

    This function mimics the behavior of the HTTP task handlers but runs
    directly in the local process for easier debugging.

    Args:
        payload: Task payload dictionary

    Returns:
        Task execution result
    """
    try:
        task_type = payload.get("type")

        if task_type == "waveform":
            return await _handle_local_waveform_task(payload)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    except Exception as e:
        logger.error(f"Local task execution failed: {e}")
        raise


async def _handle_local_waveform_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a waveform generation task locally.

    This is equivalent to the HTTP handler but runs in-process.
    """
    from src.tasks.handler import handle_waveform_task

    logger.info("Executing waveform task locally")

    # Extract retry attempt info if present
    retry_attempt = payload.pop("_retry_attempt", 0)
    if retry_attempt > 0:
        logger.info(f"Local task retry attempt: {retry_attempt}")

    try:
        # Execute the waveform task
        result = await handle_waveform_task(payload)

        logger.info(f"Local waveform task completed: {result.get('status', 'unknown')}")
        return result

    except Exception as e:
        logger.error(f"Local waveform task failed: {e}")
        raise
