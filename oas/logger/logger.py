import threading
import time
from datetime import datetime
from io import StringIO

from oas.backport import str_center
from oas.backport.patch import patch_startup
from oas.backport.rich import patch_rich_traceback_links
from oas.logger.utils import (
    empty_function, event_args_format, event_format, figure_out_exc_info, join_event_dict, replace_unicode_table,
    stringify_event
)
from oas.logger.writer import CaptureWriter, LogWriter

patch_startup()
# patch_rich_traceback_extract() is not ported: it only applies to
# python<3.11 with rich<14.3 exceptiongroup, and OAS runs on 3.14.
patch_rich_traceback_links()


def rich_formatter(exc_info):
    """
    Args:
        exc_info (tuple): Exception info

    Returns:
        tuple[str, str]: exception_rich, exception_plain
    """
    # wrap structlog.dev.RichTracebackFormatter().__call__() as an input to ExceptionRenderer
    from rich.console import Console
    from rich.traceback import Traceback

    tb = Traceback.from_exception(
        # see structlog.dev.RichTracebackFormatter()
        *exc_info, show_locals=True, word_wrap=True, max_frames=100,
    )
    if hasattr(tb, "code_width"):
        # `code_width` requires `rich>=13.8.0`
        tb.code_width = 120

    # Rich (for terminal)
    sio_rich = StringIO()
    console_rich = Console(
        file=sio_rich, color_system='auto', force_terminal=True, width=120, legacy_windows=False
    )
    console_rich.print(tb)
    exception_rich = sio_rich.getvalue()

    # Plain (for file)
    sio_plain = StringIO()
    console_plain = Console(
        file=sio_plain, color_system=None, width=120
    )
    console_plain.print(tb)
    exception_plain = sio_plain.getvalue()
    exception_plain = replace_unicode_table(exception_plain)

    return exception_rich, exception_plain


LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
}

LEVEL_METHODS = {
    'debug': 10,
    'info': 20,
    'raw': 20,
    'hr': 20,
    'hr0': 20,
    'hr1': 20,
    'hr2': 20,
    'hr3': 20,
    'attr': 20,
    'attr_align': 20,
    'warning': 30,
    'error': 40,
    'exception': 40,
    'critical': 50,
}


class LoggingLevel:
    def __init__(self):
        self._level = 20

    def set_level(self, level=20):
        """
        Set logging level.
        Methods below this level will be replaced with empty_function.

        Args:
            level (str | int): Level name or value. Defaults to 20 (INFO).

        Returns:
            Self:
        """
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.upper(), level)
        if isinstance(level, str):
            # level is still str, maybe invalid level name
            level = 20

        self._level = level
        for method_name, method_level in LEVEL_METHODS.items():
            if method_level < level:
                setattr(self, method_name, empty_function)
            else:
                # Restore original method from class if it was overridden
                if method_name in self.__dict__:
                    try:
                        delattr(self, method_name)
                    except AttributeError:
                        pass
        return self


class CaptureWriterContext:
    def __init__(self, log):
        """
        Args:
            log (AlasioLogger): Logger instance
        """
        self.logger = log
        self.writer = None
        self.old_writer = None

    def __enter__(self):
        self.old_writer = self.logger._writer
        self.writer = CaptureWriter(parent=self.old_writer)
        self.logger._writer = self.writer
        return self.writer

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger._writer = self.old_writer


