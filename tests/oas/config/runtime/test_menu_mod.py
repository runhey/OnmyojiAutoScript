"""Tests for the decorator-driven ``menu_*`` operations."""

import inspect
from typing import ClassVar, get_type_hints

import pytest

from oas.config.entry.mod_menu import MenuEntry, modmenu
from oas.config.models.registry import config_model_registry
from oas.config.runtime.menu_mod import MenuMod
from oas.config.table.menu import MenuGroupTable, MenuSchemeTable, MenuTaskTable
from oas.db.conn import SQLITE_POOL


@pytest.fixture
def menu_mod():
    yield MenuMod(':memory:')
    for table in (MenuTaskTable, MenuGroupTable, MenuSchemeTable):
        table.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


def test_mounts_one_entry_per_instance(menu_mod):
    menu_mod.menu_scheme_list(':memory:')
    entry = menu_mod.__menu_entry__
    menu_mod.menu_scheme_list(':memory:')
    assert menu_mod.__menu_entry__ is entry


def test_config_name_mismatch_is_rejected(menu_mod):
    with pytest.raises(ValueError, match='config_name mismatch'):
        menu_mod.menu_scheme_list('other')


def test_scheme_crud(menu_mod):
    scheme = menu_mod.menu_scheme_add(':memory:', 'DEFAULT', {'A': ['Task@default']})
    assert scheme['name'] == 'DEFAULT'
    assert scheme['is_default'] is False
    assert scheme['groups']['A']['tasks'] == ['Task@default']

    assert menu_mod.menu_scheme_get(':memory:', 'DEFAULT')['name'] == 'DEFAULT'
    assert [item['name'] for item in menu_mod.menu_scheme_list(':memory:')] == [
        'DEFAULT'
    ]

    assert menu_mod.menu_scheme_delete(':memory:', 'DEFAULT') is True
    with pytest.raises(KeyError):
        menu_mod.menu_scheme_get(':memory:', 'DEFAULT')


def test_missing_operations_raise_keyerror(menu_mod):
    with pytest.raises(KeyError):
        menu_mod.menu_scheme_get(':memory:', 'missing')
    with pytest.raises(KeyError):
        menu_mod.menu_scheme_delete(':memory:', 'missing')
    with pytest.raises(KeyError):
        menu_mod.menu_scheme_replace(':memory:', 'missing', {})
    with pytest.raises(KeyError):
        menu_mod.menu_group_get(':memory:', 'missing', 'G')


def test_scheme_update_default_is_exclusive(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'A', {}, is_default=True)
    menu_mod.menu_scheme_add(':memory:', 'B', {})

    updated = menu_mod.menu_scheme_update(':memory:', 'B', is_default=True)
    assert updated['is_default'] is True
    assert menu_mod.menu_scheme_get(':memory:', 'A')['is_default'] is False


def test_scheme_copy_appends_and_clears_default(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'A', {'G': ['T@1']}, is_default=True)

    copied = menu_mod.menu_scheme_copy(':memory:', 'A', 'B')
    assert copied['is_default'] is False
    assert copied['scheme_order'] == 1
    assert copied['groups']['G']['tasks'] == ['T@1']


def test_group_move_reorders_within_scheme(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'A': [], 'B': [], 'C': []})

    result = menu_mod.menu_group_move(':memory:', 'S', 'C', 0)
    assert result['group_order'] == 0
    assert list(menu_mod.menu_scheme_get(':memory:', 'S')['groups']) == [
        'C',
        'A',
        'B',
    ]


def test_group_copy_copies_metadata_and_appends(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'G': ['T@1']})
    menu_mod.menu_group_update(
        ':memory:',
        'S',
        'G',
        title='Title',
        description='Desc',
        icon='icon',
    )

    copied = menu_mod.menu_group_copy(':memory:', 'S', 'G', 'S', 'G2')
    assert copied['title'] == 'Title'
    assert copied['group_order'] == 1
    assert copied['tasks'] == ['T@1']


