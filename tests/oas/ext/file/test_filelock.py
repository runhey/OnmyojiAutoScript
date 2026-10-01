import gc
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from oas.ext.env import OAS_ROOT
from oas.ext.file.filelock import FilelockTimeout, SQLiteFileLock
from oas.ext.path import PathStr

CHILD_HOLD = (
    "import os, sys, time\n"
    "from oas.ext.file.filelock import SQLiteFileLock\n"
    "lock = SQLiteFileLock(sys.argv[1], timeout=0)\n"
    "lock.acquire()\n"
    "print('HELD', flush=True)\n"
    "flag = sys.argv[2]\n"
    "for _ in range(500):\n"
    "    if os.path.exists(flag):\n"
    "        break\n"
    "    time.sleep(0.02)\n"
    "lock.release()\n"
)


@pytest.fixture(scope="module")
def lock_dir():
    """
    Real filesystem directory for the SQLite lock tests.

    SQLite opens its database file in the C layer, so the in-memory fake
    filesystem cannot intercept it: the lock tests need a real directory.
    The directory lives under the repo's temp/ folder and is removed after
    the module finishes.
    """
    path = PathStr.new(OAS_ROOT).joinpath('temp/filelock')
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


class TestFilelockTimeout:
    """Test cases for the FilelockTimeout exception"""

    def test_exception_message_and_lock_file(self, lock_dir):
        """FilelockTimeout should carry the lock file path in its message and attribute"""
        lock_file = os.path.abspath(lock_dir / "a.lock")
        with pytest.raises(FilelockTimeout, match="Timeout occurred trying to acquire lock") as excinfo:
            raise FilelockTimeout(lock_file)
        assert excinfo.value.lock_file == lock_file


class TestProperties:
    """Test cases for the constructor and properties"""

    def test_lock_file_is_absolute(self, lock_dir):
        """lock_file should be the absolute path"""
        lock = SQLiteFileLock(lock_dir / "sub" / "a.lock")
        assert lock.lock_file == os.path.abspath(str(lock_dir / "sub" / "a.lock"))

    def test_default_timeout_get_and_set(self, lock_dir):
        """timeout should store the constructor value and be mutable"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0.5)
        assert lock.timeout == 0.5
        lock.timeout = 1.5
        assert lock.timeout == 1.5

    @pytest.mark.parametrize("lock_file", ["a.lock", Path("a.lock")])
    def test_accepts_str_and_path(self, lock_dir, lock_file):
        """Constructor should accept both str and Path lock files"""
        lock = SQLiteFileLock(os.path.join(lock_dir, lock_file), timeout=0)
        assert lock.lock_file == os.path.abspath(str(lock_dir / "a.lock"))

    def test_initial_state(self, lock_dir):
        """A new lock should not be locked"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        assert not lock.is_locked

    @pytest.mark.parametrize("lock_file", [":memory:", Path(":memory:")])
    def test_rejects_memory_database(self, lock_file):
        """Constructor should reject the in-memory database, the lock is on a file"""
        with pytest.raises(ValueError):
            SQLiteFileLock(lock_file)


class TestAcquireRelease:
    """Test cases for acquire() and release()"""

    def test_acquire_returns_self(self, lock_dir):
        """acquire() should return self, matching the filelock interface"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        assert lock.acquire() is lock
        lock.release()

    def test_acquire_and_release(self, lock_dir):
        """is_locked should be True after acquire and False after release"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock.acquire()
        assert lock.is_locked
        lock.release()
        assert not lock.is_locked

    def test_acquire_creates_parent_directory(self, lock_dir):
        """Parent directories of the lock file should be created automatically"""
        lock = SQLiteFileLock(lock_dir / "nested" / "dir" / "a.lock", timeout=0)
        lock.acquire()
        assert lock.is_locked
        lock.release()

    def test_release_without_acquire_is_noop(self, lock_dir):
        """release() should do nothing when the lock is not held"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock.release()
        assert not lock.is_locked
        lock.release(force=True)
        assert not lock.is_locked

    def test_acquire_accepts_poll_interval(self, lock_dir):
        """poll_interval should be accepted for filelock interface compatibility"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        assert lock.acquire(poll_interval=0.1) is lock
        lock.release()


