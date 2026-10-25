"""
Tests for oas.ext.path.calc.

calc.py is the string based path calculation core under PathStr, and is a
simplified and faster replacement of pathlib / os.path rather than an
equivalent of it. The tests here do two jobs:

- cover every function and every platform branch. calc selects its behavior
  with the module level WINDOWS_SEP, the tests force it to True and False so
  the Windows and the POSIX branch are both exercised on every platform (the
  same approach as the tests of oas.ext.path.atomic)
- pin the deviations from pathlib / os.path as characterization tests, so a
  behavior change becomes visible. The deviations and their reasons are
  documented in doc/2026-10-10_calc-tests-and-pathlib-deviations.md

The path in / path out functions expect normalized input (normpath() applied,
separator "/"), like PathStr does. Unnormalized input is still pinned in a few
cases to show what the functions do with it.
"""
import os

import pytest

from oas.ext.path import calc
from oas.ext.path.calc import (
    abspath, get_multisuffix, get_name, get_rootstem, get_stem, get_suffix, is_abspath, joinnormpath, joinpath,
    normpath, subpath, subpath_to, to_posix, to_python_import, uppath, with_multisuffix, with_name, with_rootstem,
    with_stem, with_suffix
)


class TestNormpathWhenWindows:
    """normpath() on the Windows branch, backslash is a separator."""

    @pytest.fixture(autouse=True)
    def windows_sep(self, monkeypatch):
        """Force the Windows branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)

    @pytest.mark.parametrize("path, expected", [
        ('', ''),
        ('a', 'a'),
        # Trailing separators are removed
        ('a/', 'a'),
        ('a\\', 'a'),
        ('a//', 'a'),
        ('a\\\\', 'a'),
        ('a/\\/', 'a'),
        # Backslash is converted to "/"
        ('a\\b', 'a/b'),
        ('a\\b\\c', 'a/b/c'),
        ('a\\b/', 'a/b'),
        ('a/b\\', 'a/b'),
        # Deviation: duplicate separators are not folded (unlike pathlib),
        # only trailing ones are removed
        ('a//b', 'a//b'),
        ('a\\b//c', 'a/b//c'),
        ('C:\\Users\\x\\', 'C:/Users/x'),
        ('C:/Users/x/', 'C:/Users/x'),
        # Only separators are removed, "C:" keeps its drive colon
        ('C:\\', 'C:'),
        ('C:', 'C:'),
        # A bare root keeps the root as "/" instead of becoming an empty string
        ('/', '/'),
        ('\\', '/'),
        # Deviation: "//" is collapsed, os.path.normpath would keep it on POSIX
        ('//', '/'),
        ('\\\\', '/'),
        # A leading "//" of a UNC path is not a separator to strip
        ('\\\\server\\share\\', '//server/share'),
        # Unicode path
        ('中文/图片\\', '中文/图片'),
    ])
    def test_normpath(self, path, expected):
        """Whatever input should end as a "/" separated path without trailing separators."""
        assert normpath(path) == expected


class TestNormpathWhenPosix:
    """normpath() on the POSIX branch, backslash is a regular character."""

    @pytest.fixture(autouse=True)
    def posix_sep(self, monkeypatch):
        """Force the POSIX branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)

    @pytest.mark.parametrize("path, expected", [
        ('', ''),
        ('a', 'a'),
        ('a/', 'a'),
        ('a//', 'a'),
        ('/a/b/', '/a/b'),
        # Deviation: duplicate separators are not folded (unlike pathlib),
        # only trailing ones are removed
        ('a//b', 'a//b'),
        ('/a///b/', '/a///b'),
        # Backslash is not a separator, it stays untouched
        ('a\\', 'a\\'),
        ('a\\b', 'a\\b'),
        # A bare root keeps the root as "/" (os.path.normpath agrees)
        ('/', '/'),
        # Deviation: "//" is collapsed, os.path.normpath would keep it as "//"
        ('//', '/'),
        ('///', '/'),
        # No platform detection, a Windows path is not converted
        ('C:/x/', 'C:/x'),
        ('C:\\x\\', 'C:\\x\\'),
    ])
    def test_normpath(self, path, expected):
        """Only trailing "/" are removed, backslash is kept as is."""
        assert normpath(path) == expected


