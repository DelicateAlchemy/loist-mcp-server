"""
A2A FastAPI Application Configuration

Configures the A2A SDK's A2AFastAPIApplication with Loist-specific
Agent Card and request handler for audio processing tasks.

Author: Task Master AI
Created: $(date)
"""

import logging
from typing import Optional

from fastapi import FastAPI

from a2a.server.apps import A2AFastAPIApplication
from .agent_card import create_agent_card
from .handler import LoistRequestHandler
from .storage import get_task_store

logger = logging.getLogger(__name__)


async def create_a2a_app(database_url: Optional[str] = None) -> FastAPI:
    """
    Create and configure the A2A FastAPI application.

    Sets up the A2A SDK's FastAPI application with:
    - Agent Card serving at /.well-known/agent-card.json
    - JSON-RPC endpoints for task operations
    - LoistRequestHandler for audio processing logic

    Args:
        database_url: Optional database URL override (uses env var if not provided)

    Returns:
        FastAPI: Configured FastAPI application

    Raises:
        ValueError: If database URL is invalid or missing
        Exception: If application creation fails
    """
    logger.info("🚀 Creating A2A FastAPI application")

    try:
        # Initialize task store (database persistence)
        logger.debug("📦 Initializing task store")
        task_store = await get_task_store(database_url)

        # Create agent card
        logger.debug("🆔 Creating agent card")
        agent_card = create_agent_card()

        # Create request handler
        logger.debug("🎛️ Creating request handler")
        # TODO: Add audio_processor when implemented in T5
        handler = LoistRequestHandler(task_store=task_store, audio_processor=None)

        # Configure A2A FastAPI application using SDK
        logger.debug("🔧 Configuring A2AFastAPIApplication")
        a2a_app = A2AFastAPIApplication(
            agent_card=agent_card,
            http_handler=handler
        )

        # Build the FastAPI application
        logger.debug("🏗️ Building FastAPI application")
        app = a2a_app.build()

        logger.info("✅ A2A FastAPI application created successfully")
        logger.info("📍 Agent Card endpoint: /.well-known/agent-card.json")
        logger.info("📍 JSON-RPC endpoint: POST /")

        return app

    except ValueError as e:
        logger.error(f"❌ Invalid configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create A2A application: {e}", exc_info=True)
        raise


async def create_a2a_app_from_env() -> FastAPI:
    """
    Create A2A application using environment variables.

    Convenience function that uses DATABASE_URL and other environment
    variables for configuration.

    Returns:
        FastAPI: Configured FastAPI application
    """
    return await create_a2a_app(database_url=None)
