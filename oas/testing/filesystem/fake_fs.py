"""
The FakeFilesystem class: an in-memory filesystem and the mock of the
os / builtins file functions.
"""
import builtins
import contextlib
import errno
import io
import os
import time
from threading import RLock

import _io

from .base import IS_WINDOWS, FakeDir, FakeFile, FakeSymlink, _normpath, synchronized
from .entry import FakeDirEntry, FakeScandirIterator
from .file_object import FakeFileObject

# O_ACCMODE is not exposed on Windows, the value is always 3
# (O_RDONLY=0, O_WRONLY=1, O_RDWR=2)
try:
    O_ACCMODE = os.O_ACCMODE
except AttributeError:
    O_ACCMODE = 3


class FakeFilesystem:
    """
    An in-memory filesystem for tests.

    Files, directories and symbolic links are stored in flat dicts keyed
    by normalized absolute path, so path lookups are O(1) dict hits
    instead of the per-segment tree walks of pyfakefs.

    activate() replaces the real file functions with the fake ones:

    - builtins.open() and io.open(), text and binary modes
    - os.path.exists / isfile / isdir / islink / lexists / getsize / realpath
    - os.stat / lstat / fstat
    - os.symlink / readlink
    - os.makedirs / mkdir / rmdir / unlink / remove / rename / replace
    - os.scandir / listdir
    - os.open / write / close / fsync, low level fd operations
    - os.utime / chmod / getcwd / chdir

    Everything is served from memory, the real disk is never touched.

    The filesystem is thread safe: every public operation takes the state lock
    of the filesystem (the file objects of it take the same lock), so the code
    under test may use the filesystem from several threads, a thread pool for
    example. The private helpers are not guarded, they must be called with the
    lock already held.

    Symbolic links are resolved on the path itself and followed by
    stat() / open() / exists() and friends, like the real os. Symlinks
    in the middle of a path (a symlinked directory) are only resolved
    by realpath(), not by the other functions.
    """

    def __init__(self, cwd=None):
        """
        Args:
            cwd (str, optional): Initial working directory.
                Defaults to None, use the real current directory.
        """
        # the state lock, taken by every public operation
        self._lock = RLock()
        if cwd is None:
            cwd = os.getcwd()
        self._cwd = _normpath(cwd, cwd)
        # the drive root on Windows, "/" on POSIX
        root = self._cwd[:2] if IS_WINDOWS else '/'
        self._ino = 0
        now = time.time()
        self.root_dir = FakeDir(
            path=root, mode=0o777, ino=self._next_ino(), nlink=2,
            atime=now, mtime=now, ctime=now,
        )
        # normalized absolute path -> FakeFile
        self._files: "dict[str, FakeFile]" = {}
        # normalized absolute path -> FakeDir
        self._dirs: "dict[str, FakeDir]" = {root: self.root_dir}
        # normalized absolute path -> FakeSymlink
        self._symlinks: "dict[str, FakeSymlink]" = {}
        # fd -> FakeFileObject
        self._fds: "dict[int, FakeFileObject]" = {}
        self._next_fd = 3
        # saved originals of activate() without monkeypatch
        self._saved = []
        # create the cwd chain, so os.getcwd() exists in the fake fs
        if self._cwd != root:
            self._create_parents(self._cwd)
            now = time.time()
            self._dirs[self._cwd] = FakeDir(
                path=self._cwd, mode=0o777, ino=self._next_ino(), nlink=2,
                atime=now, mtime=now, ctime=now,
            )

    def __repr__(self):
        return (
            f'<FakeFilesystem root={self.root_dir.path!r} cwd={self._cwd!r} '
            f'files={len(self._files)} dirs={len(self._dirs)} '
            f'symlinks={len(self._symlinks)}>'
        )

    """
    Internal helpers
    """

    def _next_ino(self):
        """
        Returns:
            int: Next inode number
        """
        self._ino += 1
        return self._ino

    def _take_fd(self):
        """
        Returns:
            int: Next file descriptor number
        """
        fd = self._next_fd
        self._next_fd += 1
        return fd

    def _normpath(self, path):
        """
        Normalize a path against the fake cwd.

        Args:
            path (str): Path to normalize

        Returns:
            str: Normalized absolute path
        """
        return _normpath(path, self._cwd)

    @staticmethod
    def _child_prefix(dirpath):
        """
        The key prefix of the direct and indirect children of a directory.

        Args:
            dirpath (str): Normalized directory path

        Returns:
            str: Key prefix, "/" for the POSIX root
        """
        return '/' if dirpath == '/' else f'{dirpath}/'

    def _has_children(self, dirpath):
        """
        Args:
            dirpath (str): Normalized directory path

        Returns:
            bool: Whether the directory has any child
        """
        prefix = self._child_prefix(dirpath)
        return (
            any(key.startswith(prefix) for key in self._files)
            or any(key.startswith(prefix) for key in self._dirs)
            or any(key.startswith(prefix) for key in self._symlinks)
        )

    def _create_parents(self, path):
        """
        Create the missing parent directories of a path.

        Args:
            path (str): Normalized absolute path

        Raises:
            NotADirectoryError: If a parent path is a file or a symlink
        """
        parent, sep, _ = path.rpartition('/')
        if not sep:
            return
        missing = []
        while parent not in self._dirs:
            if parent in self._files or parent in self._symlinks:
                raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', parent)
            missing.append(parent)
            parent, sep, _ = parent.rpartition('/')
            if not sep:
                break
        now = time.time()
        for folder in reversed(missing):
            self._dirs[folder] = FakeDir(
                path=folder, mode=0o777, ino=self._next_ino(), nlink=2,
                atime=now, mtime=now, ctime=now,
            )

    def _get_entry(self, path):
        """
        Get the record at a path, symbolic links are not followed.

        Args:
            path (str): Normalized absolute path

        Returns:
            FakeFile | FakeDir | None: Record at the path, None if missing
        """
        file = self._files.get(path)
        if file is not None:
            return file
        return self._dirs.get(path)

    def _follow_links(self, path):
        """
        Resolve the symbolic link chain at the path itself.

        The parent components are not resolved: a path through a
        symlinked directory is served as-is (the real os resolves the
        full path, realpath() does that in the fake filesystem too).

        Args:
            path (str): Normalized absolute path

        Returns:
            str: The final path after resolving the link chain, may not
                exist when the chain is dangling

        Raises:
            OSError: If a symlink loop is detected (errno.ELOOP)
        """
        seen = set()
        while path in self._symlinks:
            if path in seen:
                raise OSError(errno.ELOOP, 'Too many levels of symbolic links', path)
            seen.add(path)
            target = self._symlinks[path].target
            if not os.path.isabs(target):
                # relative target, relative to the directory of the link
                target = os.path.join(path.rpartition('/')[0], target)
            path = self._normpath(target)
        return path

    """
    Test data helpers
    """

    @synchronized
    def create_file(self, path, contents=b'', st_mode=None, encoding=None, errors=None):
        """
        Create a file, the parent directories are created automatically.

        Args:
            path (str): Path of the file
            contents (str | bytes): File content. Defaults to b''.
            st_mode (int, optional): Full file mode like os.stat uses,
                e.g. 0o100755. Defaults to None, use 0o666.
            encoding (str): Text encoding when contents is str.
                Defaults to None, use utf-8.
            errors (str): Error handling of encoding when contents is str.
                Defaults to None, use 'strict'.

        Returns:
            FakeFile: The created file record

        Raises:
            FileExistsError: If the path already exists
            IsADirectoryError: If the path is a directory
            NotADirectoryError: If a parent path is a file
        """
        path = self._normpath(path)
        if path in self._dirs or path in self._symlinks:
            raise IsADirectoryError(errno.EISDIR, 'Is a directory', path)
        if path in self._files:
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        self._create_parents(path)
        if isinstance(contents, str):
            contents = contents.encode(encoding or 'utf-8', errors or 'strict')
        elif not isinstance(contents, bytes):
            raise TypeError(f'contents must be str or bytes, not {type(contents).__name__}')
        mode = 0o666 if st_mode is None else st_mode & 0o7777
        now = time.time()
        file = FakeFile(
            path=path, content=contents, mode=mode, ino=self._next_ino(), nlink=1,
            atime=now, mtime=now, ctime=now,
        )
        self._files[path] = file
        return file

    @synchronized
    def create_dir(self, path, st_mode=None):
        """
        Create a directory, the parent directories are created automatically.

        Args:
            path (str): Path of the directory
            st_mode (int, optional): Full directory mode like os.stat uses,
                e.g. 0o40755. Defaults to None, use 0o777.

        Returns:
            FakeDir: The created directory record

        Raises:
            FileExistsError: If the path already exists
            NotADirectoryError: If a parent path is a file
        """
        path = self._normpath(path)
        if path in self._dirs or path in self._files or path in self._symlinks:
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        self._create_parents(path)
        mode = 0o777 if st_mode is None else st_mode & 0o7777
        now = time.time()
        folder = FakeDir(
            path=path, mode=mode, ino=self._next_ino(), nlink=2,
            atime=now, mtime=now, ctime=now,
        )
        self._dirs[path] = folder
        return folder

    @synchronized
    def create_symlink(self, path, target):
        """
        Create a symbolic link, the parent directories are created automatically.

        Args:
            path (str): Path of the link
            target (str): Target path of the link, may be relative or
                absolute, may point to a missing path (dangling link)

        Returns:
            FakeSymlink: The created link record

        Raises:
            FileExistsError: If the path already exists
            NotADirectoryError: If a parent path is a file
        """
        path = self._normpath(path)
        if path in self._files or path in self._dirs or path in self._symlinks:
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        self._create_parents(path)
        now = time.time()
        link = FakeSymlink(
            path=path, target=target, mode=0o777, ino=self._next_ino(), nlink=1,
            atime=now, mtime=now, ctime=now,
        )
        self._symlinks[path] = link
        return link

    @synchronized
    def get_object(self, path):
        """
        Get the record at a path.

        Args:
            path (str): Path of the file or directory

        Returns:
            FakeFile | FakeDir: Record at the path

        Raises:
            FileNotFoundError: If the path does not exist
        """
        path = self._normpath(path)
        entry = self._get_entry(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        return entry

    @synchronized
    def get_file(self, path):
        """
        Get the file record at a path.

        Args:
            path (str): Path of the file

        Returns:
            FakeFile: File record at the path

        Raises:
            FileNotFoundError: If the path is not a file
        """
        path = self._normpath(path)
        file = self._files.get(path)
        if file is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        return file

    @synchronized
    def get_dir(self, path):
        """
        Get the directory record at a path.

        Args:
            path (str): Path of the directory

        Returns:
            FakeDir: Directory record at the path

        Raises:
            FileNotFoundError: If the path is not a directory
        """
        path = self._normpath(path)
        folder = self._dirs.get(path)
        if folder is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        return folder

    @synchronized
    def remove(self, path):
        """
        Remove a file, or an empty directory.

        Args:
            path (str): Path to remove

        Raises:
            FileNotFoundError: If the path does not exist
            OSError: If the path is a non-empty directory
        """
        path = self._normpath(path)
        if path in self._files:
            del self._files[path]
            return
        if path in self._symlinks:
            del self._symlinks[path]
            return
        if path in self._dirs:
            if self._has_children(path):
                raise OSError(errno.ENOTEMPTY, 'Directory not empty', path)
            del self._dirs[path]
            return
        raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)

    @synchronized
    def rmtree(self, path):
        """
        Recursively remove a directory and its content, or a file.

        Args:
            path (str): Path to remove

        Raises:
            FileNotFoundError: If the path does not exist
            OSError: If the path is the root directory
        """
        path = self._normpath(path)
        if path in self._files:
            del self._files[path]
            return
        if path in self._symlinks:
            del self._symlinks[path]
            return
        if path not in self._dirs:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        if path == self.root_dir.path:
            raise OSError(errno.EBUSY, 'Cannot remove the root directory', path)
        prefix = self._child_prefix(path)
        for key in [key for key in self._files if key.startswith(prefix)]:
            del self._files[key]
        for key in [key for key in self._dirs if key.startswith(prefix)]:
            del self._dirs[key]
        del self._dirs[path]

    """
    open()
    """

    @synchronized
    def open(self, file, mode='r', buffering=-1, encoding=None, errors=None,
             newline=None, closefd=True, opener=None):
        """
        Mock of the builtin open().

        Args:
            file (str): Path of the file
            mode (str): Open mode, any of r / w / a / x with optional
                b / t / +. Defaults to 'r'.
            buffering (int): Accepted for compatibility, ignored.
            encoding (str): Text encoding. Defaults to None, use utf-8.
            errors (str): Error handling of encoding.
                Defaults to None, use 'strict'.
            newline (str): Newline handling of text mode.
                Defaults to None, universal newlines.
            closefd (bool): Accepted for compatibility, ignored.
            opener (callable): Accepted for compatibility, ignored.

        Returns:
            FakeFileObject: The opened file object

        Raises:
            FileNotFoundError: If the file does not exist
            FileExistsError: If mode x is used on an existing file
            IsADirectoryError: If the path is a directory
            ValueError: If the mode is invalid
        """
        file = self._normpath(file)
        file = self._follow_links(file)
        mode = str(mode)
        if not mode:
            raise ValueError(f'invalid mode: {mode!r}')
        action = mode[0]
        if action not in 'rwax':
            raise ValueError(f'invalid mode: {mode!r}')
        for char in mode[1:]:
            if char not in 'bt+':
                raise ValueError(f'invalid mode: {mode!r}')
        binary = 'b' in mode
        plus = '+' in mode
        if not binary:
            encoding = encoding or 'utf-8'
            errors = errors or 'strict'
        else:
            encoding = None
            errors = None
            newline = None

        entry = self._files.get(file)
        if entry is None and file in self._dirs:
            raise IsADirectoryError(errno.EISDIR, 'Is a directory', file)
        if action == 'r':
            if entry is None:
                raise FileNotFoundError(errno.ENOENT, 'No such file or directory', file)
        elif action == 'w':
            if entry is None:
                entry = self.create_file(file, st_mode=0o666)
            else:
                entry.content = b''
        elif action == 'a':
            if entry is None:
                entry = self.create_file(file, st_mode=0o666)
        elif action == 'x':
            if entry is not None:
                raise FileExistsError(errno.EEXIST, 'File exists', file)
            entry = self.create_file(file, st_mode=0o666)

        readable = action == 'r' or plus
        writable = action != 'r' or plus
        if action == 'a':
            position = len(entry.content)
        else:
            position = 0
        fobj = FakeFileObject(
            self, entry, mode, binary=binary, readable=readable, writable=writable,
            append=(action == 'a'), position=position, encoding=encoding,
            errors=errors, newline=newline, fd=self._take_fd(),
        )
        self._fds[fobj._fd] = fobj
        return fobj

    """
    os.path functions
    """

    @synchronized
    def exists(self, path):
        """
        Mock of os.path.exists(), follows symbolic links.

        Args:
            path (str):

        Returns:
            bool: Whether the path exists
        """
        return self._get_entry(self._follow_links(self._normpath(path))) is not None

    @synchronized
    def isfile(self, path):
        """
        Mock of os.path.isfile(), follows symbolic links.

        Args:
            path (str):

        Returns:
            bool: Whether the path is a file
        """
        return self._follow_links(self._normpath(path)) in self._files

    @synchronized
    def isdir(self, path):
        """
        Mock of os.path.isdir(), follows symbolic links.

        Args:
            path (str):

        Returns:
            bool: Whether the path is a directory
        """
        return self._follow_links(self._normpath(path)) in self._dirs

    @synchronized
    def islink(self, path):
        """
        Mock of os.path.islink().

        Args:
            path (str):

        Returns:
            bool: Whether the path is a symbolic link
        """
        return self._normpath(path) in self._symlinks

    @synchronized
    def lexists(self, path):
        """
        Mock of os.path.lexists(), True for a dangling symlink too.

        Args:
            path (str):

        Returns:
            bool: Whether the path exists or is a dangling symlink
        """
        path = self._normpath(path)
        return path in self._symlinks or self._get_entry(self._follow_links(path)) is not None

    @synchronized
    def readlink(self, path):
        """
        Mock of os.readlink().

        Args:
            path (str):

        Returns:
            str: Target of the symbolic link

        Raises:
            FileNotFoundError: If the path does not exist
            OSError: If the path is not a symbolic link
        """
        path = self._normpath(path)
        link = self._symlinks.get(path)
        if link is None:
            if self._get_entry(path) is None:
                raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
            raise OSError(errno.EINVAL, 'Invalid argument', path)
        return link.target

    @synchronized
    def symlink(self, src, dst, target_is_directory=False):
        """
        Mock of os.symlink(), the parent directory of dst must exist.

        Args:
            src (str): Target path of the link, may be relative or
                absolute, may point to a missing path (dangling link)
            dst (str): Path of the link
            target_is_directory (bool): Accepted for compatibility,
                the fake filesystem does not check the target type.

        Raises:
            FileExistsError: If dst already exists
            FileNotFoundError: If the parent directory of dst does not exist
        """
        dst = self._normpath(dst)
        if dst in self._files or dst in self._dirs or dst in self._symlinks:
            raise FileExistsError(errno.EEXIST, 'File exists', dst)
        parent, sep, _ = dst.rpartition('/')
        if not sep:
            parent = '/'
        if parent not in self._dirs:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', dst)
        now = time.time()
        link = FakeSymlink(
            path=dst, target=src, mode=0o777, ino=self._next_ino(), nlink=1,
            atime=now, mtime=now, ctime=now,
        )
        self._symlinks[dst] = link

    @synchronized
    def getsize(self, path):
        """
        Mock of os.path.getsize(), follows symbolic links.

        Args:
            path (str):

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the path does not exist
        """
        return self.stat(path).st_size

    @synchronized
    def stat(self, path, follow_symlinks=True, **kwargs):
        """
        Mock of os.stat().

        Args:
            path (str):
            follow_symlinks (bool): False to stat the symbolic link
                itself. Defaults to True.
            **kwargs: Accepted for compatibility

        Returns:
            os.stat_result:

        Raises:
            FileNotFoundError: If the path does not exist
        """
        path = self._normpath(path)
        if follow_symlinks:
            path = self._follow_links(path)
            entry = self._get_entry(path)
            if entry is None:
                raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
            return entry.stat()
        link = self._symlinks.get(path)
        if link is not None:
            return link.stat()
        entry = self._get_entry(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        return entry.stat()

    @synchronized
    def lstat(self, path):
        """
        Mock of os.lstat(), never follows symbolic links.

        Args:
            path (str):

        Returns:
            os.stat_result:

        Raises:
            FileNotFoundError: If the path does not exist
        """
        path = self._normpath(path)
        link = self._symlinks.get(path)
        if link is not None:
            return link.stat()
        entry = self._get_entry(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        return entry.stat()

    @synchronized
    def realpath(self, path, strict=False):
        """
        Mock of os.path.realpath(), resolves symbolic links component by
        component and collapses ".." on the resolved prefix, like the
        real os: a ".." after a symlink goes to the parent of the link
        target, not of the link itself.

        Args:
            path (str):
            strict (bool): Accepted for compatibility, the fake
                filesystem does not check the existence of intermediate
                components

        Returns:
            str: Canonical path with "/" separators

        Raises:
            OSError: If a symlink loop is detected (errno.ELOOP)
        """
        path = str(path)
        if IS_WINDOWS:
            path = path.replace('\\', '/')
        drive = ''
        if IS_WINDOWS and len(path) > 1 and path[1] == ':':
            # explicit drive letter, e.g. "C:/a" or "C:a"
            drive, path = path[:2], path[2:]
        if drive:
            if path.startswith('/'):
                bits = [f'{drive}/'] + path.split('/')[1:]
            else:
                # drive-relative path "C:foo", resolve on the drive root
                bits = [f'{drive}/'] + path.split('/')
        elif path.startswith('/'):
            bits = ['/'] + path.split('/')[1:]
        else:
            # relative path, resolve against the fake cwd
            bits = self._cwd.split('/') + path.split('/')
        if not bits[0]:
            bits = ['/'] + bits
        return self._join_realpath(bits[0], bits[1:])

    def _join_realpath(self, resolved, bits):
        """
        Walk the path components and resolve symbolic links recursively.

        Args:
            resolved (str): Resolved path prefix
            bits (list[str]): Remaining path components

        Returns:
            str: Canonical path with "/" separators

        Raises:
            OSError: If a symlink loop is detected (errno.ELOOP)
        """
        seen = set()
        i = 0
        while i < len(bits):
            bit = bits[i]
            if not bit or bit == '.':
                i += 1
                continue
            if bit == '..':
                # collapse on the resolved prefix, like the real os
                parent = resolved.rpartition('/')[0]
                resolved = parent if parent else resolved
                i += 1
                continue
            candidate = self._normpath(f'{resolved}/{bit}')
            link = self._symlinks.get(candidate)
            if link is None:
                resolved = candidate
                i += 1
                continue
            if candidate in seen:
                raise OSError(errno.ELOOP, 'Too many levels of symbolic links', candidate)
            seen.add(candidate)
            target = link.target
            if os.path.isabs(target):
                if IS_WINDOWS and len(target) > 1 and target[1] == ':':
                    resolved = f'{target[:2]}/'
                    tbits = target[2:].split('/')
                else:
                    resolved = '/'
                    tbits = target.split('/')[1:]
            else:
                # relative target, components are joined to the resolved prefix
                tbits = target.split('/')
            bits = tbits + bits[i + 1:]
            i = 0
        return self._normpath(resolved)

    """
    os directory functions
    """

    @synchronized
    def makedirs(self, path, mode=0o777, exist_ok=False):
        """
        Mock of os.makedirs(), creates the parent directories recursively.

        Args:
            path (str):
            mode (int): Permission bits of the created directories.
                Defaults to 0o777.
            exist_ok (bool): Don't raise if the path exists.
                Defaults to False.

        Raises:
            FileExistsError: If the path exists and exist_ok is False
            NotADirectoryError: If a parent path is a file
        """
        path = self._normpath(path)
        if path in self._dirs:
            if exist_ok:
                return
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        if path in self._files or path in self._symlinks:
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        self._create_parents(path)
        now = time.time()
        self._dirs[path] = FakeDir(
            path=path, mode=mode & 0o7777, ino=self._next_ino(), nlink=2,
            atime=now, mtime=now, ctime=now,
        )

    @synchronized
    def mkdir(self, path, mode=0o777):
        """
        Mock of os.mkdir(), the parent directory must exist.

        Args:
            path (str):
            mode (int): Permission bits of the directory. Defaults to 0o777.

        Raises:
            FileExistsError: If the path exists
            FileNotFoundError: If the parent directory does not exist
        """
        path = self._normpath(path)
        if path in self._dirs or path in self._files or path in self._symlinks:
            raise FileExistsError(errno.EEXIST, 'File exists', path)
        parent, sep, _ = path.rpartition('/')
        if not sep:
            parent = '/'
        if parent not in self._dirs:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        now = time.time()
        self._dirs[path] = FakeDir(
            path=path, mode=mode & 0o7777, ino=self._next_ino(), nlink=2,
            atime=now, mtime=now, ctime=now,
        )

    @synchronized
    def rmdir(self, path):
        """
        Mock of os.rmdir(), the directory must be empty.

        Args:
            path (str):

        Raises:
            FileNotFoundError: If the path does not exist
            NotADirectoryError: If the path is a file or a symlink
            OSError: If the directory is not empty
        """
        path = self._normpath(path)
        if path in self._files or path in self._symlinks:
            raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', path)
        if path not in self._dirs:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        if self._has_children(path):
            raise OSError(errno.ENOTEMPTY, 'Directory not empty', path)
        del self._dirs[path]

    @synchronized
    def unlink(self, path):
        """
        Mock of os.unlink() and os.remove(), removes a symbolic link
        itself, never the link target.

        Args:
            path (str):

        Raises:
            FileNotFoundError: If the path does not exist
            IsADirectoryError: If the path is a directory
        """
        path = self._normpath(path)
        if path in self._files:
            del self._files[path]
            return
        if path in self._symlinks:
            del self._symlinks[path]
            return
        if path in self._dirs:
            raise IsADirectoryError(errno.EISDIR, 'Is a directory', path)
        raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)

    @synchronized
    def rename(self, src, dst):
        """
        Mock of os.rename().

        On Windows renaming over an existing file raises, on POSIX the
        file is replaced, like the real os.

        Args:
            src (str): Source path
            dst (str): Target path

        Raises:
            FileNotFoundError: If the source does not exist
            FileExistsError: On Windows, if the target exists
        """
        self._move(src, dst, overwrite=not IS_WINDOWS)

    @synchronized
    def replace(self, src, dst):
        """
        Mock of os.replace(), the target is always replaced.

        Args:
            src (str): Source path
            dst (str): Target path

        Raises:
            FileNotFoundError: If the source does not exist
        """
        self._move(src, dst, overwrite=True)

    def _move(self, src, dst, overwrite):
        """
        Move a file or a directory, used by rename() and replace().

        Args:
            src (str): Source path
            dst (str): Target path
            overwrite (bool): Whether to replace an existing target
        """
        src = self._normpath(src)
        dst = self._normpath(dst)
        if src in self._files:
            if dst in self._dirs:
                raise IsADirectoryError(errno.EISDIR, 'Is a directory', dst)
            if dst in self._files:
                if not overwrite:
                    raise FileExistsError(errno.EEXIST, 'File exists', dst)
                del self._files[dst]
            file = self._files.pop(src)
            file.path = dst
            self._files[dst] = file
            return
        if src in self._symlinks:
            if dst in self._dirs:
                raise IsADirectoryError(errno.EISDIR, 'Is a directory', dst)
            if dst in self._files or dst in self._symlinks:
                if not overwrite:
                    raise FileExistsError(errno.EEXIST, 'File exists', dst)
                if dst in self._files:
                    del self._files[dst]
                else:
                    del self._symlinks[dst]
            link = self._symlinks.pop(src)
            link.path = dst
            self._symlinks[dst] = link
            return
        if src in self._dirs:
            if src == self.root_dir.path:
                raise OSError(errno.EBUSY, 'Cannot move the root directory', src)
            if dst in self._files:
                raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', dst)
            if dst in self._dirs:
                if not overwrite:
                    raise FileExistsError(errno.EEXIST, 'File exists', dst)
                if self._has_children(dst):
                    raise OSError(errno.ENOTEMPTY, 'Directory not empty', dst)
                del self._dirs[dst]
            folder = self._dirs.pop(src)
            folder.path = dst
            self._dirs[dst] = folder
            # move the descendants, keys are snapshotted first
            prefix = self._child_prefix(src)
            for key in [key for key in self._files if key.startswith(prefix)]:
                new_key = dst + key[len(src):]
                self._files[new_key] = self._files.pop(key)
                self._files[new_key].path = new_key
            for key in [key for key in self._dirs if key.startswith(prefix)]:
                new_key = dst + key[len(src):]
                self._dirs[new_key] = self._dirs.pop(key)
                self._dirs[new_key].path = new_key
            return
        raise FileNotFoundError(errno.ENOENT, 'No such file or directory', src)

    @synchronized
    def scandir(self, path):
        """
        Mock of os.scandir(), returns an iterator of FakeDirEntry.

        Args:
            path (str):

        Returns:
            FakeScandirIterator: Iterator of the directory entries

        Raises:
            FileNotFoundError: If the path does not exist
            NotADirectoryError: If the path is a file
        """
        path = self._normpath(path)
        if path not in self._dirs:
            if path in self._files:
                raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', path)
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        prefix = self._child_prefix(path)
        entries = []
        for key in self._files:
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    entries.append(FakeDirEntry(name, key, False, self._files[key].stat()))
        for key in self._dirs:
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    entries.append(FakeDirEntry(name, key, True, self._dirs[key].stat()))
        for key, link in self._symlinks.items():
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    follow_stat = None
                    try:
                        target = self._follow_links(key)
                    except OSError:
                        target = None
                    entry = self._get_entry(target) if target is not None else None
                    if entry is not None:
                        follow_stat = entry.stat()
                    entries.append(FakeDirEntry(
                        name, key, False, link.stat(),
                        is_symlink=True, follow_stat=follow_stat))
        return FakeScandirIterator(entries)

    @synchronized
    def listdir(self, path):
        """
        Mock of os.listdir(), names are sorted for deterministic tests.

        Args:
            path (str):

        Returns:
            list[str]: Names of the directory entries

        Raises:
            FileNotFoundError: If the path does not exist
            NotADirectoryError: If the path is a file
        """
        path = self._normpath(path)
        if path not in self._dirs:
            if path in self._files:
                raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', path)
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        prefix = self._child_prefix(path)
        names = []
        for key in self._files:
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    names.append(name)
        for key in self._dirs:
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    names.append(name)
        for key in self._symlinks:
            if key.startswith(prefix):
                name = key[len(prefix):]
                if '/' not in name:
                    names.append(name)
        return sorted(names)

    """
    Low level fd functions
    """

    @synchronized
    def os_open(self, path, flags, mode=0o777):
        """
        Mock of os.open(), returns a fake file descriptor.

        Args:
            path (str):
            flags (int): Open flags, e.g. os.O_CREAT | os.O_WRONLY
            mode (int): Permission bits of a created file. Defaults to 0o777.

        Returns:
            int: Fake file descriptor

        Raises:
            FileNotFoundError: If the file does not exist and O_CREAT is not set
            FileExistsError: If O_CREAT | O_EXCL is used on an existing file
            IsADirectoryError: If the path is a directory
        """
        path = self._normpath(path)
        path = self._follow_links(path)
        accmode = flags & O_ACCMODE
        readable = accmode == os.O_RDONLY or accmode == os.O_RDWR
        writable = accmode == os.O_WRONLY or accmode == os.O_RDWR
        if path in self._files:
            entry = self._files[path]
            if flags & os.O_CREAT and flags & os.O_EXCL:
                raise FileExistsError(errno.EEXIST, 'File exists', path)
            if flags & os.O_TRUNC:
                entry.content = b''
        elif path in self._dirs:
            raise IsADirectoryError(errno.EISDIR, 'Is a directory', path)
        else:
            if not flags & os.O_CREAT:
                raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
            entry = self.create_file(path, st_mode=mode & 0o7777)
        append = bool(flags & os.O_APPEND)
        fobj = FakeFileObject(
            self, entry, '', binary=True, readable=readable, writable=writable,
            append=append, position=len(entry.content) if append else 0,
            encoding=None, errors=None, newline=None, fd=self._take_fd(),
        )
        self._fds[fobj._fd] = fobj
        return fobj._fd

    @synchronized
    def os_write(self, fd, data):
        """
        Mock of os.write().

        Args:
            fd (int): Fake file descriptor
            data (bytes): Data to write

        Returns:
            int: Number of bytes written

        Raises:
            OSError: If the fd is not open
        """
        fobj = self._fds.get(fd)
        if fobj is None:
            raise OSError(errno.EBADF, 'Bad file descriptor')
        return fobj.write(data)

    @synchronized
    def os_close(self, fd):
        """
        Mock of os.close().

        Args:
            fd (int): Fake file descriptor

        Raises:
            OSError: If the fd is not open
        """
        fobj = self._fds.get(fd)
        if fobj is None:
            raise OSError(errno.EBADF, 'Bad file descriptor')
        fobj.close()

    @synchronized
    def os_fsync(self, fd):
        """
        Mock of os.fsync(), a no-op because content is already in memory.

        Args:
            fd (int): Fake file descriptor

        Raises:
            OSError: If the fd is not open
        """
        if fd not in self._fds:
            raise OSError(errno.EBADF, 'Bad file descriptor')

    @synchronized
    def os_fstat(self, fd):
        """
        Mock of os.fstat().

        Args:
            fd (int): Fake file descriptor

        Returns:
            os.stat_result: Stat result of the open file

        Raises:
            OSError: If the fd is not open
        """
        fobj = self._fds.get(fd)
        if fobj is None:
            raise OSError(errno.EBADF, 'Bad file descriptor')
        return fobj._entry.stat()

    """
    Other os functions
    """

    @synchronized
    def utime(self, path, times=None, ns=None):
        """
        Mock of os.utime().

        Args:
            path (str):
            times (tuple[float, float]): (atime, mtime) to set.
                Defaults to None, use the current time.
            ns (tuple[int, int]): (atime, mtime) in nanoseconds.
                Defaults to None.

        Raises:
            FileNotFoundError: If the path does not exist
        """
        path = self._normpath(path)
        path = self._follow_links(path)
        entry = self._get_entry(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        if ns is not None:
            atime, mtime = ns[0] / 1e9, ns[1] / 1e9
        elif times is not None:
            atime, mtime = times
        else:
            atime = mtime = time.time()
        entry.atime = atime
        entry.mtime = mtime

    @synchronized
    def chmod(self, path, mode, **kwargs):
        """
        Mock of os.chmod().

        Args:
            path (str):
            mode (int): New permission bits
            **kwargs: Accepted for compatibility

        Raises:
            FileNotFoundError: If the path does not exist
        """
        path = self._normpath(path)
        path = self._follow_links(path)
        entry = self._get_entry(path)
        if entry is None:
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        entry.mode = mode & 0o7777

    @synchronized
    def getcwd(self):
        """
        Mock of os.getcwd().

        Returns:
            str: The fake current working directory
        """
        return self._cwd

    @synchronized
    def chdir(self, path):
        """
        Mock of os.chdir().

        Args:
            path (str):

        Raises:
            FileNotFoundError: If the path does not exist
            NotADirectoryError: If the path is a file
        """
        path = self._normpath(path)
        path = self._follow_links(path)
        if path not in self._dirs:
            if path in self._files:
                raise NotADirectoryError(errno.ENOTDIR, 'Not a directory', path)
            raise FileNotFoundError(errno.ENOENT, 'No such file or directory', path)
        self._cwd = path

    """
    Activate / deactivate the mock
    """

    @contextlib.contextmanager
    def patch_open_code(self):
        """
        Temporarily route io.open_code / _io.open_code to the fake fs.

        The Python import machinery reads source files with
        _io.open_code() instead of open(), so code that goes through
        importlib (e.g. oas.ext.file.loadpy) is not covered by
        activate(). Entering this context manager patches
        _io.open_code (and io.open_code, the same underlying function)
        to the fake fs, and restores the originals on exit.

        It is intentionally not part of activate(): a global patch
        would make the test's own imports read from the fake fs and
        fail with FileNotFoundError, because the project sources live
        on the real disk.

        Example:
            fs.create_file('/mod.py', contents='a = 1')
            with fs.patch_open_code():
                module = loadpy('/mod.py')
        """
        originals = (io.open_code, _io.open_code)
        fake_open_code = lambda path: self.open(path, 'rb')
        io.open_code = fake_open_code
        _io.open_code = fake_open_code
        try:
            yield
        finally:
            io.open_code, _io.open_code = originals

    def _iter_patches(self):
        """
        Yield the (module, name, fake) targets to patch.

        Yields:
            tuple[module, str, callable]: Patch targets
        """
        yield builtins, 'open', self.open
        yield io, 'open', self.open
        yield os.path, 'exists', self.exists
        yield os.path, 'isfile', self.isfile
        yield os.path, 'isdir', self.isdir
        yield os.path, 'islink', self.islink
        yield os.path, 'lexists', self.lexists
        yield os.path, 'getsize', self.getsize
        yield os.path, 'realpath', self.realpath
        yield os, 'stat', self.stat
        yield os, 'lstat', self.lstat
        yield os, 'fstat', self.os_fstat
        yield os, 'symlink', self.symlink
        yield os, 'readlink', self.readlink
        yield os, 'scandir', self.scandir
        yield os, 'listdir', self.listdir
        yield os, 'makedirs', self.makedirs
        yield os, 'mkdir', self.mkdir
        yield os, 'rmdir', self.rmdir
        yield os, 'unlink', self.unlink
        yield os, 'remove', self.unlink
        yield os, 'rename', self.rename
        yield os, 'replace', self.replace
        yield os, 'open', self.os_open
        yield os, 'write', self.os_write
        yield os, 'close', self.os_close
        yield os, 'fsync', self.os_fsync
        yield os, 'utime', self.utime
        yield os, 'chmod', self.chmod
        yield os, 'getcwd', self.getcwd
        yield os, 'chdir', self.chdir

    def activate(self, monkeypatch=None):
        """
        Patch builtins.open, io.open and the os / os.path functions.

        Args:
            monkeypatch (pytest.MonkeyPatch | None): When given, the
                patches are registered on it and undone automatically.
                When None, the patches are undone by deactivate().

        Returns:
            FakeFilesystem: Self
        """
        if monkeypatch is None:
            for module, name, fake in self._iter_patches():
                original = getattr(module, name)
                setattr(module, name, fake)
                self._saved.append((module, name, original))
        else:
            for module, name, fake in self._iter_patches():
                monkeypatch.setattr(module, name, fake)
        return self

    def deactivate(self):
        """
        Undo the patches installed by activate() without monkeypatch.
        """
        for module, name, original in reversed(self._saved):
            setattr(module, name, original)
        self._saved.clear()

    def __enter__(self):
        return self.activate()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.deactivate()
        return False
