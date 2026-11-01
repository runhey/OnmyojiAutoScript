"""
Stand-in of the backend restart manager, until the restart package is ported.

The real thing is upstream's ``alasio/backend/app/restart`` package
(``restart_base`` / ``restart_step`` / ``restart_flow`` / ``restart_manager`` /
``update_check`` / ``daily`` / ``resume_file``, ~7000 lines): it is NOT ported
to OAS yet, and neither is any maintenance flow (restart / update / daily /
startup). This file exists so that ``oas/backend/worker/manager.py`` -- which
is kept upstream-identical -- can keep its top-level import of
``RESTART_MANAGER``.

The worker manager reads exactly two answers from it (upstream
``alasio/backend/worker/manager.py`` :499, :505, :1219):

- ``frozen``: upstream ``RestartBase.frozen``, a plain attribute, ``False`` in
  ``RestartBase.__init__`` (``restart_base.py``:402, :410) and set ``True`` by
  the ``handover_intent`` context manager (``restart_base.py``:526-541) once a
  flow published its resume intent and the process is about to be replaced
  (cleared again, :539, only when that publication fails). While it is True a
  worker start is refused: a worker started now would die with the backend and
  could never be resumed.
- ``flow_running``: upstream ``RestartBase.flow_running``, a property
  returning ``self.current is not None`` (``restart_base.py``:426-432), i.e.
  whether a flow owns the backend right now (the ``init`` placeholder of the
  process startup included). While it is True a start is accepted as a queued
  auto-resume instead of being started immediately.

No maintenance flow exists in OAS, so both answers are ``False``: no operation
is frozen and no flow is considered running, which makes ``worker_start``
proceed directly with the worker lifecycle (the behavior OAS wants today).

Nothing else lives here -- no restart logic, no state, no imports of the
unported modules -- and the file is deleted the day the real ``app/restart``
package lands (the imported name stays ``RESTART_MANAGER``).

Deviation recorded in oas/backend/README.md.
"""


class RestartManager:
    """
    The maintenance-flow slot of the backend, stubbed to "no flow at all"

    Attributes (upstream they are plain attributes of ``RestartBase``, readable
    from any thread while the trio thread is the only writer -- see the module
    docstring for their upstream definitions):

        frozen (bool): Always False here, upstream's ``RestartBase.frozen``
        flow_running (bool): Always False here, upstream's
            ``RestartBase.flow_running``
    """

    frozen = False
    flow_running = False


# The process-wide manager (upstream: run by the lifespan, restart_manager.py:387)
RESTART_MANAGER = RestartManager()