class TestJoinpath:
    """joinpath() is a plain "/" join of two already normalized paths."""

    @pytest.mark.parametrize("root, path, expected", [
        # Empty operands
        ('', '', ''),
        ('', 'a', 'a'),
        ('', '/a', '/a'),
        ('a', 'b', 'a/b'),
        ('/a', 'b', '/a/b'),
        ('a/b', 'c/d', 'a/b/c/d'),
        ('C:', 'a', 'C:/a'),
        # Deviation: os.path.join('a', '') returns 'a/', joinpath returns 'a'
        ('a', '', 'a'),
        # Linux root is special cased, no '//path'
        ('/', 'a', '/a'),
        ('/', 'a/b', '/a/b'),
        ('/', '', '/'),
        # Deviation: an absolute path is not recognized and not joined as a replacement,
        # os.path.join('a', '/b') returns '/b', os.path.join('/', '/a') returns '/'
        ('a', '/b', 'a//b'),
        ('/', '/a', '//a'),
        # Deviation: root must be normalized first, otherwise a double separator is produced
        ('a/', 'b', 'a//b'),
    ])
    def test_joinpath(self, root, path, expected):
        """Result should be root and path joined by "/", root wins when path is empty."""
        assert joinpath(root, path) == expected


class TestJoinnormpathWhenWindows:
    """joinnormpath() on the Windows branch, path is normalized then joined."""

    @pytest.fixture(autouse=True)
    def windows_sep(self, monkeypatch):
        """Force the Windows branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)

    @pytest.mark.parametrize("root, path, expected", [
        # Empty operands
        ('', '', ''),
        ('', 'a/', 'a'),
        ('a', '', 'a'),
        ('a', 'b', 'a/b'),
        ('a', 'b/', 'a/b'),
        ('a', 'b//', 'a/b'),
        # The path is normalized with backslash converted
        ('a', 'b\\', 'a/b'),
        ('a', 'b\\c/', 'a/b/c'),
        ('a', 'b\\\\', 'a/b'),
        # Linux root is special cased, no '//path' (same as joinpath)
        ('/', 'a', '/a'),
        ('/', '', '/'),
        ('/a', 'b', '/a/b'),
        # Deviation: an absolute path is not recognized and not joined as a replacement
        ('/a', '/b', '/a//b'),
    ])
    def test_joinnormpath(self, root, path, expected):
        """Equivalent to joinpath(root, normpath(path)), with root already normalized."""
        assert joinnormpath(root, path) == expected


class TestJoinnormpathWhenPosix:
    """joinnormpath() on the POSIX branch, only trailing "/" are removed from path."""

    @pytest.fixture(autouse=True)
    def posix_sep(self, monkeypatch):
        """Force the POSIX branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)

    @pytest.mark.parametrize("root, path, expected", [
        ('', '', ''),
        ('', 'a/', 'a'),
        ('a', '', 'a'),
        ('a', 'b', 'a/b'),
        ('a', 'b/', 'a/b'),
        ('a', 'b//', 'a/b'),
        # Backslash is not a separator, it stays untouched
        ('a', 'b\\', 'a/b\\'),
        ('a', 'b\\c/', 'a/b\\c'),
        # Linux root is special cased, no '//path' (same as joinpath)
        ('/', 'a', '/a'),
        ('/', '', '/'),
        ('/a', 'b', '/a/b'),
        ('/a', '/b', '/a//b'),
    ])
    def test_joinnormpath(self, root, path, expected):
        """Equivalent to joinpath(root, normpath(path)), with root already normalized."""
        assert joinnormpath(root, path) == expected


