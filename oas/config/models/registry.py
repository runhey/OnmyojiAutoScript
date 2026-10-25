"""Registry for declared configuration model classes.

The registry contains model classes only.  Runtime task and group instance
names belong to the configuration database and are deliberately not stored
here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, get_args, get_origin

from oas.ext.singleton import Singleton


def _is_group_type(annotation: Any) -> bool:
    if not isinstance(annotation, type):
        return False
    from oas.config.models.groups import GroupBase

    return issubclass(annotation, GroupBase) and annotation is not GroupBase


def _group_types(annotation: Any) -> tuple[type[Any], ...]:
    """Find GroupBase-derived annotations, including generic containers."""
    if _is_group_type(annotation):
        return (annotation,)

    result: list[type[Any]] = []
    for argument in get_args(annotation):
        for group_type in _group_types(argument):
            if group_type not in result:
                result.append(group_type)
    return tuple(result)


def is_dynamic_annotation(annotation: Any) -> bool:
    """Return whether an annotation declares a dynamically managed Group list.

    Only a ``list`` holding a concrete ``GroupBase`` subclass counts.  Other
    containers and Group-free lists carry Arg values, so they keep their
    existing treatment and must not be read as Group instances.  The check
    recurses, so ``list[GroupType] | None`` is recognized too.
    """
    if get_origin(annotation) is list and _group_types(annotation):
        return True
    return any(is_dynamic_annotation(argument) for argument in get_args(annotation))


class ConfigModelRegistry(metaclass=Singleton):
    """Store declared Task and Group model classes in one process-wide registry.

    ``data`` is the string-only relationship view used for discovery.  The
    class maps and ``group_index`` retain the actual Pydantic classes so the
    configuration layer can resolve a class after reading its class name.
    Runtime task and group instance names are never stored here.
    """

    _task_classes: dict[str, type[Any]]
    _task_fields: dict[type[Any], Mapping[str, type[Any]]]
    _group_classes: dict[str, type[Any]]
    _task_groups: dict[str, list[str]]
    _group_index: dict[tuple[str, str], type[Any]]

    def __init__(self) -> None:
        self._task_classes = {}
        self._task_fields = {}
        self._group_classes = {}
        self._task_groups = {}
        self._group_index = {}

    @staticmethod
    def qualified_name(model_type: type[Any]) -> str:
        """Return a stable class identifier for diagnostics and persistence."""
        return f'{model_type.__module__}.{model_type.__qualname__}'

    def register_group(self, group_type: type[Any]) -> None:
        """Register one concrete Group model class."""
        name = group_type.__name__
        self._group_classes[name] = group_type

    def register_task(self, task_type: type[Any]) -> None:
        """Register one concrete Task model and its Group fields."""
        task_name = task_type.__name__
        self._task_classes[task_name] = task_type
        field_groups: dict[str, type[Any]] = {}
        groups: list[str] = []
        for field_name, field in task_type.model_fields.items():
            candidates = _group_types(field.annotation)
            if not candidates:
                continue
            group_type = candidates[0]
            field_groups[field_name] = group_type
            group_name = group_type.__name__
            self.register_group(group_type)
            self._group_index[(task_name, group_name)] = group_type
            if group_name not in groups:
                groups.append(group_name)

        self._task_groups[task_name] = groups
        self._task_fields[task_type] = MappingProxyType(field_groups)

    @property
    def data(self) -> Mapping[str, list[str]]:
        return MappingProxyType(
            {name: list(groups) for name, groups in self._task_groups.items()}
        )

    @property
    def task_classes(self) -> Mapping[str, type[Any]]:
        return MappingProxyType(dict(self._task_classes))

    @property
    def group_classes(self) -> Mapping[str, type[Any]]:
        return MappingProxyType(dict(self._group_classes))

    @property
    def group_index(self) -> Mapping[tuple[str, str], type[Any]]:
        return MappingProxyType(dict(self._group_index))

    def get_task_class(self, taskclass: str) -> type[Any]:
        """Return a registered Task class by its class name.

        ``taskclass`` is a model class name such as ``"DebugTask"``.  It is
        deliberately not a runtime task instance name.
        """
        try:
            return self._task_classes[taskclass]
        except KeyError as exc:
            raise KeyError(f'unregistered TaskClass: {taskclass!r}') from exc

    def get_group_class(self, taskclass: str, groupclass: str) -> type[Any]:
        """Return a Group class by its owning Task and class names."""
        try:
            return self._group_index[(taskclass, groupclass)]
        except KeyError as exc:
            raise KeyError(
                f'unregistered GroupClass {groupclass!r} for TaskClass {taskclass!r}'
            ) from exc

    def groups_for_task(self, taskclass: str) -> tuple[type[Any], ...]:
        """Return all Group classes declared by a Task class name."""
        self.get_task_class(taskclass)
        return tuple(
            self._group_index[(taskclass, group_name)]
            for group_name in self._task_groups.get(taskclass, ())
        )

    @property
    def task_groups(self) -> Mapping[type[Any], tuple[type[Any], ...]]:
        """Read-only snapshot of ``TaskClass -> GroupClass tuple``."""
        return MappingProxyType(
            {
                task_type: tuple(
                    self._group_index[(name, group)]
                    for group in self._task_groups.get(name, ())
                )
                for name, task_type in self._task_classes.items()
            }
        )

    @property
    def task_fields(self) -> Mapping[type[Any], Mapping[str, type[Any]]]:
        """Read-only mapping of Task field names to Group classes."""
        return MappingProxyType(dict(self._task_fields))

    @property
    def groups(self) -> Mapping[str, tuple[type[Any], ...]]:
        """Read-only Group classes indexed by their short class name."""
        return MappingProxyType(
            {name: (model,) for name, model in self._group_classes.items()}
        )

    def find_tasks(self, name: str) -> tuple[type[Any], ...]:
        """Return registered Task classes with the given class name."""
        model = self._task_classes.get(name)
        return () if model is None else (model,)

    def is_task_registered(self, name: str) -> bool:
        """Return whether a Task class with ``name`` has been registered."""
        return name in self._task_classes

    def filter_menu(
        self,
        menu: Mapping[str, Iterable[str]],
    ) -> dict[str, list[str]]:
        """Keep only registered Tasks from a default UI menu definition.

        Menu categories and Task order are preserved. Entries for unknown
        Tasks are ignored, and categories with no registered Tasks are omitted.
        The registry does not add Tasks that are absent from ``menu``.
        """
        filtered: dict[str, list[str]] = {}
        for category, task_names in menu.items():
            tasks = [
                name
                for name in task_names
                if self.is_task_registered(name.partition('@')[0])
            ]
            if tasks:
                filtered[category] = tasks
        return filtered

    def find_groups(self, name: str) -> tuple[type[Any], ...]:
        """Return registered Group classes with the given class name."""
        model = self._group_classes.get(name)
        return () if model is None else (model,)

    def groups_for(self, task_type: type[Any]) -> tuple[type[Any], ...]:
        """Return the Group classes declared by ``task_type``."""
        name = task_type if isinstance(task_type, str) else task_type.__name__
        return tuple(
            self._group_index[(name, group)]
            for group in self._task_groups.get(name, ())
        )

    def group_for_field(
        self, task_type: type[Any], field_name: str
    ) -> type[Any] | None:
        """Return the Group class declared by one Task field."""
        return self._task_fields.get(task_type, {}).get(field_name)

    def dynamic_fields(self, task_type: type[Any]) -> Mapping[str, type[Any]]:
        """Return ``{field name: element Group class}`` of one Task class.

        Only dynamically managed Group lists are listed, so a caller can tell
        a list of instances apart from a single Group field; the latter is
        reported by :meth:`group_for_field` instead.  One instance of a listed
        field is addressed as ``field@index`` in the database and in events.
        """
        result: dict[str, type[Any]] = {}
        for field_name, field in getattr(task_type, 'model_fields', {}).items():
            if not is_dynamic_annotation(field.annotation):
                continue
            candidates = _group_types(field.annotation)
            if candidates:
                result[field_name] = candidates[0]
        return MappingProxyType(result)

    def clear(self) -> None:
        """Clear registrations, primarily for isolated tests."""
        self._task_classes.clear()
        self._task_fields.clear()
        self._group_classes.clear()
        self._task_groups.clear()
        self._group_index.clear()


class TaskNameResolver:
    """Translate ``TaskClass@name`` strings to registered Task classes."""

    @classmethod
    def split(cls, task: str) -> tuple[str, str]:
        """Split ``TaskClass@name``; plain legacy names return ``("", task)``."""
        taskclass, separator, name = task.partition('@')
        if separator and taskclass and name:
            return taskclass, name
        return '', task

    @classmethod
    def make(cls, taskclass: str, name: str) -> str:
        """Build the stored ``TaskClass@name`` string.

        Args:
            taskclass: Registered Task class name.
            name: Instance name.

        Returns:
            The ``TaskClass@name`` string stored in the ``task`` column.

        Raises:
            ValueError: If either part is empty or contains ``"@"``.
        """
        if not isinstance(taskclass, str) or not taskclass.strip():
            raise ValueError('taskclass must be a non-empty string')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('task name must be a non-empty string')
        if '@' in taskclass or '@' in name:
            raise ValueError('taskclass and task name must not contain "@"')
        return f'{taskclass}@{name}'

    @classmethod
    def registered(cls, taskclass: str) -> type[Any] | None:
        """Return the registered Task class with this class name, if any."""
        from oas.config.models.tasks import TaskBase

        try:
            task_class = config_model_registry.get_task_class(taskclass)
        except KeyError:
            return None
        return task_class if issubclass(task_class, TaskBase) else None

    @classmethod
    def resolve(cls, task: str) -> type[Any] | None:
        """Resolve ``TaskClass@name`` to a registered Task class.

        Only the name is used, so this never touches the database.  An
        operation that reads one Group row therefore performs exactly one
        table read.
        """
        taskclass, _name = cls.split(task)
        return cls.registered(taskclass or task)


class GroupAddress:
    """Address of one Group inside a Task.

    A static Group field is addressed by its field name alone.  One instance
    of a dynamically managed Group list is addressed as ``field@index``, where
    ``index`` is the zero-based position in the list.  The whole address is a
    single string, so it fits the ``group`` column and the ``group`` field of
    :class:`~oas.config.entry.model.ConfigSetEvent` unchanged.
    """

    @classmethod
    def make(cls, field: str, index: int | None = None) -> str:
        """Build the address of one Group or Group instance.

        Args:
            field: Task field name that declares the Group.
            index: Instance position; ``None`` addresses a static Group.

        Returns:
            ``field`` for a static Group, ``field@index`` for one instance.

        Raises:
            ValueError: If the field name or the index is not usable.
        """
        if not isinstance(field, str) or not field.strip():
            raise ValueError('group field must be a non-empty string')
        if '@' in field:
            raise ValueError('group field must not contain "@"')
        if index is None:
            return field
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError('group index must be a non-negative integer')
        return f'{field}@{index}'

    @classmethod
    def split(cls, address: str) -> tuple[str, int | None]:
        """Split an address into its field name and instance index.

        Parsing is deliberately lenient: a value that is not
        ``field@<digits>`` is returned as a whole field name.  A row written
        by an older or a broken writer must not make loading raise; the field
        name then fails the model lookup on its own.

        Args:
            address: Stored group address.

        Returns:
            ``(field, index)``; ``index`` is ``None`` for a static Group.
        """
        field, separator, suffix = address.partition('@')
        if separator and field and suffix.isdigit():
            return field, int(suffix)
        return address, None


config_model_registry = ConfigModelRegistry()
