"""
Concurrency safety tests for SqlitePool connection pool
Tests thread-safe operations, blocking behavior, and concurrent access
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Barrier, Semaphore, Thread

from oas.db.conn import ConnectionPool


class _NotifySpy:
    """Wraps ``ConnectionPool.notify_pool`` to record how the callers of a full pool wait.

    A caller that waits blocks in ``acquire(timeout=...)``: getting the lock
    means a connection was returned to the pool and offered its free slot. The
    timeout is ignored on purpose -- a caller that the pool does not wake stays
    blocked, so a pool that loses its wakeups leaves its callers behind and the
    test fails on the join, instead of passing by accident because the 10ms
    poll of the pool happened to serve them. ``queued`` is released once per
    call, so a test can wait until its callers are inside the wait path.

    Attributes:
        acquires (list): One entry per blocking acquire of the wait path
    """

    def __init__(self, lock, queued):
        self.lock = lock
        self.queued = queued
        self.acquires = []

    def acquire(self, blocking=True, timeout=-1):
        """Acquire the wrapped lock, counting the wait of the pool."""
        if blocking:
            self.acquires.append(None)
            self.queued.release()
        return self.lock.acquire(blocking)

    def release(self):
        """Release the wrapped lock."""
        self.lock.release()

    def locked(self):
        """Whether the wrapped lock is held, a free slot is on offer when it is not."""
        return self.lock.locked()

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


class TestPoolWaiterWakesUp:
    """A caller that queued on a full pool is woken by a returned connection."""

    # Small enough that the pool is held by the connections of the test
    POOL_SIZE = 2

    # More callers than connections: the pool hands its slots over one by one
    WAITERS = 4

    def test_queued_waiters_are_woken_not_polled(self, temp_db):
        """Every waiter is served by a returned connection, not by the 10ms poll.

        The pool is held by the connections of the test while the waiters
        queue, and the spy of the test blocks a caller that nothing wakes, so
        every waiter has to be woken by a connection that returns to the pool.
        The falling version of the pool offered a free slot to its first
        waiter only, the rest of the waiters were served by the 10ms poll of
        the pool and are left behind here.
        """
        pool = ConnectionPool(temp_db, pool_size=self.POOL_SIZE)
        spy = _NotifySpy(pool.notify_pool, Semaphore(0))
        pool.notify_pool = spy

        served = []
        try:
            # hold every connection of the pool
            held = [pool.cursor() for _ in range(self.POOL_SIZE)]
            assert not pool.idle_workers, 'the pool is not full'

            def waiter():
                with pool.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    served.append(cursor.fetchone())

            # Daemon threads: a waiter that a lost wakeup leaves behind must not
            # hold the interpreter at exit, the test has to fail and not hang
            threads = [Thread(target=waiter, daemon=True) for _ in range(self.WAITERS)]
            for thread in threads:
                thread.start()
            # every waiter is inside the wait path, none of them is served yet
            for _ in range(self.WAITERS):
                assert spy.queued.acquire(timeout=5), 'a waiter never reached the pool'
            assert not served, 'a waiter was served while the pool was held'

            # returning the connections must wake the waiters
            for cursor in held:
                cursor.close()
            for thread in threads:
                thread.join(timeout=10)
                assert not thread.is_alive(), (
                    f'a waiter was left behind: the connection that returned to the pool did not'
                    f' wake it ({len(served)} of {self.WAITERS} waiters were served)')
        finally:
            pool.release_all()

        assert len(served) == self.WAITERS