class TestUppathWhenWindows:
    """uppath() on the Windows branch, a drive root "C:" is the top."""

    @pytest.fixture(autouse=True)
    def windows_sep(self, monkeypatch):
        """Force the Windows branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)

    @pytest.mark.parametrize("root, up, expected", [
        # up=0 keeps the path
        ('a', 0, 'a'),
        ('C:/a/b', 0, 'C:/a/b'),
        # Relative path can only go up to the empty string
        ('a', 1, ''),
        ('a/b', 1, 'a'),
        ('a/b', 2, ''),
        ('a/b/c', 1, 'a/b'),
        ('a/b/c/d', 2, 'a/b'),
        ('a/b/c', 5, ''),
        ('', 1, ''),
        # Absolute path can only go up to the drive "C:"
        ('C:/a/b', 1, 'C:/a'),
        ('C:/a/b', 2, 'C:'),
        ('C:/a/b', 9, 'C:'),
        ('C:/a', 5, 'C:'),
        # Deviation: "C:" itself goes up to the empty string
        ('C:', 1, ''),
        # Deviation: "/" is not absolute on this branch, it goes up to the empty string
        ('/', 1, ''),
        ('/a', 1, ''),
        ('/a/b', 1, '/a'),
        ('/a/b', 2, ''),
    ])
    def test_uppath(self, root, up, expected):
        """Going up should stop at the empty string or at the drive root."""
        assert uppath(root, up=up) == expected


class TestUppathWhenPosix:
    """uppath() on the POSIX branch, "/" is the top of an absolute path."""

    @pytest.fixture(autouse=True)
    def posix_sep(self, monkeypatch):
        """Force the POSIX branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)

    @pytest.mark.parametrize("root, up, expected", [
        ('a', 0, 'a'),
        # Relative path can only go up to the empty string
        ('a', 1, ''),
        ('a/b', 1, 'a'),
        ('a/b', 2, ''),
        ('/a', 1, '/'),
        # Absolute path can only go up to "/"
        ('/a/b', 1, '/a'),
        ('/a/b', 2, '/'),
        ('/a/b', 9, '/'),
        ('/', 1, '/'),
        ('//', 1, '/'),
        ('', 1, ''),
        # Deviation: a backslash path is not detectable, it is treated as one name
        ('a\\b', 1, ''),
        # Deviation: a Windows path is treated as a relative path,
        # there is no drive root to stop at, so it goes up to empty
        ('C:/a/b', 1, 'C:/a'),
        ('C:/a/b', 5, ''),
    ])
    def test_uppath(self, root, up, expected):
        """Going up should stop at the empty string, or at "/" for absolute paths."""
        assert uppath(root, up=up) == expected


class TestIsAbspathWhenWindows:
    """is_abspath() on the Windows branch, a drive colon decides."""

    @pytest.fixture(autouse=True)
    def windows_sep(self, monkeypatch):
        """Force the Windows branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)

    @pytest.mark.parametrize("path, expected", [
        ('', False),
        ('a', False),
        # Too short to have a drive colon
        ('C', False),
        ('C:/a', True),
        ('C:\\a', True),
        ('c:/a', True),
        ('C:', True),
        # Deviation: any "x:" prefix counts, ntpath.isabs() rejects these
        ('1:2', True),
        ('a:b', True),
        # Deviation: a slash rooted path is not absolute here, ntpath.isabs() accepts it
        ('/a', False),
        ('\\a', False),
        ('//a', False),
    ])
    def test_is_abspath(self, path, expected):
        """A path is absolute when the second character is a colon."""
        assert is_abspath(path) == expected


class TestIsAbspathWhenPosix:
    """is_abspath() on the POSIX branch, only "/" prefix counts."""

    @pytest.fixture(autouse=True)
    def posix_sep(self, monkeypatch):
        """Force the POSIX branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)

    @pytest.mark.parametrize("path, expected", [
        ('', False),
        ('a', False),
        ('/', True),
        ('/a', True),
        ('//a', True),
        # A Windows path is not absolute on POSIX
        ('C:/a', False),
        ('\\a', False),
    ])
    def test_is_abspath(self, path, expected):
        """A path is absolute when it starts with "/"."""
        assert is_abspath(path) == expected


