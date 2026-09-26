"""
Base types of the in-memory fake filesystem.

Path normalization, the file/directory records (dataclass with slots) and the state
lock helper.
"""
import os
import stat
from dataclasses import dataclass
from functools import wraps

IS_WINDOWS = os.name == 'nt'


def synchronized(method):
    """
    Run a method of the fake filesystem with the state lock of its filesystem

    The records of the filesystem are a shared state and the code under test may
    use the filesystem from several threads (a thread pool), so every operation
    takes the lock of its own filesystem. The lock is reentrant: one operation
    may call another one, and the file objects of the filesystem take the same
    lock. The private helpers of the classes are not decorated, they must be
    called with the lock already held.

    Args:
        method (callable): Method to wrap

    Returns:
        callable: The method, guarded by ``self._lock``
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


def _normpath(path, cwd):
    """
    Normalize a path to an absolute path with "/" separators.

    Windows drive letters ("C:") are kept as the drive root, absolute
    paths without a drive letter get the drive of cwd, relative paths
    are resolved against cwd. The segment collapsing ("." and "..")
    is delegated to os.path.normpath(), which handles all edge cases
    of the platform, only the resolution and the separator style are
    done here.

    Args:
        path (str): Path to normalize
        cwd (str): Normalized absolute current working directory

    Returns:
        str: Normalized absolute path
    """
    path = str(path)
    if IS_WINDOWS:
        path = path.replace('\\', '/')
    drive = ''
    if IS_WINDOWS and len(path) > 1 and path[1] == ':':
        # explicit drive letter, e.g. "C:/a" or "C:"
        drive, path = path[:2], path[2:]
    if not path.startswith('/'):
        if drive:
            # drive-relative path "C:foo", resolved on the drive root
            path = f'/{path}'
        else:
            # relative path, resolve against cwd
            path = f'{cwd}/{path}'
            if IS_WINDOWS and len(path) > 1 and path[1] == ':':
                # the joined path starts with the cwd drive
                drive, path = path[:2], path[2:]
    elif IS_WINDOWS and not drive:
        # absolute path without a drive letter, e.g. "/data.txt",
        # use the drive of cwd like the real os
        drive = cwd[:2]
    if drive:
        # "C:" is the drive root, "C:/a" is a path on the drive
        path = drive if path == '/' else f'{drive}/{path}'
    # collapse ".", ".." and duplicate separators
    path = os.path.normpath(path)
    if IS_WINDOWS:
        path = path.replace('\\', '/')
        if drive and path == f'{drive}/':
            # normpath() returns "C:/" for the drive root
            path = drive
    elif path.startswith('//'):
        # normpath() keeps a leading "//" on POSIX, the root is "/"
        path = path[1:]
    return path


def _build_stat(st_mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime):
    """
    Build an os.stat_result from record fields.

    Args:
        st_mode (int): File mode with the file type bits
        ino (int): Inode number
        dev (int): Device number
        nlink (int): Link count
        uid (int): Owner user id
        gid (int): Owner group id
        size (int): File size
        atime (float): Last access time
        mtime (float): Last modification time
        ctime (float): Creation time

    Returns:
        os.stat_result:
    """
    return os.stat_result((st_mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime))


@dataclass(slots=True)
class FakeFile:
    """
    In-memory record of a created file, nothing is written to the real disk.

    Attributes:
        path (str): Normalized absolute path of the file
        content (bytes): File content
        mode (int): Permission bits, e.g. 0o666
        ino (int): Inode number
        dev (int): Device number
        nlink (int): Link count
        uid (int): Owner user id
        gid (int): Owner group id
        atime (float): Last access time
        mtime (float): Last modification time
        ctime (float): Creation time
    """
    path: str
    content: bytes = b''
    mode: int = 0o666
    ino: int = 0
    dev: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime: float = 0.0
    mtime: float = 0.0
    ctime: float = 0.0

    def stat(self):
        """
        Get the stat result of the file.

        Returns:
            os.stat_result:
        """
        return _build_stat(
            stat.S_IFREG | self.mode, self.ino, self.dev, self.nlink,
            self.uid, self.gid, len(self.content), self.atime, self.mtime, self.ctime,
        )


@dataclass(slots=True)
class FakeDir:
    """
    In-memory record of a created directory, nothing is written to the real disk.

    Attributes:
        path (str): Normalized absolute path of the directory
        mode (int): Permission bits, e.g. 0o777
        ino (int): Inode number
        dev (int): Device number
        nlink (int): Link count
        uid (int): Owner user id
        gid (int): Owner group id
        atime (float): Last access time
        mtime (float): Last modification time
        ctime (float): Creation time
    """
    path: str
    mode: int = 0o777
    ino: int = 0
    dev: int = 0
    nlink: int = 2
    uid: int = 0
    gid: int = 0
    atime: float = 0.0
    mtime: float = 0.0
    ctime: float = 0.0

    def stat(self):
        """
        Get the stat result of the directory.

        Returns:
            os.stat_result:
        """
        return _build_stat(
            stat.S_IFDIR | self.mode, self.ino, self.dev, self.nlink,
            self.uid, self.gid, 0, self.atime, self.mtime, self.ctime,
        )


@dataclass(slots=True)
class FakeSymlink:
    """
    In-memory record of a symbolic link, nothing is written to the real disk.

    Attributes:
        path (str): Normalized absolute path of the link
        target (str): Target path of the link, as passed to symlink()
        mode (int): Permission bits, e.g. 0o777
        ino (int): Inode number
        dev (int): Device number
        nlink (int): Link count
        uid (int): Owner user id
        gid (int): Owner group id
        atime (float): Last access time
        mtime (float): Last modification time
        ctime (float): Creation time
    """
    path: str
    target: str
    mode: int = 0o777
    ino: int = 0
    dev: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime: float = 0.0
    mtime: float = 0.0
    ctime: float = 0.0

    def stat(self):
        """
        Get the stat result of the link itself (S_IFLNK).

        Returns:
            os.stat_result:
        """
        return _build_stat(
            stat.S_IFLNK | self.mode, self.ino, self.dev, self.nlink,
            self.uid, self.gid, len(self.target), self.atime, self.mtime, self.ctime,
        )
