"""
Benchmark: SQLiteFileLock (sqlite3 BEGIN EXCLUSIVE transaction lock)
vs the plain Windows byte-range file lock (msvcrt.locking + LK_NBLCK).

SQLiteFileLock reuses SQLite's own concurrency machinery: acquiring the lock
means opening the lock file as a database and starting an EXCLUSIVE
transaction, releasing means rolling it back and closing the connection.
Every acquire therefore costs sqlite3.connect + BEGIN EXCLUSIVE (+ rollback on
release), which is orders of magnitude more work than the two _locking
syscalls the native Windows lock needs.

The point of this benchmark is to establish *how much more* it costs, across
the dimensions that matter:

  T1  uncontended access: single-thread acquire/release back-to-back
  T2  thread contention:  two threads hammering the same lock file
  T3  process contention: two real subprocesses hammering the same lock file
  T4  timeout path:       immediate failure when the lock is already held

plus a functional (non-benchmark) check that both implementations still
deliver correct mutual exclusion while under contention — "fast but wrong"
loses.

Native lock notes (probed live on Windows/Python 3.14):
  * two different fds in the SAME process DO conflict (2nd gets EACCES),
    so thread benchmarks are meaningful
  * the failure errno is EACCES (13)
  * a 0-byte file locks fine (Windows _locking handles the open region),
    but the parent directory must exist

Run with:
    python -m pytest tests/oas/ext/file/test_bench_filelock.py --benchmark-only -v
    python -m pytest tests/oas/ext/file/test_bench_filelock.py --benchmark-sort=name --benchmark-only -v
"""

import errno
import os
import shutil
import subprocess
import sys
import threading
import time

import pytest

from oas.ext.env import OAS_ROOT
from oas.ext.file.filelock import FilelockTimeout, SQLiteFileLock
from oas.ext.path import PathStr

msvcrt = pytest.importorskip("msvcrt")

pytestmark = [
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="msvcrt.locking is Windows-only; no native counterpart on this platform",
    ),
]

IMPLS = ["sqlite", "msvcrt"]

# =============================================================================
# Fixture: real-filesystem lock directory
# =============================================================================


@pytest.fixture(scope="module")
def lock_dir():
    """
    Real filesystem directory for the lock benchmarks.

    Both implementations hit the real file: SQLite opens the lock file in the
    C layer, and msvcrt.locking is a raw Windows syscall — neither can be
    intercepted by the in-memory fake filesystem.
    """
    path = PathStr.new(OAS_ROOT).joinpath("temp/bench_filelock")
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


# =============================================================================
# Low-level helpers: one acquire/release cycle per implementation
# =============================================================================


def _acquire_release_sqlite(path):
    lock = SQLiteFileLock(str(path), timeout=5)
    with lock:
        pass


def _acquire_release_msvcrt(path):
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def _acquire_release(impl, path):
    if impl == "sqlite":
        _acquire_release_sqlite(path)
    else:
        _acquire_release_msvcrt(path)


# =============================================================================
# T1  uncontended cost: full acquire/release cycle, back to back
# =============================================================================


def _bench_uncontended(benchmark, impl, lock_dir, rounds):
    path = lock_dir / f"t1_{impl}.lock"

    def loop():
        for _ in range(rounds):
            _acquire_release(impl, path)
        return path

    benchmark(loop)


@pytest.mark.parametrize("impl", IMPLS)
def test_t1_uncontended_cost(benchmark, impl, lock_dir):
    """Full acquire+release cycle, no concurrency at all."""
    _bench_uncontended(benchmark, impl, lock_dir, rounds=25)


# =============================================================================
# T2  thread contention: two threads hammering the same lock file
# =============================================================================


def _thread_contest(impl, path, rounds):
    """
    Two threads race for ``rounds`` successful acquires each.

    SQLiteFileLock: each thread builds its OWN instance (the correct usage per
    the module docstring — instance-level ownership is reentrant); msvcrt:
    each thread opens its own fd. Returns (elapsed_wallclock, fails) so the
    caller can report the share of failed attempts.
    """
    barrier = threading.Barrier(2)
    fails = []
    start = time.perf_counter()

    def worker():
        barrier.wait()
        fail = 0
        if impl == "sqlite":
            lock = SQLiteFileLock(str(path), timeout=0)
            for _ in range(rounds):
                try:
                    lock.acquire(timeout=0)
                    lock.release()
                except FilelockTimeout:
                    fail += 1
        else:
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
            try:
                for _ in range(rounds):
                    try:
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except OSError as e:
                        if e.errno not in (errno.EACCES, errno.EDEADLK):
                            raise
                        fail += 1
            finally:
                os.close(fd)
        fails.append(fail)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed = time.perf_counter() - start
    return elapsed, sum(fails)


def _bench_thread_contention(benchmark, impl, lock_dir, rounds):
    path = lock_dir / f"t2_{impl}.lock"

    def loop():
        elapsed, fails = _thread_contest(impl, str(path), rounds)
        return round(elapsed, 6)

    benchmark(loop)


