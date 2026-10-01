import ctypes

from oas.ext.cache.resource import ResourceCache
from oas.ext.path.calc import get_suffix


def loaddll(file, use_windll=False):
    """
    Dynamically load a DLL or shared library file (.dll, .so, .dylib).

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
    suffix = get_suffix(file).lower()
    if suffix not in ('.dll', '.so', '.dylib'):
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


class LoaddllCache(ResourceCache["ctypes.CDLL"]):
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
