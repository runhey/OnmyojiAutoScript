"""
Config access
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from functools import wraps
from types import MethodType, TracebackType
from typing import Any, Self, get_args, get_origin

from pydantic import ValidationError

from oas.config.entry.codec import Codec
from oas.config.entry.model import ConfigSetEvent
from oas.config.models.groups import GroupBase
from oas.config.models.registry import config_model_registry
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_mod import ConfigMod
from oas.logger import logger

_MISSING = object()


class _BatchSetContext:
    """
    Batch set context
    """

    def __init__(self, config: ConfigAccess):
        self.config = config

    def __enter__(self) -> Self:
        self.config._local.batch_depth = (
            getattr(self.config._local, 'batch_depth', 0) + 1
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        depth = max(getattr(self.config._local, 'batch_depth', 0) - 1, 0)
        self.config._local.batch_depth = depth
        # Alasio saves when leaving the outermost context, including when the
        # wrapped code raised. The database operation itself remains atomic.
        if depth == 0 and self.config.auto_save:
            self.config.save()


class _TemporaryContext:
    """
    Temporary override context
    """

    def __init__(self, config: ConfigAccess, kwargs: Mapping[str, Any]):
        self.config = config
        self.kwargs = kwargs
        self.previous_config: dict[str, dict[str, Any]] = {}
        self.previous_const: dict[str, Any] = {}

    def __enter__(self) -> Self:
        self.previous_config, self.previous_const = self.config.override(**self.kwargs)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        with self.config._lock:
            for group, values in self.previous_config.items():
                for arg, value in values.items():
                    self.config._apply_override_config(group, arg, value)
            for key, value in self.previous_const.items():
                self.config._apply_override_const(key, value)


class GroupProxy:
    """
    A proxy object upon group model to capture property set event
    So you can set property directly and trigger auto save:
        config.Group.Arg = value
    """

    __slots__ = ('_config', '_group', '_obj', '_task')

    def __init__(
        self,
        obj: GroupBase,
        config: ConfigAccess,
        task: str,
        group: str,
    ) -> None:
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_config', config)
        object.__setattr__(self, '_task', task)
        object.__setattr__(self, '_group', group)

    def __getattr__(self, name: str) -> Any:
        """
        Proxy attribute access.

        Methods marked with ``_alasio_batch_set`` are called inside a batch
        context, matching Alasio's GroupProxy behavior.
        """
        attr = getattr(self._obj, name)
        if not isinstance(attr, MethodType):
            return attr
        function = attr.__func__
        if not (
            getattr(function, '_alasio_batch_set', False)
            or getattr(function, '_oas_batch_set', False)
        ):
            return attr

        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with self._config.batch_set():
                return function(self, *args, **kwargs)

        return wrapped

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Args:
            name (str): Group argument name
            value: New argument value
        """
        if name.startswith('_'):
            raise AttributeError(f'cannot assign private proxy attribute: {name}')
        self._config._set_group_arg(self._task, self._group, name, value)

    def __repr__(self) -> str:
        return repr(self._obj)

    def __str__(self) -> str:
        return str(self._obj)