def test_group_add_respects_order(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'A': [], 'B': []})

    menu_mod.menu_group_add(':memory:', 'S', 'C', ['T@1'], order=1)
    assert list(menu_mod.menu_scheme_get(':memory:', 'S')['groups']) == [
        'A',
        'C',
        'B',
    ]


def test_group_update_reorders_and_renames(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'A': [], 'B': [], 'C': []})

    result = menu_mod.menu_group_update(
        ':memory:', 'S', 'C', new_group='CC', order=0, title='T'
    )
    assert result['group_order'] == 0
    assert result['title'] == 'T'

    view = menu_mod.menu_scheme_get(':memory:', 'S')
    assert list(view['groups']) == ['CC', 'A', 'B']


def test_task_move_within_group(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'G': ['T@1', 'T@2', 'T@3']})

    menu_mod.menu_task_move(':memory:', 'S', 'G', 'T@3', order=0)
    assert menu_mod.menu_scheme_get(':memory:', 'S')['groups']['G']['tasks'] == [
        'T@3',
        'T@1',
        'T@2',
    ]


def test_task_move_across_groups(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'A': ['T@1', 'T@2'], 'B': ['T@3']})

    menu_mod.menu_task_move(':memory:', 'S', 'A', 'T@1', target_group='B', order=0)
    view = menu_mod.menu_scheme_get(':memory:', 'S')
    assert view['groups']['A']['tasks'] == ['T@2']
    assert view['groups']['B']['tasks'] == ['T@1', 'T@3']


def test_task_copy(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'A': ['T@1'], 'B': []})

    menu_mod.menu_task_copy(':memory:', 'S', 'A', 'T@1', 'S', 'B')
    assert menu_mod.menu_scheme_get(':memory:', 'S')['groups']['B']['tasks'] == ['T@1']


def test_seed_uses_default_instance_names(menu_mod, monkeypatch):
    monkeypatch.setattr(
        config_model_registry,
        'filter_menu',
        lambda menu: {'G': ['Known']},
    )

    menu_mod.menu_scheme_seed(':memory:', {'DEFAULT': {'G': ['Known']}})

    view = menu_mod.menu_scheme_get(':memory:', 'DEFAULT')
    assert view['groups']['G']['tasks'] == ['Known@default']


def test_scheme_add_is_atomic(menu_mod):
    with pytest.raises(ValueError):
        menu_mod.menu_scheme_add(':memory:', 'BAD', {'A': ['T@1'], 'B': ['T@1']})

    with pytest.raises(KeyError):
        menu_mod.menu_scheme_get(':memory:', 'BAD')


def test_scheme_replace_rolls_back_on_invalid_tasks(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'Old': ['T@old']})

    with pytest.raises(ValueError):
        menu_mod.menu_scheme_replace(':memory:', 'S', {'A': ['T@1'], 'B': ['T@1']})

    view = menu_mod.menu_scheme_get(':memory:', 'S')
    assert list(view['groups']) == ['Old']
    assert view['groups']['Old']['tasks'] == ['T@old']


def test_group_add_is_atomic(menu_mod):
    menu_mod.menu_scheme_add(':memory:', 'S', {'G': []})

    with pytest.raises(ValueError):
        menu_mod.menu_group_add(':memory:', 'S', 'H', ['T@1', 'T@1'])

    with pytest.raises(KeyError):
        menu_mod.menu_group_get(':memory:', 'S', 'H')


def test_result_is_hidden_from_public_signature():
    signature = inspect.signature(MenuMod.menu_scheme_add)
    assert 'result' not in signature.parameters


MENU_METHODS = [
    'menu_scheme_list',
    'menu_scheme_get',
    'menu_scheme_add',
    'menu_scheme_update',
    'menu_scheme_delete',
    'menu_scheme_copy',
    'menu_scheme_replace',
    'menu_scheme_seed',
    'menu_group_get',
    'menu_group_add',
    'menu_group_update',
    'menu_group_delete',
    'menu_group_copy',
    'menu_group_move',
    'menu_task_get',
    'menu_task_add',
    'menu_task_delete',
    'menu_task_copy',
    'menu_task_move',
]


