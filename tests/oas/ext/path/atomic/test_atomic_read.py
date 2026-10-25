"""
Tests for the read functions of oas.ext.path.atomic.

Covered: file_read_text() / file_read_bytes() with the stream variants,
file_read_bytes_into(), the atomic_read_* wrappers with the Windows
PermissionError retry, and atomic_open().

The tests run on the in-memory fake filesystem (the fs fixture), the
real disk is never touched.
"""
import os

import pytest

from oas.ext.path import atomic
from oas.ext.path.atomic import (
    WINDOWS_MAX_ATTEMPT, atomic_open, atomic_read_bytes, atomic_read_bytes_into, atomic_read_bytes_stream,
    atomic_read_text, atomic_read_text_stream, file_read_bytes, file_read_bytes_into, file_read_bytes_stream,
    file_read_text, file_read_text_stream, windows_attempt_delay
)
from oas.testing.filesystem import fs  # noqa: F401
from tests.oas.ext.path.atomic.helpers import break_function, record_sleeps


class TestFileReadText:
    """Test cases for file_read_text()."""

    def test_read_utf8(self, fs):
        """UTF-8 should be the default encoding."""
        fs.create_file('/data/a.txt', contents='你好 world 🚀')
        assert file_read_text('/data/a.txt') == '你好 world 🚀'

    def test_read_encoding(self, fs):
        """The encoding argument should be used to decode the content."""
        fs.create_file('/data/gbk.txt', contents='测试'.encode('gbk'))
        assert file_read_text('/data/gbk.txt', encoding='gbk') == '测试'

    def test_read_errors_replace(self, fs):
        """errors='replace' should replace the invalid bytes."""
        fs.create_file('/data/bad.txt', contents=b'\xff\xfehello')
        assert file_read_text('/data/bad.txt', errors='replace') == '\ufffd\ufffdhello'

    def test_read_errors_strict(self, fs):
        """Invalid bytes should raise UnicodeDecodeError by default."""
        fs.create_file('/data/bad.txt', contents=b'\xff\xfehello')
        with pytest.raises(UnicodeDecodeError):
            file_read_text('/data/bad.txt')

    def test_read_newlines(self, fs):
        """CRLF should be translated to LF, like the real open()."""
        fs.create_file('/data/a.txt', contents=b'a\r\nb\rc\n')
        assert file_read_text('/data/a.txt') == 'a\nb\nc\n'

    def test_read_missing(self, fs):
        """A missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_read_text('/missing.txt')


class TestFileReadTextStream:
    """Test cases for file_read_text_stream()."""

    def test_read_chunks(self, fs):
        """The content should be yielded chunk by chunk."""
        fs.create_file('/data/a.txt', contents='abcdef')
        assert list(file_read_text_stream('/data/a.txt', chunk_size=4)) == ['abcd', 'ef']

    def test_read_exact_chunks(self, fs):
        """No empty chunk should be yielded at the end of an exact chunk."""
        fs.create_file('/data/a.txt', contents='abcdefgh')
        assert list(file_read_text_stream('/data/a.txt', chunk_size=4)) == ['abcd', 'efgh']

    def test_read_unicode(self, fs):
        """The chunk size counts characters, not bytes."""
        fs.create_file('/data/a.txt', contents='你好世界')
        assert list(file_read_text_stream('/data/a.txt', chunk_size=2)) == ['你好', '世界']

    def test_read_encoding(self, fs):
        """The encoding argument should be used to decode the content."""
        fs.create_file('/data/gbk.txt', contents='测试'.encode('gbk'))
        assert list(file_read_text_stream('/data/gbk.txt', encoding='gbk', chunk_size=1)) == ['测', '试']

    def test_read_empty(self, fs):
        """An empty file should yield nothing."""
        fs.create_file('/data/a.txt', contents='')
        assert list(file_read_text_stream('/data/a.txt')) == []

    def test_read_missing(self, fs):
        """A missing file should raise FileNotFoundError on iteration."""
        with pytest.raises(FileNotFoundError):
            list(file_read_text_stream('/missing.txt'))


class TestFileReadBytes:
    """Test cases for file_read_bytes()."""

    def test_read_bytes(self, fs):
        """The content should be read as bytes."""
        fs.create_file('/data/a.bin', contents=b'\x00\x01\xff')
        assert file_read_bytes('/data/a.bin') == b'\x00\x01\xff'

    def test_read_empty(self, fs):
        """An empty file should read as b''."""
        fs.create_file('/data/a.bin', contents=b'')
        assert file_read_bytes('/data/a.bin') == b''

    def test_read_missing(self, fs):
        """A missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_read_bytes('/missing.bin')