class TestAbspathWhenWindows:
    """abspath() on the Windows branch, relative paths are joined with cwd."""

    @pytest.fixture(autouse=True)
    def fake_env(self, monkeypatch):
        """Force the Windows branch and a fixed cwd to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)
        # os.getcwd() returns backslash separated paths on Windows
        monkeypatch.setattr(os, 'getcwd', lambda: 'C:\\fake\\cwd')

    @pytest.mark.parametrize("path, expected", [
        # An absolute path is returned as is
        ('C:/a', 'C:/a'),
        ('C:\\a', 'C:\\a'),
        ('C:', 'C:'),
        # The cwd is normalized as well, the result is fully "/" separated
        ('a', 'C:/fake/cwd/a'),
        ('a/b', 'C:/fake/cwd/a/b'),
        # The cwd itself is returned when the path is empty
        ('', 'C:/fake/cwd'),
        # Deviation: "/a" is not absolute on the Windows branch, it is joined as well
        ('/a', 'C:/fake/cwd//a'),
    ])
    def test_abspath(self, path, expected):
        """Absolute paths should be kept, relative paths joined under the cwd."""
        assert abspath(path) == expected

    def test_abspath_cwd_drive_root(self, monkeypatch):
        """A drive root cwd should be normalized to "C:" and joined as usual."""
        monkeypatch.setattr(os, 'getcwd', lambda: 'C:\\')
        assert abspath('a') == 'C:/a'


class TestAbspathWhenPosix:
    """abspath() on the POSIX branch, relative paths are joined with cwd."""

    @pytest.fixture(autouse=True)
    def fake_env(self, monkeypatch):
        """Force the POSIX branch and a fixed cwd to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)
        monkeypatch.setattr(os, 'getcwd', lambda: '/fake/cwd')

    @pytest.mark.parametrize("path, expected", [
        ('/', '/'),
        ('/a', '/a'),
        ('/a/b', '/a/b'),
        ('a', '/fake/cwd/a'),
        ('a/b', '/fake/cwd/a/b'),
        ('', '/fake/cwd'),
        # A Windows path is not absolute on POSIX, it is joined under the cwd
        ('C:/a', '/fake/cwd/C:/a'),
    ])
    def test_abspath(self, path, expected):
        """Absolute paths should be kept, relative paths joined under the cwd."""
        assert abspath(path) == expected

    def test_abspath_cwd_is_root(self, monkeypatch):
        """A root cwd should keep the joined path under "/" instead of dropping it."""
        monkeypatch.setattr(os, 'getcwd', lambda: '/')
        assert abspath('a') == '/a'


class TestToPosix:
    """to_posix() converts backslashes, on every platform."""

    @pytest.mark.parametrize("path, expected", [
        ('a\\b', 'a/b'),
        ('a/b', 'a/b'),
        ('a\\b/c\\d', 'a/b/c/d'),
        ('', ''),
        ('\\', '/'),
        ('C:\\Users\\x', 'C:/Users/x'),
        # Deviation: backslash is converted even on POSIX, where it is
        # a valid character of a filename, pathlib keeps it as is
        ('a\\b\\c', 'a/b/c'),
    ])
    def test_to_posix(self, path, expected):
        """Backslash should always be replaced by "/"."""
        assert to_posix(path) == expected


class TestToPythonImportWhenWindows:
    """to_python_import() on the Windows branch, both separators are converted."""

    @pytest.fixture(autouse=True)
    def windows_sep(self, monkeypatch):
        """Force the Windows branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)

    @pytest.mark.parametrize("path, expected", [
        ('path/to/python.py', 'path.to.python'),
        ('path\\to\\python.py', 'path.to.python'),
        ('a.py', 'a'),
        ('.py', ''),
        # Only the ".py" suffix is removed
        ('a.pyc', 'a.pyc'),
        ('a.py.py', 'a.py'),
        # Leading and trailing separators are stripped
        ('/abs/a.py', 'abs.a'),
        ('a/b/', 'a.b'),
        # Deviation: a drive colon stays in the import name
        ('C:\\a\\b.py', 'C:.a.b'),
        ('C:/a/b.py', 'C:.a.b'),
        ('a\\b', 'a.b'),
        # "." is not handled, it stays in the name
        ('../a.py', '...a'),
        ('', ''),
    ])
    def test_to_python_import(self, path, expected):
        """A path should be converted to a dot separated python import."""
        assert to_python_import(path) == expected


class TestToPythonImportWhenPosix:
    """to_python_import() on the POSIX branch, only "/" is converted."""

    @pytest.fixture(autouse=True)
    def posix_sep(self, monkeypatch):
        """Force the POSIX branch to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)

    @pytest.mark.parametrize("path, expected", [
        ('path/to/python.py', 'path.to.python'),
        ('a.py', 'a'),
        ('.py', ''),
        ('/abs/a.py', 'abs.a'),
        # Backslash is a regular character on POSIX, it is not converted
        ('path\\to\\python.py', 'path\\to\\python'),
        ('a\\b', 'a\\b'),
        ('../a.py', '...a'),
    ])
    def test_to_python_import(self, path, expected):
        """A path should be converted to a dot separated python import."""
        assert to_python_import(path) == expected


