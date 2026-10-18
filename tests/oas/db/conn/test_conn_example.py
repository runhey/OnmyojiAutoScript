"""
Custom test examples - Demonstrating how to write tests for specific business scenarios

This file shows how to:
1. Test specific business logic
2. Simulate real-world use cases
3. Add performance tests
4. Test special edge cases
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from oas.db.conn import SqlitePool

# ============================================================================
# Test directory setup
# ============================================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(TEST_DIR, 'test_data')


def safe_remove_db(db_path, pool=None):
    """
    Safely remove database file with Windows compatibility

    Args:
        db_path: Path to database file
        pool: Optional SqlitePool to release before deletion
    """
    if pool:
        pool.release_all()
    time.sleep(0.05)  # Wait for file locks to release on Windows
    try:
        os.unlink(db_path)
    except (FileNotFoundError, PermissionError, OSError):
        # File doesn't exist or is locked (common on Windows), that's ok
        pass


# ============================================================================
# Example 1: Test specific business scenario - User session management
# ============================================================================

class TestUserSessionManagement:
    """Test user session management scenario"""

    @pytest.fixture
    def session_pool(self):
        """Create session pool"""
        pool = SqlitePool(pool_size=4)
        yield pool
        pool.release_all()

    @pytest.fixture
    def session_db(self):
        """Create session database"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'sessions.db')

        # Initialize database structure
        pool = SqlitePool()
        with pool.cursor(db_path) as cursor:
            # Drop table if exists from previous failed test
            cursor.execute("DROP TABLE IF EXISTS sessions")
            cursor.execute("""
                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    created_at REAL,
                    last_access REAL
                )
            """)
            cursor.commit()

        yield db_path

        # Cleanup
        safe_remove_db(db_path, pool)

    def test_concurrent_session_creation(self, session_pool, session_db):
        """Test concurrent session creation"""

        def create_session(user_id):
            with session_pool.cursor(session_db) as cursor:
                cursor.execute("""
                    INSERT INTO sessions (session_id, user_id, created_at, last_access)
                    VALUES (?, ?, ?, ?)
                """, (f'session_{user_id}', user_id, time.time(), time.time()))
                cursor.commit()
            return True

        # 100 concurrent users
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_session, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert all(results)

        # Verify all sessions are created
        with session_pool.cursor(session_db) as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM sessions")
            assert cursor.fetchone()['cnt'] == 100

    def test_session_cleanup(self, session_pool, session_db):
        """Test session cleanup (delete expired sessions)"""
        # Create some sessions
        now = time.time()
        with session_pool.cursor(session_db) as cursor:
            # New session
            cursor.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ('new_session', 1, now, now)
            )
            # Expired session (1 hour ago)
            cursor.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ('old_session', 2, now - 3600, now - 3600)
            )
            cursor.commit()

        # Cleanup expired sessions (30 minutes)
        with session_pool.exclusive_transaction(session_db) as cursor:
            cursor.execute(
                "DELETE FROM sessions WHERE ? - last_access > ?",
                (now, 1800)  # 30 minutes = 1800 seconds
            )

        # Verify only new session remains
        with session_pool.cursor(session_db) as cursor:
            cursor.execute("SELECT session_id FROM sessions")
            sessions = [row['session_id'] for row in cursor.fetchall()]
            assert sessions == ['new_session']


# ============================================================================
# Example 2: Performance tests
# ============================================================================

class TestPerformance:
    """Performance test examples"""

    @pytest.mark.slow
    def test_connection_pool_performance(self):
        """Test connection pool performance"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'perf.db')
        pool = SqlitePool(pool_size=10)

        try:
            # Warmup
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS test")
                cursor.execute("CREATE TABLE test (id INTEGER)")
                cursor.commit()

            # Test connection reuse performance
            start = time.perf_counter()
            for _ in range(1000):
                with pool.cursor(db_path) as cursor:
                    cursor.execute("SELECT 1")
            reuse_time = time.perf_counter() - start

            # Clear pool
            pool.release_all()

            # Test new connection creation performance
            start = time.perf_counter()
            for _ in range(1000):
                with pool.cursor(db_path) as cursor:
                    cursor.execute("SELECT 1")
                pool.release_all()  # Force new connection each time
            create_time = time.perf_counter() - start

            # Connection reuse should be significantly faster
            print(f"\nConnection reuse: {reuse_time:.6f}s")
            print(f"Create connection: {create_time:.6f}s")
            print(f"Performance gain: {create_time / reuse_time:.1f}x")

            assert reuse_time < create_time
        finally:
            safe_remove_db(db_path, pool)

    @pytest.mark.slow
    def test_bulk_insert_performance(self):
        """Test bulk insert performance"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'bulk.db')
        pool = SqlitePool()

        try:
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS items")
                cursor.execute("CREATE TABLE items (id INTEGER, value TEXT)")
                cursor.commit()

            # Test single insert
            start = time.perf_counter()
            with pool.exclusive_transaction(db_path) as cursor:
                for i in range(1000):
                    cursor.execute("INSERT INTO items VALUES (?, ?)", (i, f'value_{i}'))
            single_time = time.perf_counter() - start

            # Clear table
            with pool.cursor(db_path) as cursor:
                cursor.execute("DELETE FROM items")
                cursor.commit()

            # Test batch insert
            start = time.perf_counter()
            with pool.exclusive_transaction(db_path) as cursor:
                data = [(i, f'value_{i}') for i in range(1000)]
                cursor.executemany("INSERT INTO items VALUES (?, ?)", data)
            batch_time = time.perf_counter() - start

            print(f"\nSingle insert: {single_time:.6f}s")
            print(f"Batch insert: {batch_time:.6f}s")
            print(f"Performance gain: {single_time / batch_time:.3f}x")
        finally:
            safe_remove_db(db_path, pool)


