"""
A2A Task Storage Layer

Provides DatabaseTaskStore initialization and configuration for A2A tasks
using the A2A SDK with default task model.

Author: Task Master AI
Created: $(date)
"""

import logging
import os
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from a2a.server.tasks import DatabaseTaskStore

# Import exception framework
from src.exceptions.handler import ExceptionHandler
from src.exceptions.config import ExceptionConfig
from src.exceptions.context import ExceptionContext, OperationType

logger = logging.getLogger(__name__)


async def create_task_store(
    database_url: str,
    create_table: bool = True,
    echo: bool = False,
    exception_handler: Optional[ExceptionHandler] = None
) -> DatabaseTaskStore:
    """
    Create and initialize A2A DatabaseTaskStore using SDK defaults.

    Args:
        database_url: PostgreSQL connection URL
        create_table: Whether SDK should auto-create the a2a_tasks table
        echo: Enable SQLAlchemy engine logging
        exception_handler: Exception handler for consistent error handling

    Returns:
        Configured DatabaseTaskStore instance

    Raises:
        ValueError: If database_url is invalid
        Exception: If database connection fails
    """
    # Initialize exception handler
    exception_handler = exception_handler or ExceptionHandler(ExceptionConfig().for_development())

    # Create exception context for this operation
    exc_context = ExceptionContext(
        operation="create_task_store",
        component="a2a.storage",
        operation_type=OperationType.DATABASE_QUERY,
    )

    if not database_url:
        error = ValueError("Database URL is required")
        exception_handler.handle_and_raise(error, exc_context)

    # Convert to async PostgreSQL URL for SQLAlchemy async engine
    if database_url.startswith("postgresql://"):
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql+asyncpg://"):
        async_url = database_url  # Already async
    elif not database_url.startswith("postgresql+"):
        error = ValueError(f"Unsupported database URL scheme: {database_url}")
        exception_handler.handle_and_raise(error, exc_context)
    else:
        async_url = database_url

    logger.info("🔧 Initializing A2A DatabaseTaskStore")
    logger.debug(f"📖 Database URL: {async_url.replace(async_url.split('://')[1].split('@')[0], '***:***')}")

    try:
        # Create async engine for SDK
        engine = create_async_engine(
            async_url,
            echo=echo,
            pool_pre_ping=True,  # Verify connections before use
        )

        # Initialize SDK's DatabaseTaskStore with default model
        task_store = DatabaseTaskStore(
            engine=engine,
            create_table=create_table,
            table_name='a2a_tasks'
        )

        logger.info("✅ A2A DatabaseTaskStore initialized successfully")
        return task_store

    except ValueError as e:
        logger.error(f"❌ Invalid database configuration: {e}")
        exception_handler.handle_and_raise(e, exc_context)
    except Exception as e:
        logger.error(f"❌ Failed to initialize A2A DatabaseTaskStore: {e}", exc_info=True)
        exception_handler.handle_and_raise(e, exc_context)


async def get_task_store(database_url: Optional[str] = None, exception_handler: Optional[ExceptionHandler] = None) -> DatabaseTaskStore:
    """
    Convenience function to get configured task store.

    Uses DATABASE_URL environment variable if no URL provided.
    Falls back to constructing URL from DB_* environment variables (same logic as database/pool.py).

    Args:
        database_url: Optional database URL override
        exception_handler: Exception handler for consistent error handling

    Returns:
        Configured DatabaseTaskStore instance

    Raises:
        ValueError: If database URL is not provided or invalid
    """
    # Initialize exception handler
    exception_handler = exception_handler or ExceptionHandler(ExceptionConfig().for_development())

    # Create exception context for this operation
    exc_context = ExceptionContext(
        operation="get_task_store",
        component="a2a.storage",
        operation_type=OperationType.DATABASE_QUERY,
    )

    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    # If DATABASE_URL not set, construct from individual DB_* environment variables
    # (same logic as database/pool.py for consistency)
    if not database_url:
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_connection_name = os.getenv("DB_CONNECTION_NAME")

        # PRIORITY 1: Cloud SQL Proxy connection (preferred for Cloud Run)
        if db_connection_name and db_name and db_user and db_password:
            logger.info(f"✅ Constructing Cloud SQL Proxy URL from environment variables: {db_connection_name}")
            database_url = f"postgresql://{db_user}:{db_password}@/{db_name}?host=/cloudsql/{db_connection_name}"
        # PRIORITY 2: Direct connection via individual components (fallback)
        elif db_host and db_name and db_user and db_password:
            logger.info(f"✅ Constructing direct database URL from environment variables: {db_host}:{db_port}")
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    if not database_url:
        error = ValueError("Database URL not provided and DATABASE_URL environment variable not set. Also checked DB_CONNECTION_NAME, DB_NAME, DB_USER, DB_PASSWORD, and DB_HOST environment variables.")
        exception_handler.handle_and_raise(error, exc_context)

    # Basic validation
    if not database_url.startswith(("postgresql://", "postgresql+")):
        error = ValueError(f"Invalid database URL format: {database_url}")
        exception_handler.handle_and_raise(error, exc_context)

    return await create_task_store(database_url, exception_handler=exception_handler)