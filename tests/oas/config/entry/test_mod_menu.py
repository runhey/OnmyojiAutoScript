"""Tests for the low-level ``MenuEntry`` API."""

from collections import OrderedDict

import pytest

from oas.config.entry.mod_menu import MenuEntry
from oas.config.table.menu import MenuGroupTable, MenuSchemeTable, MenuTaskTable
from oas.db.conn import SQLITE_POOL


@pytest.fixture
def entry():
    menu = MenuEntry(':memory:')
    yield menu
    for table in (MenuTaskTable, MenuGroupTable, MenuSchemeTable):
        table.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


def test_scheme_name_validation(entry):
    with pytest.raises(TypeError, match='scheme must be'):
        entry.add(123)
    with pytest.raises(ValueError, match='scheme name'):
        entry.add('   ')
    with pytest.raises(ValueError, match='scheme name'):
        entry.update_scheme('')


def test_group_and_task_name_validation(entry):
    with pytest.raises(ValueError, match='group name'):
        entry.add('S', {'': []})
    with pytest.raises(TypeError, match='group must be'):
        entry.add('S2', {123: []})
    with pytest.raises(TypeError, match='task must be'):
        entry.add('S3', {'G': [None]})
    with pytest.raises(ValueError, match='task name'):
        entry.add('S4', {'G': ['']})
    with pytest.raises(ValueError, match='appears more than once'):
        entry.add('S5', {'G': ['A', 'A']})


def test_groups_and_metadata_validation(entry):
    with pytest.raises(TypeError, match='groups must be a mapping'):
        entry.add('S', [])
    with pytest.raises(TypeError, match='group_metadata must be a mapping'):
        entry.add('S', {}, group_metadata=[])
    with pytest.raises(TypeError, match='values must be mappings'):
        entry.add('S', {}, group_metadata={'G': []})
    with pytest.raises(ValueError, match='unknown group metadata'):
        entry.add('S', {}, group_metadata={'G': {'bad': 1}})


def test_tasks_must_be_a_sequence(entry):
    with pytest.raises(TypeError, match='sequence of task names'):
        entry.add('S', {'G': 'not-a-list'})


def test_order_validation(entry):
    with pytest.raises(TypeError, match='order must be an integer'):
        entry.add('S', {}, scheme_order='0')

    entry.add('S', {'G': []})
    with pytest.raises(TypeError, match='order must be an integer'):
        entry.add_group('S', 'H', order='0')
    with pytest.raises(TypeError, match='order must be an integer'):
        entry.add_task('S', 'G', 'T@1', order='0')
    with pytest.raises(TypeError, match='order must be an integer'):
        entry.move_group('S', 'G', order='0')


def test_duplicate_scheme_is_rejected(entry):
    entry.add('S', {})

    with pytest.raises(ValueError, match='already exists'):
        entry.add('S', {})


def test_default_scheme_is_exclusive(entry):
    entry.add('A', {}, is_default=True)
    entry.add('B', {}, is_default=True)

    assert entry.view('A')['is_default'] is False
    assert entry.view('B')['is_default'] is True

    entry.update_scheme('A', is_default=True)
    assert entry.view('A')['is_default'] is True
    assert entry.view('B')['is_default'] is False


def test_scheme_order_defaults_to_end_and_can_be_overridden(entry):
    entry.add('A', {})
    entry.add('B', {})

    assert [item['name'] for item in entry.list()] == ['A', 'B']

    entry.add('C', {}, scheme_order=-1)

    assert [item['name'] for item in entry.list()] == ['C', 'A', 'B']


def test_missing_scheme_lookups_raise_keyerror(entry):
    with pytest.raises(KeyError, match='No such scheme'):
        entry.scheme('missing')
    with pytest.raises(KeyError, match='No such scheme'):
        entry.replace('missing', {})
    with pytest.raises(KeyError, match='No such scheme'):
        entry.delete('missing')
    with pytest.raises(KeyError, match='No such scheme'):
        entry.copy_scheme('missing', 'target')
    with pytest.raises(KeyError, match='No such scheme'):
        entry.update_scheme('missing')