class TestSubpathTo:
    """subpath_to() is platform independent, the separator is always "/"."""

    @pytest.mark.parametrize("path, root, expected", [
        # Sub-path cases
        ('/a/b/c', '/a/b', 'c'),
        ('/a/b/c', '/a/b/', 'c'),
        ('/a/b/c', '/a', 'b/c'),
        ('/a/b', '/a/b', ''),
        ('/a/b/c', '/', 'a/b/c'),
        ('/a/b', '/', 'a/b'),
        ('a/b/c', 'a', 'b/c'),
        ('a/b', 'a', 'b'),
        # The empty path is the sub-path of an empty root
        ('', '', ''),
        # Not a sub-path, None is returned
        ('/x/y', '/a', None),
        ('/', '/a', None),
        ('/a/b', '', None),
        ('a', '', None),
        ('/', '', None),
        # A plain string prefix is not a sub-path
        ('/a/bc', '/a/b', None),
        ('ab', 'a', None),
        # Input should be normalized first, backslash is neither a separator
        # nor a boundary (same as the get_* functions)
        ('a\\b\\c', 'a', None),
        ('a\\b\\c', 'a\\', None),
        ('a\\b\\c', 'a\\b', None),
        ('a\\bc', 'a\\b', None),
        ('a/b/c', 'a\\b', None),
    ])
    def test_subpath_to(self, path, root, expected):
        """A sub-path should be stripped, a non sub-path should yield None."""
        assert subpath_to(path, root) == expected


class TestSubpath:
    """subpath() is the strict version of subpath_to(), a non sub-path raises."""

    @pytest.mark.parametrize("path, root, expected", [
        ('/a/b/c', '/a/b', 'c'),
        ('/a/b/c', '/a/b/', 'c'),
        ('/a/b/c', '/a', 'b/c'),
        ('/a/b', '/a/b', ''),
        ('/a/b/c', '/', 'a/b/c'),
        ('a/b/c', 'a', 'b/c'),
        ('', '', ''),
    ])
    def test_subpath(self, path, root, expected):
        """A sub-path should be stripped."""
        assert subpath(path, root) == expected

    @pytest.mark.parametrize("path, root", [
        ('/x/y', '/a'),
        ('/', '/a'),
        ('/a/b', ''),
        ('/', ''),
        ('', '/a'),
        ('/a/bc', '/a/b'),
        ('ab', 'a'),
        ('a\\b\\c', 'a\\b'),
    ])
    def test_subpath_not_a_sub_path(self, path, root):
        """A non sub-path should raise ValueError."""
        with pytest.raises(ValueError, match='Not a sub-path'):
            subpath(path, root)

    def test_error_message(self):
        """The ValueError should name the path and the root."""
        with pytest.raises(ValueError) as e:
            subpath('/x/y', '/a')
        assert str(e.value) == 'Not a sub-path: path="/x/y", root="/a"'


class TestGetName:
    """get_name() is platform independent, the separator is always "/"."""

    @pytest.mark.parametrize("path, expected", [
        ('/abc/def.png', 'def.png'),
        ('/abc/def', 'def'),
        ('/abc/.git', '.git'),
        ('def.png', 'def.png'),
        ('def', 'def'),
        ('.git', '.git'),
        ('a/b.c/d', 'd'),
        ('a/b.c', 'b.c'),
        ('def.', 'def.'),
        ('..', '..'),
        ('.', '.'),
        # Deviation: a trailing "/" yields an empty name (input is expected
        # normalized, normpath() removes trailing separators)
        ('a/', ''),
        ('/a/b/', ''),
        # Deviation: pathlib treats a bare root as name '', so does this
        ('/', ''),
        ('', ''),
        # Deviation: backslash is not a separator here, even on Windows,
        # input should be normalized with normpath() first
        ('a\\b', 'a\\b'),
    ])
    def test_get_name(self, path, expected):
        """The last "/" separated component should be returned."""
        assert get_name(path) == expected


