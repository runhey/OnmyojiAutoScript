import gc
import os
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from oas.ext import env
from oas.ext.file.filelock import FilelockTimeout, SQLiteFileLock
from oas.ext.path.atomic import folder_rmtree

CHILD_HOLD = (
    'import os, sys, time\n'
    'from oas.ext.file.filelock import SQLiteFileLock\n'
    'lock = SQLiteFileLock(sys.argv[1], timeout=0)\n'
    'lock.acquire()\n'
    "print('HELD', flush=True)\n"
    'flag = sys.argv[2]\n'
    'for _ in range(500):\n'
    '    if os.path.exists(flag):\n'
    '        break\n'
    '    time.sleep(0.02)\n'
    'lock.release()\n'
)


@pytest.fixture
def lock_dir():
    """
    Real filesystem directory for the SQLite lock tests.

    SQLite opens its database file in the C layer, so the in-memory fake
    filesystem cannot intercept it: the lock tests need a real directory.

    Every test gets its own directory under the repo's temp/ folder, named
    with the process id and a random suffix. Concurrent pytest workers (and
    directories left behind by an interrupted run) therefore never share a
    lock file, while a test still sees a clean directory.

    Returns:
        PathStr: Path of the directory, removed when the test finishes
    """
    path = env.OAS_TEMP.joinpath(f'filelock_{os.getpid()}_{uuid.uuid4().hex[:8]}')
    os.makedirs(path)
    yield path
    folder_rmtree(path)


def hold_in_worker(lock):
    """
    Acquire a lock in another thread and hold it until the release event is set.

    A second thread of the same process waits for the lock through SQLite: a
    second acquire of the holding thread would be a reentrancy error instead.

    Args:
        lock (SQLiteFileLock): The lock to acquire and hold

    Returns:
        tuple[threading.Thread, threading.Event]: The started thread, and the
            event that releases the lock (join the thread after setting it)
    """
    acquired = threading.Event()
    release = threading.Event()

    def hold():
        lock.acquire()
        acquired.set()
        release.wait(timeout=10)
        lock.release()

    thread = threading.Thread(target=hold)
    thread.start()
    assert acquired.wait(timeout=10)
    return thread, release


class TestFilelockTimeout:
    """Test cases for the FilelockTimeout exception"""

    def test_exception_message_and_lock_file(self, lock_dir):
        """FilelockTimeout should carry the lock file path in its message and attribute"""
        lock_file = os.path.abspath(lock_dir / 'a.lock')
        with pytest.raises(
            FilelockTimeout, match='Timeout occurred trying to acquire lock'
        ) as excinfo:
            raise FilelockTimeout(lock_file)
        assert excinfo.value.lock_file == lock_file


class TestProperties:
    """Test cases for the constructor and properties"""

    def test_lock_file_is_absolute(self, lock_dir):
        """lock_file should be the absolute path"""
        lock = SQLiteFileLock(lock_dir / 'sub' / 'a.lock')
        assert lock.lock_file == os.path.abspath(str(lock_dir / 'sub' / 'a.lock'))

    def test_default_timeout_get_and_set(self, lock_dir):
        """timeout should store the constructor value and be mutable"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0.5)
        assert lock.timeout == 0.5
        lock.timeout = 1.5
        assert lock.timeout == 1.5

    @pytest.mark.parametrize('lock_file', ['a.lock', Path('a.lock')])
    def test_accepts_str_and_path(self, lock_dir, lock_file):
        """Constructor should accept both str and Path lock files"""
        lock = SQLiteFileLock(os.path.join(lock_dir, lock_file), timeout=0)
        assert lock.lock_file == os.path.abspath(str(lock_dir / 'a.lock'))

    def test_initial_state(self, lock_dir):
        """A new lock should not be locked"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        assert not lock.is_locked

    @pytest.mark.parametrize('lock_file', [':memory:', Path(':memory:')])
    def test_rejects_memory_database(self, lock_file):
        """Constructor should reject the in-memory database, the lock is on a file"""
        with pytest.raises(ValueError):
            SQLiteFileLock(lock_file)


