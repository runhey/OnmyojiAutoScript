"""
Tests for SqlitePool thread pool support with SQLite in-memory database (:memory:)

Note: sqlite3.connect(':memory:') creates a separate in-memory database per connection.
When ConnectionPool reuses the same connection, threads share the same in-memory database.
When multiple concurrent connections are created (e.g., pool_size > 1),
each connection has its own independent in-memory database by SQLite design.
"""
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Barrier

import pytest

from oas.db.conn import ConnectionPool, SqlitePool

# ============================================================================
# Test :memory: with ConnectionPool
# ============================================================================


class TestConnectionPoolMemory:
    """Test ConnectionPool with :memory: database"""

    @pytest.fixture
    def memory_pool(self):
        """Create a ConnectionPool for :memory: database"""
        pool = ConnectionPool(':memory:', pool_size=4)
        yield pool
        pool.release_all()

    def test_basic_operations(self, memory_pool):
        """Test basic create, insert, query on :memory: via ConnectionPool"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER, name TEXT)")
            cursor.execute("INSERT INTO test VALUES (1, 'Alice')")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT * FROM test")
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]['id'] == 1
            assert rows[0]['name'] == 'Alice'

    def test_connection_reuse_shares_memory(self, memory_pool):
        """Test that reusing the same connection shares the same in-memory database"""
        conn1 = None
        conn2 = None

        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE shared (id INTEGER)")
            cursor.execute("INSERT INTO shared VALUES (42)")
            cursor.commit()
            conn1 = cursor.connection

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT id FROM shared")
            row = cursor.fetchone()
            assert row['id'] == 42
            conn2 = cursor.connection

        # Same connection object should be reused
        assert conn1 is conn2

    def test_auto_create_table(self, memory_pool):
        """Test auto-create table works on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.TABLE_NAME = 'players'
            cursor.CREATE_TABLE = """
                CREATE TABLE {TABLE_NAME} (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """
            cursor.execute("INSERT INTO players VALUES (1, 'Bob')")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT name FROM players WHERE id = 1")
            assert cursor.fetchone()['name'] == 'Bob'

    def test_executemany_auto_create(self, memory_pool):
        """Test executemany with auto-create table on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.CREATE_TABLE = "CREATE TABLE items (id INTEGER, value TEXT)"
            cursor.executemany("INSERT INTO items VALUES (?, ?)",
                               [(1, 'a'), (2, 'b'), (3, 'c')])
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM items")
            assert cursor.fetchone()['cnt'] == 3

    def test_exclusive_transaction_commit(self, memory_pool):
        """Test exclusive transaction commit on :memory:"""
        with memory_pool.exclusive_transaction() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (100)")
            cursor.execute("INSERT INTO test VALUES (200)")

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test")
            assert cursor.fetchone()['cnt'] == 2

    def test_exclusive_transaction_rollback(self, memory_pool):
        """Test exclusive transaction rollback on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()

        try:
            with memory_pool.exclusive_transaction() as cursor:
                cursor.execute("INSERT INTO test VALUES (1)")
                raise ValueError("Simulated error")
        except ValueError:
            pass

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test")
            assert cursor.fetchone()['cnt'] == 0

    def test_connection_pool_size_limit(self):
        """Test pool_size limit is respected for :memory:"""
        pool = ConnectionPool(':memory:', pool_size=2)
        cursors = []

        try:
            for _ in range(2):
                cursor = pool.cursor()
                cursor.execute("SELECT 1")
                cursors.append(cursor)

            assert len(pool.all_workers) == 2
            assert len(pool.idle_workers) == 0
        finally:
            for cursor in cursors:
                cursor.close()
            pool.release_all()

    def test_last_use_tracking(self, memory_pool):
        """Test last_use time is tracked for :memory: connections"""
        before = time.time()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT 1")
            conn = cursor.connection

        after = time.time()
        assert conn in memory_pool.last_use
        assert before <= memory_pool.last_use[conn] <= after

    def test_gc_with_memory_database(self):
        """Test gc on :memory: pool does not crash"""
        pool = ConnectionPool(':memory:', pool_size=2)

        with pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (1)")
            cursor.commit()

        # GC with idle=0 should try to clean up
        pool.gc(idle=0)
        # Should not crash, and pool should still be usable
        pool.release_all()

    def test_release_all(self, memory_pool):
        """Test release_all on :memory: pool"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (99)")
            cursor.commit()

        memory_pool.release_all()
        assert len(memory_pool.all_workers) == 0
        assert len(memory_pool.idle_workers) == 0


# ============================================================================
# Test :memory: with SqlitePool
# ============================================================================

class TestSqlitePoolMemory:
    """Test SqlitePool with :memory: database"""

    @pytest.fixture
    def sqlite_memory_pool(self):
        pool = SqlitePool(pool_size=4)
        yield pool
        pool.release_all()

    def test_cursor_method(self, sqlite_memory_pool):
        """Test cursor method with :memory:"""
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (1)")
            cursor.commit()

        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("SELECT * FROM test")
            rows = cursor.fetchall()
            assert len(rows) == 1

    def test_exclusive_transaction_method(self, sqlite_memory_pool):
        """Test exclusive_transaction method with :memory:"""
        with sqlite_memory_pool.exclusive_transaction(':memory:') as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (42)")

        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("SELECT id FROM test")
            assert cursor.fetchone()['id'] == 42

    def test_get_pool_returns_same_pool_for_memory(self, sqlite_memory_pool):
        """Test that get_pool(':memory:') returns the same pool instance"""
        pool1 = sqlite_memory_pool.get_pool(':memory:')
        pool2 = sqlite_memory_pool.get_pool(':memory:')
        assert pool1 is pool2

    def test_multiple_memory_access_share_cache(self, sqlite_memory_pool):
        """Test that multiple accesses to :memory: share the same pool cache"""
        # Create data in first access
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("CREATE TABLE cache_test (key TEXT, value INTEGER)")
            cursor.execute("INSERT INTO cache_test VALUES ('foo', 100)")
            cursor.commit()

        # Second access should see the data via same connection
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("SELECT value FROM cache_test WHERE key = 'foo'")
            assert cursor.fetchone()['value'] == 100

    def test_gc_with_memory(self, sqlite_memory_pool):
        """Test gc on SqlitePool with :memory: does not crash"""
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()

        sqlite_memory_pool.gc(idle=0)
        sqlite_memory_pool.release_all()

    def test_release_all_with_memory(self, sqlite_memory_pool):
        """Test release_all on SqlitePool with :memory:"""
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()

        sqlite_memory_pool.release_all()
        assert len(sqlite_memory_pool.all_pool) == 0

    def test_auto_create_table_via_sqlite_pool(self, sqlite_memory_pool):
        """Test auto-create table via SqlitePool cursor with :memory:"""
        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.CREATE_TABLE = "CREATE TABLE logs (id INTEGER, msg TEXT)"
            cursor.execute("INSERT INTO logs VALUES (1, 'hello')")
            cursor.commit()

        with sqlite_memory_pool.cursor(':memory:') as cursor:
            cursor.execute("SELECT msg FROM logs WHERE id = 1")
            assert cursor.fetchone()['msg'] == 'hello'

    def test_delete_memory_reconnect_fresh_database(self):
        """Test delete_file(':memory:') releases pool, reconnect creates new database"""
        pool = SqlitePool(pool_size=1)
        try:
            # 1. Create data in :memory:
            with pool.cursor(':memory:') as cursor:
                cursor.execute("CREATE TABLE test (id INTEGER)")
                cursor.execute("INSERT INTO test VALUES (42)")
                cursor.commit()

            # Verify data exists
            with pool.cursor(':memory:') as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM test")
                assert cursor.fetchone()['cnt'] == 1

            # 2. Delete the memory database pool
            pool.delete_file(':memory:')
            assert len(pool.all_pool) == 0

            # 3. Reconnect should get a brand new empty in-memory database
            with pool.cursor(':memory:') as cursor:
                # The old table should not exist in the new database
                with pytest.raises(sqlite3.OperationalError, match="no such table"):
                    cursor.execute("SELECT * FROM test")

            # 4. New database should be fully functional
            with pool.cursor(':memory:') as cursor:
                cursor.execute("CREATE TABLE test (name TEXT)")
                cursor.execute("INSERT INTO test VALUES ('new')")
                cursor.commit()

            with pool.cursor(':memory:') as cursor:
                cursor.execute("SELECT name FROM test")
                assert cursor.fetchone()['name'] == 'new'
        finally:
            pool.release_all()


# ============================================================================
# Test single-connection :memory: sharing (pool_size=1 guarantees same DB)
# ============================================================================

class TestMemorySingleConnection:
    """Test that with pool_size=1, all threads share same in-memory database"""

    @pytest.fixture
    def single_conn_pool(self):
        pool = ConnectionPool(':memory:', pool_size=1)
        yield pool
        pool.release_all()

    def test_data_persists_across_cursors(self, single_conn_pool):
        """With pool_size=1, data persists across cursor sessions"""
        with single_conn_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE persistent (id INTEGER)")
            cursor.execute("INSERT INTO persistent VALUES (1)")
            cursor.commit()

        with single_conn_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM persistent")
            assert cursor.fetchone()['cnt'] == 1

    def test_concurrent_threads_share_memory(self, single_conn_pool):
        """With pool_size=1, concurrent threads share the same in-memory DB"""
        # Setup data first
        with single_conn_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE shared (id INTEGER PRIMARY KEY, val TEXT)")
            cursor.commit()

        results = []
        barrier = Barrier(4)

        def worker(start_id, count):
            barrier.wait()
            for i in range(count):
                with single_conn_pool.cursor() as cursor:
                    idx = start_id + i
                    cursor.execute(
                        "INSERT INTO shared VALUES (?, ?)",
                        (idx, f'worker-{idx}')
                    )
                    cursor.commit()
            results.append(count)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(worker, 1, 10),
                executor.submit(worker, 11, 10),
                executor.submit(worker, 21, 10),
                executor.submit(worker, 31, 10),
            ]
            for f in as_completed(futures):
                f.result()

        assert sum(results) == 40

        with single_conn_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM shared")
            assert cursor.fetchone()['cnt'] == 40


# ============================================================================
# Test rename_file / delete_file errors with :memory:
# ============================================================================

class TestMemoryErrorHandling:
    """Test error handling for :memory: specific operations"""

    @pytest.fixture
    def sqlite_pool(self):
        pool = SqlitePool(pool_size=4)
        yield pool
        pool.release_all()

    def test_rename_from_memory_raises(self, sqlite_pool):
        """Test rename_file raises ValueError when old_file is :memory:"""
        with pytest.raises(ValueError, match="Cannot rename memory database"):
            sqlite_pool.rename_file(':memory:', 'some_file.db')

    def test_rename_to_memory_raises(self, sqlite_pool):
        """Test rename_file raises ValueError when new_file is :memory:"""
        with pytest.raises(ValueError, match="Cannot rename"):
            sqlite_pool.rename_file('some_file.db', ':memory:')

    def test_delete_memory_does_not_crash(self, sqlite_pool):
        """Test delete_file with :memory: does not crash"""
        # Should not raise, just return None
        result = sqlite_pool.delete_file(':memory:')
        assert result is None

    def test_empty_file_name_raises(self, sqlite_pool):
        """Test empty file name raises ValueError"""
        with pytest.raises(ValueError, match="File name cannot be empty"):
            sqlite_pool.get_pool('')

        with pytest.raises(ValueError, match="File name cannot be empty"):
            sqlite_pool.get_pool(None)


# ============================================================================
# Test :memory: edge cases
# ============================================================================

class TestMemoryEdgeCases:
    """Test edge cases for :memory: database"""

    @pytest.fixture
    def memory_pool(self):
        pool = ConnectionPool(':memory:', pool_size=4)
        yield pool
        pool.release_all()

    def test_multiple_commits(self, memory_pool):
        """Test multiple commits on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()
            cursor.execute("INSERT INTO test VALUES (1)")
            cursor.commit()
            cursor.execute("INSERT INTO test VALUES (2)")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test")
            assert cursor.fetchone()['cnt'] == 2

    def test_nested_cursors(self, memory_pool):
        """Test nested cursors on :memory:

        When cursor1 holds a connection and cursor2 requests another,
        a new sqlite3.connect(':memory:') creates an independent database.
        This test verifies both independent databases work correctly.
        """
        with memory_pool.cursor() as cursor1:
            cursor1.execute("CREATE TABLE test (id INTEGER)")
            cursor1.execute("INSERT INTO test VALUES (1)")
            cursor1.commit()
            conn1 = cursor1.connection

            with memory_pool.cursor() as cursor2:
                # Cursor2 gets a new :memory: connection - separate database
                assert cursor2.connection is not conn1
                cursor2.execute("CREATE TABLE test (id INTEGER)")
                cursor2.execute("INSERT INTO test VALUES (2)")
                cursor2.commit()

        # Both connections returned to pool
        assert len(memory_pool.idle_workers) == 2

        # Reusing cursor1's connection: sees table with id=1
        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT id FROM test")
            # Depending on which connection is popped, we may get 1 or 2
            # Both are valid - each connection has its own :memory: database
            result = cursor.fetchone()['id']
            assert result in (1, 2)

    def test_very_long_query(self, memory_pool):
        """Test bulk insert on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            values = [(i,) for i in range(1000)]
            cursor.executemany("INSERT INTO test VALUES (?)", values)
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test")
            assert cursor.fetchone()['cnt'] == 1000

    def test_sql_error_propagation(self, memory_pool):
        """Test SQL error propagates on :memory:"""
        with pytest.raises(sqlite3.OperationalError):
            with memory_pool.cursor() as cursor:
                cursor.execute("SELECT * FROM non_existent_table")

    def test_drop_then_recreate(self, memory_pool):
        """Test drop and recreate table on :memory:"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (1)")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("DROP TABLE test")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (name TEXT)")
            cursor.execute("INSERT INTO test VALUES ('recreated')")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT name FROM test")
            assert cursor.fetchone()['name'] == 'recreated'

    def test_fetchall_on_empty_result(self, memory_pool):
        """Test fetchall on empty result set"""
        with memory_pool.cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()

        with memory_pool.cursor() as cursor:
            cursor.execute("SELECT * FROM test")
            rows = cursor.fetchall()
            assert rows == []


