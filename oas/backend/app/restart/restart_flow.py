"""
Ported verbatim from ``alasio/backend/app/restart/restart_flow.py``.

Deviations from upstream:

- the import rewrites only: ``alasio.`` -> ``oas.`` on the five import lines
  (``oas.backend.app.restart.restart_base``,
  ``oas.backend.app.restart.restart_step``,
  ``oas.backend.app.restart.update_check``,
  ``oas.backend.mpipe.mpipe_backend`` and ``oas.logger``) plus the single
  prose occurrence of ``alasio.backend.app.restart.restart_step`` in the
  module docstring below (the port checker maps ``alasio.`` throughout);
- no trio -> anyio rewrite applies: the file contains no trio construct at all
  (no ``import trio``, no trio token, Event, Lock, move_on_after, fail_after,
  CancelScope or nursery), so there is nothing to translate;
- no ``alasio_lang``, ``alasio_token`` or ``Alasio`` spelling occurs upstream,
  so none is renamed.

Formatting, identically imposed by ``ruff format`` on the mapped upstream and
on this file: the blank line after every docstring (module and class), the wrap
of the long ``logger.*`` call arguments and of the two
``mark_restart_required`` calls, and ``"List[str]"`` -> ``'List[str]'``.

No other deviation: every other line is byte-identical to the mapped upstream.
"""

"""
The four maintenance flows of the backend

Every flow is a class: the manager creates its object when the flow is claimed
and runs it as the body of the flow task (``Flow.run()``). The entries name the
class itself (``restart_manager``): the class carries the flow name used by the
view and the log lines, and the ``REFUSALS`` table the two user requests answer
with. The object owns the state of the flow and, above all, the *cancellable
part* of its body: the body declares it itself with ``with
self.cancel_window(past_reason):`` -- inside that block a cancel is accepted,
leaving it (or closing it early) makes the flow irreversible. A cancelled flow
never runs the code after the window (the window raises ``FlowCancelled``
there), so the tail of a body -- the handover -- is only reached when no cancel
was accepted. The manager asks the object to cancel (``Flow.cancel()``) instead
of binding a cancel scope of its own.

The four flows:

- ``startup``: the process startup (consume the resume intent, full update when
  the previous process did not just run one, start the checks, release the
  resume queue). No cancellable phase;
- ``restart``: a user restart (pause the checks, stop the workers, hand over);
- ``update``: a user update (pause the checks, pre-check the available mods,
  stop the workers, apply the deploy jobs, hand over);
- ``daily``: the daily maintenance (pause the checks, stop the workers, full
  update, hand over). No cancellable phase.

The bodies drive the single steps of the manager
(``oas.backend.app.restart.restart_step``); every flow that stops something
releases it on its way out when it does not hand over (``wrap_up``): the checks
it paused, the workers it stopped, the resume queue. A flow that hands over
does nothing else -- the process is replaced and the new one resumes what the
resume file recorded.
"""

import time
from typing import List

from oas.backend.app.restart.restart_base import INIT_FLOW, STARTING_UP, Flow
from oas.backend.app.restart.restart_step import HandoverFailed
from oas.backend.app.restart.update_check import CHECK_INTERVAL
from oas.backend.mpipe.mpipe_backend import has_supervisor
from oas.logger import logger


