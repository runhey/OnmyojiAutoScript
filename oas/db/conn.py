import os
import sqlite3
import time
from threading import Lock

from oas.ext.path.atomic import atomic_remove, atomic_rename
from oas.logger import logger


class SqlitePoolCursor(sqlite3.Cursor):
    def __init__(self, conn):
        """
        Args:
            conn (sqlite3.Connection):
        """
        super().__init__(conn)
        # value will be set in SqlitePool.cursor()
        self.pool: 'ConnectionPool | None' = None
        self.TABLE_NAME = ''
        self.CREATE_TABLE = ''

    def __enter__(self):
        return self

    def close(self):
        super().close()
        conn = self.connection
        pool = self.pool

        # check transaction
        if conn is not None:
            if conn.in_transaction:
                logger.error(
                    f'DEV ERROR: A transaction was not explicitly committed or rolled back, '
                    f'please check your code. Auto rolling back anyway.'
                )
            # rollback to prevent connection pollution
            try:
                conn.rollback()
            except Exception as e:
                logger.error(f'Failed to rollback transaction: {e}')

        # return connection
        if pool is not None:
            # Update last_visit again as SQL query may take long
            pool.last_use[conn] = time.time()
            # Release lock after all poll stuff
            pool.idle_workers[conn] = None
            pool.release_full_lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def commit(self):
        """
        Now you can commit in cursor object
        """
        self.connection.commit()

    def rollback(self):
        """
        Now you can rollback in cursor object
        """
        self.connection.rollback()

    def create_table(self):
        """
        Create table if CREATE_TABLE is set

        Returns:
            bool: If created

        Raises:
            sqlite3.OperationalError
        """
        if not self.CREATE_TABLE:
            return False
        try:
            if self.TABLE_NAME:
                # Yes this is a simple string.format to create SQL,
                # because placeholder is now allowed in the table name of CREATE TABLE
                # It's acceptable that TABLE_NAME is manually configured, not a user input
                sql = self.CREATE_TABLE.format(TABLE_NAME=self.TABLE_NAME)
                super().execute(sql)
            else:
                super().execute(self.CREATE_TABLE)
            return True
        except sqlite3.OperationalError as e:
            # table ... already exists
            if 'already exists' in str(e):
                # race condition that another thread just created the table
                return False
            else:
                raise

    def execute(self, *args, **kwargs):
        try:
            return super().execute(*args, **kwargs)
        except sqlite3.OperationalError as e:
            # sqlite3.OperationalError: no such table: .../
            if 'no such table:' in str(e) and self.CREATE_TABLE:
                pass
            else:
                raise

        self.create_table()
        return super().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        try:
            return super().executemany(*args, **kwargs)
        except sqlite3.OperationalError as e:
            # sqlite3.OperationalError: no such table: .../
            if 'no such table:' in str(e) and self.CREATE_TABLE:
                pass
            else:
                raise

        self.create_table()
        return super().executemany(*args, **kwargs)


class ExclusiveTransaction:
    def __init__(self, cursor):
        """
        Args:
            cursor (SqlitePoolCursor):
        """
        self.cursor = cursor

    def __enter__(self):
        self.cursor.execute('BEGIN EXCLUSIVE;')
        return self.cursor

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.cursor.commit()
            else:
                self.cursor.connection.rollback()
        finally:
            self.cursor.close()


