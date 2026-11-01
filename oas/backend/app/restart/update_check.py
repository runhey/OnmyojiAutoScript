"""
API-compatible stand-in of the mod update check module.

Upstream this is ``alasio/backend/app/restart/update_check.py`` (988 lines:
``ModUpdateCheck`` and ``UpdateCheck``). The real job of the module -- check
the update source of every mounted mod, drive the Update topic the frontend
reads and run the check schedules -- needs the whole deploy stack:
``deploy/httpclient`` (2683 lines: the shared async client and the mirror
probe) and ``deploy/pack`` (5910 lines: the update server and the deploy job).
Neither is ported to OAS yet, so this file keeps upstream's module surface --
the same constants with the same values (the messages below are shown to the
user by the frontend, so they are verbatim), the same classes, the same
members in the same order with the same signatures and the same docstrings --
and empties every body that would do work: nothing here parses an update
source, builds an http client, contacts a mirror, builds a deploy job,
downloads a pack or installs anything, and no state is published to the Update
topic. Every emptied body logs one warning saying so; the few pure accessors
that are kept (``names`` / ``available`` / ``state_of`` / ``_resolve`` /
``interval`` / ``first_delay``) only read the empty state or compute a number,
and therefore answer the empty value too.

The consumers of the surface keep working:

- ``oas/backend/app/restart/restart_step.py`` imports ``UPDATE_CHECK`` /
  ``UpdateCheck`` and reads ``mods`` / ``auto`` / ``names()`` / ``client()``,
  drives ``set_state`` / ``release_states`` / ``restore`` / ``pause`` /
  ``mark_restart_required`` and the per-mod objects (``mirrors`` / ``job()`` /
  ``set_state``): every one of them sees "no mod is managed" and skips its real
  work (the guard reaches ``mod is None`` / ``mirrors is None`` first);
- a future port of ``alasio/backend/topic/update.py`` imports ``UPDATE_CHECK``
  (plus ``RESTART_MANAGER`` / ``FlowRefused``) and answers its RPCs through
  ``update_check(name)`` / ``cancel_check(name)`` / ``available()``;
- ``oas/backend/app/app.py`` starts ``UPDATE_CHECK.run`` from the lifespan: the
  stand-in opens no nursery, it only waits for the backend shutdown (see
  ``UpdateCheck.run``).

What differs observably from a real backend:

- no mod is ever bound (``bind`` is a stand-in) and ``push`` binds nothing, so
  the Update topic stays empty: the frontend sees no update state at all, i.e.
  each mod reports "no update source" (``UNMANAGED_MESSAGE`` is what a real
  unmanaged mod answers) and never an update;
- ``available()`` is always empty, so the update flow of the topic never has a
  mod to apply ("No update available") and no update is ever found, downloaded
  or installed;
- the five messages (``FRESH_MESSAGE`` / ``BUSY_MESSAGE`` /
  ``UNMANAGED_MESSAGE`` / ``DISABLED_MESSAGE`` / ``NO_SUPERVISOR_MESSAGE``) are
  kept for the frontend but are never produced: a manual check answers ''
  (nothing was checked) and a cancel answers False (nothing was in flight);
- no check sequence exists: no automatic check, no nursery, no lock, no cancel
  scope -- ``running`` is always False;
- ``client()`` answers None (see its docstring) and ``close()`` awaits nothing.

The states of one mod (Update topic):

    unmanaged / no-supervisor / disabled / idle / checking / uptodate / available / error

plus the states the apply steps set: 'queued', 'stopping', 'downloading',
'updating' and 'restart-required'.

Stand-in of the classification: a real module classifies every mod once at the
startup -- 'no-supervisor' when the backend runs without a live supervisor (only
a supervisor can spawn the new process that makes an applied update effective),
'unmanaged' when it declares no usable update source (the source is parsed
once), 'disabled' when the mod updates are off for this process (``auto``,
i.e. Deploy.Update.AutoUpdate = false), 'idle' otherwise, and none of those is
ever checked. The stand-in classifies nothing: it parses no source and reads no
schedule, so none of the states above is ever published -- the Update topic
stays empty.

Replacing this file with the real module is its own porting item: it needs
``deploy/httpclient`` and ``deploy/pack`` ported first.
"""

import random
from types import SimpleNamespace
from typing import Dict, List, Optional

import anyio

from oas.backend.mpipe.mpipe_backend import has_supervisor
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.logger import logger

