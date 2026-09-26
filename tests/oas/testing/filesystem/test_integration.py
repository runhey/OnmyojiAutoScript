"""
Integration tests: the alasio/ext/path stack on the fake filesystem.

These tests verify that PathStr, the atomic read/write functions,
batch_makedirs and folder iteration work against the in-memory fake
filesystem without changes.
"""
import os

import pytest
from conftest import join

pytest.importorskip('oas.ext.path')

from oas.ext.path import PathStr
from oas.ext.path.atomic import (
    atomic_copy, atomic_open, atomic_read_bytes, atomic_read_bytes_into, atomic_read_bytes_stream, atomic_read_text,
    atomic_read_text_stream, atomic_remove, atomic_rename, atomic_replace, atomic_rmtree, atomic_rmtree_empty,
    atomic_write, atomic_write_stream, file_copy, file_ensure_exist, file_read_bytes, file_read_bytes_into,
    file_read_bytes_stream, file_read_text, file_read_text_stream, file_remove, file_touch, file_write,
    file_write_stream, folder_rmtree, is_empty_folder
)
from oas.ext.path.makedir import batch_makedirs
from oas.testing.filesystem import fs  # noqa: F401


class TestAtomicPath:
    """The alasio/ext/path atomic functions against the fake filesystem."""

    def test_file_write_read(self, fs):
        """file_write() and file_read_*() should round trip."""
        path = join(fs, 'a', 'b.txt')
        file_write(path, 'hello')
        assert file_read_text(path) == 'hello'
        assert file_read_bytes(path) == b'hello'

    def test_file_write_bytes(self, fs):
        """file_write() should auto detect bytes mode."""
        path = join(fs, 'a.bin')
        file_write(path, b'\x00\x01')
        assert file_read_bytes(path) == b'\x00\x01'

    def test_file_write_stream(self, fs):
        """file_write_stream() should write chunks."""
        path = join(fs, 'a.txt')
        file_write_stream(path, iter(['a\n', 'b\n']))
        assert file_read_text(path) == 'a\nb\n'

    def test_file_write_stream_empty(self, fs):
        """file_write_stream() of an empty generator should create nothing."""
        path = join(fs, 'a.txt')
        file_write_stream(path, iter([]))
        assert not os.path.exists(path)

    def test_file_read_streams(self, fs):
        """The stream readers should yield chunks."""
        path = join(fs, 'a.txt')
        file_write(path, 'hello world')
        assert ''.join(file_read_text_stream(path, chunk_size=3)) == 'hello world'
        assert b''.join(file_read_bytes_stream(path, chunk_size=3)) == b'hello world'

    def test_file_read_into(self, fs):
        """file_read_bytes_into() should fill a buffer."""
        path = join(fs, 'a.bin')
        file_write(path, b'hello')
        buffer = memoryview(bytearray(3))
        chunks = list(file_read_bytes_into(path, buffer))
        assert chunks == [3, 2]
        assert buffer[:2].tolist() == list(b'lo')

    def test_atomic_write(self, fs):
        """atomic_write() should leave no tmp file behind."""
        path = join(fs, 'dir', 'a.txt')
        atomic_write(path, 'data')
        assert file_read_text(path) == 'data'
        # no tmp files left behind
        assert os.listdir(join(fs, 'dir')) == ['a.txt']

    def test_atomic_write_stream(self, fs):
        """atomic_write_stream() should write the chunks atomically."""
        path = join(fs, 'a.txt')
        atomic_write_stream(path, iter(['a', 'b']))
        assert file_read_text(path) == 'ab'

    def test_atomic_read(self, fs):
        """atomic_read_text() and atomic_read_bytes() should read."""
        path = join(fs, 'a.txt')
        atomic_write(path, 'data')
        assert atomic_read_text(path) == 'data'
        assert atomic_read_bytes(path) == b'data'

    def test_atomic_read_streams(self, fs):
        """atomic_read_text_stream() / atomic_read_bytes_stream() should work."""
        path = join(fs, 'a.txt')
        atomic_write(path, 'data')
        assert ''.join(atomic_read_text_stream(path)) == 'data'
        assert b''.join(atomic_read_bytes_stream(path)) == b'data'

    def test_atomic_read_into(self, fs):
        """atomic_read_bytes_into() should fill a buffer."""
        path = join(fs, 'a.bin')
        atomic_write(path, b'data')
        buffer = memoryview(bytearray(4))
        assert list(atomic_read_bytes_into(path, buffer)) == [4]

    def test_atomic_replace(self, fs):
        """atomic_replace() should replace a file."""
        tmp = join(fs, 'tmp.txt')
        target = join(fs, 'target.txt')
        file_write(tmp, 'data')
        atomic_replace(tmp, target)
        assert file_read_text(target) == 'data'
        assert not os.path.exists(tmp)

    def test_atomic_rename(self, fs):
        """atomic_rename() should rename a file."""
        src = join(fs, 'a.txt')
        dst = join(fs, 'b.txt')
        file_write(src, 'data')
        atomic_rename(src, dst)
        assert file_read_text(dst) == 'data'
        assert not os.path.exists(src)

    def test_file_remove(self, fs):
        """file_remove() should remove a file and report the result."""
        path = join(fs, 'a.txt')
        file_write(path, 'x')
        assert file_remove(path)
        assert not file_remove(path)

    def test_atomic_remove(self, fs):
        """atomic_remove() should remove a file."""
        path = join(fs, 'a.txt')
        file_write(path, 'x')
        assert atomic_remove(path)
        assert not os.path.exists(path)

    def test_folder_rmtree(self, fs):
        """folder_rmtree() should remove a folder recursively."""
        folder = join(fs, 'folder')
        file_write(join(fs, 'folder', 'a', 'b.txt'), 'x')
        assert folder_rmtree(folder)
        assert not os.path.exists(folder)

    def test_folder_rmtree_missing(self, fs):
        """folder_rmtree() of a missing folder should return False."""
        assert not folder_rmtree(join(fs, 'missing'))

    def test_folder_rmtree_file(self, fs):
        """folder_rmtree() of a file should remove the file."""
        path = join(fs, 'a.txt')
        file_write(path, 'x')
        assert folder_rmtree(path)
        assert not os.path.exists(path)

    def test_atomic_rmtree(self, fs):
        """atomic_rmtree() should rename and remove the folder."""
        folder = join(fs, 'folder')
        file_write(join(fs, 'folder', 'a.txt'), 'x')
        assert atomic_rmtree(folder)
        assert not os.path.exists(folder)

    def test_atomic_rmtree_missing(self, fs):
        """atomic_rmtree() of a missing folder should return False."""
        assert not atomic_rmtree(join(fs, 'missing'))

    def test_atomic_rmtree_empty(self, fs):
        """atomic_rmtree_empty() should remove an empty folder."""
        folder = join(fs, 'folder')
        os.mkdir(folder)
        assert atomic_rmtree_empty(folder)
        assert not os.path.exists(folder)

    def test_is_empty_folder(self, fs):
        """is_empty_folder() should report the folder content."""
        folder = join(fs, 'folder')
        os.mkdir(folder)
        assert is_empty_folder(folder)
        file_write(join(fs, 'folder', 'a.txt'), 'x')
        assert not is_empty_folder(folder)
        assert not is_empty_folder(join(fs, 'missing'))

    def test_is_empty_folder_ignore_pycache(self, fs):
        """is_empty_folder(ignore_pycache=True) should ignore __pycache__."""
        folder = join(fs, 'folder')
        os.mkdir(folder)
        os.mkdir(join(fs, 'folder', '__pycache__'))
        assert is_empty_folder(folder, ignore_pycache=True)
        assert not is_empty_folder(folder)

    def test_file_ensure_exist(self, fs):
        """file_ensure_exist() should create the file once."""
        path = join(fs, 'a.txt')
        assert file_ensure_exist(path)
        assert file_ensure_exist(path) is False
        assert os.path.exists(path)

    def test_file_ensure_exist_default(self, fs):
        """file_ensure_exist() should write the default content."""
        path = join(fs, 'a.txt')
        file_ensure_exist(path, default=b'data')
        assert file_read_bytes(path) == b'data'

    def test_file_touch(self, fs):
        """file_touch() should create a missing file."""
        path = join(fs, 'a.txt')
        file_touch(path)
        assert os.path.exists(path)
        assert os.path.getsize(path) == 0

    def test_atomic_open(self, fs):
        """atomic_open() should return a working file object."""
        path = join(fs, 'a.txt')
        file_write(path, 'data')
        with atomic_open(path, 'rb') as f:
            assert f.read() == b'data'
            assert os.fstat(f.fileno()).st_size == 4

    def test_atomic_open_append(self, fs):
        """atomic_open() in append mode should write at the end."""
        path = join(fs, 'a.txt')
        file_write(path, 'old')
        with atomic_open(path, 'a', encoding='utf-8') as f:
            f.write('new')
        assert file_read_text(path) == 'oldnew'

    def test_atomic_failure_cleanup(self, fs):
        """atomic_failure_cleanup() should remove leftover tmp files."""
        root = PathStr.new(fs.root_dir.path)
        file_write(join(fs, 'junk.abc123.tmp'), 'junk')
        file_write(join(fs, 'keep.txt'), 'keep')
        root.atomic_failure_cleanup()
        assert not os.path.exists(join(fs, 'junk.abc123.tmp'))
        assert os.path.exists(join(fs, 'keep.txt'))

    def test_file_copy(self, fs):
        """file_copy() should copy the content."""
        src = join(fs, 'a.bin')
        dst = join(fs, 'b.bin')
        file_write(src, b'data')
        file_copy(src, dst)
        assert file_read_bytes(dst) == b'data'

    def test_atomic_copy(self, fs):
        """atomic_copy() should copy with a tmp file."""
        src = join(fs, 'dir', 'a.bin')
        dst = join(fs, 'dir', 'b.bin')
        file_write(src, b'data')
        atomic_copy(src, dst)
        assert file_read_bytes(dst) == b'data'
        assert os.listdir(join(fs, 'dir')) == ['a.bin', 'b.bin']


