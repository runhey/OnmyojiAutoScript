import os
import sys

import psutil

if psutil.LINUX:
    import psutil._psutil_posix as cetx

    def nice_get(pid):
        return cetx.getpriority(pid)

    def nice_set(pid, value):
        return cetx.setpriority(pid, value)

elif psutil.WINDOWS:
    import psutil._psutil_windows as cext

    def nice_get(pid):
        return cext.proc_priority_get(pid)

    def nice_set(pid, value):
        return cext.proc_priority_set(pid, value)

elif psutil.MACOS:
    # MACOS uses cext_posix
    import psutil._psutil_posix as cext_posix

    def nice_get(pid):
        return cext_posix.getpriority(pid)

    def nice_set(pid, value):
        return cext_posix.setpriority(pid, value)

elif psutil.BSD:
    # BSD uses cext_posix
    import psutil._psutil_posix as cext_posix

    def nice_get(pid):
        return cext_posix.getpriority(pid)

    def nice_set(pid, value):
        return cext_posix.setpriority(pid, value)

elif psutil.SUNOS:
    import psutil._psutil_posix as cext_posix
    from psutil._common import AccessDenied
    from psutil._pssunos import cext, get_procfs_path, proc_info_map

    def nice_get(pid):
        if pid in (2, 3):
            return cext.proc_basic_info(pid, get_procfs_path())[proc_info_map['nice']]
        return cext_posix.getpriority(pid)

    def nice_set(pid, value):
        if pid in (2, 3):
            raise AccessDenied(pid)
        return cext_posix.setpriority(pid, value)

elif psutil.AIX:
    # AIX uses cext_posix
    import psutil._psutil_posix as cext_posix

    def nice_get(pid):
        return cext_posix.getpriority(pid)

    def nice_set(pid, value):
        return cext_posix.setpriority(pid, value)

else:  # pragma: no cover
    raise NotImplementedError('platform %s is not supported' % sys.platform)


def set_lower_process_priority(pid=None):
    """
    Args:
        pid (int): Pid to set lower process priority,
            None to set current process

    Returns:
        Tuple[bool, Exception]: Whether success and any exception that occur
            On windows, if you try to lower an admin process, you may get PermissionError
            On Unix, if current process is already lower than nice=10, you may get error
                because lower nice requires root
    """
    if pid is None:
        pid = os.getpid()
    if psutil.WINDOWS:
        nice = psutil.BELOW_NORMAL_PRIORITY_CLASS
    else:
        nice = 10
    try:
        nice_set(pid, nice)
        return True, None
    except Exception as e:
        return False, e


def set_lowest_process_priority(pid=None):
    """
    Args:
        pid (int): Pid to set the lowest process priority possible,
            None to set current process

    Returns:
        Tuple[bool, Exception]: Whether success and any exception that occur
            On windows, if you try to lower an admin process, you may get PermissionError
            On Unix, if current process is already lower than nice=10, you may get error
                because lower nice requires root
    """
    if pid is None:
        pid = os.getpid()
    if psutil.WINDOWS:
        nice = psutil.IDLE_PRIORITY_CLASS
    else:
        nice = 19
    try:
        nice_set(pid, nice)
        return True, None
    except Exception as e:
        return False, e