class ClassicLogger(LoggingLevel):
    def __init__(self, parent):
        """
        Args:
            parent (AlasioLogger): AlasioLogger instance
        """
        super().__init__()
        self._logger = parent
        self.set_level(logger._level)

    def debug(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.debug(event, **kwargs)

    def info(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.info(event, **kwargs)

    def warning(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.warning(event, **kwargs)

    def error(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.error(event, **kwargs)

    def exception(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.exception(event, **kwargs)

    def critical(self, event, *args, **kwargs):
        if args:
            event = event_args_format(event, args)
        self._logger.critical(event, **kwargs)


class AlasioLogger(LoggingLevel):
    # global logging lock
    _lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self._context = {}
        self._writer = LogWriter()
        self.set_level(self._level)

    def mock_capture_writer(self):
        """
        Mock writer for testing purpose

        Examples:
            with logger.mock_capture_writer() as capture:
                logger.info("Hello Info")
                assert capture.fd.any_contains("Hello Info")
                assert capture.stdout.any_contains("Hello Info")
                assert any(log['l'] == 'INFO' and log['m'] == 'Hello Info' for log in capture.backend.logs)
                capture.clear()
        """
        return CaptureWriterContext(self)

    def mute(self, stdout=False, fd=False, backend=False, all=False):
        """
        Mute logging outputs.

        Args:
            stdout (bool): Mute stdout. Defaults to False.
            fd (bool): Mute file writing. Defaults to False.
            backend (bool): Mute backend. Defaults to False.
            all (bool): Mute all outputs. Defaults to False.
        """
        self._writer.mute(stdout=stdout, fd=fd, backend=backend, all=all)

    def mute_clear(self):
        """
        Clear all mutes.
        """
        self._writer.mute_clear()

    def check_rotate(self):
        """
        rotate log to file with new date
        """
        with self._lock:
            self._writer.check_rotate()

    def _process_event(self, level, event, event_dict, exc_info=None):
        """
        Internal method that emulates structlog processors chain

        Args:
            level (str): Log level name
            event (str): Log message
            event_dict (dict): Log context
            exc_info (bool | tuple | Exception): Exception info. Defaults to None.

        Returns:
            tuple[str, str, dict, str | None, str | None]:
                level, event, event_dict, exception_rich, exception_plain
        """
        # from structlog.__log_levels.add_log_level()
        # warn is just a deprecated alias in the stdlib.
        if level == "WARN":
            level = "WARNING"
        # Calling exception("") is the same as error("", exc_info=True)
        if level == "EXCEPTION":
            level = "ERROR"

        # from structlog _process_event
        if self._context:
            context = self._context.copy()
            context.update(**event_dict)
            event_dict = context

        # ExceptionRenderer(rich_formatter)
        exception_rich = None
        exception_plain = None
        if exc_info is not None:
            exc_info = figure_out_exc_info(exc_info)
            if exc_info is not None:
                exception_rich, exception_plain = rich_formatter(exc_info)

        return level, event, event_dict, exception_rich, exception_plain

    def _msg(self, level, event, event_dict, raw=False, exc_info=None):
        """
        Internal method to render message

        Note that there is something different from structlog
        1. Context will be appended to log message (same as structlog)
                logger = logger.bind(user='May')
                logger.info('User login')
                # User login, user='May'
        2. kwargs won't be appended to log message, extra kwargs will be dropped (different from structlog)
            This is for i18n logging, log messages are auto extracted as i18n key.
                logger.info('Hello {user}', user='May', age=18)
                # Hello May
        3. `%` formatting is not allowed (same as structlog, different from builtin logging)
            If you need a placeholder, use `{key}` instead
            If you do need `%` placeholder, use `logger.classic_logger()` instead
                logger.info('Hello %s', 'May')
                # will raise error

        Args:
            level (str): Log level name
            event (str): Log message
            event_dict (dict): Log context
            raw (bool): Whether to log raw message without timestamp and level. Defaults to False.
            exc_info (bool | tuple | Exception): Exception info. Defaults to None.
        """
        level, event, event_dict, exception_rich, exception_plain = self._process_event(
            level, event, event_dict, exc_info=exc_info
        )

        # build message, ignore errors
        event = event_format(event, event_dict)
        event = join_event_dict(event, self._context)

        # inject time
        timestamp = time.time()
        now = datetime.fromtimestamp(timestamp).isoformat(sep=' ', timespec='milliseconds')

        # build log text
        if raw:
            text = f'{event}\n'
        else:
            text = f'{now} | {level} | {event}\n'

        text_rich = text
        text_plain = text
        if exception_rich:
            # exception_rich already ends with \n
            # but usually it's better to ensure it's on a new line
            text_rich = f'{text_rich}{exception_rich}\n'
        if exception_plain:
            text_plain = f'{text_plain}{exception_plain}\n'

        backend_inited = self._writer.backend.inited
        if backend_inited:
            backend_event = {'t': timestamp, 'l': level, 'm': event}
            # add exception
            if exception_plain:
                backend_event['e'] = exception_plain
            # add raw tag
            if raw:
                backend_event['r'] = 1
        else:
            # no backend
            backend_event = {}

        # print text
        self._emit(text_rich, text_plain, backend_event)

    def _emit(self, text_rich, text_plain, backend_event):
        """
        Internal method to emit event directly
        `text_rich` will be print to stdout, `text_plain` will be write into log file,
        `backend_event` will be sent to backend

        Args:
            text_rich (str): Formatted log text with rich formatting
            text_plain (str): Formatted log text without formatting
            backend_event (dict): Event dictionary for backend
        """
        writer = self._writer
        backend_inited = writer.backend.inited
        is_electron = writer.is_electron
        with self._lock:
            if backend_inited:
                # backend + file
                job = writer.backend.send_log(backend_event)
                writer.fd.write(text_plain)
                writer.fd.flush()
                job.acquire()
            else:
                if is_electron:
                    # file
                    writer.fd.write(text_plain)
                    writer.fd.flush()
                else:
                    # stdout + file
                    writer.fd.write(text_plain)
                    try:
                        writer.stdout.write(text_rich)
                    except (OSError, ValueError):
                        # stdout pipe may be broken while the host process is
                        # shutting down; logging must never raise into the caller
                        pass
                    writer.fd.flush()
                    try:
                        writer.stdout.flush()
                    except (OSError, ValueError):
                        # stdout pipe may be broken while the host process is
                        # shutting down; logging must never raise into the caller
                        pass

    @staticmethod
    def backend_event(event, timestamp=None, level='INFO', raw=0):
        """
        Create backend event directly

        Args:
            event (str): Log message
            timestamp (float): Timestamp. Defaults to None.
            level (str): Log level name. Defaults to 'INFO'.
            raw (int): Whether to log raw message without timestamp and level. Defaults to 0.

        Returns:
            dict: Event dictionary for backend
        """
        if timestamp is None:
            timestamp = time.time()
        backend_event = {'t': timestamp, 'l': level, 'm': event}
        if raw:
            backend_event['r'] = 1
        return backend_event

    """
    structlog-like features
    """

    def bind(self, **value_dict):
        """
        Return a new logger with *new_values* added to the existing ones.

        Args:
            **value_dict: Key-value pairs to bind.

        Returns:
            AlasioLogger: A new logger with the context bound.
        """
        new = self.__class__()
        context = self._context.copy()
        context.update(**value_dict)
        new._context = context
        new._writer = self._writer
        new.set_level(self._level)
        return new

    def classic_logger(self):
        """
        Returns:
            ClassicLogger: Classic logger instance
        """
        return ClassicLogger(self)

    def unbind(self, *keys):
        """
        Return a new logger with *keys* removed from the context.
        missing keys are ignored.

        Args:
            *keys: Keys to unbind.

        Returns:
            AlasioLogger: A new logger with the keys removed.
        """
        new = self.__class__()
        context = self._context.copy()
        for key in keys:
            context.pop(key, None)
        new._context = context
        new._writer = self._writer
        new.set_level(self._level)
        return new

    """
    Logging levels
    """

    def debug(self, event, **kwargs):
        """
        Log at DEBUG level.

        Args:
            event: Log message or exception
            **kwargs: Log context
        """
        event = stringify_event(event)
        self._msg('DEBUG', event, kwargs)

    def info(self, event, **kwargs):
        """
        Log at INFO level.

        Args:
            event: Log message or exception
            **kwargs: Log context
        """
        event = stringify_event(event)
        self._msg('INFO', event, kwargs)

    def warning(self, event, **kwargs):
        """
        Log at WARNING level.

        Args:
            event: Log message or exception
            **kwargs: Log context
        """
        event = stringify_event(event)
        self._msg('WARNING', event, kwargs)

    def error(self, event, **kwargs):
        """
        Log at ERROR level.

        Args:
            event: Log message or exception
            **kwargs: Log context
        """
        event = stringify_event(event)
        self._msg('ERROR', event, kwargs)

    def exception(self, event, exc_info=True, **kwargs):
        """
        Log at ERROR level with exception info.

        Args:
            event: Log message or exception
            exc_info (bool | tuple | Exception): Exception info. Defaults to True.
            **kwargs: Log context
        """
        if isinstance(event, Exception):
            if isinstance(event, (BaseExceptionGroup, ExceptionGroup)):
                exc_info = (type(event), event, event.__traceback__)
            msg = str(event)
            if msg:
                event = f'{type(event).__name__}: {msg}'
            else:
                event = type(event).__name__
        # see structlog._native.exception()
        self._msg('EXCEPTION', event, kwargs, exc_info=exc_info)

    def critical(self, event, **kwargs):
        """
        Log at CRITICAL level.

        Args:
            event: Log message or exception
            **kwargs: Log context
        """
        event = stringify_event(event)
        self._msg('CRITICAL', event, kwargs)

    """
    Custom logging methods
    """

    def raw(self, event, **kwargs):
        """
        Log raw messages

        Args:
            event (str): Log message
            **kwargs: Log context
        """
        # act like info but tag raw=True
        self._msg('INFO', event, kwargs, raw=True)

    def hr(self, title, level=3, **kwargs):
        """
        Log a horizontal rule.

        Args:
            title (str): Title of the horizontal rule
            level (int): Rule level (0-3). Defaults to 3.
            **kwargs: Log context
        """
        if level == 0:
            self.hr0(title, **kwargs)
        elif level == 1:
            self.hr1(title, **kwargs)
        elif level == 2:
            self.hr2(title, **kwargs)
        else:
            self.hr3(title, **kwargs)

    def hr0(self, title, **kwargs):
        """
        +==================================================================================================+
        |                                              LOGIN                                               |
        +==================================================================================================+
        2026-01-01 13:33:48.282 | INFO | LOGIN

        If the title is too long, the box auto-extends to wrap the title with padding.
        """
        title = f'{title}'.upper()
        # Auto-extend interior to wrap long titles: at least 98, with 4+ spaces padding each side
        interior = max(98, len(title) + 10)
        edge = f'+{"=" * interior}+'
        hr = str_center(f' {title} ', interior, ' ')
        hr = f'|{hr}|'
        self.raw(edge)
        self.raw(hr, **kwargs)
        self.raw(edge)
        self.info(title, **kwargs)

    def hr1(self, title, **kwargs):
        """
        ============================================== LOGIN ===============================================
        2026-01-01 13:33:48.282 | INFO | LOGIN

        At least 5 '=' are always shown on each side of the title.
        """
        title = f'{title}'.upper()
        width = max(100, len(title) + 12)
        hr = str_center(f' {title} ', width, '=')
        self.raw(hr, **kwargs)
        self.info(title, **kwargs)

    def hr2(self, title, **kwargs):
        """
        ---------------------------------------------- LOGIN -----------------------------------------------
        2026-01-01 13:33:48.282 | INFO | LOGIN

        At least 5 '-' are always shown on each side of the title.
        """
        title = f'{title}'.upper()
        width = max(100, len(title) + 12)
        hr = str_center(f' {title} ', width, '-')
        self.raw(hr, **kwargs)
        self.info(title, **kwargs)

    def hr3(self, title, **kwargs):
        """
        2026-01-01 13:33:48.282 | INFO | ................ LOGIN .................

        At least 5 '.' are always shown on each side of the title.
        """
        title = f'{title}'.upper()
        width = max(40, len(title) + 12)
        hr = str_center(f' {title} ', width, '.')
        self.info(hr, **kwargs)

    def attr(self, name, text):
        """
        2026-01-01 13:33:48.282 | INFO | [name] text

        Args:
            name (str): Attribute name
            text (Any): Attribute value
        """
        self.info(f'[{name}] {text}')

    def attr_align(self, name, text, front='', align=22):
        """
        2026-01-01 13:33:48.282 | INFO |           globe_center: (0, 0)
        2026-01-01 13:33:48.282 | INFO | 0.330s      similarity: 0.900

        Args:
            name (str): Attribute name
            text (Any): Attribute value
            front (str): Text to prepend to name. Defaults to ''.
            align (int): Alignment width. Defaults to 22.
        """
        name = str(name).rjust(align)
        front = str(front)
        if front:
            name = front + name[len(front):]
        self.info(f'{name}: {text}')


logger = AlasioLogger()