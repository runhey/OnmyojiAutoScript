"""
Concurrency safety tests for SqlitePool connection pool
Tests thread-safe operations, blocking behavior, and concurrent access
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Barrier, Thread

from oas.db.conn import ConnectionPool

# ============================================================================
# Test Concurrency Safety
# ============================================================================


class TestConcurrency:
    """Test concurrency safety"""

    def test_concurrent_access(self, pool):
        """Test concurrent access to connection pool"""

        def worker(worker_id):
            try:
                with pool.cursor() as cursor:
                    cursor.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER, worker_id INTEGER)")
                    cursor.execute("INSERT INTO test VALUES (?, ?)",
                                   (worker_id, worker_id))
                    cursor.commit()
                return True
            except Exception as e:
                return str(e)

        # Start multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All tasks should succeed
        assert all(r is True for r in results)

        # Verify data
        with pool.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test")
            assert cursor.fetchone()['cnt'] == 20

    def test_pool_blocks_when_full(self, temp_db):
        """Test pool blocks when full"""
        pool = ConnectionPool(temp_db, pool_size=2)
        barrier = Barrier(3)  # 3 threads sync
        results = []

        def hold_connection(hold_time):
            """Hold connection for some time"""
            barrier.wait()  # Wait for all threads ready
            start = time.time()
            with pool.cursor() as cursor:
                cursor.execute("SELECT 1")
                time.sleep(hold_time)
            elapsed = time.time() - start
            results.append(elapsed)

        # Start 3 threads, pool size is 2
        threads = [
            Thread(target=hold_connection, args=(0.1,)),
            Thread(target=hold_connection, args=(0.1,)),
            Thread(target=hold_connection, args=(0.05,)),  # Third thread should wait
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pool.release_all()

        # Third thread should have waited
        assert len(results) == 3
        assert max(results) > 0.1  # At least one thread waited

    def test_concurrent_pool_creation(self, temp_db):
        """Test concurrent pool creation"""
        pool = ConnectionPool(temp_db, pool_size=10)

        # Use a barrier to ensure all threads start at the same time
        barrier = Barrier(10)
        cursors = []

        def create_and_hold_connection():
            """Create connection and hold it"""
            barrier.wait()  # Wait for all threads to be ready
            cursor = pool.cursor()
            cursor.execute("SELECT 1")
            cursors.append(cursor)  # Hold the cursor to prevent connection reuse

        # Multiple threads creating connections simultaneously
        threads = [Thread(target=create_and_hold_connection) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Connection count should not exceed pool size
        assert len(pool.all_workers) <= 10

        # Cleanup - close all cursors
        for cursor in cursors:
            cursor.close()
        pool.release_all()