class FlowStartup(Flow):
    """
    The process startup flow (the run() entry of the manager)

    1. consume the resume file of the previous process (its configs are queued,
       the stale leftovers of dead sessions are cleaned);
    2. a full update when the process this one replaces did not just run one:
       the record carries the completion time of its last full update, and the
       check is skipped while that is younger than ``CHECK_INTERVAL`` (the
       daily restart checked right before its handover, the convergence
       handover follows the update it applied; the window of a startup is the
       check rhythm of a sequence). When the full update changed
       real files the flow hands the process over -- the new process sees the
       fresh check in the record and skips its own full update, so the chain
       converges in one update and one restart. The flow runs **no full update
       at all** while the mod updates are off (Deploy.Update.AutoUpdate =
       false: every managed mod is 'disabled') or while the backend has no live
       supervisor (an applied update could only take effect in a new process,
       and no parent process can spawn one);
    3. the daily crossing: the startup full update of step 2 serves it when it
       finished after the target moment (``mark_done_if_covered``); a crossing
       this process lived through is otherwise served by the daily flow, and
       the crossings before this process started belong to the past -- the
       startup itself is their restart half;
    4. start the check sequences (the first check waits the standard spread: the
       full update just checked everything). A disabled mod has no sequence:
       nothing is checked while the mod updates are off;
    5. release the slot: the manager drains the resume queue of the configs
       marked in step 1 once no flow owns the backend.

    No cancellable phase: the process has no checks yet, a cancel would leave
    the backend without them.
    """

    name = 'startup'

    async def run(self):
        manager = self.manager
        record = await manager.read_resume_intent()
        manager.update_check.bind()
        manager.update_check.set_initial_states()
        changed = []
        try:
            if not manager.update_check.auto:
                # the mod updates are off for this process (Deploy.Update.AutoUpdate
                # = false, every managed mod is 'disabled'): the startup runs no
                # full update at all -- nothing is checked, nothing is applied and
                # the process is never handed over for an update. A crossing this
                # process lived through is served by the daily flow (a restart
                # only while the switch is off); the crossings before it started
                # belong to the past, the startup is their restart half
                logger.info(
                    '[Restart] The mod updates are disabled: the startup runs no full update'
                )
            elif not has_supervisor():
                # the backend cannot replace itself without a parent process: an
                # applied update could only take effect in a new process (the mod
                # packages live in this one), so nothing is checked and nothing is
                # applied
                logger.info(
                    '[Restart] The backend runs without a supervisor: '
                    'the startup runs no full update'
                )
            elif (
                record is not None
                and record.updated_all_at
                and time.time() - record.updated_all_at <= CHECK_INTERVAL
            ):
                # the process this one replaces checked a moment ago (the daily
                # restart checked right before its handover, a convergence handover
                # follows the update it applied): a check right now would only
                # repeat it. The completion time is carried into this process so the
                # window is always measured from the last real check. The age is a
                # wall-clock duration between two processes (the record carries an
                # epoch, the only instant the two share): a clock jump makes it
                # wrong once -- a forward jump checks a little early, a backward one
                # makes the age negative and skips the check, both harmless
                manager.daily.note_full_update(record.updated_all_at)
                logger.info(
                    f'[Restart] The previous process checked less than '
                    f'{CHECK_INTERVAL:.0f}s ago: the startup runs no full update'
                )
            else:
                # the record is missing, or its check is older than the window: the
                # tree is converged now (a record that only says "someone checked
                # hours ago" is no answer about the tree as it is now)
                changed = await manager.full_update(self)
                if manager.daily.mark_done_if_covered():
                    logger.info(
                        '[Restart] The crossing of the daily target is served by the '
                        'startup full update'
                    )
            if changed:
                # the files just applied need the new process: hand over, the new
                # process sees the fresh check in the record and starts its own
                # checks directly. The resume list is read inside the frozen
                # section of the handover: every start accepted during the
                # startup is in it
                await manager.handover(self, 'startup convergence')
                return
            manager.update_check.start()
            # the flow ends here: the manager drains the resume queue of the
            # configs marked in step 1 once the slot is released, so the starts
            # queued during the startup are read by it (a user flow may take the
            # backend over while the queue still drains, the queue stops there)
        except HandoverFailed as e:
            logger.error(
                f'[Restart] The startup convergence could not hand the backend over: {e}'
            )
            manager.update_check.mark_restart_required(changed, str(e))
            await manager.wrap_up(self)
        except Exception as e:
            logger.error(f'[Restart] The startup flow failed: {e}')
            logger.exception(e)
            await manager.wrap_up(self)


class FlowRestart(Flow):
    """
    A user restart: pause the checks, stop every worker gracefully, cross the
    daily target, hand the process over

    The wait for the workers to stop is the cancellable phase (the long part);
    an upgrade into the daily maintenance closes the window. A cancel accepted
    there ends the flow before the handover: the window raises ``FlowCancelled``
    and the wrap-up resumes the workers it stopped and restores the checks.
    """

    name = 'restart'
    PARK_STATE = 'restarting'
    # Why this request is refused, by the name of the flow owning the backend
    # when it lands (the startup window refuses a request of the process
    # startup alike)
    REFUSALS = {
        INIT_FLOW: STARTING_UP,
        'startup': STARTING_UP,
        'restart': 'A restart is already in progress',
        'update': 'An update is in progress; the backend restarts by itself when it finishes',
        'daily': 'The daily maintenance is in progress (it includes the restart)',
    }

    async def run(self):
        manager = self.manager
        resume_list = []
        handed_over = False
        try:
            with self.cancel_window('the handover started'):
                manager.update_check.pause()
                success, resume_list = await manager.stop_all(self)
                if not success:
                    # the wait was cancelled (or the workers could not be
                    # stopped): the window answers the cancel with
                    # FlowCancelled on the way out, the wrap-up below resumes
                    # the workers it stopped and restores the checks
                    return
                await manager.maybe_upgrade_to_daily(self)
            await manager.handover(self, 'user request', resume_list)
            handed_over = True
        except HandoverFailed as e:
            logger.error(f'[Restart] The restart could not hand the backend over: {e}')
        finally:
            if not handed_over:
                await manager.wrap_up(self, resume_list)


