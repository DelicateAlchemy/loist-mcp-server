# Module Organization Guide

## Overview

This guide outlines the module organization principles and patterns implemented in the Music Library MCP Server, ensuring clean separation of concerns, maintainable code structure, and scalable architecture.

## Core Architecture Principles

### 1. Dependency Inversion Principle

#### Before (Tight Coupling)
```
Business Logic → Database Operations → PostgreSQL
```

#### After (Clean Architecture)
```
Business Logic → Repository Interface ← Repository Implementation → PostgreSQL
```

### 2. Single Responsibility Principle

#### Module Responsibilities

- **Repository Layer**: Data access abstraction
- **Business Logic Layer**: Domain operations and rules
- **Presentation Layer**: MCP protocol handling
- **Infrastructure Layer**: External services and utilities

### 3. Interface Segregation

#### Repository Interface Pattern
```python
class AudioRepositoryInterface(ABC):
    """Focused interface for audio data operations."""

    @abstractmethod
    def save_metadata(self, metadata, audio_path):
        """Save single track metadata."""
        pass

    @abstractmethod
    def save_metadata_batch(self, metadata_list):
        """Save multiple tracks efficiently."""
        pass

    @abstractmethod
    def search_tracks(self, query):
        """Search tracks with full-text search."""
        pass

    # Specific methods only - no generic CRUD
```

## Directory Structure

### Recommended Project Layout

```
src/
├── exceptions/              # Unified exception framework
│   ├── __init__.py         # Framework exports
│   ├── handler.py          # Core exception handler
│   ├── context.py          # Exception context system
│   ├── recovery.py         # Recovery strategies
│   ├── config.py           # Configuration options
│   └── fastmcp_integration.py  # FastMCP integration
│
├── repositories/            # Data access layer
│   ├── __init__.py         # Repository exports
│   └── audio_repository.py # Audio repository interface & implementations
│
├── fastmcp_setup.py        # Clean FastMCP initialization
├── server.py               # MCP server and tool registration
├── config.py               # Application configuration
│
├── resources/              # MCP resource handlers
│   ├── __init__.py
│   ├── metadata.py         # Metadata resource
│   ├── audio_stream.py     # Audio streaming resource
│   └── thumbnail.py        # Thumbnail resource
│
├── tools/                  # MCP tool implementations
│   ├── __init__.py
│   ├── process_audio.py    # Audio processing tool
│   └── query_tools.py      # Search and query tools
│
├── auth/                   # Authentication (future)
├── storage/                # Cloud storage utilities (future)
└── utils/                  # Shared utilities (future)

database/                   # Database layer
├── __init__.py
├── operations.py           # Database operations
├── pool.py                 # Connection pooling
├── config.py               # Database configuration
└── migrations/             # Schema migrations

tests/                      # Test suite
├── conftest.py             # Test configuration and fixtures
├── test_*.py              # Unit and integration tests
└── test_*_integration.py  # Database integration tests
```

## Module Organization Patterns

### 1. Repository Pattern Implementation

#### Interface Definition
```python
# repositories/audio_repository.py
class AudioRepositoryInterface(ABC):
    """Abstract interface for audio data operations."""

    @abstractmethod
    def save_metadata(self, metadata: Dict, audio_path: str) -> Dict:
        pass

    @abstractmethod
    def get_metadata_by_id(self, track_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    def search_tracks(self, query: str, limit: int) -> List[Dict]:
        pass
```

#### Concrete Implementation
```python
class PostgresAudioRepository(AudioRepositoryInterface):
    """PostgreSQL implementation of audio repository."""

    def save_metadata(self, metadata, audio_path):
        # PostgreSQL-specific implementation
        with get_connection() as conn:
            # Optimized database operations
            pass

    def get_metadata_by_id(self, track_id):
        # PostgreSQL-specific queries
        pass
```

#### Factory Pattern for Dependency Injection
```python
# repositories/audio_repository.py
def get_audio_repository() -> AudioRepositoryInterface:
    """Factory function with test mode detection."""
    if os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TEST_MODE') == 'true':
        from tests.conftest import MockAudioRepository
        return MockAudioRepository()
    return PostgresAudioRepository()
```

### 2. Exception Framework Organization

#### Layered Exception Handling
```python
# exceptions/__init__.py - Public API
from .handler import ExceptionHandler
from .context import ExceptionContext
from .recovery import RecoveryStrategy

# exceptions/handler.py - Core logic
class ExceptionHandler:
    def handle_exception(self, exception, context):
        # Unified exception processing
        pass

# exceptions/fastmcp_integration.py - Framework integration
def initialize_exception_framework():
    # Clean FastMCP integration
    pass
```

#### Configuration-Driven Behavior
```python
# exceptions/config.py
@dataclass
class ExceptionConfig:
    enable_detailed_errors: bool = True
    log_level: str = "ERROR"
    enable_recovery: bool = True

    @classmethod
    def for_production(cls):
        return cls(
            enable_detailed_errors=True,
            include_stack_traces=False,
            log_level="WARNING"
        )

    @classmethod
    def for_testing(cls):
        return cls(
            enable_recovery=False,  # Deterministic testing
            include_stack_traces=True
        )
```

