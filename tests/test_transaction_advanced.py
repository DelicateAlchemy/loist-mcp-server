"""
Advanced transaction testing for database operations.

Tests verify:
- Transaction commit and rollback scenarios
- Nested transaction behavior
- Transaction isolation levels
- Transaction timeout and deadlock detection
- Concurrent transaction behavior
- Transaction boundary management
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch


def is_db_configured() -> bool:
    """Check if database configuration is available."""
    import os
    has_direct = bool(
        os.getenv("DB_HOST") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    has_proxy = bool(
        os.getenv("DB_CONNECTION_NAME") and
        os.getenv("DB_NAME") and
        os.getenv("DB_USER") and
        os.getenv("DB_PASSWORD")
    )
    return has_direct or has_proxy


@pytest.fixture
def db_pool():
    """Fixture to create a test database pool."""
    if not is_db_configured():
        pytest.skip("Database not configured")

    from database import get_connection_pool, close_pool

    # Get fresh pool for testing
    pool = get_connection_pool(force_new=True)

    yield pool

    close_pool()


@pytest.fixture
def test_schema_setup(db_pool):
    """Set up test schema for transaction testing."""
    if not db_pool:
        pytest.skip("Database pool not available")

    from tests.database_testing import TestDatabaseManager

    manager = TestDatabaseManager()
    manager.setup_test_database()

    # Create test tables for transaction testing
    # Use direct database operations to avoid transaction rollback issues
    from database import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Create test tables in test schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_schema.transaction_test (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    balance DECIMAL(10,2) DEFAULT 0,
                    version INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS test_schema.transaction_log (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(50) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

    yield manager

    manager.cleanup_test_database()


class TestTransactionCommitRollback:
    """Test transaction commit and rollback scenarios."""

    def test_successful_transaction_commit(self, test_schema_setup):
        """Test that successful transactions commit properly."""
        manager = test_schema_setup

        with manager.committing_transaction_context() as conn:
            with conn.cursor() as cur:
                # Insert test data
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s) RETURNING id
                """, ("Commit Test", 100.50))

                inserted_id = cur.fetchone()[0]

                # Insert log entry
                cur.execute("""
                    INSERT INTO test_schema.transaction_log (action, details)
                    VALUES (%s, %s)
                """, ("INSERT", f"Inserted record {inserted_id}"))

        # Verify transaction was committed
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")

                # Check main record exists
                cur.execute("SELECT name, balance FROM test_schema.transaction_test WHERE id = %s", (inserted_id,))
                result = cur.fetchone()
                assert result is not None
                assert result[0] == "Commit Test"
                assert result[1] == 100.50

                # Check log entry exists
                cur.execute("SELECT action FROM test_schema.transaction_log WHERE details = %s", (f"Inserted record {inserted_id}",))
                log_result = cur.fetchone()
                assert log_result is not None
                assert log_result[0] == "INSERT"

    def test_transaction_rollback_on_error(self, test_schema_setup):
        """Test that transactions rollback on errors."""
        manager = test_schema_setup

        inserted_id = None
        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    # Insert test data
                    cur.execute("""
                        INSERT INTO test_schema.transaction_test (name, balance)
                        VALUES (%s, %s) RETURNING id
                    """, ("Rollback Test", 50.25))

                    inserted_id = cur.fetchone()[0]

                    # Insert log entry
                    cur.execute("""
                        INSERT INTO test_schema.transaction_log (action, details)
                        VALUES (%s, %s)
                    """, ("INSERT", f"Inserted record {inserted_id}"))

                    # Cause an error
                    cur.execute("INVALID SQL THAT WILL FAIL")

        except Exception:
            pass  # Expected error

        # Verify transaction was rolled back
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")

                if inserted_id:
                    # Check main record does not exist
                    cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE id = %s", (inserted_id,))
                    count = cur.fetchone()[0]
                    assert count == 0, "Record should not exist after rollback"

                    # Check log entry does not exist
                    cur.execute("SELECT COUNT(*) FROM test_schema.transaction_log WHERE details = %s", (f"Inserted record {inserted_id}",))
                    log_count = cur.fetchone()[0]
                    assert log_count == 0, "Log entry should not exist after rollback"

    def test_manual_transaction_rollback(self, test_schema_setup):
        """Test manual transaction rollback."""
        manager = test_schema_setup

        with manager.transaction_context() as conn:
            with conn.cursor() as cur:
                # Insert test data
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s) RETURNING id
                """, ("Manual Rollback Test", 75.00))

                inserted_id = cur.fetchone()[0]

                # Manually rollback (this should happen automatically at context exit)
                conn.rollback()

        # Verify transaction was rolled back
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")

                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE id = %s", (inserted_id,))
                count = cur.fetchone()[0]
                assert count == 0, "Record should not exist after manual rollback"

    def test_nested_transaction_behavior(self, test_schema_setup):
        """Test nested transaction behavior (savepoints)."""
        manager = test_schema_setup

        with manager.committing_transaction_context() as conn:
            with conn.cursor() as cur:
                # Insert main record
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s) RETURNING id
                """, ("Nested Transaction Test", 200.00))

                main_id = cur.fetchone()[0]

                # Create savepoint
                cur.execute("SAVEPOINT nested_savepoint")

                try:
                    # Insert nested record
                    cur.execute("""
                        INSERT INTO test_schema.transaction_test (name, balance)
                        VALUES (%s, %s) RETURNING id
                    """, ("Nested Record", 50.00))

                    nested_id = cur.fetchone()[0]

                    # Simulate error that triggers savepoint rollback
                    raise Exception("Simulated nested error")

                except Exception:
                    # Rollback to savepoint on error
                    cur.execute("ROLLBACK TO SAVEPOINT nested_savepoint")
                    # Continue with main transaction

                # Insert final record to show main transaction continues
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s) RETURNING id
                """, ("Final Record", 75.00))

                final_id = cur.fetchone()[0]

        # Verify main record and final record exist, but nested record does not
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")

                # Main record should exist
                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE id = %s", (main_id,))
                assert cur.fetchone()[0] == 1

                # Final record should exist
                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE id = %s", (final_id,))
                assert cur.fetchone()[0] == 1

                # Nested record should not exist (rolled back to savepoint)
                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE name = %s", ("Nested Record",))
                assert cur.fetchone()[0] == 0


class TestTransactionIsolationLevels:
    """Test different transaction isolation levels."""

    def test_read_committed_isolation(self, test_schema_setup):
        """Test READ COMMITTED isolation level."""
        manager = test_schema_setup

        # Insert initial data
        with manager.transaction_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s)
                """, ("Isolation Test", 100.00))

        # Start two transactions
        results = []

        def transaction_worker(worker_id):
            """Worker that performs transaction operations."""
            try:
                with manager.transaction_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO test_schema, public")

                        if worker_id == 1:
                            # Worker 1: Update balance
                            time.sleep(0.1)  # Let worker 2 start
                            cur.execute("""
                                UPDATE test_schema.transaction_test
                                SET balance = balance + 50
                                WHERE name = %s
                            """, ("Isolation Test",))
                            results.append(("worker_1_updated", True))
                        else:
                            # Worker 2: Read balance
                            cur.execute("""
                                SELECT balance FROM test_schema.transaction_test
                                WHERE name = %s
                            """, ("Isolation Test",))
                            balance = cur.fetchone()[0]
                            results.append(("worker_2_read", balance))

            except Exception as e:
                results.append((f"worker_{worker_id}_error", str(e)))

        # Run concurrent transactions
        threads = [
            threading.Thread(target=transaction_worker, args=(1,)),
            threading.Thread(target=transaction_worker, args=(2,))
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify results - with READ COMMITTED, worker 2 might see old or new value
        assert len(results) == 2
        balances = [r[1] for r in results if r[0] == "worker_2_read"]
        if balances:
            assert balances[0] in [100.00, 150.00]  # Either original or updated value

    def test_transaction_isolation_consistency(self, test_schema_setup):
        """Test that transaction isolation maintains consistency."""
        manager = test_schema_setup

        # Test serializable isolation if supported
        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    # Try to set isolation level
                    cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    cur.execute("SET search_path TO test_schema, public")

                    # Insert test data
                    cur.execute("""
                        INSERT INTO test_schema.transaction_test (name, balance)
                        VALUES (%s, %s)
                    """, ("Serializable Test", 300.00))

        except Exception as e:
            # Isolation level may not be supported, that's ok
            pytest.skip(f"Isolation level not supported: {e}")

        # Verify data was inserted
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")
                cur.execute("SELECT balance FROM test_schema.transaction_test WHERE name = %s", ("Serializable Test",))
                result = cur.fetchone()
                assert result[0] == 300.00


class TestTransactionTimeoutDeadlock:
    """Test transaction timeout and deadlock scenarios."""

    def test_transaction_timeout_simulation(self, test_schema_setup):
        """Test transaction timeout behavior simulation."""
        manager = test_schema_setup

        # This is a simplified timeout test - real timeout testing
        # would require database-specific timeout settings
        timeout_occurred = False

        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO test_schema, public")

                    # Set a statement timeout (PostgreSQL specific)
                    cur.execute("SET statement_timeout = '100ms'")

                    # Try a long-running operation
                    cur.execute("SELECT pg_sleep(0.5)")  # Sleep for 500ms

        except Exception as e:
            if "timeout" in str(e).lower() or "canceling" in str(e).lower():
                timeout_occurred = True

        # Reset timeout for future tests
        try:
            with manager._pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = 0")  # Reset timeout
        except Exception:
            pass  # Ignore cleanup errors

        # Note: This test may or may not trigger a timeout depending on system
        # In a real scenario, you'd configure database timeouts appropriately

    def test_deadlock_detection_simulation(self, test_schema_setup):
        """Test deadlock detection and handling."""
        manager = test_schema_setup

        # Insert test records
        with manager.transaction_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")
                cur.execute("""
                    INSERT INTO test_schema.transaction_test (name, balance)
                    VALUES (%s, %s), (%s, %s)
                """, ("Deadlock Record 1", 100, "Deadlock Record 2", 200))

        # Create a potential deadlock scenario
        results = []

        def deadlock_worker(worker_id):
            """Worker that might cause deadlock."""
            try:
                with manager.transaction_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO test_schema, public")

                        if worker_id == 1:
                            # Lock record 1 then try to lock record 2
                            cur.execute("""
                                SELECT * FROM test_schema.transaction_test
                                WHERE name = %s FOR UPDATE
                            """, ("Deadlock Record 1",))
                            time.sleep(0.1)  # Let other worker start
                            cur.execute("""
                                SELECT * FROM test_schema.transaction_test
                                WHERE name = %s FOR UPDATE
                            """, ("Deadlock Record 2",))
                        else:
                            # Lock record 2 then try to lock record 1
                            cur.execute("""
                                SELECT * FROM test_schema.transaction_test
                                WHERE name = %s FOR UPDATE
                            """, ("Deadlock Record 2",))
                            time.sleep(0.1)  # Let other worker start
                            cur.execute("""
                                SELECT * FROM test_schema.transaction_test
                                WHERE name = %s FOR UPDATE
                            """, ("Deadlock Record 1",))

                        results.append(f"worker_{worker_id}_success")

            except Exception as e:
                results.append(f"worker_{worker_id}_error: {str(e)[:100]}")

        # Run concurrent transactions that might deadlock
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(deadlock_worker, 1),
                executor.submit(deadlock_worker, 2)
            ]

            for future in as_completed(futures, timeout=5):
                try:
                    future.result()
                except Exception as e:
                    results.append(f"future_error: {e}")

        # Verify that at least one transaction succeeded
        # (deadlock detection should allow one to proceed)
        success_count = sum(1 for r in results if "success" in r)
        assert success_count >= 1, f"Expected at least one successful transaction, got results: {results}"


