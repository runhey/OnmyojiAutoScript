"""
Ported verbatim from ``alasio/backend/app/restart/daily.py``.

Deviations from upstream:

- the import rewrites: ``alasio.`` -> ``oas.`` on the five ``alasio.`` import
  lines other than the one ADAPTATION B below replaces (the three module-level
  ones -- ``oas.base.servertime``, ``oas.ext.cache``, ``oas.logger`` -- and the
  two local ones inside ``DailyState.run`` --
  ``oas.backend.app.restart.restart_manager``,
  ``oas.backend.mpipe.mpipe_backend``), plus the two prose occurrences of
  ``alasio.`` in the docstrings below (the port checker maps ``alasio.``
  throughout);
- trio -> anyio, in code only: ``import trio`` -> ``import anyio`` and
  ``trio.sleep`` -> ``anyio.sleep`` (one call, the schedule wake). No other trio
  construct appears in the file: no Event / Lock / move_on_after / fail_after /
  CancelScope / nursery / to_thread / current_time / sleep_forever, so no other
  rewrite applies; the ``trio`` wording of the upstream comments and docstrings
  is left intact;
- ADAPTATION A -- ``parse_server_update``: the upstream import
  ``from alasio.base.servertime import parse_server_update`` becomes
  ``from oas.base.servertime import parse_server_update`` (the module moved to
  ``oas/base/servertime.py``, same API and same function);
- ADAPTATION B -- the deploy settings read in ``scheduled_restart_time``: OAS has
  no ``oas/deploy/config/model.py``, so the upstream local import of
  ``DeployConfig`` and the ``DeployConfig().config.data.Update.AutoRestartTime``
  read are replaced by the local import of ``SettingsRuntime`` and the
  ``SettingsRuntime().data.update.auto_restart_time`` read, plus the ``"HH:MM"``
  formatting line. Upstream stores this field as a ``"HH:MM"`` string in
  ``deploy.yaml`` and parses it with ``parse_restart_time``; the target's
  ``UpdateGroup.auto_restart_time`` is already a validated ``Time`` (a
  ``datetime.time`` subclass) in ``config/deploy.json``, so the port formats it
  back to the ``"HH:MM"`` string upstream's ``parse_restart_time`` expects. The
  two comment lines above the import are adapted with it; the rest of the
  function, ``parse_restart_time`` included, is unchanged (the ``value`` line
  above is over the line limit, so ``ruff format`` wraps it into the
  parenthesized conditional);
- no ``alasio_lang``, ``alasio_token`` or ``Alasio`` spelling occurs upstream, so
  none is renamed.

No other deviation: apart from the items above the file is byte-identical to the
mapped upstream after ``ruff format``, which leaves this file unchanged.
"""

"""
Daily maintenance: the crossing of the configured restart time, and its task

The daily action exists for two reasons: check every mod for updates and
restart the workers before a mod that leaks memory can grow for a whole day.
Every restart of the backend (a user restart, an update, a daily one) already
serves both -- the new process checks every mod at startup and the workers are
young again -- so the daily action is a *due* decision, not a scheduled
command:

- a process that starts after the crossing of the target time has just checked
  every mod and its workers have no accumulated runtime: the day is served by
  the startup itself (the crossings before a process started belong to the
  past, see DailyState.observe);
- a process alive when the clock crosses the target runs the daily flow (stop
  the workers, full update, handover), at the crossing or at the next
  observation (a suspend across it);
- a flow (restart / update) in flight at the crossing is upgraded into the
  daily maintenance before its handover instead of starting a second one;
- the clock walked backwards crosses nothing; when it flows forward again and
  crosses the target, that is a crossing again -- even when the same target
  instant was served before (a service is one restart, the second traversal
  owes another one).

This module owns the bookkeeping of that decision and the task that drives it:
the crossing cursor, the crossing waiting to be served, the completion time of
the last full update of this process (the resume record carries it to the next
process). Deliberately light apart from trio and the logger: the manager, the
step layer, the flows and the lifespan import it.

The clock of this module is the **local wall clock** (``datetime.now()``): the
daily action restarts the backend in the local small hours, when the user is
least likely to be playing, so the target follows the user's local time --
including DST shifts and a manually changed clock, which only move when the
action happens (the task observes the clock on every wake). Durations that
compare one instant of this process with another one (the retry interval of an
unserved crossing) do not use this clock: they use ``time.monotonic()``, a jump
of the wall clock must not change them.

Without a supervisor the backend cannot replace itself (no parent process to
spawn the new one, see ``oas.backend.mpipe.mpipe_backend``): the daily
action and the mod updates are disabled then, the task does not start at all.
"""

