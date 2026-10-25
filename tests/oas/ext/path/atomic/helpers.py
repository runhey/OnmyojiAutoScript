"""
Helpers shared by the tests of oas.ext.path.atomic.

The atomic functions retry on PermissionError with an exponential
backoff on Windows (windows_attempt_delay). The helpers break the os
functions without a real file lock, and replace the sleep of the
module, so the retry tests observe every attempt without waiting.
"""
import builtins

from oas.ext.path import atomic


class SleepRecorder:
    """
    Stand-in of the time module used by oas.ext.path.atomic.

    The retry loops call time.sleep() between the attempts, the
    recorder collects the delays instead of waiting in real time.
    """
    def __init__(self):
        # delays passed to sleep(), in the call order
        self.sleeps = []

    def sleep(self, delay):
        """
        Record a delay without waiting.

        Args:
            delay (float): Delay in seconds the caller wanted to wait
        """
        self.sleeps.append(delay)


def record_sleeps(monkeypatch):
    """
    Replace the time module of oas.ext.path.atomic with a recorder.

    Args:
        monkeypatch (pytest.MonkeyPatch): Monkeypatch fixture of the test

    Returns:
        SleepRecorder: Recorder of the delays
    """
    recorder = SleepRecorder()
    monkeypatch.setattr(atomic, 'time', recorder)
    return recorder


def break_function(monkeypatch, target, name, errors):
    """
    Patch a function to fail on its first calls.

    The errors are raised one per call, in order, the original function
    runs when the list is exhausted. The tests use it to simulate a file
    locked by another process (PermissionError) and to count the
    attempts of the retry loops.

    Args:
        monkeypatch (pytest.MonkeyPatch): Monkeypatch fixture of the test
        target (object): Module holding the function, e.g. the os module
            or the atomic module
        name (str): Name of the function, e.g. 'replace'
        errors (list): Errors to raise, one per call

    Returns:
        list: Recorded calls, an (args, kwargs) tuple per call
    """
    original = getattr(target, name, None)
    if original is None:
        # the name may be a builtin, e.g. atomic.open is builtins.open
        original = getattr(builtins, name)
    calls = []

    def broken(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return original(*args, **kwargs)

    # The atomic module does not define open() itself, the name is
    # created in the module namespace to shadow the builtin
    monkeypatch.setattr(target, name, broken, raising=False)
    return calls