def test_scheme_rename_conflicts_and_invalid_names(entry):
    entry.add('A', {})
    entry.add('B', {})

    with pytest.raises(ValueError, match='already exists'):
        entry.update_scheme('A', new_name='B')
    with pytest.raises(ValueError, match='scheme name'):
        entry.update_scheme('A', new_name=' ')


def test_scheme_copy_copies_groups_and_metadata(entry):
    entry.add(
        'A',
        {'G': ['T@1']},
        group_metadata={'G': {'title': 'Title', 'description': 'Desc', 'icon': 'icon'}},
        is_default=True,
    )

    copied = entry.copy_scheme('A', 'B')

    assert copied['name'] == 'B'
    assert copied['is_default'] is False
    assert copied['groups']['G']['title'] == 'Title'
    assert copied['groups']['G']['tasks'] == ['T@1']

    with pytest.raises(ValueError, match='already exists'):
        entry.copy_scheme('A', 'B')


def test_add_group_rejects_missing_scheme_and_duplicates(entry):
    with pytest.raises(KeyError, match='No such scheme'):
        entry.add_group('missing', 'G')

    entry.add('S', {'G': []})
    with pytest.raises(ValueError, match='already exists'):
        entry.add_group('S', 'G')


def test_add_group_rejects_invalid_tasks_atomically(entry):
    entry.add('S', {})

    with pytest.raises(ValueError, match='appears more than once'):
        entry.add_group('S', 'G', ['T@1', 'T@1'])

    with pytest.raises(KeyError):
        entry.group('S', 'G')


def test_add_group_order_is_clamped(entry):
    entry.add('S', {'A': [], 'B': []})

    entry.add_group('S', 'C', order=-10)
    entry.add_group('S', 'D', order=100)

    assert list(entry.menu_scheme_get('S')['groups'].keys()) == ['C', 'A', 'B', 'D']


def test_update_group_rejects_missing_conflicts_and_invalid_names(entry):
    entry.add('S', {'A': [], 'B': []})

    with pytest.raises(KeyError, match='No such group'):
        entry.update_group('S', 'missing')
    with pytest.raises(ValueError, match='already exists'):
        entry.update_group('S', 'A', new_name='B')
    with pytest.raises(ValueError, match='group name'):
        entry.update_group('S', 'A', new_name=' ')


def test_delete_group_rejects_missing_and_resequences(entry):
    entry.add('S', {'A': [], 'B': [], 'C': []})

    with pytest.raises(KeyError, match='No such group'):
        entry.delete_group('S', 'missing')

    entry.delete_group('S', 'B')

    assert list(entry.menu_scheme_get('S')['groups'].keys()) == ['A', 'C']
    assert [item['group_order'] for item in entry.view('S')['groups'].values()] == [
        0,
        1,
    ]


def test_copy_group_rejects_missing_and_duplicates(entry):
    entry.add('S', {'A': ['T@1']})

    with pytest.raises(KeyError, match='No such group'):
        entry.copy_group('S', 'missing', 'S', 'B')
    with pytest.raises(ValueError, match='already exists'):
        entry.copy_group('S', 'A', 'S', 'A')


def test_move_group_rejects_missing_and_reorders(entry):
    entry.add('S', {'A': [], 'B': [], 'C': []})

    with pytest.raises(KeyError, match='No such group'):
        entry.move_group('S', 'missing')

    entry.move_group('S', 'C', order=0)
    assert list(entry.menu_scheme_get('S')['groups'].keys()) == ['C', 'A', 'B']

    entry.move_group('S', 'C')
    assert list(entry.menu_scheme_get('S')['groups'].keys()) == ['A', 'B', 'C']


def test_add_task_rejects_missing_duplicate_and_invalid_names(entry):
    entry.add('S', {'G': ['T@1']})

    with pytest.raises(KeyError, match='No such group'):
        entry.add_task('S', 'missing', 'T@2')
    with pytest.raises(ValueError, match='already exists'):
        entry.add_task('S', 'G', 'T@1')
    with pytest.raises(ValueError, match='task name'):
        entry.add_task('S', 'G', ' ')
    with pytest.raises(TypeError, match='task must be'):
        entry.add_task('S', 'G', None)


