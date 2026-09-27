import os
import random
import string
import time

IS_WINDOWS = os.name == 'nt'
# Max attempt if another process is reading/writing, effective only on Windows
WINDOWS_MAX_ATTEMPT = 8
# Base time to wait between retries (seconds)
WINDOWS_RETRY_DELAY = 0.05
# Default chunk size to 256KB
CHUNK_SIZE = 262144


def random_id():
    """
    Returns:
        str: Random ID, like "sTD2kF"
    """
    # 6 random letter (62^6 combinations) would be enough
    return ''.join(random.sample(string.ascii_letters + string.digits, 6))


def is_tmp_file(file):
    """
    Check if a filename is tmp file

    Args:
        file (str): File name to check

    Returns:
        bool: True if file is a temporary file
    """
    # Check suffix first to reduce regex calls
    if not file.endswith('.tmp'):
        return False
    # Check temp file format
    dot = file[-11:-10]
    if not dot:
        return False
    rid = file[-10:-4]
    return rid.isalnum()


def to_tmp_file(file):
    """
    Convert a filename or directory name to tmp
    filename -> filename.sTD2kF.tmp

    Args:
        file (str): Original filename

    Returns:
        str: Temporary filename
    """
    suffix = random_id()
    return f'{file}.{suffix}.tmp'


def to_nontmp_file(file):
    """
    Convert a tmp filename or directory name to original file
    filename.sTD2kF.tmp -> filename

    Args:
        file (str): Temporary filename

    Returns:
        str: Original filename
    """
    if is_tmp_file(file):
        return file[:-11]
    else:
        return file


def windows_attempt_delay(attempt):
    """
    Exponential Backoff if file is in use on Windows

    Args:
        attempt (int): Current attempt, starting from 0

    Returns:
        float: Seconds to wait
    """
    # large attempt causes heavy power calculation
    if attempt > 10:
        attempt = 10
    if attempt < 0:
        attempt = 0
    delay = 2 ** attempt * WINDOWS_RETRY_DELAY
    # wait 1s at max
    if delay > 1:
        delay = 1
    return delay


def replace_tmp(tmp, file):
    """
    Replace temp file to file

    Args:
        tmp (str): Temporary file path
        file (str): Target file path

    Raises:
        PermissionError: (Windows only) If another process is still reading the file and all retries failed
        FileNotFoundError: If tmp file gets deleted unexpectedly
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is reading
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                # Atomic operation
                os.replace(tmp, file)
                # success
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
            except FileNotFoundError:
                # tmp file gets deleted unexpectedly
                raise
            except Exception as e:
                last_error = e
                break
    else:
        # Linux and Mac allow existing reading
        try:
            # Atomic operation
            os.replace(tmp, file)
            # success
            return
        except FileNotFoundError:
            raise
        except Exception as e:
            last_error = e

    # Clean up tmp file on failure
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        # tmp file already get deleted
        pass
    except Exception:
        pass
    if last_error is not None:
        raise last_error from None


def atomic_replace(path_from, path_to):
    """
    Replace file or directory

    Args:
        path_from (str): Source file/directory path
        path_to (str): Target file/directory path

    Raises:
        PermissionError: (Windows only) If another process is still reading the file and all retries failed
        FileNotFoundError:
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is reading
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                # Atomic operation
                os.replace(path_from, path_to)
                # success
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
            except FileNotFoundError:
                raise
            except Exception as e:
                last_error = e
                break
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac
        os.replace(path_from, path_to)