class TestFileReadBytesStream:
    """Test cases for file_read_bytes_stream()."""

    def test_read_chunks(self, fs):
        """The content should be yielded chunk by chunk."""
        fs.create_file('/data/a.bin', contents=b'abcdef')
        assert list(file_read_bytes_stream('/data/a.bin', chunk_size=4)) == [b'abcd', b'ef']

    def test_read_exact_chunks(self, fs):
        """No empty chunk should be yielded at the end of an exact chunk."""
        fs.create_file('/data/a.bin', contents=b'abcdefgh')
        assert list(file_read_bytes_stream('/data/a.bin', chunk_size=4)) == [b'abcd', b'efgh']

    def test_read_empty(self, fs):
        """An empty file should yield nothing."""
        fs.create_file('/data/a.bin', contents=b'')
        assert list(file_read_bytes_stream('/data/a.bin')) == []

    def test_read_missing(self, fs):
        """A missing file should raise FileNotFoundError on iteration."""
        with pytest.raises(FileNotFoundError):
            list(file_read_bytes_stream('/missing.bin'))


class TestFileReadBytesInto:
    """Test cases for file_read_bytes_into()."""

    def test_read_into_chunks(self, fs):
        """The buffer should be filled and the read length yielded."""
        fs.create_file('/data/a.bin', contents=b'hello world')
        buffer = memoryview(bytearray(4))
        chunks = [(n, bytes(buffer[:n])) for n in file_read_bytes_into('/data/a.bin', buffer)]
        assert chunks == [(4, b'hell'), (4, b'o wo'), (3, b'rld')]

    def test_read_into_larger_buffer(self, fs):
        """A buffer larger than the file should be filled once."""
        fs.create_file('/data/a.bin', contents=b'hello')
        buffer = memoryview(bytearray(16))
        assert list(file_read_bytes_into('/data/a.bin', buffer)) == [5]
        assert bytes(buffer[:5]) == b'hello'

    def test_read_into_bytearray(self, fs):
        """A plain bytearray is a valid buffer too."""
        fs.create_file('/data/a.bin', contents=b'abc')
        buffer = bytearray(2)
        assert list(file_read_bytes_into('/data/a.bin', buffer)) == [2, 1]
        assert bytes(buffer[:1]) == b'c'

    def test_read_into_empty(self, fs):
        """An empty file should yield nothing."""
        fs.create_file('/data/a.bin', contents=b'')
        assert list(file_read_bytes_into('/data/a.bin', memoryview(bytearray(4)))) == []

    def test_read_into_missing(self, fs):
        """A missing file should raise FileNotFoundError on iteration."""
        with pytest.raises(FileNotFoundError):
            list(file_read_bytes_into('/missing.bin', memoryview(bytearray(4))))


