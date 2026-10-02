import sys
from collections import deque
from inspect import isclass
from types import TracebackType
from typing import Any, Optional, Tuple, Type

ExcInfo = Tuple[Type[BaseException], BaseException, Optional[TracebackType]]


# from structlog.processors._figure_out_exc_info
def figure_out_exc_info(v: Any) -> Optional[ExcInfo]:
    """
    Try to convert *v* into an ``exc_info`` tuple.

    Return ``None`` if *v* does not represent an exception or if there is no
    current exception.
    """
    if isinstance(v, BaseException):
        return (v.__class__, v, v.__traceback__)

    if isinstance(v, tuple) and len(v) == 3:
        has_type = isinstance(v[0], type) and issubclass(v[0], BaseException)
        has_exc = isinstance(v[1], BaseException)
        has_tb = v[2] is None or isinstance(v[2], TracebackType)
        if has_type and has_exc and has_tb:
            return v

    if v:
        result = sys.exc_info()
        if result == (None, None, None):
            return None
        return result

    return None


# a function that accepts anything and does nothing
def empty_function(*args, **kwargs):
    pass


class SafeDict(dict):
    def __missing__(self, key):
        # Return placeholder when key is missing, for better debugging
        # If key is not a valid identifier (e.g. from a set literal "{'a'}"),
        # return the key with braces to preserve it.
        if isinstance(key, str) and not key.isidentifier():
            return f"{{{key}}}"
        return f'<key "{key}" missing>'


def event_format(event, event_dict):
    """
    build message from `event.format(event_dict)`, ignore errors
    check event_dict also, if someone log like this:
      modules = set('combat_ui')
      logger.info(f'Assets generate, modules={modules}')
    we won't log:
      Assets generate, modules=<key 'combat_ui' missing>

    Args:
        event (str):
        event_dict (dict[str, Any]):

    Returns:
        str:
    """
    if '{' in event and event_dict:
        try:
            event = event.format(**event_dict)
        except KeyError:
            try:
                event = event.format_map(SafeDict(event_dict))
            except Exception:
                pass
        except Exception:
            # maybe {} is unpaired
            pass
    return event


def event_args_format(event, event_args):
    """
    build message from `event % event_args`, ignore errors

    Args:
        event (str):
        event_args (tuple[Any] | Any):

    Returns:
        str:
    """
    if '%' in event and event_args:
        try:
            event = event % event_args
        except Exception:
            pass
    return event


def join_event_dict(event, event_dict):
    """
    Format event_dict into event, like:
        Hello {user}, user='May'

    Args:
        event (str):
        event_dict (dict[str, Any]):

    Returns:
        str:
    """
    if not event_dict:
        return event
    items = [f'{k}={repr(v)}' for k, v in event_dict.items()]
    if not items:
        return event
    if event:
        items.insert(0, event)
    event = ', '.join(items)
    return event


def gen_exception_tree(exc: BaseException):
    """
    Generate exception tree like:
    - sub exception 1, depth 1
      - sub exception 1, depth 2
    - sub exception 2
      - sub exception 2, depth 1
      - sub exception 2, depth 2
    """
    # (exc, depth)
    stack = deque()
    stack.append((exc, 0))

    while stack:
        current_exc, depth = stack.pop()

        prefix = "  " * depth
        yield f'{prefix}- {type(current_exc).__name__}: {current_exc}'

        if BaseExceptionGroup and isinstance(current_exc, BaseExceptionGroup):
            children = [(e, depth + 1) for e in current_exc.exceptions]
            stack.extend(reversed(children))


def stringify_event(event):
    """
    Convert whatever to str, pretty exceptions
    """
    t = type(event)
    # fast path, most events are str
    if t is str:
        return event
    # Better exception logging
    # If someone do:
    #   try:
    #       raise ExampleError("oops")
    #   except ExampleError as e:
    #       logger.error(e)
    # We can log:
    #   ExampleError: oops
    # instead of just empty string "oops"
    if isinstance(event, Exception):
        if isinstance(event, (BaseExceptionGroup, ExceptionGroup)):
            msg = str(event)
            if msg:
                title = f'{type(event).__name__}: {msg}'
            else:
                title = type(event).__name__
            detail = '\n'.join(gen_exception_tree(event))
            return f'{title}\n{detail}'
        else:
            msg = str(event)
            if msg:
                return f'{type(event).__name__}: {msg}'
            else:
                return type(event).__name__
    # maybe just ExampleError
    if isclass(event) and issubclass(event, Exception):
        return event.__name__
    return str(event)


def replace_unicode_table(output):
    """
    Convert unicode table to ascii

    Args:
        output (str):

    Returns:
        str:
    """
    mapping = {
        "┌": "+", "┐": "+", "└": "+", "┘": "+",
        "├": "+", "┤": "+", "┬": "+", "┴": "+",
        "┼": "+", "─": "-", "│": "|", "═": "=",
        "║": "|", "╒": "+", "╓": "+", "╔": "+",
        "╕": "+", "╖": "+", "╗": "+", "╘": "+",
        "╙": "+", "╚": "+", "╛": "+", "╜": "+",
        "╝": "+", "╞": "+", "╟": "+", "╠": "+",
        "╡": "+", "╢": "+", "╣": "+", "╤": "+",
        "╥": "+", "╦": "+", "╧": "+", "╨": "+",
        "╩": "+", "╪": "+", "╫": "+", "╬": "+",
        "…": "~",
    }
    for unicode_char, ascii_char in mapping.items():
        output = output.replace(unicode_char, ascii_char)
    return output