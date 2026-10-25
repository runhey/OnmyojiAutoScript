import ctypes
import re

from oas.ext.cache.resource import ResourceCache


def loaddll(file, use_windll=False):
    """
    Dynamically load a DLL or shared library file (.dll, .dylib, .so, .so.6, ...).

    Args:
        file (str): Absolute filepath to the library file
        use_windll (bool): Use ctypes.WinDLL instead of ctypes.CDLL on Windows.
            Defaults to False.

    Returns:
        ctypes.CDLL: A loaded library object

    Raises:
        ImportError: If the file cannot be loaded or is not a library file
    """
    file = str(file)
    # Versioned shared objects are the normal form on Linux (libc.so.6, libpython3.8.so.1.0)
    # and on macOS (libSystem.B.dylib), so a bare .so suffix would reject system libraries
    if not re.search(r'\.(?:dll|dylib|so(?:\.\d+)*)\Z', file, re.IGNORECASE):
        raise ImportError(f'Not a library file: "{file}"')

    try:
        if use_windll and hasattr(ctypes, 'WinDLL'):
            return ctypes.WinDLL(file)
        else:
            return ctypes.CDLL(file)
    except OSError as e:
        # OSError: [WinError 126] The specified module could not be found
        # OSError: [WinError 193] %1 is not a valid Win32 application
        raise ImportError(str(e))
    except Exception as e:
        raise ImportError(f'Could not load library "{file}": {str(e)}')


class LoaddllCache(ResourceCache['ctypes.CDLL']):
    def load_resource(self, file, **kwargs):
        """
        Load library directly.

        Args:
            file (str): Source file path
            **kwargs: Arguments passed to loaddll()

        Returns:
            ctypes.CDLL: Loaded library object
        """
        return loaddll(file, **kwargs)


LOADDLL_CACHE = LoaddllCache()
