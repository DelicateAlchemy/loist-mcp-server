"""
Retry utilities with exponential backoff and jitter.

Provides configurable retry policies for handling transient failures
in external service calls and database operations.
"""

import logging
import random
import time
from typing import Callable, Any, Optional, Dict, List, Type, Union
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 0.1  # Initial delay in seconds
    max_delay: float = 30.0     # Maximum delay between retries
    backoff_factor: float = 2.0 # Exponential backoff multiplier
    jitter: bool = True         # Add random jitter to delay
    jitter_factor: float = 0.1  # Jitter factor (0.1 = ±10% of delay)
    retryable_exceptions: List[Type[Exception]] = None

    def __post_init__(self):
        if self.retryable_exceptions is None:
            # Default retryable exceptions for network/database operations
            import psycopg2
            self.retryable_exceptions = [
                ConnectionError,
                TimeoutError,
                OSError,  # Network-related OS errors
                psycopg2.OperationalError,  # Database connection issues
                psycopg2.InterfaceError,    # Database interface issues
            ]


class RetryExhaustedException(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, message: str, attempts: int, last_exception: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for the given attempt using exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (0-based)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    # Exponential backoff: initial_delay * (backoff_factor ^ attempt)
    delay = config.initial_delay * (config.backoff_factor ** attempt)

    # Cap at maximum delay
    delay = min(delay, config.max_delay)

    # Add jitter if enabled
    if config.jitter:
        # Add random jitter of ±jitter_factor * delay
        jitter_range = delay * config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        delay += jitter

        # Ensure delay doesn't go negative
        delay = max(0.001, delay)  # Minimum 1ms delay

    return delay


def is_retryable_exception(exception: Exception, config: RetryConfig) -> bool:
    """
    Check if an exception should trigger a retry.

    Args:
        exception: The exception that occurred
        config: Retry configuration

    Returns:
        True if the exception is retryable
    """
    for retryable_type in config.retryable_exceptions:
        if isinstance(exception, retryable_type):
            return True

    # Check for common retryable error messages
    error_message = str(exception).lower()
    retryable_messages = [
        "connection refused",
        "connection reset",
        "connection timed out",
        "timeout",
        "temporary failure",
        "service unavailable",
        "too many requests",
        "rate limit",
        "network",
        "dns",
        "resolve",
    ]

    for msg in retryable_messages:
        if msg in error_message:
            return True

    return False


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    **config_kwargs
) -> Callable:
    """
    Decorator that implements retry logic with exponential backoff.

    Args:
        config: RetryConfig instance (optional)
        **config_kwargs: RetryConfig parameters (used if config is None)

    Returns:
        Decorated function

    Example:
        @retry_with_backoff(max_attempts=5, initial_delay=0.5)
        def unreliable_operation():
            # ... code that might fail ...
            pass
    """
    if config is None:
        config = RetryConfig(**config_kwargs)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if this is the last attempt
                    if attempt == config.max_attempts - 1:
                        logger.error(
                            f"Operation '{func.__name__}' failed after {config.max_attempts} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryExhaustedException(
                            f"Operation failed after {config.max_attempts} attempts",
                            config.max_attempts,
                            e
                        ) from e

                    # Check if exception is retryable
                    if not is_retryable_exception(e, config):
                        logger.debug(f"Non-retryable exception in '{func.__name__}': {e}")
                        raise  # Re-raise immediately

                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for '{func.__name__}': {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

            # This should never be reached, but just in case
            raise RetryExhaustedException(
                f"Unexpected end of retry loop for {func.__name__}",
                config.max_attempts,
                last_exception
            )

        return wrapper

    return decorator


def retry_call(
    func: Callable,
    config: Optional[RetryConfig] = None,
    **config_kwargs
) -> Any:
    """
    Call a function with retry logic.

    Args:
        func: Function to call
        config: RetryConfig instance (optional)
        **config_kwargs: RetryConfig parameters (used if config is None)

    Returns:
        Result of the function call

    Raises:
        RetryExhaustedException: If all retry attempts fail
        Exception: The last exception if it's not retryable
    """
    if config is None:
        config = RetryConfig(**config_kwargs)

    return retry_with_backoff(config)(func)()


# Pre-configured retry policies for common use cases
DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=5.0,
    backoff_factor=2.0,
    jitter=True,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
    ]
)

# Try to add psycopg2 exceptions if available
try:
    import psycopg2
    DATABASE_RETRY_CONFIG.retryable_exceptions.extend([
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    ])
except ImportError:
    pass

GCS_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.2,
    max_delay=10.0,
    backoff_factor=2.0,
    jitter=True,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
    ]
)

# Try to add google cloud exceptions if available
try:
    from google.api_core import exceptions as google_exceptions
    GCS_RETRY_CONFIG.retryable_exceptions.extend([
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.InternalServerError,
        google_exceptions.BadGateway,
        google_exceptions.GatewayTimeout,
    ])
except ImportError:
    pass

HTTP_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    backoff_factor=1.5,
    jitter=True,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
    ]
)
