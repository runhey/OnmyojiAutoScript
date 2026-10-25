"""
Tests for the remove functions of oas.ext.path.atomic.

Covered: file_remove(), atomic_remove() with the Windows PermissionError
retry, folder_rmtree(), atomic_rmtree(), is_empty_folder(),
folder_rmtree_empty(), atomic_rmtree_empty() and
atomic_failure_cleanup().

The tests run on the in-memory fake filesystem (the fs fixture), the
real disk is never touched.
"""
import os

import pytest

from oas.ext.path import atomic
from oas.ext.path.atomic import (
    WINDOWS_MAX_ATTEMPT, atomic_failure_cleanup, atomic_remove, atomic_rmtree, atomic_rmtree_empty, file_read_text,
    file_remove, folder_rmtree, folder_rmtree_empty, is_empty_folder, windows_attempt_delay
)
from oas.testing.filesystem import fs  # noqa: F401
from tests.oas.ext.path.atomic.helpers import break_function, record_sleeps


class TestFileRemove:
    """Test cases for file_remove()."""

    def test_remove(self, fs):
        """An existing file should be removed."""
        fs.create_file('/data/a.txt', contents='data')
        assert file_remove('/data/a.txt') is True
        assert not os.path.exists('/data/a.txt')

    def test_remove_missing(self, fs):
        """A missing file should report False."""
        assert file_remove('/missing.txt') is False

    def test_remove_folder(self, fs):
        """A folder should not be removed by file_remove()."""
        fs.create_dir('/data/folder')
        with pytest.raises(IsADirectoryError):
            file_remove('/data/folder')
        assert os.path.isdir('/data/folder')

    def test_remove_symlink(self, fs):
        """Only the link should be removed, never the target."""
        fs.create_file('/data/a.txt', contents='data')
        fs.create_symlink('/data/link.txt', '/data/a.txt')
        assert file_remove('/data/link.txt') is True
        assert not os.path.lexists('/data/link.txt')
        assert file_read_text('/data/a.txt') == 'data'

    def test_remove_dangling_symlink(self, fs):
        """A dangling link should be removable."""
        fs.create_symlink('/data/link.txt', '/data/missing.txt')
        assert file_remove('/data/link.txt') is True
        assert not os.path.lexists('/data/link.txt')


