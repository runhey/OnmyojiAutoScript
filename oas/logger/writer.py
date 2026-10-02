import sys
from datetime import date
from typing import TYPE_CHECKING

from oas.ext import env
from oas.ext.cache import cached_property_threadsafe
from oas.ext.path import PathStr
from oas.ext.path.atomic import atomic_open
from oas.ext.singleton import Singleton

if TYPE_CHECKING:
    from oas.backend.worker.bridge import BackendBridge


# It's a singleton because on each logger.bind() structlog.PrintLoggerFactory will create new `file` object
# But we don't want to open multiple files
class LogWriter(metaclass=Singleton):
    def __init__(self):
        self.create_date: "date | None" = None
        # OAS has no Electron shell, so the "file only, no stdout" branch in
        # AlasioLogger._emit() never applies. Kept as an instance attribute so
        # a future desktop wrapper can flip it in one place.
        self.is_electron = False

    @cached_property_threadsafe
    def backend(self) -> "BackendBridge | PseudoBackendBridge":
        from oas.backend.worker.bridge import BackendBridge
        backend = BackendBridge()
        if backend.inited:
            return backend
        else:
            return PseudoBackendBridge()

    @cached_property_threadsafe
    def file(self):
        root = env.PROJECT_ROOT.abspath()
        folder = root / 'log'
        self.create_date = date.today()

        if self.backend.inited:
            name = self.backend.config_name
            # write logs to xxx/log/2020-01-01_{config_name}.txt
            return folder / f'{self.create_date}_{name}.txt'
        else:
            # xxx/path/module.py -> module
            name = PathStr.new(sys.argv[0]).rootstem
            # write logs to xxx/log/2020-01-01_{module_name}.txt
            return folder / f'{self.create_date}_{name}.txt'

    @cached_property_threadsafe
    def fd(self):
        file = self.file
        try:
            return atomic_open(file, mode='a', encoding='utf-8')
        except FileNotFoundError:
            file.uppath().makedirs(exist_ok=True)
            return atomic_open(file, mode='a', encoding='utf-8')

    @cached_property_threadsafe
    def stdout(self):
        return sys.stdout

    def check_rotate(self):
        # rotate log to file with new date
        if self.create_date and self.create_date != date.today():
            self.close()

    def close(self):
        cached_property_threadsafe.pop(self, 'backend')
        cached_property_threadsafe.pop(self, 'file')
        cached_property_threadsafe.pop(self, 'stdout')
        fd = cached_property_threadsafe.pop(self, 'fd')
        if fd is not None:
            try:
                fd.close()
            except Exception:
                pass

    def close_fd(self):
        """
        Close the cached log file fd, the next write reopens it.

        The log file fd is cached on the singleton. Environments that
        swap the filesystem (e.g. the in-memory fake filesystem used in
        tests) must drop the cached fd, or later real logs would keep
        writing into the swapped filesystem and get lost. Only the file
        path and fd caches are dropped, stdout and backend stay intact.
        """
        cached_property_threadsafe.pop(self, 'file', None)
        fd = cached_property_threadsafe.pop(self, 'fd', None)
        if fd is not None:
            try:
                fd.close()
            except Exception:
                pass

    def mute(self, stdout=False, fd=False, backend=False, all=False):
        """
        Mute logging outputs.

        Args:
            stdout (bool): Mute stdout. Defaults to False.
            fd (bool): Mute file writing. Defaults to False.
            backend (bool): Mute backend. Defaults to False.
            all (bool): Mute all outputs. Defaults to False.
        """
        if all:
            stdout = fd = backend = True
        if stdout:
            cached_property_threadsafe.set(self, 'stdout', PseudoStream())
        if fd:
            cached_property_threadsafe.set(self, 'fd', PseudoStream())
        if backend:
            cached_property_threadsafe.set(self, 'backend', PseudoBackendBridge())

    def mute_clear(self):
        """
        Clear all mutes.
        """
        cached_property_threadsafe.pop(self, 'stdout')
        cached_property_threadsafe.pop(self, 'fd')
        cached_property_threadsafe.pop(self, 'backend')

    def __del__(self):
        self.close()


class PseudoBackendBridge:
    inited = False
    config_name = "mock"

    def send_log(self, event):
        return CaptureJob()


class PseudoStream:
    def write(self, text):
        pass

    def flush(self):
        pass


class CaptureStream:
    def __init__(self, parent=None):
        """
        Args:
            parent (CaptureStream): Parent stream to also write to. Defaults to None.
        """
        self.logs: "list[str]" = []
        self.parent = parent

    def write(self, text):
        self.logs.append(text)
        if self.parent:
            self.parent.write(text)

    def flush(self):
        if self.parent:
            self.parent.flush()

    def any_contains(self, text):
        """
        Check if any log contains the given text

        Args:
            text (str): Text to search for

        Returns:
            bool: True if text is found in any log
        """
        for log in self.logs:
            if text in log:
                return True
        return False

    def any_regex(self, pattern):
        """
        Check if any log matches the given regex pattern

        Args:
            pattern (str): Regex pattern to search for

        Returns:
            bool: True if text is found in any log
        """
        import re
        for log in self.logs:
            if re.search(pattern, log):
                return True
        return False


class CaptureJob:
    def acquire(self):
        pass


class CaptureBackend:
    def __init__(self, parent=None):
        """
        Args:
            parent (CaptureBackend): Parent backend to also send to. Defaults to None.
        """
        self.logs: "list[dict]" = []
        self.inited = True
        self.config_name = "mock"
        self.parent = parent

    def send_log(self, event):
        self.logs.append(event)
        if self.parent:
            self.parent.send_log(event)
        return CaptureJob()

    def any_contains(self, text):
        """
        Check if any log entry (dict values) contains the given text

        Args:
            text (str): Text to search for

        Returns:
            bool: True if text is found in any log entry value
        """
        for log in self.logs:
            for value in log.values():
                if isinstance(value, str) and text in value:
                    return True
        return False

    def any_regex(self, pattern):
        """
        Check if any log entry (dict values) matches the given regex pattern

        Args:
            pattern (str): Regex pattern to search for

        Returns:
            bool: True if text is found in any log entry value
        """
        import re
        for log in self.logs:
            for value in log.values():
                if isinstance(value, str) and re.search(pattern, value):
                    return True
        return False


class CaptureWriter:
    def __init__(self, parent=None):
        """
        Args:
            parent (CaptureWriter | LogWriter | None): Parent writer to chain logs to. Defaults to None.
        """
        self.is_electron = False
        if isinstance(parent, CaptureWriter):
            self.stdout = CaptureStream(parent=parent.stdout)
            self.fd = CaptureStream(parent=parent.fd)
            self.backend = CaptureBackend(parent=parent.backend)
        else:
            self.stdout = CaptureStream()
            self.fd = CaptureStream()
            self.backend = CaptureBackend()

    def clear(self):
        self.stdout.logs.clear()
        self.fd.logs.clear()
        self.backend.logs.clear()

    def check_rotate(self):
        pass

    def close(self):
        pass