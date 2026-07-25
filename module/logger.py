# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import sys

import logging
import os
import shutil
from datetime import datetime, timedelta, date
from io import TextIOBase
from pathlib import Path
from rich.console import Console, ConsoleOptions, ConsoleRenderable, NewLine, RenderResult
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.rule import Rule
from typing import Callable, List


def cleanup_logs(log_dir: str = "./log", keep_days: int = 7):
    """删除 log_dir 下所有早于 keep_days 的文件夹和文件"""
    log_path = Path(log_dir)
    if not log_path.exists():
        return  # 目录都没有，直接退出
    keep_days_ago_ts = (datetime.now() - timedelta(days=keep_days)).timestamp()
    for name in os.listdir(log_path):
        full_path = os.path.join(log_path, name)
        # 忽略软链接，仅处理文件和目录
        if not os.path.exists(full_path):
            continue
        if os.path.isfile(full_path):
            # 处理 log 根目录下超过keep_days的文件
            try:
                if os.path.getmtime(full_path) < keep_days_ago_ts:
                    os.remove(full_path)
            except OSError as e:
                logger.error(f"delete file '{full_path}' error: {e}")
        elif os.path.isdir(full_path):
            # 检查是否为 error 目录
            if name != 'error':
                continue
            for error_dir_name in os.listdir(full_path):
                error_dir_path = os.path.join(full_path, error_dir_name)
                if not os.path.isdir(error_dir_path):
                    continue
                # 处理 log/error 根目录下超过keep_days的文件夹
                try:
                    if os.path.getmtime(error_dir_path) < keep_days_ago_ts:
                        # 递归删除整个目录及其内容
                        shutil.rmtree(error_dir_path)
                except OSError as e:
                    logger.error(f"delete dir '{error_dir_path}' error: {e}")


def empty_function(*args, **kwargs):
    pass


# Ensure running in Alas root folder
os.chdir(os.path.join(os.path.dirname(__file__), '../'))
# cnocr will set root logger in cnocr.utils
# Delete logging.basicConfig to avoid logging the same message twice.
logging.basicConfig = empty_function
logging.raiseExceptions = True  # Set True if wanna see encode errors on console

# Remove HTTP keywords (GET, POST etc.)
# RichHandler.KEYWORDS = []


# def show_handlers(handlers):
#     # 获取并打印日志记录器中处理器的信息
#     for handler in logger.handlers:
#         # 获取处理器的类名
#         handler_class = handler.__class__.__name__
#         print(f"Handler class: {handler_class}")
#
#         # 获取处理器的级别
#         handler_level = logging.getLevelName(handler.level)
#         print(f"Handler level: {handler_level}")
#
#         # 获取处理器的格式化器
#         formatter = handler.formatter
#         if formatter is not None:
#             formatter_class = formatter.__class__.__name__
#             print(f"Formatter class: {formatter_class}")
#
#         # 其他处理器的属性和方法，根据需要进行获取和打印
#         print()  # 打印空行，用于分隔处理器的信息


# Logger init
logger_debug = False
logger = logging.getLogger('oas')
logger.setLevel(logging.DEBUG if logger_debug else logging.INFO)
file_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d | %(filename)20s:%(lineno)04d | %(levelname)8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d │ %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
flutter_formatter = logging.Formatter(
    fmt='| %(asctime)s.%(msecs)03d | %(message)08s', datefmt='%H:%M:%S')


# ======================================================================================================================
#            Set console logger
# ======================================================================================================================
console_hdlr = RichHandler(
    console=Console(
        width=120
    ),
    show_path=False,
    show_time=False,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
    tracebacks_extra_lines=3,
    tracebacks_width=160
)
console_hdlr.setFormatter(console_formatter)
logger.addHandler(console_hdlr)


# ======================================================================================================================
#            Set file
# ======================================================================================================================
class RichFileHandler(RichHandler):
    # Rename
    pass


# Add file logger
pyw_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]


def set_file_logger(name=pyw_name, *, do_cleanup=False):
    if '_' in name:
        name = name.split('_', 1)[0]
    log_file = f'./log/{date.today()}_{name}.txt'
    try:
        file = open(log_file, mode='a', encoding='utf-8')
    except FileNotFoundError:
        os.mkdir('./log')
        file = open(log_file, mode='a', encoding='utf-8')

    file_console = Console(
        file=file,
        no_color=True,
        highlight=False,
        width=160,
    ) 

    hdlr = RichFileHandler(
        console=file_console,
        show_path=False,
        show_time=False,
        show_level=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=3,
        tracebacks_width=160,
        highlighter=NullHighlighter(),
    )
    hdlr.setFormatter(file_formatter)

    logger.handlers = [h for h in logger.handlers if not isinstance(
        h, (logging.FileHandler, RichFileHandler))]
    logger.addHandler(hdlr)
    logger.log_file = log_file

    # ---------- 可选：清理旧文件 ----------
    if do_cleanup:
        cleanup_logs()
        logger.info("Log cleanup finished")


# ======================================================================================================================
#            Set flutter
# ======================================================================================================================
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

# ======================================================================================================================
#            Set print format
# ======================================================================================================================


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
    logger.info('Tests very long strings. Tests very long strings. Tests very long strings. Tests very long strings. Tests very long strings.')
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