class TestGetStem:
    """get_stem() drops the last extension of the name."""

    @pytest.mark.parametrize("path, expected", [
        ('/abc/def.png', 'def'),
        ('/abc/def', 'def'),
        # Deviation: pathlib keeps ".git" as the stem, here it is treated as
        # a dotfile whose stem is empty (documented in the docstring)
        ('/abc/.git', ''),
        ('.git', ''),
        ('def.png', 'def'),
        ('def', 'def'),
        ('def.part1.png', 'def.part1'),
        ('a.b.c', 'a.b'),
        ('a/b.c/d', 'd'),
        # Deviation: pathlib keeps "def." as the stem, the trailing dot is
        # an empty extension here
        ('def.', 'def'),
        ('..', '.'),
        ('.', ''),
        ('...', '..'),
        ('a/', ''),
        ('/', ''),
        ('', ''),
        # Input should be normalized first
        ('a\\b.png', 'a\\b'),
    ])
    def test_get_stem(self, path, expected):
        """The name without its last extension should be returned."""
        assert get_stem(path) == expected


class TestGetRootstem:
    """get_rootstem() drops all extensions of the name."""

    @pytest.mark.parametrize("path, expected", [
        ('/abc/def.part1.png', 'def'),
        ('/abc/def.png', 'def'),
        ('/abc/def', 'def'),
        ('/abc/.git', ''),
        ('.git', ''),
        ('.git.png', ''),
        ('def.part1.png', 'def'),
        ('a.b.c', 'a'),
        ('def.', 'def'),
        ('a/b.c/d', 'd'),
        ('..', ''),
        ('a/', ''),
        ('/', ''),
        ('', ''),
        ('a\\b.png', 'a\\b'),
    ])
    def test_get_rootstem(self, path, expected):
        """The name before the first dot should be returned."""
        assert get_rootstem(path) == expected


class TestGetSuffix:
    """get_suffix() returns the last extension, leading dot included."""

    @pytest.mark.parametrize("path, expected", [
        ('/abc/def.png', '.png'),
        ('/abc/def', ''),
        # Deviation: pathlib returns no suffix for a dotfile, here the whole
        # name becomes the suffix (documented in the docstring)
        ('/abc/.git', '.git'),
        ('.git', '.git'),
        ('def.png', '.png'),
        ('def', ''),
        ('def.part1.png', '.png'),
        ('a.b.c', '.c'),
        ('a/b.c/d', ''),
        # Deviation: pathlib returns no suffix for a trailing dot, here the
        # suffix is the dot itself
        ('def.', '.'),
        ('..', '.'),
        ('.', '.'),
        ('...', '.'),
        ('a/', ''),
        ('/', ''),
        ('', ''),
        ('a\\b', ''),
    ])
    def test_get_suffix(self, path, expected):
        """The last extension with its dot should be returned."""
        assert get_suffix(path) == expected


class TestGetMultisuffix:
    """get_multisuffix() returns all extensions from the first dot of the name."""

    @pytest.mark.parametrize("path, expected", [
        ('/abc/def.part1.png', '.part1.png'),
        ('/abc/def.png', '.png'),
        ('/abc/def', ''),
        ('/abc/.git', '.git'),
        ('.git', '.git'),
        ('.git.png', '.git.png'),
        ('def.part1.png', '.part1.png'),
        ('a.b.c', '.b.c'),
        ('a/b.c/d', ''),
        ('def.', '.'),
        ('..', '..'),
        ('.', '.'),
        ('a/', ''),
        ('/', ''),
        ('', ''),
        ('a\\b', ''),
    ])
    def test_get_multisuffix(self, path, expected):
        """All extensions from the first dot of the name should be returned."""
        assert get_multisuffix(path) == expected


class TestWithName:
    """with_name() replaces the last "/" separated component."""

    @pytest.mark.parametrize("path, name, expected", [
        ('/abc/def.png', 'xxx', '/abc/xxx'),
        ('/abc/def', 'xxx', '/abc/xxx'),
        ('/abc/.git', 'xxx', '/abc/xxx'),
        ('def', 'xxx', 'xxx'),
        ('', 'xxx', 'xxx'),
        ('a/b.c/d', 'xxx', 'a/b.c/xxx'),
        # Deviation: input is expected normalized, a trailing "/" makes the
        # new name a new component instead of replacing the old one
        ('a/b/', 'xxx', 'a/b/xxx'),
        # Input should be normalized first, a backslash path is one name
        ('a\\b\\c', 'xxx', 'xxx'),
    ])
    def test_with_name(self, path, name, expected):
        """The last component should be replaced by the new name."""
        assert with_name(path, name) == expected


