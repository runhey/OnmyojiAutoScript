"""
The background gc task: it must recycle the idle topic sources.

Alasio runs BaseSource.gc_idle() inside sync_task_gc, next to the renewal
code sweep; OAS schedules the same call inline (the only collector migrated
so far, see oas/backend/README.md, leftover 12).
"""

import anyio

from oas.backend.app.app import task_gc
from oas.backend.reactive.source import BaseSource


def test_task_gc_recycles_idle_sources(monkeypatch):
    """
    A gc pass calls BaseSource.gc_idle(), so a source whose data TTL
    expired is recycled instead of living until the process ends.
    """
    calls = []

    def spy(cls):
        calls.append(cls)

    monkeypatch.setattr(BaseSource, 'gc_idle', classmethod(spy))

    async def one_pass():
        # wait=0 keeps the loop body reachable without waiting 8 seconds
        with anyio.move_on_after(0.05):
            await task_gc(wait=0)

    anyio.run(one_pass)
    assert calls
