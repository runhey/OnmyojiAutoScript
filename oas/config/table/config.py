"""Task and Group configuration rows."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import msgspec

from oas.config.table.base import ConfigDB


class ConfigRow(msgspec.Struct):
    """One serialized Group belonging to one Task instance."""

    task: str
    group: str
    taskclass: str
    groupclass: str
    value: bytes


class ConfigTable(ConfigDB):
    """Store one binary value for each Task/Group instance pair.

    ``task`` and ``group`` are the instance-name primary key.  The associated
    ``taskclass`` and ``groupclass`` are returned with the value and are not
    part of the row identity.
    """

    TABLE_NAME = 'config'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "task" TEXT NOT NULL,
        "group" TEXT NOT NULL,
        "taskclass" TEXT NOT NULL,
        "groupclass" TEXT NOT NULL,
        "value" BLOB NOT NULL,
        PRIMARY KEY ("task", "group")
    );
    """
    MODEL = ConfigRow

    @staticmethod
    def _identity(
        task: str,
        group: str,
    ) -> dict[str, str]:
        return {
            'task': task,
            'group': group,
        }

    def get_group(
        self,
        task: str,
        group: str,
        *,
        _cursor_=None,
    ) -> ConfigRow | None:
        """Return one Group row, or ``None`` when it is absent."""

        return self.select_one(
            _cursor_=_cursor_,
            **self._identity(task, group),
        )

    def list_groups(
        self,
        task: str,
        *,
        groupclass: str | None = None,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """List all Groups for a Task instance."""

        conditions = {'task': task}
        if groupclass is not None:
            conditions['groupclass'] = groupclass
        return self.select(_cursor_=_cursor_, **conditions)

    def list_task_rows(
        self,
        task: str,
        *,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """List every serialized Group belonging to a Task instance."""

        return self.list_groups(task, _cursor_=_cursor_)

    def upsert_group(
        self,
        taskclass: str,
        task: str,
        groupclass: str,
        group: str,
        value: bytes,
        *,
        _cursor_=None,
    ) -> ConfigRow:
        """Insert or update one Group's raw binary value."""

        if not isinstance(value, bytes):
            raise TypeError('ConfigTable value must be bytes')
        row = ConfigRow(
            taskclass=taskclass,
            task=task,
            groupclass=groupclass,
            group=group,
            value=value,
        )
        self.upsert_row(
            row,
            conflicts=('task', 'group'),
            _cursor_=_cursor_,
        )
        if _cursor_ is not None:
            return row
        return self.get_group(task, group)

    def delete_group(
        self,
        task: str,
        group: str,
        *,
        _cursor_=None,
    ) -> None:
        """Delete one Group row."""

        self.delete(
            _cursor_=_cursor_,
            **self._identity(task, group),
        )

    def delete_task(self, task: str, *, _cursor_=None) -> None:
        """Delete all Group rows belonging to one Task instance."""

        self.delete(_cursor_=_cursor_, task=task)

    def read_task_rows(
        self,
        tasks: Sequence[str] | None = None,
        groups: Iterable[tuple[str, str]] = (),
        *,
        taskclasses: Sequence[str] | None = None,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """Read selected Task classes/instances and exact Group identities.

        ``groups`` contains ``(task, group)`` primary-key tuples. ``tasks``
        remains a convenience filter for task instance names. ``taskclasses``
        can additionally restrict the class metadata stored in the rows.
        """

        conditions: list[str] = []
        params: list[str] = []
        task_filters: list[str] = []
        if taskclasses:
            marks = ','.join('?' for _ in taskclasses)
            task_filters.append(f'"taskclass" IN ({marks})')
            params.extend(taskclasses)
        if tasks:
            marks = ','.join('?' for _ in tasks)
            task_filters.append(f'"task" IN ({marks})')
            params.extend(tasks)
        if task_filters:
            conditions.append('(' + ' AND '.join(task_filters) + ')')
        for identity in groups:
            if len(identity) != 2:
                raise ValueError('group identity must contain task and group')
            conditions.append('("task"=? AND "group"=?)')
            params.extend(identity)
        if not conditions:
            return self.select(_cursor_=_cursor_)
        sql = f'SELECT * FROM "{self.TABLE_NAME}" WHERE ' + ' OR '.join(conditions)
        return self.select_by_sql(sql, params, _cursor_=_cursor_)

    def read_rows(self, events: Iterable[object], *, _cursor_=None) -> list[ConfigRow]:
        """Read rows from objects with ``task`` and ``group`` attributes."""

        groups = []
        for event in events:
            groups.append(
                (
                    event.task,
                    event.group,
                )
            )
        if not groups:
            return []
        return self.read_task_rows(groups=groups, _cursor_=_cursor_)


AlasioConfigTable = ConfigTable