# Seconds between two automatic checks of one running sequence. The first check
# of a sequence waits CHECK_INTERVAL to CHECK_INTERVAL * 2 (see
# UpdateCheck.first_delay), the following ones are CHECK_INTERVAL apart
CHECK_INTERVAL = 300.0
# A check is discarded when the last one finished less than this many seconds
# ago: the result of that check is the answer already
FRESH_WINDOW = 5.0
# The messages of a discarded check (the caller, the rpc layer, shows them to
# the user)
FRESH_MESSAGE = 'Just checked a moment ago'
BUSY_MESSAGE = 'A check is already in progress'
# The message of a check requested for a mod without a usable update source
# (the entries answer it instead of raising: a mod without a source is a normal
# state, the startup flow publishes it as 'unmanaged')
UNMANAGED_MESSAGE = 'The mod has no update source'
# The message of a check requested while the mod updates are off for this
# process (Deploy.Update.AutoUpdate = false): no mod is ever checked then (the
# entries answer it instead of raising: turning the updates off is a normal
# state, the startup flow publishes it as 'disabled')
DISABLED_MESSAGE = 'The mod updates are disabled'
# The message of a check requested for a mod of a backend running without a
# live supervisor: only a supervisor can spawn the new process that makes an
# applied update effective (this one has the mod packages imported already), so
# the updates are off -- no sequence, no manual check, no full update (the
# entries answer it instead of raising: running without a supervisor is a
# normal state, the startup flow publishes it as 'no-supervisor')
NO_SUPERVISOR_MESSAGE = 'The backend runs without a supervisor'
# The states the apply steps of a flow set on a mod while the flow runs
# ('queued' / 'stopping' / 'downloading'): they describe the flow in flight, not
# the update itself -- the wrap-up of a flow that does not hand over releases
# them back to 'available' (see UpdateCheck.release_states)
FLOW_STATES = ('queued', 'stopping', 'downloading')


