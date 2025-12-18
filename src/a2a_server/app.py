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
from src.a2a_server.agent_card import create_agent_card
from src.a2a_server.handler import LoistRequestHandler
from src.a2a_server.storage import get_task_store, PushConfigStore

logger = logging.getLogger(__name__)


async def create_a2a_app(database_url: Optional[str] = None) -> FastAPI:
    """
    Create and configure the A2A FastAPI application.

    Sets up the A2A SDK's FastAPI application with:
    - Agent Card serving at /.well-known/agent-card.json
    - JSON-RPC endpoints for task operations
    - LoistRequestHandler for audio processing logic
    - Proper database connection lifecycle management

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

        # Initialize push config store (uses same engine as task store)
        logger.debug("📬 Initializing push config store")
        push_config_store = PushConfigStore(engine=task_store.engine)

        # Create agent card
        logger.debug("🆔 Creating agent card")
        agent_card = create_agent_card()

        # Create request handler
        logger.debug("🎛️ Creating request handler")
        # Audio processing handled by shared business logic (src/business/audio_processor.py)
        handler = LoistRequestHandler(
            task_store=task_store,
            push_config_store=push_config_store
        )

        # Configure A2A FastAPI application using SDK
        logger.debug("🔧 Configuring A2AFastAPIApplication")
        a2a_app = A2AFastAPIApplication(
            agent_card=agent_card,
            http_handler=handler
        )

        # Build the FastAPI application
        logger.debug("🏗️ Building FastAPI application")
        app = a2a_app.build()

        # Store task store in app state for cleanup
        app.state.task_store = task_store

        # Add shutdown event handler for proper cleanup
        @app.on_event("shutdown")
        async def shutdown_event():
            """Clean up database connections on application shutdown."""
            logger.info("🧹 Shutting down A2A application, cleaning up resources")
            try:
                if hasattr(app.state, 'task_store') and hasattr(app.state.task_store, 'engine'):
                    logger.debug("🔌 Disposing database engine")
                    await app.state.task_store.engine.dispose()
                    logger.info("✅ Database connections cleaned up")
            except Exception as e:
                logger.error(f"❌ Error during cleanup: {e}")

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


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import os
    import logging

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Get port from environment (default 8081 for A2A)
    port = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8081")))
    host = os.getenv("SERVER_HOST", "0.0.0.0")

    async def run():
        app = await create_a2a_app_from_env()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(run())
