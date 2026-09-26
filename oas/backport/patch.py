# Trimmed from alasio/backport/patch.py for OAS (Python 3.14)
# Only the environment unification patches are kept.
# Dropped: patch_mimetype / patch_threadpool_executor_maxworker / fix_py37_subprocess_communicate
import sys

from oas.backport.once import patch_once


@patch_once
def patch_std():
    """
    Force use utf-8 in stdin, stdout, stderr, ignoring any user env.

    Returns:
        bool: if success
    """
    # note that reconfigure() requires python>=3.7
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        return True
    except (AttributeError, TypeError):
        # std may get replaced by user's TextIO
        # which does not have reconfigure()
        return False


@patch_once
def patch_environ():
    """
    Remove all python related environs, updated to python 3.15
    Note that some environs effects python interpreter startup, removing them at runtime won't work.

    You can AI to extract the list from https://docs.python.org/3/using/cmdline.html
    """
    python_environment_variables = [
        "FORCE_COLOR",
        "NO_COLOR",
        "PYTHONASYNCIODEBUG",
        "PYTHONBREAKPOINT",
        "PYTHONCASEOK",
        "PYTHONCOERCECLOCALE",
        "PYTHONDEBUG",
        "PYTHONDEVMODE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONDUMPREFS",
        "PYTHONDUMPREFSFILE",
        "PYTHONEXECUTABLE",
        "PYTHONFAULTHANDLER",
        "PYTHONHASHSEED",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONINTMAXSTRDIGITS",
        "PYTHONIOENCODING",
        "PYTHONLEGACYWINDOWSFSENCODING",
        "PYTHONLEGACYWINDOWSSTDIO",
        "PYTHONMALLOC",
        "PYTHONMALLOCSTATS",
        "PYTHONNODEBUGRANGES",
        # "PYTHONNOUSERSITE",
        "PYTHONOPTIMIZE",
        "PYTHONPATH",
        "PYTHONPERFSUPPORT",
        "PYTHONPLATLIBDIR",
        "PYTHONPROFILEIMPORTTIME",
        "PYTHONPYCACHEPREFIX",
        "PYTHONSAFEPATH",
        "PYTHONSTARTUP",
        "PYTHONTRACEMALLOC",
        "PYTHONUNBUFFERED",
        "PYTHONUSERBASE",
        # "PYTHONUTF8",
        "PYTHONVERBOSE",
        "PYTHONWARNDEFAULTENCODING",
        "PYTHONWARNINGS",
        "PYTHON_BASIC_REPL",
        "PYTHON_COLORS",
        "PYTHON_CONTEXT_AWARE_WARNINGS",
        "PYTHON_CPU_COUNT",
        "PYTHON_DISABLE_REMOTE_DEBUG",
        "PYTHON_FROZEN_MODULES",
        "PYTHON_GIL",
        "PYTHON_HISTORY",
        "PYTHON_JIT",
        "PYTHON_PERF_JIT_SUPPORT",
        "PYTHON_PRESITE",
        "PYTHON_THREAD_INHERIT_CONTEXT",
        "PYTHON_TLBC",
    ]
    proxy_environment_variables = [
        'HTTP_PROXY',
        'HTTPS_PROXY',
        'ALL_PROXY',
        'NO_PROXY',
        'HTTPPROXY',
        'HTTPSPROXY',
        'ALLPROXY',
        'NOPROXY',
    ]
    removes = set(python_environment_variables + proxy_environment_variables)

    import os

    # listify to safely iterate
    environs = [key for key in os.environ]
    for key in environs:
        upper = key.upper()
        if upper in removes:
            os.environ.pop(key, None)

    # set PYTHONUTF8 so child process will use UTF8
    os.environ["PYTHONUTF8"] = "1"
    # set PYTHONNOUSERSITE so child process will ignore user site-packages
    os.environ["PYTHONNOUSERSITE"] = "1"


def patch_startup():
    """
    A collection of patches on process startup
    This function is supposed to be called in entry file (outside `if __name__ == "__main__":`)
        so subprocesses can be patched too

    It's also recommended to launch with
        python -s -OO gui.py
    "-s" to ignore user site-packages
    "-OO" to drop assert and docstring at runtime
    """
    patch_environ()
    patch_std()