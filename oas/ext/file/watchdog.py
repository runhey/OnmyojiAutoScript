import os
import stat
import time
from collections import deque
from dataclasses import dataclass

from oas.ext.path.calc import normpath


def stat_info(st):
    """
    Get path information using single os.stat call.

    Args:
        st (os.stat): Path stat to check

    Returns:
        Tuple[str, float]: path_type, mtime
            `path_type` is one of: F for file, D for directory, S for symlink

    Raises:
        FileNotFoundError:
    """
    mode = st.st_mode
    if stat.S_ISREG(mode):
        # File
        path_type = 'F'
    elif stat.S_ISDIR(mode):
        # Directory
        path_type = 'D'
    elif stat.S_ISLNK(mode):
        # Symlink
        path_type = 'S'
    else:
        # This should not happen
        raise OSError
    return path_type, st.st_mtime


@dataclass
class PathEvent:
    # `event` is one of: A for added, M for modified, D for deleted.
    event: str
    # Absolute path of the changed file
    path: str
    # `type` is one of: F for file, D for directory, S for symlink
    type: str
    # last modify time
    mtime: float


class Watchdog:
    def __init__(self, paths):
        """
        Initialize the file monitor with paths to watch.

        Args:
            paths (list[str] | str): Absolute path or a list of item
        """
        if isinstance(paths, list):
            self.paths = [normpath(p) for p in paths]
        else:
            self.paths = [normpath(paths)]
        self.info_dict = {}

        self._last_snapshot = 0
        self._first_snapshot = True

    def watch(self, include_existing=False, interval=2):
        """
        Args:
            include_existing (bool): True to return all existing files first
            interval: Interval in seconds between two _watch calls

        Returns:
            list[PathEvent]:

        Examples:
            self = Watchdog(r'E:\ProgramData\Pycharm\AzurLaneAutoScript')
            while 1:
                for row in self.watch(interval=2):
                    print(row)
            # PathEvent('M', 'E:\\ProgramData\\Pycharm\\AzurLaneAutoScript\\config', 'D', 1746358905.0225341)
            # PathEvent('M', 'E:\\ProgramData\\Pycharm\\AzurLaneAutoScript\\config\\alas.json', 'F', 1746358905.0210333)
        """
        if interval > 0:
            now = time.time()
            diff = now - self._last_snapshot
            if 0 <= diff <= interval:
                time.sleep(interval - diff)
            self._last_snapshot = time.time()

        result = list(self._watch())

        if self._first_snapshot:
            self._first_snapshot = False
            if include_existing:
                return result
            else:
                return []
        else:
            return result

    def watch_files(self, include_existing=False, interval=2):
        """
        Same as watch() but returns file changes only

        Returns:
            list[PathEvent]:
        """
        events = self.watch(include_existing=include_existing, interval=interval)
        events = [e for e in events if e.type == 'F']
        return events

    def _watch(self):
        """
        Yields:
            FileEvent:
        """
        info_dict = self.info_dict
        new_dict = {}
        need_visit = deque()

        for path in self.paths:
            try:
                info = stat_info(os.stat(path))
                info_type, info_mtime = info
            except OSError:
                prev_info = info_dict.pop(path, None)
                if prev_info is None:
                    # path never exists
                    continue
                else:
                    # path deleted
                    yield PathEvent('D', path, prev_info[0], prev_info[1])
                    continue
            try:
                prev_type, prev_mtime = info_dict.pop(path)
            except KeyError:
                # new path
                yield PathEvent('A', path, info_type, info_mtime)
                new_dict[path] = info
                if info_type == 'D':
                    # new directory
                    need_visit.append(path)
                continue
            new_dict[path] = info
            # Always scan directories recursively
            # because directory mtime don't get update when sub files changed
            if info_type == 'D':
                need_visit.append(path)
            if info_type == prev_type:
                if info_mtime > prev_mtime:
                    # modified
                    yield PathEvent('M', path, info_type, info_mtime)
                else:
                    # same
                    pass
            else:
                # file changed to directory or viceversa
                yield PathEvent('M', path, info_type, info_mtime)

        while True:
            new_visit = deque()
            for path in need_visit:
                try:
                    list_entry = list(os.scandir(path))
                except OSError:
                    # directory got deleted just now
                    prev_info = info_dict.pop(path, None)
                    if prev_info is None:
                        # path never exists
                        continue
                    else:
                        # path deleted
                        yield PathEvent('D', path, prev_info[0], prev_info[1])
                        continue
                for entry in list_entry:
                    entry_path = normpath(entry.path)
                    try:
                        entry_info = stat_info(entry.stat(follow_symlinks=True))
                        info_type, info_mtime = entry_info
                    except OSError:
                        # entry got deleted just now
                        prev_info = info_dict.pop(entry_path, None)
                        if prev_info is None:
                            # path never exists
                            continue
                        else:
                            # path deleted
                            yield PathEvent('D', entry_path, prev_info[0], prev_info[1])
                            continue
                    try:
                        prev_type, prev_mtime = info_dict.pop(entry_path)
                    except KeyError:
                        # new sub path
                        yield PathEvent('A', entry_path, info_type, info_mtime)
                        new_dict[entry_path] = entry_info
                        if info_type == 'D':
                            # new sub directory
                            new_visit.append(entry_path)
                        continue
                    new_dict[entry_path] = entry_info
                    # Always scan directories recursively
                    # because directory mtime don't get update when sub files changed
                    if entry_info[0] == 'D':
                        new_visit.append(entry_path)
                    if info_type == prev_type:
                        if info_mtime > prev_mtime:
                            # modified
                            yield PathEvent('M', entry_path, info_type, info_mtime)
                        else:
                            # same
                            pass
                    else:
                        # file changed to directory or viceversa
                        yield PathEvent('M', entry_path, info_type, info_mtime)
            # End
            need_visit = new_visit
            if not need_visit:
                break
        # path not visited, probably because they are deleted
        for path, info in info_dict.items():
            yield PathEvent('D', path, info[0], info[1])
        # swap dict
        self.info_dict = new_dict

    def mark_modified(self, path, path_type=None, path_mtime=None):
        """
        Mark a path that has been modified by us, not by external changes
        Useful to reduce duplicate modify event when we modified a file programmatically

        Args:
            path (PathEvent | str): change event or absolute filepath
            path_type (str):
                F for file, D for directory, S for symlink
                None to keep current path_type unchanged
            path_mtime (float):
                Modify time of path, None for current time
        """
        if type(path) is PathEvent:
            path = path.path

        info_dict = self.info_dict
        try:
            prev_type, prev_mtime = info_dict[path]
        except KeyError:
            # path not recorded
            try:
                info = stat_info(os.stat(path))
            except OSError:
                # path to mark modified doesn't even exist
                return
            # newly created path
            info_dict[path] = info
            return

        # having previous record
        if path_mtime is None:
            path_mtime = time.time()
        if path_type is None:
            info = (prev_type, path_mtime)
        else:
            info = (prev_type, prev_mtime)
        info_dict[path] = info
