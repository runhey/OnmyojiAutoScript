from collections import defaultdict
from datetime import datetime
from typing import Any

from msgspec import DecodeError, Struct
from msgspec.json import Decoder as JsonDecoder

from oas.config.entry.error import ConfigError
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.ext.cache import cached_property
from oas.ext.file.msgspecfile import JsonCacheTTL
from oas.ext.singleton import Singleton
from oas.logger import logger


class ModelConfigRef(Struct):
    """
    {"task": list[str], "group": list[tuple[str, str]]}
    indicates to read task and taskgroups in user config
    """

    task: list[str]
    group: list[tuple[str, str]]


class ModelNavRef(Struct):
    """
    {
        "file": str,  # indicates to read {nav}_config.json
        "i18n": list[str],  # indicates to read {nav}_i18n.json
        "config": {"task": list[str], "group": list[tuple[str, str]]}
            # indicates to read task and taskgroups in user config
    }
    """

    file: str
    i18n: list[str]
    config: ModelConfigRef


# key: {nav_name}
MODEL_CONFIG_INDEX = dict[str, ModelNavRef]


class ModelGroupRef(Struct):
    """
    {'file': file, 'cls': class_name, 'task': ref_task_name}
    which indicates:
    - read config from task={ref_task_name} and group={group_name}
    - validate with model file={file}, class {class_name}
    class_name can be:
    - {group_name} for normal group
    - {task_name}_{group_name} that inherits from class {group_name}, for override task group
    """

    file: str
    cls: str
    task: str


class ModelTaskRef(Struct):
    """
    {"group": dict[str, dict], "config": dict}
    """

    group: dict[str, ModelGroupRef]
    config: ModelConfigRef


# key: {task_name}
MODEL_TASK_INDEX = dict[str, ModelTaskRef]

# {nav}_config.json:
#   {card_name}.{arg_name}.{attr}
# {nav}_i18n.json:
#   {group_name}.{arg_name}.{lang}
# {nav}.index.json
#   {component}.{field}.{lang}
MODEL_DICT_DEPTH3_ANY = dict[str, dict[str, dict[str, Any]]]
# queue.index.json
#   {task_name}.{lang}
MODEL_DICT_DEPTH2_ANY = dict[str, dict[str, Any]]


class DecoderCache(metaclass=Singleton):
    @cached_property
    def MODEL_CONFIG_INDEX(self):
        return JsonDecoder(MODEL_CONFIG_INDEX)

    @cached_property
    def MODEL_TASK_INDEX(self):
        return JsonDecoder(MODEL_TASK_INDEX)

    @cached_property
    def MODEL_DICT_DEPTH2_ANY(self):
        return JsonDecoder(MODEL_DICT_DEPTH2_ANY)

    @cached_property
    def MODEL_DICT_DEPTH3_ANY(self):
        return JsonDecoder(MODEL_DICT_DEPTH3_ANY)


DECODER_CACHE = DecoderCache()


class ConfigSetEvent(Struct):
    task: str
    group: str
    arg: str
    value: Any
    error: ConfigError | Exception | None = None


class ConfigEvents:
    """Builders for the :class:`ConfigSetEvent` reply protocol."""

    @staticmethod
    def event(task: str, group: str, arg: str, value: Any) -> ConfigSetEvent:
        """Return one event for a single argument."""
        return ConfigSetEvent(task=task, group=group, arg=arg, value=value)

    @staticmethod
    def events_from_task(task: str, task_obj: TaskBase) -> list[ConfigSetEvent]:
        """Return the events of every argument of a Task."""
        return [
            ConfigEvents.event(task, group, arg, value)
            for group, values in task_obj.to_dict().items()
            for arg, value in values.items()
        ]

    @staticmethod
    def events_from_group(
        task: str,
        group: str,
        group_obj: GroupBase,
    ) -> list[ConfigSetEvent]:
        """Return the events of every argument of one Group."""
        return [
            ConfigEvents.event(task, group, arg, value)
            for arg, value in group_obj.to_dict().items()
        ]

    @staticmethod
    def group_events(
        events: list[ConfigSetEvent],
    ) -> dict[tuple[str, str], list[ConfigSetEvent]]:
        """Group events by ``(task, group)``."""
        grouped: dict[tuple[str, str], list[ConfigSetEvent]] = defaultdict(list)
        for event in events:
            grouped[(event.task, event.group)].append(event)
        return grouped

    @staticmethod
    def fail_events(
        events: list[ConfigSetEvent],
        message: str,
    ) -> list[ConfigSetEvent]:
        """Return copies of ``events`` marked as failed with ``message``."""
        return [ConfigEvents.failed_event(event, message) for event in events]

    @staticmethod
    def failed_event(
        event: ConfigSetEvent,
        error: str | ConfigError | Exception,
        value: Any = None,
    ) -> ConfigSetEvent:
        """Return ``event`` marked as failed with ``error``."""
        if isinstance(error, (str, Exception)):
            error = ConfigError(msg=str(error))
        return ConfigSetEvent(
            task=event.task,
            group=event.group,
            arg=event.arg,
            value=value,
            error=error,
        )

    @staticmethod
    def rollback_group(
        events: list[ConfigSetEvent],
        task: str,
        group: str,
        current: GroupBase,
        error: ConfigError,
    ) -> list[ConfigSetEvent]:
        """Return rollback events restoring every requested argument."""
        result: list[ConfigSetEvent] = []
        for index, event in enumerate(events):
            result.append(
                ConfigSetEvent(
                    task=task,
                    group=group,
                    arg=event.arg,
                    value=getattr(current, event.arg, None),
                    error=error if index == 0 else None,
                )
            )
        return result

    @staticmethod
    def post_edit_events(
        task: str,
        group: str,
        before: GroupBase,
        after: GroupBase,
        requested: dict[str, Any],
    ) -> list[ConfigSetEvent]:
        """Return the extra events caused by ``post_edit()``."""
        before_values = before.to_dict()
        after_values = after.to_dict()
        events: list[ConfigSetEvent] = []
        for arg, value in after_values.items():
            if before_values.get(arg) == value:
                continue
            if arg in requested and requested[arg] == value:
                continue
            events.append(ConfigSetEvent(task=task, group=group, arg=arg, value=value))
        return events


class TaskItem(Struct):
    TaskName: str
    NextRun: datetime

    def __str__(self):
        # show as str, to avoid showing a long tzinfo object
        return f'Task(TaskName="{self.TaskName}", NextRun="{self.NextRun}")'

    __repr__ = __str__


class ModJsonCacheTTL(JsonCacheTTL):
    def load_resource(
        self, file: str, decoder: JsonDecoder = None, default_factory=dict
    ):
        try:
            return super().load_resource(file, decoder=decoder)
        except (FileNotFoundError, DecodeError) as e:
            logger.error(f'Failed to read model json: "{file}": {e}')
            return default_factory()
        except Exception as e:  # noqa: BLE001 - log and fall back to defaults
            logger.exception(e)
            return default_factory()


MOD_JSON_CACHE = ModJsonCacheTTL()
