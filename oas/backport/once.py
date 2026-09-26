from functools import wraps
from threading import Lock


def patch_once(f):
    """
    Run a function only once, no matter how many times it has been called.
    This decorator is thread-safe.
    """
    lock = Lock()
    has_run = False

    @wraps(f)
    def wrapper(*args, **kwargs):
        nonlocal has_run, lock
        if has_run:
            return
        with lock:
            if has_run:
                return
            f(*args, **kwargs)
            has_run = True
        lock = None

    return wrapper


def run_once(f):
    """
    Run a function only once, no matter how many times it has been called.
    This decorator is thread-safe, see run_once for more info

    Examples:
        @run_once
        def do_something_heavy(foo, bar):
            pass

        while 1:
            do_something_heavy()

    Examples:
        def do_something_heavy(foo, bar):
            pass

        action = run_once(do_something_heavy)
        while 1:
            action()

    Examples:
        @run_once
        def my_function(foo, bar):
            return foo + bar

        my_function()  # run once
        my_function()  # do nothing
        my_function.has_run = False  # reset
        my_function()  # run once
        my_function()  # do nothing
    """
    lock = Lock()

    @wraps(f)
    def wrapper(*args, **kwargs):
        nonlocal lock
        if wrapper.has_run:
            return wrapper.result
        with lock:
            if wrapper.has_run:
                return wrapper.result
            result = f(*args, **kwargs)
            wrapper.has_run = True
            wrapper.result = result
        return result

    wrapper.has_run = False
    wrapper.result = None
    return wrapper
