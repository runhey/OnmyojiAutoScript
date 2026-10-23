"""
Basic functionality tests for SqlitePool connection pool
Coverage: connection creation, cursor operations, auto-create table, pool management,
          exclusive transactions, SqlitePool operations, error handling, edge cases
"""

import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from conftest import TEST_DATA_DIR

from oas.db.conn import SQLITE_POOL, ConnectionPool, SqlitePool

# ============================================================================
# Test ConnectionPool.new_conn and set_conn_pragma
# ============================================================================


class TestConnectionCreation:
    """Test connection creation"""

    def test_new_conn_creates_connection(self, temp_db):
        """Test creating new connection"""
        conn = ConnectionPool.new_conn(temp_db)
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_new_conn_creates_directory(self, temp_db_in_subdir):
        """Test auto-creating non-existent directory"""
        conn = ConnectionPool.new_conn(temp_db_in_subdir)
        assert os.path.exists(temp_db_in_subdir)
        conn.close()

    def test_set_conn_pragma(self, temp_db):
        """Test setting connection properties"""
        conn = sqlite3.connect(temp_db)
        ConnectionPool.set_conn_pragma(conn)
        assert conn.row_factory == sqlite3.Row
        conn.close()


# ============================================================================
# Test SqlitePoolCursor basic functionality
# ============================================================================


class TestSqlitePoolCursor:
    """Test cursor basic functionality"""

    def test_cursor_execute(self, pool):
        """Test executing SQL"""
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER, name TEXT)')
            cursor.execute("INSERT INTO test VALUES (1, 'Alice')")
            cursor.commit()

        # Verify data
        with pool.cursor() as cursor:
            cursor.execute('SELECT * FROM test')
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]['id'] == 1
            assert rows[0]['name'] == 'Alice'

    def test_cursor_with_statement(self, pool):
        """Test cursor auto-closing with 'with' statement"""
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()

        # Cursor should be closed, connection should be returned to pool
        assert len(pool.idle_workers) == 1

    def test_cursor_commit_method(self, pool):
        """Test cursor's commit method"""
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.execute('INSERT INTO test VALUES (1)')
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 1


# ============================================================================
# Test auto-create table functionality
# ============================================================================


class TestAutoCreateTable:
    """Test auto-create table"""

    def test_create_table_with_table_name(self, pool):
        """Test creating table with TABLE_NAME placeholder"""
        with pool.cursor() as cursor:
            cursor.TABLE_NAME = 'users'
            cursor.CREATE_TABLE = 'CREATE TABLE {TABLE_NAME} (id INTEGER, name TEXT)'
            cursor.execute("INSERT INTO users VALUES (1, 'Bob')")
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT * FROM users')
            assert len(cursor.fetchall()) == 1

    def test_create_table_without_placeholder(self, pool):
        """Test creating table without placeholder"""
        with pool.cursor() as cursor:
            cursor.CREATE_TABLE = 'CREATE TABLE products (id INTEGER, price REAL)'
            cursor.execute('INSERT INTO products VALUES (1, 9.99)')
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT * FROM products')
            assert len(cursor.fetchall()) == 1

    def test_create_table_already_exists(self, pool):
        """Test no error when table already exists"""
        # First creation
        with pool.cursor() as cursor:
            cursor.CREATE_TABLE = 'CREATE TABLE test (id INTEGER)'
            cursor.execute('INSERT INTO test VALUES (1)')
            cursor.commit()

        # Second attempt should not error
        with pool.cursor() as cursor:
            cursor.CREATE_TABLE = 'CREATE TABLE test (id INTEGER)'
            cursor.execute('INSERT INTO test VALUES (2)')
            cursor.commit()

        # Verify both records exist
        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 2

    def test_executemany_auto_create_table(self, pool):
        """Test executemany can also auto-create table"""
        with pool.cursor() as cursor:
            cursor.CREATE_TABLE = 'CREATE TABLE items (id INTEGER, value TEXT)'
            cursor.executemany(
                'INSERT INTO items VALUES (?, ?)', [(1, 'a'), (2, 'b'), (3, 'c')]
            )
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM items')
            assert cursor.fetchone()['cnt'] == 3


