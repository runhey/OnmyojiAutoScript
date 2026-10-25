"""Decorators and implementations for configuration operations.

``modconfig`` has two roles:

- it is the decoration namespace used by ``ConfigMod``; every decorated
  method receives a ``result`` argument computed by the decorator and only
  returns it;
- it owns the implementations, so the runtime state class stays free of
  business logic.

The first parameter of every public operation is ``config_name``.  A Task
instance is identified by ``TaskClass@name``; the class part is resolved
through ``config_model_registry`` and the whole string is what the ``task``
column stores.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar, get_args, get_origin

import msgspec
from pydantic import ValidationError

from oas.config.entry.codec import Codec
from oas.config.entry.error import ConfigError
from oas.config.entry.model import ConfigEvents, ConfigSetEvent, ModelConfigRef
from oas.config.entry.store import TaskStore
from oas.config.models.groups import GroupBase
from oas.config.models.registry import (
    GroupAddress,
    TaskNameResolver,
    config_model_registry,
    is_dynamic_annotation,
)
from oas.config.models.tasks import TaskBase
from oas.config.table.config import ConfigTable
from oas.logger import logger
from oas.mod.adapter import ModAdapter

F = TypeVar('F', bound=Callable[..., Any])

# Stored value of a reset Group.  Reading it yields the model defaults, and a
# later default change keeps applying (Alasio semantics).
_EMPTY_GROUP_PAYLOAD: bytes = msgspec.msgpack.encode({})


class modconfig(ModAdapter):
    """Configuration decorators and their ``config_*`` / ``cfg_*`` implementations.

    The decorated class must define ``__entry_info__``; its instances must
    define ``config_name``.  The first decorated call creates one shared
    :class:`~oas.mod.adapter.ModAdapter` and mounts it on the instance as
    ``__mod_adapter__``.  Each later call runs the matching implementation,
    inserts the computed value as ``result`` after ``self``, and calls the
    decorated method.  The method must return ``result`` unchanged.

    Every factory returns a decorator for an instance method shaped like::

        def method(self, result, config_name, ...):
            return result

    ``result`` is hidden from ``inspect.signature``.  The arguments documented
    on each factory are the arguments of the decorated method, not of the
    factory itself.

    Result families:

    * ``config_*`` mirror Alasio.  They return tuples/lists of
      :class:`ConfigSetEvent` and carry per-argument failures in
      ``event.error`` instead of raising.
    * ``cfg_*`` return ``(success, events)``.  ``success`` selects the branch,
      ``events`` carries the changed values, the failure reason in
      ``events[0].error``, and the getter result in ``events[0].value``.

    A :class:`ConfigSetEvent` always has ``task``, ``group``, ``arg``, and
    ``value`` fields.  ``error`` is ``None`` for an accepted value and a
    :class:`ConfigError` for a rejected one, which is how ``config_*`` reports
    per-argument failures without raising.

    ``group`` is the Task field name for a statically declared Group, and
    ``field@index`` for one instance of a dynamically managed Group list
    (``list[Group]``).  The index is the position in the list, so removing or
    inserting an instance shifts the addresses after it.

    Task instance names in the database are ``TaskClass@name``, for example
    ``FindJadeTask@default``.  ``cfg_task_add`` / ``cfg_task_copy`` take the
    class name and the instance name separately and build that string.
    """

    _entry_info_attribute = '__entry_info__'
    _adapter_attribute = '__mod_adapter__'

    @classmethod
    def _shared_adapter(cls, target: Any) -> ModAdapter:
        """获取或创建挂在目标实例上的共享 ModAdapter。"""
        adapter = getattr(target, cls._adapter_attribute, None)
        if adapter is not None:
            if not isinstance(adapter, ModAdapter):
                raise TypeError(f'{cls._adapter_attribute} must contain ModAdapter')
            if adapter.config_name != target.config_name:
                raise ValueError(
                    f'{cls._adapter_attribute} is bound to a different config_name'
                )
            return adapter

        entry_info = getattr(type(target), cls._entry_info_attribute, None)
        if entry_info is None:
            raise AttributeError(
                f'{type(target).__name__} must define {cls._entry_info_attribute}'
            )
        if not hasattr(target, 'config_name'):
            raise AttributeError(f'{type(target).__name__} must define config_name')

        adapter = ModAdapter(entry_info, target.config_name)
        setattr(target, cls._adapter_attribute, adapter)
        return adapter

    @classmethod
    def _decorate(
        cls,
        function: F,
        implementation: Callable[..., Any],
    ) -> F:
        """Wrap a method so the decorator computes ``result``.

        The wrapper calls ``implementation(target, *args, **kwargs)`` first,
        then calls the decorated method with ``result`` inserted after
        ``self``.  ``result`` is an internal injection and is removed from the
        public signature so ``inspect`` and IDEs only show the caller-facing
        parameters.
        """
        if not callable(function):
            raise TypeError('modconfig decorators must decorate a callable')

        @wraps(function)
        def wrapper(target: Any, *args: Any, **kwargs: Any) -> Any:
            cls._shared_adapter(target)
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
        # Keep the annotation view consistent with the public signature.
        wrapper.__annotations__ = {
            name: annotation
            for name, annotation in function.__annotations__.items()
            if name != 'result'
        }
        return wrapper  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Decorator factories
    # ------------------------------------------------------------------

    @classmethod
    def config_read(cls) -> Callable[[F], F]:
        """Decorate a method that reads configured Task and Group values.

        The decorated method signature is::

            def config_read(self, result, config_name, ref):
                return result

        Args:
            config_name: Configuration database name.
            ref: :class:`ModelConfigRef` selector.  ``ref.task`` selects every
                Group of the listed Task instances; ``ref.group`` adds only the
                listed ``(task, group)`` pairs.  A Task present in
                ``ref.task`` is read completely, so its pair entries are
                ignored.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``{task: {group: {arg: value}}}`` and must return it
            unchanged.  Missing or unregistered Tasks are skipped.

        Notes:
            Values come from the current Group rows plus model defaults for
            rows that do not exist yet.  Ordinary lookup failures do not raise;
            they simply produce an empty or partial mapping.

        Example:
            .. code-block:: python

                data = config.config_read(
                    "default",
                    ModelConfigRef(
                        task=["FindJadeTask@default"],
                        group=[("OrochiTask@default", "soul")],
                    ),
                )
        """
        return lambda function: cls._decorate(function, cls._config_read)

    @classmethod
    def config_snapshot(cls) -> Callable[[F], F]:
        """Decorate an access method that snapshots rows and data version.

        The decorated method signature is::

            def _config_snapshot(self, result, config_name):
                return result

        Args:
            config_name: Configuration database name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``(rows, (connection_id, data_version))`` and must
            return it unchanged.  ``rows`` is the list of ``ConfigRow`` rows;
            the version pair is read in the same cursor scope.

        Notes:
            Used by the runtime cache to detect external configuration changes.
            Database errors propagate to the caller.

        Example:
            .. code-block:: python

                rows, version = access._config_snapshot("default")
        """
        return lambda function: cls._decorate(function, cls._config_snapshot)

    @classmethod
    def config_data_version(cls) -> Callable[[F], F]:
        """Decorate an access method that reads only the data version.

        The decorated method signature is::

            def _config_data_version(self, result, config_name):
                return result

        Args:
            config_name: Configuration database name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``(connection_id, data_version)`` and must return it
            unchanged.

        Notes:
            This is the cheap change-detection path used before a full
            :meth:`config_snapshot`.  Database errors propagate.

        Example:
            .. code-block:: python

                version = access._config_data_version("default")
        """
        return lambda function: cls._decorate(function, cls._config_data_version)

    @classmethod
    def config_batch_set(cls) -> Callable[[F], F]:
        """Decorate a method that validates and writes many arguments at once.

        The decorated method signature is::

            def config_batch_set(
                self, result, config_name, events, post_edit=False,
            ):
                return result

        Args:
            config_name: Configuration database name.
            events: :class:`ConfigSetEvent` objects to apply.  Each event
                carries ``task``, ``group``, ``arg``, and the requested
                ``value``.
            post_edit: Run ``Group.post_edit(before, requested)`` after
                validation.  The hook may change other arguments; those changes
                are appended to the returned events.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``(success, events)`` and must return it unchanged.
            On success, ``events`` contains the validated values.  On failure,
            ``success`` is ``False`` and ``events`` contains restore events for
            every argument that was optimistically accepted.

        Notes:
            Validation failures, unknown Tasks/Groups/fields, and ``post_edit``
            errors are reported through ``event.error``; they do not raise.
            No row is written unless every event validates.  Empty ``events``
            returns ``(True, [])``.

        Example:
            .. code-block:: python

                ok, events = config.config_batch_set(
                    "default",
                    [
                        ConfigSetEvent(
                            task="FindJadeTask@default",
                            group="soul",
                            arg="enabled",
                            value=True,
                        )
                    ],
                    post_edit=True,
                )
        """
        return lambda function: cls._decorate(function, cls._config_batch_set)

    @classmethod
    def config_set(cls) -> Callable[[F], F]:
        """Decorate a single-argument variant of :meth:`config_batch_set`.

        The decorated method signature is::

            def config_set(
                self, result, config_name, event, post_edit=False,
            ):
                return result

        Args:
            config_name: Configuration database name.
            event: One :class:`ConfigSetEvent` to apply.
            post_edit: See :meth:`config_batch_set`.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``(success, events)`` and must return it unchanged.
            ``events`` holds the accepted value or the single restore event.

        Notes:
            Semantics are identical to :meth:`config_batch_set` with one event.

        Example:
            .. code-block:: python

                ok, events = config.config_set("default", event)
        """
        return lambda function: cls._decorate(function, cls._config_set)

    @classmethod
    def config_batch_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets many arguments to model defaults.

        The decorated method signature is::

            def config_batch_reset(self, result, config_name, events):
                return result

        Args:
            config_name: Configuration database name.
            events: :class:`ConfigSetEvent` objects whose ``arg`` fields name
                the arguments to reset.  ``event.value`` is ignored.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as a ``list[ConfigSetEvent]`` and must return it
            unchanged.  Each event carries the new default value; arguments
            that could not be reset are omitted.

        Notes:
            Missing Tasks, Groups, or fields are logged and skipped instead of
            raising.  If a reset Group fails model validation, the whole batch
            returns an empty list and writes nothing.  Empty ``events`` returns
            ``[]``.

        Example:
            .. code-block:: python

                events = config.config_batch_reset("default", [event])
        """
        return lambda function: cls._decorate(function, cls._config_batch_reset)

    @classmethod
    def config_reset(cls) -> Callable[[F], F]:
        """Decorate a single-argument variant of :meth:`config_batch_reset`.

        The decorated method signature is::

            def config_reset(self, result, config_name, event):
                return result

        Args:
            config_name: Configuration database name.
            event: One :class:`ConfigSetEvent` naming the argument to reset.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as the reset event or ``None`` when the argument could
            not be reset, and must return it unchanged.

        Example:
            .. code-block:: python

                event = config.config_reset("default", event)
        """
        return lambda function: cls._decorate(function, cls._config_reset)

    @classmethod
    def config_group_batch_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets whole Groups to model defaults.

        The decorated method signature is::

            def config_group_batch_reset(self, result, config_name, events):
                return result

        Args:
            config_name: Configuration database name.
            events: :class:`ConfigSetEvent` objects identifying Groups through
                ``task`` and ``group``.  ``event.arg`` is ignored.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as a ``list[ConfigSetEvent]`` and must return it
            unchanged.  It contains one event per default argument of every
            reset Group.

        Notes:
            Duplicate ``(task, group)`` pairs are reset once.  Missing Tasks and
            Groups are logged and skipped.  The row is stored with an empty
            payload so later changes to model defaults still apply.  Empty
            ``events`` returns ``[]``.

        Example:
            .. code-block:: python

                events = config.config_group_batch_reset("default", [event])
        """
        return lambda function: cls._decorate(function, cls._config_group_batch_reset)

    @classmethod
    def config_group_reset(cls) -> Callable[[F], F]:
        """Decorate a single-Group variant of :meth:`config_group_batch_reset`.

        The decorated method signature is::

            def config_group_reset(self, result, config_name, event):
                return result

        Args:
            config_name: Configuration database name.
            event: One :class:`ConfigSetEvent` identifying the Group through
                ``task`` and ``group``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as a ``list[ConfigSetEvent]`` and must return it
            unchanged.

        Example:
            .. code-block:: python

                events = config.config_group_reset("default", event)
        """
        return lambda function: cls._decorate(function, cls._config_group_reset)

    @classmethod
    def cfg_task_add(cls) -> Callable[[F], F]:
        """Decorate a method that creates a Task instance from its defaults.

        The decorated method signature is::

            def cfg_task_add(
                self, result, config_name, taskclass, name="default",
            ):
                return result

        Args:
            config_name: Configuration database name.
            taskclass: Registered Task class name, for example
                ``"FindJadeTask"``.
            name: Instance name, for example ``"default"``.  The stored Task
                name is ``f"{taskclass}@{name}"``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per default Group argument.

        Notes:
            Failures are returned as ``(False, events)`` with the reason in
            ``events[0].error``; they do not raise.  Failure cases include an
            unregistered Task class, an empty name, ``"@"`` in either part, a
            duplicate Task, and a failing default constructor.

        Example:
            .. code-block:: python

                result = config.cfg_task_add(
                    "default", "FindJadeTask", "second",
                )
                assert result.success
        """
        return lambda function: cls._decorate(function, cls._cfg_task_add)

    @classmethod
    def cfg_task_del(cls) -> Callable[[F], F]:
        """Decorate a method that deletes one Task instance.

        The decorated method signature is::

            def cfg_task_del(self, result, config_name, task):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name, for example
                ``"FindJadeTask@default"``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success has no events.

        Notes:
            A missing Task returns ``success=False`` with a
            :class:`ConfigError`; it does not raise.

        Example:
            .. code-block:: python

                result = config.cfg_task_del(
                    "default", "FindJadeTask@second",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_task_del)

    @classmethod
    def cfg_task_copy(cls) -> Callable[[F], F]:
        """Decorate a method that copies a Task instance and its values.

        The decorated method signature is::

            def cfg_task_copy(
                self, result, config_name, task, new_name="default",
            ):
                return result

        Args:
            config_name: Configuration database name.
            task: Source Task instance name, for example
                ``"FindJadeTask@default"``.
            new_name: Instance name for the copy.  The stored name is
                ``f"{TaskClass}@{new_name}"``.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per copied Group argument.

        Notes:
            Failures are returned through ``events[0].error`` and do not raise.
            They include a missing source Task, an invalid target name, a
            target equal to the source, and an existing target Task.

        Example:
            .. code-block:: python

                result = config.cfg_task_copy(
                    "default", "FindJadeTask@default", "backup",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_task_copy)

    @classmethod
    def cfg_task_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets a Task instance to model defaults.

        The decorated method signature is::

            def cfg_task_reset(self, result, config_name, task):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per default Group argument.

        Notes:
            The Task class must be registered and the instance must already
            exist; otherwise ``success`` is ``False`` and ``error`` explains
            why.  No exception is raised for these cases.

        Example:
            .. code-block:: python

                result = config.cfg_task_reset(
                    "default", "FindJadeTask@default",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_task_reset)

    @classmethod
    def cfg_group_add(cls) -> Callable[[F], F]:
        """Decorate a method that creates a Group from its defaults.

        The decorated method signature is::

            def cfg_group_add(
                self, result, config_name, task, group, groupclass, index=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group field name declared by the Task class.
            groupclass: Expected Group class name.  It must match the class
                registered for ``group``.
            index: Insert position for a new instance of a dynamically managed
                Group list.  ``None`` appends, which is also the only option
                for a static Group.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per default Group argument for a static
            Group, and one event per argument of every instance of the field
            for a dynamic Group list, because the stored addresses shift.

        Notes:
            A dynamic Group list takes the field name here and creates exactly
            one instance; an index in ``group`` is only accepted when ``index``
            is left unset, and a conflicting pair is rejected.  Missing
            Task/Group, a class-name mismatch, an out-of-range index, or an
            existing static Group returns ``success=False`` instead of raising.

        Example:
            .. code-block:: python

                result = config.cfg_group_add(
                    "default", "FindJadeTask@default", "soul", "SoulGroup",
                )
                result = config.cfg_group_add(
                    "default", "FindJadeTask@default", "targets", "TargetGroup",
                    index=0,
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_group_add)

    @classmethod
    def cfg_group_del(cls) -> Callable[[F], F]:
        """Decorate a method that deletes one Group row.

        The decorated method signature is::

            def cfg_group_del(self, result, config_name, task, group):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group address: the field name for a static Group, or
                ``field@index`` for one instance of a dynamic Group list.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            A static Group succeeds with no events.  Removing an instance
            reports every remaining instance of that field, because the
            addresses after the removed one shift down.

        Notes:
            Missing Task/Group, a static Group given an index, a dynamic field
            given without an index, and an index that names no instance return
            ``success=False`` instead of raising.

        Example:
            .. code-block:: python

                result = config.cfg_group_del(
                    "default", "FindJadeTask@default", "soul",
                )
                result = config.cfg_group_del(
                    "default", "FindJadeTask@default", "targets@1",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_group_del)

    @classmethod
    def cfg_group_copy(cls) -> Callable[[F], F]:
        """Decorate a method that copies a Group's values into another Group.

        The decorated method signature is::

            def cfg_group_copy(
                self, result, config_name, task, group,
                new_group, new_task=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            task: Source Task instance name.
            group: Source Group address: the field name, or ``field@index`` for
                one instance of a dynamic Group list.
            new_group: Target Group address.  It must be declared by the target
                Task class.  A dynamic list without an index appends the copy,
                one with an index inserts it there.
            new_task: Target Task instance name.  ``None`` keeps the copy in
                the source Task.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per copied Group argument, or every
            instance of the field when the target is a dynamic Group list.

        Notes:
            The source and target must differ.  A static Group and a dynamic
            Group list cannot be mixed.  Failures include a missing source
            Group, a missing target Task, an unknown target Group, validation
            failure under the target class, and an existing static target
            Group.  They are returned in ``events[0].error`` and do not raise.

        Example:
            .. code-block:: python

                result = config.cfg_group_copy(
                    "default", "FindJadeTask@default", "soul",
                    "backup", "FindJadeTask@backup",
                )
                result = config.cfg_group_copy(
                    "default", "FindJadeTask@default", "targets@0",
                    "targets",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_group_copy)

    @classmethod
    def cfg_group_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets a Group to model defaults.

        The decorated method signature is::

            def cfg_group_reset(self, result, config_name, task, group):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group address: the field name for a static Group, or
                ``field@index`` for one instance of a dynamic Group list.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Success carries one event per default Group argument.

        Notes:
            The Group must be declared by the Task class.  A missing static row
            is created with default values, while an instance of a dynamic
            Group list must already exist, so a reset can never add one.
            Failures are returned through ``events[0].error`` and do not raise.

        Example:
            .. code-block:: python

                result = config.cfg_group_reset(
                    "default", "FindJadeTask@default", "soul",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_group_reset)

    @classmethod
    def cfg_arg_get(cls) -> Callable[[F], F]:
        """Decorate a method that reads one Group argument.

        The decorated method signature is::

            def cfg_arg_get(
                self, result, config_name, task, group, arg, default=None,
            ):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group field name.
            arg: Argument name inside the Group.
            default: Value placed in ``result.value`` when the read fails.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            On success ``value`` is the current argument value and ``events`` is
            empty; on failure ``value`` is ``default`` and ``error`` describes
            the problem.

        Notes:
            Missing Task/Group/field and unreadable Group rows are reported
            through ``events[0].error`` instead of raising.

        Example:
            .. code-block:: python

                result = config.cfg_arg_get(
                    "default", "FindJadeTask@default", "soul", "enabled",
                    default=False,
                )
                enabled = result.value
        """
        return lambda function: cls._decorate(function, cls._cfg_arg_get)

    @classmethod
    def cfg_arg_set(cls) -> Callable[[F], F]:
        """Decorate a method that sets one Group argument.

        The decorated method signature is::

            def cfg_arg_set(
                self, result, config_name, task, group, arg, value,
                post_edit=False,
            ):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group field name.
            arg: Argument name inside the Group.
            value: Requested value; Pydantic validates and coerces it.
            post_edit: Run ``Group.post_edit(before, requested)`` after
                validation.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            On success ``value`` is the validated value and ``events`` contains
            the accepted change (plus any ``post_edit`` side effects); on
            failure ``events`` contains restore events and ``error`` explains
            the rejection.

        Notes:
            This is the single-event form of :meth:`cfg_arg_batch_set`.

        Example:
            .. code-block:: python

                result = config.cfg_arg_set(
                    "default", "FindJadeTask@default", "soul",
                    "enabled", True,
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_arg_set)

    @classmethod
    def cfg_arg_batch_set(cls) -> Callable[[F], F]:
        """Decorate a method that sets many Group arguments atomically.

        The decorated method signature is::

            def cfg_arg_batch_set(
                self, result, config_name, events, post_edit=False,
            ):
                return result

        Args:
            config_name: Configuration database name.
            events: :class:`ConfigSetEvent` objects to apply.
            post_edit: Run ``Group.post_edit(before, requested)`` for each
                touched Group after validation.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            On success ``events`` contains all accepted changes and ``value``
            is ``None``; on failure ``events`` contains restore events and
            ``error`` is the first :class:`ConfigError`.

        Notes:
            Validation is all-or-nothing: no row is written unless every event
            validates.  Empty ``events`` succeeds with no events.

        Example:
            .. code-block:: python

                result = config.cfg_arg_batch_set("default", [event_a, event_b])
        """
        return lambda function: cls._decorate(function, cls._cfg_arg_batch_set)

    @classmethod
    def cfg_arg_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets one Group argument.

        The decorated method signature is::

            def cfg_arg_reset(self, result, config_name, task, group, arg):
                return result

        Args:
            config_name: Configuration database name.
            task: Full Task instance name.
            group: Group field name.
            arg: Argument name inside the Group.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            On success ``value`` is the default value and ``events`` holds the
            reset event; on failure ``error`` explains why.

        Notes:
            Missing Task/Group/field returns ``success=False`` instead of
            raising.

        Example:
            .. code-block:: python

                result = config.cfg_arg_reset(
                    "default", "FindJadeTask@default", "soul", "enabled",
                )
        """
        return lambda function: cls._decorate(function, cls._cfg_arg_reset)

    @classmethod
    def cfg_arg_batch_reset(cls) -> Callable[[F], F]:
        """Decorate a method that resets many Group arguments.

        The decorated method signature is::

            def cfg_arg_batch_reset(self, result, config_name, events):
                return result

        Args:
            config_name: Configuration database name.
            events: :class:`ConfigSetEvent` objects naming the arguments to
                reset.  ``event.value`` is ignored.

        Returns:
            Callable[[F], F]: The decorator.  The decorated method receives
            ``result`` as ``tuple[bool, list[ConfigSetEvent]]`` and must return
            it unchanged.
            Empty input succeeds with no events; otherwise success carries the
            reset events and ``value`` is ``None``.

        Notes:
            Missing Tasks, Groups, or fields are logged and skipped.  If no
            argument can be reset, the result is ``success=False`` with an
            error.  Input errors are not raised.

        Example:
            .. code-block:: python

                result = config.cfg_arg_batch_reset("default", [event_a, event_b])
        """
        return lambda function: cls._decorate(function, cls._cfg_arg_batch_reset)

    # ------------------------------------------------------------------
    # config_* implementations (Alasio compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def _config_snapshot(
        target: Any,
        config_name: str,
    ) -> tuple[list[Any], tuple[int, int]]:
        """Read the config rows and SQLite version in one cursor scope."""
        table = ConfigTable(config_name)
        with table.cursor() as cursor:
            version = (id(cursor.connection), table.get_data_version(_cursor_=cursor))
            rows = table.select(_cursor_=cursor)
        return rows, version

    @staticmethod
    def _config_data_version(
        target: Any,
        config_name: str,
    ) -> tuple[int, int]:
        """Read the SQLite version through the configuration entry layer."""
        table = ConfigTable(config_name)
        with table.cursor() as cursor:
            return (id(cursor.connection), table.get_data_version(_cursor_=cursor))

    @staticmethod
    def _config_read(
        target: Any,
        config_name: str,
        ref: ModelConfigRef,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        selected: dict[str, set[str] | None] = {}
        for task in ref.task:
            selected[task] = None
        for task, group in ref.group:
            if task in selected and selected[task] is None:
                continue
            bucket = selected.get(task)
            if bucket is None:
                bucket = set()
                selected[task] = bucket
            bucket.add(group)

        out: dict[str, dict[str, dict[str, Any]]] = {}
        for task, groups in selected.items():
            loaded = _load_task(config_name, task)
            if loaded is None:
                continue
            _task_class, task_obj = loaded
            data = task_obj.to_dict()
            if groups is not None:
                data = {name: value for name, value in data.items() if name in groups}
            out[task] = data
        return out

    @staticmethod
    def _config_batch_set(
        target: Any,
        config_name: str,
        events: list[ConfigSetEvent],
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        if not events:
            return True, []

        table = ConfigTable(config_name)
        events = _GroupTarget.normalize_events(events)
        grouped = ConfigEvents.group_events(events)

        success: list[ConfigSetEvent] = []
        rollback: list[ConfigSetEvent] = []
        writes: list[tuple[str, str, type[TaskBase], GroupBase]] = []
        has_error = False

        for (task, group), group_events in grouped.items():
            task_class = TaskNameResolver.resolve(task)
            if task_class is None:
                has_error = True
                rollback.extend(
                    ConfigEvents.fail_events(group_events, f'No such task: "{task}"')
                )
                continue
            target, error = _GroupTarget.resolve(task, task_class, group)
            if target is None:
                has_error = True
                rollback.extend(ConfigEvents.fail_events(group_events, error))
                continue
            group_obj, error = _read_target_group(config_name, task, target)
            if group_obj is None:
                has_error = True
                rollback.extend(ConfigEvents.fail_events(group_events, error))
                continue

            new_values, group_success, error = _validate_group_args(
                task, target, group_obj, group_events
            )
            if error is not None:
                rollback.extend(group_success)
                rollback.append(error)
                has_error = True
                continue

            data = group_obj.to_dict()
            data.update(new_values)
            try:
                # Full state validation: unlike the per-argument patch check
                # above, the stored arguments are part of this payload.
                new_group = target.group_class.model_validate(data)
            except ValidationError as exc:
                rollback.extend(
                    ConfigEvents.rollback_group(
                        group_events,
                        task,
                        target.address,
                        group_obj,
                        ConfigError.from_pydantic(exc),
                    )
                )
                has_error = True
                continue

            if post_edit:
                error, extra = _run_post_edit(
                    task, target.address, group_obj, new_group, new_values
                )
                if error is not None:
                    rollback.extend(
                        ConfigEvents.rollback_group(
                            group_events, task, target.address, group_obj, error
                        )
                    )
                    has_error = True
                    continue
                group_success.extend(extra)

            success.extend(group_success)
            writes.append((task, target.address, task_class, new_group))

        if has_error:
            # Valid Groups are included too: nothing was written, so every
            # optimistic UI update has to be restored.
            rollback.extend(success)
            return False, rollback
        if not writes:
            return True, success

        with table.exclusive_transaction() as cursor:
            for task, group, task_class, group_obj in writes:
                _write_group(table, task, task_class, group, group_obj, cursor)
        logger.info(
            f'config_set "{config_name}": '
            + ', '.join(f'{e.task}.{e.group}.{e.arg}' for e in success)
        )
        return True, success

    @staticmethod
    def _config_set(
        target: Any,
        config_name: str,
        event: ConfigSetEvent,
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        return modconfig._config_batch_set(target, config_name, [event], post_edit)

    @staticmethod
    def _config_batch_reset(
        target: Any,
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> list[ConfigSetEvent]:
        if not events:
            return []

        table = ConfigTable(config_name)
        events = _GroupTarget.normalize_events(events)
        grouped = ConfigEvents.group_events(events)

        success: list[ConfigSetEvent] = []
        writes: list[tuple[str, str, type[TaskBase], GroupBase]] = []

        for (task, group), group_events in grouped.items():
            task_class = TaskNameResolver.resolve(task)
            if task_class is None:
                logger.warning(f'Cannot reset non-exist task "{task}"')
                continue
            target, error = _GroupTarget.resolve(task, task_class, group)
            if target is None:
                logger.warning(f'Cannot reset group: {error}')
                continue
            group_obj, error = _read_target_group(config_name, task, target)
            if group_obj is None:
                logger.warning(f'Cannot reset group: {error}')
                continue

            data = group_obj.to_dict()
            args: list[str] = []
            for event in group_events:
                if event.arg not in target.group_class.model_fields:
                    logger.warning(
                        f'Cannot reset non-exist field '
                        f'"{task}.{target.address}.{event.arg}"'
                    )
                    continue
                data.pop(event.arg, None)
                args.append(event.arg)

            try:
                new_group = target.group_class.model_validate(data)
            except ValidationError as exc:
                logger.warning(
                    f'Failed to convert after reset for '
                    f'"{task}.{target.address}": {exc}'
                )
                return []

            default = target.group_class()
            for arg in args:
                success.append(
                    ConfigEvents.event(task, target.address, arg, getattr(default, arg))
                )
            writes.append((task, target.address, task_class, new_group))

        if not writes:
            return success
        with table.exclusive_transaction() as cursor:
            for task, group, task_class, group_obj in writes:
                _write_group(table, task, task_class, group, group_obj, cursor)
        logger.info(
            f'config_reset "{config_name}": '
            + ', '.join(f'{e.task}.{e.group}.{e.arg}' for e in success)
        )
        return success

    @staticmethod
    def _config_reset(
        target: Any,
        config_name: str,
        event: ConfigSetEvent,
    ) -> ConfigSetEvent | None:
        events = modconfig._config_batch_reset(target, config_name, [event])
        return events[0] if events else None

    @staticmethod
    def _config_group_batch_reset(
        target: Any,
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> list[ConfigSetEvent]:
        if not events:
            return []

        table = ConfigTable(config_name)
        events = _GroupTarget.normalize_events(events)
        seen: set[tuple[str, str]] = set()
        success: list[ConfigSetEvent] = []
        writes: list[tuple[str, str, type[TaskBase], type[GroupBase]]] = []

        for event in events:
            task, group = event.task, event.group
            key = (task, group)
            if key in seen:
                continue
            seen.add(key)

            task_class = TaskNameResolver.resolve(task)
            if task_class is None:
                logger.warning(f'Cannot reset non-exist task "{task}"')
                continue
            target, error = _GroupTarget.resolve(task, task_class, group)
            if target is None:
                logger.warning(f'Cannot reset group: {error}')
                continue
            # A static Group is reset by writing its default row, while an
            # instance that does not exist must not be created: that would
            # leave a hole in the stored index sequence.
            if target.dynamic and table.get_group(task, target.address) is None:
                logger.warning(f'Cannot reset non-exist group instance "{group}"')
                continue

            default = target.group_class()
            for arg, value in default.to_dict().items():
                success.append(ConfigEvents.event(task, target.address, arg, value))
            writes.append((task, target.address, task_class, target.group_class))

        if not writes:
            return success
        with table.exclusive_transaction() as cursor:
            for task, group, task_class, group_class in writes:
                _reset_group(table, task, task_class, group, group_class, cursor)
        logger.info(
            f'config_group_reset "{config_name}": '
            + ', '.join(sorted({f'{e.task}.{e.group}' for e in success}))
        )
        return success

    @staticmethod
    def _config_group_reset(
        target: Any,
        config_name: str,
        event: ConfigSetEvent,
    ) -> list[ConfigSetEvent]:
        return modconfig._config_group_batch_reset(target, config_name, [event])

    # ------------------------------------------------------------------
    # cfg_* implementations (OAS native, unified (success, events))
    # ------------------------------------------------------------------

    @staticmethod
    def _cfg_task_add(
        target: Any,
        config_name: str,
        taskclass: str,
        name: str = 'default',
    ) -> tuple[bool, list[ConfigSetEvent]]:
        task_class = TaskNameResolver.registered(taskclass)
        if task_class is None:
            return _failure(f'Unregistered TaskClass: "{taskclass}"')
        try:
            task_name = TaskNameResolver.make(taskclass, name)
        except ValueError as exc:
            return _failure(str(exc))

        table = ConfigTable(config_name)
        if table.list_task_rows(task_name):
            return _failure(f'Task already exists: "{task_name}"')
        try:
            task_obj = task_class()
        except Exception as exc:  # noqa: BLE001
            return _failure(f'Cannot construct default Task "{taskclass}": {exc}')

        TaskStore.save(config_name, task_obj, task_name)
        return True, ConfigEvents.events_from_task(task_name, task_obj)

    @staticmethod
    def _cfg_task_del(
        target: Any,
        config_name: str,
        task: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        table = ConfigTable(config_name)
        if not table.list_task_rows(task):
            return _failure(f'No such task: "{task}"')
        table.delete_task(task)
        return True, []

    @staticmethod
    def _cfg_task_copy(
        target: Any,
        config_name: str,
        task: str,
        new_name: str = 'default',
    ) -> tuple[bool, list[ConfigSetEvent]]:
        loaded = _load_task(config_name, task)
        if loaded is None:
            return _failure(f'No such task: "{task}"')
        task_class, task_obj = loaded
        try:
            target_task = TaskNameResolver.make(task_class.__name__, new_name)
        except ValueError as exc:
            return _failure(str(exc))
        if target_task == task:
            return _failure(f'Target is the same as source: "{task}"')

        table = ConfigTable(config_name)
        if table.list_task_rows(target_task):
            return _failure(f'Task already exists: "{target_task}"')

        TaskStore.save(config_name, task_obj, target_task)
        return True, ConfigEvents.events_from_task(target_task, task_obj)

    @staticmethod
    def _cfg_task_reset(
        target: Any,
        config_name: str,
        task: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        task_class = TaskNameResolver.resolve(task)
        if task_class is None:
            return _failure(f'No such task: "{task}"')
        table = ConfigTable(config_name)
        if not table.list_task_rows(task):
            return _failure(f'No such task: "{task}"')

        default_obj = task_class()
        TaskStore.save(config_name, default_obj, task)
        return True, ConfigEvents.events_from_task(task, default_obj)

    @staticmethod
    def _cfg_group_add(
        target: Any,
        config_name: str,
        task: str,
        group: str,
        groupclass: str,
        index: int | None = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """Add one Group, or one instance of a dynamic Group list.

        ``group`` is the Task field name; a dynamically managed Group list also
        accepts an index in the address, but the ``index`` argument takes
        precedence and is what the caller normally uses to insert an instance.
        """
        task_class = TaskNameResolver.resolve(task)
        if task_class is None:
            return _failure(f'No such task: "{task}"')
        resolved, error = _GroupTarget.resolve(
            task, task_class, group, bare_dynamic=True
        )
        if resolved is None:
            return _failure(error)
        if groupclass != resolved.group_class.__name__:
            return _failure(
                f'GroupClass mismatch: expected "{resolved.group_class.__name__}", '
                f'got "{groupclass}"'
            )

        table = ConfigTable(config_name)
        if not resolved.dynamic:
            if table.get_group(task, resolved.field) is not None:
                return _failure(f'Group already exists: "{task}.{resolved.field}"')
            default_obj = resolved.group_class()
            _write_group(table, task, task_class, resolved.field, default_obj)
            return True, ConfigEvents.events_from_group(
                task, resolved.field, default_obj
            )

        if resolved.index is not None:
            if index is None:
                index = resolved.index
            elif index != resolved.index:
                return _failure(f'Conflicting index: "{group}" and index={index}')

        instances = _read_dynamic_field(config_name, task, resolved)
        if index is None:
            position = len(instances)
        elif 0 <= index <= len(instances):
            position = index
        else:
            return _failure(
                f'Group index out of range for "{task}.{resolved.field}": '
                f'{index} (0..{len(instances)})'
            )

        instances.insert(position, resolved.group_class())
        return True, _write_dynamic_field(
            config_name, task, task_class, resolved, instances
        )

    @staticmethod
    def _cfg_group_del(
        target: Any,
        config_name: str,
        task: str,
        group: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """Delete one Group, or one instance of a dynamic Group list.

        Removing an instance resequences the stored addresses, so the reply
        reports every remaining instance of that field instead of one row.
        """
        task_class = TaskNameResolver.resolve(task)
        if task_class is None:
            return _failure(f'No such task: "{task}"')
        resolved, error = _GroupTarget.resolve(task, task_class, group)
        if resolved is None:
            return _failure(error)

        table = ConfigTable(config_name)
        if not resolved.dynamic:
            if table.get_group(task, resolved.field) is None:
                return _failure(f'No such group: "{task}.{resolved.field}"')
            table.delete_group(task, resolved.field)
            return True, []

        instances = _read_dynamic_field(config_name, task, resolved)
        if resolved.index >= len(instances):
            return _failure(f'No such Group instance: "{task}.{resolved.address}"')
        del instances[resolved.index]
        return True, _write_dynamic_field(
            config_name, task, task_class, resolved, instances
        )

    @staticmethod
    def _cfg_group_copy(
        target: Any,
        config_name: str,
        task: str,
        group: str,
        new_group: str,
        new_task: str | None = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """Copy one Group, or one instance of a dynamic Group list.

        ``group`` and ``new_group`` are addresses; a dynamic destination
        without an index appends a new instance, and one with an index inserts
        there.  A static Group and a dynamic Group list cannot be mixed.
        """
        source_task_class = TaskNameResolver.resolve(task)
        if source_task_class is None:
            return _failure(f'No such task: "{task}"')
        source, error = _GroupTarget.resolve(task, source_task_class, group)
        if source is None:
            return _failure(error)
        source_obj, error = _read_target_group(config_name, task, source)
        if source_obj is None:
            return _failure(error)

        same_target = new_task is None or new_task == task
        target_task = task if new_task is None else new_task
        target_task_class = (
            source_task_class if same_target else TaskNameResolver.resolve(target_task)
        )
        if target_task_class is None:
            return _failure(f'No such task: "{target_task}"')

        destination, error = _GroupTarget.resolve(
            target_task, target_task_class, new_group, bare_dynamic=True
        )
        if destination is None:
            return _failure(error)
        if same_target and destination.address == source.address:
            return _failure('Target is the same as source')
        if destination.dynamic != source.dynamic:
            return _failure(
                'Cannot copy between a static Group and a dynamic Group list: '
                f'"{group}" -> "{new_group}"'
            )

        try:
            copied = destination.group_class.model_validate(source_obj.to_dict())
        except ValidationError as exc:
            return _failure(ConfigError.from_pydantic(exc))

        table = ConfigTable(config_name)
        if not destination.dynamic:
            if table.get_group(target_task, destination.field) is not None:
                return _failure(
                    f'Group already exists: "{target_task}.{destination.field}"'
                )
            _write_group(
                table,
                target_task,
                target_task_class,
                destination.field,
                copied,
            )
            return True, ConfigEvents.events_from_group(
                target_task, destination.field, copied
            )

        instances = _read_dynamic_field(config_name, target_task, destination)
        if destination.index is None:
            position = len(instances)
        elif 0 <= destination.index <= len(instances):
            position = destination.index
        else:
            return _failure(
                f'Group index out of range for "{target_task}.{destination.field}": '
                f'{destination.index} (0..{len(instances)})'
            )

        instances.insert(position, copied)
        return True, _write_dynamic_field(
            config_name, target_task, target_task_class, destination, instances
        )

    @staticmethod
    def _cfg_group_reset(
        target: Any,
        config_name: str,
        task: str,
        group: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """Reset one Group, or one instance of a dynamic Group list."""
        task_class = TaskNameResolver.resolve(task)
        if task_class is None:
            return _failure(f'No such task: "{task}"')
        resolved, error = _GroupTarget.resolve(task, task_class, group)
        if resolved is None:
            return _failure(error)

        table = ConfigTable(config_name)
        # An instance that does not exist must not be created by a reset: that
        # would leave a hole in the stored index sequence.
        if resolved.dynamic and table.get_group(task, resolved.address) is None:
            return _failure(f'No such Group instance: "{task}.{resolved.address}"')

        _reset_group(table, task, task_class, resolved.address, resolved.group_class)
        default = resolved.group_class()
        return True, ConfigEvents.events_from_group(task, resolved.address, default)

    @staticmethod
    def _cfg_arg_get(
        target: Any,
        config_name: str,
        task: str,
        group: str,
        arg: str,
        default: Any = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        task_class = TaskNameResolver.resolve(task)
        if task_class is None:
            return _failure(f'No such task: "{task}"', value=default)
        resolved, error = _GroupTarget.resolve(task, task_class, group)
        if resolved is None:
            return _failure(error, value=default)
        group_obj, error = _read_target_group(config_name, task, resolved)
        if group_obj is None:
            return _failure(error, value=default)
        if arg not in resolved.group_class.model_fields:
            return _failure(
                f'No such field: "{task}.{resolved.address}.{arg}"', value=default
            )
        return True, [
            ConfigEvents.event(task, resolved.address, arg, getattr(group_obj, arg))
        ]

    @staticmethod
    def _cfg_arg_set(
        target: Any,
        config_name: str,
        task: str,
        group: str,
        arg: str,
        value: Any,
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        ok, events = modconfig._config_batch_set(
            target,
            config_name,
            [ConfigEvents.event(task, group, arg, value)],
            post_edit,
        )
        return ok, events

    @staticmethod
    def _cfg_arg_batch_set(
        target: Any,
        config_name: str,
        events: list[ConfigSetEvent],
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        ok, results = modconfig._config_batch_set(
            target, config_name, events, post_edit
        )
        return ok, results

    @staticmethod
    def _cfg_arg_reset(
        target: Any,
        config_name: str,
        task: str,
        group: str,
        arg: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        events = modconfig._config_batch_reset(
            target,
            config_name,
            [ConfigEvents.event(task, group, arg, None)],
        )
        if not events:
            return _failure(f'No such field: "{task}.{group}.{arg}"')
        return True, events

    @staticmethod
    def _cfg_arg_batch_reset(
        target: Any,
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> tuple[bool, list[ConfigSetEvent]]:
        if not events:
            return True, []
        results = modconfig._config_batch_reset(target, config_name, events)
        if not results:
            return _failure('Failed to reset arguments')
        return True, results


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _GroupTarget:
    """One Group address resolved against a Task class.

    A static Group is addressed by its field name.  One instance of a
    dynamically managed Group list is addressed as ``field@index``, and a bare
    field name is rejected so the caller always names the instance it edits.
    """

    field: str
    group_class: type[GroupBase]
    dynamic: bool = False
    index: int | None = None

    @property
    def address(self) -> str:
        """Return the canonical ``field`` or ``field@index`` address."""
        return GroupAddress.make(self.field, self.index)

    @staticmethod
    def normalize_events(events: list[ConfigSetEvent]) -> list[ConfigSetEvent]:
        """Rewrite event addresses into their canonical form.

        Only ``field@index`` is stored, so a client that sends ``groups@01``
        must not read back an address that does not exist.
        """
        normalized: list[ConfigSetEvent] = []
        for event in events:
            field, index = GroupAddress.split(event.group)
            try:
                address = GroupAddress.make(field, index)
            except ValueError:
                address = event.group
            if address == event.group:
                normalized.append(event)
                continue
            normalized.append(
                ConfigSetEvent(
                    task=event.task,
                    group=address,
                    arg=event.arg,
                    value=event.value,
                    error=event.error,
                )
            )
        return normalized

    @classmethod
    def resolve(
        cls,
        task: str,
        task_class: type[TaskBase],
        address: str,
        *,
        bare_dynamic: bool = False,
    ) -> tuple[_GroupTarget | None, str | None]:
        """Resolve one Group address against a Task class.

        Args:
            task: Full Task instance name, used in the failure reasons.
            task_class: Task class that declares the Group field.
            address: Group address; ``field`` or ``field@index``.
            bare_dynamic: Accept a dynamic field without an index, for the
                operation that creates an instance.

        Returns:
            ``(target, None)`` on success, otherwise ``(None, reason)``.
        """
        field, index = GroupAddress.split(address)
        field_info = task_class.model_fields.get(field)
        if field_info is None:
            return None, f'No such group: "{task}.{field}"'
        dynamic = is_dynamic_annotation(field_info.annotation)
        if not dynamic and index is not None:
            return None, f'Static Group does not take an index: "{task}.{address}"'
        if dynamic and index is None and not bare_dynamic:
            return None, (
                f'Dynamic Group requires an index: "{task}.{address}", '
                f'use "{task}.{GroupAddress.make(field, 0)}"'
            )
        group_class = config_model_registry.group_for_field(task_class, field)
        if group_class is None or not issubclass(group_class, GroupBase):
            return None, f'No such group: "{task}.{field}"'
        return cls(
            field=field,
            group_class=group_class,
            dynamic=dynamic,
            index=index,
        ), None


def _read_group(
    config_name: str,
    task: str,
    group: str,
    group_class: type[GroupBase],
) -> GroupBase | None:
    """Read one Group row; a missing row yields the model defaults."""
    row = ConfigTable(config_name).get_group(task, group)
    if row is None:
        return group_class()
    try:
        return group_class.from_dict(Codec.decode(row.value))
    except (ValueError, ValidationError) as exc:
        logger.warning(f'Cannot load group "{task}.{group}": {exc}')
        return None


def _read_target_group(
    config_name: str,
    task: str,
    target: _GroupTarget,
) -> tuple[GroupBase | None, str | None]:
    """Read the Group of one resolved address.

    A static Group falls back to the model defaults when it has no row.  An
    instance of a dynamic Group list must have a row: a wrong index must not
    silently create an instance that was never added.
    """
    table = ConfigTable(config_name)
    if target.dynamic and table.get_group(task, target.address) is None:
        return None, f'No such Group instance: "{task}.{target.address}"'
    group_obj = _read_group(config_name, task, target.address, target.group_class)
    if group_obj is None:
        return None, f'Failed to load group: "{task}.{target.address}"'
    return group_obj, None


def _read_dynamic_field(
    config_name: str,
    task: str,
    target: _GroupTarget,
) -> list[GroupBase]:
    """Return every instance of a dynamic Group list, in stored index order.

    The stored index is the list position, so ordering by it is what restores
    the arrangement the user made.
    """
    instances: list[tuple[int, GroupBase]] = []
    for row in ConfigTable(config_name).list_task_rows(task):
        field, index = GroupAddress.split(row.group)
        if field != target.field or index is None:
            continue
        try:
            instances.append(
                (index, target.group_class.from_dict(Codec.decode(row.value)))
            )
        except (ValueError, ValidationError) as exc:
            logger.warning(f'Cannot load group "{task}.{row.group}": {exc}')
    instances.sort(key=lambda item: item[0])
    return [group_obj for _index, group_obj in instances]


def _write_dynamic_field(
    config_name: str,
    task: str,
    task_class: type[TaskBase],
    target: _GroupTarget,
    instances: list[GroupBase],
) -> list[ConfigSetEvent]:
    """Store a whole dynamic Group list, resequencing its addresses.

    Every row of the field is replaced by ``field@0`` ... ``field@n-1`` in one
    transaction, so the stored order always equals the list order and no stale
    index survives an insert, a removal or a reorder.  The reply reports every
    instance, because a structural change moves the addresses a client holds.
    """
    table = ConfigTable(config_name)
    events: list[ConfigSetEvent] = []
    with table.exclusive_transaction() as cursor:
        for row in table.list_task_rows(task, _cursor_=cursor):
            field, index = GroupAddress.split(row.group)
            if field == target.field and index is not None:
                table.delete_group(task, row.group, _cursor_=cursor)
        for index, group_obj in enumerate(instances):
            address = GroupAddress.make(target.field, index)
            _write_group(table, task, task_class, address, group_obj, cursor)
            events.extend(ConfigEvents.events_from_group(task, address, group_obj))
    return events


def _load_task(
    config_name: str,
    task: str,
) -> tuple[type[TaskBase], TaskBase] | None:
    """Load a whole Task; only used by operations that need every Group."""
    task_class = TaskNameResolver.resolve(task)
    if task_class is None:
        logger.warning(f'No such task class for task "{task}"')
        return None
    try:
        task_obj = TaskStore.load(config_name, task_class, task)
    except (KeyError, ValueError, ValidationError) as exc:
        logger.warning(f'Cannot load task "{task}": {exc}')
        return None
    return task_class, task_obj


def _write_group(
    table: ConfigTable,
    task: str,
    task_class: type[TaskBase],
    group: str,
    group_obj: GroupBase,
    cursor: Any = None,
) -> None:
    table.upsert_group(
        taskclass=task_class.__name__,
        task=task,
        groupclass=type(group_obj).__name__,
        group=group,
        value=Codec.encode(group_obj.to_dict()),
        _cursor_=cursor,
    )


def _reset_group(
    table: ConfigTable,
    task: str,
    task_class: type[TaskBase],
    group: str,
    group_class: type[GroupBase],
    cursor: Any = None,
) -> None:
    table.upsert_group(
        taskclass=task_class.__name__,
        task=task,
        groupclass=group_class.__name__,
        group=group,
        value=_EMPTY_GROUP_PAYLOAD,
        _cursor_=cursor,
    )


def _run_post_edit(
    task: str,
    group: str,
    before: GroupBase,
    after: GroupBase,
    requested: dict[str, Any],
) -> tuple[ConfigError | None, list[ConfigSetEvent]]:
    """Run ``post_edit()`` and return ``(error, side_effect_events)``."""
    try:
        after.post_edit(before, requested)
    except ValidationError as exc:
        return ConfigError.from_pydantic(exc), []
    except Exception as exc:  # noqa: BLE001
        logger.exception(exc)
        return ConfigError(msg=f'post_edit failed: {exc}'), []
    return None, ConfigEvents.post_edit_events(task, group, before, after, requested)


def _validate_group_args(
    task: str,
    target: _GroupTarget,
    group_obj: GroupBase,
    events: list[ConfigSetEvent],
) -> tuple[dict[str, Any], list[ConfigSetEvent], ConfigSetEvent | None]:
    """Validate each Argument separately and merge the validated values.

    Returns ``(new_values, accepted_events, error_event)``.  On failure the
    accepted events are returned too, so the caller can roll them back.
    """
    new_values: dict[str, Any] = {}
    accepted: list[ConfigSetEvent] = []
    for event in events:
        if event.arg not in target.group_class.model_fields:
            return (
                new_values,
                accepted,
                ConfigEvents.failed_event(
                    event,
                    f'No such field: "{task}.{target.address}.{event.arg}"',
                ),
            )
        try:
            validated = target.group_class.validate_patch({event.arg: event.value})
        except ValidationError as exc:
            return (
                new_values,
                accepted,
                ConfigEvents.failed_event(
                    event,
                    ConfigError.from_pydantic(exc),
                    value=getattr(group_obj, event.arg, None),
                ),
            )
        value = getattr(validated, event.arg)
        new_values[event.arg] = value
        accepted.append(ConfigEvents.event(task, target.address, event.arg, value))
    return new_values, accepted, None


def _failure(
    msg: str | ConfigError,
    *,
    value: Any = None,
) -> tuple[bool, list[ConfigSetEvent]]:
    """Return an operation level failure.

    The reason travels in an event whose task, group and arg are empty:
    operations that are not tied to one config argument (add, delete, copy)
    have no argument to attribute the error to.  ``value`` is returned in that
    event, which is how a getter hands back its default.
    """
    error = msg if isinstance(msg, ConfigError) else ConfigError(msg=msg)
    return False, [ConfigSetEvent(task='', group='', arg='', value=value, error=error)]
