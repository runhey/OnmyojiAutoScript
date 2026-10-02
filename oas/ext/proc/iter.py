import psutil
from psutil import _psplatform as psplatform

from .cmd import get_cmdline

# proc.py is an alternative of psutil.
# It's 10+ times faster by directly access psutil's C bindings

# psutil.pids()
def pids() -> "list[int]":
    # [MODIFIED] No global variable _LOWEST_PID
    return sorted(psplatform.pids())


def process_iter():
    """
    Iter all running processes, equivalent to `psutil.process_iter()`

    FYI, to terminate or kill the process, do:
        psutil.Process(pid).terminate()
        psutil.Process(pid).kill()

    Yields:
        "tuple[int, list[str]]": (pid, cmdline)
            cmdline is guaranteed to have at least one element
            Don't forget to normpath if you need to check cmdline
    """
    if psutil.WINDOWS:
        # Since this is a one-time-usage, we access psutil._psplatform.Process directly
        # to bypass the call of psutil.Process.is_running().
        # This only costs about 0.017s.
        # If you do psutil.process_iter(['pid', 'cmdline']) it will take over 1s
        for pid in pids():
            # 0 and 4 are always represented in taskmgr and process-hacker
            if pid == 0 or pid == 4:
                continue
            cmd = get_cmdline(pid)
            # Validate cmdline
            if not cmd:
                continue
            try:
                exe = cmd[0]
            except IndexError:
                continue
            # \??\C:\Windows\system32\conhost.exe
            if exe.startswith(r'\??'):
                continue
            yield pid, cmd
    else:
        for pid in pids():
            cmd = get_cmdline(pid)
            # Validate cmdline
            if not cmd:
                continue
            try:
                cmd[0]
            except IndexError:
                continue
            yield pid, cmd
