"""
Thread safety of the in-memory fake filesystem.

The code under test may use the filesystem from several threads at once (the
asar module writes the extracted files on the project's thread pool), so a race
on the records would make the tests of that code flaky and hide real bugs. Every
operation of the filesystem takes the state lock of its filesystem; these tests
hammer it from several threads and check the result of such a run.
"""
import os
import threading

import pytest
from conftest import join

pytest.importorskip('oas.ext.concurrent.threadpool')

from oas.ext.concurrent.threadpool import THREAD_POOL  # noqa: E402
from oas.ext.path.atomic import file_read_bytes
from oas.testing.filesystem import fs  # noqa: F401


def write_atomically(path, content):
    """
    Write a file the way the atomic helpers of the project do.

    Args:
        path (str): Target path
        content (bytes): Content to write
    """
    tmp = f'{path}.tmp'
    with open(tmp, 'wb') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class TestThreadSafety:
    def test_concurrent_writes(self, fs):
        """Files written from several threads at once are all complete."""
        contents = {
            join(fs, 'f%d.bin' % index): (b'content %d ' % index) * 64
            for index in range(48)
        }
        with THREAD_POOL.wait_jobs() as pool:
            for path, content in contents.items():
                pool.start_thread_soon(write_atomically, path, content)
        for path, content in contents.items():
            assert fs.get_file(path).content == content
        assert [path for path in fs._files if path.endswith('.tmp')] == []

    def test_concurrent_directories(self, fs):
        """Directories created and written from several threads at once.

        Four threads share every directory of the tree, so the checks of
        ``makedirs(exist_ok=True)`` run against each other.
        """
        def write_nested(index):
            directory = join(fs, 'root', 'sub%d' % (index % 4))
            os.makedirs(directory, exist_ok=True)
            write_atomically(f'{directory}/f{index}.bin', b'data %d' % index)

        with THREAD_POOL.wait_jobs() as pool:
            for index in range(24):
                pool.start_thread_soon(write_nested, index)
        assert sorted(os.listdir(join(fs, 'root'))) == ['sub0', 'sub1', 'sub2', 'sub3']
        for index in range(24):
            assert file_read_bytes(f'{join(fs, "root", "sub%d" % (index % 4))}/f{index}.bin') == b'data %d' % index

    def test_a_listing_is_not_disturbed_by_a_write(self, fs):
        """Listing a directory while other threads write into it is safe.

        The listing walks the records of the filesystem: a write landing in the
        middle of a walk would make it raise (or read a torn state) when the
        operations do not take the lock.
        """
        directory = join(fs, 'data')
        os.makedirs(directory)
        stop = threading.Event()
        errors = []

        def list_until_stopped():
            try:
                while not stop.is_set():
                    os.listdir(directory)
            except BaseException as e:
                errors.append(e)

        def write_many(writer):
            for index in range(100):
                write_atomically(f'{directory}/f{writer}_{index}.bin', b'x')

        with THREAD_POOL.wait_jobs() as pool:
            lister = pool.start_thread_soon(list_until_stopped)
            writers = [pool.start_thread_soon(write_many, writer) for writer in range(3)]
            for job in writers:
                job.get()
            stop.set()
            lister.get()
        assert errors == []
        assert sorted(os.listdir(directory)) == sorted(
            f'f{writer}_{index}.bin' for writer in range(3) for index in range(100)
        )

    def test_an_operation_waits_for_the_lock(self, fs):
        """An operation of another thread waits while the state lock is held."""
        started = threading.Event()
        done = threading.Event()

        def create():
            started.set()
            fs.create_file('/data.txt', contents=b'hello')
            done.set()

        with fs._lock:
            thread = threading.Thread(target=create)
            thread.start()
            assert started.wait(5)
            # The operation is blocked on the lock: give it the chance to finish
            # (it must not) before the lock is released by this with block
            assert not done.wait(0.05)
        thread.join(5)
        assert done.is_set()
        assert file_read_bytes('/data.txt') == b'hello'