def atomic_rename(path_from, path_to):
    """
    Replace file or directory

    Args:
        path_from (str): Source file/directory path
        path_to (str): Target file/directory path

    Raises:
        PermissionError: (Windows only) If another process is still reading the file and all retries failed
        FileNotFoundError:
        FileExistError:
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is reading
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                # Atomic operation
                os.rename(path_from, path_to)
                # success
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
            except (FileNotFoundError, FileExistsError):
                raise
            except Exception as e:
                last_error = e
                break
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac
        os.rename(path_from, path_to)


def file_write(file, data):
    """
    Write data into file, auto create directory
    Auto determines write mode based on the type of data.

    Args:
        file (str): Target file path
        data (Union[str, bytes]): Data to write
    """
    if isinstance(data, str):
        mode = 'w'
        encoding = 'utf-8'
        newline = ''
    elif isinstance(data, bytes):
        mode = 'wb'
        encoding = None
        newline = None
        # Create memoryview as Pathlib do
        data = memoryview(data)
    elif isinstance(data, (bytearray, memoryview)):
        mode = 'wb'
        encoding = None
        newline = None
    else:
        typename = str(type(data))
        if typename == "<class 'numpy.ndarray'>":
            mode = 'wb'
            encoding = None
            newline = None
        else:
            mode = 'w'
            encoding = 'utf-8'
            newline = ''

    try:
        # Write temp file
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(data)
            # Ensure data flush to disk
            f.flush()
            os.fsync(f.fileno())
        return
    except FileNotFoundError:
        pass
    # Create parent directory
    directory = os.path.dirname(file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write again
    with open(file, mode=mode, encoding=encoding, newline=newline) as f:
        f.write(data)
        # Ensure data flush to disk
        f.flush()
        os.fsync(f.fileno())


def file_write_stream(file, data_generator):
    """
    Only creates a file if the generator yields at least one data chunk.
    Auto determines write mode based on the type of first chunk.

    Args:
        file (str): Target file path
        data_generator (Iterable): An iterable that yields data chunks (str or bytes)
    """
    # Convert generator to iterator to ensure we can peek at first chunk
    data_iter = iter(data_generator)

    # Try to get the first chunk
    try:
        first_chunk = next(data_iter)
    except StopIteration:
        # Generator is empty, no file will be created
        return

    # Determine mode, encoding and newline from first chunk
    if isinstance(first_chunk, str):
        mode = 'w'
        encoding = 'utf-8'
        newline = ''
    elif isinstance(first_chunk, (bytes, bytearray, memoryview)):
        mode = 'wb'
        encoding = None
        newline = None
    else:
        # Default to text mode for other types
        mode = 'w'
        encoding = 'utf-8'
        newline = ''

    try:
        # Write temp file
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(first_chunk)
            for chunk in data_iter:
                f.write(chunk)
            # Ensure data flush to disk
            f.flush()
            os.fsync(f.fileno())
        return
    except FileNotFoundError:
        pass
    # Create parent directory
    directory = os.path.dirname(file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write again
    with open(file, mode=mode, encoding=encoding, newline=newline) as f:
        f.write(first_chunk)
        for chunk in data_iter:
            f.write(chunk)
        # Ensure data flush to disk
        f.flush()
        os.fsync(f.fileno())


async def afile_write_stream(file, data_iter):
    """
    Only creates a file if the generator yields at least one data chunk.
    Auto determines write mode based on the type of first chunk.

    Args:
        file (str): Target file path
        data_iter (Iterable): An iterable that yields data chunks (str or bytes)
    """
    # Try to get the first chunk
    try:
        first_chunk = await data_iter.__anext__()
    except StopAsyncIteration:
        # Generator is empty, no file will be created
        return

    # Determine mode, encoding and newline from first chunk
    if isinstance(first_chunk, str):
        mode = 'w'
        encoding = 'utf-8'
        newline = ''
    elif isinstance(first_chunk, bytes):
        mode = 'wb'
        encoding = None
        newline = None
    else:
        # Default to text mode for other types
        mode = 'w'
        encoding = 'utf-8'
        newline = ''

    try:
        # Write temp file
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(first_chunk)
            async for chunk in data_iter:
                f.write(chunk)
            # Ensure data flush to disk
            f.flush()
            os.fsync(f.fileno())
        return
    except FileNotFoundError:
        pass
    # Create parent directory
    directory = os.path.dirname(file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write again
    with open(file, mode=mode, encoding=encoding, newline=newline) as f:
        f.write(first_chunk)
        async for chunk in data_iter:
            f.write(chunk)
        # Ensure data flush to disk
        f.flush()
        os.fsync(f.fileno())


def atomic_write(file, data):
    """
    Atomic file write with minimal IO operation
    and handles cases where file might be read by another process.

    os.replace() is an atomic operation among all OS,
    we write to temp file then do os.replace()

    Args:
        file (str): Target file path
        data (Union[str, bytes]): Data to write
    """
    tmp = to_tmp_file(file)
    file_write(tmp, data)
    replace_tmp(tmp, file)


def atomic_write_stream(file, data_generator):
    """
    Atomic file write with streaming data support.
    Handles cases where file might be read by another process.

    os.replace() is an atomic operation among all OS,
    we write to temp file then do os.replace()

    Args:
        file (str): Target file path
        data_generator (Iterable): An iterable that yields data chunks (str or bytes)
    """
    tmp = to_tmp_file(file)
    file_write_stream(tmp, data_generator)
    replace_tmp(tmp, file)


def file_read_text(file, encoding='utf-8', errors='strict'):
    """
    Read text file content

    Args:
        file (str): Source file path
        encoding (str): Text encoding. Defaults to 'utf-8'.
        errors (str): Error handling strategy. Defaults to 'strict'.
            'strict', 'ignore', 'replace' and any other errors mode in open()

    Returns:
        str: File content
    """
    with open(file, mode='r', encoding=encoding, errors=errors) as f:
        return f.read()


def file_read_text_stream(file, encoding='utf-8', errors='strict', chunk_size=CHUNK_SIZE):
    """
    Read text file content as stream

    Args:
        file (str): Source file path
        encoding (str): Text encoding. Defaults to 'utf-8'.
        errors (str): Error handling strategy. Defaults to 'strict'.
            'strict', 'ignore', 'replace' and any other errors mode in open()
        chunk_size (int): Size of chunks to read. Defaults to 256KB.

    Yields:
        str: Generator yielding file content chunks
    """
    with open(file, mode='r', encoding=encoding, errors=errors) as f:
        while 1:
            chunk = f.read(chunk_size)
            if not chunk:
                return
            yield chunk


def file_read_bytes(file):
    """
    Read binary file content

    Args:
        file (str): Source file path

    Returns:
        bytes: File content
    """
    # No python-side buffering when reading the entire file to speedup reading
    # https://github.com/python/cpython/pull/122111
    with open(file, mode='rb', buffering=0) as f:
        return f.read()


def file_read_bytes_stream(file, chunk_size=CHUNK_SIZE):
    """
    Read binary file content as stream

    Args:
        file (str): Source file path
        chunk_size (int): Size of chunks to read. Defaults to 256KB.

    Yields:
        bytes: Generator yielding file content chunks
    """
    with open(file, mode='rb') as f:
        while 1:
            chunk = f.read(chunk_size)
            if not chunk:
                return
            yield chunk


def file_read_bytes_into(file, buffer):
    """
    Read binary file content into memoryview(bytearray())

    Args:
        file (str): Source file path
        buffer (memoryview | bytearray):

    Yields:
        int: Length read
    """
    with open(file, mode='rb') as f:
        while 1:
            n = f.readinto(buffer)
            if not n:
                return
            yield n


def atomic_read_text(file, encoding='utf-8', errors='strict'):
    """
    Atomic file read with minimal IO operation

    Args:
        file (str): Source file path
        encoding (str): Text encoding. Defaults to 'utf-8'.
        errors (str): Error handling strategy. Defaults to 'strict'.
            'strict', 'ignore', 'replace' and any other errors mode in open()

    Returns:
        str: File content
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return file_read_text(file, encoding=encoding, errors=errors)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        return file_read_text(file, encoding=encoding, errors=errors)


