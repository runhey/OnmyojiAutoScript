"""
Worker protocol events, ported from alasio/backend/worker/event.py.

Backend to worker commands (CommandEvent) and worker to backend messages
(ConfigEvent) plus the singleton decoder cache for both.
"""

from typing import Any, Tuple

from msgspec import Struct
from msgspec.msgpack import Decoder as MsgspecDecoder

from oas.ext.cache import cached_property
from oas.ext.singleton import Singleton


class CommandEvent(Struct):
    """
    Message from backend to worker
    """

    # command
    c: str
    # value
    v: Any = None


class ConfigEvent(Struct, omit_defaults=True):
    """
    Message from worker to backend.
    Backend will broadcast to websocket connections that subscribed this topic and key.
    """

    # topic_name
    t: str
    # config_name
    c: str = ''
    # Operation is always set
    # Key path of config
    # Usually to be (task, group, arg), might also be any custom key path
    k: Tuple = ()
    # Value.
    # value may be omitted, if so, value is None
    # if operation is "del", value will be omitted
    v: Any = None


class DecoderCache(metaclass=Singleton):
    @cached_property
    def COMMAND_EVENT(self):
        return MsgspecDecoder(CommandEvent)

    @cached_property
    def CONFIG_EVENT(self):
        return MsgspecDecoder(ConfigEvent)


DECODER_CACHE = DecoderCache()
