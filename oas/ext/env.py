import os
import sys

from oas.ext.path import PathStr

# Operating System
POSIX = os.name == "posix"
WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
MACOS = sys.platform.startswith("darwin")
OSX = MACOS  # deprecated alias
FREEBSD = sys.platform.startswith(("freebsd", "midnightbsd"))
OPENBSD = sys.platform.startswith("openbsd")
NETBSD = sys.platform.startswith("netbsd")
BSD = FREEBSD or OPENBSD or NETBSD
SUNOS = sys.platform.startswith(("sunos", "solaris"))
AIX = sys.platform.startswith("aix")

# Global variable
PROJECT_ROOT = PathStr.new('')
OAS_ROOT = PathStr.new(__file__).uppath(3)


def set_project_root(root, up=0):
    """
    Args:
        root (str):
        up (int):
    """
    root = PathStr.new(root)
    if up:
        root = root.uppath(up)
    global PROJECT_ROOT
    PROJECT_ROOT = root