@pytest.fixture
def menu_mod_errors():
    yield MenuMod(':memory:')
    for table in (MenuTaskTable, MenuGroupTable, MenuSchemeTable):
        table.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


@pytest.mark.parametrize('name', MENU_METHODS)
def test_public_signature_hides_result(name):
    method = getattr(MenuMod, name)
    signature = inspect.signature(method)

    assert list(signature.parameters)[:2] == ['self', 'config_name']
    assert 'result' not in signature.parameters
    assert 'result' not in get_type_hints(method)
    assert 'result' in inspect.signature(method.__wrapped__).parameters


def test_entry_is_mounted_once_and_reused(menu_mod_errors):
    assert '__menu_entry__' not in menu_mod_errors.__dict__

    menu_mod_errors.menu_scheme_list(':memory:')
    entry = menu_mod_errors.__dict__['__menu_entry__']
    menu_mod_errors.menu_scheme_list(':memory:')

    assert menu_mod_errors.__dict__['__menu_entry__'] is entry
    assert isinstance(entry, MenuEntry)


def test_entry_rejects_config_name_mismatch(menu_mod_errors):
    with pytest.raises(ValueError, match='config_name mismatch'):
        menu_mod_errors.menu_scheme_list('other')


def test_entry_requires_config_name():
    class NoConfig:
        def list(self, result, config_name):
            return result

    NoConfig.list = modmenu._decorate(
        NoConfig.list,
        lambda target, config_name: modmenu._entry(target, config_name),
    )

    with pytest.raises(AttributeError, match='config_name'):
        NoConfig().list(':memory:')


def test_decorate_requires_callable():
    with pytest.raises(TypeError, match='must decorate a callable'):
        modmenu._decorate(object(), lambda target: None)


class Dummy:
    config_name = ':memory:'
    calls: ClassVar[list[str]] = []

    def read(self, result, value):
        Dummy.calls.append('method')
        return result


Dummy.read = modmenu._decorate(
    Dummy.read,
    lambda target, value: (Dummy.calls.append('impl'), value)[1],
)


def test_implementation_runs_before_the_method_body():
    Dummy.calls.clear()

    assert Dummy().read('result') == 'result'
    assert Dummy.calls == ['impl', 'method']


def test_scheme_errors(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {})

    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_scheme_add(':memory:', 'S', {})
    with pytest.raises(ValueError, match='scheme name'):
        menu_mod_errors.menu_scheme_add(':memory:', ' ', {})
    with pytest.raises(TypeError, match='groups must be a mapping'):
        menu_mod_errors.menu_scheme_add(':memory:', 'T', [])
    with pytest.raises(TypeError, match='order must be an integer'):
        menu_mod_errors.menu_scheme_add(':memory:', 'U', {}, order='0')
    with pytest.raises(KeyError, match='No such scheme'):
        menu_mod_errors.menu_scheme_replace(':memory:', 'missing', {})
    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_scheme_copy(':memory:', 'S', 'S')


def test_scheme_seed_is_idempotent(menu_mod_errors, monkeypatch):
    from oas.config.models.registry import config_model_registry

    monkeypatch.setattr(
        config_model_registry, 'filter_menu', lambda menu: {'G': ['Known']}
    )

    first = menu_mod_errors.menu_scheme_seed(':memory:', {'DEFAULT': {'G': ['Known']}})
    second = menu_mod_errors.menu_scheme_seed(':memory:', {'DEFAULT': {'G': ['Known']}})

    assert [item['name'] for item in first] == ['DEFAULT']
    assert [item['name'] for item in second] == ['DEFAULT']
    assert second[0]['groups']['G']['tasks'] == ['Known@default']


def test_scheme_seed_marks_the_first_scheme_as_default(menu_mod_errors, monkeypatch):
    from oas.config.models.registry import config_model_registry

    monkeypatch.setattr(config_model_registry, 'filter_menu', lambda menu: {})

    views = menu_mod_errors.menu_scheme_seed(':memory:', {'A': {}, 'B': {}})

    assert [view['is_default'] for view in views] == [True, False]