class FlowUpdate(Flow):
    """
    A user update: pause the checks, pre-check the available mods, stop the
    workers, apply the deploy jobs, hand the process over

    The user entry is a single one (there is no per-mod update button): the mods
    with an available update at the moment of the click are the scope of this
    flow. An in-flight job that finds a mod already up to date (another flow
    applied it meanwhile) keeps its state and skips it, a failed mod is
    isolated, the other mods and the handover are not affected.

    The dependencies of every applied mod are reconciled by ``update_mods``
    right after its tree: the pins of the new requirements file are installed,
    the declared ones the folder already satisfies are verified and repaired --
    a dependency that has no update is validated all the same. A failed tree
    stops before its dependency step, so its packdep snapshot is never used; a
    failed dependency step marks the mod 'error' as well, because the update is
    incomplete even when its tree changed. Any failed mod keeps the backend
    running: the flow wraps up and resumes every config it stopped, including
    the configs of the failed mod, because an update failure does not prove
    that their files are unusable -- a broken one reports its own error when it
    starts. The daily upgrade is the exception: it turns the request into the
    daily maintenance, whose restart is not blocked by an update failure.

    The cancellable phase is the stop and the download: the apply step closes
    the window at the first real write (the deploy jobs report their 'updating'
    phase there), a daily upgrade closes it too. A cancel accepted before that
    point ends the flow before the handover: the window raises
    ``FlowCancelled`` and the wrap-up resumes the workers it stopped and
    restores the checks (nothing on disk changed yet).
    """

    name = 'update'
    # Why this request is refused, by the name of the flow owning the backend
    # when it lands (the startup window refuses a request of the process
    # startup alike)
    REFUSALS = {
        INIT_FLOW: STARTING_UP,
        'startup': STARTING_UP,
        'update': 'An update is already in progress',
        'restart': 'A restart is in progress; the updates are checked and applied right after it',
        'daily': 'The daily maintenance is in progress (it includes the full update)',
    }

    async def run(self):
        manager = self.manager
        names = manager.update_check.available()
        resume_list = []
        changed = []
        handed_over = False
        try:
            with self.cancel_window('the mods are being written'):
                manager.update_check.pause()
                for name in names:
                    manager.update_check.set_state(name, 'queued')
                if names and await self._all_uptodate(names):
                    # the pre-check (read-only, nothing stopped yet): every mod
                    # of the scope is up to date now, the update is a no-op
                    logger.info(
                        '[Restart] The update is already applied, nothing to do'
                    )
                    return
                success, resume_list = await manager.stop_all(self)
                if not success:
                    return
                for name in names:
                    manager.update_check.set_state(name, 'stopping')
                result = await manager.update_mods(names, flow=self)
                changed = result.changed
                upgraded = await manager.maybe_upgrade_to_daily(self)
                if result.failed and not upgraded:
                    # The files of a failed mod may already be written, but a
                    # user update must not restart the backend into an
                    # incomplete environment. The flow wraps up below and the
                    # stopped configs are resumed: a file that still works is
                    # not taken away from its running state, and a broken one
                    # reports its own error when it starts.
                    logger.error(
                        f'[Update] The update failed for {result.failed}, '
                        'the backend keeps running'
                    )
                    return
            await manager.handover(self, 'update', resume_list)
            handed_over = True
        except HandoverFailed as e:
            logger.error(f'[Restart] The update could not hand the backend over: {e}')
            if changed:
                manager.update_check.mark_restart_required(
                    changed,
                    f'The update is applied, a backend restart is required: {e}',
                )
        finally:
            if not handed_over:
                await manager.wrap_up(self, resume_list)

    async def _all_uptodate(self, names: 'List[str]') -> bool:
        """
        The read-only pre-check of the update flow

        Every mod of the scope is checked (DeployJob.check(): the local ledger
        against the latest pack, no lock, nothing on disk) and its state is
        refreshed in passing; the flow only stops the workers when at least one
        mod still has an update.

        Args:
            names (List[str]): Mod names of the scope

        Returns:
            bool: True when every checked mod is up to date (a check that fails
                counts as "not up to date": a broken mirror must not turn the
                click into a no-op)
        """
        update_check = self.manager.update_check
        for name in names:
            mod = update_check.mods.get(name, None)
            if mod is None or mod.mirrors is None:
                continue
            try:
                job = await mod.job()
                check = await job.check()
            except Exception as e:
                logger.warning(f'[Update] The pre-check of "{name}" failed: {e}')
                return False
            if check.uptodate():
                update_check.set_state(name, 'uptodate')
            else:
                mod.set_state('available', current=check.local, latest=check.latest)
                return False
        return True


class FlowDaily(Flow):
    """
    The daily maintenance: pause the checks, stop the workers, run the full
    update of every mod, hand the process over

    No cancellable phase: the daily action is done in one go (the schedule would
    retrigger otherwise, with the workers already stopped), and an upgrade of a
    flow in flight (``maybe_upgrade_to_daily``) closes its window the same way.

    With the automatic mod updates off (Deploy.Update.AutoUpdate = false, every
    mod is 'disabled') the full update is empty and the daily maintenance of
    such a backend is a graceful restart -- its other purpose.
    """

    name = 'daily'

    async def run(self):
        manager = self.manager
        resume_list = []
        changed = []
        handed_over = False
        try:
            manager.update_check.pause()
            success, resume_list = await manager.stop_all(self)
            if not success:
                return
            changed = await manager.full_update(self)
            await manager.handover(self, 'daily', resume_list)
            handed_over = True
        except HandoverFailed as e:
            logger.error(
                f'[Restart] The daily maintenance could not hand the backend over: {e}'
            )
            if changed:
                manager.update_check.mark_restart_required(
                    changed,
                    f'The update is applied, a backend restart is required: {e}',
                )
        finally:
            if not handed_over:
                await manager.wrap_up(self, resume_list)
