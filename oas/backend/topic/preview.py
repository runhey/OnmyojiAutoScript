"""
The Preview topic of the second websocket server (/api/preview).

Ported from alasio/backend/topic/preview.py (297 lines). **This port is the
topic surface only: an empty implementation.** It answers the preview
protocol and sends nothing.

Deviations from upstream:

- the preview data path is NOT ported. Upstream's ``PreviewTask`` (a
  ``BackgroundTask`` driven by the global trio nursery) asks the worker for
  a frame with ``CommandEvent(c='preview')``, throttles its normal / realtime
  subscribers and forwards the JPEG bytes to each connection through
  ``send_lossy``. None of it is here: this topic never talks to a worker and
  never sends a picture, so no constant of that flow (``PREVIEW_AVAILABLE`` /
  ``PREVIEW_IDLE`` / ``recurrence``) exists either;
- ``get_source()`` returns None, exactly as upstream: Preview has no snapshot
  model, so subscribing is silent (no "full" event, the scaffold sends
  nothing) and the topic is driven by its RPCs alone. "No data" here is the
  upstream semantic, not a deviation;
- ``preview_start`` keeps the upstream request contract -- the same ``name`` /
  ``speed`` arguments and the same refusal of a malformed or unknown config
  with ``RpcValueError`` (``validate_config_name`` then the scan cache) -- so
  a frontend written against upstream gets no unexpected protocol error; it
  simply never receives a frame. The accepted request is not recorded: there
  is no subscription to remember until the real flow lands;
- ``preview_stop`` and ``op_unsub`` keep their upstream names and are no-ops,
  for the same reason (nothing to unsubscribe);
- ``preview_start`` does not create a ``PreviewTask`` and the topic keeps no
  ``cache``: upstream's per-connection cache is part of the unported flow.

When the real preview lands, this module gains the ported ``PreviewTask``
(``BackgroundTask`` + ``SingletonNamed`` + ``GLOBAL_CONTEXT.global_task_group``
in place of the trio nursery), ``oas/backend/topic/_worker.py`` gets back the
branch that routes ``ConfigEvent(t='Preview')`` to
``PreviewTask(config).on_preview(...)`` (it currently logs it as an unknown
topic), and the server below gets mounted.

Reachability: upstream serves Preview on a second server of its own --
``PreviewServer`` with ``ALL_TOPIC_CLASS = {Preview}`` and
``LOSSY_BUFFER_LENGTH = 1`` (one live frame per connection, the rest dropped)
-- mounted at ``/api/preview`` (upstream ``ws/topic.py:108-112``,
``app/app.py:262``). ``oas/backend/ws/topic.py`` does not define that server
yet, so this module is not reachable over a websocket until it does. Preview
is deliberately NOT added to the ``/api/ws`` registry: upstream keeps the
per-connection lossy binary channel away from the regular topics.
"""

from typing import Literal

from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.event import RpcValueError
from oas.backend.topic.scan import ConfigScanSource
from oas.backend.ws.ws_topic import BaseTopic
from oas.config.table.scan import validate_config_name

PREVIEW_SPEED = Literal['normal', 'realtime']


class Preview(BaseTopic):
    """
    The preview topic: RPC-only, no snapshot, currently no data stream

    Subscribing sends nothing (``get_source`` returns None, so the connection
    registers silently and the scaffold emits no "full" event), which is what
    upstream does too. The two RPCs keep the upstream protocol: the frontend
    may start and stop a preview without an error, it just receives no frame
    while the data path is unported.
    """

    TOPIC_NAME = 'Preview'

    async def get_source(self):
        """
        Preview has no source: it is not migrated to the source model

        Upstream returns None here as well: Preview has no snapshot, and its
        subscription is driven by the preview_start / preview_stop RPCs. A
        None source means "subscribe silently, send no full event".

        Returns:
            None: Always, until the real preview flow lands.
        """
        return None

    @rpc
    async def preview_start(self, name: str, speed: PREVIEW_SPEED):
        """
        Accept a preview request without starting a stream

        The request is validated exactly like upstream (the name must be a
        usable config file name, and the config must be in the scan cache) so
        a bad or unknown config is refused with the same error; a valid
        request is accepted and then ignored, because the frame flow is not
        ported.

        Args:
            name (str): Name of the config whose worker should be previewed
            speed (PREVIEW_SPEED): Requested display speed, 'normal' or
                'realtime'. Accepted for protocol compatibility, unused here.
        """
        # check if name is a validate filename
        error = validate_config_name(name)
        if error:
            raise RpcValueError(error)
        # get current configs
        data = ConfigScanSource().data
        try:
            _ = data[name]
        except KeyError:
            raise RpcValueError(f'No such config: "{name}"')

    @rpc
    async def preview_stop(self):
        """
        Stop the preview of this connection

        Kept for the upstream protocol. There is no stream and no recorded
        request, so this is a no-op.
        """

    async def op_unsub(self):
        """
        Drop the preview state of a connection that unsubscribed

        Kept for the upstream protocol, see preview_stop: a no-op while no
        subscription state exists.
        """
