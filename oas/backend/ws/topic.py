"""
The topic registry of the websocket servers.

Ported from alasio/backend/ws/topic.py: ``WebsocketServer`` is the class
the app mounts on /api/ws, and it owns the two registries of that server
(ALL_TOPIC_CLASS: every topic the server can serve, DEFAULT_TOPIC_CLASS:
the topics it registers on connect).

Every topic of upstream is registered here: ConnState, ModList, ModHistory,
ConfigScan, ConfigNav, ConfigArg, Worker, Restart, Update, Log, TaskQueue,
TaskQueueI18n and Dashboard. Two registrations deviate from upstream, both to
make a topic reachable that upstream leaves out of its registry:

- ``TaskRunning``: upstream defines it in ``topic/que.py`` but never registers
  it (its data only arrives through worker pushes, so the topic is silent until
  a worker publishes a task);
- ``DevAssetsManager``: upstream has the line commented out (a dev-only tool);
  the OAS topic is empty and its folder operations refuse, see
  ``oas/backend/topic/dev_assets.py``.

This module also defines the second server of upstream, ``PreviewServer``:
it serves Preview alone on /api/preview, with a lossy buffer of one frame
per connection. Preview stays off the registry above on purpose (the frames
are raw binary, not events); the topic itself lives in
``oas/backend/topic/preview.py``.

``init()`` also negotiates the GUI language of the connection, as upstream
does: the language is stored in the ConnState default topic of this
connection, where every language-dependent topic reads it as a reactive
dependency.
"""

from typing import Type

from oas.backend.locale.accept_language import negotiate_accept_language
from oas.backend.topic.config import ConfigArg, ConfigNav
from oas.backend.topic.dashboard import Dashboard
from oas.backend.topic.dev_assets import DevAssetsManager
from oas.backend.topic.log import Log
from oas.backend.topic.mod import ModHistory, ModList
from oas.backend.topic.preview import Preview
from oas.backend.topic.que import TaskQueue, TaskQueueI18n, TaskRunning
from oas.backend.topic.restart import Restart
from oas.backend.topic.scan import ConfigScan
from oas.backend.topic.state import ConnState
from oas.backend.topic.worker import Worker
from oas.backend.topic.update import Update
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.backend.ws.ws_topic import BaseTopic
from oas.mod.info import ModEntryInfo

# The cookie the frontend stores the chosen GUI language in (upstream name
# ``alasio_lang``). The frontend must keep sending this name.
LANG_COOKIE = 'oas_lang'


def create_topic_dict(
    topic_classes: 'list[Type[BaseTopic]]',
) -> 'dict[str, Type[BaseTopic]]':
    """
    Convert a list of topic classes to a dict of them
    """
    return {topic.TOPIC_NAME: topic for topic in topic_classes}


class WebsocketServer(WebsocketTopicServer):
    # OAS backend transfer data via topics, not one-time request-response
    #
    # Frontend can subscribe to these topics, backend will send a "full" event immediately,
    # and push data events if any data changes. Once frontend unsubscribed, data push ends.
    #
    # After subscribing, frontend can call RPC function under that topic.
    # RPC functions won't give response data, it will trigger internal data changes and push topic data updates.
    ALL_TOPIC_CLASS = create_topic_dict(
        [
            # must contain ConnState
            ConnState,
            ModList,
            ModHistory,
            ConfigScan,
            ConfigNav,
            ConfigArg,
            Worker,
            Restart,
            Update,
            Log,
            TaskQueue,
            # upstream does not register TaskRunning (the topic is defined in
            # topic/que.py but left out of its registry)
            TaskRunning,
            TaskQueueI18n,
            Dashboard,
            # upstream keeps DevAssetsManager commented out of its registry
            # (a dev-only tool); the empty OAS topic is served here
            DevAssetsManager,
        ]
    )
    # List of default subscribed topics.
    # Without actively subscribing:
    # - Frontend can send and backend should accept RPC calls.
    # - Backend will send and frontend should accept data updates.
    DEFAULT_TOPIC_CLASS = create_topic_dict(
        [
            # must contain ConnState
            ConnState,
        ]
    )

    async def init(self):
        await super().init()
        # set language
        topic: 'ConnState | None' = self.subscribed.get(ConnState.TOPIC_NAME, None)
        if topic is not None:
            lang = self._negotiate_lang()
            state = await topic.nav_state
            state.lang = lang
            await topic.nav_state.mutate()

    def _negotiate_lang(self, default='en-US'):
        """
        Parse request into one available language

        Returns:
            str:
        """
        available = list(ModEntryInfo.oas().gui_language)
        ws = self.ws
        # try to match the lang in cookie
        prefer = ws.cookies.get(LANG_COOKIE, '')
        if prefer:
            use = negotiate_accept_language(prefer, available)
            if use:
                return use
        # try to match Accept-Language header
        try:
            prefer = ws.headers['Accept-Language']
        except KeyError:
            # this shouldn't happen, most browsers would post Accept-Language header
            prefer = ''
        if prefer:
            use = negotiate_accept_language(prefer, available)
            if use:
                return use
        # no luck, try to use default
        if default in available:
            return default
        # ohno, default language is not available, use the first language
        try:
            return available[0]
        except IndexError:
            # empty available languages, there's nothing we can do
            # return default anyway
            return default


class PreviewServer(WebsocketTopicServer):
    """
    The preview server: /api/preview, serving the Preview topic alone

    A second server of its own, as upstream: preview frames are raw binary
    sent through the lossy channel (they bypass the event protocol and reach
    the connection directly), so they are kept away from the topics of
    /api/ws. One frame is buffered per connection -- a slow client drops the
    frames in between instead of queueing them.

    ``init()`` is the base one: the language negotiation belongs to the
    ConnState default topic, which this server does not serve.
    """

    ALL_TOPIC_CLASS = create_topic_dict(
        [
            Preview,
        ]
    )
    # buffer 1 preview only
    LOSSY_BUFFER_LENGTH = 1