### 3. Clean FastMCP Integration

#### Separation of Concerns
```python
# fastmcp_setup.py - FastMCP initialization
def create_fastmcp_server():
    """Create and configure FastMCP server instance."""
    mcp = FastMCP("Music Library MCP Server")
    # Basic configuration only
    return mcp

# server.py - Application logic
def register_tools(mcp):
    """Register MCP tools with business logic."""
    @mcp.tool()
    async def process_audio(url: str):
        # Tool implementation
        pass
```

#### Middleware Pattern
```python
# exceptions/fastmcp_integration.py
class FastMCPExceptionMiddleware:
    """Clean exception handling middleware."""

    def __init__(self, handler: ExceptionHandler):
        self.handler = handler

    def process_exception(self, exception, context=None):
        """Process exceptions for FastMCP compatibility."""
        return self.handler.handle_exception(exception, context).to_dict()
```

## Import Strategy

### Absolute Imports with Clean Structure

#### Preferred Import Pattern
```python
# ✅ Good: Clear module hierarchy
from src.repositories.audio_repository import get_audio_repository
from src.exceptions import ExceptionHandler, ExceptionContext
from database.operations import save_audio_metadata_batch

# ❌ Bad: Relative imports create coupling
from ..repositories.audio_repository import get_audio_repository
from .exceptions import ExceptionHandler
```

#### Import Organization
```python
# Standard library imports
import logging
import os
from typing import Dict, Optional

# Third-party imports
import psycopg2

# Local application imports (grouped by layer)
from src.config import config
from src.exceptions import ExceptionHandler
from database.operations import get_connection
```

### Avoiding Circular Dependencies

#### Common Anti-Patterns

```python
# ❌ Circular dependency
# module_a.py
from module_b import function_b

# module_b.py
from module_a import function_a

# ✅ Solution: Dependency injection
# module_a.py
class ServiceA:
    def __init__(self, service_b):
        self.service_b = service_b

# module_b.py
class ServiceB:
    def __init__(self, service_a):
        self.service_a = service_a

# factory.py
def create_services():
    service_a = ServiceA(None)
    service_b = ServiceB(None)
    service_a.service_b = service_b
    service_b.service_a = service_a
    return service_a, service_b
```

#### Late Imports for Optional Dependencies

```python
# ✅ Good: Import when needed
def get_audio_repository():
    if os.getenv('PYTEST_CURRENT_TEST'):
        from tests.conftest import MockAudioRepository
        return MockAudioRepository()
    else:
        from src.repositories.audio_repository import PostgresAudioRepository
        return PostgresAudioRepository()
```

## Configuration Management

### Environment-Based Configuration

#### Configuration Hierarchy
```python
# config.py - Base configuration
@dataclass
class Config:
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "music_library"

    # FastMCP
    mcp_server_name: str = "Music Library MCP Server"
    mcp_transport: str = "stdio"

# Environment-specific overrides
def load_config() -> Config:
    config = Config()

    # Environment variables override defaults
    config.db_host = os.getenv('DB_HOST', config.db_host)
    config.environment = os.getenv('ENVIRONMENT', config.environment)

    # Environment-specific adjustments
    if config.environment == "production":
        config.debug = False
        config.log_level = "WARNING"
    elif config.environment == "testing":
        config.db_name = "music_library_test"

    return config
```

### Feature Flags

```python
# config.py
@dataclass
class FeatureFlags:
    enable_batch_operations: bool = True
    enable_full_text_search: bool = True
    enable_exception_recovery: bool = True
    enable_performance_monitoring: bool = False
```

## Testing Organization

### Test Module Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_exceptions.py       # Exception framework tests
├── test_repositories.py     # Repository pattern tests
├── test_resources.py        # MCP resource tests
├── test_tools.py           # MCP tool tests
├── test_database_pool.py   # Connection pool tests
├── test_database_operations_integration.py  # DB integration tests
└── test_fastmcp_integration.py  # End-to-end MCP tests
```

### Fixture Organization

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def test_db_config():
    """Database configuration for testing."""
    return {
        'host': 'localhost',
        'port': 5432,
        'database': 'music_library_test',
        'user': 'loist_user',
        'password': 'dev_password'
    }

@pytest.fixture
def mock_repository():
    """Mock repository for unit testing."""
    return MockAudioRepository()

@pytest.fixture
def exception_handler():
    """Configured exception handler for testing."""
    config = ExceptionConfig().for_testing()
    return ExceptionHandler(config)
```

### Test Categories

#### Unit Tests
```python
class TestAudioRepository:
    """Test repository interface compliance."""

    def test_save_metadata_interface(self, mock_repository, sample_metadata):
        """Test repository save method signature."""
        result = mock_repository.save_metadata(sample_metadata, "gs://test/audio.mp3")

        assert 'id' in result
        assert result['title'] == sample_metadata['title']
```

#### Integration Tests
```python
class TestDatabaseOperations:
    """Test database operations with real database."""

    def test_batch_insert_performance(self, db_pool):
        """Test batch operations perform better than individual inserts."""
        # Performance comparison tests
        pass
```