# ============================================================================
# Example 3: Test complex transaction scenarios
# ============================================================================

class TestComplexTransactions:
    """Test complex transaction scenarios"""

    def test_bank_transfer_with_exclusive_lock(self):
        """Test bank transfer scenario (needs exclusive lock for consistency)"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'bank.db')
        pool = SqlitePool()

        try:
            # Initialize accounts
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS accounts")
                cursor.execute("""
                    CREATE TABLE accounts (
                        account_id INTEGER PRIMARY KEY,
                        balance REAL
                    )
                """)
                cursor.execute("INSERT INTO accounts VALUES (1, 1000.0)")
                cursor.execute("INSERT INTO accounts VALUES (2, 500.0)")
                cursor.commit()

            # Transfer function
            def transfer(from_id, to_id, amount):
                with pool.exclusive_transaction(db_path) as cursor:
                    # Check balance
                    cursor.execute("SELECT balance FROM accounts WHERE account_id = ?", (from_id,))
                    from_balance = cursor.fetchone()['balance']

                    if from_balance < amount:
                        raise ValueError("Insufficient balance")

                    # Deduct
                    cursor.execute(
                        "UPDATE accounts SET balance = balance - ? WHERE account_id = ?",
                        (amount, from_id)
                    )

                    # Simulate processing delay
                    time.sleep(0.01)

                    # Credit
                    cursor.execute(
                        "UPDATE accounts SET balance = balance + ? WHERE account_id = ?",
                        (amount, to_id)
                    )

            # Concurrent transfers
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Transfer from account 1 to account 2, 10 times, 100 each
                futures = [
                    executor.submit(transfer, 1, 2, 100.0)
                    for _ in range(10)
                ]

                # Wait for all transfers to complete
                for f in futures:
                    f.result()

            # Verify final balance
            with pool.cursor(db_path) as cursor:
                cursor.execute("SELECT balance FROM accounts WHERE account_id = 1")
                balance1 = cursor.fetchone()['balance']
                cursor.execute("SELECT balance FROM accounts WHERE account_id = 2")
                balance2 = cursor.fetchone()['balance']

            # Account 1 should decrease by 1000, account 2 should increase by 1000
            assert balance1 == 0.0
            assert balance2 == 1500.0

            # Total amount should remain unchanged
            assert balance1 + balance2 == 1500.0
        finally:
            safe_remove_db(db_path, pool)


# ============================================================================
# Example 4: Test edge cases and error recovery
# ============================================================================

class TestEdgeCasesAndRecovery:
    """Test edge cases and error recovery"""

    def test_transaction_rollback_on_constraint_violation(self):
        """Test transaction rollback on constraint violation"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'test.db')
        pool = SqlitePool()

        try:
            # Create table (with unique constraint)
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS users")
                cursor.execute("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        email TEXT UNIQUE
                    )
                """)
                cursor.execute("INSERT INTO users VALUES (1, 'test@example.com')")
                cursor.commit()

            # Try to insert duplicate email (should rollback)
            import sqlite3
            try:
                with pool.exclusive_transaction(db_path) as cursor:
                    cursor.execute("INSERT INTO users VALUES (2, 'new@example.com')")
                    cursor.execute("INSERT INTO users VALUES (3, 'test@example.com')")  # Duplicate!
            except sqlite3.IntegrityError:
                pass

            # Verify partial data is not committed
            with pool.cursor(db_path) as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM users")
                assert cursor.fetchone()['cnt'] == 1  # Only first record
        finally:
            safe_remove_db(db_path, pool)

    def test_pool_recovery_after_database_deletion(self):
        """Test pool recovery after database deletion"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'test.db')
        pool = SqlitePool()

        try:
            # Use database
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS test")
                cursor.execute("CREATE TABLE test (id INTEGER)")
                cursor.commit()

            # Delete database file
            success = pool.delete_file(db_path)
            assert success
            assert not os.path.exists(db_path)

            # Use again should create new database
            with pool.cursor(db_path) as cursor:
                cursor.execute("CREATE TABLE test2 (id INTEGER)")
                cursor.commit()

            assert os.path.exists(db_path)
        finally:
            safe_remove_db(db_path, pool)


# ============================================================================
# Example 5: Stress test
# ============================================================================

class TestStress:
    """Stress test"""

    @pytest.mark.slow
    def test_high_concurrency_stress(self):
        """High concurrency stress test"""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        db_path = os.path.join(TEST_DATA_DIR, 'stress.db')
        pool = SqlitePool(pool_size=10)

        try:
            # Initialize
            with pool.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute("DROP TABLE IF EXISTS counter")
                cursor.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, value INTEGER)")
                cursor.execute("INSERT INTO counter VALUES (1, 0)")
                cursor.commit()

            def increment_counter():
                """Atomically increment counter"""
                with pool.exclusive_transaction(db_path) as cursor:
                    cursor.execute("UPDATE counter SET value = value + 1 WHERE id = 1")

            # 1000 concurrent increments
            with ThreadPoolExecutor(max_workers=25) as executor:
                futures = [executor.submit(increment_counter) for _ in range(100)]
                for f in futures:
                    f.result()

            # Verify counter value
            with pool.cursor(db_path) as cursor:
                cursor.execute("SELECT value FROM counter WHERE id = 1")
                final_value = cursor.fetchone()['value']

            assert final_value == 100
        finally:
            safe_remove_db(db_path, pool)

