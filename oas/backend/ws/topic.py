"""
The topic registry of the websocket servers.

Ported from alasio/backend/ws/topic.py: ``WebsocketServer`` is the class
the app mounts on /api/ws, and it owns the two registries of that server
(ALL_TOPIC_CLASS: every topic the server can serve, DEFAULT_TOPIC_CLASS:
the topics it registers on connect).

Only the ported topics are registered here. The rest of the upstream
registry -- ConnState, ModList, ModHistory, ConfigNav, ConfigArg,
Worker, Restart, Update, Log, TaskQueue, TaskQueueI18n and Dashboard --
lands with its own topic (see oas/backend/README.md, leftover 14). The
second server of upstream (PreviewServer on /api/preview) has no topic
here at all.
"""

from typing import Type

from oas.backend.topic.scan import ConfigScan
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.backend.ws.ws_topic import BaseTopic


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
            ConfigScan,
        ]
    )
    # List of default subscribed topics.
    # Without actively subscribing:
    # - Frontend can send and backend should accept RPC calls.
    # - Backend will send and frontend should accept data updates.
    #
    # Empty until ConnState is ported: upstream registers ConnState here
    # as the one topic every connection takes on connect.
    DEFAULT_TOPIC_CLASS = create_topic_dict([])