class TestAtomicReadText:
    """Test cases for atomic_read_text()."""

    def test_read(self, fs):
        """The content should be read like file_read_text() does."""
        fs.create_file('/data/a.txt', contents='data')
        assert atomic_read_text('/data/a.txt') == 'data'

    def test_read_arguments(self, fs, monkeypatch):
        """The encoding and errors arguments should be forwarded."""
        calls = []

        def fake_read(file, encoding=None, errors=None):
            calls.append((file, encoding, errors))
            return 'data'

        monkeypatch.setattr(atomic, 'file_read_text', fake_read)
        assert atomic_read_text('/data/a.txt', encoding='gbk', errors='ignore') == 'data'
        assert calls == [('/data/a.txt', 'gbk', 'ignore')]

    def test_read_retries_on_windows(self, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def flaky_read(file, encoding=None, errors=None):
            calls.append(file)
            if len(calls) < 3:
                raise error
            return 'data'

        monkeypatch.setattr(atomic, 'file_read_text', flaky_read)
        assert atomic_read_text('/data/a.txt') == 'data'
        assert len(calls) == 3
        assert sleeps.sleeps == [windows_attempt_delay(0), windows_attempt_delay(1)]

    def test_read_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_read(file, encoding=None, errors=None):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_text', locked_read)
        with pytest.raises(PermissionError) as e:
            atomic_read_text('/data/a.txt')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]

    def test_read_posix_no_retry(self, monkeypatch):
        """On platforms that allow reading while replacing, the error is not retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_read(file, encoding=None, errors=None):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_text', locked_read)
        with pytest.raises(PermissionError) as e:
            atomic_read_text('/data/a.txt')
        assert e.value is error
        assert len(calls) == 1


class TestAtomicReadBytes:
    """Test cases for atomic_read_bytes()."""

    def test_read(self, fs):
        """The content should be read like file_read_bytes() does."""
        fs.create_file('/data/a.bin', contents=b'data')
        assert atomic_read_bytes('/data/a.bin') == b'data'

    def test_read_retries_on_windows(self, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def flaky_read(file):
            calls.append(file)
            if len(calls) < 2:
                raise error
            return b'data'

        monkeypatch.setattr(atomic, 'file_read_bytes', flaky_read)
        assert atomic_read_bytes('/data/a.bin') == b'data'
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_read_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_read(file):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_bytes', locked_read)
        with pytest.raises(PermissionError) as e:
            atomic_read_bytes('/data/a.bin')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]

    def test_read_posix_no_retry(self, monkeypatch):
        """On platforms that allow reading while replacing, the error is not retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_read(file):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_bytes', locked_read)
        with pytest.raises(PermissionError) as e:
            atomic_read_bytes('/data/a.bin')
        assert e.value is error
        assert len(calls) == 1


class TestAtomicReadTextStream:
    """Test cases for atomic_read_text_stream()."""

    def test_read_chunks(self, fs):
        """The chunks of the underlying stream should be yielded."""
        fs.create_file('/data/a.txt', contents='abcdef')
        assert list(atomic_read_text_stream('/data/a.txt', chunk_size=4)) == ['abcd', 'ef']

    def test_read_posix(self, fs, monkeypatch):
        """On the other platforms the chunks are yielded right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        fs.create_file('/data/a.txt', contents='abcdef')
        assert list(atomic_read_text_stream('/data/a.txt', chunk_size=4)) == ['abcd', 'ef']

    def test_read_retries_on_windows(self, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def flaky_stream(file, encoding=None, errors=None, chunk_size=None):
            calls.append(file)
            if len(calls) < 2:
                raise error
            yield 'ab'
            yield 'cd'

        monkeypatch.setattr(atomic, 'file_read_text_stream', flaky_stream)
        assert list(atomic_read_text_stream('/data/a.txt')) == ['ab', 'cd']
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_read_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_stream(file, encoding=None, errors=None, chunk_size=None):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_text_stream', locked_stream)
        with pytest.raises(PermissionError) as e:
            list(atomic_read_text_stream('/data/a.txt'))
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]


class TestAtomicReadBytesStream:
    """Test cases for atomic_read_bytes_stream()."""

    def test_read_chunks(self, fs):
        """The chunks of the underlying stream should be yielded."""
        fs.create_file('/data/a.bin', contents=b'abcdef')
        assert list(atomic_read_bytes_stream('/data/a.bin', chunk_size=4)) == [b'abcd', b'ef']

    def test_read_posix(self, fs, monkeypatch):
        """On the other platforms the chunks are yielded right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        fs.create_file('/data/a.bin', contents=b'abcdef')
        assert list(atomic_read_bytes_stream('/data/a.bin', chunk_size=4)) == [b'abcd', b'ef']

    def test_read_retries_on_windows(self, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def flaky_stream(file, chunk_size=None):
            calls.append(file)
            if len(calls) < 2:
                raise error
            yield b'ab'
            yield b'cd'

        monkeypatch.setattr(atomic, 'file_read_bytes_stream', flaky_stream)
        assert list(atomic_read_bytes_stream('/data/a.bin')) == [b'ab', b'cd']
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_read_posix_no_retry(self, monkeypatch):
        """On platforms that allow reading while replacing, the error is not retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_stream(file, chunk_size=None):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_bytes_stream', locked_stream)
        with pytest.raises(PermissionError) as e:
            list(atomic_read_bytes_stream('/data/a.bin'))
        assert e.value is error
        assert len(calls) == 1

    def test_read_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_stream(file, chunk_size=None):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_bytes_stream', locked_stream)
        with pytest.raises(PermissionError) as e:
            list(atomic_read_bytes_stream('/data/a.bin'))
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]


class TestAtomicReadBytesInto:
    """Test cases for atomic_read_bytes_into()."""

    def test_read_into(self, fs):
        """The buffer should be filled like file_read_bytes_into() does."""
        fs.create_file('/data/a.bin', contents=b'hello')
        buffer = memoryview(bytearray(4))
        assert list(atomic_read_bytes_into('/data/a.bin', buffer)) == [4, 1]
        assert bytes(buffer[:1]) == b'o'

    def test_read_into_posix(self, fs, monkeypatch):
        """On the other platforms the buffer is filled right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        fs.create_file('/data/a.bin', contents=b'hello')
        buffer = memoryview(bytearray(4))
        assert list(atomic_read_bytes_into('/data/a.bin', buffer)) == [4, 1]
        assert bytes(buffer[:1]) == b'o'

    def test_read_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')
        original = atomic.file_read_bytes_into

        def flaky_read(file, buffer):
            calls.append(file)
            if len(calls) < 2:
                raise error
            yield from original(file, buffer)

        monkeypatch.setattr(atomic, 'file_read_bytes_into', flaky_read)
        fs.create_file('/data/a.bin', contents=b'data')
        buffer = memoryview(bytearray(4))
        assert list(atomic_read_bytes_into('/data/a.bin', buffer)) == [4]
        assert bytes(buffer) == b'data'
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_read_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        calls = []
        error = PermissionError(13, 'Permission denied')

        def locked_read(file, buffer):
            calls.append(file)
            raise error

        monkeypatch.setattr(atomic, 'file_read_bytes_into', locked_read)
        with pytest.raises(PermissionError) as e:
            list(atomic_read_bytes_into('/data/a.bin', memoryview(bytearray(4))))
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]