def test_add_task_order_is_clamped(entry):
    entry.add('S', {'G': ['T@1', 'T@2']})

    entry.add_task('S', 'G', 'T@3', order=-10)
    entry.add_task('S', 'G', 'T@4', order=100)

    assert entry.menu_scheme_get('S')['groups']['G']['tasks'] == [
        'T@3',
        'T@1',
        'T@2',
        'T@4',
    ]


def test_delete_task_rejects_missing_and_resequences(entry):
    entry.add('S', {'G': ['T@1', 'T@2', 'T@3']})

    with pytest.raises(KeyError, match='No such task'):
        entry.delete_task('S', 'G', 'missing')

    entry.delete_task('S', 'G', 'T@2')

    assert entry.menu_scheme_get('S')['groups']['G']['tasks'] == ['T@1', 'T@3']
    group_row = entry.group('S', 'G')
    assert [row.task_order for row in entry.tasks.list_tasks(group_row.id)] == [
        0,
        1,
    ]


def test_copy_task_rejects_missing_and_duplicates(entry):
    entry.add('S', {'A': ['T@1'], 'B': []})

    with pytest.raises(KeyError, match='No such task'):
        entry.copy_task('S', 'A', 'missing', 'S', 'B')
    with pytest.raises(ValueError, match='already exists'):
        entry.copy_task('S', 'A', 'T@1', 'S', 'A')
    with pytest.raises(ValueError, match='task name'):
        entry.copy_task('S', 'A', 'T@1', 'S', 'B', new_task=' ')


def test_copy_task_can_rename(entry):
    entry.add('S', {'A': ['T@1'], 'B': []})

    copied = entry.copy_task('S', 'A', 'T@1', 'S', 'B', new_task='T@2')

    assert copied['task'] == 'T@2'
    assert entry.menu_scheme_get('S')['groups']['B']['tasks'] == ['T@2']


def test_move_task_rejects_missing_and_cross_group_duplicates(entry):
    entry.add('S', {'A': ['T@1'], 'B': []})
    entry.add_task('S', 'B', 'T@1')

    with pytest.raises(KeyError, match='No such task'):
        entry.move_task('S', 'A', 'missing')
    with pytest.raises(KeyError, match='No such group'):
        entry.move_task('S', 'A', 'T@1', target_group='missing')
    with pytest.raises(ValueError, match='already exists'):
        entry.move_task('S', 'A', 'T@1', target_group='B')


def test_move_task_reorders_within_and_across_groups(entry):
    entry.add('S', {'A': ['T@1', 'T@2'], 'B': []})

    entry.move_task('S', 'A', 'T@2', order=0)
    assert entry.menu_scheme_get('S')['groups']['A']['tasks'] == ['T@2', 'T@1']

    entry.move_task('S', 'A', 'T@2', target_group='B')
    assert entry.menu_scheme_get('S')['groups']['A']['tasks'] == ['T@1']
    assert entry.menu_scheme_get('S')['groups']['B']['tasks'] == ['T@2']


def test_group_and_task_views_reject_missing(entry):
    entry.add('S', {'G': ['T@1']})

    with pytest.raises(KeyError, match='No such group'):
        entry.group_view('S', 'missing')
    with pytest.raises(KeyError, match='No such task'):
        entry.task_view('S', 'G', 'missing')


@pytest.fixture
def menu_entry():
    entry = MenuEntry(':memory:')
    yield entry
    for table in (MenuTaskTable, MenuGroupTable, MenuSchemeTable):
        table.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


def test_add_scheme_preserves_group_and_task_order(menu_entry):
    menu_entry.menu_scheme_add(
        'DEFAULT_MENU',
        OrderedDict(
            [
                ('Script', ['Script@default']),
                ('Soul Zones', ['Orochi@魂十', 'Orochi@魂王']),
            ]
        ),
    )

    v = menu_entry.menu_scheme_get('DEFAULT_MENU')
    assert {k: val['tasks'] for k, val in v['groups'].items()} == {
        'Script': ['Script@default'],
        'Soul Zones': ['Orochi@魂十', 'Orochi@魂王'],
    }
    rows = menu_entry.menu_scheme_list()
    assert [row['name'] for row in rows] == ['DEFAULT_MENU']


