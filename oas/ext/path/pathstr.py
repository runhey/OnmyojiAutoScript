from .atomic import *
from .calc import *
from .iter import *


class PathStr(str):
    """
    A faster alternative of Pathlib

    If you really need high performance path calculations, use path functions instead

    joinpath:
        function joinpath(root, path)     0.26us
        PathStr  root.joinpath(path)      0.71us
        os path  os.path.join(root, path) 2.55us
        pathlib  root.joinpath(path)      2.94us
    """
    __slots__ = ()

    @classmethod
    def new(cls, path):
        """
        Create a PathStr object from str
        Don't do "PathStr(path)", path should be normalized first

        Args:
            path (str): Path string

        Returns:
            PathStr: Normalized path string
        """
        return cls(normpath(path))

    @classmethod
    def cwd(cls):
        """
        Create a PathStr object from current path

        Returns:
            PathStr: Current working directory
        """
        return cls(os.getcwd())

    def chdir_here(self):
        """
        Change dir to this path

        Examples:
            PathStr.new(__file__).uppath(3).chdir_here()

        Returns:
            PathStr: Self
        """
        os.chdir(self)
        return self

    def __fspath__(self):
        """
        Path protocol, so PathStr can be used as os.PathLike

        Returns:
            str: Path string
        """
        return str(self)

    """
    Path calculations
    """

    def normpath(self):
        """
        Equivalent to os.path.normpath(self)

        Returns:
            PathStr: Normalized path
        """
        return self.__class__(normpath(self))

    def uppath(self, up=1):
        """
        Equivalent to os.path.join(self, '../')

        Args:
            up (int): Directory upward level. Defaults to 1.

        Returns:
            PathStr: Path to upper directory
        """
        return self.__class__(uppath(self, up=up))

    def joinpath(self, path):
        """
        Equivalent to os.path.join(self, path)
        but "./" and "../" is not available, to do "../" use uppath() instead

        Args:
            path (str): Path to join

        Returns:
            PathStr: Joined path
        """
        return self.__class__(joinnormpath(self, path))

    def __truediv__(self, other):
        """
        root = PathStr.new(__file__).uppath(3)
        path = root / "alas.json"

        Args:
            other (str): Path to join

        Returns:
            PathStr: Joined path
        """
        return self.__class__(joinnormpath(self, other))

    def abspath(self):
        """
        Equivalent to os.path.abspath(self, path)

        Note that, to improve performance, this method should be used less
        Reuse root folder is recommended:
            root = PathStr.new(__file__).uppath(3)
            path = root.joinpath('config/alas.json')
        instead of creating everytime:
            path = PathStr.new('config/alas.json').abspath()

        Returns:
            PathStr: Absolute path
        """
        return self.__class__(abspath(self))

    def is_abspath(self):
        """
        Equivalent to os.path.isabs(self, path)

        Returns:
            bool: Whether path is absolute
        """
        return is_abspath(self)

    @property
    def name(self):
        """
        /abc/def.png -> def.png
        /abc/def     -> def
        /abc/.git    -> .git

        Returns:
            str: Filename
        """
        return get_name(self)

    @property
    def stem(self):
        """
        /abc/def.png -> def
        /abc/def     -> def
        /abc/.git    -> ""

        Returns:
            str: Filename without last extension
        """
        return get_stem(self)

    @property
    def rootstem(self):
        """
        /abc/def.part1.png -> def
        /abc/def.png -> def
        /abc/def     -> def
        /abc/.git    -> ""

        Returns:
            str: Filename without any extension
        """
        return get_rootstem(self)

    @property
    def suffix(self):
        """
        /abc/def.png -> .png
        /abc/def     -> ""
        /abc/.git    -> .git

        Returns:
            str: Last extension
        """
        return get_suffix(self)

    @property
    def multisuffix(self):
        """
        /abc/def.part1.png -> .part1.png
        /abc/def.png -> .png
        /abc/def     -> ""
        /abc/.git    -> .git

        Returns:
            str: All extensions
        """
        return get_multisuffix(self)

    def with_name(self, name):
        """
        /abc/def.png -> /abc/xxx
        /abc/def     -> /abc/xxx
        /abc/.git    -> /abc/xxx

        Args:
            name (str): New filename

        Returns:
            PathStr: Path with new filename
        """
        return self.__class__(with_name(self, name))

    def with_stem(self, name):
        """
        /abc/def.png -> /abc/xxx.png
        /abc/def     -> /abc/xxx
        /abc/.git    -> /abc/xxx.git

        Args:
            name (str): New stem (filename without extension)

        Returns:
            PathStr: Path with new stem
        """
        return self.__class__(with_stem(self, name))

    def with_rootstem(self, name):
        """
        /abc/def.part1.png -> /abc/xxx.part1.png
        /abc/def.png -> /abc/xxx.png
        /abc/def     -> /abc/xxx
        /abc/.git    -> /abc/xxx.git

        Args:
            name (str): New stem (filename without extension)

        Returns:
            PathStr: Path with new stem
        """
        return self.__class__(with_rootstem(self, name))

    def with_suffix(self, name):
        """
        /abc/def.png -> /abc/def.xxx
        /abc/def     -> /abc/def.xxx
        /abc/.git    -> /abc/.xxx

        Args:
            name (str): New extension

        Returns:
            PathStr: Path with new extension
        """
        return self.__class__(with_suffix(self, name))

    def with_multisuffix(self, name):
        """
        /abc/def.part1.png -> /abc/def.xxx.xxx
        /abc/def     -> /abc/def.xxx
        /abc/.git    -> /abc/.xxx

        Args:
            name (str): New extension

        Returns:
            PathStr: Path with new extension
        """
        return self.__class__(with_multisuffix(self, name))

    def to_posix(self):
        """
        Convert to posix path
        Note that this method returns str instead of PathStr,
        since path is no longer normalized.

        Returns:
            str:
        """
        return to_posix(self)

    def to_python_import(self):
        """
        Convert path to python dot-like import
        path/to/python.py -> path.to.python

        Returns:
            str:
        """
        return to_python_import(self)

    def subpath_to(self, root):
        """
        Calculate sub-path to `root`.
        If `self` is not sub-path to `root`, return `self`

        Args:
            root (str):

        Returns:
            PathStr
        """
        return self.__class__(subpath_to(self, root))

    @property
    def is_tmp_file(self):
        """
        Check if path is a temporary file

        Returns:
            bool: Whether path is a temporary file
        """
        return is_tmp_file(self)

    def to_tmp_file(self):
        """
        Convert a filename or directory name to tmp
        filename.sTD2kF.tmp -> filename

        Returns:
            PathStr: Temporary file path
        """
        return self.__class__(to_tmp_file(self))

    def to_nontmp_file(self):
        """
        Convert a tmp filename or directory name to original file
        filename.sTD2kF.tmp -> filename

        Returns:
            PathStr: Original file path
        """
        return self.__class__(to_nontmp_file(self))

    """
    File read/write

    Note that always using atomic method is recommended,
    Call simple read/write on tmp files only.
    """

    def file_write(self, data):
        """
        Write data into file, auto create directory
        Auto determines write mode based on the type of data.

        Args:
            data (str | bytes): String or bytes to write

        Returns:
            PathStr: Self
        """
        file_write(self, data)
        return self

    def file_write_stream(self, data_generator):
        """
        Only creates a file if the generator yields at least one data chunk.
        Auto determines write mode based on the type of first chunk.

        Args:
            data_generator (Iterable): An iterable that yields data chunks (str or bytes)

        Returns:
            PathStr: Self
        """
        file_write_stream(self, data_generator)
        return self

    def atomic_write(self, data):
        """
        Atomic file write with minimal IO operation
        and handles cases where file might be read by another process.

        os.replace() is an atomic operation among all OS,
        we write to temp file then do os.replace()

        Args:
            data (str | bytes): String or bytes to write

        Returns:
            PathStr: Self
        """
        atomic_write(self, data)
        return self

    def atomic_write_stream(self, data_generator):
        """
        Atomic file write with streaming data support.
        Handles cases where file might be read by another process.

        os.replace() is an atomic operation among all OS,
        we write to temp file then do os.replace()

        Args:
            data_generator (Iterable): An iterable that yields data chunks (str or bytes)

        Returns:
            PathStr: Self
        """
        atomic_write_stream(self, data_generator)
        return self

    def atomic_read_text(self, encoding='utf-8', errors='strict'):
        """
        Atomic file read with minimal IO operation

        Args:
            encoding (str): Text encoding. Defaults to 'utf-8'.
            errors (str): Error handling strategy. Defaults to 'strict'.
                'strict', 'ignore', 'replace' and any other errors mode in open()

        Returns:
            str: File content
        """
        return atomic_read_text(self, encoding=encoding, errors=errors)

    def atomic_read_text_stream(self, encoding='utf-8', errors='strict', chunk_size=8192):
        """
        Read text file content as stream

        Args:
            encoding (str): Text encoding. Defaults to 'utf-8'.
            errors (str): Error handling strategy. Defaults to 'strict'.
                'strict', 'ignore', 'replace' and any other errors mode in open()
            chunk_size (int): Size of chunks to read. Defaults to 8192.

        Returns:
            Iterable[str]: Generator yielding file content chunks
        """
        return atomic_read_text_stream(self, encoding=encoding, errors=errors, chunk_size=chunk_size)

    def atomic_read_bytes(self):
        """
        Atomic file read with minimal IO operation

        Returns:
            bytes: File content
        """
        return atomic_read_bytes(self)

    def atomic_read_bytes_stream(self, chunk_size=8192):
        """
        Read binary file content as stream

        Args:
            chunk_size (int): Size of chunks to read. Defaults to 8192.

        Returns:
            Iterable[bytes]: Generator yielding file content chunks
        """
        return atomic_read_bytes_stream(self, chunk_size=chunk_size)

    def file_remove(self):
        """
        Remove a file non-atomic

        Returns:
            bool: True if success
        """
        return file_remove(self)

    def atomic_remove(self):
        """
        Atomic file remove

        Returns:
            bool: True if success
        """
        return atomic_remove(self)

    def folder_rmtree(self, may_symlinks=True):
        """
        Recursively remove a folder and its content

        Args:
            may_symlinks (bool): Whether to handle symlinks. Defaults to True.
                False if you already know it's not a symlink

        Returns:
            bool: If success
        """
        return folder_rmtree(self, may_symlinks=may_symlinks)

    def atomic_rmtree(self):
        """
        Atomic folder rmtree
        Rename folder as temp folder and remove it,
        folder can be removed by atomic_failure_cleanup at next startup if remove gets interrupted

        Returns:
            bool: True if success
        """
        return atomic_rmtree(self)

    def is_empty_folder(self, ignore_pycache=False):
        """
        Args:
            ignore_pycache (bool): True to treat as empty folder if there's only one __pycache__
        Returns:
            bool: True if `root` is an empty folder
                False if `root` not exist, or is file, or having any error
        """
        return is_empty_folder(self, ignore_pycache=ignore_pycache)

    def folder_rmtree_empty(self):
        """
        Remove an empty folder.
        If folder is not empty, do nothing

        Returns:
            bool: True if success
        """
        return folder_rmtree_empty(self)

    def atomic_rmtree_empty(self):
        """
        Atomic remove an empty folder.
        If folder is not empty, do nothing.

        Returns:
            bool: If success
        """
        return atomic_rmtree_empty(self)

    def atomic_replace(self, path_to):
        """
        Replace file or directory

        Args:
            path_to (str): Target path

        Returns:
            PathStr: target PathStr

        Raises:
            PermissionError: (Windows only) If another process is still reading the file and all retries failed
            FileNotFoundError:
        """
        path_to = self.__class__.new(path_to)
        atomic_replace(self, path_to)
        return path_to

    def atomic_rename(self, path_to):
        """
        Rename file or directory

        Args:
            path_to (str): Target path

        Returns:
            PathStr: target PathStr

        Raises:
            PermissionError: (Windows only) If another process is still reading the file and all retries failed
            FileNotFoundError:
            FileExistError:
        """
        path_to = self.__class__.new(path_to)
        atomic_rename(self, path_to)
        return path_to

    def atomic_failure_cleanup(self, recursive=False):
        """
        Cleanup remaining temp file under given path.
        In most cases there should be no remaining temp files unless write process get interrupted.

        This method should only be called at startup
        to avoid deleting temp files that another process is writing.

        Args:
            recursive (bool): Whether to clean subdirectories. Defaults to False.

        Returns:
            PathStr: Self
        """
        atomic_failure_cleanup(self, recursive=recursive)
        return self

    """
    Iter folder
    """

    def iter_files(self, ext='', recursive=False, follow_symlinks=False):
        """
        Iter full filepath of files in folder with the good performance

        Args:
            ext (str): If ext is given, iter files with extension only.
                If ext is empty, iter all files. Defaults to ''.
            recursive (bool): True to recursively traverse subdirectories. Defaults to False.
            follow_symlinks (bool): True to follow symlinks. Defaults to False.

        Yields:
            PathStr: Full path
        """
        for path in iter_files(self, ext=ext, recursive=recursive, follow_symlinks=follow_symlinks):
            yield self.__class__(normpath(path))

    def iter_filenames(self, ext='', follow_symlinks=False):
        """
        Iter filename of files in folder with the good performance

        Args:
            ext (str): If ext is given, iter files with extension only.
                If ext is empty, iter all files. Defaults to ''.
            follow_symlinks (bool): True to follow symlinks. Defaults to False.

        Yields:
            str: Filename
        """
        yield from iter_filenames(self, ext=ext, follow_symlinks=follow_symlinks)

    def iter_folders(self, recursive=False, follow_symlinks=False):
        """
        Iter full filepath of directories in folder with the good performance

        Args:
            recursive (bool): True to recursively traverse subdirectories. Defaults to False.
            follow_symlinks (bool): True to follow symlinks. Defaults to False.

        Yields:
            PathStr: Full path
        """
        for path in iter_folders(self, recursive=recursive, follow_symlinks=follow_symlinks):
            yield self.__class__(normpath(path))

    def iter_foldernames(self, recursive=False, follow_symlinks=False):
        """
        Iter name of directories in folder with the good performance

        Args:
            recursive (bool): True to recursively traverse subdirectories. Defaults to False.
            follow_symlinks (bool): True to follow symlinks. Defaults to False.

        Yields:
            str: Folder name
        """
        yield from iter_foldernames(self, recursive=recursive, follow_symlinks=follow_symlinks)

    def iter_entry(self, recursive=False, follow_symlinks=False):
        """
        Iter DirEntry objects in folder with good performance

        This yields the actual DirEntry objects from os.scandir(), which can be
        more efficient than yielding paths since DirEntry caches filesystem info.
        You can then call entry.path, entry.name, entry.is_file(), entry.is_dir(),
        entry.stat(), etc. on the results without additional filesystem calls.

        Args:
            recursive (bool): True to recursively traverse subdirectories
            follow_symlinks (bool): True to follow symlinks

        Yields:
            os.DirEntry: Directory entry object with cached filesystem info
        """
        yield from iter_entry(self, recursive=recursive, follow_symlinks=follow_symlinks)

    """
    Wrap os module, imitating Pathlib
    """

    def exists(self):
        """
        Check if path exists

        Returns:
            bool: Whether path exists
        """
        return os.path.exists(self)

    def isfile(self):
        """
        Check if path is a file

        Returns:
            bool: Whether path is a file
        """
        return os.path.isfile(self)

    def isdir(self):
        """
        Check if path is a directory

        Returns:
            bool: Whether path is a directory
        """
        return os.path.isdir(self)

    def islink(self):
        """
        Check if path is a symbolic link

        Returns:
            bool: Whether path is a symbolic link
        """
        return os.path.islink(self)

    def stat(self, follow_symlinks=True):
        """
        Get file/directory stats

        Args:
            follow_symlinks (bool): Whether to follow symbolic links. Defaults to True.

        Returns:
            os.stat_result: File stats
        """
        return os.stat(self, follow_symlinks=follow_symlinks)

    def ensure_exist(self, mode=0o666, default=b''):
        """
        Ensure a file exists with minimal I/O operations using os.open.
        Uses O_EXCL flag to atomically check and create in one operation.

        Args:
            mode (int):
            default (bytes): Default content to write if file doesn't exist

        Returns:
            bool: True if file just created
        """
        return file_ensure_exist(self, mode=mode, default=default)

    def touch(self, mode=0o666, exist_ok=True):
        """
        Touch a file, copied from pathlib
        - If file not exist, create file
        - If file exist, set modify time to now

        Args:
            mode (int):
            exist_ok (bool):
        """
        file_touch(self, mode=mode, exist_ok=exist_ok)

    def makedirs(self, mode=0o777, exist_ok=True):
        """
        Create directories recursively

        Args:
            mode (int): Directory permissions. Defaults to 0o777.
            exist_ok (bool): Don't raise error if directory exists. Defaults to True.
        """
        os.makedirs(self, mode=mode, exist_ok=exist_ok)

    """
    Other
    """