# ============================================================================
# Test connection pool management
# ============================================================================


class TestConnectionPoolManagement:
    """Test connection pool management"""

    def test_connection_reuse(self, pool):
        """Test connection reuse"""
        # First use
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()
            conn1 = cursor.connection

        # Second use should reuse same connection
        with pool.cursor() as cursor:
            cursor.execute('SELECT * FROM test')
            conn2 = cursor.connection

        assert conn1 is conn2

    def test_pool_size_limit(self, temp_db):
        """Test connection pool size limit"""
        pool = ConnectionPool(temp_db, pool_size=2)
        cursors = []

        # Occupy all connections
        for _ in range(2):
            cursor = pool.cursor()
            cursor.execute('SELECT 1')
            cursors.append(cursor)

        assert len(pool.all_workers) == 2
        assert len(pool.idle_workers) == 0

        # Cleanup
        for cursor in cursors:
            cursor.close()
        pool.release_all()

    def test_last_use_tracking(self, pool):
        """Test last use time tracking"""
        before_time = time.time()

        with pool.cursor() as cursor:
            cursor.execute('SELECT 1')
            conn = cursor.connection

        after_time = time.time()

        # Check last_use time is in reasonable range
        assert conn in pool.last_use
        assert before_time <= pool.last_use[conn] <= after_time


# ============================================================================
# Test ExclusiveTransaction
# ============================================================================


class TestExclusiveTransaction:
    """Test exclusive transaction"""

    def test_exclusive_transaction_commit(self, pool):
        """Test exclusive transaction successful commit"""
        with pool.exclusive_transaction() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.execute('INSERT INTO test VALUES (1)')

        # Verify data is committed
        with pool.cursor() as cursor:
            cursor.execute('SELECT * FROM test')
            assert len(cursor.fetchall()) == 1

    def test_exclusive_transaction_rollback(self, pool):
        """Test exclusive transaction rollback on exception"""
        # First create table
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()

        # Exception in transaction
        try:
            with pool.exclusive_transaction() as cursor:
                cursor.execute('INSERT INTO test VALUES (1)')
                raise ValueError('Test error')
        except ValueError:
            pass

        # Verify data is not committed
        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 0

    def test_exclusive_transaction_is_exclusive(self, pool):
        """Test exclusive transaction is truly exclusive"""
        from threading import Barrier, Thread

        # Create table
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()

        results = []
        barrier = Barrier(2)

        def writer_exclusive():
            """Write using exclusive transaction"""
            barrier.wait()
            start = time.time()
            with pool.exclusive_transaction() as cursor:
                cursor.execute('INSERT INTO test VALUES (1)')
                time.sleep(0.2)  # Hold lock for some time
            elapsed = time.time() - start
            results.append(('exclusive', elapsed))

        def writer_normal():
            """Write using normal cursor"""
            barrier.wait()
            start = time.time()
            time.sleep(
                0.05
            )  # Slight delay to let exclusive transaction acquire lock first
            with pool.cursor() as cursor:
                cursor.execute('INSERT INTO test VALUES (2)')
                cursor.commit()
            elapsed = time.time() - start
            results.append(('normal', elapsed))

        # Start two threads
        t1 = Thread(target=writer_exclusive)
        t2 = Thread(target=writer_normal)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Verify both records are written
        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 2

        # Normal write should wait for exclusive transaction to complete
        normal_time = [r[1] for r in results if r[0] == 'normal'][0]
        assert normal_time > 0.15  # Should have waited at least 0.15 seconds


# ============================================================================
# Test SqlitePool
# ============================================================================