class ModUpdateCheck:
    """
    The update check of one mounted mod: its state and its check sequence

    The state (``info``, the update source of the mod) and the sequence that
    refreshes it live in one class: the sequence calls back into the state it
    serves instead of a second object that owns the mod.

    The check of a mod is one operation with two entries and one lock:

    - ``run_check_loop()``: the automatic sequence, a task of the module
      nursery (started by ``start_check_loop``, dropped by
      ``stop_check_loop``): wait the spread (CHECK_INTERVAL to
      CHECK_INTERVAL * 2), check, wait CHECK_INTERVAL, check, ...;
    - ``update_check()``: the manual check (the user entry): the automatic
      sequence is interrupted, the check runs in the caller's task and the
      sequence starts over afterwards.

    Both run the real check (``_run_update_check``) under ``_check_lock`` and
    both discard it when the last check finished less than FRESH_WINDOW seconds
    ago. Two callers arriving together therefore leave exactly one check
    running: the loser is answered with FRESH_MESSAGE or BUSY_MESSAGE (the two
    checks before the lock only exist for those messages, the arbitration is
    the re-check inside the lock). ``cancel_check()`` interrupts the
    request in flight alone: nothing is recorded, the state of the last check
    stays.

    Attributes (read-only for the outside):
        info (UpdateInfo): The state of the mod, also the value bound on the
            Update topic

    Stand-in: no check exists. ``mirrors`` is always None (see
    ``_parse_mirrors``) and ``info`` is a local state object that is never
    pushed to the Update topic (see ``push``), so the whole operation above
    never runs; ``_check_lock`` and the two cancel scopes are None and
    ``running`` is always False.
    """

    def __init__(self, update_check, mod):
        """
        Args:
            update_check (UpdateCheck): The module of the process
            mod (Mod): The mounted mod to check, its entry carries the update
                source (mirrors)

        Stand-in: the same attributes with the values they have before a first
        check: ``mirrors`` is None (nothing is parsed, see ``_parse_mirrors``),
        ``info`` is a local state object in 'idle' (upstream's ``UpdateInfo``
        lives in the unported Update topic), ``_check_lock`` and the two cancel
        scopes stay None (no lock, no task, no request is ever created) and no
        check timestamp is recorded.
        """
        # the module of the process (the shared client and nursery, the
        # schedule); it is not called ``update_check`` -- that name is the
        # manual check of this mod
        self.check_module = update_check
        self.mod = mod
        self.name = mod.name
        # the update source of the mod, parsed once here: the mount of a mod
        # never changes while the process runs, so a malformed declaration is
        # not retried on every check -- the mod is unmanaged for good (None)
        # Stand-in: always None (see _parse_mirrors)
        self.mirrors = self._parse_mirrors()
        # the state of the mod, the value pushed to the Update topic: a new
        # instance per change (the topic binds the instance, it is never
        # mutated in place)
        # Stand-in: the UpdateInfo struct of the Update topic is stood in by a
        # SimpleNamespace carrying its fields (and its defaults); nothing is
        # ever pushed, so no frontend sees it
        self.info = SimpleNamespace(
            state='idle',
            current_version='',
            latest_version='',
            checked_at=0,
            error='',
        )
        # the lock the real check runs under: one check at a time per mod, the
        # discard of a check that arrives too late happens inside it
        # Stand-in: None -- no check ever runs, and the trio.Lock of upstream
        # could not even be created outside a running async loop
        self._check_lock = None
        # the cancel scope of the sequence task in flight, None when no
        # sequence runs (the module starts the task, the scope is created here
        # so a stop landing before the task starts is not lost)
        # Stand-in: always None (no sequence is ever started)
        self._loop_scope: 'Optional[anyio.CancelScope]' = None
        # the cancel scope of the check request in flight, None when there is
        # none; cancel_check() cancels it
        # Stand-in: always None (no request is ever sent)
        self._request_scope: 'Optional[anyio.CancelScope]' = None
        # monotonic timestamp (time.monotonic) of the last check that ran (any
        # outcome, a cancelled request does not count): a check younger than
        # FRESH_WINDOW is not repeated. Monotonic on purpose: the wall clock
        # can jump (NTP, the user, DST) and a jump must neither make a check
        # look fresh nor stale (the checked_at of the topic stays the wall
        # clock timestamp, it is what the frontend shows)
        # Stand-in: 0.0 and never updated, no check ever runs
        self._checked_mono = 0.0

    # ------------------------------------------------------------------
    # State on the Update topic
    # ------------------------------------------------------------------

    def set_state(self, state, current=None, latest=None, checked_at=None, error=''):
        """
        Set the state of the mod and push it to the Update topic.

        Args:
            state (str): One of UPDATE_STATE
            current (str): Local version, None keeps the known one
            latest (str): Latest version, None keeps the known one
            checked_at (int): Check timestamp (unix seconds), None keeps the
                known one
            error (str): Failure message, '' when there is none

        Returns:
            UpdateInfo: The new state (also the object bound by the topic)

        Stand-in: the state is recorded on the local state object (upstream's
        field keeping rules are kept) but ``push`` binds nothing, so the Update
        topic never shows it; no real version or timestamp is ever produced.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the state "{state}" of '
            f'"{self.name}" is not published to the Update topic'
        )
        previous = self.info
        self.info = SimpleNamespace(
            state=state,
            current_version=previous.current_version if current is None else current,
            latest_version=previous.latest_version if latest is None else latest,
            checked_at=previous.checked_at if checked_at is None else checked_at,
            error=error,
        )
        self.push(self.info)
        return self.info

    def push(self, info):
        """
        Bind a state to the mod on the Update topic.

        Args:
            info (UpdateInfo): The state, never mutated afterwards

        Stand-in: nothing is bound -- ``UpdateSource`` belongs to the unported
        Update topic (``alasio/backend/topic/update.py``), so the frontend
        never receives an update state and the topic stays empty.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the state of '
            f'"{self.name}" is bound to no Update topic'
        )

    # ------------------------------------------------------------------
    # Update source of the mod
    # ------------------------------------------------------------------

    def _parse_mirrors(self):
        """
        Parse the update source the mod declares (once, at construction)

        The mount of a mod never changes while the process runs, so the source
        is parsed once instead of on every check: a mod without usable mirrors
        is unmanaged from then on -- no check ever runs on it (the startup flow
        publishes the state once, see UpdateCheck.set_initial_states).

        Returns:
            Mirrors | None: The mirrors, None when the mod declares none (it is
                not updated on purpose) or a malformed one (a warning says so)

        Stand-in: nothing is parsed and None is answered, so every mod is
        unmanaged (which is also the state the entries report, see
        ``update_check``): ``Mirrors`` belongs to the unported
        ``deploy/httpclient`` (the mirror probe), and ``mod.entry.mirrors`` is
        not even read. A malformed declaration is therefore never detected.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the update source of '
            f'"{self.name}" is not parsed, the mod stays unmanaged'
        )
        return None

    @property
    def disabled(self) -> bool:
        """
        Whether the mod updates are off for this process

        The switch (``auto``, Deploy.Update.AutoUpdate) is read once at the
        startup, so the classification is final like the update source: a
        disabled mod is never checked -- no sequence is started for it and the
        manual entry answers DISABLED_MESSAGE (the state published at the
        startup is 'disabled'). A mod without a usable update source is
        'unmanaged' whatever the switch says: the source is the classification
        that outlives the switch.

        Returns:
            bool: True when the mod updates are off for this process
                (Deploy.Update.AutoUpdate = false) and the mod has an update
                source to check (a mod without one is unmanaged, whatever the
                switch says)

        Stand-in: always False -- ``mirrors`` is None for every mod (see
        ``_parse_mirrors``), which is upstream's own first term, so the
        stand-in never claims the user turned the updates off; the mod is
        reported unmanaged instead.
        """
        return self.mirrors is not None and not self.check_module.auto

    @property
    def no_supervisor(self) -> bool:
        """
        Whether the mod updates are off because the backend has no live supervisor

        A supervisor is the only one that can replace the backend process, and
        an applied update only takes effect in the new process (this one has
        the mod packages imported already). Without a live supervisor nothing
        is checked -- no sequence, no manual check, no full update -- and the
        state published at the startup is 'no-supervisor'. Read live: the
        supervisor can die while the backend runs (the recv loop of the
        lifespan clears the pipe), the backend shuts itself down right after.
        A mod without a usable update source is 'unmanaged' whatever the
        environment says.

        Returns:
            bool: True when the backend runs without a live supervisor and the
                mod has an update source to check

        Stand-in: upstream's expression, answered truthfully. The probe is
        live -- ``has_supervisor()`` reads the pipe of the supervisor -- so
        this keeps answering "the backend has a supervisor" while one is
        attached. The stand-in's mods have no update source at all, so the
        first term (``self.mirrors is not None``) already answers False and
        they are reported as unmanaged (see ``_parse_mirrors``).
        """
        return self.mirrors is not None and not has_supervisor()

    async def job(self):
        """
        Build the deploy job of this mod, bound to a fresh update server

        The server is created per use: a ServerFile serves one flow (see its
        class docstring -- it caches the mirror selection and the probe of that
        flow, one instance for the process would freeze the selection of a
        long-running backend), and it is warmed up here (the record read of the
        mirror selection is blocking sqlite IO, it runs in a worker thread
        instead of on the request path; see ServerFile.warmup).

        Returns:
            DeployJob: The job, bound to the warmed server

        Raises:
            ValueError: The mod is unmanaged: the entries of the mod (the
                check, the sequence) refuse an unmanaged mod before this point
                and the steps of the flows skip it, so this is the last line
                of defence
            AllMirrorsFailedError: If the warmup probe finds no usable mirror

        Stand-in: None is answered instead of a job -- ``ServerFile`` /
        ``DeployJob`` belong to the unported ``deploy/pack`` and nothing is
        warmed up (no probe, no sqlite read, no network). The Raises section
        above does not apply: the callers of the real module guard on
        ``mod.mirrors is None`` first and never reach this body, and a caller
        that did would get None, not an exception.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: no deploy job is built '
            f'for "{self.name}", the mod is never checked'
        )
        return None

    # ------------------------------------------------------------------
    # The automatic sequence
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        """
        Returns:
            bool: Whether the automatic sequence of this mod is running (a mod
                that is never checked -- unmanaged, disabled -- has none)

        Stand-in: always False -- ``_loop_scope`` is None because no sequence
        is ever started (see ``start_check_loop``), which is also what a real
        module answers for a mod that is never checked.
        """
        return self._loop_scope is not None

    def start_check_loop(self):
        """
        Start the automatic sequence of this mod (the module's entry: the
        startup flow, a restore, the end of the manual check)

        The sequence in flight, if any, is stopped first: one sequence per mod.
        The new task waits the standard spread before its first check -- the
        startup flow just ran a full update, a check right now would repeat it.

        A mod that is never checked has no sequence: nothing is started for an
        unmanaged, disabled or no-supervisor one (their states are published
        once by the startup flow).

        Stand-in: no sequence is started and no cancel scope is created -- the
        module never owns a nursery (see ``UpdateCheck.run``), and no check
        could run anyway (there is no update source and no deploy job).
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: no check sequence is '
            f'started for "{self.name}"'
        )

    def stop_check_loop(self):
        """
        Drop the automatic sequence of this mod (a maintenance flow pauses the
        mod, the manual check restarts it)

        A sequence whose task did not start yet is dropped all the same: the
        task finds no scope of its own and returns without checking.

        Stand-in: nothing is running, so the body below finds no scope to
        cancel (``_loop_scope`` is always None); the call is kept so the
        pause / restore discipline of the flows needs no special case.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: "{self.name}" has no '
            f'check sequence to drop'
        )
        scope = self._loop_scope
        self._loop_scope = None
        if scope is not None:
            scope.cancel()

    async def run_check_loop(self):
        """
        Serve the automatic sequence of this mod: wait the spread, check, wait
        CHECK_INTERVAL, check, ...

        Returns when the sequence is dropped (a pause, a replacement) or when a
        check raised (reported: the flow that paused the mod restores a fresh
        sequence).

        Stand-in: the sequence has no body -- there is no first delay to wait
        for (no check would follow), nothing to check and no exception to
        report, so the task returns at once.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the check sequence of '
            f'"{self.name}" has nothing to check'
        )

    # ------------------------------------------------------------------
    # The manual check
    # ------------------------------------------------------------------

    async def update_check(self) -> str:
        """
        Check the updates of this mod now (the manual entry)

        The check runs in the caller's task: the automatic sequence is dropped
        first (the check takes its place in the rhythm) and started over
        afterwards. The two checks before the lock only serve the message the
        caller gets -- the arbitration is the re-check inside the lock, so two
        callers arriving together leave exactly one check running.

        Returns:
            str: The message of the check: '' when it ran, the reason it was
                discarded otherwise (FRESH_MESSAGE / BUSY_MESSAGE /
                UNMANAGED_MESSAGE / DISABLED_MESSAGE / NO_SUPERVISOR_MESSAGE)

        Stand-in: '' is answered, like a check that ran, but nothing is checked
        and no state is written. The refusals of the upstream body (the five
        messages above) are never produced: there is no source, no lock and no
        rhythm to be fresh or busy against.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the manual check of '
            f'"{self.name}" checks nothing'
        )
        return ''

    def cancel_check(self) -> bool:
        """
        Interrupt the check request in flight of this mod (the manual cancel).

        Only the request is interrupted: the sequence continues (or the manual
        check of the caller returns), the state of the last check stays.

        Returns:
            bool: True when a request was in flight

        Stand-in: False -- ``_request_scope`` is always None (no request is
        ever sent), so there is never a request to interrupt; the body below
        keeps upstream's shape and finds nothing to cancel.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: "{self.name}" has no '
            f'check request to interrupt'
        )
        scope = self._request_scope
        if scope is None:
            return False
        scope.cancel()
        return True

    # ------------------------------------------------------------------
    # The real check (the body under the lock)
    # ------------------------------------------------------------------

    async def _run_update_check(self) -> str:
        """
        Run the real check of this mod and record its verdict (the body inside
        ``_check_lock``)

        Read-only (the local ledger version against latest.pack). A failure is
        recorded as the state of the mod; an interrupted check (the manual
        cancel, the sequence dropped mid-request) records nothing: the state of
        the last check goes back, the topic is never left on 'checking'.

        Returns:
            str: '' when the check ran, FRESH_MESSAGE when it was discarded
                (the second check of the fresh window, inside the lock),
                UNMANAGED_MESSAGE for an unmanaged mod (defensive: the entry
                refuses it and its sequence is never started), DISABLED_MESSAGE
                for a disabled one, NO_SUPERVISOR_MESSAGE for a mod of a
                backend without a live supervisor (the same, the mod updates
                are off)

        Stand-in: '' is answered and nothing is recorded -- there is no ledger
        to compare against latest.pack (``deploy/pack``) and no request to
        send, so the state is never moved to 'checking', 'uptodate' or
        'error'. The defensive refusals above are not produced either.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the check of '
            f'"{self.name}" reads nothing and records nothing'
        )
        return ''

    def _rollback_check(self, checking, previous):
        """
        Put the state of the last check back after an interrupted request

        Called by an interrupted check (a dropped sequence, the manual cancel):
        no verdict exists, so nothing is recorded. Only when the state of the
        mod is still the ``'checking'`` instance this request pushed -- a writer
        that moved the state on meanwhile (a maintenance flow marking its scope
        'queued' / 'stopping') did it knowingly and its state is the newer truth
        (the interrupted check must not resurrect the verdict it replaced).
        Binding the previous instance as-is is enough: the topic drops a push
        whose value is already bound by identity.

        Args:
            checking (UpdateInfo): The 'checking' state this request pushed
            previous (UpdateInfo): The state it replaced

        Stand-in: nothing is restored and nothing is pushed -- the state is
        never moved to 'checking' (see ``_run_update_check``), so there is no
        interrupted request to unwind, and the Update topic would not show the
        restored instance anyway.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: there is no check state '
            f'of "{self.name}" to roll back'
        )

    async def _request_check(self):
        """
        Run one check request of the mod (DeployJob.check()) under the request
        cancel scope: cancel_check() interrupts this request alone.

        Returns:
            DeployCheck | None: The result, None when the request was cancelled

        Stand-in: None is answered and no cancel scope is opened --
        ``DeployJob`` belongs to the unported ``deploy/pack``, no request is
        sent to a mirror and there is no check to cancel.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: no check request is '
            f'sent for "{self.name}"'
        )
        return None