def test_empty_group_is_persisted_with_metadata(menu_entry):
    menu_entry.menu_scheme_add(
        'EMPTY',
        {'Empty': []},
        group_metadata={
            'Empty': {
                'title': '空分组',
                'description': '暂无任务',
                'icon': 'box',
            }
        },
    )

    scheme = menu_entry.schemes.get_scheme('EMPTY')
    groups = menu_entry.groups.list_groups(scheme.id)
    assert len(groups) == 1
    assert groups[0].name == 'Empty'
    assert groups[0].title == '空分组'
    v = menu_entry.menu_scheme_get('EMPTY')
    assert {k: val['tasks'] for k, val in v['groups'].items()} == {'Empty': []}


def test_multiple_schemes_are_independent(menu_entry):
    menu_entry.menu_scheme_add('ONE', {'A': ['Task@one']}, order=1)
    menu_entry.menu_scheme_add('TWO', {'B': ['Task@two']}, order=0)

    assert [row['name'] for row in menu_entry.menu_scheme_list()] == ['TWO', 'ONE']
    v = menu_entry.menu_scheme_get('ONE')
    assert {k: val['tasks'] for k, val in v['groups'].items()} == {'A': ['Task@one']}
    v2 = menu_entry.menu_scheme_get('TWO')
    assert {k: val['tasks'] for k, val in v2['groups'].items()} == {'B': ['Task@two']}


def test_replace_scheme_removes_old_groups_and_tasks(menu_entry):
    menu_entry.menu_scheme_add('LAYOUT', {'Old': ['Task@old']})
    menu_entry.menu_scheme_replace('LAYOUT', {'New': []})

    v = menu_entry.menu_scheme_get('LAYOUT')
    assert {k: val['tasks'] for k, val in v['groups'].items()} == {'New': []}
    scheme = menu_entry.schemes.get_scheme('LAYOUT')
    assert menu_entry.groups.list_groups(scheme.id)[0].name == 'New'


def test_delete_scheme_removes_groups_and_tasks(menu_entry):
    menu_entry.menu_scheme_add('LAYOUT', {'Group': ['Task@one']})
    scheme = menu_entry.schemes.get_scheme('LAYOUT')
    group = menu_entry.groups.list_groups(scheme.id)[0]

    assert menu_entry.menu_scheme_delete('LAYOUT') is True
    with pytest.raises(KeyError):
        menu_entry.menu_scheme_get('LAYOUT')
    assert menu_entry.tasks.list_tasks(group.id) == []
    with pytest.raises(KeyError):
        menu_entry.menu_scheme_delete('LAYOUT')


def test_duplicate_task_is_rejected(menu_entry):
    with pytest.raises(ValueError, match='appears more than once'):
        menu_entry.menu_scheme_add(
            'DUPLICATE',
            {'A': ['Task@one'], 'B': ['Task@one']},
        )

    with pytest.raises(KeyError):
        menu_entry.menu_scheme_get('DUPLICATE')


def test_invalid_scheme_and_group_inputs_are_rejected(menu_entry):
    with pytest.raises(ValueError, match='scheme name'):
        menu_entry.menu_scheme_add('', {})
    with pytest.raises(ValueError, match='group name'):
        menu_entry.menu_scheme_add('BAD', {'': []})
    with pytest.raises(TypeError, match='non-empty string'):
        menu_entry.menu_scheme_add('BAD', {'Group': [None]})
    with pytest.raises(ValueError, match='unknown group metadata'):
        menu_entry.menu_scheme_add(
            'BAD',
            {'Group': []},
            group_metadata={'Group': {'unknown': 'value'}},
        )


def test_seed_defaults_filters_unregistered_task_classes(menu_entry, monkeypatch):
    from oas.config.models.registry import config_model_registry

    monkeypatch.setattr(
        config_model_registry,
        'filter_menu',
        lambda menu: {'Visible': ['Known@default']},
    )
    menu_entry.seed_defaults(
        {'DEFAULT_MENU': {'Visible': ['Known'], 'Hidden': ['Missing']}}
    )

    view = menu_entry.menu_scheme_get('DEFAULT_MENU')
    assert {k: v['tasks'] for k, v in view['groups'].items()} == {'Visible': ['Known@default']}