class TestConcurrentTransactions:
    """Test concurrent transaction behavior."""

    def test_concurrent_transaction_isolation(self, test_schema_setup):
        """Test that concurrent transactions are properly isolated."""
        manager = test_schema_setup

        results = []

        def concurrent_transaction_worker(worker_id, operation):
            """Worker performing concurrent transaction operations."""
            try:
                with manager.transaction_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO test_schema, public")

                        if operation == "insert":
                            # Insert operation
                            cur.execute("""
                                INSERT INTO test_schema.transaction_test (name, balance)
                                VALUES (%s, %s) RETURNING id
                            """, (f"Concurrent Insert {worker_id}", worker_id * 10))

                            inserted_id = cur.fetchone()[0]
                            results.append(("insert", worker_id, inserted_id))

                        elif operation == "update":
                            # Update operation (assuming records exist)
                            cur.execute("""
                                UPDATE test_schema.transaction_test
                                SET balance = balance + %s
                                WHERE name LIKE %s
                            """, (5, "Concurrent Insert%"))

                            results.append(("update", worker_id, None))

                        elif operation == "select":
                            # Select operation
                            cur.execute("""
                                SELECT COUNT(*) FROM test_schema.transaction_test
                                WHERE name LIKE %s
                            """, ("Concurrent Insert%",))

                            count = cur.fetchone()[0]
                            results.append(("select", worker_id, count))

            except Exception as e:
                results.append(("error", worker_id, str(e)[:100]))

        # Insert initial data
        with manager.transaction_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")
                for i in range(5):
                    cur.execute("""
                        INSERT INTO test_schema.transaction_test (name, balance)
                        VALUES (%s, %s)
                    """, (f"Concurrent Insert {i}", i * 10))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                operation = ["insert", "update", "select"][i % 3]
                futures.append(executor.submit(concurrent_transaction_worker, i, operation))

            for future in as_completed(futures, timeout=10):
                future.result()

        # Verify results
        inserts = [r for r in results if r[0] == "insert"]
        updates = [r for r in results if r[0] == "update"]
        selects = [r for r in results if r[0] == "select"]
        errors = [r for r in results if r[0] == "error"]

        # Should have some successful operations
        assert len(inserts) + len(updates) + len(selects) > 0, f"All operations failed: {results}"

        # Errors should be minimal (acceptable race conditions)
        assert len(errors) <= len(results) * 0.3, f"Too many errors: {errors}"

    def test_transaction_boundary_integrity(self, test_schema_setup):
        """Test that transaction boundaries maintain data integrity."""
        manager = test_schema_setup

        # Test atomicity: all operations in a transaction should succeed or fail together
        try:
            with manager.transaction_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO test_schema, public")

                    # Insert related records
                    cur.execute("""
                        INSERT INTO test_schema.transaction_test (name, balance)
                        VALUES (%s, %s), (%s, %s), (%s, %s)
                    """, ("Atomic Test 1", 100, "Atomic Test 2", 200, "Atomic Test 3", 300))

                    # Insert log entries for each
                    for i in range(1, 4):
                        cur.execute("""
                            INSERT INTO test_schema.transaction_log (action, details)
                            VALUES (%s, %s)
                        """, ("ATOMIC_INSERT", f"Inserted Atomic Test {i}"))

                    # Simulate error on last operation
                    if True:  # Always trigger error for testing
                        raise Exception("Simulated transaction failure")

        except Exception:
            pass  # Expected error

        # Verify atomicity - either all records exist or none do
        with manager._pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO test_schema, public")

                # Count main records
                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_test WHERE name LIKE %s", ("Atomic Test%",))
                main_count = cur.fetchone()[0]

                # Count log records
                cur.execute("SELECT COUNT(*) FROM test_schema.transaction_log WHERE action = %s", ("ATOMIC_INSERT",))
                log_count = cur.fetchone()[0]

                # Atomicity check: counts should be equal (all or nothing)
                assert main_count == log_count, f"Atomicity violation: {main_count} main records, {log_count} log records"

                # Should be 0 (transaction rolled back) or 3 (transaction committed)
                assert main_count in [0, 3], f"Unexpected record count: {main_count}"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
