"""
The ModList and ModHistory topics: the mods this build ships.

Ported from alasio/backend/topic/mod.py, with one deviation recorded in
oas/backend/README.md: the mods come from the OAS mod layer
(``oas/mod/loader.py`` MOD_LOADER) instead of Alasio's ``config/entry``
loader, and MOD_LOADER.dict_mod declares the built-in entries directly
rather than reading ``_index/*.json`` folders.

Both topics are one-shot disk-cache sources: the data is read on the first
subscribe (in a thread, see on_init_async) and recycled when the cache TTL
expired, so a mod folder changed on disk is picked up by the next
subscription after the TTL.
"""

from msgspec import Struct
from msgspec.structs import asdict

from oas.backend.reactive.source import DiskCache, GlobalSource
from oas.backend.ws.ws_topic import BaseTopic
from oas.deploy.history.decode_history import decode_history
from oas.ext.path.atomic import atomic_read_bytes
from oas.logger import logger
from oas.mod.loader import MOD_LOADER


class ModOption(Struct):
    value: str
    label: str


class ModListSource(GlobalSource, DiskCache):
    """
    One-shot disk-cache source of ModList: static mod list read from
    MOD_LOADER, recycled by the data-expiry GC when the TTL expired.
    """

    TOPIC_NAME = 'ModList'

    def on_init(self):
        """
        Returns:
            list[ModOption]: List of mod names

        Note: MOD_LOADER.dict_mod builds the mod list, which reads config
        entry data: on_init always runs in a thread (on_init_async), so the
        first subscription never blocks the event loop.
        """
        dic_mod = MOD_LOADER.dict_mod
        return [ModOption(value=name, label=name) for name in dic_mod if name]


class ModList(BaseTopic):
    TOPIC_NAME = 'ModList'

    async def get_source(self):
        source = ModListSource()
        await source.reinit()
        return source


class ModHistorySource(GlobalSource, DiskCache):
    """
    One-shot disk-cache source of ModHistory.

    There is exactly one cache layer -- the source data itself (model-
    default TTL 8s + data-expiry GC). The old file-level HISTORY_CACHE
    (ResourceCacheTTL) was removed: it duplicated the source cache, and
    the source already holds the decoded history for its whole lifetime.
    """

    TOPIC_NAME = 'ModHistory'

    def on_init(self):
        """
        Traverse all mods and decode their packed release history.
        Runs in a thread (on_init_async): file reads must not block the
        event loop.

        Returns:
            dict[str, dict[str, Union[list[dict], str]]]:
                key: mod name
                value: {"data": list[dict], "error": str}
                    "data" is the release history of the mod, empty on error
                    "error" is the error message, only present on error
        """
        dic_mod = MOD_LOADER.dict_mod
        out = {}
        for name, mod in dic_mod.items():
            if not name:
                continue
            file = mod.root.joinpath('.pack/history.pack')
            try:
                history = decode_history(atomic_read_bytes(file))
            except Exception as e:
                logger.warning(f'Failed to load mod history "{file}": {e}')
                out[name] = {'data': [], 'error': f'{e.__class__.__name__}: {e}'}
                continue
            # HistoryObj is array_like, convert to dict to avoid encoding as a list
            out[name] = {'data': [asdict(obj) for obj in history]}
        return out


class ModHistory(BaseTopic):
    TOPIC_NAME = 'ModHistory'

    async def get_source(self):
        source = ModHistorySource()
        await source.reinit()
        return source