class TestPathStr:
    """The PathStr methods against the fake filesystem."""

    def test_root_dir_path(self, fs):
        """fs.root_dir.path should be a valid PathStr base."""
        root = PathStr.new(fs.root_dir.path)
        assert root.isdir()
        assert root.exists()

    def test_file_write_atomic_read(self, fs):
        """PathStr.file_write() and atomic_read_text() should work."""
        root = PathStr.new(fs.root_dir.path)
        path = root.joinpath('a')
        path.file_write('hello')
        assert path.atomic_read_text() == 'hello'
        assert path.atomic_read_bytes() == b'hello'

    def test_atomic_write(self, fs):
        """PathStr.atomic_write() should work."""
        path = PathStr.new(fs.root_dir.path).joinpath('a.txt')
        path.atomic_write('data')
        assert path.atomic_read_text() == 'data'

    def test_iter_files(self, fs):
        """PathStr.iter_files() should iterate the files."""
        root = PathStr.new(fs.root_dir.path)
        file_write(root.joinpath('a.txt'), 'x')
        file_write(root.joinpath('b/c.txt'), 'x')
        assert sorted(str(p) for p in root.iter_files(recursive=True)) == [
            root.joinpath('a.txt'), root.joinpath('b/c.txt'),
        ]
        assert [p for p in root.iter_files(ext='.txt')] == [root.joinpath('a.txt')]

    def test_iter_folders(self, fs):
        """PathStr.iter_folders() should iterate the directories."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('folder')
        file_write(folder.joinpath('a/b/c.txt'), 'x')
        folders = sorted(str(p) for p in folder.iter_folders(recursive=True))
        assert folders == [folder.joinpath('a'), folder.joinpath('a/b')]

    def test_iter_filenames(self, fs):
        """PathStr.iter_filenames() should yield the file names."""
        root = PathStr.new(fs.root_dir.path)
        file_write(root.joinpath('a.txt'), 'x')
        file_write(root.joinpath('b.txt'), 'x')
        assert sorted(root.iter_filenames()) == ['a.txt', 'b.txt']

    def test_exists_isfile_isdir(self, fs):
        """PathStr.exists() / isfile() / isdir() should work."""
        root = PathStr.new(fs.root_dir.path)
        file = root.joinpath('a.txt')
        file.file_write('x')
        assert file.exists()
        assert file.isfile()
        assert not file.isdir()
        assert root.isdir()
        assert not root.isfile()

    def test_stat(self, fs):
        """PathStr.stat() should return the record stat."""
        root = PathStr.new(fs.root_dir.path)
        file = root.joinpath('a.txt')
        file.file_write('data')
        assert file.stat().st_size == 4

    def test_makedirs(self, fs):
        """PathStr.makedirs() should create the directories."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('a')
        folder.makedirs(exist_ok=True)
        assert folder.isdir()

    def test_touch_ensure_exist(self, fs):
        """PathStr.touch() and ensure_exist() should work."""
        root = PathStr.new(fs.root_dir.path)
        file = root.joinpath('a.txt')
        file.touch()
        assert file.exists()
        assert file.ensure_exist() is False

    def test_folder_rmtree(self, fs):
        """PathStr.folder_rmtree() and atomic_rmtree() should work."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('folder')
        folder.joinpath('a.txt').file_write('x')
        assert folder.folder_rmtree()
        assert not folder.exists()
        folder2 = root.joinpath('folder2')
        folder2.joinpath('a.txt').file_write('x')
        assert folder2.atomic_rmtree()
        assert not folder2.exists()

    def test_is_empty_folder(self, fs):
        """PathStr.is_empty_folder() should work."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('folder')
        folder.makedirs(exist_ok=True)
        assert folder.is_empty_folder()

    def test_atomic_replace(self, fs):
        """PathStr.atomic_replace() should replace a file."""
        root = PathStr.new(fs.root_dir.path)
        tmp = root.joinpath('tmp.txt')
        target = root.joinpath('target.txt')
        tmp.file_write('data')
        tmp.atomic_replace(target)
        assert target.atomic_read_text() == 'data'
        assert not tmp.exists()

    def test_atomic_rename(self, fs):
        """PathStr.atomic_rename() should rename a file."""
        root = PathStr.new(fs.root_dir.path)
        src = root.joinpath('a.txt')
        dst = root.joinpath('b.txt')
        src.file_write('data')
        src.atomic_rename(dst)
        assert dst.atomic_read_text() == 'data'
        assert not src.exists()

    def test_chdir_here(self, fs):
        """PathStr.chdir_here() should change the fake cwd."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('folder')
        folder.makedirs(exist_ok=True)
        folder.chdir_here()
        assert os.getcwd() == folder

    def test_cwd(self, fs):
        """PathStr.cwd() should return the fake cwd."""
        cwd = PathStr.cwd()
        assert cwd.isdir()

    def test_iter_entry(self, fs):
        """PathStr.iter_entry() should yield entries with stat()."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('folder')
        file = folder.joinpath('a.txt')
        file.file_write('data')
        entries = list(folder.iter_entry())
        assert len(entries) == 1
        assert entries[0].name == 'a.txt'
        assert entries[0].is_file()
        assert entries[0].stat().st_size == 4


