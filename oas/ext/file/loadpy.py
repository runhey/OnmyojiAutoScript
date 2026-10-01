import os.path
import types

from oas.ext.cache.resource import ResourceCache
from oas.ext.path.calc import get_stem


def loadpy(file):
    """
    Dynamically load a python file.
    Note that you should use this function very carefully, remember:
        1. Target python file cannot have relative import syntax like "from . import xxx"
            because it has no parent package.
        2. You should always use the module in the minimum scope.
            If you do:
                obj.data = module.data
            the entire module won't get garbage collected, because it's referenced. You will have memory leak.
        3. Each loadpy() call will create a new module, even if they load the same file.
            To avoid duplicate module and to be threadsafe, use class LoadpyCache.

    Args:
        file (str): Absolute filepath to python file

    Returns:
        a python module object

    Raises:
        ImportError: if encounter any error
    """
    # file can't be subclasses of str
    file = str(file)
    if not file.endswith('.py'):
        raise ImportError('Not a ".py" file')
    name = get_stem(file)

    import importlib.util

    # create spec
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None:
        # path invalid or not endswith .py
        raise ImportError(f'Could not create import spec for file "{file}"')
    if spec.loader is None:
        raise ImportError(f'Could not create spec.loader for file "{file}"')

    # create module object
    # may raise ImportError('loaders that define exec_module() must also define create_module()')
    module = importlib.util.module_from_spec(spec)

    # import
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError as e:
        # no such file
        raise ImportError(str(e))
    except PermissionError as e:
        if os.path.isdir(file):
            # target is a directory
            raise ImportError(f'Filepath to load is not a file {file}')
        else:
            # other permission errors
            raise ImportError(str(e))
    except ImportError as e:
        msg = str(e)
        if 'no known parent package' in msg:
            # ImportError: attempted relative import with no known parent package
            raise ImportError(
                f'loadpy() cannot load files that has relative import syntax like "from . import xxx", {e}') from e
        else:
            raise
    except Exception as e:
        raise ImportError(f'Could not load file "{file}", {e}') from e

    return module


class LoadpyCache(ResourceCache[types.ModuleType]):
    def load_resource(self, file: str, **kwargs):
        return loadpy(file)


LOADPY_CACHE = LoadpyCache()
