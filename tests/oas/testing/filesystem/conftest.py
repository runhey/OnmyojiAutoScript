# The fs fixture is not registered here: every test module imports it
# explicitly (from oas.testing.filesystem import fs), see the usage
# notes in alasio/testing/filesystem/__init__.py.


def join(fs, *parts):
    """
    Build a normalized absolute path under the fake root.

    Args:
        fs (FakeFilesystem): Fake filesystem
        *parts (str): Path parts

    Returns:
        str: Absolute path string
    """
    path = fs.root_dir.path
    for part in parts:
        path = f'{path}/{part}'
    return path