@pytest.mark.parametrize("impl", IMPLS)
def test_t2_thread_contention(benchmark, impl, lock_dir):
    """Two threads racing the same lock file: wall-clock for 2xN attempts."""
    _bench_thread_contention(benchmark, impl, lock_dir, rounds=50)


# =============================================================================
# T3  process contention: two real subprocesses hammering the same lock
# =============================================================================

CHILD_ROUNDS = 1000


def _child_program(impl):
    if impl == "sqlite":
        imports = "from oas.ext.file.filelock import SQLiteFileLock\n"
        setup = "lock = SQLiteFileLock(path, timeout=5)\n"
        body = "    with lock:\n        pass\n"
    else:
        imports = "import msvcrt\n"
        setup = "fd = os.open(path, os.O_RDWR | os.O_CREAT)\n"
        body = (
            "    while True:\n"
            "        try:\n"
            "            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)\n"
            "            break\n"
            "        except OSError:\n"
            "            pass\n"
            "    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)\n"
        )
    return (
        "import os, sys, time\n"
        + imports
        + "path, n = sys.argv[1], int(sys.argv[2])\n"
        + setup
        + "t0 = time.perf_counter()\n"
        + "for _ in range(n):\n"
        + body
        + "print(f'{time.perf_counter() - t0:.6f}')\n"
    )


def _process_contest(impl, path, rounds):
    """
    Spawn two subprocesses that both race ``rounds`` acquires on the same
    lock file. The Python startup (~50-80ms) is part of the wall-clock for
    BOTH implementations, so it is a constant offset, not a differentiator.
    Returns the larger of the two per-process wall-clocks.
    """
    code = _child_program(impl)
    procs = [
        subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", code, str(path), str(rounds)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=OAS_ROOT,
        )
        for _ in range(2)
    ]
    elapsed = []
    for p in procs:
        out, err = p.communicate(timeout=120)
        if p.returncode != 0:
            raise RuntimeError(f"child failed ({p.returncode}): {err.strip()}")
        elapsed.append(float(out.strip()))
    return max(elapsed)


def _bench_process_contention(benchmark, impl, lock_dir, rounds):
    path = lock_dir / f"t3_{impl}.lock"

    def loop():
        return _process_contest(impl, str(path), rounds)

    benchmark(loop)


@pytest.mark.parametrize("impl", IMPLS)
def test_t3_process_contention(benchmark, impl, lock_dir):
    """Two subprocesses racing the same lock file (end-to-end, incl. startup)."""
    _bench_process_contention(benchmark, impl, lock_dir, rounds=CHILD_ROUNDS)


# =============================================================================
# T4  timeout path: immediate failure when the lock is already held
# =============================================================================


@pytest.mark.parametrize("impl", IMPLS)
def test_t4_timeout_path(benchmark, impl, lock_dir):
    """Cost of a rejected acquire when someone already holds the lock."""
    path = lock_dir / f"t4_{impl}.lock"

    if impl == "sqlite":
        holder = SQLiteFileLock(str(path), timeout=0)
        holder.acquire()
        loser = SQLiteFileLock(str(path), timeout=0)

        def loop():
            try:
                loser.acquire(timeout=0)
                loser.release()
            except FilelockTimeout:
                pass
            return path

    else:
        holder_fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
        msvcrt.locking(holder_fd, msvcrt.LK_NBLCK, 1)

        def loop():
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
            try:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError as e:
                    if e.errno not in (errno.EACCES, errno.EDEADLK):
                        raise
            finally:
                os.close(fd)
            return path

    benchmark(loop)

    # teardown: release the holder so the module-scoped clean-up can delete the dir
    if impl == "sqlite":
        holder.release()
    else:
        try:
            msvcrt.locking(holder_fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        os.close(holder_fd)


# =============================================================================
# Functional check: both implementations stay CORRECT under contention
# =============================================================================


@pytest.mark.parametrize("impl", IMPLS)
def test_contended_counter_is_exact(impl, lock_dir):
    """
    N threads each bump a shared counter ITERS times, guarded by the lock.

    A broken lock (or one that silently allows two writers) would lose
    increments. Every implementation must finish at exactly N*ITERS even
    though the threads are fighting for the same file.
    """
    path = lock_dir / f"correct_{impl}.lock"
    n_threads, iters = 4, 200

    counter = [0]
    thread_fails = []

    def worker():
        if impl == "sqlite":
            lock = SQLiteFileLock(str(path), timeout=10)
            for _ in range(iters):
                with lock:
                    counter[0] += 1
        else:
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
            try:
                for _ in range(iters):
                    while True:
                        try:
                            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                            break
                        except OSError as e:
                            if e.errno not in (errno.EACCES, errno.EDEADLK):
                                raise
                    counter[0] += 1
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(fd)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert counter[0] == n_threads * iters, (
        f"{impl}: counter={counter[0]}, expected {n_threads * iters}"
    )