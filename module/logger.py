# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import datetime
import logging
import os
import sys
import traceback

from io import TextIOBase
from typing import Callable, List

from rich.console import Console, ConsoleOptions, ConsoleRenderable, NewLine, RenderResult
from rich.highlighter import RegexHighlighter, NullHighlighter
from rich.logging import RichHandler
from rich.text import Text
from rich.rule import Rule
from rich.style import Style
from rich.theme import Theme
from rich.traceback import Traceback


def empty_function(*args, **kwargs):
    pass


# cnocr will set root logger in cnocr.utils
# Delete logging.basicConfig to avoid logging the same message twice.
logging.basicConfig = empty_function
logging.raiseExceptions = True  # Set True if wanna see encode errors on console

# Remove HTTP keywords (GET, POST etc.)
RichHandler.KEYWORDS = []


class RichFileHandler(RichHandler):
    # Rename
    pass



#
# class FlutterHandler(RichHandler):
#     """
#     Pass renderable into a function
#     主要是传入一个回调函数
#     """
#
#     def __init__(self, *args, func: Callable[[ConsoleRenderable], None] = None, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._func = func
#
#     def emit(self, record: logging.LogRecord) -> None:
#         message = self.format(record)
#         tb = None
#         if (
#             self.rich_tracebacks
#             and record.exc_info
#             and record.exc_info != (None, None, None)
#         ):
#             exc_type, exc_value, exc_traceback = record.exc_info
#             traceback.print_tb(exc_traceback)
#             self._func(exc_traceback)
#             assert exc_type is not None
#             assert exc_value is not None
#             tb = Traceback.from_exception(
#                 exc_type,
#                 exc_value,
#                 exc_traceback,
#                 width=self.tracebacks_width,
#                 extra_lines=self.tracebacks_extra_lines,
#                 theme=self.tracebacks_theme,
#                 word_wrap=self.tracebacks_word_wrap,
#                 show_locals=self.tracebacks_show_locals,
#                 locals_max_length=self.locals_max_length,
#                 locals_max_string=self.locals_max_string,
#             )
#             # 这个好理解转化为特定格式， getMessage()返回寸str
#             message = record.getMessage()
#             if self.formatter:
#                 record.message = record.getMessage()
#                 formatter = self.formatter
#                 if hasattr(formatter, "usesTime") and formatter.usesTime():
#                     record.asctime = formatter.formatTime(
#                         record, formatter.datefmt)
#                 message = formatter.formatMessage(record)
#
#         # 这个message_renderable是一个Text对象
#         message_renderable = self.render_message(record, message)
#         log_renderable: ConsoleRenderable = self.render(
#             record=record, traceback=tb, message_renderable=message_renderable
#         )
#
#         # msg2 = Text.from_markup(message).markup
#
#         # 这个message_renderable是一个Text对象
#         # traceback是表示异常的对象
#         # Directly put renderable into function
#         if log_renderable:
#             if log_renderable is not str:
#                 print(f'-------------------------------------------------------log is not str{log_renderable}')
#                 log_renderable = str(log_renderable)
#             self._func(log_renderable)
#
#     def handle(self, record: logging.LogRecord) -> bool:
#         if not self._func:
#             return True
#         super().handle(record)

class FlutterHandler(RichHandler):
    # Rename
    pass

class FlutterConsole(Console):
    """
    Force full feature console
    but not working lol :(
    """
    @property
    def options(self) -> ConsoleOptions:
        return ConsoleOptions(
            max_height=self.size.height,
            size=self.size,
            legacy_windows=False,
            min_width=1,
            max_width=self.width,
            encoding='utf-8',
            is_terminal=False,
        )

class FlutterLogStream(TextIOBase):
    def __init__(self, *args, func: Callable[[ConsoleRenderable], None] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._func = func

    def write(self, msg: str) -> int:
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8")
        self._func(msg)
        return len(msg)


def show_handlers(handlers):
    # 获取并打印日志记录器中处理器的信息
    for handler in logger.handlers:
        # 获取处理器的类名
        handler_class = handler.__class__.__name__
        print(f"Handler class: {handler_class}")

        # 获取处理器的级别
        handler_level = logging.getLevelName(handler.level)
        print(f"Handler level: {handler_level}")

        # 获取处理器的格式化器
        formatter = handler.formatter
        if formatter is not None:
            formatter_class = formatter.__class__.__name__
            print(f"Formatter class: {formatter_class}")

        # 其他处理器的属性和方法，根据需要进行获取和打印

        print()  # 打印空行，用于分隔处理器的信息

# Logger init
logger_debug = False
logger = logging.getLogger('oas')
logger.setLevel(logging.DEBUG if logger_debug else logging.INFO)
file_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d | %(levelname)8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d │ %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
flutter_formatter = logging.Formatter(
    fmt='| %(asctime)s.%(msecs)03d | %(message)08s', datefmt='%H:%M:%S')


# Add rich console logger
# ======================================================================================================================
#            设置控制台的
# ======================================================================================================================
stdout_console = console = Console()
console_hdlr = RichHandler(
    show_path=False,
    show_time=False,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
    tracebacks_extra_lines=3,
)
console_hdlr.setFormatter(console_formatter)
logger.addHandler(console_hdlr)

# Ensure running in Alas root folder
os.chdir(os.path.join(os.path.dirname(__file__), '../'))
# Add file logger
pyw_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]


