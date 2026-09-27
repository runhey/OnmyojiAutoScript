import os

WINDOWS_SEP = os.sep == '\\'


def normpath(path: str) -> str:
    """
    Normalize whatever to seperator "/"
    """
    if WINDOWS_SEP:
        # In most cases just normpath('xxx.png') check '/' first to be faster
        if '\\' in path:
            return path.rstrip('\\/').replace('\\', '/')
        else:
            return path.rstrip('\\/')
    else:
        return path.rstrip('/')


def joinpath(root: str, path: str) -> str:
    """
    Equivalent to os.path.join(self, path)
    Cannot handle "./" and "../", if you need "../" use uppath() instead

    Args:
        root: Base path, needs to be normalized first
        path: Relative path, needs to be normalized first

    Returns:
        str:
    """
    if root:
        if path:
            if root == '/':
                # linux root, don't create '//path'
                return f'/{path}'
            else:
                return f'{root}/{path}'
        else:
            return root
    else:
        return path


def joinnormpath(root: str, path: str) -> str:
    """
    Equivalent to joinpath(root, normpath(path))
    Reduce python function call to be about 0.1us faster

    Args:
        root: Base path, needs to be normalized first
        path: Relative path

    Returns:
        str:
    """
    if WINDOWS_SEP:
        # In most cases just normpath('xxx.png') check '/' first to be faster
        if '\\' in path:
            path = path.rstrip('\\/').replace('\\', '/')
        else:
            path = path.rstrip('\\/')
    else:
        path = path.rstrip('/')

    if root:
        if path:
            return f'{root}/{path}'
        else:
            return root
    else:
        return path


def uppath(root: str, up: int = 1) -> str:
    """
    Equivalent to os.path.join(self, '../')

    Args:
        root: Base path, needs to be normalized first
        up: Directory upward level

    Returns:
        str:
    """
    if WINDOWS_SEP:
        for _ in range(up):
            root, _, _ = root.rpartition('/')
            # Relative path can only up to empty string
            if not root:
                return ''
            # Absolute path can only up to "C:"
            elif root.endswith(':'):
                break
        return root
    else:
        is_absolute = root.startswith('/')
        for _ in range(up):
            root, _, _ = root.rpartition('/')
            if not root:
                if is_absolute:
                    # Absolute path can only up to "/"
                    return '/'
                else:
                    # Relative path can only up to empty string
                    return ''
        return root


def is_abspath(path: str) -> bool:
    """
    A simplified os.path.isabs()
    """
    if WINDOWS_SEP:
        try:
            return path[1] == ':'
        except IndexError:
            return False
    else:
        return path.startswith('/')


def abspath(path: str) -> str:
    """
    A simplified os.path.abspath()
    Note that, to improve performance, this method should be used less
    """
    if is_abspath(path):
        return path
    root = os.getcwd()
    return joinpath(root, path)


def to_posix(path):
    """
    Convert to posix path

    Args:
        path (str):

    Returns:
        str:
    """
    return path.replace('\\', '/')


def to_python_import(path):
    """
    Convert path to python dot-like import
    path/to/python.py -> path.to.python

    Args:
        path (str):

    Returns:
        str:
    """
    if path.endswith('.py'):
        path = path[:-3]
    if WINDOWS_SEP:
        path = path.strip('\\/')
        if '\\' in path:
            path = path.replace('\\', '.')
    else:
        path = path.strip('/')
    if '/' in path:
        path = path.replace('/', '.')
    return path


def subpath_to(path, root):
    """
    Calculate sub-path to `root`.
    If `path` is not sub-path to `root`, return `path`

    Args:
        path (str): Normalized path
        root (str): Normalized path

    Returns:
        str:
    """
    if path.startswith(root):
        path = path[len(root):]
        if WINDOWS_SEP:
            return path.lstrip('\\/')
        else:
            return path.lstrip('/')
    else:
        return path


def get_name(path: str) -> str:
    """
    /abc/def.png -> def.png
    /abc/def     -> def
    /abc/.git    -> .git
    """
    if '/' in path:
        _, _, path = path.rpartition('/')
    return path