class TestReentrant:
    """Test cases for reentrant locking on the same instance"""

    def test_multiple_acquire_counts(self, lock_dir):
        """Each acquire() should increase the counter and each release() decrease it"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock.acquire()
        lock.acquire()
        lock.acquire()
        assert lock.is_locked
        lock.release()
        assert lock.is_locked
        lock.release()
        assert lock.is_locked
        lock.release()
        assert not lock.is_locked

    def test_reentrant_acquire_does_not_block(self, lock_dir):
        """A second acquire() on the same instance should succeed even with timeout=0"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock.acquire()
        assert lock.acquire() is lock
        lock.release()
        lock.release()

    def test_force_release(self, lock_dir):
        """release(force=True) should release the lock immediately, ignoring the counter"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock.acquire()
        lock.acquire()
        lock.release(force=True)
        assert not lock.is_locked


class TestExclusion:
    """Test cases for mutual exclusion between instances"""

    def test_timeout_zero_is_non_blocking(self, lock_dir):
        """acquire() with timeout=0 should fail fast with FilelockTimeout when the lock is busy"""
        lock_file = lock_dir / "a.lock"
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock1.acquire()
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout) as excinfo:
                lock2.acquire()
            elapsed = time.monotonic() - start
            assert excinfo.value.lock_file == lock1.lock_file
            assert elapsed < 0.5
        finally:
            lock1.release()

    def test_positive_timeout_waits_then_raises(self, lock_dir):
        """acquire() with a positive timeout should wait and then raise FilelockTimeout"""
        lock_file = lock_dir / "a.lock"
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0.2)
        lock1.acquire()
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                lock2.acquire()
            elapsed = time.monotonic() - start
            assert elapsed >= 0.15
        finally:
            lock1.release()

    def test_acquire_after_release(self, lock_dir):
        """Another instance should acquire the lock once the holder releases it"""
        lock_file = lock_dir / "a.lock"
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock1.acquire()
        lock1.release()
        lock2.acquire()
        assert lock2.is_locked
        lock2.release()

    def test_different_files_do_not_conflict(self, lock_dir):
        """Locks on different files should not block each other"""
        lock1 = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        lock2 = SQLiteFileLock(lock_dir / "b.lock", timeout=0)
        lock1.acquire()
        lock2.acquire()
        assert lock1.is_locked
        assert lock2.is_locked
        lock1.release()
        lock2.release()

    def test_unrelated_operational_error_is_reraisied(self, lock_dir):
        """OperationalError not related to locking should be propagated as is"""
        dir_path = lock_dir / "adir"
        os.mkdir(dir_path)
        lock = SQLiteFileLock(dir_path, timeout=0)
        with pytest.raises(sqlite3.OperationalError):
            lock.acquire()


class TestDefaultTimeout:
    """Test cases for the default timeout"""

    def test_constructor_timeout_is_used(self, lock_dir):
        """acquire() without a timeout should use the constructor timeout"""
        lock_file = lock_dir / "a.lock"
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0.2)
        lock1.acquire()
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                lock2.acquire()
            assert time.monotonic() - start >= 0.15
        finally:
            lock1.release()

    def test_acquire_timeout_overrides_constructor(self, lock_dir):
        """acquire(timeout=...) should override the constructor timeout"""
        lock_file = lock_dir / "a.lock"
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        # Constructor timeout is 0, but the override should make acquire() wait
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock1.acquire()
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                lock2.acquire(timeout=0.2)
            assert time.monotonic() - start >= 0.15
        finally:
            lock1.release()


class TestContextManager:
    """Test cases for the context manager protocol"""

    def test_context_manager(self, lock_dir):
        """The lock should be acquired on enter and released on exit"""
        lock = SQLiteFileLock(lock_dir / "a.lock", timeout=0)
        with lock as acquired:
            assert acquired is lock
            assert lock.is_locked
        assert not lock.is_locked

    def test_release_on_exception(self, lock_dir):
        """The lock should be released even when the block raises"""
        lock_file = lock_dir / "a.lock"
        with pytest.raises(RuntimeError), SQLiteFileLock(lock_file, timeout=0):
            raise RuntimeError("boom")
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock2.acquire()
        lock2.release()


class TestThreads:
    """Test cases for locking across threads"""

    def test_exclusion_between_threads(self, lock_dir):
        """A thread should not acquire a lock held by another thread"""
        lock_file = lock_dir / "a.lock"
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=0)
        holder.acquire()
        results = []

        def try_acquire():
            try:
                contender.acquire()
            except FilelockTimeout:
                results.append("timeout")
            else:
                results.append("acquired")

        thread = threading.Thread(target=try_acquire)
        thread.start()
        thread.join(timeout=10)
        holder.release()
        assert not thread.is_alive()
        assert results == ["timeout"]

    def test_thread_waits_until_release(self, lock_dir):
        """A thread should acquire the lock once the holder releases it"""
        lock_file = lock_dir / "a.lock"
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=5)
        holder.acquire()
        results = []
        started = threading.Event()

        def try_acquire():
            started.set()
            with contender:
                results.append("acquired")

        thread = threading.Thread(target=try_acquire)
        thread.start()
        # Wait until the contender thread is about to acquire, then release
        assert started.wait(timeout=10)
        holder.release()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert results == ["acquired"]

    def test_concurrent_acquire_on_same_instance(self, lock_dir):
        """Concurrent acquires on the same instance must race on the SQLite lock,
        each thread failing on its own timeout budget without waiting for others"""
        lock_file = lock_dir / "a.lock"
        holder = SQLiteFileLock(lock_file, timeout=0)
        shared = SQLiteFileLock(lock_file, timeout=0)
        holder.acquire()
        results = []
        c_elapsed = []
        b_started = threading.Event()

        def thread_b():
            b_started.set()
            # Waits 0.5s on the SQLite lock
            try:
                shared.acquire(timeout=0.5)
            except FilelockTimeout:
                results.append("b:timeout")

        def thread_c():
            # Non-blocking, must fail fast even though thread B is also waiting
            start = time.monotonic()
            try:
                shared.acquire(timeout=0)
            except FilelockTimeout:
                c_elapsed.append(time.monotonic() - start)
                results.append("c:timeout")

        b = threading.Thread(target=thread_b)
        c = threading.Thread(target=thread_c)
        b.start()
        # Wait until thread B has started its acquire
        assert b_started.wait(timeout=10)
        c.start()
        c.join(timeout=10)
        b.join(timeout=10)
        holder.release()
        assert not c.is_alive()
        assert not b.is_alive()
        assert results == ["c:timeout", "b:timeout"]
        # Thread C must not wait for thread B's SQLite wait to finish
        assert c_elapsed[0] < 0.3

    def test_concurrent_acquire_has_single_winner(self, lock_dir):
        """Concurrent acquires on the same instance must yield exactly one winner,
        the loser timing out on its own budget"""
        lock_file = lock_dir / "a.lock"
        holder = SQLiteFileLock(lock_file, timeout=0)
        # Loser budget 0.2s must be shorter than the winner's hold time of 0.5s
        shared = SQLiteFileLock(lock_file, timeout=0.01)
        holder.acquire()
        results = []
        b_started = threading.Event()
        c_started = threading.Event()

        def try_acquire(tag, started):
            started.set()
            try:
                with shared:
                    results.append(f"{tag}:acquired")
                    # Hold the lock long enough to force the loser to time out
                    time.sleep(0.5)
            except FilelockTimeout:
                results.append(f"{tag}:timeout")

        b = threading.Thread(target=try_acquire, args=("b", b_started))
        c = threading.Thread(target=try_acquire, args=("c", c_started))
        b.start()
        c.start()
        # Wait until both threads have started their acquire, then release
        assert b_started.wait(timeout=10)
        assert c_started.wait(timeout=10)
        holder.release()
        b.join(timeout=10)
        c.join(timeout=10)
        assert not b.is_alive()
        assert not c.is_alive()
        winners = [r for r in results if r.endswith(":acquired")]
        losers = [r for r in results if r.endswith(":timeout")]
        assert len(winners) == 1
        assert len(losers) == 1


class TestCrossProcess:
    """Test cases for locking across processes"""

    def test_exclusion_between_processes(self, lock_dir):
        """A child process should not acquire a lock held by the parent"""
        lock_file = lock_dir / "a.lock"
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()
        code = (
            "import sys\n"
            "from oas.ext.file.filelock import SQLiteFileLock, FilelockTimeout\n"
            "try:\n"
            "    with SQLiteFileLock(sys.argv[1], timeout=0.5):\n"
            "        print('ACQUIRED')\n"
            "except FilelockTimeout:\n"
            "    print('TIMEOUT')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(lock_file)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=OAS_ROOT,
        )
        lock.release()
        assert result.returncode == 0
        assert "TIMEOUT" in result.stdout

    def test_parent_acquires_after_child_release(self, lock_dir):
        """The parent should acquire the lock after the child process releases it"""
        lock_file = lock_dir / "a.lock"
        flag_file = lock_dir / "release.flag"
        proc = subprocess.Popen(
            [sys.executable, "-c", CHILD_HOLD, str(lock_file), str(flag_file)],
            stdout=subprocess.PIPE,
            text=True,
            cwd=OAS_ROOT,
        )
        try:
            assert proc.stdout.readline().strip() == "HELD"
            flag_file.touch()
            lock = SQLiteFileLock(lock_file, timeout=10)
            lock.acquire()
            assert lock.is_locked
            lock.release()
        finally:
            proc.wait(timeout=10)
            proc.kill()


class TestDestructor:
    """Test cases for the destructor fallback"""

    def test_del_releases_lock(self, lock_dir):
        """Destroying the lock object should release the underlying lock"""
        lock_file = lock_dir / "a.lock"
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()
        del lock
        gc.collect()
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock2.acquire()
        lock2.release()