class TestBatchMakedirs:
    """batch_makedirs() against the fake filesystem."""

    def test_batch_makedirs(self, fs):
        """batch_makedirs() should create all parent folders."""
        root = PathStr.new(fs.root_dir.path)
        batch_makedirs([root.joinpath('a/b/c.txt'), root.joinpath('a/d.txt')])
        assert os.path.isdir(root.joinpath('a/b'))
        assert os.path.isdir(root.joinpath('a'))

    def test_batch_makedirs_existing(self, fs):
        """batch_makedirs() should not fail on existing folders."""
        root = PathStr.new(fs.root_dir.path)
        os.makedirs(root.joinpath('a'), exist_ok=True)
        batch_makedirs([root.joinpath('a/b.txt')])
        assert os.path.isdir(root.joinpath('a'))

    def test_batch_makedirs_file_in_way(self, fs):
        """A file in the way of a folder should be removed first."""
        root = PathStr.new(fs.root_dir.path)
        os.makedirs(root.joinpath('a'), exist_ok=True)
        file_write(root.joinpath('a/b'), 'x')
        batch_makedirs([root.joinpath('a/b/c.txt')])
        assert os.path.isdir(root.joinpath('a/b'))
        assert not os.path.isfile(root.joinpath('a/b'))


class TestScale:
    """Sanity tests of the flat dict storage at a larger scale."""

    def test_many_files(self, fs):
        """Creating and iterating many files should work."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('files')
        for i in range(500):
            file_write(folder.joinpath(f'{i:04d}.txt'), str(i))
        assert len(list(folder.iter_files())) == 500
        assert len(os.listdir(folder)) == 500
        assert os.path.getsize(folder.joinpath('0123.txt')) == 3

    def test_atomic_rmtree_many(self, fs):
        """atomic_rmtree() of a large folder should remove everything."""
        root = PathStr.new(fs.root_dir.path)
        folder = root.joinpath('big')
        for i in range(200):
            file_write(folder.joinpath(f'sub/{i}.txt'), 'x')
        assert folder.atomic_rmtree()
        assert not folder.exists()
        assert root.exists()
