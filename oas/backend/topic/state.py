"""
The ConnState topic: the navigation state of one GUI connection.

Ported from alasio/backend/topic/state.py, with two deviations (both
recorded in oas/backend/README.md):

- the three restart RPCs (``restart`` / ``cancel_restart`` /
  ``force_restart``) are not ported: they drive
  ``alasio/backend/app/restart/restart_manager.py``, which has no OAS
  equivalent yet, and the Restart topic that reports their progress is not
  ported either;
- the language list of ``set_lang`` comes from the built-in mod entry
  (``ModEntryInfo.oas().gui_language``) instead of upstream's
  ``Const.GUI_LANGUAGE``: OAS has no ``config/const.py``, and the mod entry
  is the declarer of the languages this build serves.

ConnState is the default topic of the websocket server: every connection
registers it on connect (see ws/topic.py), and its language is negotiated in
``WebsocketServer.init``. It has no data source of its own -- its state is
the reactive ``nav_state`` value that other topics observe, so a change of
the language re-subscribes those topics and pushes their data in the new
language. A client subscription to ConnState therefore sends no full event,
exactly as upstream.
"""

from msgspec import Struct

from oas.backend.locale.accept_language import negotiate_accept_language
from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.event import RpcValueError
from oas.backend.reactive.rx_trio import async_reactive, async_reactive_source
from oas.backend.topic.scan import ConfigScanSource
from oas.backend.ws.ws_topic import BaseTopic
from oas.config.table.scan import validate_config_name
from oas.mod.info import ModEntryInfo


class NavState(Struct):
    lang: str = 'en-US'
    config_name: str = ''
    mod_name: str = ''
    nav_name: str = ''

    def clear(self):
        self.config_name = ''
        self.mod_name = ''
        self.nav_name = ''


class ConnState(BaseTopic):
    TOPIC_NAME = 'ConnState'

    @async_reactive_source
    async def nav_state(self):
        return NavState()

    # Proxy reactive nav_state,
    # so one modification to nav_state won't trigger mutation to all topics listening to nav_state
    @async_reactive
    async def lang(self) -> str:
        state = await self.nav_state
        return state.lang

    @async_reactive
    async def config_name(self) -> str:
        state = await self.nav_state
        return state.config_name

    @async_reactive
    async def mod_name(self) -> str:
        state = await self.nav_state
        return state.mod_name

    @async_reactive
    async def nav_name(self) -> str:
        state = await self.nav_state
        return state.nav_name

    @rpc
    async def set_lang(self, lang: str):
        """
        Set the GUI language of this connection.

        Like upstream, the input is validated against the available GUI
        languages and stored as given (the negotiation is only a check here,
        the frontend sends the canonical code).
        """
        available = list(ModEntryInfo.oas().gui_language)
        use = negotiate_accept_language(lang, available)
        if not use:
            raise RpcValueError(
                f'Language "{lang}" does not match any available languages'
            )
        # set
        state: NavState = await self.nav_state
        state.lang = lang
        await self.nav_state.mutate()

    @rpc
    async def set_config(self, name: str):
        """
        Set config name, and change nav_state accordingly
        """
        # allow set empty config to clear state on page leave
        if not name:
            state: NavState = await self.nav_state
            state.clear()
            # broadcast
            await self.nav_state.mutate()
            return

        # check if name is a validate filename
        error = validate_config_name(name)
        if error:
            raise RpcValueError(error)

        state: NavState = await self.nav_state
        if state.config_name == name:
            # same config, no need to change it
            return

        # get current configs
        data = ConfigScanSource().data
        try:
            config = data[name]
        except KeyError:
            raise RpcValueError(f'No such config: "{name}"')

        # set
        # note that mod_name is calculated in backend to ensure consistency of mod_name and config_name
        state.config_name = name
        state.mod_name = config.mod
        # reset nav when switching to new config
        state.nav_name = ''

        # broadcast
        await self.nav_state.mutate()

    @rpc
    async def set_nav(self, name: str):
        """
        Set config name, and change nav_state accordingly
        """
        state: NavState = await self.nav_state
        if state.nav_name == name:
            # same nav, no need to change it
            return

        # maybe we don't need to validate nav_name, as ConfigArg can handle
        state.nav_name = name

        # broadcast
        await self.nav_state.mutate()
