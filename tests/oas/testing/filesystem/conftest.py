# The fs fixture is not registered here: every test module imports it
# explicitly (from alasio.testing.filesystem import fs), see the usage
# notes in alasio/testing/filesystem/__init__.py.
from oas.ext.path.calc import joinpath


def join(fs, *parts):
    """
    Build a normalized absolute path under the fake root.

    joinpath() keeps the POSIX root "/" as it is, a plain f-string would
    build "//a/b" out of the root and the first part.

    Args:
        fs (FakeFilesystem): Fake filesystem
        *parts (str): Path parts

    Returns:
        str: Absolute path string
    """
    path = fs.root_dir.path
    for part in parts:
        path = joinpath(path, part)
    return path
