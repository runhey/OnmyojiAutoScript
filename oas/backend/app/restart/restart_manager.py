"""
Ported verbatim from ``alasio/backend/app/restart/restart_manager.py``.

This file replaces the former stand-in: the 58-line ``RestartManager`` sketch
that existed only so ``oas/backend/worker/manager.py`` could import
``RESTART_MANAGER`` (it answered ``frozen = False`` / ``flow_running = False``).
The full manager lives here now -- the entries and ``run()`` of the maintenance
flows -- and the imported name is unchanged: ``RESTART_MANAGER`` at the end of
the file (upstream line 387).

Contract kept for the worker manager: ``RestartManager`` subclasses
``RestartStep`` (``restart_step``), which subclasses ``RestartBase``
(``restart_base``), so ``RESTART_MANAGER.frozen`` (the plain attribute set in
``RestartBase.__init__`` and by ``handover_intent``) and
``RESTART_MANAGER.flow_running`` (the ``RestartBase`` property) are the same two
members the worker manager reads.

Deviations from upstream:

- the import rewrites: ``alasio.`` -> ``oas.`` on the five ``alasio`` import
  lines (``oas.backend.app.restart.restart_base``,
  ``oas.backend.app.restart.restart_flow``,
  ``oas.backend.app.restart.restart_step``, ``oas.backend.mpipe.mpipe_backend``,
  ``oas.logger``) and on the ``alasio.backend.app.restart.daily`` module path
  named by the ``request_daily`` docstring;
- trio -> anyio, in code only: ``import trio`` -> ``import anyio``,
  ``trio.open_nursery() as nursery`` -> ``anyio.create_task_group() as tg``
  (anyio's call takes no name argument), with the alias ``tg`` used at the three
  places that touch the task group (``run()``: ``self.nursery = tg``;
  ``spawn()`` and ``_claim()``: ``tg = self.nursery`` + ``tg.start_soon(...)``),
  ``trio.sleep_forever()`` -> ``anyio.sleep_forever()`` and
  ``except trio.Cancelled:`` -> ``except anyio.get_cancelled_exc_class():`` (two
  sites). No other trio construct appears in the file: no Event / Lock /
  move_on_after / fail_after / CancelScope / doorbell;
- the ``trio`` wording of the upstream comments and docstrings is left intact
  (the ``Entries (trio thread: ...)`` comment included), as the port rules keep
  prose unchanged; no ``alasio_lang``, ``alasio_token`` or ``Alasio`` spelling
  occurs upstream, so none is renamed;
- the ``self.nursery`` field keeps upstream's name (``restart_base`` documents
  it); only the alias bound to the task group is anyio's;
- formatting only: the file is the ``ruff format`` fixed point of the mapped
  upstream under the repo config (``py314``, single quotes): the two long
  ``restart_base`` / ``restart_flow`` import lines are wrapped, and the blank
  line that ``ruff format`` puts after the upstream docstring (the module
  docstring upstream) is kept.
"""

"""
Restart manager: the single slot of the backend maintenance flows

The manager is the entry surface of the flow model: the rpc layer (restart /
update_apply / cancel_restart / cancel_apply) and the daily task request a flow
here, the lifespan runs it with ``run()``. Requesting a flow while another one
owns the backend is
*refused* with a user-facing reason (never queued, never joined): the user
retries, or the chain satisfies the request by itself (an update hands over
with a restart, a restart is followed by the startup update check). The
frontend disables the restart / update buttons while a flow is in flight, so
the refusals are the guard for the racy cases (two clicks, a click from a
second client).

The slot is the single source of truth (``restart_base``) and every entry
claims it in one synchronous section (no await between the judgment and the
claim), so two concurrent rpc calls can never both be accepted. The process
startup enters the slot as ``init`` first: only the startup flow may leave it,
so no user flow can sneak in between the process start and the startup flow.

The class layers of the package: ``RestartBase`` (the state of the slot and
its context managers) -> ``RestartStep`` (the single steps a flow drives) ->
``RestartManager`` (this module: the entries and ``run()``). The flows
(``restart_flow``) are objects the manager creates per run: each one owns its
state (the cancellation window above all) and its body (``Flow.run()``). Every
entry names the flow class it claims: the class carries the flow name, the
refusal of its request and the parked state of its workers -- no name-keyed
registry is resolved at the claim.
"""

