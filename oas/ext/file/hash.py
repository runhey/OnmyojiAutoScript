import hashlib
import time

from oas.ext.path.atomic import IS_WINDOWS, WINDOWS_MAX_ATTEMPT, windows_attempt_delay


def _get_md5(file, chunk_size=262144):
    """
    Directly get md5 of a file, and be fast
    If filesize <= chunk_size, read and calculate directly
    If filesize > chunk_size, create buffer to reuse memory

    Args:
        file (str):
        chunk_size (int): Default to 256KB

    Returns:
        str:
    """
    with open(file, mode='rb', buffering=0) as f:
        head = f.read(chunk_size)
        # File smaller than chunk_size
        if len(head) < chunk_size:
            return hashlib.md5(head).hexdigest()
        # Big file
        digest = hashlib.md5(head)
        buffer = bytearray(chunk_size)
        while 1:
            length = f.readinto(buffer)
            if length == chunk_size:
                digest.update(buffer)
            elif length:
                digest.update(buffer[:length])
            else:
                break
    return digest.hexdigest()


def file_md5(file, chunk_size=262144):
    """
    Get md5 of a file, be fast and handle locked files on Windows

    Args:
        file (str):
        chunk_size (int): Default to 256KB

    Returns:
        str:
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return _get_md5(file, chunk_size)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        return _get_md5(file, chunk_size)


def _get_sha1(file, chunk_size=262144):
    """
    Directly get sha1 of a file, and be fast
    If filesize <= chunk_size, read and calculate directly
    If filesize > chunk_size, create buffer to reuse memory

    Args:
        file (str):
        chunk_size (int): Default to 256KB

    Returns:
        str:
    """
    with open(file, mode='rb', buffering=0) as f:
        head = f.read(chunk_size)
        # File smaller than chunk_size
        if len(head) < chunk_size:
            return hashlib.sha1(head).hexdigest()
        # Big file
        digest = hashlib.sha1(head)
        buffer = bytearray(chunk_size)
        while 1:
            length = f.readinto(buffer)
            if length == chunk_size:
                digest.update(buffer)
            elif length:
                digest.update(buffer[:length])
            else:
                break
    return digest.hexdigest()


def file_sha1(file, chunk_size=262144):
    """
    Get sha1 of a file, be fast and handle locked files on Windows

    Args:
        file (str):
        chunk_size (int): Default to 256KB

    Returns:
        str:
    """
    if IS_WINDOWS:
        # PermissionError on Windows if another process is replacing
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return _get_sha1(file, chunk_size)
            except PermissionError as e:
                last_error = e
                delay = windows_attempt_delay(attempt)
                time.sleep(delay)
                continue
        if last_error is not None:
            raise last_error from None
    else:
        # Linux and Mac allow reading while replacing
        return _get_sha1(file, chunk_size)
