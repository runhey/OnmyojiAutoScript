"""
Tests for alasio/ext/path/pathstr.py.

PathStr is the string based path object of the project: its path calculation
methods delegate to the functions of oas.ext.path.calc (covered by
test_calc.py), the members implemented by PathStr itself are covered here.
"""
import os

import pytest

from oas.ext.path import calc
from oas.ext.path.pathstr import PathStr


class TestCwd:
    """Tests for PathStr.cwd()."""

    @pytest.fixture(autouse=True)
    def fake_env(self, monkeypatch):
        """Force the POSIX branch and a fixed cwd to run on every platform."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', False)
        monkeypatch.setattr(os, 'getcwd', lambda: '/fake/cwd')

    def test_cwd(self):
        """cwd should come back as a normalized PathStr."""
        cwd = PathStr.cwd()
        assert isinstance(cwd, PathStr)
        assert cwd == '/fake/cwd'

    def test_cwd_windows_sep(self, monkeypatch):
        """A backslash separated cwd should be normalized on the Windows branch."""
        monkeypatch.setattr(calc, 'WINDOWS_SEP', True)
        monkeypatch.setattr(os, 'getcwd', lambda: 'C:\\fake\\cwd')
        assert PathStr.cwd() == 'C:/fake/cwd'

    def test_cwd_is_root(self, monkeypatch):
        """A root cwd should stay "/" instead of becoming an empty string."""
        monkeypatch.setattr(os, 'getcwd', lambda: '/')
        assert PathStr.cwd() == '/'


class TestSubpath:
    """Tests for PathStr.subpath_to() and PathStr.subpath(), the calc wrappers."""

    def test_subpath_to(self):
        """A sub-path should come back as a PathStr."""
        sub = PathStr.new('/a/b/c').subpath_to('/a/b')
        assert isinstance(sub, PathStr)
        assert sub == 'c'

    def test_subpath_to_not_a_sub_path(self):
        """A non sub-path should yield None instead of a broken PathStr."""
        assert PathStr.new('/a/bc').subpath_to('/a/b') is None

    def test_subpath(self):
        """The strict version should come back as a PathStr."""
        sub = PathStr.new('/a/b/c').subpath('/a/b')
        assert isinstance(sub, PathStr)
        assert sub == 'c'

    def test_subpath_not_a_sub_path(self):
        """The strict version should raise ValueError for a non sub-path."""
        with pytest.raises(ValueError, match='Not a sub-path'):
            PathStr.new('/a/bc').subpath('/a/b')
