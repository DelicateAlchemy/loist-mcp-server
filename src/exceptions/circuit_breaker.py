"""
Circuit Breaker Implementation for Fault Tolerance

Provides circuit breaker pattern to prevent cascading failures by automatically
stopping calls to failing services and allowing them to recover gracefully.

Features:
- Configurable failure thresholds and timeouts
- Environment variable configuration
- Thread-safe operation
- Comprehensive statistics and monitoring
- Multiple circuit breaker instances by name
"""

import time
import threading
import logging
from enum import Enum
from typing import Optional, Dict, Any, Callable, TypeVar
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, requests fail fast
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open."""
    pass


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker operation."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0  # Requests rejected when OPEN
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    consecutive_successes: int = 0
    consecutive_failures: int = 0


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.

    Can be configured via environment variables with CIRCUIT_BREAKER_ prefix.
    """
    name: str
    failure_threshold: int
    recovery_timeout: float
    success_threshold: int
    timeout: float = 30.0  # Request timeout

    def __init__(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
        success_threshold: Optional[int] = None,
        timeout: Optional[float] = None
    ):
        """
        Initialize circuit breaker configuration.

        Parameters can be overridden by environment variables:
        - CIRCUIT_BREAKER_FAILURE_THRESHOLD (default: 5)
        - CIRCUIT_BREAKER_RECOVERY_TIMEOUT (default: 60.0)
        - CIRCUIT_BREAKER_SUCCESS_THRESHOLD (default: 3)
        - CIRCUIT_BREAKER_TIMEOUT (default: 30.0)
        """
        self.name = name

        # Use environment variables with fallbacks to provided values or defaults
        self.failure_threshold = (
            failure_threshold or
            int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', '5'))
        )
        self.recovery_timeout = (
            recovery_timeout or
            float(os.getenv('CIRCUIT_BREAKER_RECOVERY_TIMEOUT', '60.0'))
        )
        self.success_threshold = (
            success_threshold or
            int(os.getenv('CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '3'))
        )
        self.timeout = (
            timeout or
            float(os.getenv('CIRCUIT_BREAKER_TIMEOUT', '30.0'))
        )

        # Validate configuration
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout <= 0:
            raise ValueError("timeout must be > 0")


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable behavior.

    Automatically transitions between CLOSED, OPEN, and HALF_OPEN states
    based on failure patterns and recovery attempts.
    """

    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.

        Args:
            config: CircuitBreakerConfig with behavior settings
        """
        self.config = config
        self._state = CircuitBreakerState.CLOSED
        self.state = self._state  # For backward compatibility
        self.stats = CircuitBreakerStats()
        self._lock = threading.RLock()
        self._last_state_change = time.time()

        logger.info(
            f"Circuit breaker '{config.name}' initialized: "
            f"failure_threshold={config.failure_threshold}, "
            f"recovery_timeout={config.recovery_timeout}s, "
            f"success_threshold={config.success_threshold}"
        )

    def call(self, func: Callable[[], T], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenException: If circuit is OPEN
            Exception: Any exception raised by the function
        """
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if not self._should_attempt_recovery():
                    self.stats.rejected_requests += 1
                    logger.warning(f"Circuit breaker '{self.config.name}' is OPEN - rejecting request")
                    raise CircuitBreakerOpenException(f"Circuit breaker '{self.config.name}' is open")

                # Transition to HALF_OPEN for testing
                self._transition_to(CircuitBreakerState.HALF_OPEN)
                logger.info(f"Circuit breaker '{self.config.name}' entering HALF_OPEN state")

            self.stats.total_requests += 1

        try:
            # Execute the function with timeout
            import signal
            from contextlib import contextmanager

            @contextmanager
            def timeout_context(seconds):
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Operation timed out after {seconds}s")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
                try:
                    yield
                finally:
                    signal.alarm(0)

            with timeout_context(int(self.config.timeout)):
                result = func(*args, **kwargs)

            # Success
            self._on_success()
            return result

        except Exception as e:
            # Failure
            self._on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if we should attempt recovery from OPEN state."""
        if self.state != CircuitBreakerState.OPEN:
            return False

        time_since_open = time.time() - self._last_state_change
        return time_since_open >= self.config.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        with self._lock:
            self.stats.successful_requests += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)
                    logger.info(f"Circuit breaker '{self.config.name}' recovered - CLOSED")

    def _on_failure(self):
        """Handle failed operation."""
        with self._lock:
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()

            if self.state == CircuitBreakerState.HALF_OPEN:
                # Failed during recovery test - back to OPEN
                self._transition_to(CircuitBreakerState.OPEN)
                logger.warning(f"Circuit breaker '{self.config.name}' recovery failed - OPEN")
            elif (self.state == CircuitBreakerState.CLOSED and
                  self.stats.consecutive_failures >= self.config.failure_threshold):
                # Too many failures - open circuit
                self._transition_to(CircuitBreakerState.OPEN)
                logger.warning(
                    f"Circuit breaker '{self.config.name}' opened after "
                    f"{self.stats.consecutive_failures} consecutive failures"
                )

    def _transition_to(self, new_state: CircuitBreakerState):
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self.state = new_state  # Keep both for compatibility
        self._last_state_change = time.time()

        logger.info(
            f"Circuit breaker '{self.config.name}' state: {old_state.value} -> {new_state.value}"
        )

    def _change_state(self, new_state: CircuitBreakerState):
        """Change state (for testing/backward compatibility)."""
        self._transition_to(new_state)

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to(CircuitBreakerState.CLOSED)
            self.stats = CircuitBreakerStats()
            logger.info(f"Circuit breaker '{self.config.name}' manually reset")


# Global registry of circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance.

    Args:
        name: Unique name for the circuit breaker
        config: Optional configuration (uses defaults if not provided)

    Returns:
        CircuitBreaker instance
    """
    global _circuit_breakers

    with _registry_lock:
        if name not in _circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig(name)
            elif config.name != name:
                # Ensure config name matches
                config = CircuitBreakerConfig(
                    name=name,
                    failure_threshold=config.failure_threshold,
                    recovery_timeout=config.recovery_timeout,
                    success_threshold=config.success_threshold,
                    timeout=config.timeout
                )

            _circuit_breakers[name] = CircuitBreaker(config)

        return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """
    Get all registered circuit breakers.

    Returns:
        Dictionary mapping names to circuit breaker instances
    """
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_circuit_breaker(name: str) -> bool:
    """
    Reset a circuit breaker to CLOSED state.

    Args:
        name: Name of the circuit breaker to reset

    Returns:
        True if reset was successful, False if breaker not found

    Raises:
        KeyError: If circuit breaker doesn't exist
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            raise KeyError(f"Circuit breaker '{name}' not found")
        _circuit_breakers[name].reset()
        return True


def reset_all_circuit_breakers():
    """Reset all circuit breakers to CLOSED state."""
    with _registry_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()