# ============================================================================
# Integration test with :memory:
# ============================================================================

class TestMemoryIntegration:
    """Integration test simulating realistic workflow with :memory:"""

    @pytest.fixture
    def sqlite_pool_single(self):
        """SqlitePool with pool_size=1 to guarantee single :memory: connection"""
        pool = SqlitePool(pool_size=1)
        yield pool
        pool.release_all()

    def test_full_workflow(self, sqlite_pool_single):
        """Test a realistic workflow using :memory:

        Uses pool_size=1 so all threads share the same in-memory database.
        With pool_size > 1, concurrent threads may get new :memory: connections
        that are independent databases.
        """

        # 1. Create table via exclusive transaction
        with sqlite_pool_single.exclusive_transaction(':memory:') as cursor:
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE
                )
            """)

        # 2. Insert data concurrently (must use pool_size=1 to share memory DB)
        def insert_user(user_id, name):
            with sqlite_pool_single.cursor(':memory:') as cursor:
                cursor.execute(
                    "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                    (user_id, name, f'{name.lower()}@example.com')
                )
                cursor.commit()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(insert_user, i, f'User{i}')
                for i in range(1, 11)
            ]
            for f in as_completed(futures):
                f.result()

        # 3. Query data
        with sqlite_pool_single.cursor(':memory:') as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM users")
            assert cursor.fetchone()['cnt'] == 10

        # 4. Update via exclusive transaction
        with sqlite_pool_single.exclusive_transaction(':memory:') as cursor:
            cursor.execute(
                "UPDATE users SET name = ? WHERE id = ?",
                ('Alice', 1)
            )

        # 5. Verify update
        with sqlite_pool_single.cursor(':memory:') as cursor:
            cursor.execute("SELECT name FROM users WHERE id = 1")
            assert cursor.fetchone()['name'] == 'Alice'

        # 6. GC and release
        sqlite_pool_single.gc(idle=0)
        sqlite_pool_single.release_all()
        assert len(sqlite_pool_single.all_pool) == 0

