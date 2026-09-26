"""
In-memory fake filesystem for tests, a simplified and faster pyfakefs.

Every file is stored in memory, tests never read or write the real
disk. Files are recorded as dataclass records (FakeFile / FakeDir), and
stored in flat dicts keyed by normalized absolute path, so path
lookups are O(1) dict hits instead of the per-segment tree walks of
pyfakefs.

Usage as a pytest fixture: import the fixture at the top of the test
module, then the file functions are mocked in every test that
requests it.

    from oas.testing.filesystem import fs  # noqa: F401

    def test_write(fs):
        fs.create_file('/data.txt', contents='hello')
        with open('/data.txt') as f:
            assert f.read() == 'hello'

The `# noqa: F401` is required: pytest injects the fixture through the
argument name, so the import has no visible reference in the module
and ruff would remove it as an unused import otherwise.

The fixture is imported explicitly in every test module that uses it,
never registered in a conftest.py nor installed as a pytest plugin.
The explicit import keeps the fake filesystem visible in the test
source, and avoids any confusion with the "fs" fixture of the
pyfakefs pytest plugin (the plugin is disabled globally in
pyproject.toml).

The fixture is a full replacement of the filesystem: every path is
served by the fake filesystem, nothing touches the real disk. Python
imports inside a test keep working because the import machinery reads
sources with io.open_code(), which is not patched.

Mocked functions:

- builtins.open() and io.open(), text and binary modes
- os.path.exists / isfile / isdir / islink / lexists / getsize / realpath
- os.stat / lstat / fstat
- os.symlink / readlink
- os.makedirs / mkdir / rmdir / unlink / remove / rename / replace
- os.scandir / listdir
- os.open / write / close / fsync, low level fd operations
- os.utime / chmod / getcwd / chdir

Symbolic links are supported: os.symlink() / os.readlink() work, and
stat() / open() / exists() and friends follow the link like the real
os (os.lstat() and stat(follow_symlinks=False) return the link itself).

The filesystem is thread safe: every operation takes the state lock of
the filesystem, and the file objects returned by open() take the same
lock. Code under test may therefore use the filesystem from several
threads, a thread pool for example, without a race on the records.

The whole oas/ext/path stack (PathStr, atomic read/write, iter
folders, makedir) works on the fake filesystem without changes, so it
is a drop-in replacement of pyfakefs for the deploy tests:

    fs.create_file('/full.pack', contents=...)
    fs.remove(target)
    env.PROJECT_ROOT = PathStr.new(fs.root_dir.path)

io.open_code() is NOT mocked by the fixture on purpose: a global patch
would make the test's own Python imports read from the fake fs and
fail. Code that loads sources through importlib (e.g. loadpy) can
opt in with the fs.patch_open_code() context manager, which routes
io.open_code / _io.open_code to the fake fs for the duration of the
with block:

    from oas.ext.file.loadpy import loadpy

    def test_loadpy(fs):
        fs.create_file('/valid.py', contents='a = 1')
        with fs.patch_open_code():
            module = loadpy('/valid.py')
        assert module.a == 1

Not supported (documented limitations):

- symlinks in the middle of a path (a symlinked directory) are only
  resolved by realpath(), the other functions resolve the link at the
  path itself
- os.walk(), os.access() and other rarely used os functions
- tarfile writes through its own open(), it is not mocked
  (zipfile goes through io.open and works)
- do not combine the fixture with pytest tmp_path / tmpdir, the fake
  os.makedirs would create the tmp dirs in the fake filesystem
"""
import pytest

from .base import FakeDir, FakeFile, FakeSymlink
from .entry import FakeDirEntry, FakeScandirIterator
from .fake_fs import FakeFilesystem
from .file_object import FakeFileObject

__all__ = [
    'FakeDir',
    'FakeDirEntry',
    'FakeFile',
    'FakeFileObject',
    'FakeFilesystem',
    'FakeScandirIterator',
    'FakeSymlink',
    'fs',
]


@pytest.fixture
def fs(monkeypatch):
    """
    An in-memory filesystem pytest fixture.

    The fixture patches builtins.open, io.open and the os / os.path
    file functions, all file operations go to the memory filesystem
    and the real disk is never touched. The patches are undone
    automatically when the test finishes.

    The logger caches its log file fd on the LogWriter singleton. The
    fixture resets the logger caches before and after the test, so logs
    during the test don't leak into the real log file, and the cached fd
    left by the test doesn't point into the fake filesystem after
    deactivation.

    Yields:
        FakeFilesystem: The active fake filesystem
    """
    try:
        from oas.logger.writer import LogWriter
    except ImportError:
        LogWriter = None

    fake = FakeFilesystem()
    fake.activate(monkeypatch)
    if LogWriter is not None:
        LogWriter().close_fd()
    yield fake
    if LogWriter is not None:
        LogWriter().close_fd()
    fake.deactivate()