class TestAtomicOpen:
    """Test cases for atomic_open()."""

    def test_open_read(self, fs):
        """The returned file object should be readable."""
        fs.create_file('/data/a.bin', contents=b'data')
        with atomic_open('/data/a.bin', 'rb') as f:
            assert f.read() == b'data'
            assert os.fstat(f.fileno()).st_size == 4

    def test_open_append(self, fs):
        """The append mode should write at the end of the file."""
        fs.create_file('/data/a.txt', contents='old')
        with atomic_open('/data/a.txt', 'a', encoding='utf-8') as f:
            f.write('new')
        assert file_read_text('/data/a.txt') == 'oldnew'

    def test_open_kwargs_forwarded(self, fs, monkeypatch):
        """Extra keyword arguments should be forwarded to open()."""
        fs.create_file('/data/a.txt', contents=b'data')
        calls = break_function(monkeypatch, atomic, 'open', [])
        with atomic_open('/data/a.txt', 'rb', buffering=0) as f:
            assert f.read() == b'data'
        assert calls[0][0] == ('/data/a.txt',)
        assert calls[0][1] == {'mode': 'rb', 'encoding': None, 'buffering': 0}

    def test_open_missing(self, fs):
        """A missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            atomic_open('/missing.txt')

    def test_open_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        fs.create_file('/data/a.txt', contents='data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, atomic, 'open', [error])
        with atomic_open('/data/a.txt', 'r', encoding='utf-8') as f:
            assert f.read() == 'data'
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]

    def test_open_gives_up_on_windows(self, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, atomic, 'open', [error] * WINDOWS_MAX_ATTEMPT)
        with pytest.raises(PermissionError) as e:
            atomic_open('/data/a.txt')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]

    def test_open_posix_no_retry(self, monkeypatch):
        """On platforms that allow reading while replacing, the error is not retried."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, atomic, 'open', [error])
        with pytest.raises(PermissionError) as e:
            atomic_open('/data/a.txt')
        assert e.value is error
        assert len(calls) == 1
