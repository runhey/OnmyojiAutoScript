"""WebSocket topics for the OAS configuration editor.

This implementation calls the existing ``MenuModMixin`` and
``ConfigModMixin`` APIs directly. It returns OAS-native menu and configuration
data so the WebSocket lifecycle can be verified before a frontend projection
layer is added.
"""

from typing import Any

import anyio
from msgspec import ValidationError

from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.source import DiskCache, KeyedSource
from oas.backend.topic.state import ConnState, NavState
from oas.backend.ws.ws_topic import BaseTopic
from oas.config.entry.error import ConfigError
from oas.config.entry.model import ConfigSetEvent, ModelConfigRef
from oas.mod.loader import MOD_LOADER


class ConfigNavSource(KeyedSource, DiskCache):
    """
    One-shot disk-cache source of ConfigNav: key (mod_name, config_name,
    lang).

    Static nav content read from disk; no push after the full snapshot --
    content changes come from subscription-condition changes (mod / config /
    lang), which rebuild the data through get_source -> reinit. Recycled by
    the data-expiry GC when the data TTL expired, regardless of subscribers
    (DiskCache semantics).
    """

    TOPIC_NAME = 'ConfigNav'

    def __init__(self, mod_name, config_name, lang):
        super().__init__()
        self.mod_name = mod_name
        self.config_name = config_name
        self.lang = lang

    def on_init(self):
        """
        Returns:
            dict[str, dict[str, dict]]:
                key: {nav_name}.{card_name}
                value:
                    {"i18n": name} for normal cards
                    {"i18n": name, "scheduler": True} for cards with scheduler
        """
        schemes = MOD_LOADER.menu_scheme_list(self.config_name)
        return {
            scheme['name']: MOD_LOADER.menu_nav(self.config_name, scheme['name'])
            for scheme in schemes
            if isinstance(scheme, dict) and isinstance(scheme.get('name'), str)
        }


class ConfigNav(BaseTopic):
    TOPIC_NAME = 'ConfigNav'

    async def get_source(self):
        state = ConnState(self.conn_id, self.server)
        mod_name = await state.mod_name
        config_name = await state.config_name
        lang = await state.lang
        if not mod_name or not config_name or not lang:
            return None
        source = ConfigNavSource.get(mod_name, config_name, lang)
        await source.reinit()
        return source


class ConfigArgSource(KeyedSource, DiskCache):
    """
    Disk-backed source of the ConfigArg topic. It directly uses the
    ``MenuModMixin`` and ``ConfigModMixin`` APIs. The returned value is the
    raw ``config_read`` mapping; GUI-specific projection is intentionally
    postponed until the Topic data path is working.
    """

    TOPIC_NAME = 'ConfigArg'

    def __init__(self, mod_name, config_name, nav_name, lang):
        super().__init__()
        self.mod_name = mod_name
        self.config_name = config_name
        self.nav_name = nav_name
        self.lang = lang

    def on_init(self):
        scheme = MOD_LOADER.menu_scheme_get(self.config_name, self.nav_name)
        tasks = []
        for group in scheme.get('groups', {}).values():
            if isinstance(group, dict):
                tasks.extend(
                    task for task in group.get('tasks', ()) if isinstance(task, str)
                )
        return MOD_LOADER.config_read(
            self.config_name,
            ModelConfigRef(task=list(dict.fromkeys(tasks)), group=[]),
        )