def test_group_errors(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {'G': []})

    with pytest.raises(KeyError, match='No such scheme'):
        menu_mod_errors.menu_group_add(':memory:', 'missing', 'H')
    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_group_add(':memory:', 'S', 'G')
    with pytest.raises(ValueError, match='appears more than once'):
        menu_mod_errors.menu_group_add(':memory:', 'S', 'H', ['T@1', 'T@1'])
    with pytest.raises(ValueError, match='group name'):
        menu_mod_errors.menu_group_add(':memory:', 'S', ' ')
    with pytest.raises(TypeError, match='order must be an integer'):
        menu_mod_errors.menu_group_add(':memory:', 'S', 'H', order='0')
    with pytest.raises(KeyError, match='No such group'):
        menu_mod_errors.menu_group_get(':memory:', 'S', 'missing')
    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_group_copy(':memory:', 'S', 'G', 'S', 'G')
    with pytest.raises(KeyError, match='No such group'):
        menu_mod_errors.menu_group_move(':memory:', 'S', 'missing')


def test_group_add_is_atomic_on_invalid_tasks(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {})

    with pytest.raises(ValueError, match='appears more than once'):
        menu_mod_errors.menu_group_add(':memory:', 'S', 'G', ['T@1', 'T@1'])

    with pytest.raises(KeyError):
        menu_mod_errors.menu_group_get(':memory:', 'S', 'G')


def test_task_errors(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {'A': ['T@1'], 'B': []})

    with pytest.raises(KeyError, match='No such task'):
        menu_mod_errors.menu_task_get(':memory:', 'S', 'A', 'missing')
    with pytest.raises(KeyError, match='No such group'):
        menu_mod_errors.menu_task_add(':memory:', 'S', 'missing', 'T@2')
    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_task_add(':memory:', 'S', 'A', 'T@1')
    with pytest.raises(ValueError, match='task name'):
        menu_mod_errors.menu_task_add(':memory:', 'S', 'A', ' ')
    with pytest.raises(KeyError, match='No such task'):
        menu_mod_errors.menu_task_delete(':memory:', 'S', 'A', 'missing')
    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_task_copy(':memory:', 'S', 'A', 'T@1', 'S', 'A')
    with pytest.raises(ValueError, match='task name'):
        menu_mod_errors.menu_task_copy(
            ':memory:', 'S', 'A', 'T@1', 'S', 'B', new_task=' '
        )


def test_task_move_rejects_cross_group_duplicates(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {'A': ['T@1'], 'B': []})
    menu_mod_errors.menu_task_add(':memory:', 'S', 'B', 'T@1')

    with pytest.raises(ValueError, match='already exists'):
        menu_mod_errors.menu_task_move(':memory:', 'S', 'A', 'T@1', target_group='B')


def test_task_move_reorders_and_moves_across_groups(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(':memory:', 'S', {'A': ['T@1', 'T@2'], 'B': []})

    menu_mod_errors.menu_task_move(':memory:', 'S', 'A', 'T@2', order=0)
    assert menu_mod_errors.menu_scheme_get(':memory:', 'S')['groups']['A']['tasks'] == [
        'T@2',
        'T@1',
    ]

    menu_mod_errors.menu_task_move(':memory:', 'S', 'A', 'T@2', target_group='B')
    view = menu_mod_errors.menu_scheme_get(':memory:', 'S')
    assert view['groups']['A']['tasks'] == ['T@1']
    assert view['groups']['B']['tasks'] == ['T@2']


def test_group_and_task_order_are_resequenced_after_delete(menu_mod_errors):
    menu_mod_errors.menu_scheme_add(
        ':memory:', 'S', {'A': [], 'B': [], 'C': ['T@1', 'T@2']}
    )

    menu_mod_errors.menu_group_delete(':memory:', 'S', 'B')
    menu_mod_errors.menu_task_delete(':memory:', 'S', 'C', 'T@1')

    view = menu_mod_errors.menu_scheme_get(':memory:', 'S')
    assert list(view['groups']) == ['A', 'C']
    assert view['groups']['C']['tasks'] == ['T@2']