def set_file_logger(name=pyw_name):
    if '_' in name:
        name = name.split('_', 1)[0]
    log_file = f'./log/{datetime.date.today()}_{name}.txt'
    try:
        file = open(log_file, mode='a', encoding='utf-8')
    except FileNotFoundError:
        os.mkdir('./log')
        file = open(log_file, mode='a', encoding='utf-8')

    file_console = Console(
        file=file,
        no_color=True,
        highlight=False,
        width=80,
    )

    hdlr = RichFileHandler(
        console=file_console,
        show_path=False,
        show_time=False,
        show_level=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=3,
        tracebacks_width=80,
        highlighter=NullHighlighter(),
    )
    hdlr.setFormatter(file_formatter)

    logger.handlers = [h for h in logger.handlers if not isinstance(
        h, (logging.FileHandler, RichFileHandler))]
    logger.addHandler(hdlr)
    logger.log_file = log_file

# 给flutter设置
def set_func_logger(func):
    stream = FlutterLogStream(func=func)
    stream_console = Console(
        file=stream,
        force_terminal=False,
        force_interactive=False,
        no_color=True,
        highlight=False,
        width=80,
    )
    hdlr = FlutterHandler(
        console=stream_console,
        show_path=False,
        show_time=False,
        show_level=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=3,
        highlighter=NullHighlighter(),
    )
    hdlr.setFormatter(flutter_formatter)
    logger.addHandler(hdlr)


def _get_renderables(
    self: Console, *objects, sep=" ", end="\n", justify=None, emoji=None, markup=None, highlight=None,
) -> List[ConsoleRenderable]:
    """
    Refer to rich.console.Console.print()
    """
    if not objects:
        objects = (NewLine(),)

    render_hooks = self._render_hooks[:]
    with self:
        renderables = self._collect_renderables(
            objects,
            sep,
            end,
            justify=justify,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
        )
        for hook in render_hooks:
            renderables = hook.process_renderables(renderables)
    return renderables


def print(*objects: ConsoleRenderable, **kwargs):
    for hdlr in logger.handlers:
        if isinstance(hdlr, FlutterHandler):
            for renderable in _get_renderables(hdlr.console, *objects, **kwargs):
                hdlr.console.file._func(str(renderable))
        elif isinstance(hdlr, RichHandler):
            hdlr.console.print(*objects)

class GuiRule(Rule):
    def __rich_console__(
            self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        options.max_width = 80
        return super().__rich_console__(console, options)

    def __str__(self):
        total_width = 80
        cell_len = len(self.title) + 2
        aside_len = (total_width - cell_len) // 2
        left = self.characters * aside_len
        right = self.characters * (total_width - cell_len - aside_len)
        if self.title:
            space = ' '
        else:
            space = self.characters
        return f"{left}{space}{self.title}{space}{right}\n"

    def __repr__(self):
        return self.__str__()

def rule(title="", *, characters="─", style="rule.line", end="\n", align="center"):
    rule = GuiRule(title=title, characters=characters,
                style=style, end=end)
    print(rule)

def hr(title, level=3):
    title = str(title).upper()
    if level == 1:
        logger.rule(title, characters='═')
        logger.info(title)
    if level == 2:
        logger.rule(title, characters='─')
        logger.info(title)
    if level == 3:
        logger.info(f"[bold]<<< {title} >>>[/bold]", extra={"markup": True})
    if level == 0:
        logger.rule(characters='═')
        logger.rule(title, characters='─')
        logger.rule(characters='═')

def attr(name, text):
    logger.info('[%s] %s' % (str(name), str(text)))

def attr_align(name, text, front='', align=22):
    name = str(name).rjust(align)
    if front:
        name = front + name[len(front):]
    logger.info('%s: %s' % (name, str(text)))

def show():
    logger.info('INFO')
    logger.warning('WARNING')
    logger.debug('DEBUG')
    logger.error('ERROR')
    logger.critical('CRITICAL')
    logger.hr('hr0', 0)
    logger.hr('hr1', 1)
    logger.hr('hr2', 2)
    logger.hr('hr3', 3)
    logger.info(r'Brace { [ ( ) ] }')
    logger.info(r'True, False, None')
    logger.info(r'E:/path\\to/alas/alas.exe, /root/alas/, ./relative/path/log.txt')
    local_var1 = 'This is local variable'
    # Line before exception
    raise Exception("Exception")
    # Line below exception

def error_convert(func):
    def error_wrapper(msg, *args, **kwargs):
        if isinstance(msg, Exception):
            msg = f'{type(msg).__name__}: {msg}'
        return func(msg, *args, **kwargs)

    return error_wrapper


logger.error = error_convert(logger.error)
logger.hr = hr
logger.attr = attr
logger.attr_align = attr_align
logger.set_file_logger = set_file_logger
logger.set_func_logger = set_func_logger
logger.rule = rule
logger.print = print
logger.log_file: str

logger.set_file_logger()
logger.hr('Start', level=0)


