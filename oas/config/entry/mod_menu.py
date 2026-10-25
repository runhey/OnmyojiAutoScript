"""Decorated menu operations backed by the three UI menu tables."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from functools import wraps
from typing import Any, TypeVar

from oas.config.models.menu import DEFAULT_MENU
from oas.config.models.registry import config_model_registry
from oas.config.table.menu import (
    MenuGroupRow,
    MenuGroupTable,
    MenuSchemeRow,
    MenuSchemeTable,
    MenuTaskRow,
    MenuTaskTable,
)
from oas.mod.adapter import ModAdapter

F = TypeVar('F', bound=Callable[..., Any])
MenuGroups = Mapping[str, Sequence[str]]
MenuMetadata = Mapping[str, Mapping[str, str | None]]


def _default_task_name(task: str) -> str:
    """Return the default Task instance name for a menu entry."""
    return task if '@' in task else f'{task}@default'


class MenuEntryValidator:
    _METADATA_FIELDS = frozenset({'title', 'description', 'icon'})

    @classmethod
    def require_name(cls, value: Any, label: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f'{label} must be a non-empty string')
        if not value.strip():
            raise ValueError(f'{label} name must be a non-empty string')
        return value

    @classmethod
    def check_groups(cls, groups: MenuGroups) -> None:
        if not isinstance(groups, Mapping):
            raise TypeError('groups must be a mapping')

    @classmethod
    def check_metadata(cls, metadata: MenuMetadata | None) -> None:
        if metadata is None:
            return
        if not isinstance(metadata, Mapping):
            raise TypeError('group_metadata must be a mapping')
        for values in metadata.values():
            if not isinstance(values, Mapping):
                raise TypeError('group_metadata values must be mappings')
            unknown = set(values) - cls._METADATA_FIELDS
            if unknown:
                raise ValueError(f'unknown group metadata: {sorted(unknown)!r}')

    @classmethod
    def check_tasks(cls, tasks: Sequence[str]) -> None:
        if isinstance(tasks, (str, bytes)) or not isinstance(tasks, Sequence):
            raise TypeError('tasks must be a sequence of task names')
        seen: set[str] = set()
        for task in tasks:
            cls.require_name(task, 'task')
            if task in seen:
                raise ValueError(f'task appears more than once: {task!r}')
            seen.add(task)

    @classmethod
    def check_order(cls, order: int | None) -> int | None:
        if order is not None and not isinstance(order, int):
            raise TypeError('order must be an integer')
        return order


class MenuEntry:
    """Menu store and operations used by ``modmenu`` implementations.

    Every multi-row write runs in a single ``EXCLUSIVE`` transaction, so a failed
    menu edit never leaves a half-created scheme or group behind.
    """

    def __init__(self, config_name: str):
        self.schemes = MenuSchemeTable(config_name)
        self.groups = MenuGroupTable(config_name)
        self.tasks = MenuTaskTable(config_name)
        self.schemes.create_table()
        self.groups.create_table()
        self.tasks.create_table()

    _require_name = MenuEntryValidator.require_name
    _check_groups = MenuEntryValidator.check_groups
    _check_metadata = MenuEntryValidator.check_metadata
    _check_tasks = MenuEntryValidator.check_tasks
    _check_order = MenuEntryValidator.check_order

    # ------------------------------------------------------------------
    # Row lookups
    # ------------------------------------------------------------------

    def scheme(self, name: str, *, _cursor_=None) -> MenuSchemeRow:
        """Return one scheme row; a missing scheme raises ``KeyError``."""
        self._require_name(name, 'scheme')
        row = self.schemes.get_scheme(name, _cursor_=_cursor_)
        if row is None:
            raise KeyError(f'No such scheme: "{name}"')
        return row

    def group(self, scheme: str, name: str, *, _cursor_=None) -> MenuGroupRow:
        """Return one group row; missing scheme or group raises ``KeyError``."""
        scheme_row = self.scheme(scheme, _cursor_=_cursor_)
        self._require_name(name, 'group')
        row = self.groups.get_group(scheme_row.id, name, _cursor_=_cursor_)
        if row is None:
            raise KeyError(f'No such group: "{scheme}.{name}"')
        return row

    def task(self, scheme: str, group: str, name: str, *, _cursor_=None) -> MenuTaskRow:
        """Return one task row; missing scheme, group, or task raises ``KeyError``."""
        group_row = self.group(scheme, group, _cursor_=_cursor_)
        self._require_name(name, 'task')
        row = self.tasks.select_one(group_id=group_row.id, task=name, _cursor_=_cursor_)
        if row is None:
            raise KeyError(f'No such task: "{name}"')
        return row

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def view(self, name: str, *, _cursor_=None) -> dict[str, Any]:
        """Return the full view of one scheme."""
        scheme = self.scheme(name, _cursor_=_cursor_)
        groups = self.groups.list_groups(scheme.id, _cursor_=_cursor_)
        return {
            'name': scheme.name,
            'scheme_order': scheme.scheme_order,
            'is_default': bool(scheme.is_default),
            'groups': {
                group.name: {
                    'group_order': group.group_order,
                    'title': group.title,
                    'description': group.description,
                    'icon': group.icon,
                    'tasks': [
                        task.task
                        for task in self.tasks.list_tasks(group.id, _cursor_=_cursor_)
                    ],
                }
                for group in groups
            },
        }

    def group_view(self, scheme: str, group: str, *, _cursor_=None) -> dict[str, Any]:
        """Return the view of one group inside a scheme."""
        self.group(scheme, group, _cursor_=_cursor_)
        return self.view(scheme, _cursor_=_cursor_)['groups'][group]

    def task_view(
        self, scheme: str, group: str, name: str, *, _cursor_=None
    ) -> dict[str, Any]:
        """Return the view of one task inside a group."""
        row = self.task(scheme, group, name, _cursor_=_cursor_)
        return {'group': group, 'task': row.task, 'task_order': row.task_order}

    def list(self) -> list[dict[str, Any]]:
        """Return every scheme view ordered by ``scheme_order``."""
        return [self.view(row.name) for row in self.schemes.list_schemes()]

    # ------------------------------------------------------------------
    # Order helpers
    # ------------------------------------------------------------------

    def _next_scheme_order(self, cursor) -> int:
        rows = self.schemes.list_schemes(_cursor_=cursor)
        return max((row.scheme_order for row in rows), default=-1) + 1

    def _clear_default(self, cursor, *, exclude: int | None = None) -> None:
        for row in self.schemes.select(_cursor_=cursor, is_default=1):
            if row.id == exclude:
                continue
            row.is_default = 0
            self.schemes.update_row(row, updates=('is_default',), _cursor_=cursor)

    def _resequence_groups(self, scheme_id: int, cursor) -> None:
        rows = self.groups.list_groups(scheme_id, _cursor_=cursor)
        for row in rows:
            row.group_order = -row.id
            self.groups.update_row(row, updates=('group_order',), _cursor_=cursor)
        for order, row in enumerate(rows):
            row.group_order = order
            self.groups.update_row(row, updates=('group_order',), _cursor_=cursor)

    def _resequence_tasks(self, group_id: int, cursor) -> None:
        rows = self.tasks.list_tasks(group_id, _cursor_=cursor)
        for row in rows:
            row.task_order = -row.id
            self.tasks.update_row(row, updates=('task_order',), _cursor_=cursor)
        for order, row in enumerate(rows):
            row.task_order = order
            self.tasks.update_row(row, updates=('task_order',), _cursor_=cursor)

    def _insert_group_at(
        self,
        scheme_id: int,
        row: MenuGroupRow,
        order: int | None,
        cursor,
    ) -> None:
        rows = self.groups.list_groups(scheme_id, _cursor_=cursor)
        index = len(rows) if order is None else max(0, min(order, len(rows)))
        for other in reversed(rows[index:]):
            other.group_order += 1
            self.groups.update_row(other, updates=('group_order',), _cursor_=cursor)
        row.group_order = index
        self.groups.insert_row(row, _cursor_=cursor)

    def _insert_task_at(
        self,
        group_id: int,
        row: MenuTaskRow,
        order: int | None,
        cursor,
    ) -> None:
        rows = self.tasks.list_tasks(group_id, _cursor_=cursor)
        index = len(rows) if order is None else max(0, min(order, len(rows)))
        for other in reversed(rows[index:]):
            other.task_order += 1
            self.tasks.update_row(other, updates=('task_order',), _cursor_=cursor)
        row.task_order = index
        self.tasks.insert_row(row, _cursor_=cursor)

    def _move_group(
        self, scheme_id: int, group_id: int, order: int | None, cursor
    ) -> None:
        rows = self.groups.list_groups(scheme_id, _cursor_=cursor)
        row = next((item for item in rows if item.id == group_id), None)
        if row is None:
            raise KeyError(f'No such group id: {group_id}')
        rows.remove(row)
        index = len(rows) if order is None else max(0, min(order, len(rows)))
        ordered = [*rows[:index], row, *rows[index:]]
        for item in ordered:
            item.group_order = -item.id
            self.groups.update_row(item, updates=('group_order',), _cursor_=cursor)
        for position, item in enumerate(ordered):
            item.group_order = position
            self.groups.update_row(item, updates=('group_order',), _cursor_=cursor)

    def _move_task(
        self,
        scheme: str,
        group: str,
        task: str,
        target_group: str | None,
        order: int | None,
        cursor,
    ) -> tuple[str, str]:
        source = self.group(scheme, group, _cursor_=cursor)
        row = self.task(scheme, group, task, _cursor_=cursor)
        destination = (
            source
            if target_group is None
            else self.group(scheme, target_group, _cursor_=cursor)
        )
        if source.id == destination.id:
            rows = self.tasks.list_tasks(source.id, _cursor_=cursor)
            rows = [item for item in rows if item.id != row.id]
            index = len(rows) if order is None else max(0, min(order, len(rows)))
            ordered = [*rows[:index], row, *rows[index:]]
            for item in ordered:
                item.task_order = -item.id
                self.tasks.update_row(item, updates=('task_order',), _cursor_=cursor)
            for position, item in enumerate(ordered):
                item.task_order = position
                self.tasks.update_row(item, updates=('task_order',), _cursor_=cursor)
            return scheme, destination.name

        duplicate = self.tasks.select_one(
            group_id=destination.id, task=row.task, _cursor_=cursor
        )
        if duplicate is not None:
            raise ValueError(f'Task already exists: "{row.task}"')
        self.tasks.delete(_cursor_=cursor, id=row.id)
        self._resequence_tasks(source.id, cursor)
        self._insert_task_at(
            destination.id,
            MenuTaskRow(destination.id, row.task),
            order,
            cursor,
        )
        return scheme, destination.name

    # ------------------------------------------------------------------
    # Scheme operations
    # ------------------------------------------------------------------

    def add(
        self,
        name: str,
        groups: MenuGroups | None = None,
        *,
        scheme_order: int | None = None,
        is_default: bool = False,
        group_metadata: MenuMetadata | None = None,
    ) -> dict[str, Any]:
        """Create a scheme and its groups in one transaction."""
        self._require_name(name, 'scheme')
        groups = {} if groups is None else groups
        self._check_groups(groups)
        self._check_metadata(group_metadata)
        scheme_order = self._check_order(scheme_order)
        with self.schemes.exclusive_transaction() as cursor:
            if self.schemes.get_scheme(name, _cursor_=cursor) is not None:
                raise ValueError(f'Scheme already exists: "{name}"')
            order = (
                self._next_scheme_order(cursor)
                if scheme_order is None
                else scheme_order
            )
            if is_default:
                self._clear_default(cursor)
            self.schemes.insert_row(
                MenuSchemeRow(name, order, int(bool(is_default))),
                _cursor_=cursor,
            )
            scheme = self.schemes.get_scheme(name, _cursor_=cursor)
            if scheme is None:
                raise RuntimeError(f'Scheme insert failed: "{name}"')
            self._replace_groups(scheme, groups, group_metadata, cursor)
        return self.view(name)

    def replace(
        self,
        name: str,
        groups: MenuGroups,
        *,
        group_metadata: MenuMetadata | None = None,
    ) -> dict[str, Any]:
        """Replace the groups of an existing scheme in one transaction."""
        self._require_name(name, 'scheme')
        self._check_groups(groups)
        self._check_metadata(group_metadata)
        with self.schemes.exclusive_transaction() as cursor:
            scheme = self.scheme(name, _cursor_=cursor)
            self._replace_groups(scheme, groups, group_metadata, cursor)
        return self.view(name)

    def update_scheme(
        self,
        name: str,
        *,
        new_name: str | None = None,
        order: int | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        """Rename, reorder, or change the default flag of a scheme."""
        self._require_name(name, 'scheme')
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            row = self.scheme(name, _cursor_=cursor)
            if new_name is not None:
                self._require_name(new_name, 'scheme')
                if new_name != name:
                    if self.schemes.get_scheme(new_name, _cursor_=cursor) is not None:
                        raise ValueError(f'Scheme already exists: "{new_name}"')
                    row.name = new_name
            if order is not None:
                row.scheme_order = order
            if is_default is not None:
                if is_default:
                    self._clear_default(cursor, exclude=row.id)
                row.is_default = int(bool(is_default))
            self.schemes.update_row(
                row,
                updates=('name', 'scheme_order', 'is_default'),
                _cursor_=cursor,
            )
        return self.view(row.name)

    def delete(self, name: str) -> bool:
        """Delete a scheme, its groups, and its tasks; missing raises ``KeyError``."""
        self._require_name(name, 'scheme')
        with self.schemes.exclusive_transaction() as cursor:
            scheme = self.scheme(name, _cursor_=cursor)
            groups = self.groups.list_groups(scheme.id, _cursor_=cursor)
            self.tasks.delete_groups((row.id for row in groups), _cursor_=cursor)
            self.groups.delete_scheme(scheme.id, _cursor_=cursor)
            self.schemes.delete(_cursor_=cursor, id=scheme.id)
        return True

    def copy_scheme(self, source: str, target: str) -> dict[str, Any]:
        """Copy a scheme to the end of the scheme list."""
        source_view = self.view(source)
        if self.schemes.get_scheme(target) is not None:
            raise ValueError(f'Scheme already exists: "{target}"')
        groups = {name: data['tasks'] for name, data in source_view['groups'].items()}
        metadata = {
            name: {
                'title': data['title'],
                'description': data['description'],
                'icon': data['icon'],
            }
            for name, data in source_view['groups'].items()
        }
        return self.add(target, groups, group_metadata=metadata)

    def _replace_groups(
        self,
        scheme: MenuSchemeRow,
        groups: MenuGroups,
        metadata: MenuMetadata | None,
        cursor,
    ) -> None:
        self._check_groups(groups)
        self._check_metadata(metadata)
        metadata = metadata or {}
        old = self.groups.list_groups(scheme.id, _cursor_=cursor)
        self.tasks.delete_groups((row.id for row in old), _cursor_=cursor)
        self.groups.delete_scheme(scheme.id, _cursor_=cursor)
        seen_tasks: set[str] = set()
        for group_order, (group_name, tasks) in enumerate(groups.items()):
            self._require_name(group_name, 'group')
            self._check_tasks(tasks)
            values = metadata.get(group_name, {})
            group = MenuGroupRow(
                scheme.id,
                group_name,
                group_order,
                values.get('title'),
                values.get('description'),
                values.get('icon'),
            )
            self.groups.insert_row(group, _cursor_=cursor)
            group = self.groups.get_group(scheme.id, group_name, _cursor_=cursor)
            if group is None:
                raise RuntimeError(f'Group insert failed: "{scheme.name}.{group_name}"')
            for task_order, task in enumerate(tasks):
                if task in seen_tasks:
                    raise ValueError(f'task appears more than once: {task!r}')
                seen_tasks.add(task)
                self.tasks.insert_row(
                    MenuTaskRow(group.id, task, task_order),
                    _cursor_=cursor,
                )

    def seed_defaults(self, menus: Mapping[str, MenuGroups] | None = None) -> None:
        """Create the default schemes that do not exist yet."""
        if menus is not None and not isinstance(menus, Mapping):
            raise TypeError('menus must be a mapping')
        source = {'DEFAULT_MENU': DEFAULT_MENU} if menus is None else menus
        for order, (name, menu) in enumerate(source.items()):
            self._require_name(name, 'scheme')
            if not isinstance(menu, Mapping):
                raise TypeError('menu must be a mapping')
            with self.schemes.exclusive_transaction() as cursor:
                if self.schemes.get_scheme(name, _cursor_=cursor) is not None:
                    continue
                if order == 0:
                    self._clear_default(cursor)
                self.schemes.insert_row(
                    MenuSchemeRow(name, order, int(order == 0)),
                    _cursor_=cursor,
                )
                scheme = self.schemes.get_scheme(name, _cursor_=cursor)
                if scheme is None:
                    raise RuntimeError(f'Scheme insert failed: "{name}"')
                filtered = config_model_registry.filter_menu(menu)
                mapped = {
                    category: [_default_task_name(task) for task in tasks]
                    for category, tasks in filtered.items()
                }
                self._replace_groups(scheme, mapped, None, cursor)

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def add_group(
        self,
        scheme: str,
        name: str,
        tasks: Sequence[str] = (),
        *,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        """Create a group and its tasks in one transaction."""
        scheme_row = self.scheme(scheme)
        self._require_name(name, 'group')
        self._check_tasks(tasks)
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            if self.groups.get_group(scheme_row.id, name, _cursor_=cursor) is not None:
                raise ValueError(f'Group already exists: "{scheme}.{name}"')
            self._insert_group_at(
                scheme_row.id,
                MenuGroupRow(scheme_row.id, name, 0, title, description, icon),
                order,
                cursor,
            )
            group = self.groups.get_group(scheme_row.id, name, _cursor_=cursor)
            if group is None:
                raise RuntimeError(f'Group insert failed: "{scheme}.{name}"')
            for task_order, task in enumerate(tasks):
                self.tasks.insert_row(
                    MenuTaskRow(group.id, task, task_order),
                    _cursor_=cursor,
                )
        return self.group_view(scheme, name)

    def update_group(
        self,
        scheme: str,
        name: str,
        *,
        new_name: str | None = None,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        """Rename, reorder, or edit the metadata of a group."""
        scheme_row = self.scheme(scheme)
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            row = self.group(scheme, name, _cursor_=cursor)
            if new_name is not None:
                self._require_name(new_name, 'group')
                if new_name != name:
                    if (
                        self.groups.get_group(scheme_row.id, new_name, _cursor_=cursor)
                        is not None
                    ):
                        raise ValueError(f'Group already exists: "{scheme}.{new_name}"')
                    row.name = new_name
            if title is not None:
                row.title = title
            if description is not None:
                row.description = description
            if icon is not None:
                row.icon = icon
            self.groups.update_row(
                row,
                updates=(
                    'name',
                    'group_order',
                    'title',
                    'description',
                    'icon',
                ),
                _cursor_=cursor,
            )
            if order is not None:
                self._move_group(scheme_row.id, row.id, order, cursor)
        return self.group_view(scheme, row.name)

    def delete_group(self, scheme: str, name: str) -> bool:
        """Delete a group and its tasks, then close the order gap."""
        scheme_row = self.scheme(scheme)
        with self.schemes.exclusive_transaction() as cursor:
            row = self.group(scheme, name, _cursor_=cursor)
            self.tasks.delete_group(row.id, _cursor_=cursor)
            self.groups.delete(_cursor_=cursor, id=row.id)
            self._resequence_groups(scheme_row.id, cursor)
        return True

    def copy_group(
        self,
        source_scheme: str,
        source_group: str,
        target_scheme: str,
        target_group: str,
    ) -> dict[str, Any]:
        """Copy a group, including metadata, to the end of a scheme."""
        source = self.group_view(source_scheme, source_group)
        return self.add_group(
            target_scheme,
            target_group,
            source['tasks'],
            title=source['title'],
            description=source['description'],
            icon=source['icon'],
        )

    def move_group(
        self, scheme: str, name: str, order: int | None = None
    ) -> dict[str, Any]:
        """Move a group to another position inside the same scheme."""
        scheme_row = self.scheme(scheme)
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            row = self.group(scheme, name, _cursor_=cursor)
            self._move_group(scheme_row.id, row.id, order, cursor)
        return self.group_view(scheme, name)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def add_task(
        self,
        scheme: str,
        group: str,
        task: str,
        *,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Append or insert a task in a group."""
        group_row = self.group(scheme, group)
        self._require_name(task, 'task')
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            if (
                self.tasks.select_one(group_id=group_row.id, task=task, _cursor_=cursor)
                is not None
            ):
                raise ValueError(f'Task already exists: "{task}"')
            self._insert_task_at(
                group_row.id,
                MenuTaskRow(group_row.id, task),
                order,
                cursor,
            )
        return self.task_view(scheme, group, task)

    def delete_task(self, scheme: str, group: str, task: str) -> bool:
        """Delete a task, then close the order gap."""
        group_row = self.group(scheme, group)
        with self.schemes.exclusive_transaction() as cursor:
            row = self.task(scheme, group, task, _cursor_=cursor)
            self.tasks.delete(_cursor_=cursor, id=row.id)
            self._resequence_tasks(group_row.id, cursor)
        return True

    def copy_task(
        self,
        source_scheme: str,
        source_group: str,
        task: str,
        target_scheme: str,
        target_group: str,
        *,
        new_task: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Copy a task to another group."""
        self.task(source_scheme, source_group, task)
        target = task if new_task is None else new_task
        return self.add_task(target_scheme, target_group, target, order=order)

    def move_task(
        self,
        scheme: str,
        group: str,
        task: str,
        *,
        target_group: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Move a task within its group or to another group."""
        order = self._check_order(order)
        with self.schemes.exclusive_transaction() as cursor:
            scheme_name, group_name = self._move_task(
                scheme, group, task, target_group, order, cursor
            )
        return self.task_view(scheme_name, group_name, task)

    # ------------------------------------------------------------------
    # Menu API (menu_<obj>_<verb>)
    # ------------------------------------------------------------------

    def menu_scheme_list(self) -> list[dict[str, Any]]:
        return self.list()

    def menu_scheme_get(self, name: str) -> dict[str, Any]:
        return self.view(name)

    def menu_scheme_add(
        self,
        name: str,
        groups: MenuGroups | None = None,
        *,
        order: int | None = None,
        is_default: bool = False,
        group_metadata: MenuMetadata | None = None,
    ) -> dict[str, Any]:
        return self.add(
            name,
            groups,
            scheme_order=order,
            is_default=is_default,
            group_metadata=group_metadata,
        )

    def menu_scheme_update(
        self,
        name: str,
        *,
        new_name: str | None = None,
        order: int | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        return self.update_scheme(
            name,
            new_name=new_name,
            order=order,
            is_default=is_default,
        )

    def menu_scheme_delete(self, name: str) -> bool:
        return self.delete(name)

    def menu_scheme_copy(self, source: str, target: str) -> dict[str, Any]:
        return self.copy_scheme(source, target)

    def menu_scheme_replace(
        self,
        name: str,
        groups: MenuGroups,
        *,
        group_metadata: MenuMetadata | None = None,
    ) -> dict[str, Any]:
        return self.replace(name, groups, group_metadata=group_metadata)

    def menu_scheme_seed(
        self, menus: Mapping[str, MenuGroups] | None = None
    ) -> list[dict[str, Any]]:
        self.seed_defaults(menus)
        return self.list()

    def menu_group_get(self, scheme: str, group: str) -> dict[str, Any]:
        return self.group_view(scheme, group)

    def menu_group_add(
        self,
        scheme: str,
        group: str,
        tasks: Sequence[str] = (),
        *,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        return self.add_group(
            scheme,
            group,
            tasks,
            order=order,
            title=title,
            description=description,
            icon=icon,
        )

    def menu_group_update(
        self,
        scheme: str,
        group: str,
        *,
        new_group: str | None = None,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        return self.update_group(
            scheme,
            group,
            new_name=new_group,
            order=order,
            title=title,
            description=description,
            icon=icon,
        )

    def menu_group_delete(self, scheme: str, group: str) -> bool:
        return self.delete_group(scheme, group)

    def menu_group_copy(
        self,
        source_scheme: str,
        source_group: str,
        target_scheme: str,
        target_group: str,
    ) -> dict[str, Any]:
        return self.copy_group(
            source_scheme,
            source_group,
            target_scheme,
            target_group,
        )

    def menu_group_move(self, scheme: str, group: str, order: int | None = None) -> dict[str, Any]:
        return self.move_group(scheme, group, order)

    def menu_task_get(self, scheme: str, group: str, task: str) -> dict[str, Any]:
        return self.task_view(scheme, group, task)

    def menu_task_add(
        self,
        scheme: str,
        group: str,
        task: str,
        *,
        order: int | None = None,
    ) -> dict[str, Any]:
        return self.add_task(scheme, group, task, order=order)

    def menu_task_delete(self, scheme: str, group: str, task: str) -> bool:
        return self.delete_task(scheme, group, task)

    def menu_task_copy(
        self,
        source_scheme: str,
        source_group: str,
        task: str,
        target_scheme: str,
        target_group: str,
        *,
        new_task: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        return self.copy_task(
            source_scheme,
            source_group,
            task,
            target_scheme,
            target_group,
            new_task=new_task,
            order=order,
        )

    def menu_task_move(
        self,
        scheme: str,
        group: str,
        task: str,
        *,
        target_group: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        return self.move_task(scheme, group, task, target_group=target_group, order=order)


class modmenu(ModAdapter):
    """Decorators for Scheme, Group and Task menu CRUD operations.

    ``modmenu`` itself stores no menu state.  The first decorated call mounts
    one :class:`MenuEntry` on the target instance (``__menu_entry__``), keyed by
    the instance's ``config_name``; later calls reuse that entry.  This mirrors
    how ``modconfig`` mounts its shared adapter.

    Every ``menu_*`` classmethod is a decorator factory for an instance method
    with this shape::

        def method(self, result, config_name, ...):
            return result

    The decorator computes ``result`` and inserts it after ``self``; ``result``
    is hidden from ``inspect.signature``.  The decorated method must return
    ``result`` unchanged.  The arguments documented on each factory are the
    arguments of the decorated method, not of the factory itself.

    All operations share one error contract:

    * empty or whitespace-only names raise :class:`ValueError`;
    * non-string names raise :class:`TypeError`;
    * a missing scheme, group, or task raises :class:`KeyError`;
    * creating a duplicate scheme, group, or task raises :class:`ValueError`;
    * passing a ``config_name`` different from the target instance's
      ``config_name`` raises :class:`ValueError`;
    * multi-row writes are atomic and roll back completely on failure.
    """

    _entry_attribute = '__menu_entry__'

    @classmethod
    def _entry(cls, target: Any, config_name: str) -> MenuEntry:
        if not hasattr(target, 'config_name'):
            raise AttributeError(f'{type(target).__name__} must define config_name')
        if target.config_name != config_name:
            raise ValueError(
                f'config_name mismatch: {config_name!r} != {target.config_name!r}'
            )
        entry = getattr(target, cls._entry_attribute, None)
        if entry is not None:
            return entry
        entry = MenuEntry(config_name)
        setattr(target, cls._entry_attribute, entry)
        return entry

    @classmethod
    def _decorate(cls, function: F, implementation: Callable[..., Any]) -> F:
        if not callable(function):
            raise TypeError('modmenu decorators must decorate a callable')

        @wraps(function)
        def wrapper(target: Any, *args: Any, **kwargs: Any) -> Any:
            result = implementation(target, *args, **kwargs)
            return function(target, result, *args, **kwargs)

        signature = inspect.signature(function)
        wrapper.__signature__ = signature.replace(  # type: ignore[attr-defined]
            parameters=[
                parameter
                for name, parameter in signature.parameters.items()
                if name != 'result'
            ]
        )
        wrapper.__annotations__ = {
            name: value
            for name, value in function.__annotations__.items()
            if name != 'result'
        }
        return wrapper  # type: ignore[return-value]

    @classmethod
    def _factory(cls, implementation: Callable[..., Any]) -> Callable[[F], F]:
        return lambda function: cls._decorate(function, implementation)

    # ------------------------------------------------------------------
    # Decorator factories
    # ------------------------------------------------------------------

    @classmethod
    def menu_scheme_list(cls) -> Callable[[F], F]:
        """Decorate a method that lists every UI menu scheme.

        The decorated method signature is::

            def menu_scheme_list(self, result, config_name):
                return result

        Args:
            config_name: Configuration database name, for example
                ``"default"``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as a ``list[dict[str, Any]]`` ordered by
            ``scheme_order`` and must return it unchanged.  Each view has the
            shape::

                {
                    "name": str,
                    "scheme_order": int,
                    "is_default": bool,
                    "groups": {
                        group_name: {
                            "group_order": int,
                            "title": str | None,
                            "description": str | None,
                            "icon": str | None,
                            "tasks": [task_name, ...],
                        },
                    },
                }

        Example:
            .. code-block:: python

                class MenuMod:
                    @modmenu.menu_scheme_list()
                    def menu_scheme_list(self, result, config_name):
                        return result

                MenuMod("default").menu_scheme_list("default")
        """
        return cls._factory(cls._scheme_list)

    @classmethod
    def menu_scheme_get(cls) -> Callable[[F], F]:
        """Decorate a method that reads one scheme by name.

        The decorated method signature is::

            def menu_scheme_get(self, result, config_name, name):
                return result

        Args:
            config_name: Configuration database name.
            name: Scheme name.  Empty names raise ``ValueError``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the complete scheme view ``{name, scheme_order,
            is_default, groups}`` and must return it unchanged.

        Raises:
            KeyError: The scheme does not exist.

        Example:
            .. code-block:: python

                view = menu.menu_scheme_get("default", "DEFAULT_MENU")
                tasks = view["groups"]["Script"]["tasks"]
        """
        return cls._factory(cls._scheme_get)

    @classmethod
    def menu_scheme_add(cls) -> Callable[[F], F]:
        """Decorate a method that creates a scheme and its groups.

        The decorated method signature is::

            def menu_scheme_add(
                self, result, config_name, name, groups=None, *,
                order=None, is_default=False,
            ):
                return result

        Args:
            config_name: Configuration database name.
            name: New scheme name.
            groups: Optional mapping of group name to an ordered sequence of
                Task instance names.  Group and Task names must be non-empty
                strings, and one Task may appear only once in the scheme.
            order: Scheme position.  ``None`` appends after the current last
                scheme; an integer inserts at that position.
            is_default: When true, the new scheme becomes the only default
                scheme; other defaults are cleared.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the view of the new scheme and must return it
            unchanged.

        Raises:
            ValueError: The scheme already exists, a name is empty, or a Task
                appears more than once.
            TypeError: A name is not a string, or ``groups`` has an invalid
                shape.

        Notes:
            The scheme row, all group rows, and all task rows are inserted in
            one transaction.  A failure leaves no partial scheme behind.

        Example:
            .. code-block:: python

                menu.menu_scheme_add(
                    "default",
                    "MY_MENU",
                    {"Script": ["Script@default"], "Daily": []},
                    is_default=True,
                )
        """
        return cls._factory(cls._scheme_add)

    @classmethod
    def menu_scheme_update(cls) -> Callable[[F], F]:
        """Decorate a method that renames, reorders, or edits a scheme.

        The decorated method signature is::

            def menu_scheme_update(
                self, result, config_name, name, *,
                new_name=None, order=None, is_default=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            name: Existing scheme name.
            new_name: New name.  ``None`` keeps the current name.
            order: New position.  ``None`` keeps the current position.
            is_default: ``True`` makes this the only default scheme,
                ``False`` clears the flag, ``None`` leaves it unchanged.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the updated scheme view and must return it
            unchanged.

        Raises:
            KeyError: The scheme does not exist.
            ValueError: ``new_name`` is empty or already used by another
                scheme.

        Example:
            .. code-block:: python

                menu.menu_scheme_update(
                    "default", "MY_MENU", new_name="MY_LAYOUT",
                    order=0, is_default=True,
                )
        """
        return cls._factory(cls._scheme_update)

    @classmethod
    def menu_scheme_delete(cls) -> Callable[[F], F]:
        """Decorate a method that deletes a scheme and all of its children.

        The decorated method signature is::

            def menu_scheme_delete(self, result, config_name, name):
                return result

        Args:
            config_name: Configuration database name.
            name: Existing scheme name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``True`` and must return it unchanged.

        Raises:
            KeyError: The scheme does not exist.  Deletion is not silently
                idempotent.

        Notes:
            The scheme row, its group rows, and its task rows are deleted in
            one transaction.

        Example:
            .. code-block:: python

                menu.menu_scheme_delete("default", "MY_MENU")
        """
        return cls._factory(cls._scheme_delete)

    @classmethod
    def menu_scheme_copy(cls) -> Callable[[F], F]:
        """Decorate a method that copies a scheme to the end of the list.

        The decorated method signature is::

            def menu_scheme_copy(self, result, config_name, source, target):
                return result

        Args:
            config_name: Configuration database name.
            source: Existing scheme to copy.
            target: New scheme name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the view of the copied scheme and must return it
            unchanged.

        Raises:
            KeyError: The source scheme does not exist.
            ValueError: The target name is empty or already exists.

        Notes:
            Group order, task order, and group metadata (``title``,
            ``description``, ``icon``) are preserved.  The copy is appended
            after the current last scheme and its ``is_default`` flag is
            forced to ``False``.

        Example:
            .. code-block:: python

                menu.menu_scheme_copy("default", "MY_MENU", "MY_MENU_BACKUP")
        """
        return cls._factory(cls._scheme_copy)

    @classmethod
    def menu_scheme_replace(cls) -> Callable[[F], F]:
        """Decorate a method that replaces the groups of an existing scheme.

        The decorated method signature is::

            def menu_scheme_replace(self, result, config_name, name, groups):
                return result

        Args:
            config_name: Configuration database name.
            name: Existing scheme name.
            groups: Mapping of group name to an ordered sequence of Task
                instance names.  All old groups and tasks are removed first.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the replaced scheme view and must return it
            unchanged.

        Raises:
            KeyError: The scheme does not exist.  Use ``menu_scheme_add`` to
                create a scheme.
            ValueError: A group or Task name is empty, or a Task appears more
                than once.
            TypeError: ``groups`` is not a mapping.

        Notes:
            Deletion of the old rows and insertion of the new rows happen in
            one transaction, so an invalid replacement keeps the previous
            layout intact.

        Example:
            .. code-block:: python

                menu.menu_scheme_replace(
                    "default", "MY_MENU",
                    {"Script": ["Script@default"], "Empty": []},
                )
        """
        return cls._factory(cls._scheme_replace)

    @classmethod
    def menu_scheme_seed(cls) -> Callable[[F], F]:
        """Decorate a method that creates the missing default menu schemes.

        The decorated method signature is::

            def menu_scheme_seed(self, result, config_name, menus=None):
                return result

        Args:
            config_name: Configuration database name.
            menus: Optional mapping of scheme name to menu groups.  Each menu
                maps a group name to an ordered sequence of Task names.  When
                omitted, ``DEFAULT_MENU`` is used.  Bare Task class names
                such as ``"FindJade"`` are expanded to the default instance
                name ``"FindJade@default"``; names that already contain
                ``"@"`` are kept unchanged.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the complete list of scheme views after seeding and
            must return it unchanged.

        Raises:
            ValueError: A scheme or group name is empty.
            TypeError: A name is not a string, or ``menus`` is not a mapping.

        Notes:
            Existing schemes are skipped entirely, so this method is safe to
            call repeatedly.  Each missing scheme is created in its own
            transaction.  The first scheme in ``menus`` becomes the default
            scheme; other defaults are cleared.

        Example:
            .. code-block:: python

                menu.menu_scheme_seed("default")

                menu.menu_scheme_seed(
                    "default",
                    {"CUSTOM": {"Script": ["FindJade"]}},
                )
        """
        return cls._factory(cls._scheme_seed)

    @classmethod
    def menu_group_get(cls) -> Callable[[F], F]:
        """Decorate a method that reads one group inside a scheme.

        The decorated method signature is::

            def menu_group_get(self, result, config_name, scheme, group):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Group name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the group view and must return it unchanged::

                {
                    "group_order": int,
                    "title": str | None,
                    "description": str | None,
                    "icon": str | None,
                    "tasks": [task_name, ...],
                }

        Raises:
            KeyError: The scheme or group does not exist.

        Example:
            .. code-block:: python

                group = menu.menu_group_get("default", "MY_MENU", "Script")
                assert group["tasks"] == ["Script@default"]
        """
        return cls._factory(cls._group_get)

    @classmethod
    def menu_group_add(cls) -> Callable[[F], F]:
        """Decorate a method that creates a group and its tasks.

        The decorated method signature is::

            def menu_group_add(
                self, result, config_name, scheme, group, tasks=(), *,
                order=None, title=None, description=None, icon=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Existing scheme name.
            group: New group name.
            tasks: Ordered Task instance names.  A Task may appear only once
                in the group.
            order: Group position inside the scheme.  ``None`` appends;
                out-of-range integers are clamped to the valid range.
            title: Optional display title.
            description: Optional display description.
            icon: Optional icon name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the new group view and must return it unchanged.

        Raises:
            KeyError: The scheme does not exist.
            ValueError: The group already exists, or a Task appears more than
                once in ``tasks``.
            TypeError: A name is not a string, or ``tasks`` is not a sequence.

        Notes:
            The group row and all task rows are inserted in one transaction.

        Example:
            .. code-block:: python

                menu.menu_group_add(
                    "default", "MY_MENU", "Daily",
                    ["DailyTrifles@default", "Pets@default"],
                    title="Daily", icon="calendar",
                )
        """
        return cls._factory(cls._group_add)

    @classmethod
    def menu_group_update(cls) -> Callable[[F], F]:
        """Decorate a method that edits a group's name, order, or metadata.

        The decorated method signature is::

            def menu_group_update(
                self, result, config_name, scheme, group, *,
                new_group=None, order=None, title=None,
                description=None, icon=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Existing group name.
            new_group: New group name.  ``None`` keeps the current name.
            order: New position inside the scheme.  ``None`` keeps the current
                position; out-of-range integers are clamped.
            title: New title.  ``None`` keeps the current value.
            description: New description.  ``None`` keeps the current value.
            icon: New icon.  ``None`` keeps the current value.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the updated group view and must return it unchanged.

        Raises:
            KeyError: The scheme or group does not exist.
            ValueError: ``new_group`` is empty or already used in the scheme.

        Notes:
            Renaming and reordering happen in one transaction.

        Example:
            .. code-block:: python

                menu.menu_group_update(
                    "default", "MY_MENU", "Daily",
                    new_group="Daily Task", order=0, icon="calendar",
                )
        """
        return cls._factory(cls._group_update)

    @classmethod
    def menu_group_delete(cls) -> Callable[[F], F]:
        """Decorate a method that deletes a group and its tasks.

        The decorated method signature is::

            def menu_group_delete(self, result, config_name, scheme, group):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Existing group name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``True`` and must return it unchanged.

        Raises:
            KeyError: The scheme or group does not exist.

        Notes:
            Remaining groups are resequenced so their ``group_order`` values
            stay contiguous.  The task rows and the group row are deleted in
            one transaction.

        Example:
            .. code-block:: python

                menu.menu_group_delete("default", "MY_MENU", "Daily")
        """
        return cls._factory(cls._group_delete)

    @classmethod
    def menu_group_copy(cls) -> Callable[[F], F]:
        """Decorate a method that copies a group into another scheme.

        The decorated method signature is::

            def menu_group_copy(
                self, result, config_name, source_scheme, source_group,
                target_scheme, target_group,
            ):
                return result

        Args:
            config_name: Configuration database name.
            source_scheme: Scheme containing the source group.
            source_group: Existing group to copy.
            target_scheme: Scheme that receives the copy.
            target_group: New group name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the copied group view and must return it unchanged.

        Raises:
            KeyError: The source scheme, source group, or target scheme does
                not exist.
            ValueError: The target group already exists in the target scheme.

        Notes:
            The copy keeps ``title``, ``description``, ``icon``, and task
            order, and is appended after the target scheme's last group.

        Example:
            .. code-block:: python

                menu.menu_group_copy(
                    "default", "MY_MENU", "Daily",
                    "MY_MENU", "Daily Backup",
                )
        """
        return cls._factory(cls._group_copy)

    @classmethod
    def menu_group_move(cls) -> Callable[[F], F]:
        """Decorate a method that moves a group inside its scheme.

        The decorated method signature is::

            def menu_group_move(
                self, result, config_name, scheme, group, order=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Existing group name.
            order: New zero-based position.  ``None`` appends; out-of-range
                integers are clamped to the valid range.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the moved group view and must return it unchanged.

        Raises:
            KeyError: The scheme or group does not exist.

        Notes:
            A group cannot move to another scheme through this decorator; use
            ``menu_group_copy`` followed by ``menu_group_delete`` for that.
            All affected ``group_order`` values are rewritten in one
            transaction.

        Example:
            .. code-block:: python

                menu.menu_group_move("default", "MY_MENU", "Daily", 0)
        """
        return cls._factory(cls._group_move)

    @classmethod
    def menu_task_get(cls) -> Callable[[F], F]:
        """Decorate a method that reads one task inside a group.

        The decorated method signature is::

            def menu_task_get(
                self, result, config_name, scheme, group, task,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Group name.
            task: Task instance name, for example ``"FindJade@default"``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the task view and must return it unchanged::

                {
                    "group": str,
                    "task": str,
                    "task_order": int,
                }

        Raises:
            KeyError: The scheme, group, or task does not exist.

        Example:
            .. code-block:: python

                task = menu.menu_task_get(
                    "default", "MY_MENU", "Daily", "Pets@default",
                )
                assert task["task_order"] == 0
        """
        return cls._factory(cls._task_get)

    @classmethod
    def menu_task_add(cls) -> Callable[[F], F]:
        """Decorate a method that adds a task to a group.

        The decorated method signature is::

            def menu_task_add(
                self, result, config_name, scheme, group, task, *,
                order=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Existing group name.
            task: Task instance name, for example ``"FindJade@default"``.
            order: Task position inside the group.  ``None`` appends;
                out-of-range integers are clamped to the valid range.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the new task view and must return it unchanged.

        Raises:
            KeyError: The scheme or group does not exist.
            ValueError: The task already exists in the group.

        Example:
            .. code-block:: python

                menu.menu_task_add(
                    "default", "MY_MENU", "Daily", "Pets@default",
                )
        """
        return cls._factory(cls._task_add)

    @classmethod
    def menu_task_delete(cls) -> Callable[[F], F]:
        """Decorate a method that deletes a task from a group.

        The decorated method signature is::

            def menu_task_delete(
                self, result, config_name, scheme, group, task,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Group name.
            task: Existing task instance name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``True`` and must return it unchanged.

        Raises:
            KeyError: The scheme, group, or task does not exist.

        Notes:
            Remaining tasks are resequenced so their ``task_order`` values stay
            contiguous.

        Example:
            .. code-block:: python

                menu.menu_task_delete(
                    "default", "MY_MENU", "Daily", "Pets@default",
                )
        """
        return cls._factory(cls._task_delete)

    @classmethod
    def menu_task_copy(cls) -> Callable[[F], F]:
        """Decorate a method that copies a task to another group.

        The decorated method signature is::

            def menu_task_copy(
                self, result, config_name, source_scheme, source_group,
                task, target_scheme, target_group, *,
                new_task=None, order=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            source_scheme: Scheme containing the source task.
            source_group: Group containing the source task.
            task: Existing task instance name.
            target_scheme: Scheme that receives the copy.
            target_group: Group that receives the copy.
            new_task: Name of the copy.  ``None`` reuses the source Task name.
            order: Position inside the target group.  ``None`` appends;
                out-of-range integers are clamped.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the copied task view and must return it unchanged.

        Raises:
            KeyError: The source scheme, source group, target scheme, or
                target group does not exist.
            ValueError: The target group already contains a task with the
                target name.

        Example:
            .. code-block:: python

                menu.menu_task_copy(
                    "default", "MY_MENU", "Daily", "Pets@default",
                    "MY_MENU", "Daily Backup",
                )
        """
        return cls._factory(cls._task_copy)

    @classmethod
    def menu_task_move(cls) -> Callable[[F], F]:
        """Decorate a method that moves a task inside or across groups.

        The decorated method signature is::

            def menu_task_move(
                self, result, config_name, scheme, group, task, *,
                target_group=None, order=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            scheme: Scheme name.
            group: Current group name.
            task: Existing task instance name.
            target_group: Destination group.  ``None`` keeps the task in its
                current group and only changes its order.
            order: Position inside the destination group.  ``None`` appends;
                out-of-range integers are clamped.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the moved task view and must return it unchanged.

        Raises:
            KeyError: The scheme, source group, task, or target group does not
                exist.
            ValueError: The target group already contains a task with the same
                name.

        Notes:
            Both groups are updated in one transaction.  A failure, including
            a duplicate name in the target group, leaves the source task in
            place.

        Example:
            .. code-block:: python

                # Reorder inside the same group.
                menu.menu_task_move(
                    "default", "MY_MENU", "Daily", "Pets@default", order=0,
                )

                # Move to another group.
                menu.menu_task_move(
                    "default", "MY_MENU", "Daily", "Pets@default",
                    target_group="Daily Backup",
                )
        """
        return cls._factory(cls._task_move)

    # ------------------------------------------------------------------
    # Scheme implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _scheme_list(target: Any, config_name: str) -> list[dict[str, Any]]:
        return modmenu._entry(target, config_name).list()

    @staticmethod
    def _scheme_get(target: Any, config_name: str, name: str) -> dict[str, Any]:
        return modmenu._entry(target, config_name).view(name)

    @staticmethod
    def _scheme_add(
        target: Any,
        config_name: str,
        name: str,
        groups: MenuGroups | None = None,
        *,
        order: int | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).add(
            name,
            groups,
            scheme_order=order,
            is_default=is_default,
        )

    @staticmethod
    def _scheme_update(
        target: Any,
        config_name: str,
        name: str,
        *,
        new_name: str | None = None,
        order: int | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).update_scheme(
            name,
            new_name=new_name,
            order=order,
            is_default=is_default,
        )

    @staticmethod
    def _scheme_delete(target: Any, config_name: str, name: str) -> bool:
        return modmenu._entry(target, config_name).delete(name)

    @staticmethod
    def _scheme_copy(
        _target: Any, config_name: str, source: str, target: str
    ) -> dict[str, Any]:
        return modmenu._entry(_target, config_name).copy_scheme(source, target)

    @staticmethod
    def _scheme_replace(
        target: Any,
        config_name: str,
        name: str,
        groups: MenuGroups,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).replace(name, groups)

    @staticmethod
    def _scheme_seed(
        target: Any,
        config_name: str,
        menus: Mapping[str, MenuGroups] | None = None,
    ) -> list[dict[str, Any]]:
        entry = modmenu._entry(target, config_name)
        entry.seed_defaults(menus)
        return entry.list()

    # ------------------------------------------------------------------
    # Group implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _group_get(
        target: Any, config_name: str, scheme: str, group: str
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).group_view(scheme, group)

    @staticmethod
    def _group_add(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        tasks: Sequence[str] = (),
        *,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).add_group(
            scheme,
            group,
            tasks,
            order=order,
            title=title,
            description=description,
            icon=icon,
        )

    @staticmethod
    def _group_update(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        *,
        new_group: str | None = None,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).update_group(
            scheme,
            group,
            new_name=new_group,
            order=order,
            title=title,
            description=description,
            icon=icon,
        )

    @staticmethod
    def _group_delete(target: Any, config_name: str, scheme: str, group: str) -> bool:
        return modmenu._entry(target, config_name).delete_group(scheme, group)

    @staticmethod
    def _group_copy(
        target: Any,
        config_name: str,
        source_scheme: str,
        source_group: str,
        target_scheme: str,
        target_group: str,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).copy_group(
            source_scheme,
            source_group,
            target_scheme,
            target_group,
        )

    @staticmethod
    def _group_move(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        order: int | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).move_group(scheme, group, order)

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _task_get(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        task: str,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).task_view(scheme, group, task)

    @staticmethod
    def _task_add(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        task: str,
        *,
        order: int | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).add_task(
            scheme, group, task, order=order
        )

    @staticmethod
    def _task_delete(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        task: str,
    ) -> bool:
        return modmenu._entry(target, config_name).delete_task(scheme, group, task)

    @staticmethod
    def _task_copy(
        target: Any,
        config_name: str,
        source_scheme: str,
        source_group: str,
        task: str,
        target_scheme: str,
        target_group: str,
        *,
        new_task: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).copy_task(
            source_scheme,
            source_group,
            task,
            target_scheme,
            target_group,
            new_task=new_task,
            order=order,
        )

    @staticmethod
    def _task_move(
        target: Any,
        config_name: str,
        scheme: str,
        group: str,
        task: str,
        *,
        target_group: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        return modmenu._entry(target, config_name).move_task(
            scheme,
            group,
            task,
            target_group=target_group,
            order=order,
        )
