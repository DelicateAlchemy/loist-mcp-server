"""
Exception Framework Configuration

Provides configuration options for the exception handling system,
allowing customization of behavior for different environments.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExceptionConfig:
    """
    Configuration for the exception handling framework.

    Allows customization of exception handling behavior including
    error detail levels, logging, recovery strategies, and environment-specific settings.
    """

    # Error Response Configuration
    enable_detailed_errors: bool = True
    """Include detailed error information in responses"""

    include_stack_traces: bool = False
    """Include stack traces in error responses (development only)"""

    mask_sensitive_data: bool = True
    """Mask sensitive information in error messages"""

    # Logging Configuration
    log_level: str = "ERROR"
    """Logging level for exceptions ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')"""

    enable_structured_logging: bool = True
    """Use structured logging format for exceptions"""

    # Recovery Configuration
    enable_recovery: bool = True
    """Enable automatic recovery strategies"""

    max_retry_attempts: int = 3
    """Maximum number of retry attempts for recoverable errors"""

    retry_backoff_seconds: float = 0.1
    """Base backoff time between retry attempts"""

    # Framework Integration
    fastmcp_integration: bool = True
    """Enable FastMCP-specific integration features"""

    enable_metrics: bool = False
    """Enable error metrics collection (future feature)"""

    # Environment-specific overrides
    def for_production(self) -> 'ExceptionConfig':
        """Production-optimized configuration."""
        return ExceptionConfig(
            enable_detailed_errors=True,
            include_stack_traces=False,
            mask_sensitive_data=True,
            log_level="WARNING",
            enable_recovery=True,
            fastmcp_integration=True,
            enable_metrics=True,
        )

    def for_development(self) -> 'ExceptionConfig':
        """Development-optimized configuration."""
        return ExceptionConfig(
            enable_detailed_errors=True,
            include_stack_traces=True,
            mask_sensitive_data=False,
            log_level="DEBUG",
            enable_recovery=True,
            fastmcp_integration=True,
            enable_metrics=False,
        )

    def for_testing(self) -> 'ExceptionConfig':
        """Testing-optimized configuration."""
        return ExceptionConfig(
            enable_detailed_errors=True,
            include_stack_traces=True,
            mask_sensitive_data=False,
            log_level="WARNING",
            enable_recovery=False,  # Disable recovery in tests for predictability
            fastmcp_integration=False,
            enable_metrics=False,
        )
