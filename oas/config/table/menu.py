"""SQLite tables for user-configurable UI menu layouts."""

from __future__ import annotations

from collections.abc import Iterable

import msgspec

from oas.config.table.base import ConfigDB


class MenuSchemeRow(msgspec.Struct):
    """One complete UI menu scheme."""

    name: str
    scheme_order: int = 0
    is_default: int = 0
    id: int = 0


class MenuGroupRow(msgspec.Struct):
    """One group inside a UI menu scheme."""

    scheme_id: int
    name: str
    group_order: int = 0
    title: str | None = None
    description: str | None = None
    icon: str | None = None
    id: int = 0


class MenuTaskRow(msgspec.Struct):
    """One Task instance inside a UI menu group."""

    group_id: int
    task: str
    task_order: int = 0
    id: int = 0


class MenuSchemeTable(ConfigDB):
    """Store the available UI menu schemes."""

    TABLE_NAME = 'ui_menu_scheme'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL UNIQUE,
        "scheme_order" INTEGER NOT NULL DEFAULT 0,
        "is_default" INTEGER NOT NULL DEFAULT 0
    );
    """
    MODEL = MenuSchemeRow

    def get_scheme(self, name: str, *, _cursor_=None) -> MenuSchemeRow | None:
        return self.select_one(_cursor_=_cursor_, name=name)

    def list_schemes(self, *, _cursor_=None) -> list[MenuSchemeRow]:
        return self.select(_cursor_=_cursor_, _orderby_='scheme_order')

    def upsert_scheme(
        self,
        row: MenuSchemeRow,
        *,
        _cursor_=None,
    ) -> MenuSchemeRow:
        self.upsert_row(row, conflicts='name', _cursor_=_cursor_)
        if _cursor_ is not None:
            return row
        return self.get_scheme(row.name)


class MenuGroupTable(ConfigDB):
    """Store groups, including groups that currently contain no Tasks."""

    TABLE_NAME = 'ui_menu_group'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "scheme_id" INTEGER NOT NULL,
        "name" TEXT NOT NULL,
        "group_order" INTEGER NOT NULL DEFAULT 0,
        "title" TEXT,
        "description" TEXT,
        "icon" TEXT,
        FOREIGN KEY ("scheme_id") REFERENCES "ui_menu_scheme" ("id"),
        UNIQUE ("scheme_id", "name"),
        UNIQUE ("scheme_id", "group_order")
    );
    """
    MODEL = MenuGroupRow

    def get_group(
        self,
        scheme_id: int,
        name: str,
        *,
        _cursor_=None,
    ) -> MenuGroupRow | None:
        return self.select_one(_cursor_=_cursor_, scheme_id=scheme_id, name=name)

    def list_groups(self, scheme_id: int, *, _cursor_=None) -> list[MenuGroupRow]:
        return self.select(
            _cursor_=_cursor_,
            scheme_id=scheme_id,
            _orderby_='group_order',
        )

    def delete_scheme(self, scheme_id: int, *, _cursor_=None) -> None:
        self.delete(_cursor_=_cursor_, scheme_id=scheme_id)


class MenuTaskTable(ConfigDB):
    """Store ordered Task instances belonging to menu groups."""

    TABLE_NAME = 'ui_menu_task'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "group_id" INTEGER NOT NULL,
        "task" TEXT NOT NULL,
        "task_order" INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY ("group_id") REFERENCES "ui_menu_group" ("id"),
        UNIQUE ("group_id", "task"),
        UNIQUE ("group_id", "task_order")
    );
    """
    MODEL = MenuTaskRow

    def list_tasks(self, group_id: int, *, _cursor_=None) -> list[MenuTaskRow]:
        return self.select(
            _cursor_=_cursor_,
            group_id=group_id,
            _orderby_='task_order',
        )

    def delete_group(self, group_id: int, *, _cursor_=None) -> None:
        self.delete(_cursor_=_cursor_, group_id=group_id)

    def delete_groups(self, group_ids: Iterable[int], *, _cursor_=None) -> None:
        for group_id in group_ids:
            self.delete_group(group_id, _cursor_=_cursor_)