class ConnectionPool:
    def __init__(self, file, pool_size=4):
        """
        Args:
            file (str): Absolute path to sqlite database
            pool_size: Max connections
        """
        self.file = file
        self.pool_size = pool_size
        self.last_use: 'dict[sqlite3.Connection, float]' = {}

        # Same as WorkerPool, let's just keep the name 'worker'
        self.idle_workers: 'dict[sqlite3.Connection, None]' = {}
        self.all_workers: 'dict[sqlite3.Connection, None]' = {}

        self.notify_worker = Lock()
        self.notify_worker.acquire()
        self.notify_pool = Lock()
        self.notify_pool.acquire()

        self.create_lock = Lock()

    @classmethod
    def new_conn(cls, file):
        """
        Create a connection directly
        Auto create folder if folder not exists

        Returns:
            sqlite3.Connection:
        """
        try:
            conn = sqlite3.connect(file, timeout=10.0, check_same_thread=False)
            cls.set_conn_pragma(conn)
            return conn
        except sqlite3.OperationalError as e:
            # sqlite3.OperationalError: unable to open database file
            if str(e) == 'unable to open database file':
                pass
            else:
                raise

        # Create folder
        folder = os.path.dirname(file)
        os.makedirs(folder, exist_ok=True)

        conn = sqlite3.connect(file, timeout=10.0, check_same_thread=False)
        cls.set_conn_pragma(conn)
        return conn

    @classmethod
    def set_conn_pragma(cls, conn):
        """
        Set PRAGMA in sqlite

        Args:
            conn (sqlite3.Connection):
        """
        # Alasio uses the default journal_mode which is DELETE,
        # so users can have one single config file to be copied around
        # conn.execute('PRAGMA journal_mode=PERSIST')

        # Set sqlite3.Row to pass kwargs instead of tuple to msgspec.Struct
        conn.row_factory = sqlite3.Row

    def release_full_lock(self):
        """
        Call this method if worker finished any job, or exited, or get killed.

        When pool full,
        Pool tells all workers: any worker finishes his job notify me.
        `self.notify_worker.release()`
        Then the pool blocks himself.
        `self.notify_pool.acquire()`
        The fastest worker, and also the only worker, receives the message,
        `if self.notify_worker.acquire(blocking=False):`
        Worker tells the pool, new pool slot is ready, you are ready to go.
        `self.notify_pool.release()`
        """
        if self.notify_worker.acquire(blocking=False):
            try:
                self.notify_pool.release()
            except RuntimeError:
                # Race condition when multiple threads trying to get thread worker
                # They released `notify_worker` but not yet acquire `notify_pool`
                pass

    def _get_thread_worker(self):
        """
        Returns:
            sqlite3.Connection:
        """
        try:
            worker, _ = self.idle_workers.popitem()
            # logger.info(f'reuse worker thread: {worker.default_name}')
            return worker
        except KeyError:
            pass

        # Wait if reached max thread
        # Check without `create_lock` first, otherwise will be 10x slower
        # if multiple thread trying to get `create_lock`
        if len(self.all_workers) >= self.pool_size:
            # See release_full_lock()
            try:
                self.notify_worker.release()
            except RuntimeError:
                # Race condition when multiple threads trying to get thread worker
                # It's ok to treat multiple release as one
                pass
            while 1:
                # If any worker finishes within timeout, we can get it
                # Race condition when all workers just done `release_full_lock` and no one notifies
                # To handle that, we acquire with timeout and check if there's idle worker
                self.notify_pool.acquire(timeout=0.01)
                # Re-acquire `notify_worker` so other workers can
                # call `release_full_lock` for next `_get_thread_worker`
                self.notify_worker.acquire(blocking=False)
                # A worker just idle
                try:
                    worker, _ = self.idle_workers.popitem()
                    return worker
                except KeyError:
                    # Race condition when multiple threads trying to get thread worker,
                    # they all pass through full lock check and pop the only idle worker.
                    # Just let the slower ones do full lock check again
                    pass
                # A thread just existed, pool no longer full
                if len(self.all_workers) < self.pool_size:
                    break

        # Create thread with lock
        with self.create_lock:
            # Wait if reached max thread
            # Check without `create_lock` first, otherwise will be 10x slower
            # if multiple thread trying to get `create_lock`
            if len(self.all_workers) >= self.pool_size:
                # See release_full_lock()
                try:
                    self.notify_worker.release()
                except RuntimeError:
                    # Race condition when multiple threads trying to get thread worker
                    # It's ok to treat multiple release as one
                    pass
                while 1:
                    # If any worker finishes within timeout, we can get it
                    # Race condition when all workers just done `release_full_lock` and no one notifies
                    # To handle that, we acquire with timeout and check if there's idle worker
                    self.notify_pool.acquire(timeout=0.01)
                    # Re-acquire `notify_worker` so other workers can
                    # call `release_full_lock` for next `_get_thread_worker`
                    self.notify_worker.acquire(blocking=False)
                    # A worker just idle
                    try:
                        worker, _ = self.idle_workers.popitem()
                        return worker
                    except KeyError:
                        # Race condition when multiple threads trying to get thread worker,
                        # they all pass through full lock check and pop the only idle worker.
                        # Just let the slower ones do full lock check again
                        pass
                    # A thread just existed, pool no longer full
                    if len(self.all_workers) < self.pool_size:
                        break
            else:
                # A thread just idle while we were waiting for `create_lock`
                try:
                    worker, _ = self.idle_workers.popitem()
                    # logger.info(f'reuse worker thread: {worker.default_name}')
                    return worker
                except KeyError:
                    pass
            # Create connection
            worker = self.new_conn(self.file)
            self.all_workers[worker] = None
        # logger.info(f'New worker thread: {worker.default_name}')
        return worker

    def cursor(self):
        """
        Returns:
            SqlitePoolCursor:
        """
        conn = self._get_thread_worker()
        cursor = conn.cursor(SqlitePoolCursor)

        self.last_use[conn] = time.time()
        cursor.pool = self
        return cursor

    def exclusive_transaction(self):
        """
        Provides a cursor within a single EXCLUSIVE transaction.
        Commits on successful exit, rolls back on exception.

        Usage:
            with pool.exclusive_transaction() as c:
                cursor.execute(...)
                cursor.execute(...)
        """
        cursor = self.cursor()
        return ExclusiveTransaction(cursor)

    def gc(self, idle=60):
        """
        Close connections that have not been used for more than 60s
        """
        to_close = []
        with self.create_lock:
            now = time.time()
            # List keys first, so we can delete while iterating
            idle_workers = list(self.idle_workers)
            for conn in idle_workers:
                try:
                    last_use = self.last_use[conn]
                except KeyError:
                    # no last_ues, probably a newly created connection
                    continue
                if now - last_use <= idle:
                    # not an idle connection
                    continue

                # now this is an idle connection
                # remove from idle_workers, so other threads cannot take it
                try:
                    del self.idle_workers[conn]
                except KeyError:
                    # already taken by other thread
                    continue
                try:
                    del self.last_use[conn]
                except KeyError:
                    continue
                # mark this connection is ready to close
                to_close.append(conn)

        # close connection outside of lock to improve performance
        for conn in to_close:
            try:
                del self.all_workers[conn]
            except KeyError:
                # this shouldn't happen
                pass
            self.release_full_lock()
            # close
            conn.close()

    def release_all(self):
        """
        Release all connections at the end of lifespan
        """
        # copy with lock, release without lock
        with self.create_lock:
            all_conn = list(self.all_workers.keys())
            self.idle_workers.clear()
            self.last_use.clear()
            self.all_workers.clear()
            self.release_full_lock()

        for conn in all_conn:
            try:
                conn.close()
            except Exception:
                pass


