"""
The Restart topic: which maintenance flow owns the backend right now.

Ported from alasio/backend/topic/restart.py verbatim. The topic is passive
by design -- upstream defines no producer and no RPC here: the restart
manager pushes phases / the flow view into RestartSource, and the frontend
just reads them (it disables the update / restart buttons from this data).
The RPCs that trigger those flows live in ConnState (restart /
cancel_restart / force_restart), which are not ported yet, so for now the
topic only ever reports "the backend is idle"; see oas/backend/README.md.
"""

import time

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import GlobalSource, ResidentCache
from oas.backend.ws.ws_topic import BaseTopic


class RestartSource(GlobalSource, ResidentCache):
    """
    Phase of the backend maintenance flow: data = {phase, flow, cancellable,
    upgraded, update} while a restart / update / daily flow is in progress,
    empty otherwise.

    Event protocol: a string sets the phase ('' clears it: no restart in
    progress), a dict merges the flow view ({flow, cancellable, upgraded}) of
    the restart manager. The data clears itself when neither a phase nor a flow
    is left. Worker states are NOT duplicated here: the Worker topic is the
    single source of truth for every worker, this topic only tells which flow
    owns the backend, in which stage, and whether it may still be cancelled
    (the frontend disables the update / restart buttons from here).

    Phases:
    - 'stopping': waiting for the workers to stop gracefully;
    - 'shutting-down': all workers stopped, the backend is about to exit;
    - 'resuming': the new backend is starting the recorded workers;
    - 'done': the resume queue was processed (transient, usually only seen by
      a frontend that reconnects fast).
    """

    TOPIC_NAME = 'Restart'

    # the keys of the flow view (the events that merge instead of setting the
    # phase)
    VIEW_KEYS = ('flow', 'cancellable', 'upgraded')

    def _apply(self, event):
        """
        [锁内] phase string / flow view dict -> data

        A phase string sets the phase, '' clears it, a dict merges the flow
        view; the data clears when no phase and no flow are left (the frontend
        reads "empty topic" as "the backend is idle").

        Returns:
            bool: If data changed
        """
        data = dict(self.data)
        if isinstance(event, dict):
            for key in self.VIEW_KEYS:
                if key in event:
                    data[key] = event[key]
        elif event:
            data['phase'] = event
        else:
            data.pop('phase', None)
        if not data.get('phase') and not data.get('flow'):
            if not self.data:
                return False
            self.data = {}
            return True
        data['update'] = time.time()
        if self.data == data:
            return False
        self.data = data
        return True

    def _convert(self, event):
        """
        [锁内] Whole-data set: the payload references the data dict, which is
        replaced wholesale by later events (never mutated in place), so the
        deferred encoding outside the lock is safe

        Returns:
            ResponseEvent:
        """
        return ResponseEvent(t=self.TOPIC_NAME, o='full', v=self.data)


class Restart(BaseTopic):
    TOPIC_NAME = 'Restart'

    async def get_source(self):
        """
        Restart phases flow entirely through events, there is no full-data
        source to refresh on subscribe
        """
        return RestartSource()
