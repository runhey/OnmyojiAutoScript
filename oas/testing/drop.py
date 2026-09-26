import functools
import random


def function_drop(drop_rate, default=..., log=True):
    """
    Decorator for testing purposes that randomly drops function calls.

    Args:
        drop_rate (float): Probability (0.0-1.0) to drop the function call.
        default: Default return value when the call is dropped.
            Defaults to Ellipsis.
        log (bool): Whether to log when a call is dropped.
            Defaults to True.

    Returns:
        callable: Decorated function.
    """
    def decorator(func):
        # Unwrap classmethod/staticmethod to work with the underlying function
        is_classmethod = isinstance(func, classmethod)
        is_staticmethod = isinstance(func, staticmethod)
        underlying = func.__func__ if is_classmethod or is_staticmethod else func

        # Use __qualname__ as the display name so devs can distinguish local functions
        qualname = getattr(underlying, '__qualname__', '') or underlying.__name__

        # Check first param via __code__ to detect self/cls
        try:
            code = underlying.__code__
            first_param = code.co_varnames[0] if code.co_argcount > 0 else None
        except AttributeError:
            first_param = None

        # Detect if this is a method where we should strip the first arg
        # Look at the segment immediately before the function name in qualifier
        parts = qualname.rsplit('.', 1)
        is_method = (
            len(parts) == 2
            and parts[1] == underlying.__name__
            and parts[0].rsplit('.', 1)[-1] != '<locals>'
            and first_param in ('self', 'cls')
        )

        @functools.wraps(underlying)
        def wrapper(*args, **kwargs):
            if random.random() < drop_rate:
                if log:
                    if is_method and args:
                        display_args = args[1:]
                    else:
                        display_args = args

                    args_str = ', '.join(
                        [repr(a) for a in display_args]
                        + [f'{k}={v!r}' for k, v in kwargs.items()]
                    )
                    print(f'Dropped: {qualname}({args_str})')
                return default
            return underlying(*args, **kwargs)

        if is_classmethod:
            return classmethod(wrapper)
        elif is_staticmethod:
            return staticmethod(wrapper)
        return wrapper
    return decorator