def get_stem(path: str) -> str:
    """
    /abc/def.png -> def
    /abc/def     -> def
    /abc/.git    -> ""
    """
    if '/' in path:
        _, _, path = path.rpartition('/')
    stem, dot, _ = path.rpartition('.')
    if dot:
        return stem
    else:
        return path


def get_rootstem(path: str) -> str:
    """
    /abc/def.part1.png -> def
    /abc/def.png -> def
    /abc/def     -> def
    /abc/.git    -> ""
    """
    if '/' in path:
        _, _, path = path.rpartition('/')
    stem, dot, _ = path.partition('.')
    if dot:
        return stem
    else:
        return path


def get_suffix(path: str) -> str:
    """
    /abc/def.png -> .png
    /abc/def     -> ""
    /abc/.git    -> .git
    """
    if '/' in path:
        _, _, path = path.rpartition('/')
    path, dot, suffix = path.rpartition('.')
    if dot:
        return dot + suffix
    return path


def get_multisuffix(path: str) -> str:
    """
    /abc/def.part1.png -> .part1.png
    /abc/def.png -> .png
    /abc/def     -> ""
    /abc/.git    -> .git
    """
    if '/' in path:
        _, _, path = path.rpartition('/')
    _, dot, suffix = path.partition('.')
    if dot:
        return dot + suffix
    else:
        return ''


def with_name(path: str, name: str) -> str:
    """
    /abc/def.png -> /abc/xxx
    /abc/def     -> /abc/xxx
    /abc/.git    -> /abc/xxx
    """
    root, sep, _ = path.rpartition('/')
    if sep:
        return f'{root}{sep}{name}'
    else:
        return name


def with_stem(path: str, stem: str) -> str:
    """
    /abc/def.png -> /abc/xxx.png
    /abc/def     -> /abc/xxx
    /abc/.git    -> /abc/xxx.git
    """
    root, sep, name = path.rpartition('/')
    _, dot, suffix = name.rpartition('.')
    if sep:
        if dot:
            return f'{root}{sep}{stem}.{suffix}'
        else:
            return f'{root}{sep}{stem}'
    else:
        if dot:
            return f'{stem}.{suffix}'
        else:
            return stem


def with_rootstem(path: str, stem: str) -> str:
    """
    /abc/def.part1.png -> /abc/xxx.part1.png
    /abc/def.png -> /abc/xxx.png
    /abc/def     -> /abc/xxx
    /abc/.git    -> /abc/xxx.git
    """
    root, sep, name = path.rpartition('/')
    _, dot, suffix = name.partition('.')
    if sep:
        if dot:
            return f'{root}{sep}{stem}.{suffix}'
        else:
            return f'{root}{sep}{stem}'
    else:
        if dot:
            return f'{stem}.{suffix}'
        else:
            return stem


def with_suffix(path: str, suffix: str) -> str:
    """
    /abc/def.png -> /abc/def.xxx
    /abc/def     -> /abc/def.xxx
    /abc/.git    -> /abc/.xxx
    """
    root, sep, name = path.rpartition('/')
    stem, dot, _ = name.rpartition('.')
    if sep:
        if dot:
            return f'{root}{sep}{stem}{suffix}'
        else:
            return f'{root}{sep}{name}{suffix}'
    else:
        if dot:
            return f'{stem}{suffix}'
        else:
            return suffix


def with_multisuffix(path: str, suffix: str) -> str:
    """
    /abc/def.part1.png -> /abc/def.xxx.xxx
    /abc/def     -> /abc/def.xxx
    /abc/.git    -> /abc/.xxx
    """
    root, sep, name = path.rpartition('/')
    stem, dot, _ = name.partition('.')
    if sep:
        if dot:
            return f'{root}{sep}{stem}{suffix}'
        else:
            return f'{root}{sep}{name}{suffix}'
    else:
        if dot:
            return f'{stem}{suffix}'
        else:
            return suffix