def atomic_read_text_stream(file, encoding='utf-8', errors='strict', chunk_size=CHUNK_SIZE):
    """
    Atomic file read with streaming support

    Args:
        file (str): Source file path
        encoding (str): Text encoding. Defaults to 'utf-8'.
        errors (str): Error handling strategy. Defaults to 'strict'.
            'strict', 'ignore', 'replace' and any other errors mode in open()
        chunk_size (int): Size of chunks to read. Defaults to 256KB.

    Yields:
        str: Generator yielding file content chunks
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                yield from file_read_text_stream(file, encoding=encoding, errors=errors, chunk_size=chunk_size)
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        yield from file_read_text_stream(file, encoding=encoding, errors=errors, chunk_size=chunk_size)
        return


def atomic_read_bytes(file):
    """
    Atomic file read with minimal IO operation

    Args:
        file (str): Source file path

    Returns:
        bytes: File content
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return file_read_bytes(file)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        return file_read_bytes(file)


def atomic_read_bytes_stream(file, chunk_size=CHUNK_SIZE):
    """
    Atomic file read with streaming support

    Args:
        file (str): Source file path
        chunk_size (int): Size of chunks to read. Defaults to 256KB.

    Yields:
        bytes: Generator yielding file content chunks
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                yield from file_read_bytes_stream(file, chunk_size=chunk_size)
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        yield from file_read_bytes_stream(file, chunk_size=chunk_size)
        return


def atomic_read_bytes_into(file, buffer):
    """
    Read binary file content into memoryview(bytearray())

    Args:
        file (str): Source file path
        buffer (memoryview | bytearray):

    Yields:
        int: Length read
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                yield from file_read_bytes_into(file, buffer)
                return
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        yield from file_read_bytes_into(file, buffer)
        return