class TestSqlitePool:
    """Test SqlitePool"""

    def test_get_pool_creates_pool(self, sqlite_pool, temp_db):
        """Test getting connection pool"""
        pool = sqlite_pool.get_pool(temp_db)
        assert isinstance(pool, ConnectionPool)
        assert temp_db in sqlite_pool.all_pool

    def test_get_pool_reuses_pool(self, sqlite_pool, temp_db):
        """Test connection pool reuse"""
        pool1 = sqlite_pool.get_pool(temp_db)
        pool2 = sqlite_pool.get_pool(temp_db)
        assert pool1 is pool2

    def test_cursor_method(self, sqlite_pool, temp_db):
        """Test cursor method"""
        with sqlite_pool.cursor(temp_db) as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()

        with sqlite_pool.cursor(temp_db) as cursor:
            cursor.execute('SELECT * FROM test')
            cursor.fetchall()

    def test_exclusive_transaction_method(self, sqlite_pool, temp_db):
        """Test exclusive_transaction method"""
        with sqlite_pool.exclusive_transaction(temp_db) as cursor:
            # Drop table if exists from previous failed test
            cursor.execute('DROP TABLE IF EXISTS test')
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.execute('INSERT INTO test VALUES (1)')

        with sqlite_pool.cursor(temp_db) as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 1

    def test_multiple_databases(self, sqlite_pool):
        """Test managing multiple databases"""
        db1 = os.path.join(TEST_DATA_DIR, 'db1.db')
        db2 = os.path.join(TEST_DATA_DIR, 'db2.db')

        try:
            # Access two different databases
            with sqlite_pool.cursor(db1) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute('DROP TABLE IF EXISTS test')
                cursor.execute('CREATE TABLE test (id INTEGER)')
                cursor.execute('INSERT INTO test VALUES (1)')
                cursor.commit()

            with sqlite_pool.cursor(db2) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute('DROP TABLE IF EXISTS test')
                cursor.execute('CREATE TABLE test (id INTEGER)')
                cursor.execute('INSERT INTO test VALUES (2)')
                cursor.commit()

            # Verify two databases are independent
            with sqlite_pool.cursor(db1) as cursor:
                cursor.execute('SELECT id FROM test')
                assert cursor.fetchone()['id'] == 1

            with sqlite_pool.cursor(db2) as cursor:
                cursor.execute('SELECT id FROM test')
                assert cursor.fetchone()['id'] == 2
        finally:
            # Cleanup - wait for Windows file locks
            sqlite_pool.release_all()
            time.sleep(0.05)
            for db_path in [db1, db2]:
                try:
                    os.unlink(db_path)
                except FileNotFoundError, PermissionError, OSError:
                    pass


# ============================================================================
# Test error handling
# ============================================================================


class TestErrorHandling:
    """Test error handling"""

    def test_uncommitted_transaction_warning(self, pool, caplog):
        """Test warning for uncommitted transaction"""
        with pool.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS test')
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.execute('BEGIN')
            cursor.execute('INSERT INTO test VALUES (1)')
            # Don't commit, just close

        # Should have error log (requires actual logging system)
        # Here we just verify no crash

    def test_sql_error_propagation(self, pool):
        """Test SQL error is properly propagated"""
        with pytest.raises(sqlite3.OperationalError):
            with pool.cursor() as cursor:
                cursor.execute('SELECT * FROM non_existent_table')


# ============================================================================
# Test global singleton
# ============================================================================


class TestGlobalSingleton:
    """Test global SQLITE_POOL"""

    def test_sqlite_pool_singleton_exists(self):
        """Test global singleton exists"""
        assert SQLITE_POOL is not None
        assert isinstance(SQLITE_POOL, SqlitePool)

    def test_sqlite_pool_singleton_usable(self):
        """Test global singleton is usable"""
        db_path = os.path.join(TEST_DATA_DIR, 'singleton_test.db')

        try:
            with SQLITE_POOL.cursor(db_path) as cursor:
                # Drop table if exists from previous failed test
                cursor.execute('DROP TABLE IF EXISTS test')
                cursor.execute('CREATE TABLE test (id INTEGER)')
                cursor.execute('INSERT INTO test VALUES (1)')
                cursor.commit()

            with SQLITE_POOL.cursor(db_path) as cursor:
                cursor.execute('SELECT * FROM test')
                rows = cursor.fetchall()
                assert len(rows) == 1
        finally:
            # Cleanup - ensure connection is released
            time.sleep(0.05)
            try:
                os.unlink(db_path)
            except FileNotFoundError, PermissionError, OSError:
                pass


