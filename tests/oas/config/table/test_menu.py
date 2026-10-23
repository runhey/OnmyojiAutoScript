import sqlite3

import pytest

from oas.config.table.menu import (
    MenuGroupRow,
    MenuGroupTable,
    MenuSchemeRow,
    MenuSchemeTable,
    MenuTaskRow,
    MenuTaskTable,
)
from oas.db.conn import SQLITE_POOL


@pytest.fixture
def tables():
    schemes = MenuSchemeTable(':memory:')
    groups = MenuGroupTable(':memory:')
    tasks = MenuTaskTable(':memory:')
    schemes.create_table()
    groups.create_table()
    tasks.create_table()
    yield schemes, groups, tasks
    for table in (MenuTaskTable, MenuGroupTable, MenuSchemeTable):
        table.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


def _scheme(schemes, name='S', order=0, is_default=0):
    schemes.insert_row(
        MenuSchemeRow(name=name, scheme_order=order, is_default=is_default)
    )
    return schemes.get_scheme(name)


def _group(groups, scheme_id, name='G', order=0):
    groups.insert_row(MenuGroupRow(scheme_id=scheme_id, name=name, group_order=order))
    return groups.get_group(scheme_id, name)


def _task(tasks, group_id, name='T@1', order=0):
    tasks.insert_row(MenuTaskRow(group_id=group_id, task=name, task_order=order))
    return tasks.select_one(group_id=group_id, task=name)


def test_table_columns(tables):
    schemes, groups, tasks = tables
    expected = {
        'ui_menu_scheme': {'id', 'name', 'scheme_order', 'is_default'},
        'ui_menu_group': {
            'id',
            'scheme_id',
            'name',
            'group_order',
            'title',
            'description',
            'icon',
        },
        'ui_menu_task': {'id', 'group_id', 'task', 'task_order'},
    }
    for table, columns in (
        (schemes, expected['ui_menu_scheme']),
        (groups, expected['ui_menu_group']),
        (tasks, expected['ui_menu_task']),
    ):
        with table.cursor() as cursor:
            cursor.execute(f'PRAGMA table_info("{table.TABLE_NAME}")')
            assert {row[1] for row in cursor.fetchall()} == columns


def test_scheme_name_is_unique(tables):
    schemes, _groups, _tasks = tables
    _scheme(schemes, 'S')

    with pytest.raises(sqlite3.IntegrityError):
        _scheme(schemes, 'S')


def test_group_name_and_order_are_unique_per_scheme(tables):
    schemes, groups, _tasks = tables
    scheme = _scheme(schemes, 'S')
    _group(groups, scheme.id, 'G', 0)

    with pytest.raises(sqlite3.IntegrityError):
        _group(groups, scheme.id, 'G', 1)
    with pytest.raises(sqlite3.IntegrityError):
        _group(groups, scheme.id, 'H', 0)


def test_task_name_and_order_are_unique_per_group(tables):
    schemes, groups, tasks = tables
    scheme = _scheme(schemes, 'S')
    group = _group(groups, scheme.id, 'G')
    _task(tasks, group.id, 'T@1', 0)

    with pytest.raises(sqlite3.IntegrityError):
        _task(tasks, group.id, 'T@1', 1)
    with pytest.raises(sqlite3.IntegrityError):
        _task(tasks, group.id, 'T@2', 0)


def test_list_orders_follow_the_order_columns(tables):
    schemes, groups, tasks = tables
    _scheme(schemes, 'B', 1)
    _scheme(schemes, 'A', 0)
    assert [row.name for row in schemes.list_schemes()] == ['A', 'B']

    scheme = schemes.get_scheme('A')
    _group(groups, scheme.id, 'B', 1)
    _group(groups, scheme.id, 'A', 0)
    assert [row.name for row in groups.list_groups(scheme.id)] == ['A', 'B']

    group = groups.get_group(scheme.id, 'A')
    _task(tasks, group.id, 'T@2', 1)
    _task(tasks, group.id, 'T@1', 0)
    assert [row.task for row in tasks.list_tasks(group.id)] == ['T@1', 'T@2']


def test_upsert_scheme_updates_by_name(tables):
    schemes, _groups, _tasks = tables
    _scheme(schemes, 'S', 0, 0)

    updated = schemes.upsert_scheme(
        MenuSchemeRow(name='S', scheme_order=7, is_default=1)
    )

    assert updated.scheme_order == 7
    assert updated.is_default == 1
    assert len(schemes.select()) == 1


def test_missing_lookups_return_none(tables):
    schemes, groups, tasks = tables

    assert schemes.get_scheme('missing') is None
    assert groups.get_group(1, 'missing') is None
    assert tasks.select_one(group_id=1, task='missing') is None


def test_delete_helpers_remove_children(tables):
    schemes, groups, tasks = tables
    scheme = _scheme(schemes, 'S')
    first = _group(groups, scheme.id, 'A', 0)
    second = _group(groups, scheme.id, 'B', 1)
    _task(tasks, first.id, 'T@1')
    _task(tasks, second.id, 'T@2')

    tasks.delete_group(first.id)
    assert tasks.list_tasks(first.id) == []
    assert tasks.list_tasks(second.id) != []

    tasks.delete_groups([first.id, second.id])
    assert tasks.list_tasks(second.id) == []

    groups.delete_scheme(scheme.id)
    assert groups.list_groups(scheme.id) == []
