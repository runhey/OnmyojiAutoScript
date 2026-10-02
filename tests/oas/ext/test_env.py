"""
Tests for oas.ext.env

Alasio has no tests/ext/test_env.py, so this module is written from scratch.
Scope is limited to the deterministic surface: OS flags, OAS_ROOT and
set_project_root. Nothing here measures host state beyond os/sys.
"""
import os
import sys

import pytest

from oas.ext import env
from oas.ext.env import OAS_ROOT, PROJECT_ROOT, set_project_root


class TestOsFlags:
    def test_posix_and_windows_are_mutually_exclusive(self):
        assert env.POSIX is (os.name == 'posix')
        assert env.WINDOWS is (os.name == 'nt')
        assert not (env.POSIX and env.WINDOWS)

    @pytest.mark.parametrize(
        'flag, prefix',
        [
            (env.LINUX, 'linux'),
            (env.MACOS, 'darwin'),
            (env.OPENBSD, 'openbsd'),
            (env.NETBSD, 'netbsd'),
            (env.AIX, 'aix'),
        ],
    )
    def test_platform_prefix_flags(self, flag, prefix):
        if flag:
            assert sys.platform.startswith(prefix)
        else:
            assert not sys.platform.startswith(prefix)

    def test_osx_is_alias_of_macos(self):
        assert env.OSX == env.MACOS

    def test_freebsd_accepts_two_platform_strings(self):
        if env.FREEBSD:
            assert sys.platform.startswith(('freebsd', 'midnightbsd'))
        else:
            assert not sys.platform.startswith(('freebsd', 'midnightbsd'))

    def test_sunos_accepts_two_platform_strings(self):
        if env.SUNOS:
            assert sys.platform.startswith(('sunos', 'solaris'))
        else:
            assert not sys.platform.startswith(('sunos', 'solaris'))

    def test_bsd_is_union_of_three_bsds(self):
        assert env.BSD == (env.FREEBSD or env.OPENBSD or env.NETBSD)

    def test_no_bsd_flags_imply_not_bsd(self):
        if not env.BSD:
            assert not (env.FREEBSD or env.OPENBSD or env.NETBSD)


class TestOasRoot:
    def test_oas_root_contains_the_oas_package(self):
        # oas/ is a namespace package (no __init__.py), so check the dir only
        assert os.path.isdir(str(OAS_ROOT.joinpath('oas')))

    def test_oas_root_contains_pyproject(self):
        assert os.path.isfile(str(OAS_ROOT.joinpath('pyproject.toml')))

    def test_oas_root_is_absolute(self):
        assert os.path.isabs(str(OAS_ROOT))

    def test_oas_root_is_a_pathstr(self):
        from oas.ext.path import PathStr

        assert isinstance(OAS_ROOT, PathStr)

    def test_oas_root_matches_this_file_location(self):
        # oas/ext/env.py -> uppath(3) lands on the repo root. PathStr keeps
        # forward slashes, so compare against a normalised os path.
        here = os.path.dirname(os.path.abspath(__file__))
        expected = os.path.abspath(os.path.join(here, '..', '..', '..'))
        assert os.path.normpath(str(OAS_ROOT)) == os.path.normpath(expected)

    def test_oas_root_is_stable_across_imports(self):
        from oas.ext.env import OAS_ROOT as second

        assert OAS_ROOT == second

    def test_joinpath_takes_one_segment(self):
        # PathStr.joinpath is not varargs like pathlib.Path.joinpath
        assert str(OAS_ROOT.joinpath('oas')) == os.path.normpath(str(OAS_ROOT)).replace('\\', '/') + '/oas'


class TestSetProjectRoot:
    @pytest.fixture(autouse=True)
    def restore(self):
        original = env.PROJECT_ROOT
        yield
        env.PROJECT_ROOT = original

    def test_initial_project_root_is_empty(self):
        assert str(PROJECT_ROOT) == ''

    def test_set_plain_path(self, tmp_path):
        set_project_root(str(tmp_path))
        assert os.path.normpath(str(env.PROJECT_ROOT)) == os.path.normpath(str(tmp_path))

    def test_set_with_up(self, tmp_path):
        nested = tmp_path / 'a' / 'b' / 'c'
        nested.mkdir(parents=True)
        set_project_root(str(nested), up=2)
        assert os.path.normpath(str(env.PROJECT_ROOT)) == os.path.normpath(str(tmp_path / 'a'))

    def test_up_zero_is_same_as_omitting_up(self, tmp_path):
        set_project_root(str(tmp_path), up=0)
        assert os.path.normpath(str(env.PROJECT_ROOT)) == os.path.normpath(str(tmp_path))

    def test_set_returns_none(self, tmp_path):
        assert set_project_root(str(tmp_path)) is None

    def test_rejects_pathlib_path(self, tmp_path):
        # PathStr.new -> oas.ext.path.calc.normpath does `'\\' in path`,
        # which raises on a pathlib.Path. Contract: str only.
        with pytest.raises(TypeError):
            set_project_root(tmp_path)

    def test_result_is_a_pathstr(self, tmp_path):
        from oas.ext.path import PathStr

        set_project_root(str(tmp_path))
        assert isinstance(env.PROJECT_ROOT, PathStr)