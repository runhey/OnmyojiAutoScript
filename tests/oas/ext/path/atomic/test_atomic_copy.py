"""
Tests for the copy functions of oas.ext.path.atomic.

Covered: _copy_iter() with its buffer reuse, file_copy() and
atomic_copy() with the Windows PermissionError retry.

The tests run on the in-memory fake filesystem (the fs fixture), the
real disk is never touched.
"""
import os

import pytest

from oas.ext.path import atomic
from oas.ext.path.atomic import (
    _copy_iter, atomic_copy, file_copy, file_read_bytes, is_tmp_file, windows_attempt_delay
)
from oas.testing.filesystem import fs  # noqa: F401
from tests.oas.ext.path.atomic.helpers import break_function, record_sleeps


class TestCopyIter:
    """Test cases for _copy_iter()."""

    def test_copy_chunks(self, fs):
        """The source should be read into the buffer, the chunks yielded."""
        fs.create_file('/data/a.bin', contents=b'abcdefghij')
        buffer = memoryview(bytearray(4))
        assert [bytes(chunk) for chunk in _copy_iter('/data/a.bin', buffer, 4)] == [b'abcd', b'efgh', b'ij']

    def test_copy_buffer_reuse(self, fs):
        """A full chunk should be the buffer itself, the memory is reused."""
        fs.create_file('/data/a.bin', contents=b'abcdefghij')
        buffer = memoryview(bytearray(4))
        chunks = list(_copy_iter('/data/a.bin', buffer, 4))
        assert [len(chunk) for chunk in chunks] == [4, 4, 2]
        assert chunks[0] is buffer
        assert chunks[1] is buffer
        # the last chunk is a slice, only its own part of the buffer
        assert chunks[2] is not buffer

    def test_copy_exact_chunks(self, fs):
        """A file of an exact chunk size should not yield an empty chunk."""
        fs.create_file('/data/a.bin', contents=b'abcdefgh')
        buffer = memoryview(bytearray(4))
        assert [len(chunk) for chunk in _copy_iter('/data/a.bin', buffer, 4)] == [4, 4]

    def test_copy_smaller_than_buffer(self, fs):
        """A file smaller than the buffer should be yielded with its own length."""
        fs.create_file('/data/a.bin', contents=b'abc')
        buffer = memoryview(bytearray(8))
        assert [bytes(chunk) for chunk in _copy_iter('/data/a.bin', buffer, 8)] == [b'abc']

    def test_copy_empty(self, fs):
        """An empty file should yield nothing."""
        fs.create_file('/data/a.bin', contents=b'')
        assert list(_copy_iter('/data/a.bin', memoryview(bytearray(4)), 4)) == []

    def test_copy_zero_read_stops(self, fs, monkeypatch):
        """A read of 0 bytes should stop the iteration."""
        monkeypatch.setattr(atomic, 'atomic_read_bytes_into', lambda file, buffer: iter([0]))
        assert list(_copy_iter('/data/a.bin', memoryview(bytearray(4)), 4)) == []