class ConfigArg(BaseTopic):
    TOPIC_NAME = 'ConfigArg'

    async def get_source(self):
        """
        Resolve the view source of the current (mod, config, nav, lang);
        the full view is built by source.subscribe() on registration.
        """
        state = ConnState(self.conn_id, self.server)
        mod_name = await state.mod_name
        config_name = await state.config_name
        nav_name = await state.nav_name
        lang = await state.lang
        if not mod_name or not config_name or not nav_name or not lang:
            return None
        source = ConfigArgSource.get(mod_name, config_name, nav_name, lang)
        if source is None:
            # config / mod / nav deleted: silent, next dependency change
            # re-runs this flow
            return None
        await source.reinit()
        return source

    @rpc
    async def set(self, task: str, group: str, arg: str, value: Any):
        if not task or not group or not arg:
            return
        # get config_name
        state = ConnState(self.conn_id, self.server)
        nav: NavState = await state.nav_state
        mod_name = nav.mod_name
        config_name = nav.config_name
        if not config_name:
            return

        success, responses = await anyio.to_thread.run_sync(
            MOD_LOADER.config_set,
            config_name,
            ConfigSetEvent(task=task, group=group, arg=arg, value=value),
            True,
        )
        responses: 'list[ConfigSetEvent]'
        if success:
            source = ConfigArgSource.get(
                mod_name, config_name, nav.nav_name, await state.lang
            )
            if source is not None:
                await source.reinit(force=True)
        else:
            resp = responses[0]
            if resp.error is not None:
                if isinstance(resp.error, ConfigError):
                    msg = resp.error.msg
                else:
                    msg = str(resp.error)
            else:
                msg = 'Unknown validation error'
            raise ValidationError(msg)

    @rpc
    async def reset(self, task: str, group: str, arg: str):
        if not task or not group or not arg:
            return
        # get config_name
        state = ConnState(self.conn_id, self.server)
        nav: NavState = await state.nav_state
        mod_name = nav.mod_name
        config_name = nav.config_name
        if not config_name:
            return

        resp = await anyio.to_thread.run_sync(
            MOD_LOADER.config_reset,
            config_name,
            ConfigSetEvent(task=task, group=group, arg=arg, value=None),
        )
        # resp: ConfigSetEvent | None
        if resp is None:
            # reset failed, do nothing
            return

        source = ConfigArgSource.get(
            mod_name, config_name, nav.nav_name, await state.lang
        )
        if source is not None:
            await source.reinit(force=True)

    @rpc
    async def group_reset(self, task: str, group: str):
        """
        Reset an entire group (task.group) to its default values.

        All args of the group fall back to the default value; the reset is
        broadcast through the unified config event entry, so every view of
        this config updates.

        Args:
            task (str): Task name
            group (str): Group name
        """
        if not task or not group:
            return
        # get config_name
        state = ConnState(self.conn_id, self.server)
        nav: NavState = await state.nav_state
        mod_name = nav.mod_name
        config_name = nav.config_name
        if not config_name:
            return

        resp = await anyio.to_thread.run_sync(
            MOD_LOADER.config_group_reset,
            config_name,
            ConfigSetEvent(task=task, group=group, arg='', value=None),
        )
        # resp: list[ConfigSetEvent]
        if not resp:
            # reset failed, do nothing
            return

        source = ConfigArgSource.get(
            mod_name, config_name, nav.nav_name, await state.lang
        )
        if source is not None:
            await source.reinit(force=True)

    @rpc
    async def card_reset(self, card: str):
        if not card:
            return
        # get config_name
        state = ConnState(self.conn_id, self.server)
        nav: NavState = await state.nav_state
        mod_name = nav.mod_name
        config_name = nav.config_name
        nav_name = nav.nav_name
        lang = await state.lang
        if not config_name or not nav_name:
            return

        scheme = MOD_LOADER.menu_scheme_get(config_name, nav_name)
        card_data = scheme.get('groups', {}).get(card, {})
        tasks = card_data.get('tasks', ()) if isinstance(card_data, dict) else ()

        source = ConfigArgSource.get(mod_name, config_name, nav_name, lang)
        if source is None:
            return
        list_task_group = [
            (task, group) for task in tasks for group in source.data.get(task, {})
        ]
        events = [
            ConfigSetEvent(task=task, group=group, arg='', value=None)
            for task, group in list_task_group
        ]

        resp = await anyio.to_thread.run_sync(
            MOD_LOADER.config_group_batch_reset,
            config_name,
            events,
        )
        # resp: list[ConfigSetEvent]
        if not resp:
            return

        await source.reinit(force=True)
