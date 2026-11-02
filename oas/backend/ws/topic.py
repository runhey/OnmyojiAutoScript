"""
The topic registry of the websocket servers.

Ported from alasio/backend/ws/topic.py: ``WebsocketServer`` is the class
the app mounts on /api/ws, and it owns the two registries of that server
(ALL_TOPIC_CLASS: every topic the server can serve, DEFAULT_TOPIC_CLASS:
the topics it registers on connect).

Only the ported topics are registered here: ConnState, ModList, ModHistory,
ConfigScan, ConfigNav, ConfigArg, Worker, Restart, Update and Log. The rest of
the upstream registry -- TaskQueue, TaskQueueI18n and Dashboard -- lands with
its own topic (see oas/backend/README.md, the topic checklist).

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
from oas.backend.topic.log import Log
from oas.backend.topic.mod import ModHistory, ModList
from oas.backend.topic.preview import Preview
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
