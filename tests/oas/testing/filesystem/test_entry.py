"""
Tests for alasio/testing/filesystem/entry.py.

The mocks of os.DirEntry and the iterator returned by os.scandir().
"""
import os
import stat as statmod

import pytest
from conftest import join

from oas.testing.filesystem import FakeDirEntry, FakeScandirIterator, fs  # noqa: F401


def make_stat(st_mode, size=0):
    """
    Build a stat_result for a fake entry.

    Args:
        st_mode (int): Full mode with the file type bits
        size (int): File size. Defaults to 0.

    Returns:
        os.stat_result:
    """
    return os.stat_result((st_mode, 1, 0, 1, 0, 0, size, 0.0, 0.0, 0.0))


class TestFakeDirEntry:
    """Tests for FakeDirEntry."""

    def test_file_entry(self):
        """A file entry should report is_file() and its stat."""
        st = make_stat(0o100644, size=4)
        entry = FakeDirEntry('a.txt', '/dir/a.txt', False, st)
        assert entry.name == 'a.txt'
        assert entry.path == '/dir/a.txt'
        assert entry.is_file()
        assert not entry.is_dir()
        assert not entry.is_symlink()
        assert entry.is_file(follow_symlinks=False)
        assert not entry.is_dir(follow_symlinks=False)
        assert entry.stat() is st
        assert entry.stat(follow_symlinks=False) is st

    def test_dir_entry(self):
        """A directory entry should report is_dir() and its stat."""
        st = make_stat(0o40755)
        entry = FakeDirEntry('folder', '/dir/folder', True, st)
        assert entry.is_dir()
        assert not entry.is_file()
        assert not entry.is_symlink()
        assert statmod.S_ISDIR(entry.stat().st_mode)

    def test_repr(self):
        """The repr should contain the path."""
        entry = FakeDirEntry('a.txt', '/dir/a.txt', False, make_stat(0o100644))
        assert '/dir/a.txt' in repr(entry)


class TestFakeDirEntrySymlink:
    """Tests for FakeDirEntry of a symbolic link."""

    def _make_link_entry(self, target_stat=None):
        """
        Build a symlink entry pointing to a regular file.

        Args:
            target_stat (os.stat_result | None): Stat of the link target,
                None for a dangling link

        Returns:
            FakeDirEntry:
        """
        link_stat = make_stat(0o120777, size=8)
        return FakeDirEntry('link', '/dir/link', False, link_stat, is_symlink=True, follow_stat=target_stat)

    def test_is_symlink(self):
        """A symlink entry should report is_symlink()."""
        entry = self._make_link_entry(make_stat(0o100644, size=4))
        assert entry.is_symlink()
        assert not entry.is_dir()
        assert entry.is_file()

    def test_not_follow(self):
        """With follow_symlinks=False the entry should not be a dir or file."""
        entry = self._make_link_entry(make_stat(0o100644, size=4))
        assert not entry.is_dir(follow_symlinks=False)
        assert not entry.is_file(follow_symlinks=False)
        assert statmod.S_ISLNK(entry.stat(follow_symlinks=False).st_mode)

    def test_follow_to_file(self):
        """The followed stat should be the target stat."""
        target_stat = make_stat(0o100644, size=4)
        entry = self._make_link_entry(target_stat)
        assert entry.stat() is target_stat
        assert entry.stat(follow_symlinks=True) is target_stat

    def test_follow_to_dir(self):
        """A link to a directory should report is_dir() when followed."""
        link_stat = make_stat(0o120777, size=4)
        target_stat = make_stat(0o40755)
        entry = FakeDirEntry('link', '/dir/link', False, link_stat, is_symlink=True, follow_stat=target_stat)
        assert entry.is_dir()
        assert not entry.is_file()

    def test_dangling(self):
        """A dangling link should not be a dir or file, stat() raises."""
        entry = self._make_link_entry(None)
        assert entry.is_symlink()
        assert not entry.is_dir()
        assert not entry.is_file()
        with pytest.raises(FileNotFoundError):
            entry.stat()


class TestFakeScandirIterator:
    """Tests for FakeScandirIterator."""

    def test_iteration(self):
        """Iterating should yield the entries in order."""
        st = make_stat(0o100644)
        entries = [FakeDirEntry('a', '/x/a', False, st), FakeDirEntry('b', '/x/b', False, st)]
        iterator = FakeScandirIterator(entries)
        assert list(iterator) == entries

    def test_stop_iteration(self):
        """A finished iterator should raise StopIteration."""
        iterator = FakeScandirIterator([])
        with pytest.raises(StopIteration):
            next(iterator)

    def test_context_manager(self):
        """The context manager should return the iterator."""
        st = make_stat(0o100644)
        entries = [FakeDirEntry('a', '/x/a', False, st)]
        with FakeScandirIterator(entries) as iterator:
            assert list(iterator) == entries

    def test_scandir_entries(self, fs):
        """fs.scandir() should yield FakeDirEntry objects."""
        fs.create_file(join(fs, 'a.txt'), contents='data')
        with fs.scandir(fs.root_dir.path) as entries:
            entry = next(entries)
        assert isinstance(entry, FakeDirEntry)
        assert entry.name == 'a.txt'
        assert entry.is_file()
        assert entry.stat().st_size == 4