class UpdateCheck:
    """
    The check module of the process: one ModUpdateCheck per mounted mod, the
    shared http client and the pause bookkeeping of the maintenance flows.

    The module runs as one task of the lifespan (``run``): the task owns the
    nursery of the check sequences and tears them down, with the shared http
    client, when the process shuts down (``close``).

    Attributes (read-only for the outside):
        mods (dict[str, ModUpdateCheck]): The managed mods, keyed by mod name,
            built by bind()

    Stand-in: no mod is ever bound (``bind`` is a stand-in), no nursery and no
    http client are ever created (``run`` only waits for the backend shutdown,
    ``client()`` answers None) and ``close`` awaits nothing.
    """

    def __init__(self):
        self.mods: 'Dict[str, ModUpdateCheck]' = {}
        self._client = None
        # upstream Optional[trio.Nursery]: always None here, no nursery is ever
        # opened (see run)
        self._nursery: 'Optional[anyio.abc.TaskGroup]' = None
        # the master switch of the mod updates (Deploy.Update.AutoUpdate), read
        # once per process by load_schedule(): with it off every managed mod is
        # 'disabled' -- no sequence, no manual check, no full update (see
        # ModUpdateCheck.disabled)
        # Stand-in: upstream's initial value; load_schedule reads nothing, so
        # the switch stays True (nothing is checked either way, there is no mod)
        self.auto = True

    # ------------------------------------------------------------------
    # Wiring (the lifespan task and the nursery of the sequences)
    # ------------------------------------------------------------------

    async def run(self):
        """
        Lifespan background task: own the nursery the check sequences run in

        One task per backend process, started by the lifespan before the
        restart manager: the manager's startup flow starts the check sequences
        (``start``) and finds the nursery set here -- this task sets it in its
        first synchronous section, and the startup flow, spawned by the task
        of the manager, only runs after the pass both tasks were queued in (see
        the comment at the entry of the lifespan).

        The sequences are children of the nursery opened here, never of the
        lifespan nursery: a failing sequence ends alone (its body reports and
        never raises), and the module can join every sequence before it tears
        down. The task runs until the process shuts down (the lifespan nursery
        is cancelled): the sequences are cancelled and joined with this
        nursery, then ``close`` closes the shared http client (shielded: the
        teardown must complete under the cancellation of the shutdown).

        The nursery field is cleared the moment the teardown starts, before
        the sequences are cancelled and joined: from then on the module starts
        no sequence (the field is what the entries read). A restore landing in
        that window -- the wrap-up of a flow during the shutdown -- starts
        nothing instead of hitting a closing nursery.

        Stand-in: no nursery is opened and no sequence exists, so the task only
        keeps the lifespan task group alive: it waits on the backend shutdown
        (``GLOBAL_CONTEXT.shutdown_event``, created by the lifespan of
        ``oas/backend/app/app.py`` before the tasks are started and set on the
        way out; when there is no lifespan event -- the app never started or it
        already shut down -- it waits forever instead, which the task group
        cancels at its exit) and then runs ``close``. Waiting is what upstream
        does, and it is what the only call site needs: the lifespan starts this
        task with ``task_group.start_soon``, and a task returning right away
        would run its teardown at startup and leave the module looking torn
        down for the whole process life.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: it opens no nursery and '
            'owns no check sequence, it only waits for the backend shutdown'
        )
        try:
            event = GLOBAL_CONTEXT.shutdown_event
            if event is None:
                # no lifespan event to wait on: a task group started without
                # the app, or one that already shut down. Waiting forever is as
                # safe as waiting on the event -- the group cancels this task
                # when it exits
                await anyio.sleep_forever()
            else:
                await event.wait()
        finally:
            # the teardown: upstream clears the nursery field here, before the
            # sequences are cancelled and joined (no sequence may start from
            # then on); the field is always None here
            self._nursery = None
            await self.close()

    @property
    def nursery(self):
        """
        Returns:
            trio.Nursery | None: The nursery of the check sequences, owned by
                ``run``; None when the module does not run (the process startup
                has not reached the task yet, or the process is shutting down:
                no sequence is started then)

        Stand-in: always None -- ``run`` opens no nursery and no sequence
        exists, so no caller can start a task in it.
        """
        return self._nursery

    def reset(self):
        """
        Return to the initial state (tests: a fresh process has a fresh module)

        Stand-in: the assignments below are upstream's, but there is nothing
        else to return to -- no client, no nursery and no mod (see ``bind``).
        """
        logger.warning(
            '[Update] The update check module is a stand-in: there is no check state '
            'to reset'
        )
        self.mods = {}
        self._nursery = None
        self.auto = True

    def bind(self, mods=None):
        """
        Build one ModUpdateCheck per mounted mod and set the initial states.

        Args:
            mods (dict[str, Mod]): The mount to manage, defaults to the
                MOD_LOADER mount (imported here: the loader is bound to the
                project root resolved at the backend startup, see
                asgi.create_config)

        Returns:
            dict[str, ModUpdateCheck]: The per-mod checks, keyed by mod name

        Stand-in: nothing is bound and the empty ``self.mods`` is returned --
        the loader that would default ``mods`` (``MOD_LOADER``) belongs to the
        unported config entry stack, and the ModUpdateCheck the body would
        build is a stand-in anyway. Every caller reads the empty dict as "no
        mod is managed" and skips its real work.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no mod is bound, no '
            'update state is tracked'
        )
        return self.mods

    def load_schedule(self):
        """
        Read the update schedule from the deploy config (once per process, like
        the daily restart time: changing it takes effect with the next
        restart). A broken config falls back to the defaults: the checks of a
        broken installation must not stop.

        Sets `auto`. Read once: the classification of the mods ('disabled', see
        ModUpdateCheck.disabled) is as final as their update source.

        Stand-in: nothing is read -- the deploy config (``Deploy.Update.
        AutoUpdate``) belongs to the unported ``deploy/config``, so ``auto``
        keeps its upstream initial value True and the warning about a broken
        config can never occur. Nothing is checked either way: no mod exists.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: the update schedule is '
            'not read, the switch keeps its default (auto = True)'
        )

    def first_delay(self) -> float:
        """
        Seconds to the first automatic check of a fresh sequence

        Always ``random(CHECK_INTERVAL, CHECK_INTERVAL * 2)``. The window is a
        fixed mathematical design, not a tunable:

        - the spread is exactly CHECK_INTERVAL wide, and the checks that follow
          are CHECK_INTERVAL apart, so the sequence stays evenly spread --
          backends started at the same moment (a fleet restarted together, the
          daily maintenance) never hit the mirrors together, at any time;
        - the lower bound CHECK_INTERVAL covers the startup full update: the
          process just checked every mod, a check right after would repeat it.

        Returns:
            float: The delay

        Stand-in: the value is upstream's (a pure computation, no unported
        code), but no sequence exists here to wait for it, so it is never
        consumed.
        """
        return random.uniform(CHECK_INTERVAL, CHECK_INTERVAL * 2)

    def interval(self) -> float:
        """
        Seconds between two checks of a running sequence

        Returns:
            float: CHECK_INTERVAL

        Stand-in: unchanged (a constant, no unported code); no sequence exists
        here to wait for it.
        """
        return CHECK_INTERVAL

    def client(self):
        """
        The shared http client of the update servers, created lazily (a client
        is bound to the event loop it is used in). Never replaced: a client
        ``close`` closed stays the client, a further request fails through it
        instead of a second client being built.

        Returns:
            httpx2.AsyncClient: The client

        Stand-in: None is answered and nothing is created, cached or closed --
        the deploy http client (``AsyncHttpClient`` of the unported
        ``deploy/httpclient``) is what would be built here. The callers still
        work: ``InstallBase(mod, site_packages, client=...)`` accepts None and
        the real installer builds its own client, and there is no update server
        here that would send a request with it.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: there is no shared http '
            'client, returning None (the caller builds its own)'
        )
        return None

    async def close(self):
        """
        Tear the module down: stop every sequence and close the shared http
        client

        The teardown of ``run`` (its ``finally``); also callable on its own (a
        test). The sequences are stopped (a task still in flight is cancelled;
        ``run`` joins them with its nursery before this point, so no request of
        the module is in flight here) and the client is closed.

        The closed client is kept: the close is final -- a request that arrives
        after it goes to the closed client and fails with "Cannot send a
        request, as the client has been closed" instead of silently building a
        second client that nothing would ever close (a foreign task may still
        be in flight while the process goes down: its request fails, the
        teardown does not wait for it). Idempotent, and shielded: the process
        may be shutting down with the cancellation already in flight, the
        closing itself must complete.

        Stand-in: awaits nothing and never raises -- no sequence exists to stop
        and no http client exists to close (``client()`` answers None and is
        never stored). The entry is kept so the lifespan teardown and a test
        can still call it.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: there is no check sequence '
            'and no http client to close'
        )

    def set_initial_states(self):
        """
        Publish the initial state of every mod (the startup flow, before the
        first check): 'no-supervisor' for a mod of a backend without a live
        supervisor, 'unmanaged' for a mod without a usable update source (no
        mirrors, or a malformed declaration: the mod is never checked),
        'disabled' for a mod whose updates are off (``auto``), 'idle'
        otherwise. The classification is final for the update source and the
        switch (parsed and read once, see ModUpdateCheck.mirrors and
        ModUpdateCheck.disabled); the supervisor gate is read live
        (ModUpdateCheck.no_supervisor).

        Stand-in: nothing is published -- the loop below is empty because no
        mod is bound (see ``bind``) and the Update topic is not reachable
        anyway (see ModUpdateCheck.push). The state a real mod without a source
        reports is 'unmanaged'.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no initial update state is '
            'published to the Update topic'
        )
        for mod in self.mods.values():
            if mod.no_supervisor:
                mod.set_state('no-supervisor')
            elif mod.mirrors is None:
                mod.set_state('unmanaged')
            elif mod.disabled:
                mod.set_state('disabled')
            else:
                mod.set_state('idle')

    # ------------------------------------------------------------------
    # The flows' API: start / pause / restore / check / cancel
    # ------------------------------------------------------------------

    def names(self, managed=True) -> 'List[str]':
        """
        Args:
            managed (bool): Only the mods with a usable update source (a
                disabled mod still has one: the update of a mod and the switch
                of the process are two different things)

        Returns:
            List[str]: The mod names (the order of the mount), sorted

        Stand-in: [] -- no mod is bound (see ``bind``), so the body below has
        nothing to list (and no mod would have a usable update source anyway,
        see ModUpdateCheck._parse_mirrors). The flows that start from this list
        do nothing.
        """
        if not managed:
            return sorted(self.mods)
        return sorted(
            name for name, mod in self.mods.items() if mod.mirrors is not None
        )

    def start(self, names=None):
        """
        Start the check sequences of the mods (the startup flow): every
        sequence waits the standard spread before its first check -- the
        startup full update just checked everything.

        Args:
            names (Iterable[str]): Mod names, defaults to every managed mod

        Stand-in: no sequence is started -- the body below is empty (no mod is
        bound, see ``bind``) and ``start_check_loop`` is a stand-in itself.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no check sequence is started'
        )
        for name in self._resolve(names):
            self.mods[name].start_check_loop()

    def pause(self, names=None):
        """
        Pause the check sequences of the mods (a maintenance flow owns them):
        the sequences in flight are dropped, the states stay.

        Args:
            names (Iterable[str]): Mod names, defaults to every managed mod

        Stand-in: nothing is paused -- no sequence runs and no mod is bound
        (see ``bind``); the body below is empty.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no check sequence is paused'
        )
        for name in self._resolve(names):
            self.mods[name].stop_check_loop()

    def restore(self, names=None):
        """
        Restore the check sequences a flow paused (its wrap-up): the sequences
        that are not running start again with the standard spread.

        A mod whose sequence runs is left alone: the flows are mutually
        exclusive, so the flow wrapping up is the one that paused it (if it did
        not, the sequence must not be restarted -- the spread would be drawn
        again for nothing). A sequence that ended by itself (a check raised) is
        restored the same way, it is not running either.

        Args:
            names (Iterable[str]): Mod names, defaults to every managed mod

        Stand-in: nothing is restored -- no sequence was paused and no mod is
        bound (see ``bind``); the body below is empty and ``start_check_loop``
        is a stand-in itself.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no check sequence is restored'
        )
        for name in self._resolve(names):
            mod = self.mods[name]
            if mod.running:
                continue
            mod.start_check_loop()

    async def update_check(self, name: str) -> str:
        """
        Check the updates of one mod now (the manual check of the rpc layer)

        Args:
            name (str): Mod name

        Returns:
            str: The message of the check: '' when it ran, the reason it was
                discarded otherwise (see ModUpdateCheck.update_check)

        Raises:
            ValueError: The mod is unknown (the entry of the module): an
                unmanaged mod answers UNMANAGED_MESSAGE and a disabled one
                DISABLED_MESSAGE, like their own entries

        Stand-in: '' for every name -- nothing is checked and no mod is bound
        (see ``bind``), so there is no state to report and no source to refuse.
        The ValueError of the upstream body is not raised: every name would be
        unknown here, and the manual check of the frontend must not turn into
        an error; it is answered like a check that did nothing, which is what
        happened.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the manual check of '
            f'"{name}" checks nothing'
        )
        return ''

    def cancel_check(self, name: str) -> bool:
        """
        Interrupt the check request in flight of one mod.

        Args:
            name (str): Mod name

        Returns:
            bool: True when a request was in flight

        Stand-in: always False -- the body below keeps upstream's shape and
        finds no mod (see ``bind``), and no request is ever sent (see
        ModUpdateCheck._request_scope), so there is nothing to interrupt.
        """
        mod = self.mods.get(name, None)
        return mod is not None and mod.cancel_check()

    # ------------------------------------------------------------------
    # States (the rpc precondition and the apply steps)
    # ------------------------------------------------------------------

    def state_of(self, name: str) -> str:
        """
        Args:
            name (str): Mod name

        Returns:
            str: The state of the mod, '' for an unknown mod

        Stand-in: '' for every name -- the body below keeps upstream's shape
        and finds no mod (see ``bind``), which is upstream's own answer for an
        unknown mod; there is no published state to read.
        """
        mod = self.mods.get(name, None)
        return mod.info.state if mod is not None else ''

    def available(self) -> 'List[str]':
        """
        Returns:
            List[str]: The mods whose update is available (the update flow
                applies them), sorted

        Stand-in: [] -- no mod is bound and no check ever runs (see
        ModUpdateCheck._run_update_check), so no mod is ever 'available'; the
        update flow of the topic refuses with "No update available" and nothing
        is ever applied.
        """
        return sorted(
            name for name, mod in self.mods.items() if mod.info.state == 'available'
        )

    def set_state(self, name: str, state: str, error=''):
        """
        Set the state of one mod (the apply steps drive it).

        Args:
            name (str): Mod name
            state (str): One of UPDATE_STATE
            error (str): Failure message, '' when there is none

        Stand-in: no state is set -- the body below keeps upstream's shape and
        finds no mod (see ``bind``), and ModUpdateCheck.set_state publishes to
        no topic anyway. The apply steps therefore drive nothing, which is what
        the empty update flow expects.
        """
        logger.warning(
            f'[Update] The update check module is a stand-in: the state "{state}" of '
            f'"{name}" is set nowhere'
        )
        mod = self.mods.get(name, None)
        if mod is None:
            return
        mod.set_state(state, error=error)

    def mark_restart_required(self, names, error=''):
        """
        Mark the mods whose files were already written by a flow whose handover
        failed: the disk holds the new version, the process still runs the old
        one, a restart applies it.

        Args:
            names (Iterable[str]): Mod names
            error (str): Failure message shown on the cards

        Stand-in: nothing is marked -- the loop below finds no mod (see
        ``bind``), and no update is ever applied by the stand-in, so no restart
        can be required by one.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no mod is marked '
            'restart-required'
        )
        for name in names:
            mod = self.mods.get(name, None)
            if mod is None:
                continue
            logger.warning(
                f'[Update] The update of "{name}" needs a restart to be applied'
            )
            mod.set_state('restart-required', error=error)

    def release_states(self):
        """
        Release the transient states of the flow in flight (the wrap-up of a
        flow that does not hand over)

        The pending states the apply steps set (``FLOW_STATES``: 'queued',
        'stopping', 'downloading') describe the flow that set them: once it
        wrapped up they are stale -- the update of the last check is still
        pending (nothing on disk changed) and the wrapped-up flow restored the
        check sequences, so the mod returns to 'available' (the versions of the
        last check are kept).

        The states of the files ('updating', 'restart-required') and the
        failures ('error') do not describe the flow in flight and stay (the next
        process start converges the tree); 'checking' is the state of a check
        request, not of the flow: the check module puts the state of the last
        check back itself when the request is interrupted (see
        ``ModUpdateCheck._rollback_check``). A mod the flow never touched is
        left alone.

        Stand-in: nothing is released -- the loop below is empty (no mod is
        bound, see ``bind``) and no 'available' state was ever published.
        """
        logger.warning(
            '[Update] The update check module is a stand-in: no flow state is released'
        )
        for name, mod in self.mods.items():
            if mod.info.state in FLOW_STATES:
                self.set_state(name, 'available')

    def _resolve(self, names):
        """
        Resolve the mod names of a flow call against the managed mods

        Args:
            names (Iterable[str] | None): Given names, None means every mod

        Returns:
            Iterator[str]: The names actually managed

        Stand-in: an empty iterator (or list) -- no mod is bound (see
        ``bind``) and ``names`` answers [] itself, so the flows that call it
        iterate nothing.
        """
        if names is None:
            return list(self.names())
        return [name for name in names if name in self.mods]


# The process-wide check module, attached by the lifespan
UPDATE_CHECK = UpdateCheck()