import datetime
import time

import anyio

from oas.base.servertime import parse_server_update
from oas.ext.cache import cached_property
from oas.logger import logger

# Re-evaluation cap of the sleep: the next wake is the sooner of the remaining
# delay to the target and this cap, so a clock jump / DST shift / a suspend
# crossing the target is judged within it instead of after a full day
SCHEDULE_WAKE_CAP = 60.0
# Seconds between two claims of a flow for a crossing that is not served yet (a
# flow that failed before its handover): a claim stops every worker and runs a
# full update, a failed one must not be repeated on every wake
RETRY_INTERVAL = 600.0
# Reminder interval of the retry log
RETRY_LOG_INTERVAL = 60.0 * 60.0


class DailyState:
    """
    The daily bookkeeping of one backend process, and its schedule task

    Attributes (read-only for the outside):
        target (tuple[int, int] | None): (hour, minute) of the daily action,
            read once from the deploy config (a changed config takes effect
            with the next restart); None when the config disables it
        seen (datetime.datetime): The local wall clock of the last observation;
            at construction it is the boundary of this process -- the crossings
            at or before it belong to the past and are never detected
        pending (datetime.datetime | None): The daily target instant of the
            crossing detected and not served yet, None when there is none. A
            clock rolled back below it drops it (the action is due again when
            the clock crosses the target another time)
        updated_all_at (float): Completion time (unix timestamp) of the last
            full update of THIS process, 0 when it ran none
    """

    def __init__(self):
        # the boundary of the process and the cursor every observation compares
        # against
        self.seen = datetime.datetime.now()
        self.pending = None
        self.updated_all_at = 0.0

    @cached_property
    def target(self):
        """
        (hour, minute) of the daily action, read once from the deploy config

        Returns:
            tuple[int, int] | None: The time, None when the config disables the
                daily action (or holds an invalid value: the reason is logged
                once, a typo must not restart the backend daily at an arbitrary
                time)
        """
        return scheduled_restart_time()

    def reset(self):
        """
        Return to the initial state (tests: a fresh process has fresh state)

        The cached target is dropped as well: a test that patched the config
        reader must not leak its target into the next one.
        """
        cached_property.pop(self, 'target')
        self.__init__()

    # ------------------------------------------------------------------
    # The crossing of the daily target
    # ------------------------------------------------------------------

    def observe(self):
        """
        Read the wall clock and detect the crossing it just made

        Every judgment of this class calls this first. A crossing is the clock
        walking from before a daily target to at or after it: the comparison is
        the previous observation (``seen``), so a rollback crosses nothing (the
        interval backwards is empty) and it never invents a crossing, while the
        same stretch of wall clock walked a second time crosses the target
        again -- a crossing again, even when that target instant was served
        before.

        One traversal detects the crossing once: the observation advances
        ``seen`` past the target it just crossed, so the crossing is not
        re-detected while it waits to be served. A clock that walks back below
        the target drops the crossing it had detected: the rollback is not a
        crossing (nothing is served for it) and the service it undid is not
        owed -- the action is due again when the clock crosses the target
        another time.
        """
        now = datetime.datetime.now()
        target = self.target
        if target is not None:
            crossed = last_target(now, target)
            if crossed > self.seen:
                # the clock walked over the target: a crossing
                self.pending = crossed
            elif self.pending is not None and crossed < self.pending:
                # the clock walked back below the crossing it had reached: the
                # rollback crosses nothing, and the owed service is dropped with
                # it (the next traversal of the target owes it again)
                self.pending = None
        self.seen = now

    def is_due(self) -> bool:
        """
        Whether a crossing was detected and is not served yet (the trigger)

        Returns:
            bool: True when the daily action must run
        """
        self.observe()
        return self.pending is not None

    def mark_done(self) -> bool:
        """
        Serve the pending crossing

        The observation runs first: the traversal that crossed the target is
        not detected again. A service that does not hand the process over (the
        startup of a process that started before the target, a flow in flight
        covering the crossing itself) must not be repeated.

        Returns:
            bool: True when there was a crossing to serve
        """
        self.observe()
        if self.pending is None:
            return False
        self.pending = None
        return True

    def covered_by(self, ts) -> bool:
        """
        Whether a full update completed at ``ts`` covers the crossing of now

        Stateless: compared against the most recent target instant at or
        before now, so the answer is the same for the handover mark (the full
        update of this process ran after the crossing), the guard of a daily
        upgrade (the full update of this process is not repeated) and the
        startup (the previous process checked after the crossing).

        Args:
            ts (float): Completion time of the full update (unix timestamp),
                0 when there was none

        Returns:
            bool: True when the update finished at or after the crossing
        """
        target = self.target
        if not ts or target is None:
            return False
        return datetime.datetime.fromtimestamp(ts) >= last_target(
            datetime.datetime.now(), target
        )

    def mark_done_if_covered(self) -> bool:
        """
        Serve the pending crossing when the last full update of this process
        covers it (the handover mark, the startup full update)

        Returns:
            bool: True when a crossing was served
        """
        if not self.covered_by(self.updated_all_at):
            return False
        return self.mark_done()

    def note_full_update(self, ts=None):
        """
        Record that a full update finished (the apply steps call this)

        The value is an epoch (``time.time()``): it travels to the next process
        in the resume record, and an epoch is the only instant two processes
        share -- the local naive calendar of this module is not one (see the
        module docstring).

        Args:
            ts (float): Completion time (time.time()), defaults to now; a
                startup that skips its full update records the completion time
                of the process it replaces -- the check it relies on
        """
        self.updated_all_at = ts if ts is not None else time.time()

    # ------------------------------------------------------------------
    # The schedule task
    # ------------------------------------------------------------------

    async def run(self, manager=None):
        """
        Lifespan background task: wake up, judge the crossing, claim the daily flow

        One task per backend process. The target time is read once (the deploy
        config; changing it takes effect with the next restart); with the daily
        action disabled, or without a supervisor (the backend cannot replace
        itself then), the task ends right away. It wakes in bounded steps and
        observes the wall clock on every wake, so a clock jump / DST shift / a
        suspend crossing the target is judged shortly after instead of a day
        later.

        One evaluation: the crossing of the clock is served -> nothing;
        otherwise the manager decides -- an idle slot claims the daily flow (it
        stops the workers, runs the full update and hands the process over), a
        restart / update flow in flight covers the crossing itself (it upgrades
        into the daily maintenance before its handover), a backend that is
        starting up has just checked every mod and has no accumulated runtime
        (it serves the crossing itself). The task never interrupts a flow: it
        only re-evaluates.

        A crossing that could not be served (a flow that failed before its
        handover) is retried: the claim is throttled by RETRY_INTERVAL (it is
        expensive) and the retry log by RETRY_LOG_INTERVAL.

        Args:
            manager (RestartManager): The restart manager, defaults to the
                process singleton
        """
        if manager is None:
            # local import: the manager imports this module (its bookkeeping), a
            # module level import would be circular
            from oas.backend.app.restart.restart_manager import RESTART_MANAGER

            manager = RESTART_MANAGER
        target = self.target
        if target is None:
            return
        # local import: this module stays light (the mpipe module is a leaf, but
        # the import is only needed by the task)
        from oas.backend.mpipe.mpipe_backend import has_supervisor

        if not has_supervisor():
            # the backend cannot replace itself without a parent process (see
            # MPipeBackend): the daily restart and the mod updates are disabled,
            # the schedule has nothing to do
            logger.info(
                '[Schedule] The backend runs without a supervisor: '
                'the daily maintenance is disabled'
            )
            return
        logger.info(f'[Schedule] Daily maintenance at {target[0]:02d}:{target[1]:02d}')
        last_attempt = None
        last_retry_log = 0.0
        while True:
            if not has_supervisor():
                # the supervisor died while the backend ran (the recv loop
                # cleared the pipe): the process is shutting down, the schedule
                # stops claiming
                return
            if self.is_due():
                if (
                    last_attempt is None
                    or time.monotonic() - last_attempt >= RETRY_INTERVAL
                ):
                    last_attempt = time.monotonic()
                    try:
                        flow = manager.request_daily()
                    except Exception as e:
                        # a failed request must never kill the lifespan task
                        logger.error(
                            f'[Schedule] Failed to start the daily maintenance: {e}'
                        )
                    else:
                        if flow is not None:
                            logger.info(
                                f'[Schedule] Daily maintenance started by the schedule '
                                f'("{flow.name}" flow)'
                            )
                elif time.monotonic() - last_retry_log >= RETRY_LOG_INTERVAL:
                    last_retry_log = time.monotonic()
                    logger.info(
                        '[Schedule] The daily action of the crossed target is not served '
                        'yet, retrying'
                    )
            else:
                last_attempt = None
            # sleep to the next occurrence, in bounded steps: an idle loop wakes
            # exactly at the target, a clock jump / a suspend is judged within
            # SCHEDULE_WAKE_CAP (a rollback needs no special case: it simply
            # crosses nothing)
            await anyio.sleep(
                min(
                    next_restart_delay(datetime.datetime.now(), target),
                    SCHEDULE_WAKE_CAP,
                )
            )


