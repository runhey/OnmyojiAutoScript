"""
Tests for alasio/testing/filesystem/file_object.py.

The file object returned by open(), text and binary modes.
"""
import io
import os
import stat as statmod

import pytest
from conftest import join

from oas.testing.filesystem import fs  # noqa: F401


class TestFileObject:
    """The file object returned by open()."""

    def test_read_size(self, fs):
        """read(size) should read at most size bytes / characters."""
        fs.create_file(join(fs, 'a.txt'), contents='hello world')
        with open(join(fs, 'a.txt')) as f:
            assert f.read(5) == 'hello'
            assert f.read(5) == ' worl'
            assert f.read(5) == 'd'
            assert f.read() == ''

    def test_read_negative(self, fs):
        """read(-1) should read to the end."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt'), 'rb') as f:
            assert f.read(-1) == b'hello'

    def test_read_all_from_start_no_copy(self, fs):
        """read() all from the start should return the content as-is."""
        fs.create_file(join(fs, 'a.bin'), contents=b'data')
        with open(join(fs, 'a.bin'), 'rb') as f:
            assert f.read() is fs.get_file(join(fs, 'a.bin')).content

    def test_read_all_from_position_copies(self, fs):
        """read() all from a position should return a sliced copy."""
        fs.create_file(join(fs, 'a.bin'), contents=b'data')
        with open(join(fs, 'a.bin'), 'rb') as f:
            f.seek(1)
            data = f.read()
            assert data == b'ata'
            assert data is not fs.get_file(join(fs, 'a.bin')).content

    def test_read_size_from_start_copies(self, fs):
        """read(size) from the start should still slice the content."""
        fs.create_file(join(fs, 'a.bin'), contents=b'data')
        with open(join(fs, 'a.bin'), 'rb') as f:
            data = f.read(2)
            assert data == b'da'
            assert data is not fs.get_file(join(fs, 'a.bin')).content

    def test_readline(self, fs):
        """readline() should read one line including the ending."""
        fs.create_file(join(fs, 'a.txt'), contents='a\nb\nc')
        with open(join(fs, 'a.txt')) as f:
            assert f.readline() == 'a\n'
            assert f.readline() == 'b\n'
            assert f.readline() == 'c'
            assert f.readline() == ''

    def test_readline_size(self, fs):
        """readline(size) should stop at the size."""
        fs.create_file(join(fs, 'a.txt'), contents='abcdef\n')
        with open(join(fs, 'a.txt')) as f:
            assert f.readline(3) == 'abc'
            assert f.readline() == 'def\n'

    def test_readlines(self, fs):
        """readlines() should read all lines."""
        fs.create_file(join(fs, 'a.txt'), contents='a\nb\n')
        with open(join(fs, 'a.txt')) as f:
            assert f.readlines() == ['a\n', 'b\n']

    def test_readinto(self, fs):
        """readinto() should fill a bytearray."""
        fs.create_file(join(fs, 'a.bin'), contents=b'hello')
        with open(join(fs, 'a.bin'), 'rb') as f:
            buffer = bytearray(3)
            assert f.readinto(buffer) == 3
            assert bytes(buffer) == b'hel'
            assert f.readinto(buffer) == 2
            assert bytes(buffer[:2]) == b'lo'

    def test_readinto_text_raises(self, fs):
        """readinto() in text mode should raise io.UnsupportedOperation."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt')) as f:
            with pytest.raises(io.UnsupportedOperation):
                f.readinto(bytearray(3))

    def test_write_returns_count(self, fs):
        """write() should return the number of characters / bytes."""
        with open(join(fs, 'a.txt'), 'w') as f:
            assert f.write('hello') == 5
        with open(join(fs, 'a.bin'), 'wb') as f:
            assert f.write(b'hello') == 5

    def test_write_overwrites(self, fs):
        """write() at a position should overwrite the content."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt'), 'r+') as f:
            f.seek(1)
            f.write('X')
        assert open(join(fs, 'a.txt')).read() == 'hXllo'

    def test_write_beyond_end_pads(self, fs):
        """write() beyond the end should pad with zeros."""
        with open(join(fs, 'a.bin'), 'wb') as f:
            f.write(b'a')
            f.seek(4)
            f.write(b'b')
        assert open(join(fs, 'a.bin'), 'rb').read() == b'a\x00\x00\x00b'

    def test_write_type_error(self, fs):
        """Writing str to a binary file should raise TypeError."""
        with open(join(fs, 'a.bin'), 'wb') as f:
            with pytest.raises(TypeError):
                f.write('text')

    def test_write_to_readonly(self, fs):
        """Writing a read-only file should raise io.UnsupportedOperation."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt')) as f:
            with pytest.raises(io.UnsupportedOperation):
                f.write('x')

    def test_writelines(self, fs):
        """writelines() should write every line."""
        with open(join(fs, 'a.txt'), 'w') as f:
            f.writelines(['a\n', 'b\n'])
        assert open(join(fs, 'a.txt')).read() == 'a\nb\n'

    def test_seek_tell(self, fs):
        """seek() and tell() should work in binary mode."""
        fs.create_file(join(fs, 'a.bin'), contents=b'hello')
        with open(join(fs, 'a.bin'), 'rb') as f:
            f.seek(2)
            assert f.tell() == 2
            assert f.read() == b'llo'
            f.seek(-2, 2)
            assert f.tell() == 3
            assert f.read() == b'lo'
            f.seek(0, 2)
            assert f.tell() == 5

    def test_seek_text(self, fs):
        """Text mode should only seek from the start."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt')) as f:
            f.seek(2)
            assert f.read() == 'llo'
            f.seek(0)
            assert f.read() == 'hello'
            with pytest.raises(ValueError):
                f.seek(1, 1)

    def test_truncate(self, fs):
        """truncate() should cut the content at the size."""
        fs.create_file(join(fs, 'a.bin'), contents=b'hello')
        with open(join(fs, 'a.bin'), 'r+b') as f:
            f.truncate(2)
        assert open(join(fs, 'a.bin'), 'rb').read() == b'he'

    def test_truncate_current_position(self, fs):
        """truncate() without size should use the current position."""
        fs.create_file(join(fs, 'a.bin'), contents=b'hello')
        with open(join(fs, 'a.bin'), 'r+b') as f:
            f.seek(3)
            f.truncate()
        assert open(join(fs, 'a.bin'), 'rb').read() == b'hel'

    def test_iteration(self, fs):
        """Iterating the file object should yield lines."""
        fs.create_file(join(fs, 'a.txt'), contents='a\nb\n')
        fs.create_file(join(fs, 'a.bin'), contents=b'a\nb\n')
        with open(join(fs, 'a.txt')) as f:
            assert list(f) == ['a\n', 'b\n']
        with open(join(fs, 'a.bin'), 'rb') as f:
            assert list(f) == [b'a\n', b'b\n']

    def test_fileno_fstat(self, fs):
        """fileno() should work with the mocked os.fstat()."""
        fs.create_file(join(fs, 'a.txt'), contents='data')
        with open(join(fs, 'a.txt'), 'rb') as f:
            st = os.fstat(f.fileno())
            assert st.st_size == 4
            assert statmod.S_ISREG(st.st_mode)

    def test_close(self, fs):
        """close() should close the file, operations after raise ValueError."""
        f = open(join(fs, 'a.txt'), 'w')
        f.close()
        assert f.closed
        with pytest.raises(ValueError):
            f.write('x')
        with pytest.raises(ValueError):
            f.read()
        f.close()

    def test_context_manager(self, fs):
        """The context manager should close the file."""
        with open(join(fs, 'a.txt'), 'w') as f:
            assert not f.closed
        assert f.closed

    def test_shared_content(self, fs):
        """Writes through one handle should be visible to another."""
        fs.create_file(join(fs, 'a.txt'), contents='hello')
        with open(join(fs, 'a.txt'), 'a') as writer, open(join(fs, 'a.txt')) as reader:
            writer.write(' world')
            reader.seek(0)
            assert reader.read() == 'hello world'

    def test_replaced_file_keeps_old_content(self, fs):
        """A replaced file should keep its old content for open handles."""
        fs.create_file(join(fs, 'a.txt'), contents='old')
        with open(join(fs, 'a.txt'), 'rb') as f:
            os.replace(join(fs, 'a.txt'), join(fs, 'b.txt'))
            assert f.read() == b'old'
        assert open(join(fs, 'b.txt'), 'rb').read() == b'old'

    def test_repr(self, fs):
        """The repr should look like a real file object."""
        fs.create_file(join(fs, 'a.txt'), contents='x')
        with open(join(fs, 'a.txt')) as f:
            assert 'a.txt' in repr(f)
            assert 'utf-8' in repr(f)


class TestTextMode:
    """Text mode encoding, errors and newline handling."""

    def test_encoding_roundtrip(self, fs):
        """Non utf-8 encodings should round trip."""
        with open(join(fs, 'a.txt'), 'w', encoding='utf-16') as f:
            f.write('你好')
        with open(join(fs, 'a.txt'), 'r', encoding='utf-16') as f:
            assert f.read() == '你好'

    def test_multibyte_read(self, fs):
        """read(n) in text mode should count characters, not bytes."""
        fs.create_file(join(fs, 'a.txt'), contents='你好世界')
        with open(join(fs, 'a.txt')) as f:
            assert f.read(2) == '你好'
            assert f.read() == '世界'

    def test_universal_newlines_read(self, fs):
        """newline=None should translate CRLF and CR to LF on read."""
        fs.create_file(join(fs, 'a.txt'), contents='a\r\nb\rc')
        with open(join(fs, 'a.txt')) as f:
            assert f.read() == 'a\nb\nc'

    def test_newline_empty_keeps(self, fs):
        """newline='' should keep the line endings as-is."""
        fs.create_file(join(fs, 'a.txt'), contents='a\r\nb')
        with open(join(fs, 'a.txt'), newline='') as f:
            assert f.read() == 'a\r\nb'

    def test_newline_write_translation(self, fs):
        """newline=None should translate LF to the platform separator."""
        with open(join(fs, 'a.txt'), 'w', newline='') as f:
            f.write('a\nb')
        # written with newline='' the LF is kept
        assert open(join(fs, 'a.txt'), 'rb').read() == b'a\nb'
        with open(join(fs, 'a.txt'), 'w') as f:
            f.write('a\nb')
        # written with newline=None, reads translate back to LF
        with open(join(fs, 'a.txt')) as f:
            assert f.read() == 'a\nb'

    def test_errors_ignore(self, fs):
        """errors='ignore' should skip undecodable bytes."""
        fs.create_file(join(fs, 'a.txt'), contents=b'a\xffb')
        with open(join(fs, 'a.txt'), errors='ignore') as f:
            assert f.read() == 'ab'

    def test_errors_strict(self, fs):
        """errors='strict' should raise on undecodable bytes."""
        fs.create_file(join(fs, 'a.txt'), contents=b'a\xffb')
        with open(join(fs, 'a.txt')) as f:
            with pytest.raises(UnicodeDecodeError):
                f.read()

    def test_read_write_roundtrip(self, fs):
        """write() then read() through the same handle should round trip."""
        with open(join(fs, 'a.txt'), 'w+') as f:
            f.write('hello\nworld\n')
            f.seek(0)
            assert f.read() == 'hello\nworld\n'
