"""
Tests for the write functions of oas.ext.path.atomic.

Covered: the file movers (atomic_replace, atomic_rename), the writers
(file_write, file_write_stream, afile_write_stream, atomic_write,
atomic_write_stream) and the file creators (file_ensure_exist,
file_touch). The tmp file helpers (random_id, is_tmp_file, to_tmp_file,
to_nontmp_file, windows_attempt_delay) and replace_tmp are covered in
test_atomic_tmp.py.

The tests run on the in-memory fake filesystem (the fs fixture), the
real disk is never touched. The Windows retry loops are tested on every
platform by patching IS_WINDOWS, the retries never wait in real time
(record_sleeps) and the file locks are simulated by breaking the os
functions (break_function).
"""
import os
import stat

import numpy
import pytest

from oas.ext.path import atomic
from oas.ext.path.atomic import (
    WINDOWS_MAX_ATTEMPT, afile_write_stream, atomic_rename, atomic_replace, atomic_write, atomic_write_stream,
    file_ensure_exist, file_read_bytes, file_read_text, file_touch, file_write, file_write_stream, is_tmp_file,
    windows_attempt_delay
)
from oas.testing.filesystem import fs  # noqa: F401
from oas.testing.filesystem.base import IS_WINDOWS as FS_IS_WINDOWS
from tests.oas.ext.path.atomic.helpers import break_function, record_sleeps