class SqlitePool:
    def __init__(self, pool_size=4):
        """
        Args:
            pool_size (int): Max connections for each database
        """
        self.pool_size = pool_size

        self.all_pool: 'dict[str, ConnectionPool]' = {}
        self.create_lock = Lock()

    def get_pool(self, file):
        """
        Args:
            file (str):

        Returns:
            ConnectionPool:
        """
        if not file:
            raise ValueError(f'File name cannot be empty, got "{file}"')
        # but ":memory:" is allowed

        try:
            return self.all_pool[file]
        except KeyError:
            pass

        # create
        with self.create_lock:
            # another thread may have created pool
            # while current thread was waiting for lock
            try:
                return self.all_pool[file]
            except KeyError:
                pass

            # create
            pool = ConnectionPool(file, self.pool_size)
            self.all_pool[file] = pool
            return pool

    def cursor(self, file):
        """
        Get a cursor to operate sqlite file, with connection reuse
        costs 2.7us if connection reused
        costs 129us if create new connection (110us for direct sqlite3.Connection call)

        Args:
            file (str): Absolute filepath to database or ":memory:" for in-memory database
                Due to connection pool, in-memory database is shared,
                meaning every ":memory:" connect returns the same db.

        Returns:
            SqlitePoolCursor:

        Examples:
            with SQLITE_POOL.cursor(file) as cursor:
                cursor.execute(...)
        """
        pool = self.get_pool(file)
        return pool.cursor()

    def exclusive_transaction(self, file):
        """
        Provides a cursor within a single EXCLUSIVE transaction.
        Commits on successful exit, rolls back on exception.

        Args:
            file (str):

        Returns:
            ExclusiveTransaction:

        Usage:
            with pool.exclusive_transaction() as cursor:
                cursor.execute(...)
                cursor.execute(...)
        """
        pool = self.get_pool(file)
        return pool.exclusive_transaction()

    def gc(self, idle=60):
        """
        Close connections that have not been used for more than 60s
        """
        with self.create_lock:
            # List pools first, so we can delete while iterating
            all_pool = list(self.all_pool.items())
            if not all_pool:
                return

            for file, pool in all_pool:
                pool.gc(idle)
                if pool.all_workers:
                    # still using
                    continue
                # delete pool entry
                # it just ok to have race condition when another thread taken the pool we are about to delete
                # that thread will use its old pool, and new requests will have new pool
                try:
                    del self.all_pool[file]
                except KeyError:
                    # this shouldn't happen
                    continue

    def release_all(self):
        """
        Release all connections at the end of lifespan
        """
        # copy with lock, release without lock
        with self.create_lock:
            all_pool = list(self.all_pool.values())
            self.all_pool.clear()

        for pool in all_pool:
            pool.release_all()

    def rename_file(self, old_file, new_file):
        """
        Release pool of old_file and rename it.

        Args:
            old_file (str):
            new_file (str):

        Returns:
            bool: If success
        """
        if not old_file:
            raise ValueError(f'Old name cannot be empty, got "{old_file}"')
        if not new_file:
            raise ValueError(f'Old name cannot be empty, got "{new_file}"')
        if old_file == ':memory:':
            raise ValueError(
                f'Cannot rename memory database "{old_file}" to "{new_file}"'
            )
        if new_file == ':memory:':
            raise ValueError(
                f'Cannot rename "{old_file}" to memory database "{new_file}"'
            )

        with self.create_lock:
            try:
                pool = self.all_pool.pop(old_file)
            except KeyError:
                # no such pool, no need to release
                pass
            else:
                # Delete within create_lock, because we need to prevent other threads starts using the file
                pool.release_all()

            # rename file
            return atomic_rename(old_file, new_file)

    def delete_file(self, file):
        """
        Release pool of specific file and delete the file.

        Args:
            file (str):

        Returns:
            bool: If success
        """
        with self.create_lock:
            try:
                pool = self.all_pool.pop(file)
            except KeyError:
                # no such pool, no need to release
                pass
            else:
                # Delete within create_lock, because we need to prevent other threads starts using the file
                pool.release_all()

            # delete file
            if file and file != ':memory:':
                return atomic_remove(file)


SQLITE_POOL = SqlitePool()
