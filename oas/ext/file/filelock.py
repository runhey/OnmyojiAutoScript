"""
Cross-platform file lock based on SQLite exclusive transactions.

The lock is implemented as a ``BEGIN EXCLUSIVE`` transaction on a SQLite
database file, so it works across processes and threads on Windows, macOS and
Linux. The lock of one file is one lock in the process: every SQLiteFileLock
of the same lock file shares the state, so the exclusion is left to SQLite,
the connections of the threads and the processes all race on the same file
lock. The lock is not reentrant: an acquire() of the thread that already
holds it raises at once instead of waiting for itself.

Notes:
    - The lock file is a SQLite database file and stays on disk after release.
      Deleting it would break mutual exclusion: a new file could be created and
      locked while another process still holds a lock on the old one.
    - The lock is released automatically when the holding process crashes or
      exits, because the operating system releases the underlying file locks
      and SQLite rolls back unfinished transactions.
    - The lock is held by the thread that acquired it, and the handles have no
      destructor: a lock that is never released is held until the process
      exits, the way a threading.Lock does.
"""

import os
import sqlite3
import threading

# Busy timeout of the SQLite C layer for an infinite wait, in seconds: the C
# API takes an int of milliseconds, 2**31-1 ms is about 24.8 days, the largest
# wait it accepts. A larger timeout overflows the int and disables the wait:
# the connection fails with "database is locked" at once
SQL_TIMEOUT_FOREVER = (2**31 - 1) / 1000


class FilelockTimeout(Exception):
    """
    Raised when the lock cannot be acquired within the timeout
    (consistent with filelock.Timeout).

    Args:
        lock_file (str): Path of the lock file
    """

    def __init__(self, lock_file):
        self.lock_file = lock_file
        super().__init__(f'Timeout occurred trying to acquire lock for: {lock_file}')


class _FileLockState:
    """
    The state of the lock of one file in this process.

    Attributes:
        conns (dict[int, sqlite3.Connection]): Connection of every thread
            holding the lock, keyed by the identity of the thread (see
            threading.get_ident)
        guard (threading.Lock): Guards conns
    """

    __slots__ = ('conns', 'guard')

    def __init__(self):
        self.conns = {}
        self.guard = threading.Lock()


# The state of every lock file of the process, keyed by the normalized
# absolute path of the file: the lock of a file is one lock, the instances are
# handles of it
_FILE_STATES = {}
_FILE_STATES_GUARD = threading.Lock()


def _file_state(lock_file):
    """
    State of the lock of a file, created on first use.

    The path is made absolute, the symlinks of the existing directories are
    resolved and the case is normalized (Windows), so the same lock file
    reached by two spellings shares one lock.

    Args:
        lock_file (str): Path of the lock file

    Returns:
        _FileLockState: The state shared by the instances of the file
    """
    key = os.path.normcase(os.path.realpath(lock_file))
    with _FILE_STATES_GUARD:
        state = _FILE_STATES.get(key)
        if state is None:
            state = _FILE_STATES[key] = _FileLockState()
        return state


