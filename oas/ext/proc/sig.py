import os
import signal
import sys

import psutil

if psutil.POSIX:

    def _send_signal(pid, sig):
        if pid < 0:
            raise ValueError("pid must be a positive integer")
        if pid == 0:
            # see "man 2 kill"
            raise ValueError(
                "preventing sending signal to process with PID 0 as it "
                "would affect every process in the process group of the "
                "calling process (os.getpid()) instead of PID 0")
        os.kill(pid, sig)

    def terminate(pid):
        _send_signal(pid, signal.SIGTERM)

    def kill(pid):
        _send_signal(pid, signal.SIGKILL)

elif psutil.WINDOWS:
    import psutil._psutil_windows as cext

    def terminate(pid):
        cext.proc_kill(pid)

    def kill(pid):
        cext.proc_kill(pid)

else:  # pragma: no cover
    raise NotImplementedError('platform %s is not supported' % sys.platform)


def process_terminate(pid):
    """
    Terminate the process with SIGTERM
    On Windows this is an alias for kill()

    Args:
        pid (int):

    Returns:
        Tuple[bool, Exception]: Whether success and any exception that occur
    """
    try:
        terminate(pid)
        return True, None
    except Exception as e:
        return False, e


def process_kill(pid):
    """
    Terminate the process with SIGKILL

    Args:
        pid (int):

    Returns:
        Tuple[bool, Exception]: Whether success and any exception that occur
    """
    try:
        kill(pid)
        return True, None
    except Exception as e:
        return False, e
