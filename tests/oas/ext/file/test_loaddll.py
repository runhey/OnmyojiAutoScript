import ctypes
import os

import pytest

from oas.ext.file.loaddll import LOADDLL_CACHE, loaddll
from oas.testing.filesystem import fs  # noqa: F401


def test_loaddll_invalid_extension(fs):
    """
    Test loaddll with an invalid file extension
    """
    fs.create_file('/invalid.txt', contents='dummy')

    with pytest.raises(ImportError, match='Not a library file'):
        loaddll('/invalid.txt')


def test_loaddll_non_existent(fs):
    """
    Test loaddll with a non-existent file
    """
    # The path is guaranteed to not exist in the fake filesystem
    with pytest.raises(ImportError):
        loaddll('/oas_non_existent_dll_test.dll')


def test_loaddll_generic_exception(monkeypatch):
    """
    Test loaddll wraps unexpected exceptions into ImportError
    """
    def raiser(*args, **kwargs):
        raise ValueError('boom')

    monkeypatch.setattr(ctypes, 'CDLL', raiser)

    with pytest.raises(ImportError, match='Could not load library'):
        loaddll('/test.dll')


@pytest.mark.skipif(os.name != 'nt', reason="Windows only test")
def test_loaddll_windows_kernel32():
    """
    Test loaddll with kernel32.dll on Windows
    """
    # Use absolute path to bypass any search path issues and match loadpy behavior
    path = "C:\\Windows\\System32\\kernel32.dll"
    if not os.path.exists(path):
        pytest.skip("kernel32.dll not found at expected path")

    lib = loaddll(path)
    assert isinstance(lib, ctypes.CDLL)
    # GetTickCount is a common function in kernel32.dll
    assert lib.GetTickCount() > 0


@pytest.mark.skipif(os.name == 'nt', reason="Linux/Mac only test")
def test_loaddll_linux_libc():
    """
    Test loaddll with libc on Linux/Mac
    """
    # Common paths for libc
    paths = ["/lib/x86_64-linux-gnu/libc.so.6", "/lib/libc.so.6", "/usr/lib/libc.dylib"]
    path = None
    for p in paths:
        if os.path.exists(p):
            path = p
            break

    if path is None:
        pytest.skip("libc not found at expected paths")

    lib = loaddll(path)
    assert isinstance(lib, ctypes.CDLL)


@pytest.mark.skipif(os.name != 'nt', reason="Windows only test")
def test_loaddll_windows_user32_windll():
    """
    Test loaddll with user32.dll and use_windll=True on Windows
    """
    path = "C:\\Windows\\System32\\user32.dll"
    if not os.path.exists(path):
        pytest.skip("user32.dll not found")

    # user32.dll uses stdcall, loading with WinDLL is appropriate
    lib = loaddll(path, use_windll=True)
    assert isinstance(lib, ctypes.WinDLL)
    # MessageBoxA is a common function in user32.dll
    assert lib.GetDesktopWindow() > 0


def test_loaddll_cache():
    """
    Test LOADDLL_CACHE caching behavior
    """
    # We use kernel32.dll for cache test on Windows as it's reliable
    if os.name == 'nt':
        path = "C:\\Windows\\System32\\kernel32.dll"
        if not os.path.exists(path):
            pytest.skip("kernel32.dll not found")
    else:
        # Try to find a libc on Linux
        paths = ["/lib/x86_64-linux-gnu/libc.so.6", "/lib/libc.so.6", "/usr/lib/libc.dylib"]
        path = None
        for p in paths:
            if os.path.exists(p):
                path = p
                break
        if path is None:
            pytest.skip("No library found for testing cache")

    # First load
    lib1 = LOADDLL_CACHE.get(path)
    assert isinstance(lib1, ctypes.CDLL)

    # Second load from cache
    lib2 = LOADDLL_CACHE.get(path)
    assert lib1 is lib2

    # GC clears cache
    LOADDLL_CACHE.gc()
    lib3 = LOADDLL_CACHE.get(path)
    # ctypes.CDLL(path) creates a new object every time
    assert lib3 is not lib1
