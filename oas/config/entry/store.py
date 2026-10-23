"""Read and write Task configuration in the configuration database.

A Task instance is stored as one ``config`` row per Group field::

    task        runtime Task instance name
    group       Group field name
    taskclass   Task model class name
    groupclass  Group model class name
    value       MsgPack payload of ``GroupBase.to_dict()``

``TaskStore`` combines ``TaskBase.to_dict()`` / ``from_dict()`` with
``Codec`` and ``ConfigTable``.  Model classes stay independent of the
database, and the table stays independent of Pydantic.
"""

from __future__ import annotations

from oas.config.entry.codec import Codec
from oas.config.models.tasks import TaskBase
from oas.config.table.config import ConfigTable


class TaskStore:
    """Read and write Task instances in a named configuration database.

    Every operation is a class method and takes ``config_name`` as its first
    argument, so the class holds no state and each call creates the
    :class:`ConfigTable` it needs.
    """

    @classmethod
    def save(cls, config_name: str, task: TaskBase, task_name: str) -> None:
        """Write one Task instance, replacing its stored Group set.

        Rows of this Task instance that no longer correspond to a Group field
        are deleted in the same transaction.
        """

        if not task_name:
            raise ValueError("task_name must not be empty")

        table = ConfigTable(config_name)
        data = task.to_dict()
        taskclass = type(task).__name__

        with table.cursor() as cursor:
            try:
                for row in table.list_task_rows(task_name, _cursor_=cursor):
                    if row.group not in data:
                        table.delete_group(
                            row.task,
                            row.group,
                            _cursor_=cursor,
                        )
                for group_name, payload in data.items():
                    table.upsert_group(
                        taskclass=taskclass,
                        task=task_name,
                        groupclass=type(getattr(task, group_name)).__name__,
                        group=group_name,
                        value=Codec.encode(payload),
                        _cursor_=cursor,
                    )
                cursor.commit()
            except BaseException:
                cursor.rollback()
                raise

    @classmethod
    def load(
        cls,
        config_name: str,
        task_class: type[TaskBase],
        task_name: str,
    ) -> TaskBase:
        """Read one Task instance, using Pydantic defaults for missing fields."""

        if not task_name:
            raise ValueError("task_name must not be empty")

        data = {
            row.group: Codec.decode(row.value)
            for row in ConfigTable(config_name).list_task_rows(task_name)
        }
        return task_class.from_dict(data)