class TestAtomicRemove:
    """Test cases for atomic_remove()."""

    def test_remove(self, fs):
        """An existing file should be removed."""
        fs.create_file('/data/a.txt', contents='data')
        assert atomic_remove('/data/a.txt') is True
        assert not os.path.exists('/data/a.txt')

    def test_remove_missing(self, fs):
        """A missing file should report False."""
        assert atomic_remove('/missing.txt') is False

    def test_remove_retries_on_windows(self, fs, monkeypatch):
        """PermissionError should be retried on Windows until it works."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        fs.create_file('/data/a.txt', contents='data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'unlink', [error])
        assert atomic_remove('/data/a.txt') is True
        assert len(calls) == 2
        assert sleeps.sleeps == [windows_attempt_delay(0)]
        assert not os.path.exists('/data/a.txt')

    def test_remove_gives_up_on_windows(self, fs, monkeypatch):
        """The last PermissionError should be raised when every attempt failed."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', True)
        sleeps = record_sleeps(monkeypatch)
        fs.create_file('/data/a.txt', contents='data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'unlink', [error] * WINDOWS_MAX_ATTEMPT)
        with pytest.raises(PermissionError) as e:
            atomic_remove('/data/a.txt')
        assert e.value is error
        assert len(calls) == WINDOWS_MAX_ATTEMPT
        assert sleeps.sleeps == [windows_attempt_delay(attempt) for attempt in range(WINDOWS_MAX_ATTEMPT)]
        assert os.path.exists('/data/a.txt')

    def test_remove_posix_no_retry(self, fs, monkeypatch):
        """On the other platforms the error is raised right away."""
        monkeypatch.setattr(atomic, 'IS_WINDOWS', False)
        fs.create_file('/data/a.txt', contents='data')
        error = PermissionError(13, 'Permission denied')
        calls = break_function(monkeypatch, os, 'unlink', [error])
        with pytest.raises(PermissionError) as e:
            atomic_remove('/data/a.txt')
        assert e.value is error
        assert len(calls) == 1
        assert os.path.exists('/data/a.txt')


class TestFolderRmtree:
    """Test cases for folder_rmtree()."""

    def test_rmtree(self, fs):
        """The folder and all its content should be removed."""
        fs.create_file('/data/folder/a.txt', contents='x')
        fs.create_file('/data/folder/sub/b.txt', contents='y')
        assert folder_rmtree('/data/folder') is True
        assert not os.path.exists('/data/folder')
        assert os.path.isdir('/data')

    def test_rmtree_missing(self, fs):
        """A missing folder should report False."""
        assert folder_rmtree('/missing') is False

    def test_rmtree_file(self, fs):
        """A path that is a file should be removed like file_remove() does."""
        fs.create_file('/data/a.txt', contents='x')
        assert folder_rmtree('/data/a.txt') is True
        assert not os.path.exists('/data/a.txt')

    def test_rmtree_symlink(self, fs):
        """A symlink should be unlinked, the folder it points to is kept."""
        fs.create_file('/data/real/a.txt', contents='x')
        fs.create_symlink('/data/link', '/data/real')
        assert folder_rmtree('/data/link') is True
        assert not os.path.lexists('/data/link')
        assert file_read_text('/data/real/a.txt') == 'x'

    def test_rmtree_nested_symlink(self, fs):
        """A symlink inside the folder should be unlinked, the target is kept."""
        fs.create_file('/data/outside/a.txt', contents='x')
        fs.create_file('/data/folder/a.txt', contents='x')
        fs.create_symlink('/data/folder/link', '/data/outside')
        assert folder_rmtree('/data/folder') is True
        assert not os.path.exists('/data/folder')
        assert file_read_text('/data/outside/a.txt') == 'x'

    def test_rmtree_locked_file(self, fs, monkeypatch):
        """A file that can not be removed should be skipped, the folder is kept."""
        fs.create_file('/data/folder/locked.txt', contents='x')
        fs.create_file('/data/folder/free.txt', contents='x')
        original = os.unlink

        def locked_unlink(path):
            # the paths of scandir entries are normalized by the filesystem
            if os.path.basename(path) == 'locked.txt':
                raise PermissionError(13, 'Permission denied', path)
            return original(path)

        monkeypatch.setattr(os, 'unlink', locked_unlink)
        assert folder_rmtree('/data/folder') is False
        assert file_read_text('/data/folder/locked.txt') == 'x'
        assert not os.path.exists('/data/folder/free.txt')

    def test_rmtree_without_symlink(self, fs):
        """may_symlinks=False should work for a folder that is not a symlink."""
        fs.create_file('/data/folder/a.txt', contents='x')
        assert folder_rmtree('/data/folder', may_symlinks=False) is True
        assert not os.path.exists('/data/folder')

    def test_rmtree_rmdir_missing(self, fs, monkeypatch):
        """A folder removed while it was iterated should report False."""
        fs.create_dir('/data/folder')

        def racing_rmdir(path):
            # simulate another process removing the folder after the scan
            fs.remove(path)
            raise FileNotFoundError(2, 'No such file or directory', path)

        monkeypatch.setattr(os, 'rmdir', racing_rmdir)
        assert folder_rmtree('/data/folder') is False

    def test_rmtree_rmdir_not_a_directory(self, fs, monkeypatch):
        """A folder replaced by a file while it was iterated should be removed like file_remove()."""
        fs.create_dir('/data/folder')

        def racing_rmdir(path):
            # simulate another process replacing the folder after the scan
            fs.remove(path)
            fs.create_file(path, contents='x')
            raise NotADirectoryError(20, 'Not a directory', path)

        monkeypatch.setattr(os, 'rmdir', racing_rmdir)
        assert folder_rmtree('/data/folder') is True
        assert not os.path.exists('/data/folder')


class TestAtomicRmtree:
    """Test cases for atomic_rmtree()."""

    def test_rmtree(self, fs):
        """The folder and all its content should be removed, no tmp folder left."""
        fs.create_file('/data/folder/a.txt', contents='x')
        fs.create_file('/data/folder/sub/b.txt', contents='y')
        assert atomic_rmtree('/data/folder') is True
        assert not os.path.exists('/data/folder')
        assert os.listdir('/data') == []

    def test_rmtree_missing(self, fs):
        """A missing folder should report False."""
        assert atomic_rmtree('/missing') is False

    def test_rmtree_file(self, fs):
        """A path that is a file should be removed."""
        fs.create_file('/data/a.txt', contents='x')
        assert atomic_rmtree('/data/a.txt') is True
        assert not os.path.exists('/data/a.txt')


class TestIsEmptyFolder:
    """Test cases for is_empty_folder()."""

    def test_empty(self, fs):
        """An empty folder should report True."""
        fs.create_dir('/data/folder')
        assert is_empty_folder('/data/folder') is True

    def test_with_file(self, fs):
        """A folder holding a file should report False."""
        fs.create_file('/data/folder/a.txt', contents='x')
        assert is_empty_folder('/data/folder') is False

    def test_with_folder(self, fs):
        """A folder holding a folder should report False."""
        fs.create_dir('/data/folder/sub')
        assert is_empty_folder('/data/folder') is False

    def test_missing(self, fs):
        """A missing folder should report False."""
        assert is_empty_folder('/missing') is False

    def test_file(self, fs):
        """A path that is a file should report False."""
        fs.create_file('/data/a.txt', contents='x')
        assert is_empty_folder('/data/a.txt') is False

    def test_ignore_pycache(self, fs):
        """A folder holding only __pycache__ should report True with ignore_pycache."""
        fs.create_dir('/data/folder/__pycache__')
        assert is_empty_folder('/data/folder', ignore_pycache=True) is True
        assert is_empty_folder('/data/folder') is False

    def test_ignore_pycache_other_entry(self, fs):
        """A folder holding __pycache__ and anything else should report False."""
        fs.create_dir('/data/folder/__pycache__')
        fs.create_file('/data/folder/a.py', contents='x')
        assert is_empty_folder('/data/folder', ignore_pycache=True) is False


class TestFolderRmtreeEmpty:
    """Test cases for folder_rmtree_empty()."""

    def test_rmtree_empty(self, fs):
        """An empty folder should be removed."""
        fs.create_dir('/data/folder')
        assert folder_rmtree_empty('/data/folder') is True
        assert not os.path.exists('/data/folder')

    def test_rmtree_empty_not_empty(self, fs):
        """A non-empty folder should be kept as-is."""
        fs.create_file('/data/folder/a.txt', contents='x')
        assert folder_rmtree_empty('/data/folder') is False
        assert file_read_text('/data/folder/a.txt') == 'x'

    def test_rmtree_empty_missing(self, fs):
        """A missing folder should report False."""
        assert folder_rmtree_empty('/missing') is False

    def test_rmtree_empty_file(self, fs):
        """A path that is a file should be kept as-is."""
        fs.create_file('/data/a.txt', contents='x')
        assert folder_rmtree_empty('/data/a.txt') is False
        assert file_read_text('/data/a.txt') == 'x'


class TestAtomicRmtreeEmpty:
    """Test cases for atomic_rmtree_empty()."""

    def test_rmtree_empty(self, fs):
        """An empty folder should be removed, no tmp folder left behind."""
        fs.create_dir('/data/folder')
        assert atomic_rmtree_empty('/data/folder') is True
        assert os.listdir('/data') == []

    def test_rmtree_empty_missing(self, fs):
        """A missing folder should report False."""
        assert atomic_rmtree_empty('/missing') is False

    def test_rmtree_empty_not_empty(self, fs):
        """A non-empty folder should be kept as-is."""
        fs.create_file('/data/folder/a.txt', contents='x')
        assert atomic_rmtree_empty('/data/folder') is False
        assert file_read_text('/data/folder/a.txt') == 'x'

    def test_rmtree_empty_file(self, fs):
        """A path that is a file should be kept as-is."""
        fs.create_file('/data/a.txt', contents='x')
        assert atomic_rmtree_empty('/data/a.txt') is False
        assert file_read_text('/data/a.txt') == 'x'

    def test_rmtree_empty_race(self, fs, monkeypatch):
        """A folder removed by another process after the empty check should report False."""
        fs.create_dir('/data/folder')
        error = FileNotFoundError(2, 'No such file or directory')
        break_function(monkeypatch, os, 'replace', [error])
        assert atomic_rmtree_empty('/data/folder') is False


class TestAtomicFailureCleanup:
    """Test cases for atomic_failure_cleanup()."""

    def test_cleanup(self, fs):
        """Tmp files and tmp folders should be removed, the other entries kept."""
        fs.create_file('/data/keep.txt', contents='keep')
        fs.create_file('/data/a.txt.ABC123.tmp', contents='junk')
        fs.create_file('/data/folder.ABC123.tmp/b.txt', contents='junk')
        atomic_failure_cleanup('/data')
        assert os.listdir('/data') == ['keep.txt']

    def test_cleanup_not_recursive(self, fs):
        """Tmp files in the subfolders should be kept by default."""
        fs.create_file('/data/sub/a.txt.ABC123.tmp', contents='junk')
        atomic_failure_cleanup('/data')
        assert os.path.exists('/data/sub/a.txt.ABC123.tmp')

    def test_cleanup_recursive(self, fs):
        """Tmp files in the subfolders should be removed with recursive=True."""
        fs.create_file('/data/sub/a.txt.ABC123.tmp', contents='junk')
        fs.create_file('/data/sub/keep.txt', contents='keep')
        atomic_failure_cleanup('/data', recursive=True)
        assert os.listdir('/data/sub') == ['keep.txt']

    def test_cleanup_missing(self, fs):
        """A missing folder should not raise."""
        atomic_failure_cleanup('/missing')

    def test_cleanup_file(self, fs):
        """A path that is a file should be removed like file_remove() does."""
        fs.create_file('/data.zip', contents='data')
        atomic_failure_cleanup('/data.zip')
        assert not os.path.exists('/data.zip')

    def test_cleanup_locked(self, fs, monkeypatch):
        """A tmp file that can not be removed should be skipped."""
        fs.create_file('/data/locked.txt.ABC123.tmp', contents='junk')
        fs.create_file('/data/a.txt.ABC123.tmp', contents='junk')
        original = os.unlink

        def locked_unlink(path):
            # the paths of scandir entries are normalized by the filesystem
            if os.path.basename(path) == 'locked.txt.ABC123.tmp':
                raise PermissionError(13, 'Permission denied', path)
            return original(path)

        monkeypatch.setattr(os, 'unlink', locked_unlink)
        atomic_failure_cleanup('/data')
        assert os.listdir('/data') == ['locked.txt.ABC123.tmp']

    def test_cleanup_recursive_locked(self, fs, monkeypatch):
        """A subfolder that can not be scanned should not abort the cleanup."""
        fs.create_file('/data/a/keep.txt', contents='keep')
        fs.create_file('/data/b/keep.txt', contents='keep')
        fs.create_file('/data/c/a.txt.ABC123.tmp', contents='junk')
        fs.create_file('/data/a.txt.ABC123.tmp', contents='junk')
        original = os.scandir

        def broken_scandir(path):
            # the paths of scandir entries are normalized by the filesystem
            name = os.path.basename(path)
            if name == 'a':
                raise PermissionError(13, 'Permission denied', path)
            if name == 'b':
                raise OSError(5, 'I/O error', path)
            return original(path)

        monkeypatch.setattr(os, 'scandir', broken_scandir)
        atomic_failure_cleanup('/data', recursive=True)
        assert os.listdir('/data') == ['a', 'b', 'c']
        assert os.listdir('/data/a') == ['keep.txt']
        assert os.listdir('/data/b') == ['keep.txt']
        assert os.listdir('/data/c') == []

    def test_cleanup_error(self, fs, monkeypatch):
        """A tmp file that fails to be removed should be skipped."""
        fs.create_file('/data/a.txt.ABC123.tmp', contents='junk')
        fs.create_file('/data/b.txt.ABC123.tmp', contents='junk')
        original = os.unlink

        def broken_unlink(path):
            # the paths of scandir entries are normalized by the filesystem
            if os.path.basename(path) == 'a.txt.ABC123.tmp':
                raise OSError('Other error')
            return original(path)

        monkeypatch.setattr(os, 'unlink', broken_unlink)
        atomic_failure_cleanup('/data')
        assert os.listdir('/data') == ['a.txt.ABC123.tmp']

    def test_cleanup_recursive_errors(self, fs, monkeypatch):
        """A subfolder that fails to be cleaned should not abort the cleanup."""
        fs.create_file('/data/a/keep.txt', contents='keep')
        fs.create_file('/data/b/keep.txt', contents='keep')
        fs.create_file('/data/c/a.txt.ABC123.tmp', contents='junk')
        original = atomic.atomic_failure_cleanup

        def broken_cleanup(folder, recursive=False):
            name = os.path.basename(folder)
            if name == 'a':
                raise PermissionError(13, 'Permission denied', folder)
            if name == 'b':
                raise OSError('Other error')
            return original(folder, recursive=recursive)

        monkeypatch.setattr(atomic, 'atomic_failure_cleanup', broken_cleanup)
        original('/data', recursive=True)
        assert os.listdir('/data/c') == []
