"""
Tests for the ``oas.ext.proc`` package surface.

``__init__.py`` re-exports seven names from the four submodules. The re-export
must be *identity*, not a copy: ``test_cmd``/``test_nice``/``test_sig`` patch the
submodule attributes, and ``from oas.ext.proc import get_cmdline`` has to keep
pointing at the same object for those patches to be visible. A wrapper function
around the real one would silently break that, so identity is pinned here.

There are also two migration guards. The package came from AlasIO, where
``iter.py`` imported ``from alasio.ext.proc.cmd import get_cmdline``; that would
raise ImportError here. And the submodules must keep importing each other
*relatively*, because ``test_platform_branches.py`` loads a private copy of the
package under a throwaway name -- an absolute ``oas.ext.proc.cmd`` reference
would bind the real module and quietly test the wrong thing.
"""

import inspect
import pathlib

import pytest

from oas.ext import proc

#: Public name -> the submodule that must own the very same object.
PUBLIC_API = {
    'get_cmdline': 'cmd',
    'get_executable': 'cmd',
    'process_iter': 'iter',
    'set_lower_process_priority': 'nice',
    'set_lowest_process_priority': 'nice',
    'process_kill': 'sig',
    'process_terminate': 'sig',
}

SUBMODULES = ('cmd', 'iter', 'nice', 'sig')

PROC_DIR = pathlib.Path(proc.__file__).parent

#: The exact signature every public callable must keep.
EXPECTED_SIGNATURES = {
    'get_cmdline': '(pid)',
    'get_executable': '(pid)',
    'process_iter': '()',
    'set_lower_process_priority': '(pid=None)',
    'set_lowest_process_priority': '(pid=None)',
    'process_kill': '(pid)',
    'process_terminate': '(pid)',
}


class TestPublicApi:
    """Everything the package promises to export."""

    @pytest.mark.parametrize('name', sorted(PUBLIC_API))
    def test_name_is_exported(self, name):
        assert hasattr(proc, name)

    @pytest.mark.parametrize('name', sorted(PUBLIC_API))
    def test_name_is_callable(self, name):
        assert callable(getattr(proc, name))

    @pytest.mark.parametrize('name', sorted(PUBLIC_API))
    def test_export_is_the_submodule_object_itself(self, name):
        """Identity, not a wrapper -- the other test modules depend on it."""
        submodule = getattr(proc, PUBLIC_API[name])
        assert getattr(proc, name) is getattr(submodule, name)

    @pytest.mark.parametrize('name', SUBMODULES)
    def test_submodule_is_reachable_as_an_attribute(self, name):
        assert inspect.ismodule(getattr(proc, name))

    @pytest.mark.parametrize('name', SUBMODULES)
    def test_submodule_are_the_same_module_objects(self, name):
        """No duplicate module instances hiding behind the package."""
        assert getattr(proc, name) is __import__(
            f'oas.ext.proc.{name}', fromlist=[name]
        )

    def test_public_surface_is_exactly_the_documented_names(self):
        """Nothing leaks out that callers did not sign up for."""
        public = {name for name in dir(proc) if not name.startswith('_')}
        assert public == set(PUBLIC_API) | set(SUBMODULES)

    @pytest.mark.parametrize('name, signature', sorted(EXPECTED_SIGNATURES.items()))
    def test_signature_is_unchanged(self, name, signature):
        """The wrappers are called positionally all over the codebase."""
        assert str(inspect.signature(getattr(proc, name))) == signature

    def test_star_import_does_not_shadow_builtins(self):
        """A star import must not hand out anything surprising."""
        exported = {
            name for name in dir(proc) if not name.startswith('_')
        }
        assert {'open', 'list', 'dict', 'type'} & exported == set()

    def test_importing_is_idempotent(self):
        """Importing again returns the cached module, running no module code."""
        import oas.ext.proc as again

        assert again is proc

    def test_docstrings_are_present_on_the_public_api(self):
        """The API is documented in place; these are the ones callers read."""
        for name in PUBLIC_API:
            assert inspect.getdoc(getattr(proc, name)), f'{name} has no docstring'


class TestMigrationGuards:
    """The package was copied from another project and must stay self-contained."""

    @pytest.mark.parametrize('source', ['__init__.py', 'cmd.py', 'iter.py', 'nice.py', 'sig.py'])
    def test_source_has_no_alasios_reference(self, source):
        """A leftover ``alasio`` import would only fail on the path that uses it."""
        text = (PROC_DIR / source).read_text(encoding='utf-8')
        assert 'alasio' not in text

    @pytest.mark.parametrize('source', SUBMODULES)
    def test_submodules_do_not_import_themselves_absolutely(self, source):
        """
        Submodules must reach each other relatively.

        The fake-platform tests in ``test_platform_branches.py`` exec a private
        copy of the package under another name; an absolute self-import would
        resolve to the real module and the faked copy would silently stop being
        the thing under test.
        """
        text = (PROC_DIR / f'{source}.py').read_text(encoding='utf-8')
        assert 'oas.ext.proc' not in text

    def test_only_expected_sources_exist(self):
        """No stray module was dropped into the package."""
        assert sorted(p.name for p in PROC_DIR.glob('*.py')) == [
            '__init__.py', 'cmd.py', 'iter.py', 'nice.py', 'sig.py'
        ]

    def test_the_seven_public_names_are_all_that_is_reexported(self):
        """``__init__.py`` is a pure re-export barrel, nothing else."""
        text = (PROC_DIR / '__init__.py').read_text(encoding='utf-8')
        for name in PUBLIC_API:
            assert name in text
        assert 'def ' not in text
        assert 'class ' not in text