class TestAtomicReplace:
    """Test cases for atomic_replace()."""

    def test_replace(self, fs):
        """The source should replace an existing target."""
        file_write('/data/a.txt', 'new')
        file_write('/data/b.txt', 'old')
        atomic_replace('/data/a.txt', '/data/b.txt')
        assert file_read_text('/data/b.txt') == 'new'
        assert not os.path.exists('/data/a.txt')

    def test_replace_to_new_path(self, fs):
        """A missing target should be created."""
        file_write('/data/a.txt', 'data')
        atomic_replace('/data/a.txt', '/data/b.txt')
        assert file_read_text('/data/b.txt') == 'data'
        assert not os.path.exists('/data/a.txt')

    def test_replace_folder(self, fs):
        """A folder should be moved as well."""
        file_write('/data/folder/a.txt', 'data')
        atomic_replace('/data/folder', '/data/moved')
        assert file_read_text('/data/moved/a.txt') == 'data'
        assert not os.path.exists('/data/folder')

    def test_replace_missing_source(self, fs, monkeypatch):
        """A missing source should raise FileNotFoundError, without a retry."""
        calls = break_function(monkeypatch, os, 'replace', [])
        with pytest.raises(FileNotFoundError):
            atomic_replace('/data/missing.txt', '/data/b.txt')
        assert len(calls) == 1

    def test_replace_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        file_write('/data/a.txt', 'data')
        calls = break_function(monkeypatch, os, 'replace', [error])
        atomic_replace('/data/a.txt', '/data/b.txt')
        assert file_read_text('/data/b.txt') == 'data'
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_replace_gives_up_on_windows(self, fs, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        file_write('/data/a.txt', 'data')
        calls = break_function(monkeypatch, os, 'replace', [error] * WINDOWS_MAX_ATTEMPT)
        with pytest.raises(PermissionError) as e:
            atomic_replace('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]

    def test_replace_windows_other_error(self, fs, monkeypatch):
        """An unexpected error should not be retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = OSError('Other error')
        file_write('/data/a.txt', 'data')
        calls = break_function(monkeypatch, os, 'replace', [error])
        with pytest.raises(OSError) as e:
            atomic_replace('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == 1
        assert sleeps.sleeps == []

    def test_replace_posix_no_retry(self, monkeypatch):
        """On the other platforms the error is raised right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'replace', [error])
        with pytest.raises(PermissionError) as e:
            atomic_replace('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == 1


class TestAtomicRename:
    """Test cases for atomic_rename()."""

    def test_rename(self, fs):
        """The source should be renamed."""
        file_write('/data/a.txt', 'data')
        atomic_rename('/data/a.txt', '/data/b.txt')
        assert file_read_text('/data/b.txt') == 'data'
        assert not os.path.exists('/data/a.txt')

    def test_rename_over_existing(self, fs):
        """os.rename() refuses an existing target on Windows, replaces it on the other platforms."""
        file_write('/data/a.txt', 'new')
        file_write('/data/b.txt', 'old')
        if FS_IS_WINDOWS:
            with pytest.raises(FileExistsError):
                atomic_rename('/data/a.txt', '/data/b.txt')
            assert file_read_text('/data/a.txt') == 'new'
            assert file_read_text('/data/b.txt') == 'old'
        else:
            atomic_rename('/data/a.txt', '/data/b.txt')
            assert file_read_text('/data/b.txt') == 'new'
            assert not os.path.exists('/data/a.txt')

    @pytest.mark.parametrize('error', [FileNotFoundError(2, 'No such file or directory'), FileExistsError(17, 'File exists')])
    def test_rename_immediate_errors_on_windows(self, monkeypatch, error):
        """FileNotFoundError and FileExistsError should not be retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = break_function(monkeypatch, os, 'rename', [error])
        with pytest.raises(type(error)) as e:
            atomic_rename('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == 1
        assert sleeps.sleeps == []

    def test_rename_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        file_write('/data/a.txt', 'data')
        calls = break_function(monkeypatch, os, 'rename', [error])
        atomic_rename('/data/a.txt', '/data/b.txt')
        assert file_read_text('/data/b.txt') == 'data'
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_rename_gives_up_on_windows(self, fs, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        file_write('/data/a.txt', 'data')
        calls = break_function(monkeypatch, os, 'rename', [error] * WINDOWS_MAX_ATTEMPT)
        with pytest.raises(PermissionError) as e:
            atomic_rename('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]

    def test_rename_posix_no_retry(self, monkeypatch):
        """On the other platforms the error is raised right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'rename', [error])
        with pytest.raises(PermissionError) as e:
            atomic_rename('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == 1

    def test_rename_windows_other_error(self, monkeypatch):
        """An unexpected error should not be retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = OSError('Other error')
        calls = break_function(monkeypatch, os, 'rename', [error])
        with pytest.raises(OSError) as e:
            atomic_rename('/data/a.txt', '/data/b.txt')
        assert e.value is error
        assert len(calls) == 1
        assert sleeps.sleeps == []


class TestFileWrite:
    """Test cases for file_write()."""

    def test_write_text(self, fs):
        """Text should be written as utf-8 with no newline translation."""
        file_write('/data/a.txt', 'a\nb')
        assert file_read_bytes('/data/a.txt') == b'a\nb'
        assert file_read_text('/data/a.txt') == 'a\nb'

    def test_write_unicode(self, fs):
        """Unicode text should be written as utf-8."""
        file_write('/data/a.txt', '你好 🚀')
        assert file_read_bytes('/data/a.txt') == '你好 🚀'.encode('utf-8')

    @pytest.mark.parametrize('data', [b'\x00\x01\xff', bytearray(b'\x00\x01\xff'), memoryview(b'\x00\x01\xff')])
    def test_write_bytes(self, fs, data):
        """Bytes and bytes-like data should be written as-is."""
        file_write('/data/a.bin', data)
        assert file_read_bytes('/data/a.bin') == b'\x00\x01\xff'

    def test_write_empty_bytes(self, fs):
        """Writing empty bytes should still create the file."""
        file_write('/data/a.bin', b'')
        assert file_read_bytes('/data/a.bin') == b''

    def test_write_ndarray(self, fs):
        """A numpy array should be written as raw bytes."""
        file_write('/data/a.bin', numpy.array([1, 2, 255], dtype=numpy.uint8))
        assert file_read_bytes('/data/a.bin') == b'\x01\x02\xff'

    def test_write_creates_parents(self, fs, monkeypatch):
        """The parent folders should be created when the first open() fails."""
        calls = break_function(monkeypatch, atomic, 'open', [FileNotFoundError(2, 'No such file or directory')])
        makedirs = break_function(monkeypatch, os, 'makedirs', [])
        file_write('/data/a/b/c.txt', 'data')
        assert len(calls) == 2
        assert makedirs == [(('/data/a/b',), {'exist_ok': True})]
        assert file_read_text('/data/a/b/c.txt') == 'data'

    def test_write_overwrite(self, fs):
        """An existing file should be truncated to the new content."""
        file_write('/data/a.txt', 'hello world')
        file_write('/data/a.txt', 'hi')
        assert file_read_bytes('/data/a.txt') == b'hi'

    def test_write_unsupported_type(self, fs):
        """Other types default to text mode, write() refuses them."""
        with pytest.raises(TypeError):
            file_write('/data/a.txt', 123)


class TestFileWriteStream:
    """Test cases for file_write_stream()."""

    def test_write_text(self, fs):
        """Text chunks should be written with no newline translation."""
        file_write_stream('/data/a.txt', iter(['a\n', 'b\n']))
        assert file_read_bytes('/data/a.txt') == b'a\nb\n'

    def test_write_bytes(self, fs):
        """Bytes chunks should be written as-is."""
        file_write_stream('/data/a.bin', iter([b'ab', b'cd']))
        assert file_read_bytes('/data/a.bin') == b'abcd'

    def test_write_bytes_like(self, fs):
        """The mode is taken from the first chunk, the later chunks follow it."""
        file_write_stream('/data/a.bin', iter([bytearray(b'ab'), memoryview(b'cd')]))
        assert file_read_bytes('/data/a.bin') == b'abcd'

    def test_write_empty(self, fs):
        """A generator that yields nothing should create an empty file."""
        file_write_stream('/data/a/b.txt', iter([]))
        assert file_read_bytes('/data/a/b.txt') == b''
        assert os.listdir('/data/a') == ['b.txt']

    def test_write_empty_over_existing(self, fs):
        """An empty generator should empty an existing file."""
        file_write('/data/a.txt', 'old content')
        file_write_stream('/data/a.txt', iter([]))
        assert file_read_bytes('/data/a.txt') == b''

    def test_write_empty_creates_parents(self, fs, monkeypatch):
        """The parent folders should be created for an empty generator too."""
        calls = break_function(monkeypatch, atomic, 'open', [FileNotFoundError(2, 'No such file or directory')])
        makedirs = break_function(monkeypatch, os, 'makedirs', [])
        file_write_stream('/data/a/b.txt', iter([]))
        assert len(calls) == 2
        assert makedirs == [(('/data/a',), {'exist_ok': True})]
        assert file_read_bytes('/data/a/b.txt') == b''

    def test_write_creates_parents(self, fs, monkeypatch):
        """All the chunks should be written after the parent folders are created."""
        calls = break_function(monkeypatch, atomic, 'open', [FileNotFoundError(2, 'No such file or directory')])
        makedirs = break_function(monkeypatch, os, 'makedirs', [])
        file_write_stream('/data/a/b/c.txt', iter(['x', 'y', 'z']))
        assert len(calls) == 2
        assert makedirs == [(('/data/a/b',), {'exist_ok': True})]
        assert file_read_text('/data/a/b/c.txt') == 'xyz'

    def test_write_unsupported_type(self, fs):
        """Other chunk types default to text mode, write() refuses them."""
        with pytest.raises(TypeError):
            file_write_stream('/data/a.txt', iter([123]))


class TestAfileWriteStream:
    """Test cases for afile_write_stream()."""

    @pytest.mark.trio
    async def test_write_text(self, fs):
        """Text chunks should be written with no newline translation."""
        async def chunks():
            yield 'a\n'
            yield 'b\n'

        await afile_write_stream('/data/a.txt', chunks())
        assert file_read_bytes('/data/a.txt') == b'a\nb\n'

    @pytest.mark.trio
    async def test_write_bytes(self, fs):
        """Bytes chunks should be written as-is."""
        async def chunks():
            yield b'ab'
            yield b'cd'

        await afile_write_stream('/data/a.bin', chunks())
        assert file_read_bytes('/data/a.bin') == b'abcd'

    @pytest.mark.trio
    async def test_write_empty(self, fs):
        """An iterator that yields nothing should create an empty file."""
        async def chunks():
            for chunk in []:
                yield chunk

        await afile_write_stream('/data/a/b.txt', chunks())
        assert file_read_bytes('/data/a/b.txt') == b''
        assert os.listdir('/data/a') == ['b.txt']

    @pytest.mark.trio
    async def test_write_creates_parents(self, fs, monkeypatch):
        """All the chunks should be written after the parent folders are created."""
        calls = break_function(monkeypatch, atomic, 'open', [FileNotFoundError(2, 'No such file or directory')])
        makedirs = break_function(monkeypatch, os, 'makedirs', [])

        async def chunks():
            yield 'x'
            yield 'y'
            yield 'z'

        await afile_write_stream('/data/a/b/c.txt', chunks())
        assert len(calls) == 2
        assert makedirs == [(('/data/a/b',), {'exist_ok': True})]
        assert file_read_text('/data/a/b/c.txt') == 'xyz'

    @pytest.mark.trio
    async def test_write_unsupported_type(self, fs):
        """Other chunk types default to text mode, write() refuses them."""
        async def chunks():
            yield 123

        with pytest.raises(TypeError):
            await afile_write_stream('/data/a.txt', chunks())


class TestAtomicWrite:
    """Test cases for atomic_write()."""

    def test_write(self, fs):
        """The data should be written and no tmp file left behind."""
        atomic_write('/data/a/b.txt', 'data')
        assert file_read_text('/data/a/b.txt') == 'data'
        assert os.listdir('/data/a') == ['b.txt']

    def test_write_bytes(self, fs):
        """Bytes data should be written as-is."""
        atomic_write('/data/a.bin', b'\x00\x01')
        assert file_read_bytes('/data/a.bin') == b'\x00\x01'

    def test_write_overwrite(self, fs):
        """An existing file should be replaced by the new content."""
        atomic_write('/data/a.txt', 'old')
        atomic_write('/data/a.txt', 'new data')
        assert file_read_text('/data/a.txt') == 'new data'
        assert os.listdir('/data') == ['a.txt']

    def test_write_replaces_complete_tmp(self, fs, monkeypatch):
        """The target should only be replaced once the tmp file holds the whole content."""
        original = os.replace
        seen = []

        def checking_replace(src, dst):
            # the tmp file is a sibling of the target and already complete
            assert os.path.dirname(src) == '/data'
            assert is_tmp_file(src) is True
            assert file_read_bytes(src) == b'payload'
            seen.append((src, dst))
            return original(src, dst)

        monkeypatch.setattr(os, 'replace', checking_replace)
        atomic_write('/data/a.txt', 'payload')
        assert len(seen) == 1
        assert seen[0][1] == '/data/a.txt'
        assert file_read_text('/data/a.txt') == 'payload'

    def test_write_failure_cleans_tmp(self, fs, monkeypatch):
        """The tmp file should be removed when the replace fails."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'replace', [error])
        with pytest.raises(PermissionError) as e:
            atomic_write('/data/a.txt', 'data')
        assert e.value is error
        assert len(calls) == 1
        assert os.listdir('/data') == []

    def test_write_error_cleans_tmp(self, fs):
        """A failed write should remove the tmp file and keep the target."""
        file_write('/data/a.txt', 'old content')
        with pytest.raises(TypeError):
            # the tmp file is opened, then write() refuses the data
            atomic_write('/data/a.txt', 12345)
        assert file_read_text('/data/a.txt') == 'old content'
        assert os.listdir('/data') == ['a.txt']

    def test_write_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        break_function(monkeypatch, os, 'replace', [error])
        atomic_write('/data/a.txt', 'data')
        assert file_read_text('/data/a.txt') == 'data'
        assert os.listdir('/data') == ['a.txt']
        assert sleeps.sleeps == [windows_attempt_delay(0)]


class TestAtomicWriteStream:
    """Test cases for atomic_write_stream()."""

    def test_write_stream(self, fs):
        """The chunks should be written and no tmp file left behind."""
        atomic_write_stream('/data/a/b.txt', iter(['a', 'b']))
        assert file_read_text('/data/a/b.txt') == 'ab'
        assert os.listdir('/data/a') == ['b.txt']

    def test_write_stream_bytes(self, fs):
        """Bytes chunks should be written as-is."""
        atomic_write_stream('/data/a.bin', iter([b'ab', b'cd']))
        assert file_read_bytes('/data/a.bin') == b'abcd'

    def test_write_stream_empty(self, fs):
        """An empty generator should write an empty file, like atomic_write(file, b'')."""
        atomic_write_stream('/data/a/b.txt', iter([]))
        assert file_read_bytes('/data/a/b.txt') == b''
        assert os.listdir('/data/a') == ['b.txt']

    def test_write_stream_empty_over_existing(self, fs):
        """An empty generator should empty an existing file."""
        file_write('/data/a.txt', 'old content')
        atomic_write_stream('/data/a.txt', iter([]))
        assert file_read_bytes('/data/a.txt') == b''
        assert os.listdir('/data') == ['a.txt']

    def test_write_stream_creates_parents(self, fs):
        """The parent folders should be created automatically."""
        atomic_write_stream('/data/a/b/c.txt', iter(['x', 'y']))
        assert file_read_text('/data/a/b/c.txt') == 'xy'

    def test_write_stream_mode(self, fs):
        """The mode should be used for the written file."""
        atomic_write_stream('/data/a.sh', iter(['x']), mode=0o755)
        assert stat.S_IMODE(os.stat('/data/a.sh').st_mode) == 0o755

    def test_write_stream_mode_before_replace(self, fs, monkeypatch):
        """The mode should be set on the tmp file, before it replaces the target."""
        original = os.replace
        seen = []

        def checking_replace(src, dst):
            seen.append(stat.S_IMODE(os.stat(src).st_mode))
            return original(src, dst)

        monkeypatch.setattr(os, 'replace', checking_replace)
        atomic_write_stream('/data/a.sh', iter(['x']), mode=0o755)
        assert seen == [0o755]

    def test_write_stream_failure_cleans_tmp(self, fs, monkeypatch):
        """The tmp file should be removed when the replace fails."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'replace', [error])
        with pytest.raises(PermissionError) as e:
            atomic_write_stream('/data/a.txt', iter(['data']))
        assert e.value is error
        assert len(calls) == 1
        assert os.listdir('/data') == []

    def test_write_stream_error_cleans_tmp(self, fs):
        """The tmp file should be removed when the generator fails midway."""
        file_write('/data/a.txt', 'old content')

        def chunks():
            yield 'new'
            raise RuntimeError('generator failed midway')

        with pytest.raises(RuntimeError, match='generator failed midway'):
            atomic_write_stream('/data/a.txt', chunks())
        assert file_read_text('/data/a.txt') == 'old content'
        assert os.listdir('/data') == ['a.txt']

    def test_write_stream_failure_before_chunk(self, fs):
        """A generator failing before yielding should leave no tmp file."""
        def chunks():
            raise RuntimeError('generator failed at once')
            yield 'never'

        with pytest.raises(RuntimeError, match='generator failed at once'):
            atomic_write_stream('/data/a.txt', chunks())
        assert not os.path.exists('/data')

    def test_write_stream_chmod_error_cleans_tmp(self, fs, monkeypatch):
        """A failed chmod should remove the tmp file and keep the target."""
        file_write('/data/a.sh', 'old')
        error = OSError(1, 'Operation not permitted')
        calls = break_function(monkeypatch, os, 'chmod', [error])
        with pytest.raises(OSError) as e:
            atomic_write_stream('/data/a.sh', iter(['new']), mode=0o755)
        assert e.value is error
        assert len(calls) == 1
        assert file_read_text('/data/a.sh') == 'old'
        assert os.listdir('/data') == ['a.sh']

    def test_write_stream_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        break_function(monkeypatch, os, 'replace', [error])
        atomic_write_stream('/data/a.txt', iter(['data']))
        assert file_read_text('/data/a.txt') == 'data'
        assert os.listdir('/data') == ['a.txt']
        assert sleeps.sleeps == [windows_attempt_delay(0)]


class TestFileEnsureExist:
    """Test cases for file_ensure_exist()."""

    def test_create(self, fs):
        """A missing file should be created empty."""
        fs.create_dir('/data')
        assert file_ensure_exist('/data/a.txt') is True
        assert file_read_bytes('/data/a.txt') == b''

    def test_create_default(self, fs):
        """The default content should be written on creation."""
        fs.create_dir('/data')
        assert file_ensure_exist('/data/a.txt', default=b'data') is True
        assert file_read_bytes('/data/a.txt') == b'data'

    def test_missing_parent(self, fs):
        """A missing parent directory should be reported, nothing is created."""
        assert file_ensure_exist('/data/a.txt') is False
        assert not os.path.exists('/data')

    def test_exists(self, fs):
        """An existing file should be kept untouched."""
        file_write('/data/a.txt', 'data')
        assert file_ensure_exist('/data/a.txt', default=b'other') is False
        assert file_read_bytes('/data/a.txt') == b'data'

    def test_folder_in_the_way(self, fs):
        """A path that is a folder should be reported, not replaced."""
        fs.create_dir('/data/a.txt')
        assert file_ensure_exist('/data/a.txt') is False
        assert os.path.isdir('/data/a.txt')

    def test_mode(self, fs):
        """The mode should be used for the created file."""
        fs.create_dir('/data')
        assert file_ensure_exist('/data/a.txt', mode=0o600) is True
        assert stat.S_IMODE(os.stat('/data/a.txt').st_mode) == 0o600


class TestFileTouch:
    """Test cases for file_touch()."""

    def test_touch_create(self, fs):
        """A missing file should be created empty."""
        fs.create_dir('/data')
        file_touch('/data/a.txt')
        assert os.path.getsize('/data/a.txt') == 0

    def test_touch_missing_parent(self, fs):
        """A missing parent directory should raise, like the real os."""
        with pytest.raises(FileNotFoundError):
            file_touch('/data/a.txt')
        assert not os.path.exists('/data')

    def test_touch_update(self, fs):
        """An existing file should keep its content and get a new modify time."""
        file_write('/data/a.txt', 'data')
        os.utime('/data/a.txt', (0, 0))
        file_touch('/data/a.txt')
        assert file_read_text('/data/a.txt') == 'data'
        assert os.stat('/data/a.txt').st_mtime > 0

    def test_touch_not_exist_ok(self, fs):
        """A missing file should be created with exist_ok=False as well."""
        fs.create_dir('/data')
        file_touch('/data/a.txt', exist_ok=False)
        assert os.path.getsize('/data/a.txt') == 0

    def test_touch_exists_not_exist_ok(self, fs):
        """An existing file should be refused with exist_ok=False."""
        file_write('/data/a.txt', 'data')
        with pytest.raises(FileExistsError):
            file_touch('/data/a.txt', exist_ok=False)
        assert file_read_text('/data/a.txt') == 'data'