class TestFileCopy:
    """Test cases for file_copy()."""

    def test_copy(self, fs):
        """The content should be copied to the target, the source is kept."""
        fs.create_file('/data/a.bin', contents=b'data')
        file_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b'data'
        assert file_read_bytes('/data/a.bin') == b'data'

    def test_copy_chunk_size(self, fs):
        """A small chunk size should not change the result."""
        fs.create_file('/data/a.bin', contents=b'abcdefg')
        file_copy('/data/a.bin', '/data/b.bin', chunk_size=3)
        assert file_read_bytes('/data/b.bin') == b'abcdefg'

    def test_copy_creates_parents(self, fs):
        """The parent folders of the target should be created."""
        fs.create_file('/data/a.bin', contents=b'data')
        file_copy('/data/a.bin', '/data/new/b.bin')
        assert file_read_bytes('/data/new/b.bin') == b'data'

    def test_copy_over_existing(self, fs):
        """An existing target should be replaced."""
        fs.create_file('/data/a.bin', contents=b'data')
        fs.create_file('/data/b.bin', contents=b'long old content')
        file_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b'data'

    def test_copy_empty(self, fs):
        """An empty source should create an empty target, not no target."""
        fs.create_file('/data/a.bin', contents=b'')
        file_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b''
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_empty_over_existing(self, fs):
        """An empty source should empty an existing target."""
        fs.create_file('/data/a.bin', contents=b'')
        fs.create_file('/data/b.bin', contents=b'long old content')
        file_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b''

    def test_copy_empty_creates_parents(self, fs):
        """The parent folders of the target should be created for an empty source."""
        fs.create_file('/data/a.bin', contents=b'')
        file_copy('/data/a.bin', '/data/new/b.bin')
        assert file_read_bytes('/data/new/b.bin') == b''

    def test_copy_missing_source(self, fs):
        """A missing source should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_copy('/missing.bin', '/data/b.bin')


class TestAtomicCopy:
    """Test cases for atomic_copy()."""

    def test_copy(self, fs):
        """The content should be copied, no tmp file left behind."""
        fs.create_file('/data/a.bin', contents=b'data')
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b'data'
        assert file_read_bytes('/data/a.bin') == b'data'
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_chunk_size(self, fs):
        """A small chunk size should not change the result."""
        fs.create_file('/data/a.bin', contents=b'abcdefg')
        atomic_copy('/data/a.bin', '/data/b.bin', chunk_size=3)
        assert file_read_bytes('/data/b.bin') == b'abcdefg'
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_over_existing(self, fs):
        """An existing target should be replaced."""
        fs.create_file('/data/a.bin', contents=b'data')
        fs.create_file('/data/b.bin', contents=b'long old content')
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b'data'
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_empty(self, fs):
        """An empty source should give an empty target, no tmp file left behind."""
        fs.create_file('/data/a.bin', contents=b'')
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b''
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_empty_over_existing(self, fs):
        """An empty source should empty an existing target."""
        fs.create_file('/data/a.bin', contents=b'')
        fs.create_file('/data/b.bin', contents=b'long old content')
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b''
        assert os.listdir('/data') == ['a.bin', 'b.bin']

    def test_copy_to_other_folder(self, fs):
        """The target may live in another folder."""
        fs.create_file('/data/src/a.bin', contents=b'data')
        fs.create_dir('/data/dst')
        atomic_copy('/data/src/a.bin', '/data/dst/b.bin')
        assert file_read_bytes('/data/dst/b.bin') == b'data'
        assert os.listdir('/data/src') == ['a.bin']
        assert os.listdir('/data/dst') == ['b.bin']

    def test_copy_uses_tmp_of_source(self, fs, monkeypatch):
        """The content should be written to a tmp file next to the source first."""
        fs.create_file('/data/a.bin', contents=b'data')
        seen = []
        original = atomic.file_copy

        def checking_copy(source, target, chunk_size=None):
            seen.append((source, target))
            assert source == '/data/a.bin'
            assert os.path.dirname(target) == '/data'
            assert is_tmp_file(target) is True
            return original(source, target, chunk_size=chunk_size)

        monkeypatch.setattr(atomic, 'file_copy', checking_copy)
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert len(seen) == 1
        assert file_read_bytes('/data/b.bin') == b'data'

    def test_copy_failure_cleans_tmp(self, fs, monkeypatch):
        """The tmp file should be removed when the replace fails."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        fs.create_file('/data/a.bin', contents=b'data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'replace', [error])
        with pytest.raises(PermissionError) as e:
            atomic_copy('/data/a.bin', '/data/b.bin')
        assert e.value is error
        assert len(calls) == 1
        assert os.listdir('/data') == ['a.bin']
        assert file_read_bytes('/data/a.bin') == b'data'

    def test_copy_read_error_cleans_tmp(self, fs, monkeypatch):
        """The tmp file should be removed when the source read fails midway."""
        fs.create_file('/data/a.bin', contents=b'abcdefgh')
        real_read = atomic.atomic_read_bytes_into

        def broken_read(file, buffer):
            read = real_read(file, buffer)
            yield next(read)
            raise RuntimeError('source read failed midway')

        monkeypatch.setattr(atomic, 'atomic_read_bytes_into', broken_read)
        with pytest.raises(RuntimeError, match='source read failed midway'):
            atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/a.bin') == b'abcdefgh'
        assert os.listdir('/data') == ['a.bin']

    def test_copy_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        fs.create_file('/data/a.bin', contents=b'data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'replace', [error])
        atomic_copy('/data/a.bin', '/data/b.bin')
        assert file_read_bytes('/data/b.bin') == b'data'
        assert os.listdir('/data') == ['a.bin', 'b.bin']
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]
