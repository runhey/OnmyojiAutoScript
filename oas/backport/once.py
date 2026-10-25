from functools import wraps
from threading import Lock


def init_once(f):
    """
    Run a function only once, no matter how many times it has been called.
    This decorator is thread-safe, see run_once for more info.
    """
    lock = Lock()
    has_run = False

    @wraps(f)
    def wrapper(*args, **kwargs):
        nonlocal has_run
        if has_run:
            return
        with lock:
            if has_run:
                return
            f(*args, **kwargs)
            has_run = True
        # Keep the lock referenced, a thread that already passed the check
        # above may still be about to acquire it.

    return wrapper


def run_once(f):
    """
    Run a function only once, no matter how many times it has been called.
    run_once() can be reset and return cached result on later calls.
    init_once() cannot be reset and has no return, usually to be used in initialization.
    This decorator is thread-safe.

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
            wrapper.result = result
            wrapper.has_run = True
        return result

    wrapper.has_run = False
    wrapper.result = None
    return wrapper
