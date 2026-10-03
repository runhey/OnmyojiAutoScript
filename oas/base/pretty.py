from datetime import datetime


def pretty_value(value):
    """
    Like repr(value) but pretty showing datetime
    """
    if isinstance(value, datetime):
        # '2026-06-30T12:00:00+08:00'
        value = value.isoformat(sep='T')
        return f"'{value}'"
    return repr(value)


def dict2kv(dic, drop_none=False, use_pretty=False):
    """
    Format dict to readable string

    Args:
        dic (dict): {'path': 'Scheduler.ServerUpdate', 'value': True}
        drop_none: True to drop None values
        use_pretty:

    Returns:
        str: "path='Scheduler.ServerUpdate', value=True"
    """
    if drop_none:
        if use_pretty:
            items = [f'{k}={pretty_value(v)}' for k, v in dic.items() if v is not None]
        else:
            items = [f'{k}={repr(v)}' for k, v in dic.items() if v is not None]
    else:
        if use_pretty:
            items = [f'{k}={pretty_value(v)}' for k, v in dic.items()]
        else:
            items = [f'{k}={repr(v)}' for k, v in dic.items()]
    return ', '.join(items)


def pretty_time(second):
    """
    Format time with adaptive units (s or ms or us)

    Args:
        second (float): Time in seconds

    Returns:
        str: Formatted time string
    """
    if second >= 1:
        return f'{second:.3f}s'
    if second >= 0.001:
        return f"{second * 1000:.3f}ms"
    return f"{second * 1000000:.3f}us"


def pretty_size(size):
    """Converts a byte size into a human-readable string format.

    Args:
        size (int | float): The size in bytes to be formatted.

    Returns:
        str: A formatted string representing the size (e.g., '123.12KB').
             The maximum unit used is 'TB'.
    """
    # Handle zero or negative cases
    if size <= 0:
        return "0.00B"

    units = ['B', 'KB', 'MB', 'GB']
    for unit in units:
        if size < 1024.0:
            return f"{size:.2f}{unit}"
        size /= 1024.0
    return f"{size:.2f}TB"
