"""
Exception Context System for Rich Error Information

Provides structured context for exceptions to enable better debugging,
monitoring, and recovery strategies.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class OperationType(Enum):
    """Standard operation types for consistent categorization."""
    DATABASE_QUERY = "database_query"
    FILE_UPLOAD = "file_upload"
    AUDIO_PROCESSING = "audio_processing"
    METADATA_EXTRACTION = "metadata_extraction"
    STORAGE_OPERATION = "storage_operation"
    SEARCH_OPERATION = "search_operation"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"


@dataclass
class ExceptionContext:
    """
    Rich context information for exceptions.

    Provides structured information about when, where, and how an exception
    occurred to enable better error handling and debugging.
    """

    operation: str
    """Operation being performed (e.g., 'database_query', 'file_upload')"""

    component: str
    """Component where error occurred (e.g., 'tools.process_audio', 'resources.metadata')"""

    user_id: Optional[str] = None
    """User ID if available (for user-specific operations)"""

    request_id: Optional[str] = None
    """Request ID for tracing across distributed operations"""

    operation_type: Optional[OperationType] = None
    """Standardized operation type for categorization"""

    retry_count: int = 0
    """Number of retry attempts made"""

    max_retries: int = 3
    """Maximum number of retry attempts allowed"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional context-specific metadata"""

    def increment_retry(self) -> None:
        """Increment the retry count."""
        self.retry_count += 1

    def can_retry(self) -> bool:
        """Check if retry is still allowed."""
        return self.retry_count < self.max_retries

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the context."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the context."""
        return self.metadata.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'operation': self.operation,
            'component': self.component,
            'user_id': self.user_id,
            'request_id': self.request_id,
            'operation_type': self.operation_type.value if self.operation_type else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'metadata': self.metadata,
        }
