"""
The ConnState topic: the navigation state of one GUI connection.

Ported from alasio/backend/topic/state.py, with one deviation (recorded in
oas/backend/README.md):

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
    async def restart(self):
        """
        Gracefully restart the entire backend

        Every running worker is asked to stop gracefully (scheduler-stopping:
        the current task finishes first, a 10-minute wait escalates to a kill),
        then the backend restarts and resumes the workers stopped by this
        request. Returns as soon as the restart flow is accepted: the progress
        flows through the Restart and Worker topics.
        """
        # local import (see set_config below): the restart package drives the
        # worker manager, whose topic imports this module
        from oas.backend.app.restart.restart_manager import RESTART_MANAGER, FlowRefused

        try:
            RESTART_MANAGER.restart()
        except FlowRefused as e:
            # the message carries the next step for the user (a restart is
            # already in progress, an update restarts the backend by itself,
            # the backend is still starting up)
            raise RpcValueError(str(e)) from None

    @rpc
    async def cancel_restart(self):
        """
        Cancel the restart flow waiting for the workers to stop

        Only the cancellable phase of the flow is interrupted: the workers it
        stopped are resumed again and the check sequences it paused restart
        (the wrap-up of the flow owns both). Past its point of no return (the
        handover started) or after a daily upgrade the cancel is refused.
        """
        # local import (see restart above)
        from oas.backend.app.restart.restart_manager import RESTART_MANAGER, FlowRefused

        try:
            await RESTART_MANAGER.cancel_restart()
        except FlowRefused as e:
            raise RpcValueError(str(e)) from None

    @rpc
    async def force_restart(self):
        """
        Restart the entire backend immediately

        Unlike restart(), the workers are not waited for: every running worker
        is ended right away and nothing is resumed after the backend restarted.
        """
        # local import (see restart above)
        from oas.backend.app.restart.restart_manager import RESTART_MANAGER

        await RESTART_MANAGER.force_restart()

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