def atomic_open(file, mode='r', encoding=None, **kwargs):
    """
    Open a file atomically with retry on PermissionError (Windows only).

    Unlike atomic_write, this returns an open file handle rather than
    writing data atomically. The PermissionError retry handles cases
    where the file is temporarily locked by another process.

    Args:
        file (str): Target file path
        mode (str): File open mode. Defaults to 'r'.
        encoding (str): Text encoding. Defaults to None.
        **kwargs: Additional arguments passed to open()

    Returns:
        file object: Opened file handle

    Examples:
        # Append-mode log file
        with atomic_open('log.txt', mode='a', encoding='utf-8') as f:
            f.write('hello\\n')

        # Read-mode with error handling
        f = atomic_open('config.json', mode='r', encoding='utf-8')
        data = f.read()
        f.close()
    """
    if IS_WINDOWS:
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return open(file, mode=mode, encoding=encoding, **kwargs)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        return open(file, mode=mode, encoding=encoding, **kwargs)


def _copy_iter(source, buffer, chunk_size):
    """
    Args:
        source (str): Source file path
        buffer (memoryview | bytearray):

    Yields:
        buffer
    """
    for n in atomic_read_bytes_into(source, buffer):
        if not n:
            return
        elif n < chunk_size:
            yield buffer[:n]
        else:
            yield buffer


def file_copy(source, target, chunk_size=CHUNK_SIZE):
    """
    Copy file with memory reuse

    Args:
        source (str):
        target (str):
        chunk_size (int):
    """
    buffer = memoryview(bytearray(chunk_size))
    stream = _copy_iter(source, buffer, chunk_size)
    file_write_stream(target, stream)


def atomic_copy(source, target, chunk_size=CHUNK_SIZE):
    """
    Atomic file write with minimal IO operation and memory usage

    Args:
        source (str):
        target (str):
        chunk_size (int):
    """
    tmp = to_tmp_file(source)
    file_copy(source, tmp, chunk_size=chunk_size)
    replace_tmp(tmp, target)


def file_ensure_exist(file, mode=0o666, default=b''):
    """
    Ensure a file exists with minimal I/O operations using os.open.
    Uses O_EXCL flag to atomically check and create in one operation.

    Args:
        file (str):
        mode (int):
        default (bytes): Default content to write if file doesn't exist

    Returns:
        bool: True if file just created
    """
    try:
        # Try to create file with O_EXCL flag - will fail if file exists
        # O_CREAT | O_EXCL | O_WRONLY ensures atomic "create if not exists" operation
        fd = os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)

        # If we get here, the file was created successfully
        if default:
            os.write(fd, default)
        os.close(fd)
        return True
    except FileExistsError:
        # File already exists
        return False
    except OSError:
        # Other errors
        return False


def file_touch(file, mode=0o666, exist_ok=True):
    """
    Touch a file, copied from pathlib
    - If file not exist, create file
    - If file exist, set modify time to now

    Args:
        file (str):
        mode (int):
        exist_ok (bool):
    """
    if exist_ok:
        # First try to bump modification time
        # Implementation note: GNU touch uses the UTIME_NOW option of
        # the utimensat() / futimens() functions.
        try:
            os.utime(file, None)
        except OSError:
            # Avoid exception chaining
            pass
        else:
            return
    flags = os.O_CREAT | os.O_WRONLY
    if not exist_ok:
        flags |= os.O_EXCL
    fd = os.open(file, flags, mode)
    os.close(fd)


def file_remove(file):
    """
    Remove a file non-atomic

    Args:
        file (str): File path to remove

    Returns:
        bool: If removed
    """
    try:
        os.unlink(file)
        return True
    except FileNotFoundError:
        # If file not exist, just no need to remove
        return False