#### End-to-End Tests
```python
class TestFastMCPIntegration:
    """Test complete MCP server functionality."""

    def test_process_audio_tool(self):
        """Test complete audio processing workflow."""
        # Full workflow testing
        pass
```

## Error Handling Patterns

### Centralized Exception Handling

```python
# exceptions/fastmcp_integration.py
_global_exception_handler = None

def get_global_exception_handler():
    """Get the global exception handler instance."""
    if _global_exception_handler is None:
        raise RuntimeError("Exception framework not initialized")
    return _global_exception_handler

def initialize_exception_framework():
    """Initialize unified exception handling."""
    global _global_exception_handler

    config = ExceptionConfig()
    handler = ExceptionHandler(config)

    # Add recovery strategies
    handler.add_recovery_strategy(DatabaseRecoveryStrategy())

    _global_exception_handler = handler
    return handler
```

### Context-Aware Error Handling

```python
# In any module
from src.exceptions import ExceptionContext
from src.exceptions.fastmcp_integration import get_global_exception_handler

def process_audio_file(audio_data):
    """Process audio with proper error context."""

    handler = get_global_exception_handler()
    context = ExceptionContext(
        operation="process_audio",
        component="tools.process_audio",
        user_id=get_current_user_id()
    )

    try:
        # Business logic
        metadata = extract_metadata(audio_data)
        return repository.save_metadata(metadata, audio_data.path)
    except Exception as e:
        # Contextual error handling
        return handler.handle_exception(e, context)
```

## Performance Considerations

### Lazy Loading

```python
# repositories/audio_repository.py
_audio_repository = None

def get_audio_repository():
    """Lazy initialization of repository."""
    global _audio_repository

    if _audio_repository is None:
        if is_test_mode():
            _audio_repository = MockAudioRepository()
        else:
            _audio_repository = PostgresAudioRepository()

    return _audio_repository
```

### Connection Pool Optimization

```python
# database/pool.py
class DatabasePool:
    def __init__(self, min_connections=2, max_connections=10):
        # Optimized for Cloud Run
        self.min_connections = min_connections
        self.max_connections = max_connections
        # Connection validation caching
        # Health check monitoring
```

## Migration Guide

### From Monolithic Structure

#### Phase 1: Extract Interfaces
1. Define repository interfaces
2. Create abstraction layers
3. Implement dependency injection

#### Phase 2: Modularize Components
1. Split large modules into focused components
2. Create clear module boundaries
3. Establish import hierarchies

#### Phase 3: Implement Patterns
1. Apply repository pattern
2. Implement exception framework
3. Add configuration management

#### Phase 4: Testing and Validation
1. Create comprehensive test suite
2. Validate module interactions
3. Performance testing and optimization

### Module Responsibility Checklist

When creating new modules, ensure:

- [ ] **Single Responsibility**: Module has one clear purpose
- [ ] **Dependency Injection**: Dependencies are injected, not imported
- [ ] **Interface Segregation**: Interfaces are focused and minimal
- [ ] **Test Coverage**: Module has comprehensive tests
- [ ] **Documentation**: Module has clear docstrings and usage examples
- [ ] **Configuration**: Module respects configuration boundaries
- [ ] **Error Handling**: Module uses unified exception framework

### Example: Adding a New Feature

```python
# 1. Define interface
class SearchServiceInterface(ABC):
    @abstractmethod
    def advanced_search(self, query, filters):
        pass

# 2. Create implementation
class PostgresSearchService(SearchServiceInterface):
    def __init__(self, repository: AudioRepositoryInterface):
        self.repository = repository

    def advanced_search(self, query, filters):
        # Implementation
        pass

# 3. Add to factory
def get_search_service():
    repository = get_audio_repository()
    return PostgresSearchService(repository)

# 4. Use in tools
@mcp.tool()
async def advanced_search(query: str, **filters):
    service = get_search_service()
    return await service.advanced_search(query, filters)
```

## Best Practices Summary

### Module Design
- **Clear Boundaries**: Each module has a single, well-defined responsibility
- **Dependency Injection**: Use factories and interfaces for loose coupling
- **Configuration Management**: Environment-based configuration with sensible defaults
- **Error Handling**: Unified exception framework across all modules

### Code Organization
- **Consistent Naming**: Follow established naming conventions
- **Import Strategy**: Prefer absolute imports with clear module hierarchy
- **Documentation**: Comprehensive docstrings and usage examples
- **Testing**: Test-first approach with comprehensive coverage

### Performance
- **Lazy Loading**: Initialize resources only when needed
- **Connection Pooling**: Efficient database connection management
- **Caching**: Implement appropriate caching strategies
- **Monitoring**: Built-in performance monitoring and metrics

### Maintainability
- **Interface Contracts**: Clear interfaces prevent breaking changes
- **Migration Paths**: Plan for future refactoring and evolution
- **Documentation**: Keep documentation synchronized with code
- **Testing**: Automated testing prevents regressions

This module organization guide provides the foundation for scalable, maintainable, and testable code in the Music Library MCP Server.
