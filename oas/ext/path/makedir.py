import os
import stat

from .calc import is_abspath, joinpath, normpath


def _convert_path(filepaths):
    """
    Convert relative filepaths to absolute normalized paths

    Args:
        filepaths (list[str]): List of filepaths

    Yields:
        str: Absolute normalized filepath
    """
    root = normpath(os.getcwd())
    for filepath in filepaths:
        filepath = normpath(filepath)
        if is_abspath(filepath):
            yield filepath
        else:
            yield joinpath(root, filepath)


def _iter_parent_folder(filepath):
    """
    Iter parent folders of a normalized filepath, from deep to shallow.
    C:/folder/file
        - C:/folder
        - C: (same as C:/)

    Args:
        filepath (str): Normalized filepath

    Yields:
        str: Parent folder, from deep to shallow
    """
    folder, sep, _ = filepath.rpartition('/')
    while sep and folder:
        yield folder
        folder, sep, _ = folder.rpartition('/')


def _get_parent_folder(filepaths):
    """
    Get parent folders of filepaths, with all ancestors, deduplicated,
    sorted from shallow to deep.
    If a folder was already added, all of its ancestors were added as well,
    so the remaining ancestors of this filepath can be skipped

    Args:
        filepaths (list[str]): List of filepaths

    Returns:
        list[str]: Deduplicated parent folders, sorted from shallow to deep
    """
    folders = set()
    for filepath in filepaths:
        for folder in _iter_parent_folder(filepath):
            if folder in folders:
                # All of its ancestors are already added
                break
            folders.add(folder)
    return sorted(folders, key=lambda folder: folder.count('/'))


def batch_makedirs(filepaths):
    """
    Create parent folders for all filepaths with minimal IO operations.
    Reference os.makedirs(), but check folders from shallow to deep with
    deduplication, instead of calling os.makedirs() in a loop.
    Filepaths are converted to absolute normalized paths first,
    folders are always created on absolute paths.
    If a file is in the way of a folder, the file is removed first

    Args:
        filepaths (list[str]): List of filepaths

    Raises:
        OSError: If a folder cannot be created, such as permission denied,
            or a file exists at the folder path
    """
    filepaths = _convert_path(filepaths)
    folders = _get_parent_folder(filepaths)
    for folder in folders:
        try:
            # One call to check whether the path is a file or a folder
            st = os.stat(folder)
        except FileNotFoundError:
            # Folder doesn't exist, create it
            try:
                os.mkdir(folder)
            except FileExistsError:
                # Another process created the folder in between
                pass
        else:
            if stat.S_ISDIR(st.st_mode):
                # Folder already exists
                continue
            if stat.S_ISREG(st.st_mode):
                # A file is in the way, remove it and create the folder
                try:
                    os.unlink(folder)
                except FileNotFoundError:
                    # Another process removed the file in between
                    pass
                try:
                    os.mkdir(folder)
                except FileExistsError:
                    # Another process created the folder in between
                    pass
