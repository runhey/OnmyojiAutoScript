"""Read and write Task configuration in the configuration database.

A Task instance is stored as one ``config`` row per Group::

    task        runtime Task instance name
    group       Group field name, or "<field>@<index>" for one instance of a
                dynamically managed Group list
    taskclass   Task model class name
    groupclass  Group model class name
    value       MsgPack payload of ``GroupBase.to_dict()``

Each instance of a dynamic Group list is its own row, so the list order is the
row index and no separate ordering column is needed.  ``TaskStore`` combines
``TaskBase.group_rows()`` / ``from_dict()`` with ``Codec`` and ``ConfigTable``.
Model classes stay independent of the database, and the table stays
independent of Pydantic.
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
        """Write one Task instance, replacing its stored Group rows.

        Rows of this Task instance that no longer correspond to a Group or to
        an instance of a dynamic Group list are deleted in the same
        transaction, so reordering or removing an instance resequences the
        stored addresses to ``<field>@0`` ... ``<field>@n-1``.
        """
        if not task_name:
            raise ValueError('task_name must not be empty')

        table = ConfigTable(config_name)
        rows = list(task.group_rows())
        taskclass = type(task).__name__
        addresses = {address for address, _group_class, _payload in rows}

        with table.cursor() as cursor:
            try:
                for row in table.list_task_rows(task_name, _cursor_=cursor):
                    if row.group not in addresses:
                        table.delete_group(
                            row.task,
                            row.group,
                            _cursor_=cursor,
                        )
                for address, group_class, payload in rows:
                    table.upsert_group(
                        taskclass=taskclass,
                        task=task_name,
                        groupclass=group_class.__name__,
                        group=address,
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
        """Read one Task instance, using Pydantic defaults for missing fields.

        Rows addressed as ``<field>@<index>`` are reassembled into the ordered
        instance list of that field.
        """
        if not task_name:
            raise ValueError('task_name must not be empty')

        data = {
            row.group: Codec.decode(row.value)
            for row in ConfigTable(config_name).list_task_rows(task_name)
        }
        return task_class.from_dict(data)
