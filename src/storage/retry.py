"""
Retry utilities for reliable cloud storage operations.

Implements exponential backoff with jitter for handling transient failures
in cloud services like Google Cloud Storage.
"""

import time
import random
import logging
from typing import Callable, TypeVar, Any, Optional, Type, Tuple
from functools import wraps
from google.cloud.exceptions import GoogleCloudError, TooManyRequests, ServiceUnavailable

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Default retryable exceptions for GCS operations
RETRYABLE_EXCEPTIONS = (
    TooManyRequests,      # 429 - Rate limit exceeded
    ServiceUnavailable,   # 503 - Service temporarily unavailable
    ConnectionError,      # Network connection issues
    TimeoutError,         # Request timeout
)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 32.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of attempts (including initial)
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            exponential_base: Base for exponential backoff (typically 2.0)
            jitter: Whether to add randomness to delay (recommended)
            retryable_exceptions: Tuple of exception types to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
            
        Formula:
            delay = min(initial_delay * (exponential_base ** attempt), max_delay)
            
        With jitter:
            delay = delay * random.uniform(0.5, 1.5)
        """
        # Calculate exponential delay
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Cap at maximum delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled (±50% randomness)
        if self.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay = delay * jitter_factor
        
        return delay


def with_retry(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic with exponential backoff to a function.
    
    Args:
        config: RetryConfig object (uses defaults if not provided)
        operation_name: Name of operation for logging (uses function name if not provided)
    
    Returns:
        Decorated function with retry logic
        
    Example:
        >>> @with_retry(RetryConfig(max_attempts=5))
        ... def upload_file(path):
        ...     # Upload logic here
        ...     pass
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    # Attempt the operation
                    result = func(*args, **kwargs)
                    
                    # Log success if this wasn't the first attempt
                    if attempt > 0:
                        logger.info(
                            f"{op_name} succeeded on attempt {attempt + 1}/{config.max_attempts}"
                        )
                    
                    return result
                    
                except config.retryable_exceptions as e:
                    last_exception = e
                    is_last_attempt = (attempt == config.max_attempts - 1)
                    
                    if is_last_attempt:
                        logger.error(
                            f"{op_name} failed after {config.max_attempts} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay for next retry
                    delay = config.calculate_delay(attempt)
                    
                    logger.warning(
                        f"{op_name} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Sleep before retry
                    time.sleep(delay)
                    
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(f"{op_name} failed with non-retryable error: {e}")
                    raise
            
            # This should never be reached, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{op_name} failed without exception")
        
        return wrapper
    return decorator


def retry_operation(
    operation: Callable[[], T],
    config: Optional[RetryConfig] = None,
    operation_name: str = "operation",
) -> T:
    """
    Execute an operation with retry logic (functional approach).
    
    This is an alternative to the decorator for cases where you can't
    decorate the function directly.
    
    Args:
        operation: Callable to execute (takes no arguments)
        config: RetryConfig object (uses defaults if not provided)
        operation_name: Name of operation for logging
    
    Returns:
        Result from successful operation
        
    Raises:
        Last exception if all retries failed
        
    Example:
        >>> result = retry_operation(
        ...     lambda: upload_to_gcs(file_path),
        ...     RetryConfig(max_attempts=5),
        ...     "file_upload"
        ... )
    """
    if config is None:
        config = RetryConfig()
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_attempts):
        try:
            result = operation()
            
            if attempt > 0:
                logger.info(
                    f"{operation_name} succeeded on attempt {attempt + 1}/{config.max_attempts}"
                )
            
            return result
            
        except config.retryable_exceptions as e:
            last_exception = e
            is_last_attempt = (attempt == config.max_attempts - 1)
            
            if is_last_attempt:
                logger.error(
                    f"{operation_name} failed after {config.max_attempts} attempts: {e}"
                )
                raise
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"{operation_name} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"{operation_name} failed with non-retryable error: {e}")
            raise
    
    if last_exception:
        raise last_exception
    raise RuntimeError(f"{operation_name} failed without exception")


# Preset configurations for common scenarios

# Conservative: 3 attempts, moderate delays
CONSERVATIVE_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=16.0,
    exponential_base=2.0,
    jitter=True,
)

# Aggressive: 5 attempts, shorter delays
AGGRESSIVE_CONFIG = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=8.0,
    exponential_base=1.5,
    jitter=True,
)

# Patient: 4 attempts, longer delays (good for large files)
PATIENT_CONFIG = RetryConfig(
    max_attempts=4,
    initial_delay=2.0,
    max_delay=60.0,
    exponential_base=2.5,
    jitter=True,
)



