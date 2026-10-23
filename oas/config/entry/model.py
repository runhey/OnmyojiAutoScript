from datetime import datetime
from typing import Any

from msgspec import DecodeError, Struct, field
from msgspec.json import Decoder as JsonDecoder

from oas.config.entry.error import ConfigError
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


class ConfigResult(Struct):
    """Unified result object for the OAS native ``cfg_*`` API.

    ``success`` is the only branch selector.  On success ``events`` carries
    the per-arg values that changed (and ``value`` is used by getters); on
    failure ``error`` always contains a :class:`ConfigError`.
    """

    success: bool
    events: list[ConfigSetEvent] = field(default_factory=list)
    value: Any = None
    error: ConfigError | None = None


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
