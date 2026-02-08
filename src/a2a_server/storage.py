"""
A2A Task Storage Layer

Provides DatabaseTaskStore initialization and configuration for A2A tasks
using the A2A SDK with default task model.

Author: Task Master AI
Created: $(date)
"""

import logging
import os
import uuid
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from a2a.server.tasks import DatabaseTaskStore
from a2a.types import PushNotificationConfig

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


class PushConfigStore:
    """
    Storage for push notification configurations.
    
    Provides async database operations for managing push notification configs
    associated with A2A tasks. Uses async SQLAlchemy to match the pattern
    used by DatabaseTaskStore.
    """
    
    def __init__(self, engine, exception_handler: Optional[ExceptionHandler] = None):
        """
        Initialize push config store.
        
        Args:
            engine: SQLAlchemy async engine (from DatabaseTaskStore)
            exception_handler: Exception handler for consistent error handling
        """
        self.engine = engine
        self.exception_handler = exception_handler or ExceptionHandler(
            ExceptionConfig().for_development()
        )
        self._session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        logger.info("🔧 PushConfigStore initialized")
    
    async def set_info(
        self,
        task_id: str,
        push_notification_config: PushNotificationConfig,
        config_id: Optional[str] = None
    ) -> None:
        """
        Set or update push notification configuration for a task.
        
        Args:
            task_id: A2A task ID
            push_notification_config: Push notification configuration from SDK
            config_id: Optional config ID (if not provided, uses config.id or generates one)
        
        Raises:
            Exception: If database operation fails
        """
        exc_context = ExceptionContext(
            operation="set_push_config",
            component="a2a.storage",
            operation_type=OperationType.DATABASE_QUERY,
        )
        
        try:
            # Use provided config_id, or from config, or generate one
            final_config_id = config_id or getattr(push_notification_config, 'id', None) or str(uuid.uuid4())
            
            # Extract config fields
            url = push_notification_config.url
            token = getattr(push_notification_config, 'token', None)
            authentication = None
            if hasattr(push_notification_config, 'authentication') and push_notification_config.authentication:
                # Convert authentication to JSONB-compatible dict
                if hasattr(push_notification_config.authentication, 'model_dump'):
                    authentication = push_notification_config.authentication.model_dump()
                else:
                    authentication = dict(push_notification_config.authentication)
            
            async with self._session_factory() as session:
                # Upsert: insert or update if (task_id, config_id) exists
                # Build SQL with conditional JSONB cast for authentication
                if authentication is not None:
                    sql = """
                        INSERT INTO push_notification_configs (task_id, config_id, url, token, authentication, updated_at)
                        VALUES (:task_id, :config_id, :url, :token, :authentication::jsonb, NOW())
                        ON CONFLICT (task_id, config_id)
                        DO UPDATE SET
                            url = EXCLUDED.url,
                            token = EXCLUDED.token,
                            authentication = EXCLUDED.authentication,
                            updated_at = NOW()
                    """
                else:
                    sql = """
                        INSERT INTO push_notification_configs (task_id, config_id, url, token, authentication, updated_at)
                        VALUES (:task_id, :config_id, :url, :token, NULL, NOW())
                        ON CONFLICT (task_id, config_id)
                        DO UPDATE SET
                            url = EXCLUDED.url,
                            token = EXCLUDED.token,
                            authentication = EXCLUDED.authentication,
                            updated_at = NOW()
                    """
                
                await session.execute(
                    text(sql),
                    {
                        "task_id": task_id,
                        "config_id": final_config_id,
                        "url": url,
                        "token": token,
                        "authentication": authentication
                    }
                )
                await session.commit()
                logger.info(f"✅ Push notification config set for task {task_id}, config_id {final_config_id}")
        
        except Exception as e:
            logger.error(f"❌ Failed to set push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)
    
    async def get_info(self, task_id: str) -> List[Tuple[Optional[str], PushNotificationConfig]]:
        """
        Get push notification configurations for a task.
        
        Args:
            task_id: A2A task ID
        
        Returns:
            List of tuples: (config_id, PushNotificationConfig)
        
        Raises:
            Exception: If database operation fails
        """
        exc_context = ExceptionContext(
            operation="get_push_config",
            component="a2a.storage",
            operation_type=OperationType.DATABASE_QUERY,
        )
        
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    text("""
                        SELECT config_id, url, token, authentication
                        FROM push_notification_configs
                        WHERE task_id = :task_id
                        ORDER BY created_at
                    """),
                    {"task_id": task_id}
                )
                rows = result.fetchall()
                
                configs = []
                for row in rows:
                    config_id, url, token, auth_dict = row
                    # Reconstruct PushNotificationConfig from database fields
                    # Note: PushNotificationConfig structure may vary by SDK version
                    # We'll create a dict that matches the expected structure
                    config_dict = {"url": url}
                    if token:
                        config_dict["token"] = token
                    if auth_dict:
                        config_dict["authentication"] = auth_dict
                    if config_id:
                        config_dict["id"] = config_id
                    
                    # Create PushNotificationConfig object
                    push_config = PushNotificationConfig(**config_dict)
                    configs.append((config_id, push_config))
                
                logger.debug(f"✅ Retrieved {len(configs)} push notification config(s) for task {task_id}")
                return configs
        
        except Exception as e:
            logger.error(f"❌ Failed to get push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)
    
    async def delete_info(self, task_id: str, config_id: Optional[str] = None) -> None:
        """
        Delete push notification configuration(s) for a task.
        
        Args:
            task_id: A2A task ID
            config_id: Optional config ID. If None, deletes all configs for the task.
        
        Raises:
            Exception: If database operation fails
        """
        exc_context = ExceptionContext(
            operation="delete_push_config",
            component="a2a.storage",
            operation_type=OperationType.DATABASE_QUERY,
        )
        
        try:
            async with self._session_factory() as session:
                if config_id:
                    # Delete specific config
                    result = await session.execute(
                        text("""
                            DELETE FROM push_notification_configs
                            WHERE task_id = :task_id AND config_id = :config_id
                        """),
                        {"task_id": task_id, "config_id": config_id}
                    )
                    deleted_count = result.rowcount
                    logger.info(f"✅ Deleted push notification config {config_id} for task {task_id}")
                else:
                    # Delete all configs for task
                    result = await session.execute(
                        text("""
                            DELETE FROM push_notification_configs
                            WHERE task_id = :task_id
                        """),
                        {"task_id": task_id}
                    )
                    deleted_count = result.rowcount
                    logger.info(f"✅ Deleted {deleted_count} push notification config(s) for task {task_id}")
                
                await session.commit()
        
        except Exception as e:
            logger.error(f"❌ Failed to delete push notification config for task {task_id}: {e}")
            self.exception_handler.handle_and_raise(e, exc_context)