"""
Tests for alasio/testing/filesystem/base.py.

Path normalization and the FakeFile / FakeDir records (dataclass with slots).
"""
import dataclasses
import os
import stat as statmod

import pytest
from conftest import join
from pathlib import Path

from oas.testing.filesystem import FakeDir, FakeFile, FakeSymlink, fs  # noqa: F401
from oas.testing.filesystem.base import IS_WINDOWS, _normpath


class TestNormpath:
    """Tests for _normpath()."""

    def _cases(self):
        """
        Returns:
            list[tuple[str, str]]: (path, expected) pairs of one platform
        """
        root = 'C:' if IS_WINDOWS else ''
        cwd = f'{root}/work'
        return [
            # absolute paths
            ('/a/b', f'{root}/a/b'),
            ('/a/../b', f'{root}/b'),
            ('/a/./b', f'{root}/a/b'),
            ('//a//b', f'{root}/a/b'),
            ('/a/../..', root),
            ('/data.txt', f'{root}/data.txt'),
            # relative paths
            ('a.txt', f'{cwd}/a.txt'),
            ('a/b/../c', f'{cwd}/a/c'),
            ('a/../../b', f'{root}/b'),
            ('a/../..', root),
            ('./a', f'{cwd}/a'),
            ('', cwd),
        ]

    def test_normpath(self):
        """Paths should normalize to absolute "/" separated paths."""
        for path, expected in self._cases():
            cwd = 'C:/work' if IS_WINDOWS else '/work'
            assert _normpath(path, cwd) == expected, path

    def test_root_cwd(self):
        """Relative paths against the root cwd should work."""
        root = 'C:' if IS_WINDOWS else '/'
        assert _normpath('a/b', root) == f'{root}/a/b'
        assert _normpath('..', root) == root
        assert _normpath('a/../..', root) == root

    @pytest.mark.skipif(not IS_WINDOWS, reason='backslash is a separator on Windows only')
    def test_backslash(self):
        """Windows style backslash paths should be normalized."""
        assert _normpath(r'a\b\c.txt', 'C:/work') == 'C:/work/a/b/c.txt'
        assert _normpath(r'C:\a\b.txt', 'C:/work') == 'C:/a/b.txt'

    @pytest.mark.skipif(not IS_WINDOWS, reason='drive letters are Windows only')
    def test_drive_letters(self):
        """Drive letters should be kept, drive root is "C:"."""
        assert _normpath('C:/a/b', 'C:/work') == 'C:/a/b'
        assert _normpath('C:/', 'C:/work') == 'C:'
        assert _normpath('C:', 'C:/work') == 'C:'
        assert _normpath('C:/a/..', 'C:/work') == 'C:'
        assert _normpath('D:/a', 'C:/work') == 'D:/a'

    @pytest.mark.skipif(IS_WINDOWS, reason='POSIX paths are Windows only')
    def test_posix_root(self):
        """The POSIX root should stay "/"."""
        assert _normpath('/a/b', '/work') == '/a/b'
        assert _normpath('/', '/work') == '/'
        assert _normpath('/a/..', '/work') == '/'

    def test_pathlike_input(self):
        """PathLike inputs should be accepted."""
        cwd = 'C:/work' if IS_WINDOWS else '/work'
        assert _normpath(Path('/a/b'), cwd) == _normpath('/a/b', cwd)


class TestFakeFileRecord:
    """FakeFile and FakeDir records, dataclass records of file information."""

    def test_fake_file_is_dataclass_record(self, fs):
        """create_file() should return a dataclass record."""
        file = fs.create_file(join(fs, 'a.txt'), contents=b'data')
        assert isinstance(file, FakeFile)
        assert dataclasses.is_dataclass(file)
        assert file.path == join(fs, 'a.txt')
        assert file.content == b'data'
        assert file.mode == 0o666

    def test_fake_dir_is_dataclass_record(self, fs):
        """create_dir() should return a dataclass record."""
        folder = fs.create_dir(join(fs, 'folder'))
        assert isinstance(folder, FakeDir)
        assert dataclasses.is_dataclass(folder)
        assert folder.path == join(fs, 'folder')
        assert folder.mode == 0o777

    def test_stat_result(self, fs):
        """stat() should return a real os.stat_result with mode and size."""
        fs.create_file(join(fs, 'a.txt'), contents=b'data', st_mode=0o100755)
        st = fs.stat(join(fs, 'a.txt'))
        assert isinstance(st, os.stat_result)
        assert statmod.S_ISREG(st.st_mode)
        assert not statmod.S_ISDIR(st.st_mode)
        assert st.st_mode & 0o7777 == 0o755
        assert st.st_size == 4

    def test_stat_dir(self, fs):
        """stat() of a directory should have the directory type bit."""
        fs.create_dir(join(fs, 'folder'))
        st = fs.stat(join(fs, 'folder'))
        assert statmod.S_ISDIR(st.st_mode)
        assert not statmod.S_ISREG(st.st_mode)

    def test_stat_missing(self, fs):
        """stat() of a missing path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            fs.stat(join(fs, 'missing.txt'))

    def test_inode_unique(self, fs):
        """Every record should get a unique inode number."""
        a = fs.create_file(join(fs, 'a.txt'))
        b = fs.create_file(join(fs, 'b.txt'))
        c = fs.create_dir(join(fs, 'folder'))
        assert len({a.ino, b.ino, c.ino}) == 3

    def test_timestamps(self, fs):
        """Timestamps should be set at creation."""
        file = fs.create_file(join(fs, 'a.txt'))
        assert file.atime > 0
        assert file.mtime > 0
        assert file.ctime > 0


class TestFakeSymlinkRecord:
    """FakeSymlink record, dataclass record of a symbolic link."""

    def test_fake_symlink_is_dataclass_record(self, fs):
        """create_symlink() should return a dataclass record."""
        link = fs.create_symlink(join(fs, 'link'), join(fs, 'a.txt'))
        assert isinstance(link, FakeSymlink)
        assert dataclasses.is_dataclass(link)
        assert link.path == join(fs, 'link')
        assert link.target == join(fs, 'a.txt')

    def test_stat_result(self, fs):
        """stat() of the link itself should have the S_IFLNK type bit."""
        link = fs.create_symlink(join(fs, 'link'), join(fs, 'a.txt'))
        st = link.stat()
        assert isinstance(st, os.stat_result)
        assert statmod.S_ISLNK(st.st_mode)
        assert not statmod.S_ISREG(st.st_mode)
        assert not statmod.S_ISDIR(st.st_mode)
        # the size is the length of the target string, like the real os
        assert st.st_size == len(join(fs, 'a.txt'))

    def test_inode_unique(self, fs):
        """A symlink should get its own inode number."""
        file = fs.create_file(join(fs, 'a.txt'))
        link = fs.create_symlink(join(fs, 'link'), join(fs, 'a.txt'))
        assert file.ino != link.ino
