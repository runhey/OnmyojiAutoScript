"""
Resource management tests for SqlitePool connection pool
Tests garbage collection, connection release, and resource cleanup
"""
import os
import time
from threading import Barrier, Thread

from conftest import TEST_DATA_DIR

# ============================================================================
# Test Resource Management
# ============================================================================


class TestResourceManagement:
    """Test resource management"""

    def test_gc_closes_idle_connections(self, pool):
        """Test GC closes idle connections"""
        # Create multiple connections by holding them simultaneously
        # Use barrier to ensure true concurrent creation
        barrier = Barrier(4)  # 3 worker threads + 1 main thread
        cursors = []

        def create_and_hold():
            barrier.wait()  # Wait for all threads ready
            cursor = pool.cursor()
            cursor.execute("SELECT 1")
            cursors.append(cursor)

        threads = [Thread(target=create_and_hold) for _ in range(3)]
        for t in threads:
            t.start()

        barrier.wait()  # Main thread joins the barrier
        for t in threads:
            t.join()

        # Now we have 3 different connections
        assert len(pool.all_workers) == 3

        # Close all cursors to return connections to pool
        for cursor in cursors:
            cursor.close()

        assert len(pool.idle_workers) == 3

        # Wait for connections to become idle
        time.sleep(0.1)

        # Execute GC (idle time set to 0 seconds)
        pool.gc(idle=0)

        # All connections should be closed
        assert len(pool.all_workers) == 0
        assert len(pool.idle_workers) == 0

    def test_gc_keeps_active_connections(self, pool):
        """Test GC keeps active connections"""
        # Create a connection
        with pool.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Execute GC immediately (idle time set to 60 seconds)
        pool.gc(idle=60)

        # Connection should not be closed
        assert len(pool.all_workers) == 1

    def test_release_all(self, pool):
        """Test releasing all connections"""
        # Create multiple connections by holding them simultaneously
        barrier = Barrier(4)  # 3 worker threads + 1 main thread
        cursors = []

        def create_and_hold():
            barrier.wait()  # Wait for all threads ready
            cursor = pool.cursor()
            cursor.execute("SELECT 1")
            cursors.append(cursor)

        threads = [Thread(target=create_and_hold) for _ in range(3)]
        for t in threads:
            t.start()

        barrier.wait()  # Main thread joins the barrier
        for t in threads:
            t.join()

        # Now we have 3 different connections
        assert len(pool.all_workers) == 3

        # Release all connections
        pool.release_all()

        assert len(pool.all_workers) == 0
        assert len(pool.idle_workers) == 0
        assert len(pool.last_use) == 0


# ============================================================================
# Test SqlitePool Resource Management
# ============================================================================

class TestSqlitePoolResourceManagement:
    """Test SqlitePool resource management"""

    def test_gc_removes_empty_pools(self, sqlite_pool, temp_db):
        """Test GC removes empty pools"""
        # Use connection pool
        with sqlite_pool.cursor(temp_db) as cursor:
            cursor.execute("SELECT 1")

        assert temp_db in sqlite_pool.all_pool

        # Wait and execute GC
        time.sleep(0.1)
        sqlite_pool.gc(idle=0)

        # Empty pool should be deleted
        assert temp_db not in sqlite_pool.all_pool

    def test_delete_file(self, sqlite_pool):
        """Test deleting file"""
        db_path = os.path.join(TEST_DATA_DIR, 'test_delete.db')

        # Create and use database
        with sqlite_pool.cursor(db_path) as cursor:
            # Drop table if exists from previous failed test
            cursor.execute("DROP TABLE IF EXISTS test")
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.commit()

        assert os.path.exists(db_path)
        assert db_path in sqlite_pool.all_pool

        # Delete file
        result = sqlite_pool.delete_file(db_path)

        assert result is True
        assert not os.path.exists(db_path)
        assert db_path not in sqlite_pool.all_pool

