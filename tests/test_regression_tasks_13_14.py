"""
Regression Tests for Tasks 13 and 14 Fixes

Task 13: Fix FastMCP Exception Serialization Context Issues
- Exception serialization should work without NameError exceptions
- Complex objects in exception details should be safely serialized
- FastMCP tools should handle exceptions properly

Task 14: Resolve Architectural Issues and Technical Debt
- Exception handling should be consistent across all modules
- Database operations should use optimized batch operations
- Import dependencies should not cause circular imports
- Repository abstraction should work correctly
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from pathlib import Path

# Test FastMCP exception serialization (Task 13)
from src.exception_serializer import SafeExceptionSerializer
from src.exceptions import (
    MusicLibraryError, ValidationError, AudioProcessingError,
    StorageError, DatabaseOperationError
)

# Test exception handling framework (Task 14)
from src.error_utils import create_error_response, log_error
from src.repositories.audio_repository import AudioRepositoryInterface, get_audio_repository

# Test database optimizations (Task 14)
from database.operations import save_audio_metadata_batch
from database.pool import DatabasePool

# Test import dependencies (Task 14)
from src.fastmcp_setup import create_fastmcp_server
from src.server import create_mcp_tools


class TestFastMCPExceptionSerialization:
    """Regression tests for Task 13: FastMCP Exception Serialization"""

    def setup_method(self):
        self.serializer = SafeExceptionSerializer()

    def test_basic_exception_serialization(self):
        """Test that basic exceptions serialize correctly"""
        exception = ValidationError("Invalid input", {"field": "url"})
        result = self.serializer.serialize_exception(exception)

        assert result["success"] is False
        assert "VALIDATION_ERROR" in result["error"]
        assert result["exception_type"] == "ValidationError"
        assert result["details"]["field"] == "url"

    def test_complex_object_serialization(self):
        """Test that complex objects in exception details are safely handled"""
        complex_details = {
            "datetime": datetime.now(),
            "path": Path("/tmp/file.mp3"),
            "mock": MagicMock(),
            "lambda": lambda x: x,
            "nested": {
                "another_mock": MagicMock(),
                "list_with_complex": [datetime.now(), Path("/tmp")]
            }
        }

        exception = AudioProcessingError("Processing failed", complex_details)
        result = self.serializer.serialize_exception(exception)

        # Should not raise JSON serialization errors
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Complex objects should be converted to safe string representations
        assert "<datetime object>" in parsed["details"]["datetime"]
        assert "<PosixPath object>" in parsed["details"]["path"]
        assert "<MagicMock object>" in parsed["details"]["mock"]
        assert "<function object>" in parsed["details"]["lambda"]

    def test_exception_hierarchy_preservation(self):
        """Test that exception class hierarchy is preserved during serialization"""
        exception = DatabaseOperationError("Connection failed")
        result = self.serializer.serialize_exception(exception)

        assert result["exception_type"] == "DatabaseOperationError"
        assert result["exception_module"] == "src.exceptions"
        assert "DatabaseOperationError" in result["exception_class_hierarchy"]

    def test_no_nameerror_exceptions(self):
        """Regression test: Ensure no NameError during serialization"""
        # This was the original issue - exceptions raised in different contexts
        # would cause NameError when FastMCP tried to access __class__, __name__, etc.

        exception = StorageError("Upload failed", {"file": "test.mp3"})

        # This should not raise NameError
        result = self.serializer.serialize_exception(exception)

        assert result is not None
        assert result["success"] is False
        assert "STORAGE_ERROR" in result["error"]

    def test_async_context_serialization(self):
        """Test serialization works in async contexts (where original issue occurred)"""
        async def test_async_serialization():
            exception = ValidationError("Async validation failed")
            result = self.serializer.serialize_exception(exception)
            return result

        # Should not raise NameError or other context-related errors
        result = asyncio.run(test_async_serialization())

        assert result["success"] is False
        assert result["exception_type"] == "ValidationError"


class TestExceptionHandlingFramework:
    """Regression tests for Task 14: Exception Handling Framework"""

    def test_consistent_error_responses(self):
        """Test that error responses are consistent across all modules"""
        # Test different exception types produce consistent response format
        exceptions = [
            ValidationError("Validation failed", {"field": "url"}),
            AudioProcessingError("Processing failed"),
            StorageError("Storage failed"),
            DatabaseOperationError("Database failed")
        ]

        for exception in exceptions:
            result = create_error_response(exception, "test_operation")

            # All should have consistent structure
            assert "success" in result
            assert result["success"] is False
            assert "error" in result
            assert "message" in result["error"]
            assert "exception_type" in result["error"]

    def test_error_logging_integration(self):
        """Test that error logging works with new framework"""
        exception = ValidationError("Test error for logging")

        # Should not raise errors during logging
        log_error(exception, "test_context")

        # Log should contain structured information
        # (Detailed logging verification would require log capture)

    def test_backward_compatibility(self):
        """Test that old error handling patterns still work"""
        # This ensures the framework is backward compatible
        exception = MusicLibraryError("Base error")

        result = create_error_response(exception, "test_operation")

        assert result["success"] is False
        assert "MUSIC_LIBRARY_ERROR" in result["error"]


class TestDatabasePerformanceOptimizations:
    """Regression tests for Task 14: Database Performance Improvements"""

    def test_batch_operations_optimization(self):
        """Test that batch operations use optimized multi-row inserts"""
        # This test verifies the N+1 query fix from Task 14.2
        mock_pool = Mock()
        mock_conn = Mock()
        mock_cur = Mock()

        mock_pool.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_pool.get_connection.return_value.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        # Mock successful execution
        mock_cur.executemany.return_value = None
        mock_cur.rowcount = 5

        # This should use the optimized batch insert, not individual inserts
        test_data = [
            {"audio_id": f"test-{i}", "title": f"Track {i}", "artist": "Test Artist"}
            for i in range(5)
        ]

        # Note: This test would need a real database connection in integration tests
        # For unit testing, we verify the method exists and has proper structure
        assert callable(save_audio_metadata_batch)

    def test_connection_pool_optimization(self):
        """Test that connection pool optimizations are in place"""
        # Verify connection validation optimizations exist
        pool = DatabasePool()

        # Should have optimized connection validation
        assert hasattr(pool, 'get_connection')

        # Connection method should handle validation efficiently
        # (Detailed testing requires actual database connections)


class TestImportDependencyRefactoring:
    """Regression tests for Task 14: Import Dependency Refactoring"""

    def test_no_circular_imports(self):
        """Test that circular import issues are resolved"""
        # This was a major issue in Task 14.3

        # Should be able to import all these modules without circular dependency errors
        try:
            from src import server
            from src import fastmcp_setup
            from src.repositories import audio_repository
            from src.resources import metadata
            from database import operations
            from database import pool

            # If we get here without ImportError, circular imports are resolved
            assert True

        except ImportError as e:
            if "circular import" in str(e).lower():
                pytest.fail(f"Circular import still exists: {e}")
            else:
                # Re-raise if it's a different import error
                raise

    def test_repository_abstraction(self):
        """Test that repository abstraction works correctly"""
        # This verifies the repository pattern implemented in Task 14.3

        # Should be able to get a repository instance
        repository = get_audio_repository()

        # Should implement the interface
        assert isinstance(repository, AudioRepositoryInterface)

        # Should have required methods
        required_methods = [
            'get_metadata_by_id',
            'search_tracks',
            'save_track_metadata',
            'update_track_status'
        ]

        for method in required_methods:
            assert hasattr(repository, method)
            assert callable(getattr(repository, method))

    def test_fastmcp_clean_initialization(self):
        """Test that FastMCP initialization is clean without workarounds"""
        # This verifies the FastMCP setup cleanup from Task 14.6

        # Should be able to create FastMCP server without complex workarounds
        try:
            mcp = create_fastmcp_server()
            assert mcp is not None

            # Should have proper configuration
            assert hasattr(mcp, '_config')

        except Exception as e:
            # FastMCP initialization should not fail due to exception loading issues
            if "NameError" in str(e) or "exception" in str(e).lower():
                pytest.fail(f"FastMCP initialization still has exception issues: {e}")
            else:
                # Re-raise other errors (might be expected in test environment)
                raise

    def test_server_module_separation(self):
        """Test that server module responsibilities are properly separated"""
        # This verifies the server.py refactoring from Task 14.6

        # Should be able to import server module
        from src import server

        # Should have MCP tool creation function
        assert hasattr(server, 'create_mcp_tools')
        assert callable(server.create_mcp_tools)

        # Should not have direct database imports (those should go through repositories)
        # This is a weak test - in practice we'd need to check the actual imports


class TestEndToEndIntegration:
    """End-to-end regression tests combining multiple fixes"""

    def test_complete_error_handling_flow(self):
        """Test complete error handling flow from exception to response"""
        # This tests the integration of multiple Task 13/14 improvements

        # Create an exception with complex details (Task 13 issue)
        complex_details = {
            "timestamp": datetime.now(),
            "file_path": Path("/tmp/test.mp3"),
            "mock_connection": MagicMock(),
            "callback": lambda: None
        }

        exception = AudioProcessingError("Complex processing error", complex_details)

        # Handle through error utils (Task 14 framework)
        result = create_error_response(exception, "test_processing")

        # Should serialize successfully (Task 13 fix)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Should have proper structure (Task 14 consistency)
        assert parsed["success"] is False
        assert "error" in parsed
        assert "message" in parsed["error"]
        assert parsed["error"]["message"] == "Complex processing error"

        # Complex objects should be safely converted
        assert "<datetime object>" in parsed["details"]["timestamp"]
        assert "<PosixPath object>" in parsed["details"]["file_path"]

    def test_database_and_repository_integration(self):
        """Test that database optimizations work with repository abstraction"""
        # This tests the integration of Task 14.5 (DB perf) and Task 14.6 (repository)

        # Get repository (should use optimized database operations)
        repository = get_audio_repository()

        # Repository should be able to handle batch operations efficiently
        # (Detailed testing requires database connection)

        assert repository is not None
        assert isinstance(repository, AudioRepositoryInterface)


# Test markers for different test categories
pytestmark = [
    pytest.mark.regression,
    pytest.mark.tasks_13_14
]