class TestAcquireRelease:
    """Test cases for acquire() and release()"""

    def test_acquire_returns_self(self, lock_dir):
        """acquire() should return self, matching the filelock interface"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        assert lock.acquire() is lock
        lock.release()

    def test_acquire_and_release(self, lock_dir):
        """is_locked should be True after acquire and False after release"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        lock.acquire()
        assert lock.is_locked
        lock.release()
        assert not lock.is_locked

    def test_acquire_creates_parent_directory(self, lock_dir):
        """Parent directories of the lock file should be created automatically"""
        lock = SQLiteFileLock(lock_dir / 'nested' / 'dir' / 'a.lock', timeout=0)
        lock.acquire()
        assert lock.is_locked
        lock.release()

    def test_release_without_acquire_is_noop(self, lock_dir):
        """release() should do nothing when the lock is not held"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        lock.release()
        assert not lock.is_locked
        lock.release(force=True)
        assert not lock.is_locked

    def test_acquire_accepts_poll_interval(self, lock_dir):
        """poll_interval should be accepted for filelock interface compatibility"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        assert lock.acquire(poll_interval=0.1) is lock
        lock.release()


class TestReentrancy:
    """The lock of a file is not reentrant, the holding thread raises"""

    def test_reentrant_acquire_raises(self, lock_dir):
        """A second acquire() of the holding thread raises instead of waiting"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        lock.acquire()
        with pytest.raises(RuntimeError, match='already held by this thread'):
            lock.acquire()
        assert lock.is_locked
        lock.release()
        assert not lock.is_locked

    def test_reentrant_acquire_of_another_handle_raises(self, lock_dir):
        """The lock of a file is shared by every handle of the process"""
        lock_file = lock_dir / 'a.lock'
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock1.acquire()
        with pytest.raises(RuntimeError, match='already held by this thread'):
            lock2.acquire(timeout=0)
        # The two handles see the same lock
        assert lock2.is_locked
        lock1.release()
        assert not lock2.is_locked


class TestExclusion:
    """Test cases for mutual exclusion between threads and processes"""

    def test_timeout_zero_is_non_blocking(self, lock_dir):
        """acquire() with timeout=0 fails fast with FilelockTimeout when another thread holds the lock"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=0)
        thread, release = hold_in_worker(holder)
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout) as excinfo:
                contender.acquire()
            elapsed = time.monotonic() - start
            assert excinfo.value.lock_file == contender.lock_file
            assert elapsed < 0.5
        finally:
            release.set()
            thread.join(timeout=10)
        assert not contender.is_locked

    def test_positive_timeout_waits_then_raises(self, lock_dir):
        """acquire() with a positive timeout should wait and then raise FilelockTimeout"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=0.2)
        thread, release = hold_in_worker(holder)
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                contender.acquire()
            elapsed = time.monotonic() - start
            assert elapsed >= 0.15
        finally:
            release.set()
            thread.join(timeout=10)

    def test_negative_timeout_waits_for_the_release(self, lock_dir):
        """A negative timeout blocks until the holder releases, it never fails
        at once: the busy timeout of the SQLite C layer has to stay inside the
        int of milliseconds it accepts."""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        waiter = SQLiteFileLock(lock_file, timeout=-1)
        thread, release = hold_in_worker(holder)
        acquired = []

        def wait():
            waiter.acquire(timeout=-1)
            acquired.append(True)
            waiter.release()

        waiter_thread = threading.Thread(target=wait)
        try:
            waiter_thread.start()
            # The waiter is inside the SQLite wait until the holder releases
            time.sleep(0.2)
            assert acquired == []
        finally:
            release.set()
            thread.join(timeout=10)
            waiter_thread.join(timeout=10)
        assert not waiter_thread.is_alive()
        assert acquired == [True]

    def test_acquire_after_release(self, lock_dir):
        """Another instance should acquire the lock once the holder releases it"""
        lock_file = lock_dir / 'a.lock'
        lock1 = SQLiteFileLock(lock_file, timeout=0)
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock1.acquire()
        lock1.release()
        lock2.acquire()
        assert lock2.is_locked
        lock2.release()

    def test_different_files_do_not_conflict(self, lock_dir):
        """Locks on different files should not block each other"""
        lock1 = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        lock2 = SQLiteFileLock(lock_dir / 'b.lock', timeout=0)
        lock1.acquire()
        lock2.acquire()
        assert lock1.is_locked
        assert lock2.is_locked
        lock1.release()
        lock2.release()

    def test_unrelated_operational_error_is_reraisied(self, lock_dir):
        """OperationalError not related to locking should be propagated as is"""
        dir_path = lock_dir / 'adir'
        os.mkdir(dir_path)
        lock = SQLiteFileLock(dir_path, timeout=0)
        with pytest.raises(sqlite3.OperationalError):
            lock.acquire()


class TestDefaultTimeout:
    """Test cases for the default timeout"""

    def test_constructor_timeout_is_used(self, lock_dir):
        """acquire() without a timeout should use the constructor timeout"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=0.2)
        thread, release = hold_in_worker(holder)
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                contender.acquire()
            assert time.monotonic() - start >= 0.15
        finally:
            release.set()
            thread.join(timeout=10)

    def test_acquire_timeout_overrides_constructor(self, lock_dir):
        """acquire(timeout=...) should override the constructor timeout"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        # Constructor timeout is 0, but the override should make acquire() wait
        contender = SQLiteFileLock(lock_file, timeout=0)
        thread, release = hold_in_worker(holder)
        try:
            start = time.monotonic()
            with pytest.raises(FilelockTimeout):
                contender.acquire(timeout=0.2)
            assert time.monotonic() - start >= 0.15
        finally:
            release.set()
            thread.join(timeout=10)


class TestContextManager:
    """Test cases for the context manager protocol"""

    def test_context_manager(self, lock_dir):
        """The lock should be acquired on enter and released on exit"""
        lock = SQLiteFileLock(lock_dir / 'a.lock', timeout=0)
        with lock as acquired:
            assert acquired is lock
            assert lock.is_locked
        assert not lock.is_locked

    def test_release_on_exception(self, lock_dir):
        """The lock should be released even when the block raises"""
        lock_file = lock_dir / 'a.lock'
        with pytest.raises(RuntimeError), SQLiteFileLock(lock_file, timeout=0):
            raise RuntimeError('boom')
        lock2 = SQLiteFileLock(lock_file, timeout=0)
        lock2.acquire()
        lock2.release()


class TestThreads:
    """Test cases for locking across threads"""

    def test_exclusion_between_threads(self, lock_dir):
        """A thread should not acquire a lock held by another thread"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=0)
        holder.acquire()
        results = []

        def try_acquire():
            try:
                contender.acquire()
            except FilelockTimeout:
                results.append('timeout')
            else:
                results.append('acquired')

        thread = threading.Thread(target=try_acquire)
        thread.start()
        thread.join(timeout=10)
        holder.release()
        assert not thread.is_alive()
        assert results == ['timeout']

    def test_thread_waits_until_release(self, lock_dir):
        """A thread should acquire the lock once the holder releases it"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        contender = SQLiteFileLock(lock_file, timeout=5)
        holder.acquire()
        results = []
        started = threading.Event()

        def try_acquire():
            started.set()
            with contender:
                results.append('acquired')

        thread = threading.Thread(target=try_acquire)
        thread.start()
        # Wait until the contender thread is about to acquire, then release
        assert started.wait(timeout=10)
        holder.release()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert results == ['acquired']

    def test_concurrent_acquire_on_same_instance(self, lock_dir):
        """Concurrent acquires on the same instance: the thread that does not own
        the acquire fails on its own timeout budget instead of queueing behind
        the SQLite wait of the other thread"""
        lock_file = lock_dir / 'a.lock'
        holder = SQLiteFileLock(lock_file, timeout=0)
        shared = SQLiteFileLock(lock_file, timeout=0)
        holder.acquire()
        results = []
        c_elapsed = []
        b_started = threading.Event()

        def thread_b():
            b_started.set()
            # Waits 0.5s for the SQLite lock of the holder
            try:
                shared.acquire(timeout=0.5)
            except FilelockTimeout:
                results.append('b:timeout')

        def thread_c():
            # Non-blocking, must fail fast while thread B is acquiring
            start = time.monotonic()
            try:
                shared.acquire(timeout=0)
            except FilelockTimeout:
                c_elapsed.append(time.monotonic() - start)
                results.append('c:timeout')

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
        assert results == ['c:timeout', 'b:timeout']
        # Thread C must not wait for thread B's SQLite wait to finish
        assert c_elapsed[0] < 0.3

    def test_concurrent_acquire_has_single_winner(self, lock_dir):
        """Two threads racing on one lock file yield exactly one winner.

        The lock of the file is shared and not reentrant: the loser waits for the
        holder and times out on its own budget.
        """
        lock_file = lock_dir / 'a.lock'
        # Loser budget 0.2s, the winner holds the lock until the loser failed
        shared = SQLiteFileLock(lock_file, timeout=0.2)
        results = []
        acquired = threading.Event()
        timed_out = threading.Event()
        release = threading.Event()

        def try_acquire(tag):
            try:
                with shared:
                    results.append(f'{tag}:acquired')
                    acquired.set()
                    # Hold the lock until the other thread timed out
                    release.wait(timeout=10)
            except FilelockTimeout:
                results.append(f'{tag}:timeout')
                timed_out.set()

        b = threading.Thread(target=try_acquire, args=('b',))
        c = threading.Thread(target=try_acquire, args=('c',))
        b.start()
        c.start()
        # The winner keeps the lock until the other thread failed on its own
        # budget, so a thread that starts late waits on a held lock and can not
        # win after the release of the winner
        assert acquired.wait(timeout=10)
        assert timed_out.wait(timeout=10)
        release.set()
        b.join(timeout=10)
        c.join(timeout=10)
        assert not b.is_alive()
        assert not c.is_alive()
        winners = [r for r in results if r.endswith(':acquired')]
        losers = [r for r in results if r.endswith(':timeout')]
        assert len(winners) == 1
        assert len(losers) == 1

    def test_shared_instance_excludes_other_threads(self, lock_dir):
        """The handles of one lock file share the lock: a second thread waits
        for the holder and times out on its own budget."""
        lock_file = lock_dir / 'a.lock'
        shared = SQLiteFileLock(lock_file, timeout=0)
        results = []
        shared.acquire()

        def acquire_in_worker():
            try:
                with shared:
                    results.append('acquired')
            except FilelockTimeout:
                results.append('timeout')

        thread = threading.Thread(target=acquire_in_worker)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert results == ['timeout']
        assert shared.is_locked
        shared.release()
        assert not shared.is_locked

    def test_shared_instance_waiter_acquires_after_release(self, lock_dir):
        """A thread waiting on the lock acquires it when the holder releases:
        the SQLite busy handler retries and succeeds."""
        lock_file = lock_dir / 'a.lock'
        shared = SQLiteFileLock(lock_file, timeout=0)
        results = []
        shared.acquire()

        def acquire_in_worker():
            # Long budget: the acquire waits for the release of the owner
            try:
                shared.acquire(timeout=5)
            except FilelockTimeout:
                results.append('timeout')
                return
            results.append('acquired')
            shared.release()

        thread = threading.Thread(target=acquire_in_worker)
        thread.start()
        shared.release()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert results == ['acquired']
        assert not shared.is_locked

    def test_release_from_another_thread_keeps_the_lock(self, lock_dir):
        """A thread that does not hold the lock has nothing to release."""
        lock_file = lock_dir / 'a.lock'
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()

        thread = threading.Thread(target=lock.release)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive()
        # The lock of the holder is untouched, the holder releases it
        assert lock.is_locked
        lock.release()
        assert not lock.is_locked

    def test_force_release_from_another_thread(self, lock_dir):
        """release(force=True) is the escape hatch of a thread that is not the
        owner."""
        lock_file = lock_dir / 'a.lock'
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()

        thread = threading.Thread(target=lock.release, kwargs={'force': True})
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert not lock.is_locked


class TestCrossProcess:
    """Test cases for locking across processes"""

    def test_exclusion_between_processes(self, lock_dir):
        """A child process should not acquire a lock held by the parent"""
        lock_file = lock_dir / 'a.lock'
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()
        code = (
            'import sys\n'
            'from oas.ext.file.filelock import SQLiteFileLock, FilelockTimeout\n'
            'try:\n'
            '    with SQLiteFileLock(sys.argv[1], timeout=0.5):\n'
            "        print('ACQUIRED')\n"
            'except FilelockTimeout:\n'
            "    print('TIMEOUT')\n"
        )
        result = subprocess.run(
            [sys.executable, '-c', code, str(lock_file)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        lock.release()
        assert result.returncode == 0
        assert 'TIMEOUT' in result.stdout

    def test_parent_acquires_after_child_release(self, lock_dir):
        """The parent should acquire the lock after the child process releases it"""
        lock_file = lock_dir / 'a.lock'
        flag_file = lock_dir / 'release.flag'
        proc = subprocess.Popen(
            [sys.executable, '-c', CHILD_HOLD, str(lock_file), str(flag_file)],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert proc.stdout.readline().strip() == 'HELD'
            flag_file.touch()
            lock = SQLiteFileLock(lock_file, timeout=10)
            lock.acquire()
            assert lock.is_locked
            lock.release()
        finally:
            proc.wait(timeout=10)
            proc.kill()


class TestHandleLifetime:
    """The lock is held by the file and the thread, not by a handle"""

    def test_dropping_a_handle_keeps_the_lock(self, lock_dir):
        """The lock outlives its handle, another handle of the thread releases it"""
        lock_file = lock_dir / 'a.lock'
        lock = SQLiteFileLock(lock_file, timeout=0)
        lock.acquire()
        del lock
        gc.collect()
        other = SQLiteFileLock(lock_file, timeout=0)
        assert other.is_locked
        with pytest.raises(RuntimeError, match='already held by this thread'):
            other.acquire(timeout=0)
        other.release()
        assert not other.is_locked
