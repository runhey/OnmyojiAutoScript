"""Task and Group configuration rows."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import msgspec

from oas.config.table.base import ConfigDB


class ConfigRow(msgspec.Struct):
    """One serialized Group belonging to one Task instance."""

    taskclass: str
    task: str
    groupclass: str
    group: str
    value: bytes
    id: int = 0


class ConfigTable(ConfigDB):
    """Store one binary value for each Task/Group instance."""

    TABLE_NAME = "config"
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL,
        "taskclass" TEXT NOT NULL,
        "task" TEXT NOT NULL,
        "groupclass" TEXT NOT NULL,
        "group" TEXT NOT NULL,
        "value" BLOB NOT NULL,
        PRIMARY KEY ("id"),
        UNIQUE ("taskclass", "task", "groupclass", "group")
    );
    """
    MODEL = ConfigRow

    @staticmethod
    def _identity(
        taskclass: str,
        task: str,
        groupclass: str,
        group: str,
    ) -> dict[str, str]:
        return {
            "taskclass": taskclass,
            "task": task,
            "groupclass": groupclass,
            "group": group,
        }

    def get_group(
        self,
        taskclass: str,
        task: str,
        groupclass: str,
        group: str,
        *,
        _cursor_=None,
    ) -> ConfigRow | None:
        """Return one Group row, or ``None`` when it is absent."""

        return self.select_one(
            _cursor_=_cursor_,
            **self._identity(taskclass, task, groupclass, group),
        )

    def list_groups(
        self,
        taskclass: str,
        task: str,
        *,
        groupclass: str | None = None,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """List all Groups for a Task instance."""

        conditions = {"taskclass": taskclass, "task": task}
        if groupclass is not None:
            conditions["groupclass"] = groupclass
        return self.select(_cursor_=_cursor_, **conditions)

    def list_task_rows(
        self,
        taskclass: str,
        task: str,
        *,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """List every serialized Group belonging to a Task instance."""

        return self.list_groups(taskclass, task, _cursor_=_cursor_)

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
            raise TypeError("ConfigTable value must be bytes")
        row = ConfigRow(
            taskclass=taskclass,
            task=task,
            groupclass=groupclass,
            group=group,
            value=value,
        )
        self.upsert_row(
            row,
            conflicts=("taskclass", "task", "groupclass", "group"),
            _cursor_=_cursor_,
        )
        if _cursor_ is not None:
            return row
        return self.get_group(taskclass, task, groupclass, group)

    def delete_group(
        self,
        taskclass: str,
        task: str,
        groupclass: str,
        group: str,
        *,
        _cursor_=None,
    ) -> None:
        """Delete one Group row."""

        self.delete(
            _cursor_=_cursor_,
            **self._identity(taskclass, task, groupclass, group),
        )

    def delete_task(self, taskclass: str, task: str, *, _cursor_=None) -> None:
        """Delete all Group rows belonging to one Task instance."""

        self.delete(_cursor_=_cursor_, taskclass=taskclass, task=task)

    def read_task_rows(
        self,
        tasks: Sequence[str] | None = None,
        groups: Iterable[tuple[str, str, str, str]] = (),
        *,
        taskclasses: Sequence[str] | None = None,
        _cursor_=None,
    ) -> list[ConfigRow]:
        """Read selected Task classes/instances and exact Group identities.

        ``groups`` contains ``(taskclass, task, groupclass, group)`` tuples.
        ``tasks`` remains a convenience filter for task instance names; when
        ``taskclasses`` is supplied, both filters are applied together.
        """

        conditions: list[str] = []
        params: list[str] = []
        task_filters: list[str] = []
        if taskclasses:
            marks = ",".join("?" for _ in taskclasses)
            task_filters.append(f'"taskclass" IN ({marks})')
            params.extend(taskclasses)
        if tasks:
            marks = ",".join("?" for _ in tasks)
            task_filters.append(f'"task" IN ({marks})')
            params.extend(tasks)
        if task_filters:
            conditions.append("(" + " AND ".join(task_filters) + ")")
        for identity in groups:
            if len(identity) != 4:
                raise ValueError("group identity must contain four values")
            conditions.append(
                '("taskclass"=? AND "task"=? AND "groupclass"=? AND "group"=?)'
            )
            params.extend(identity)
        if not conditions:
            return self.select(_cursor_=_cursor_)
        sql = f'SELECT * FROM "{self.TABLE_NAME}" WHERE ' + " OR ".join(conditions)
        return self.select_by_sql(sql, params, _cursor_=_cursor_)

    def read_rows(self, events: Iterable[object], *, _cursor_=None) -> list[ConfigRow]:
        """Read rows from objects with four identity attributes."""

        groups = []
        for event in events:
            groups.append(
                (
                    event.taskclass,
                    event.task,
                    event.groupclass,
                    event.group,
                )
            )
        if not groups:
            return []
        return self.read_task_rows(groups=groups, _cursor_=_cursor_)


AlasioConfigTable = ConfigTable

__all__ = ["AlasioConfigTable", "ConfigRow", "ConfigTable"]
