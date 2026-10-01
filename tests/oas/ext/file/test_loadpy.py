import _io
import pytest

from oas.ext.file.loadpy import LOADPY_CACHE, loadpy
from oas.testing.filesystem import fs  # noqa: F401


def test_loadpy_valid(fs):
    """
    Test loadpy with a valid .py file
    """
    fs.create_file('/valid.py', contents='a = 1\ndef func(): return 2')

    with fs.patch_open_code():
        module = loadpy('/valid.py')

    assert module.a == 1
    assert module.func() == 2
    assert module.__name__ == 'valid'


def test_loadpy_invalid_extension(fs):
    """
    Test loadpy with an invalid file extension
    """
    fs.create_file('/invalid.txt', contents='a = 1')

    with pytest.raises(ImportError, match='Not a ".py" file'):
        loadpy('/invalid.txt')


def test_loadpy_non_existent(fs):
    """
    Test loadpy with a non-existent file
    """
    with fs.patch_open_code(), pytest.raises(ImportError):
        loadpy('/non_existent.py')


def test_loadpy_relative_import(fs):
    """
    Test loadpy with a file containing relative imports
    """
    fs.create_file('/relative.py', contents='from . import something')

    with fs.patch_open_code(), pytest.raises(ImportError, match='cannot load files that has relative import syntax'):
        loadpy('/relative.py')


def test_loadpy_directory(fs):
    """
    Test loadpy with a directory path
    """
    fs.create_dir('/dir.py')

    with fs.patch_open_code(), pytest.raises(ImportError):
        loadpy('/dir.py')


def test_loadpy_independent_modules(fs):
    """
    Test that each loadpy call creates a new module
    """
    fs.create_file('/independent.py', contents='a = 1')

    with fs.patch_open_code():
        module1 = loadpy('/independent.py')
        module2 = loadpy('/independent.py')

    assert module1 is not module2
    module1.a = 2
    assert module2.a == 1


def test_loadpy_cache(fs):
    """
    Test LOADPY_CACHE caching behavior
    """
    # clear the global cache so a previous run cannot leak into this test
    LOADPY_CACHE.gc()
    fs.create_file('/cached.py', contents='a = 1')

    with fs.patch_open_code():
        # First load
        module1 = LOADPY_CACHE.get('/cached.py')
        assert module1.a == 1

        # Second load from cache
        module2 = LOADPY_CACHE.get('/cached.py')
        assert module1 is module2

        # GC clears cache
        LOADPY_CACHE.gc()
        module3 = LOADPY_CACHE.get('/cached.py')
        assert module3 is not module1
        assert module3.a == 1


def test_loadpy_syntax_error(fs):
    """
    Test loadpy with a file containing syntax error
    """
    fs.create_file('/syntax_error.py', contents='if True')

    with fs.patch_open_code(), pytest.raises(ImportError, match='Could not load file'):
        loadpy('/syntax_error.py')


def test_loadpy_permission_error_directory(fs, monkeypatch):
    """
    Test loadpy with a directory that raises PermissionError
    """
    # On the real disk Windows raises PermissionError when opening a directory,
    # the fake fs raises IsADirectoryError instead, so simulate it here
    fs.create_dir('/perm_dir.py')
    monkeypatch.setattr(
        _io,
        'open_code',
        lambda path: (_ for _ in ()).throw(PermissionError(13, 'Permission denied', path))
    )

    with pytest.raises(ImportError, match='Filepath to load is not a file'):
        loadpy('/perm_dir.py')


def test_loadpy_permission_error_file(fs, monkeypatch):
    """
    Test loadpy with a file that raises PermissionError
    """
    fs.create_file('/perm_file.py', contents='a = 1')
    monkeypatch.setattr(
        _io,
        'open_code',
        lambda path: (_ for _ in ()).throw(PermissionError(13, 'Permission denied', path))
    )

    with pytest.raises(ImportError, match='Permission denied'):
        loadpy('/perm_file.py')


def test_loadpy_import_error_reraises(fs):
    """
    Test loadpy re-raises the original ImportError when it is not a relative import
    """
    fs.create_file('/bad_import.py', contents='import definitely_missing_module_xyz')

    with fs.patch_open_code(), pytest.raises(ModuleNotFoundError, match='definitely_missing_module_xyz'):
        loadpy('/bad_import.py')


def test_loadpy_multiple_dots(fs):
    """
    Test loadpy with a file name containing multiple dots
    """
    fs.create_file('/foo.bar.py', contents='a = 1')

    with fs.patch_open_code():
        module = loadpy('/foo.bar.py')

    assert module.a == 1
    # get_stem("foo.bar.py") -> "foo.bar"
    assert module.__name__ == 'foo.bar'
