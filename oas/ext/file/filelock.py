"""
Cross-platform file lock based on SQLite exclusive transactions.

The lock is implemented as a ``BEGIN EXCLUSIVE`` transaction on a SQLite
database file, so it works across processes and threads on Windows, macOS and
Linux. The public interface is compatible with the third-party
filelock.FileLock library.

Notes:
    - The lock file is a SQLite database file and stays on disk after release.
      Deleting it would break mutual exclusion: a new file could be created and
      locked while another process still holds a lock on the old one.
    - The lock is released automatically when the holding process crashes or
      exits, because the operating system releases the underlying file locks
      and SQLite rolls back unfinished transactions.
"""
import os
import sqlite3
import threading


class FilelockTimeout(Exception):
    """
    Raised when the lock cannot be acquired within the timeout
    (consistent with filelock.Timeout).

    Args:
        lock_file (str): Path of the lock file
    """

    def __init__(self, lock_file):
        self.lock_file = lock_file
        super().__init__(f"Timeout occurred trying to acquire lock for: {lock_file}")


class SQLiteFileLock:
    """
    Cross-platform file lock based on SQLite exclusive transactions
    (``BEGIN EXCLUSIVE``).

    The interface is fully compatible with the third-party filelock.FileLock
    library.

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

        Handle the timeout when the lock is held by another process:

            from oas.ext.file.filelock import SQLiteFileLock, FilelockTimeout

            try:
                with SQLiteFileLock("app.lock", timeout=0.5):
                    # critical section
            except FilelockTimeout:
                # the lock is held elsewhere

        The lock is reentrant within one instance. For mutual exclusion across
        threads, each thread should use its own instance:

            # thread 1
            with SQLiteFileLock("app.lock", timeout=1.0):
                # critical section

            # thread 2
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
            raise ValueError('Cannot lock an in-memory database, the lock must be on a file')

        # Absolute path without symlink resolution (os.path.abspath does no IO),
        # so instances in different working directories still lock the same file
        self._lock_file = os.path.abspath(lock_file)
        self._default_timeout = timeout

        # Internal state, supports reentrant locking within the same instance
        self._conn = None
        self._lock_counter = 0
        self._thread_lock = threading.Lock()

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
            bool: True if the current instance holds the lock
        """
        with self._thread_lock:
            return self._lock_counter > 0

    def acquire(self, timeout=None, poll_interval=0.05):
        """
        Acquire the lock.

        Args:
            timeout (float): Overrides the constructor timeout. Defaults to None.
            poll_interval (float): Kept for compatibility with the filelock
                interface, the SQLite C layer polls automatically.
                Defaults to 0.05.

        Returns:
            SQLiteFileLock: self

        Raises:
            FilelockTimeout: If the lock cannot be acquired within the timeout
        """
        if timeout is None:
            timeout = self._default_timeout

        with self._thread_lock:
            # Reentrant lock: repeated acquire() on the same instance must not deadlock
            if self._lock_counter > 0:
                self._lock_counter += 1
                return self

        # The thread lock above only guards the shared state. The SQLite lock
        # itself is acquired outside the thread lock, so a thread waiting on
        # the SQLite lock never blocks other threads of the same instance,
        # and every thread waits on its own timeout budget.
        # Convert to the SQLite C API timeout in seconds:
        # < 0 waits forever, 0 is non-blocking.
        # 315360000.0 is 10 years, effectively infinite for a blocking wait
        sql_timeout = 315360000.0 if timeout < 0 else max(0.0, float(timeout))

        # Optimistically assume the parent directory exists to save IO.
        # Create it and retry once only if connect fails with
        # "unable to open database file".
        conn = None
        for attempt in range(2):
            try:
                conn = self.__begin_exclusive(sql_timeout)
                break
            except sqlite3.OperationalError as e:
                if attempt == 0 and str(e).lower() == "unable to open database file":
                    # Create the missing parent directory and retry once
                    parent_dir = os.path.dirname(self._lock_file)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    continue
                raise

        # Register the connection and the counter atomically. BEGIN EXCLUSIVE
        # is globally exclusive, so while this connection holds the lock no
        # other thread can have set the counter, and no other thread can
        # succeed before this registration.
        with self._thread_lock:
            self._conn = conn
            self._lock_counter = 1
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
            conn.execute("BEGIN EXCLUSIVE")
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
            if "locked" in err_msg or "busy" in err_msg:
                raise FilelockTimeout(self._lock_file) from e
            raise

    def release(self, force=False):
        """
        Release the lock.

        Args:
            force (bool): If True, ignore the reentrancy counter and release
                the lock immediately. Defaults to False.
        """
        with self._thread_lock:
            if self._lock_counter == 0:
                return

            if force:
                self._lock_counter = 1

            self._lock_counter -= 1

            # Only close the connection and release the file lock when the counter drops to zero
            if self._lock_counter == 0:
                if self._conn:
                    try:
                        # End the transaction
                        self._conn.rollback()
                    except Exception:
                        pass
                    finally:
                        try:
                            # Close the connection, the OS releases the exclusive lock
                            self._conn.close()
                        except Exception:
                            pass
                        self._conn = None

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

    def __del__(self):
        """Safe fallback to release the lock when the object is destroyed."""
        # __del__ is also called on partially initialized objects when
        # __init__ raises, so guard against missing attributes
        if hasattr(self, '_thread_lock'):
            self.release(force=True)
