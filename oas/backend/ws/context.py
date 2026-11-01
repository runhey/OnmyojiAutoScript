"""
The runtime context of the backend, injected by the lifespan.
"""

from typing import Optional

from anyio import Event
from anyio.abc import TaskGroup

from oas.ext.singleton import Singleton


class GlobalContext(metaclass=Singleton):
    """
    Everything the backend has to reach from outside the running loop.

    The lifespan injects the fields on startup and clears them on shutdown.
    Two fields differ from Alasio's GlobalContext:

    - ``trio_token`` is gone: the loop lives in ``oas.backend.anyio.AnyIO``,
      and a worker thread wakes it with ``AnyIO.call_soon()``;
    - ``global_nursery`` becomes ``global_task_group``: the group opened by
      the lifespan owns the long-lived background tasks only (the mpipe
      receiver, the token rotation). Every WebSocket connection opens its
      own task group for its receive, send and heartbeat tasks, so a stuck
      connection cannot hold the other ones.
    """

    def __init__(self):
        # injected on lifespan start, cleared on lifespan end
        self.global_task_group: Optional[TaskGroup] = None
        self.shutdown_event: Optional[Event] = None


GLOBAL_CONTEXT = GlobalContext()