from typing import Optional

import anyio

from oas.backend.app.restart.restart_base import (
    INIT_FLOW,
    STARTING_UP,
    Flow,
    FlowCancelled,
    FlowRefused,
    InitFlow,
)
from oas.backend.app.restart.restart_flow import (
    FlowDaily,
    FlowRestart,
    FlowStartup,
    FlowUpdate,
)
from oas.backend.app.restart.restart_step import RestartStep
from oas.backend.mpipe.mpipe_backend import has_supervisor
from oas.logger import logger


class RestartManager(RestartStep):
    """
    The single slot of the maintenance flows, its entries and its run

    ``run()`` is the lifespan entry: it owns the nursery the flows (and the
    resume queue) run in and keeps the manager alive for the requests until the
    process shuts down. The flows are objects the manager creates at the claim
    (``flow_cls(self)``, see ``restart_flow``).
    """

    async def run(self):
        """
        Run the maintenance flows of this process (the lifespan entry)

        The manager owns its nursery: the flow bodies (and the resume queue a
        flow spawns) are tasks of it, a failing flow ends alone and the lifespan
        nursery is never taken down by the maintenance. The slot enters ``init``
        in the same synchronous section as the nursery, then the startup flow is
        claimed -- the process is served by that flow from its first
        instruction.

        Returns when the process shuts down (the lifespan nursery is
        cancelled); a failure of the nursery is reported, the backend keeps
        running without a flow (the next restart / update request claims the
        slot normally).

        The nursery field is cleared the moment the teardown starts, before the
        flows are cancelled and joined: from then on the manager serves no task
        -- no flow is claimed, no view is pushed, no resume queue is spawned.
        """
        try:
            async with anyio.create_task_group() as tg:
                # one synchronous section: no request can slip in between the
                # nursery and the init slot
                self.nursery = tg
                self.enter_init()
                try:
                    self.request_startup()
                except Exception as e:
                    # the gate must never stay shut: without the startup flow
                    # the backend runs with the configs startable by hand
                    logger.error(f'[Restart] Failed to start the startup flow: {e}')
                    logger.exception(e)
                    self.abandon_startup()
                # the requests claim flows from any task of the backend (the
                # rpc layer, the daily task) while this task keeps the nursery
                try:
                    await anyio.sleep_forever()
                finally:
                    # the teardown: the flows are about to be cancelled and
                    # joined, no task may start from here on (the field is
                    # cleared before the nursery closes for new arrivals)
                    self.nursery = None
        except anyio.get_cancelled_exc_class():
            # the process is going down (the lifespan nursery was cancelled)
            raise
        except Exception as e:
            logger.error(f'[Restart] The restart manager stopped: {e}')
            logger.exception(e)
        finally:
            self.nursery = None

    def enter_init(self):
        """
        Enter the init slot (the process startup)

        Only the startup flow may leave it: a user flow claimed there would
        refuse the startup and leave the process without its update checks.
        """
        if self.current is None:
            self.claim(InitFlow())

    def abandon_startup(self):
        """
        Release the init slot when the startup flow could not start

        The backend then runs without a flow: the configs are startable by hand
        and the next restart / update request claims the slot normally.
        """
        if self.current is not None and self.current.name == INIT_FLOW:
            self.current = None
            self.publish_view()
            logger.warning(
                '[Restart] The startup flow is not running, the backend has no '
                'maintenance flow'
            )

    # ------------------------------------------------------------------
    # Entries (trio thread: the judgment and the claim are one sync section)
    # The user entries are named after the rpc that drives them; the internal
    # ones (the lifespan, the daily task) carry the request_ prefix.
    # ------------------------------------------------------------------

    def request_startup(self) -> Flow:
        """
        Claim the slot for the startup flow (the lifespan entry)

        The only transition out of the init slot; a startup requested while
        anything else owns the backend is an internal error (``run()`` is the
        only caller and it does that before every other entry).

        Returns:
            Flow: The claimed flow

        Raises:
            FlowRefused: When the slot is not in init
        """
        current = self.current
        if current is not None and not (current.name == INIT_FLOW):
            raise FlowRefused(
                f'The backend is already running the "{current.name}" flow'
            )
        return self._claim(FlowStartup)

    def restart(self) -> Flow:
        """
        Claim the slot for a user restart

        Returns:
            Flow: The claimed flow

        Raises:
            FlowRefused: When another flow owns the backend (the message is the
                user-facing reason of FlowRestart.REFUSALS), or when the backend
                runs without a supervisor: only a supervisor spawns the new
                process, refusing the request up front is the accurate answer
                (the alternative is failing at the handover)
        """
        if not has_supervisor():
            raise FlowRefused(
                'The backend runs without a supervisor: it cannot restart itself'
            )
        return self._claim(FlowRestart)

    def update_apply(self) -> Flow:
        """
        Claim the slot for a user update

        The caller checks the precondition (at least one mod has an update, the
        Update topic knows it) before requesting; the manager owns the slot
        only.

        Returns:
            Flow: The claimed flow

        Raises:
            FlowRefused: When another flow owns the backend (the message is the
                user-facing reason of FlowUpdate.REFUSALS)
        """
        return self._claim(FlowUpdate)

    def request_daily(self) -> 'Optional[Flow]':
        """
        Claim the slot for the daily maintenance (the daily task entry)

        The daily action is a *due* decision (see
        ``oas.backend.app.restart.daily``): an occupied slot is not an error.

        Returns:
            Flow | None: The claimed flow, None when the action is skipped --
                restart / update in flight upgrade themselves before their
                handover, a startup (or the init slot) serves the crossing
                itself (the process just started: its young workers are the
                restart half of the daily action), a daily flow already runs
        """
        current = self.current
        if current is None:
            if self.nursery is None:
                # the process is not serving flows yet (the next evaluation
                # retries): nothing may be claimed before the startup flow
                return None
            return self._claim(FlowDaily)
        if current.name in (INIT_FLOW, 'startup'):
            # the process just started: its startup full update and its young
            # workers already serve both purposes of the daily action. The
            # crossing is served only when one was detected: the process may
            # have started before the target and be evaluated after it
            if self.daily.mark_done():
                logger.info(
                    '[Restart] Daily action skipped: the backend is starting up'
                )
        return None

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel_restart(self):
        """
        Cancel the restart flow in flight (the wait for the workers to stop)

        The flow object owns the cancellation: it decides whether the cancel is
        still accepted (the window is open, the flow was not upgraded) and
        interrupts its own cancellable phase. The wrap-up (restore the queue,
        restart the checks) belongs to the flow task, which observes the
        cancellation at its next checkpoint.

        Raises:
            FlowRefused: When no restart is in flight, when it was already
                cancelled, or when it is past its point of no return
        """
        await self._require_flow(FlowRestart).cancel()

    async def cancel_apply(self):
        """
        Cancel the update flow in flight (the stop and the download phase)

        Past the point of no return (the first mod is being written to disk) and
        after a daily upgrade the cancel is refused: the file replacement must
        not be interrupted half way, its own handover ends the flow.

        Raises:
            FlowRefused: When no update is in flight, when it was already
                cancelled, or when it is past its point of no return
        """
        await self._require_flow(FlowUpdate).cancel()

    # ------------------------------------------------------------------
    # Tasks of the manager nursery
    # ------------------------------------------------------------------

    def spawn(self, async_fn, *args):
        """
        Run a task in the manager nursery (the flows outside the slot)

        The resume queue is the task that matters here: a flow spawns it before
        releasing the slot, so the drain of the queue is not part of the flow
        (a new flow may take the slot over while it still runs).

        Args:
            async_fn (Callable): Coroutine function to run
            args: Arguments of the call

        Raises:
            RuntimeError: When the manager does not run
        """
        tg = self.nursery
        if tg is None:
            raise RuntimeError(
                'The restart manager does not run (run() was not started)'
            )
        tg.start_soon(async_fn, *args)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _claim(self, flow_cls: 'type[Flow]') -> Flow:
        """
        Take the slot for a flow and spawn its body (one synchronous section)

        Args:
            flow_cls (type[Flow]): The class of the flow the entry claims the
                slot with (the class carries the flow name and the refusal of
                its request)

        Returns:
            Flow: The claimed flow

        Raises:
            FlowRefused: When the slot is occupied, or when the backend does not
                serve flows yet (no run())
        """
        current = self.current
        if current is not None:
            # the only transition out of init is the startup flow
            if not (current.name == INIT_FLOW and flow_cls is FlowStartup):
                # the user entries answer with a message of their own; the
                # internal ones carry no refusal table: their request landing on
                # a busy slot is a bug, not a user action
                message = flow_cls.REFUSALS.get(current.name, None)
                if message is None:
                    message = (
                        f'The backend is already running the "{current.name}" flow'
                    )
                raise FlowRefused(message)
        tg = self.nursery
        if tg is None:
            if not flow_cls.REFUSALS:
                raise RuntimeError(
                    'The restart manager does not run (run() was not started)'
                )
            # the process is not serving flows yet (run() did not run): the
            # user entry answers like any startup window
            raise FlowRefused(STARTING_UP)
        flow = flow_cls(self)
        self.claim(flow)
        tg.start_soon(self._run_flow, flow)
        return flow

    async def _run_flow(self, flow: Flow):
        """
        Run the body of a flow under the slot, whatever happens

        The task boundary is the last line of defence of the backend: the
        nursery is the manager's own, an escaped error would end the flows for
        the rest of the process (the lifespan keeps running). The wrap-up of a
        failure (workers, checks, queue) belongs to the flow body, which runs it
        before propagating; a failure reaching here is reported and releases
        the slot, an accepted cancel (``FlowCancelled``) is an expected end.

        The resume queue is spawned here, after the slot was released: the
        queue drains the starts queued while the flow owned the backend, and
        it reads them when no flow owns the backend any more -- a start
        accepted while the flow ran is in that read, a start accepted after
        the release is started directly (it is only accepted as a queued resume
        while the slot is owned, see ``worker_start``). Spawning the queue from
        the flow body would leave the read before the release: a start
        accepted in between would wait for a drainer that never comes.
        The frozen state (a published handover) and the shutdown (the nursery
        field is cleared by then) skip the queue: the process is being
        replaced or going down, its queued starts belong to it.

        Args:
            flow (Flow): The flow to run
        """
        with self.slot(flow):
            try:
                await flow.run()
            except FlowCancelled as e:
                # the flow was cancelled (or force-restarted) inside its
                # cancellable window: it wrapped up on its own way out, the
                # slot is released and the next request is served as usual
                logger.info(f'[Restart] {e}')
            except anyio.get_cancelled_exc_class():
                # the process is going down (the manager nursery was cancelled)
                raise
            except Exception as e:
                logger.error(f'[Restart] Flow "{flow.name}" failed: {e}')
                logger.exception(e)
        if not self.frozen and self.nursery is not None:
            # the slot is free, no handover published anything and the manager
            # still serves tasks: drain what was queued while the flow owned the
            # backend (the release and this check are one synchronous section:
            # no other flow ran in between). Nothing is drained at shutdown:
            # the process is going down, its queued starts belong to it
            self.spawn(self.resume_queue)

    def _require_flow(self, flow_cls: 'type[Flow]') -> Flow:
        """
        The flow in flight of that class (the cancel entry)

        Args:
            flow_cls (type[Flow]): The class the cancel addresses

        Returns:
            Flow: The flow to cancel

        Raises:
            FlowRefused: When no flow of that class is in flight (the flow
                itself answers why its cancel is refused otherwise, see
                ``Flow.cancel()``)
        """
        flow = self.current
        if flow is None or not isinstance(flow, flow_cls):
            raise FlowRefused(f'No {flow_cls.name} is in progress')
        return flow


# The process-wide manager, run by the lifespan
RESTART_MANAGER = RestartManager()