# ============================================================================
# Test edge cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases"""

    def test_empty_cursor_operations(self, pool):
        """Test empty operations"""
        with pool.cursor() as cursor:
            pass  # Do nothing

        # Should close normally
        assert len(pool.idle_workers) == 1

    def test_multiple_commits(self, pool):
        """Test multiple commits"""
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            cursor.commit()
            cursor.execute('INSERT INTO test VALUES (1)')
            cursor.commit()
            cursor.execute('INSERT INTO test VALUES (2)')
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 2

    def test_nested_cursors(self, pool):
        """Test nested cursors (not recommended but should work)"""
        with pool.cursor() as cursor1:
            cursor1.execute('CREATE TABLE test (id INTEGER)')
            cursor1.commit()

            with pool.cursor() as cursor2:
                cursor2.execute('INSERT INTO test VALUES (1)')
                cursor2.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 1

    def test_very_long_query(self, pool):
        """Test long-running query"""
        with pool.cursor() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER)')
            # Insert large amount of data
            values = [(i,) for i in range(1000)]
            cursor.executemany('INSERT INTO test VALUES (?)', values)
            cursor.commit()

        with pool.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM test')
            assert cursor.fetchone()['cnt'] == 1000


# ============================================================================
# Integration test
# ============================================================================


class TestIntegration:
    """Integration test"""

    def test_realistic_workflow(self, sqlite_pool):
        """Test realistic workflow"""
        db_path = os.path.join(TEST_DATA_DIR, 'app.db')

        try:
            # 0. Drop table if exists from previous failed test
            with sqlite_pool.cursor(db_path) as cursor:
                cursor.execute('DROP TABLE IF EXISTS users')
                cursor.commit()

            # 1. Create table
            with sqlite_pool.cursor(db_path) as cursor:
                cursor.CREATE_TABLE = """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE
                    )
                """
                cursor.execute(
                    'INSERT INTO users (name, email) VALUES (?, ?)',
                    ('Alice', 'alice@example.com'),
                )
                cursor.commit()

            # 2. Concurrent insert data
            def insert_user(user_id, name):
                with sqlite_pool.cursor(db_path) as cursor:
                    cursor.execute(
                        'INSERT INTO users (id, name, email) VALUES (?, ?, ?)',
                        (user_id, name, f'{name.lower()}@example.com'),
                    )
                    cursor.commit()

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(insert_user, i, f'User{i}') for i in range(2, 12)
                ]
                for f in as_completed(futures):
                    f.result()

            # 3. Query data
            with sqlite_pool.cursor(db_path) as cursor:
                cursor.execute('SELECT COUNT(*) as cnt FROM users')
                assert cursor.fetchone()['cnt'] == 11

            # 4. Use exclusive transaction to update
            with sqlite_pool.exclusive_transaction(db_path) as cursor:
                cursor.execute(
                    'UPDATE users SET name = ? WHERE id = ?', ('Alice Updated', 1)
                )

            # 5. Verify update
            with sqlite_pool.cursor(db_path) as cursor:
                cursor.execute('SELECT name FROM users WHERE id = 1')
                assert cursor.fetchone()['name'] == 'Alice Updated'

            # 6. Cleanup
            sqlite_pool.gc(idle=0)
        finally:
            # Ensure all connections are released before deleting
            sqlite_pool.release_all()
            time.sleep(0.05)
            try:
                os.unlink(db_path)
            except FileNotFoundError, PermissionError, OSError:
                pass
