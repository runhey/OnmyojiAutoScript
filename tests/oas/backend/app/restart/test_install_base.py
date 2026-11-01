"""
The contract of the dependency installer stand-in (``install_base``).

``InstallBase`` is the API-compatible stand-in of the upstream installer.
``restart_step.update_mod_dep`` constructs it and reads exactly three things:
``path_requirements``, ``install_pack()`` and ``cleanup_dist_info()``. These
tests pin the construction contract and the two return shapes the ported caller
depends on.
"""

from types import SimpleNamespace

import pytest

from oas.deploy.simple_pip.install_base import InstallBase
from oas.ext.path import PathStr

pytestmark = pytest.mark.anyio


def _make_mod(root, requirements_file='requirements.txt'):
    """
    A mod stand-in: the root, the entry and a name for the log line.

    The paths go in as ``str``: ``PathStr.new`` normalizes a path string (it is
    not a ``os.PathLike`` consumer).
    """
    return SimpleNamespace(
        root=PathStr.new(str(root)),
        entry=SimpleNamespace(requirements_file=requirements_file),
        name='demo',
    )


def test_construction_coerces_the_folder_and_keeps_the_client(tmp_path):
    mod = _make_mod(tmp_path)
    client = object()
    install = InstallBase(mod, str(tmp_path / 'site'), client=client)
    assert install.mod is mod
    assert isinstance(install.site_packages, PathStr)
    assert install.site_packages == PathStr.new(str(tmp_path / 'site'))
    assert install.client is client
    # the client belongs to the caller, the caller creates the installer
    # without one as well
    assert InstallBase(mod, str(tmp_path)).client is None


def test_path_requirements_is_the_requirements_file_of_the_mod(tmp_path):
    mod = _make_mod(tmp_path)
    install = InstallBase(mod, str(tmp_path))
    assert install.path_requirements == mod.root.joinpath(mod.entry.requirements_file)
    assert install.path_requirements.name == 'requirements.txt'


async def test_install_pack_returns_an_empty_dict(tmp_path):
    """
    The caller reads the result as "no dependency was left behind", so the
    stand-in answers an empty mapping and never None.
    """
    install = InstallBase(_make_mod(tmp_path), str(tmp_path))
    result = await install.install_pack()
    assert isinstance(result, dict)
    assert result == {}


async def test_cleanup_dist_info_returns_an_empty_list(tmp_path):
    install = InstallBase(_make_mod(tmp_path), str(tmp_path))
    result = await install.cleanup_dist_info()
    assert isinstance(result, list)
    assert result == []
