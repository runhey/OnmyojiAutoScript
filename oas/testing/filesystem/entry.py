"""
Mocks of os.DirEntry and the iterator returned by os.scandir().

The entry information (is_dir / is_file / stat) is resolved once when
the directory is scanned, like the real os.DirEntry caches it.
"""
import errno
import stat


class FakeDirEntry:
    """
    Mock of os.DirEntry, all information is resolved at scandir() time.

    For symlink entries the follow state is resolved once at scandir()
    time too: `_follow_stat` is the stat of the link target, None when
    the link is dangling.
    """
    __slots__ = ('name', 'path', '_is_dir', '_is_symlink', '_stat', '_follow_stat')

    def __init__(self, name, path, is_dir, stat_result, is_symlink=False, follow_stat=None):
        """
        Args:
            name (str): Name of the entry
            path (str): Full normalized path of the entry
            is_dir (bool): Whether the entry is a directory
            stat_result (os.stat_result): Stat result of the entry itself
            is_symlink (bool): Whether the entry is a symbolic link.
                Defaults to False.
            follow_stat (os.stat_result | None): Stat result of the link
                target, None for a dangling link or a non-link entry.
                Defaults to None.
        """
        self.name = name
        self.path = path
        self._is_dir = is_dir
        self._is_symlink = is_symlink
        self._stat = stat_result
        self._follow_stat = follow_stat

    def is_dir(self, follow_symlinks=True):
        """
        Args:
            follow_symlinks (bool): Whether to follow symbolic links.
                Defaults to True.

        Returns:
            bool: Whether the entry is a directory
        """
        if self._is_symlink:
            if not follow_symlinks:
                return False
            if self._follow_stat is None:
                return False
            return stat.S_ISDIR(self._follow_stat.st_mode)
        return self._is_dir

    def is_file(self, follow_symlinks=True):
        """
        Args:
            follow_symlinks (bool): Whether to follow symbolic links.
                Defaults to True.

        Returns:
            bool: Whether the entry is a file
        """
        if self._is_symlink:
            if not follow_symlinks:
                return False
            if self._follow_stat is None:
                return False
            return stat.S_ISREG(self._follow_stat.st_mode)
        return not self._is_dir

    def is_symlink(self):
        """
        Returns:
            bool: Whether the entry is a symbolic link
        """
        return self._is_symlink

    def stat(self, follow_symlinks=True):
        """
        Args:
            follow_symlinks (bool): Whether to follow symbolic links.
                Defaults to True.

        Returns:
            os.stat_result: Stat result of the entry

        Raises:
            FileNotFoundError: If following a dangling symlink
        """
        if self._is_symlink and follow_symlinks:
            if self._follow_stat is None:
                raise FileNotFoundError(errno.ENOENT, 'No such file or directory', self.path)
            return self._follow_stat
        return self._stat

    def __repr__(self):
        return f'<FakeDirEntry {self.path!r}>'


class FakeScandirIterator:
    """
    Mock of the iterator returned by os.scandir().

    Supports both iteration and context manager usage.
    """
    def __init__(self, entries):
        """
        Args:
            entries (list[FakeDirEntry]): Entries of the directory
        """
        self._iterator = iter(entries)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iterator)