class TestWithStem:
    """with_stem() replaces the name without its last extension."""

    @pytest.mark.parametrize("path, stem, expected", [
        ('/abc/def.png', 'xxx', '/abc/xxx.png'),
        ('/abc/def', 'xxx', '/abc/xxx'),
        ('/abc/.git', 'xxx', '/abc/xxx.git'),
        ('def', 'xxx', 'xxx'),
        ('def.png', 'xxx', 'xxx.png'),
        # Deviation: pathlib replaces only the last extension too, ".part1"
        # belongs to the stem of "def.part1.png" and gets dropped
        ('def.part1.png', 'xxx', 'xxx.png'),
        # Only the last extension is kept, like get_stem()
        ('a.b.c', 'x', 'x.c'),
        ('', 'xxx', 'xxx'),
        # Deviation: the empty extension of a trailing dot is kept
        ('/abc/def.', 'xxx', '/abc/xxx.'),
        # Input should be normalized first, a backslash path is one name
        ('a\\b\\def.png', 'xxx', 'xxx.png'),
    ])
    def test_with_stem(self, path, stem, expected):
        """The last extension should be kept, the stem before it replaced."""
        assert with_stem(path, stem) == expected


class TestWithRootstem:
    """with_rootstem() replaces the name before its first dot."""

    @pytest.mark.parametrize("path, stem, expected", [
        ('/abc/def.part1.png', 'xxx', '/abc/xxx.part1.png'),
        ('/abc/def.png', 'xxx', '/abc/xxx.png'),
        ('/abc/def', 'xxx', '/abc/xxx'),
        ('/abc/.git', 'xxx', '/abc/xxx.git'),
        ('def', 'xxx', 'xxx'),
        ('def.part1.png', 'xxx', 'xxx.part1.png'),
        ('a.b.c', 'xxx', 'xxx.b.c'),
        ('.git.png', 'xxx', 'xxx.git.png'),
        ('', 'xxx', 'xxx'),
        ('/abc/def.', 'xxx', '/abc/xxx.'),
        # Input should be normalized first, a backslash path is one name
        ('a\\b\\def.png', 'xxx', 'xxx.png'),
    ])
    def test_with_rootstem(self, path, stem, expected):
        """All extensions should be kept, the root stem replaced."""
        assert with_rootstem(path, stem) == expected


class TestWithSuffix:
    """with_suffix() replaces the last extension, the dot is part of the input."""

    @pytest.mark.parametrize("path, suffix, expected", [
        ('/abc/def.png', '.xxx', '/abc/def.xxx'),
        ('/abc/def', '.xxx', '/abc/def.xxx'),
        ('/abc/.git', '.xxx', '/abc/.xxx'),
        ('def', '.xxx', 'def.xxx'),
        ('def.png', '.xxx', 'def.xxx'),
        ('def.part1.png', '.xxx', 'def.part1.xxx'),
        ('a/b', '.c', 'a/b.c'),
        ('', '.xxx', '.xxx'),
        ('def.', '.xxx', 'def.xxx'),
        # Deviation: pathlib keeps "def." and appends, the trailing dot is
        # an extension here
        # Deviation: the suffix should contain its dot, otherwise it is
        # appended as is
        ('/abc/def.png', 'xxx', '/abc/defxxx'),
    ])
    def test_with_suffix(self, path, suffix, expected):
        """The last extension should be replaced, the extension is kept when there is none."""
        assert with_suffix(path, suffix) == expected


class TestWithMultisuffix:
    """with_multisuffix() replaces all extensions, the dot is part of the input."""

    @pytest.mark.parametrize("path, suffix, expected", [
        ('/abc/def.part1.png', '.xxx', '/abc/def.xxx'),
        ('/abc/def.png', '.xxx', '/abc/def.xxx'),
        ('/abc/def', '.xxx', '/abc/def.xxx'),
        ('/abc/.git', '.xxx', '/abc/.xxx'),
        ('def', '.xxx', 'def.xxx'),
        ('def.part1.png', '.xxx', 'def.xxx'),
        ('a/b.c/d', '.xxx', 'a/b.c/d.xxx'),
        ('', '.xxx', '.xxx'),
        ('def.', '.xxx', 'def.xxx'),
        ('/abc/def.png', 'xxx', '/abc/defxxx'),
    ])
    def test_with_multisuffix(self, path, suffix, expected):
        """All extensions should be replaced, the extension is kept when there is none."""
        assert with_multisuffix(path, suffix) == expected