class ConfigAccess(ConfigMod):
    """
    Config access and Group runtime state.
    """

    def __init__(self, config_name: str, task: str = '') -> None:
        super().__init__(config_name, task)
        self.init_task()

    # ------------------------------------------------------------------
    # Cache and model loading
    # ------------------------------------------------------------------

    def _read_data_version(self) -> tuple[int, int]:
        """
        Read SQLite data version.

        Returns:
            tuple[int, int]: Connection identity and SQLite data version
        """
        return self._config_data_version(self.config_name)

    def config_cache(self) -> None:
        """
        Cache configuration rows.
        """
        with self._lock:
            if self.is_template_config or self._config_cached:
                return
            rows, data_version = self._config_snapshot(self.config_name)
            self._data_version = data_version
            self._dict_row = {(row.task, row.group): row.value for row in rows}
            self._dict_group.clear()
            self._config_cached = True

    def config_changed(self) -> bool:
        """
        Check whether the configuration database changed after caching.

        Returns:
            bool: Whether the current SQLite data version differs from the
                cached version
        """
        with self._lock:
            if not self._config_cached or self.is_template_config:
                return False
            return self._read_data_version() != self._data_version

    def refresh(self) -> bool:
        """
        Reload the configuration cache when the database changed.

        Returns:
            bool: Whether the cache was reloaded
        """
        with self._lock:
            if not self.config_changed():
                return False
            self.release()
            self.init_task()
            return True

    def release(self) -> None:
        """
        Release configuration cache.
        """
        with self._lock:
            if self._modified:
                logger.error(
                    'Trying to release config cache but having unsaved config '
                    'modifications, this could lead to data inconsistency'
                )
            depth = getattr(self._local, 'batch_depth', 0)
            if depth > 0:
                logger.error(
                    'Trying to release config cache but batch_depth > 0, '
                    'this could lead to data inconsistency'
                )
            self._dict_row.clear()
            self._dict_group.clear()
            self._config_cached = False
            self._modified.clear()
            self._local.batch_depth = 0

    @staticmethod
    def _task_class(task: str) -> type[TaskBase] | None:
        taskclass, separator, _name = task.partition('@')
        name = taskclass if separator else task
        try:
            candidate = config_model_registry.get_task_class(name)
        except KeyError:
            return None
        return candidate if issubclass(candidate, TaskBase) else None

    @staticmethod
    def _group_class(task_class: type[TaskBase], group: str) -> type[GroupBase] | None:
        field = task_class.model_fields.get(group)
        if field is None:
            return None
        # Dynamic Group containers are intentionally outside this access layer
        # until their flattened persistence format is implemented.
        annotation = field.annotation
        origin = get_origin(annotation)
        if origin in (list, tuple, set, frozenset):
            return None
        if any(
            get_origin(argument) in (list, tuple, set, frozenset)
            for argument in get_args(annotation)
        ):
            return None
        group_class = config_model_registry.group_for_field(task_class, group)
        if group_class is None or not issubclass(group_class, GroupBase):
            return None
        return group_class

    def _load_group(
        self,
        task: str,
        group: str,
        group_class: type[GroupBase] | None = None,
    ) -> GroupBase | None:
        """
        Load one static Group from cache or database.

        Args:
            task (str): Task instance name
            group (str): Group field name
            group_class (type[GroupBase] | None): Optional Group class

        Returns:
            GroupBase | None: Validated Group, or ``None`` on failure
        """
        self.config_cache()
        key = (task, group)
        cached = self._dict_group.get(key)
        if cached is not None:
            return cached
        task_class = self._task_class(task)
        if task_class is None:
            return None
        group_class = group_class or self._group_class(task_class, group)
        if group_class is None:
            return None
        payload = self._dict_row.get(key)
        try:
            obj = (
                group_class()
                if payload is None
                else group_class.from_dict(Codec.decode(payload))
            )
        except TypeError, ValueError, ValidationError:
            return None
        self._dict_group[key] = obj
        return obj

    def _set_group_arg(
        self,
        task: str,
        group: str,
        arg: str,
        value: Any,
    ) -> Any:
        """
        Set one Group argument.

        Args:
            task (str): Task instance name
            group (str): Group field name
            arg (str): Argument name
            value: New argument value

        Returns:
            Any: Validated argument value
        """
        obj = self._load_group(task, group)
        if obj is None:
            raise AttributeError(f'no such group: {task}.{group}')
        if arg not in type(obj).model_fields:
            raise AttributeError(f'no such field: {task}.{group}.{arg}')

        data = obj.model_dump(mode='python')
        data[arg] = value
        validated = type(obj).model_validate(data)
        new_value = getattr(validated, arg)
        if getattr(obj, arg) == new_value:
            return new_value
        self._dict_group[(task, group)] = validated
        self.register_modify(task, group, arg, new_value)
        return new_value

    def init_task(self) -> None:
        """
        Initialize Groups declared by the selected Task instance.
        """
        if not self.task or self.is_template_config:
            return
        with self._lock:
            self.config_cache()
            task_class = self._task_class(self.task)
            if task_class is None:
                return
            for group in task_class.model_fields:
                group_class = self._group_class(task_class, group)
                if group_class is not None:
                    self._load_group(self.task, group, group_class)

    def __getattr__(self, name: str) -> Any:
        """
        A fallback to access bound Groups.
        """
        if name.startswith('_') or not self.task:
            raise AttributeError(name)
        task_class = self._task_class(self.task)
        if task_class is None or name not in task_class.model_fields:
            raise AttributeError(name)
        group = self._load_group(self.task, name)
        if group is None:
            raise AttributeError(f'no such static group: {self.task}.{name}')
        return GroupProxy(group, self, self.task, name)

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------

    @property
    def bound(self) -> dict[tuple[str, str], None]:
        """Return ``(group, arg)`` pairs loaded for the selected Task."""
        with self._lock:
            return {
                (group, arg): None
                for (task, group), obj in self._dict_group.items()
                if task == self.task
                for arg in type(obj).model_fields
            }

    def bound_get(self, group: str, arg: str, default: Any = None) -> Any:
        """
        Get config from a bound Group.

        Args:
            group (str): Group name
            arg (str): Argument name
            default: Value returned when the Group or argument is missing

        Returns:
            Any: Current argument value or ``default``
        """
        obj = self._load_group(self.task, group)
        return default if obj is None else getattr(obj, arg, default)

    def cross_get(self, task: str, group: str, arg: str, default: Any = None) -> Any:
        """
        Get config from another Task.

        Args:
            task (str): Task instance name
            group (str): Group name
            arg (str): Argument name
            default: Value returned when the value is missing

        Returns:
            Any: Current argument value or ``default``
        """
        obj = self._load_group(task, group)
        return default if obj is None else getattr(obj, arg, default)

    def cross_set(self, task: str, group: str, arg: str, value: Any) -> None:
        """
        Set config to another Task.

        Invalid values and missing fields are ignored, matching the existing
        cross-task API behavior.
        """
        obj = self._load_group(task, group)
        if obj is None or arg not in type(obj).model_fields:
            return
        try:
            current = getattr(obj, arg)
            validated = type(obj).validate_patch({arg: value})
            new_value = getattr(validated, arg)
            if current == new_value:
                return
            setattr(obj, arg, new_value)
        except TypeError, ValueError, ValidationError:
            return
        self.register_modify(task, group, arg, new_value)

    # ------------------------------------------------------------------
    # Persistence and overrides
    # ------------------------------------------------------------------

    def register_modify(self, task: str, group: str, arg: str, value: Any) -> None:
        """
        Register config modification.

        Args:
            task (str): Task instance name
            group (str): Group name
            arg (str): Argument name
            value: New argument value
        """
        event = ConfigSetEvent(task=task, group=group, arg=arg, value=value)
        with self._lock:
            self._modified[(task, group, arg)] = event
            if self.auto_save and getattr(self._local, 'batch_depth', 0) == 0:
                self.save()

    def save(self) -> bool:
        """
        Save modified configs.

        Returns:
            bool: Whether there were pending changes and the save succeeded
        """
        with self._lock:
            if not self._modified:
                return False
            events = list(self._modified.values())
            self._modified.clear()
        try:
            if len(events) == 1:
                success, _responses = self.config_set(self.config_name, events[0])
            else:
                success, _responses = self.config_batch_set(self.config_name, events)
        except Exception:
            with self._lock:
                for event in events:
                    self._modified[(event.task, event.group, event.arg)] = event
            raise
        for response in _responses:
            if response.error:
                logger.info(
                    f'Failed to save config "{self.config_name}", '
                    f'key={response.task}.{response.group}.{response.arg}, '
                    f'error={response.error}'
                )
        if not success:
            with self._lock:
                for event in events:
                    self._modified[(event.task, event.group, event.arg)] = event
        return success

    def batch_set(self) -> _BatchSetContext:
        """
        Suppress auto-save for batch modifications.

        Returns:
            _BatchSetContext: Batch context
        """
        return _BatchSetContext(self)

    def _apply_override_config(self, group: str, arg: str, value: Any) -> Any:
        obj = self._load_group(self.task, group)
        if obj is None or arg not in type(obj).model_fields:
            return None
        previous = getattr(obj, arg)
        try:
            validated = type(obj).validate_patch({arg: value})
            setattr(obj, arg, getattr(validated, arg))
        except TypeError, ValueError, ValidationError:
            return _MISSING
        return previous

    def _apply_override_const(self, key: str, value: Any) -> Any:
        previous = getattr(self, key, _MISSING)
        setattr(self, key, value)
        return previous

    def override(
        self, **kwargs: Any
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """
        Permanently override config values in memory.

        Group arguments use ``Group_Arg=value``. Uppercase names are treated
        as constant overrides. Values are not written to the database.

        Returns:
            tuple[dict[str, dict[str, Any]], dict[str, Any]]: Previous values
        """
        previous_config: dict[str, dict[str, Any]] = defaultdict(dict)
        previous_const: dict[str, Any] = {}
        with self._lock:
            for key, value in kwargs.items():
                if key.isupper():
                    previous = self._apply_override_const(key, value)
                    previous_const[key] = previous
                    self._override_const[key] = value
                    continue
                group, separator, arg = key.partition('_')
                if not separator:
                    continue
                previous = self._apply_override_config(group, arg, value)
                if previous is _MISSING:
                    continue
                previous_config[group][arg] = previous
                self._override_config[group][arg] = value
                self._override_prev_config[group].setdefault(arg, previous)
        return dict(previous_config), previous_const

    def override_clear(self) -> None:
        """
        Clear all memory overrides and restore original values.
        """
        with self._lock:
            for group, values in self._override_prev_config.items():
                for arg, value in values.items():
                    self._apply_override_config(group, arg, value)
            for key in self._override_const:
                if key in self.__dict__:
                    del self.__dict__[key]
            self._override_config.clear()
            self._override_const.clear()
            self._override_prev_config.clear()

    def temporary(self, **kwargs: Any) -> _TemporaryContext:
        """
        Temporarily override config values in memory.

        Returns:
            _TemporaryContext: Context that restores values on exit
        """
        return _TemporaryContext(self, kwargs)