class SQLiteFileLock:
    """
    Exclusive lock of a lock file, based on a SQLite exclusive transaction
    (``BEGIN EXCLUSIVE``).

    The lock of one file is one lock in the process: every instance of the
    same lock file shares the state, an acquire() of one handle is seen by the
    others (is_locked) and the exclusion is left to SQLite, the connections of
    the threads and of the processes race on the same file lock.

    The lock is not reentrant: SQLite can not tell the connection that holds
    the file lock from another one, an acquire() of the thread that already
    holds it would wait for itself until its timeout. The call raises
    RuntimeError at once instead, a deadlock has to be found, not waited for.
    It is the one interface difference from the third-party filelock.FileLock,
    which counts a repeated acquire().

    The owner of the lock is the calling thread, or the identity given to
    acquire(owner=...): a caller that has to wait in another thread (an async
    block that can not block the event loop) passes the identity of the
    thread that will release the lock, the wait itself only runs on a worker.

    Examples:
        Use as a context manager, the lock is released automatically on exit:

            with SQLiteFileLock("app.lock") as lock:
                # critical section

        Acquire and release manually, each acquire() must pair with a release():

            lock = SQLiteFileLock("app.lock")
            lock.acquire()
            try:
                # critical section
            finally:
                lock.release()

        Handle the timeout when the lock is held by another thread or process:

            from oas.ext.file.filelock import SQLiteFileLock, FilelockTimeout

            try:
                with SQLiteFileLock("app.lock", timeout=0.5):
                    # critical section
            except FilelockTimeout:
                # the lock is held elsewhere

        Two handles of one lock file share the lock: another thread waits for
        the holder (the thread that holds it raises, see above)

            # thread 1
            with SQLiteFileLock("app.lock", timeout=1.0):
                # critical section

            # thread 2, waits here until the first thread released it
            with SQLiteFileLock("app.lock", timeout=1.0):
                # critical section
    """

    def __init__(self, lock_file, timeout=-1):
        """
        Args:
            lock_file (str or Path): Lock file path, parent directories are
                created automatically if missing
            timeout (float): Timeout in seconds. Defaults to -1.
                -1 waits indefinitely (blocking);
                 0 is non-blocking, raises FilelockTimeout immediately if the lock
                   cannot be acquired;
                > 0 waits at most N seconds

        Raises:
            ValueError: If lock_file is an in-memory database ":memory:"
        """
        lock_file = str(lock_file)
        if lock_file == ':memory:':
            raise ValueError(
                'Cannot lock an in-memory database, the lock must be on a file'
            )

        # Absolute path without symlink resolution (os.path.abspath does no IO),
        # the path of the lock file and of the error messages
        self._lock_file = os.path.abspath(lock_file)
        self._default_timeout = timeout
        # The state of the lock file, shared by every instance of the file
        self._state = _file_state(self._lock_file)

    @property
    def lock_file(self):
        """
        Returns:
            str: Absolute path of the lock file
        """
        return self._lock_file

    @property
    def timeout(self):
        """
        Returns:
            float: Default timeout in seconds
        """
        return self._default_timeout

    @timeout.setter
    def timeout(self, value):
        """
        Args:
            value (float): Default timeout in seconds
        """
        self._default_timeout = value

    @property
    def is_locked(self):
        """
        Returns:
            bool: True if a thread of this process holds the lock file
        """
        with self._state.guard:
            return bool(self._state.conns)

    def acquire(self, timeout=None, poll_interval=0.05, owner=None):
        """
        Acquire the lock, wait for it while another thread or process holds it.

        Args:
            timeout (float): Overrides the constructor timeout. Defaults to None.
            poll_interval (float): Kept for compatibility with the filelock
                interface, the SQLite C layer polls automatically.
                Defaults to 0.05.
            owner (int, optional): Identity of the owner of the lock, compared
                by equality. Defaults to None, the identity of the calling
                thread. A caller that has to wait in another thread passes the
                identity of the thread that will release the lock, see
                DeployJob.alocked().

        Returns:
            SQLiteFileLock: self

        Raises:
            FilelockTimeout: If the lock cannot be acquired within the timeout
            RuntimeError: If the owner already holds the lock, the acquire is a
                reentrancy that would wait for itself
        """
        if timeout is None:
            timeout = self._default_timeout
        if owner is None:
            owner = threading.get_ident()
        with self._state.guard:
            held = owner in self._state.conns
        if held:
            # SQLite can not tell the connection of this owner from another
            # one, the acquire would block on the lock the owner holds itself
            raise RuntimeError(
                f'The lock "{self._lock_file}" is already held by this thread, '
                f'a reentrant acquire would wait for itself'
            )

        # Convert to the SQLite C API timeout in seconds:
        # < 0 waits forever, 0 is non-blocking
        sql_timeout = SQL_TIMEOUT_FOREVER if timeout < 0 else max(0.0, float(timeout))

        # Optimistically assume the parent directory exists to save IO.
        # Create it and retry once only if connect fails with
        # "unable to open database file".
        conn = None
        for attempt in range(2):
            try:
                conn = self.__begin_exclusive(sql_timeout)
                break
            except sqlite3.OperationalError as e:
                if attempt == 0 and str(e).lower() == 'unable to open database file':
                    # Create the missing parent directory and retry once
                    parent_dir = os.path.dirname(self._lock_file)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    continue
                raise

        with self._state.guard:
            self._state.conns[owner] = conn
        return self

    def __begin_exclusive(self, sql_timeout):
        """
        Open a connection and start an exclusive transaction.

        Args:
            sql_timeout (float): SQLite C API timeout in seconds

        Returns:
            sqlite3.Connection: Connection holding the exclusive lock

        Raises:
            FilelockTimeout: If the lock cannot be acquired within the timeout
            sqlite3.OperationalError: If the database cannot be opened,
                e.g. "unable to open database file" when the directory is missing
        """
        conn = None
        try:
            # Open a connection and rely on SQLite's native busy_timeout mechanism
            conn = sqlite3.connect(
                self._lock_file,
                timeout=sql_timeout,
                check_same_thread=False,
            )

            # Start an exclusive transaction, which takes an OS-level exclusive file lock
            conn.execute('BEGIN EXCLUSIVE')
            return conn

        except sqlite3.OperationalError as e:
            # Close the connection that failed to acquire the lock
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

            # Convert the "database is locked" error to FilelockTimeout
            err_msg = str(e).lower()
            if 'locked' in err_msg or 'busy' in err_msg:
                raise FilelockTimeout(self._lock_file) from e
            raise

    def release(self, force=False):
        """
        Release the lock of the calling thread, a thread that does not hold the
        lock has nothing to release.

        Args:
            force (bool): If True, close every connection the process holds on
                the lock file, whatever the threads. An escape hatch for a
                thread that is not the holder, never used by the normal flow.
                Defaults to False.
        """
        owner = threading.get_ident()
        with self._state.guard:
            if force:
                conns = list(self._state.conns.values())
                self._state.conns.clear()
            else:
                conn = self._state.conns.pop(owner, None)
                conns = [] if conn is None else [conn]

        for conn in conns:
            try:
                # End the transaction
                conn.rollback()
            except Exception:
                pass
            finally:
                try:
                    # Close the connection, the OS releases the exclusive lock
                    conn.close()
                except Exception:
                    pass

    def __enter__(self):
        """
        Acquire the lock when entering the context.

        Returns:
            SQLiteFileLock: self
        """
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Release the lock when leaving the context.
        """
        self.release()
