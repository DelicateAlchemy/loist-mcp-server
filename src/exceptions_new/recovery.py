"""
Recovery Strategies for Exception Handling

Provides automatic recovery mechanisms for different types of errors,
including retry logic, fallback strategies, and circuit breaker patterns.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Callable
from .context import ExceptionContext
# Import MusicLibraryError at the module level to avoid circular imports

logger = logging.getLogger(__name__)


class RecoveryStrategy(ABC):
    """
    Abstract base class for exception recovery strategies.

    Recovery strategies determine if an exception is recoverable and
    attempt to recover from it using appropriate mechanisms.
    """

    @abstractmethod
    def can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """
        Determine if the given exception can be recovered from.

        Args:
            exception: The exception that occurred
            context: Context information about the operation

        Returns:
            True if recovery is possible, False otherwise
        """
        pass

    @abstractmethod
    def recover(self, exception: Exception, context: ExceptionContext) -> Any:
        """
        Attempt to recover from the exception.

        Args:
            exception: The exception that occurred
            context: Context information about the operation

        Returns:
            Recovered result or raises exception if recovery fails

        Raises:
            Exception: If recovery is not possible or fails
        """
        pass


class DatabaseRecoveryStrategy(RecoveryStrategy):
    """
    Recovery strategy for database-related errors.

    Handles connection issues, timeouts, and transient database errors
    with retry logic and connection pool management.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 0.1):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """Check if database exception can be recovered."""
        from psycopg2 import OperationalError, InterfaceError

        # Recoverable database errors
        recoverable_errors = (
            OperationalError,  # Connection issues
            InterfaceError,    # Connection state issues
        )

        # Check exception type
        if not isinstance(exception, recoverable_errors):
            return False

        # Check if we haven't exceeded retry limit
        return context.can_retry()

    def recover(self, exception: Exception, context: ExceptionContext) -> Any:
        """Attempt to recover from database exception."""
        if not self.can_recover(exception, context):
            raise exception

        # Implement exponential backoff
        delay = self.base_delay * (2 ** context.retry_count)
        logger.info(f"Retrying database operation in {delay}s (attempt {context.retry_count + 1})")

        time.sleep(delay)
        context.increment_retry()

        # For database errors, the recovery is typically handled by
        # retrying the operation at a higher level
        raise exception  # Re-raise to trigger retry at caller level


class CircuitBreakerRecoveryStrategy(RecoveryStrategy):
    """
    Circuit breaker pattern for external service failures.

    Prevents cascading failures by temporarily stopping calls to failing services.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open

    def can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """Check if circuit breaker allows recovery."""
        current_time = time.time()

        if self.state == "open":
            # Check if recovery timeout has passed
            if current_time - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker entering half-open state")
                return True
            return False

        return self.state in ["closed", "half-open"]

    def recover(self, exception: Exception, context: ExceptionContext) -> Any:
        """Apply circuit breaker recovery logic."""
        current_time = time.time()

        if self.state == "half-open":
            # Single test request in half-open state
            try:
                # If we get here, the operation succeeded in half-open state
                self._reset()
                logger.info("Circuit breaker recovered, closing circuit")
                raise exception  # Still need to retry the original operation
            except Exception:
                # Operation still failing, open circuit again
                self._record_failure()
                raise exception

        # Record the failure
        self._record_failure()

        # Check if we should open the circuit
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.last_failure_time = current_time
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

        raise exception

    def _record_failure(self):
        """Record a failure occurrence."""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.state = "closed"


class FallbackRecoveryStrategy(RecoveryStrategy):
    """
    Fallback strategy that provides alternative behavior when primary operation fails.
    """

    def __init__(self, fallback_function: Callable, can_recover_check: Optional[Callable] = None):
        self.fallback_function = fallback_function
        self.can_recover_check = can_recover_check or self._default_can_recover

    def can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """Check if fallback recovery is applicable."""
        return self.can_recover_check(exception, context)

    def recover(self, exception: Exception, context: ExceptionContext) -> Any:
        """Execute fallback recovery."""
        logger.info(f"Executing fallback recovery for {context.operation}")
        try:
            return self.fallback_function(exception, context)
        except Exception as fallback_error:
            logger.error(f"Fallback recovery failed: {fallback_error}")
            raise exception  # Raise original exception

    def _default_can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """Default recovery check - allow for most exceptions."""
        # Don't recover from programming errors or critical failures
        programming_errors = (TypeError, ValueError, AttributeError, ImportError)
        if isinstance(exception, programming_errors):
            return False

        # Allow recovery for operational errors
        return True


class CompositeRecoveryStrategy(RecoveryStrategy):
    """
    Composite strategy that tries multiple recovery strategies in order.
    """

    def __init__(self, strategies: list[RecoveryStrategy]):
        self.strategies = strategies

    def can_recover(self, exception: Exception, context: ExceptionContext) -> bool:
        """Check if any strategy can recover."""
        return any(strategy.can_recover(exception, context) for strategy in self.strategies)

    def recover(self, exception: Exception, context: ExceptionContext) -> Any:
        """Try each strategy in order until one succeeds."""
        last_exception = exception

        for strategy in self.strategies:
            if strategy.can_recover(last_exception, context):
                try:
                    return strategy.recover(last_exception, context)
                except Exception as recovery_exception:
                    last_exception = recovery_exception
                    continue

        # All strategies failed
        raise last_exception