def atomic_remove(file):
    """
    Atomic file remove

    Args:
        file (str): File path to remove

    Returns:
        bool: If success
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return file_remove(file)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow deleting while another process is reading
        # The directory entry is removed but the storage allocated to the file is not made available
        # until the original file is no longer in use.
        return file_remove(file)


def folder_rmtree(folder, may_symlinks=True):
    """
    Recursively remove a folder and its content

    Args:
        folder (str): Folder path to remove
        may_symlinks (bool): Whether to handle symlinks. Defaults to True.
            False if you already know it's not a symlink

    Returns:
        bool: If removed
    """
    try:
        # If it's a symlinks, unlink it
        if may_symlinks and os.path.islink(folder):
            return file_remove(folder)
        # Iter folder
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    folder_rmtree(entry.path, may_symlinks=False)
                else:
                    # File or symlink
                    # Just remove the symlink, not what it points to
                    try:
                        file_remove(entry.path)
                    except PermissionError:
                        # Another process is reading/writing
                        pass

    except FileNotFoundError:
        # directory to clean up does not exist, no need to clean up
        return False
    except NotADirectoryError:
        return file_remove(folder)

    # Remove empty folder
    # May raise OSError if it's still not empty
    try:
        os.rmdir(folder)
        return True
    except FileNotFoundError:
        return False
    except NotADirectoryError:
        return file_remove(folder)
    except OSError:
        return False


def atomic_rmtree(folder):
    """
    Atomic folder rmtree
    Rename folder as temp folder and remove it,
    folder can be removed by atomic_failure_cleanup at next startup if remove gets interrupted

    Args:
        folder (str): Folder path to remove

    Returns:
        bool: If success
    """
    tmp = to_tmp_file(folder)
    try:
        atomic_replace(folder, tmp)
    except FileNotFoundError:
        # Folder not exist, no need to rmtree
        return False
    return folder_rmtree(tmp)


def is_empty_folder(folder, ignore_pycache=False):
    """
    Args:
        folder (str):
        ignore_pycache (bool): True to treat as empty folder if there's only one __pycache__

    Returns:
        bool: True if `root` is an empty folder
            False if `root` not exist, or is file, or having any error
    """
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if ignore_pycache:
                    if entry.name == '__pycache__':
                        continue
                    else:
                        # having any non-pycache
                        return False
                else:
                    # having any entry
                    return False
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False


def folder_rmtree_empty(folder):
    """
    Remove an empty folder.
    If folder is not empty, do nothing

    Args:
        folder (str): Folder path to remove

    Returns:
        bool: True if success
    """
    try:
        os.rmdir(folder)
        return True
    except FileNotFoundError:
        return False
    except NotADirectoryError:
        return False
    except OSError:
        return False


def atomic_rmtree_empty(folder):
    """
    Atomic remove an empty folder.
    If folder is not empty, do nothing.

    Args:
        folder (str): Folder path to remove

    Returns:
        bool: If success
    """
    tmp = to_tmp_file(folder)
    try:
        atomic_replace(folder, tmp)
    except FileNotFoundError:
        # Folder not exist, no need to rmtree
        return False
    return folder_rmtree_empty(tmp)


def atomic_failure_cleanup(folder, recursive=False):
    """
    Cleanup remaining temp file under given path.
    In most cases there should be no remaining temp files unless write process get interrupted.

    This method should only be called at startup
    to avoid deleting temp files that another process is writing.

    Args:
        folder (str): Folder path to clean
        recursive (bool): Whether to clean subdirectories. Defaults to False.
    """
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if is_tmp_file(entry.name):
                    try:
                        # Delete temp file or directory
                        if entry.is_dir(follow_symlinks=False):
                            folder_rmtree(entry.path, may_symlinks=False)
                        else:
                            file_remove(entry.path)
                    except PermissionError:
                        # Another process is reading/writing
                        pass
                    except Exception:
                        pass
                else:
                    if recursive:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                # Normal directory
                                atomic_failure_cleanup(entry.path, recursive=True)
                        except PermissionError:
                            # Another process is reading/writing
                            pass
                        except Exception:
                            pass

    except FileNotFoundError:
        # directory to clean up does not exist, no need to clean up
        pass
    except NotADirectoryError:
        file_remove(folder)
    except Exception:
        # Ignore all failures, it doesn't matter if tmp files still exist
        pass