# =============================================================================
# The configured time
# =============================================================================


def parse_restart_time(value):
    """
    Parse the AutoRestartTime config value into (hour, minute)

    The time forms are the server_update forms of
    :func:`oas.base.servertime.parse_server_update` ("HH:MM", "H:MM" or a
    bare hour, which means minute 0); the config field additionally pins the
    stored value to the strict HH:MM pattern.

    Args:
        value (str | None): Configured time; None or a blank value disables
            the daily action

    Returns:
        tuple[int, int] | None: (hour, minute), or None when disabled

    Raises:
        ValueError: When the value is not a valid time, or carries a weekday /
            monthday restriction (the daily action is daily, a
            weekday-restricted time is a different feature)
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        condition = parse_server_update(text)
    except ValueError as e:
        raise ValueError(f'Invalid restart time "{value}": {e}') from None
    if condition.weekday is not None or condition.monthday is not None:
        raise ValueError(
            f'Invalid restart time "{value}": only a daily HH:MM time is supported'
        )
    return condition.hour, condition.minute or 0


def last_target(now, hour_minute):
    """
    The most recent occurrence of `hour_minute` at or before `now` (local time)

    The instant a crossing walks over (see DailyState.observe). Computed from
    the local datetime itself, like `next_restart_delay`, so the daily rhythm
    follows the local wall clock through DST shifts.

    Args:
        now (datetime.datetime): The local time of the observation
        hour_minute (tuple[int, int]): (hour, minute) of the daily target

    Returns:
        datetime.datetime: The occurrence at or before `now` (today or yesterday)
    """
    hour, minute = hour_minute
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target > now:
        target -= datetime.timedelta(days=1)
    return target


def next_restart_delay(now, hour_minute):
    """
    Seconds from `now` to the next occurrence of `hour_minute` in local time

    Computed numerically from `now` (local datetime), so the local time of the
    target is the constant and DST-shifted days are handled by the arithmetic
    itself. The occurrence exactly at `now` counts as passed: this helper only
    says how long to sleep towards the next crossing, whether a crossing is due
    is decided by DailyState (its cursor), never here.

    Args:
        now (datetime.datetime): Current local time
        hour_minute (tuple[int, int]): (hour, minute) of the daily target

    Returns:
        float: Seconds to the next occurrence, always within (0, 86400]
    """
    hour, minute = hour_minute
    # seconds since midnight on both sides: one unit, no mixed arithmetic
    now_seconds = (now.hour * 60 + now.minute) * 60 + now.second
    target_seconds = (hour * 60 + minute) * 60
    if target_seconds > now_seconds:
        # later today
        return target_seconds - now_seconds
    # passed (or exactly now, see above): the remainder of today plus the
    # whole of tomorrow up to the target
    return 86400 - now_seconds + target_seconds


def scheduled_restart_time():
    """
    Read the configured daily time (once per process)

    Returns:
        tuple[int, int] | None: (hour, minute), or None when disabled or
            invalid (a bad value is reported once at startup and the daily task
            stays off: a typo must not restart the backend daily at an
            arbitrary time)
    """
    # local import: the deploy settings module is only safe to import after
    # the project root is set (see oas.backend.app.app)
    from oas.deploy.settings.runtime import SettingsRuntime

    auto_restart_time = SettingsRuntime().data.update.auto_restart_time
    value = (
        None
        if auto_restart_time is None
        else f'{auto_restart_time.hour:02d}:{auto_restart_time.minute:02d}'
    )
    try:
        return parse_restart_time(value)
    except ValueError as e:
        logger.error(f'[Schedule] {e}, the daily maintenance is disabled')
        return None


# The process-wide daily bookkeeping
DAILY = DailyState()
