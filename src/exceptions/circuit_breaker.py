"""
Circuit breaker pattern implementation for fault tolerance.

Provides automatic failure detection and recovery for external service calls,
preventing cascading failures and allowing graceful degradation.
"""

import logging
import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation, requests pass through
    OPEN = "open"           # Circuit is open, requests fail fast
    HALF_OPEN = "half_open" # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5         # Failures before opening circuit
    recovery_timeout: float = 60.0     # Seconds to wait before trying half-open
    success_threshold: int = 3         # Successes needed to close circuit from half-open
    timeout: float = 30.0              # Request timeout in seconds
    name: str = "default"               # Circuit breaker name for logging


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open and request cannot proceed."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable thresholds and recovery.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Circuit has failed, requests fail fast with exception
    - HALF_OPEN: Testing recovery, limited requests allowed

    Features:
    - Thread-safe state management
    - Configurable failure/success thresholds
    - Automatic recovery testing
    - Comprehensive statistics
    - Timeout handling
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._state = CircuitBreakerState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = threading.RLock()
        self._last_state_change = time.time()

        logger.info(
            f"Circuit breaker '{config.name}' initialized: "
            f"failure_threshold={config.failure_threshold}, "
            f"recovery_timeout={config.recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get current statistics (returns a copy)."""
        with self._lock:
            return CircuitBreakerStats(**self._stats.__dict__)

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._state != CircuitBreakerState.OPEN:
            return False

        time_since_failure = time.time() - (self._stats.last_failure_time or 0)
        return time_since_failure >= self.config.recovery_timeout

    def _record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self._stats.total_requests += 1
            self._stats.successful_requests += 1
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes += 1
            self._stats.last_success_time = time.time()

            # Check if we should close the circuit from half-open
            if (self._state == CircuitBreakerState.HALF_OPEN and
                self._stats.consecutive_successes >= self.config.success_threshold):
                self._change_state(CircuitBreakerState.CLOSED)

    def _record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self._stats.total_requests += 1
            self._stats.failed_requests += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.time()

            # Check if we should open the circuit
            if (self._state == CircuitBreakerState.CLOSED and
                self._stats.consecutive_failures >= self.config.failure_threshold):
                self._change_state(CircuitBreakerState.OPEN)
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Failed during recovery test, go back to open
                self._change_state(CircuitBreakerState.OPEN)

    def _change_state(self, new_state: CircuitBreakerState) -> None:
        """Change circuit breaker state."""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1
        self._last_state_change = time.time()

        logger.info(
            f"Circuit breaker '{self.config.name}' state change: "
            f"{old_state.value} -> {new_state.value} "
            f"(failures: {self._stats.consecutive_failures}, "
            f"successes: {self._stats.consecutive_successes})"
        )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Any exception raised by the function
        """
        with self._lock:
            # Check if we should attempt to reset from open to half-open
            if self._state == CircuitBreakerState.OPEN and self._should_attempt_reset():
                self._change_state(CircuitBreakerState.HALF_OPEN)

            # Fail fast if circuit is open
            if self._state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.config.name}' is OPEN. "
                    f"Last failure: {self._stats.last_failure_time}, "
                    f"Consecutive failures: {self._stats.consecutive_failures}"
                )

        # Execute the function with timeout
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Check for timeout
            if execution_time > self.config.timeout:
                logger.warning(
                    f"Function call exceeded timeout ({execution_time:.2f}s > {self.config.timeout}s) "
                    f"in circuit breaker '{self.config.name}'"
                )
                self._record_failure()
                raise TimeoutError(f"Operation timed out after {execution_time:.2f} seconds")

            self._record_success()
            return result

        except Exception as e:
            # Don't count CircuitBreakerOpenException as a failure
            if not isinstance(e, CircuitBreakerOpenException):
                self._record_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function through the circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the async function call

        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Any exception raised by the function
        """
        import asyncio

        with self._lock:
            # Check if we should attempt to reset from open to half-open
            if self._state == CircuitBreakerState.OPEN and self._should_attempt_reset():
                self._change_state(CircuitBreakerState.HALF_OPEN)

            # Fail fast if circuit is open
            if self._state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.config.name}' is OPEN. "
                    f"Last failure: {self._stats.last_failure_time}, "
                    f"Consecutive failures: {self._stats.consecutive_failures}"
                )

        # Execute the async function with timeout
        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            execution_time = time.time() - start_time

            self._record_success()
            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(
                f"Async function call exceeded timeout ({execution_time:.2f}s > {self.config.timeout}s) "
                f"in circuit breaker '{self.config.name}'"
            )
            self._record_failure()
            raise TimeoutError(f"Async operation timed out after {execution_time:.2f} seconds")

        except Exception as e:
            # Don't count CircuitBreakerOpenException as a failure
            if not isinstance(e, CircuitBreakerOpenException):
                self._record_failure()
            raise


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.RLock()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance.

    Args:
        name: Unique name for the circuit breaker
        config: Configuration for the circuit breaker (uses defaults if not provided)

    Returns:
        CircuitBreaker instance
    """
    global _circuit_breakers

    with _registry_lock:
        if name not in _circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig(name=name)
            _circuit_breakers[name] = CircuitBreaker(config)

        return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_circuit_breaker(name: str) -> bool:
    """
    Reset a circuit breaker to closed state.

    Args:
        name: Name of the circuit breaker to reset

    Returns:
        True if reset was successful, False if breaker doesn't exist
    """
    with _registry_lock:
        if name in _circuit_breakers:
            breaker = _circuit_breakers[name]
            with breaker._lock:
                breaker._change_state(CircuitBreakerState.CLOSED)
                breaker._stats = CircuitBreakerStats()  # Reset stats
            return True
    return False
