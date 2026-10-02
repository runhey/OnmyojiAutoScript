"""
Benchmark: is ``oas.ext.proc`` actually faster than psutil?

The module exists for exactly one reason. Its docstring says it is "10+ times
faster by directly access[ing] psutil's C bindings", and ``cmd.py`` carries a
more specific note::

    # This would be fast on psutil<=5.9.8 taking overall time 0.027s
    # but taking 0.39s on psutil>=6.0.0

This file measures those claims instead of repeating them. Measured here on
psutil 7.2.2 / Python 3.14 / Windows with ~380 live processes::

    fast sweep (process_iter)           ~5.5 ms
    psutil.process_iter([...])         ~11.6 ms     ~2.1x
    psutil.process_iter() + .cmdline()  ~9.5 ms     ~1.7x
    pids() only                         ~0.03 ms     ~1.0x

So the fast path still wins, but the "10+" is stale: psutil 7 closed most of the
gap that psutil 5 had. The assertions below therefore use a loose floor (1.2x)
that is meant to catch the module losing its whole advantage -- not to police a
constant that upstream psutil controls.

Run with::

    python -m pytest tests/oas/ext/proc/test_bench_proc.py --benchmark-only -v
    python -m pytest tests/oas/ext/proc/test_bench_proc.py --benchmark-sort=name --benchmark-only -v

``--benchmark-skip`` is in the project's ``addopts``, so the ``benchmark``-driven
tests below are skipped by a plain ``pytest`` run. ``TestFastPathAgreesWithPsutil``
and the ratio floor are ordinary tests and always run -- "fast but wrong" loses.
"""

import subprocess
import timeit

import psutil
import pytest
from conftest import python_argv

from oas.ext.proc import get_cmdline, process_iter, process_kill
from oas.ext.proc.cmd import cmdline as raw_cmdline
from oas.ext.proc.iter import pids

#: How many children the end-to-end kill benchmark spawns per round.
KILL_BATCH = 8

#: The floor the fast sweep must beat psutil by. Deliberately far below the
#: measured ratio; see the module docstring.
MIN_SPEEDUP = 1.2


# =============================================================================
# The three sweeps under comparison
# =============================================================================


def fast_sweep():
    """The module's own sweep: pid -> cmdline, straight from the C extension."""
    return dict(process_iter())


def psutil_sweep_with_attrs():
    """
    ``psutil.process_iter(['pid', 'cmdline'])`` -- the slow call the module's
    docstring names as the thing being replaced.
    """
    return {proc.info['pid']: proc.info['cmdline'] for proc in psutil.process_iter(['pid', 'cmdline'])}


def psutil_sweep_lazy():
    """
    The honest comparison: iterate pids, then ask each process for its cmdline.

    This pays for a ``Process`` object and an ``is_running()`` check per pid,
    which is exactly the per-pid overhead the module deliberately skips -- but
    nothing more, so the ratio it produces is the ratio that matters.
    """
    result = {}
    for proc in psutil.process_iter():
        try:
            result[proc.pid] = proc.cmdline()
        except (psutil.Error, OSError):
            continue
    return result


def psutil_kill_dead(pid):
    """``psutil``'s way of killing a pid that is already gone."""
    try:
        psutil.Process(pid).kill()
    except (psutil.Error, OSError):
        return False
    return True


def _spawn_and_kill_batch(kill):
    """
    Spawn ``KILL_BATCH`` children and kill them all with ``kill``.

    Returns:
        float: seconds spent killing, spawn cost excluded
    """
    children = [subprocess.Popen(python_argv()) for _ in range(KILL_BATCH)]
    try:
        start = timeit.default_timer()
        for child in children:
            kill(child.pid)
        elapsed = timeit.default_timer() - start
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=15)
    return elapsed


def _pids_psutil_can_describe():
    """
    pids psutil reports a usable cmdline for, minus the filtered placeholders.

    Returns:
        set[int]: pids whose cmdline is non-empty and is not the conhost
            ``\\??\\...`` internal form -- i.e. pids the sweep *could* have
            yielded if it had permission to read them.
    """
    readable = set()
    for pid in psutil.pids():
        if pid in (0, 4):
            continue
        try:
            cmd = psutil.Process(pid).cmdline()
        except (psutil.Error, OSError):
            continue
        if cmd and not cmd[0].startswith(r'\??'):
            readable.add(pid)
    return readable


# =============================================================================
# Benchmarks
# =============================================================================


class TestSweepBenchmarks:
    """Cost of enumerating every process on the machine."""

    def test_t1_fast_sweep(self, benchmark):
        """``process_iter()`` -- the module's own pid+cmdline sweep."""
        benchmark(fast_sweep)

    def test_t1_psutil_sweep_with_attrs(self, benchmark):
        """``psutil.process_iter(['pid', 'cmdline'])`` -- the named alternative."""
        benchmark(psutil_sweep_with_attrs)

    def test_t2_psutil_sweep_lazy(self, benchmark):
        """``psutil.process_iter()`` plus a ``cmdline()`` call per pid."""
        benchmark(psutil_sweep_lazy)

    def test_t3_pids_only(self, benchmark):
        """The pid listing alone -- both sides call the same C function."""
        benchmark(pids)

    def test_t3_psutil_pids_only(self, benchmark):
        benchmark(psutil.pids)


class TestSingleReadBenchmarks:
    """Cost of one read, on a live pid and on a dead one."""

    def test_t4_fast_read_live_pid(self, benchmark):
        """One ``get_cmdline`` on a pid that is definitely alive."""
        pid = psutil.Process().pid
        benchmark(lambda: get_cmdline(pid))

    def test_t4_psutil_cmdline_live_pid(self, benchmark):
        pid = psutil.Process().pid
        benchmark(lambda: psutil.Process(pid).cmdline())

    def test_t5_fast_kill_dead_pid(self, benchmark, dead_pid):
        """
        The error path, which a sweep pays for every process that exited first.

        This is where the module's blanket ``except`` earns its keep: psutil
        builds a ``Process`` and raises before the caller can decide.
        """
        benchmark(lambda: process_kill(dead_pid))

    def test_t5_psutil_kill_dead_pid(self, benchmark, dead_pid):
        benchmark(lambda: psutil_kill_dead(dead_pid))


class TestKillBatchBenchmarks:
    """End-to-end cost of the other documented use case: kill the emulators."""

    def test_t6_fast_path_batch_kill(self, benchmark):
        benchmark.pedantic(
            lambda: _spawn_and_kill_batch(process_kill), rounds=3, iterations=1
        )

    def test_t6_psutil_batch_kill(self, benchmark):
        benchmark.pedantic(
            lambda: _spawn_and_kill_batch(psutil_kill_dead), rounds=3, iterations=1
        )


# =============================================================================
# "Fast but wrong loses"
# =============================================================================


class TestFastPathAgreesWithPsutil:
    """A speedup is worthless if the answer differs."""

    def test_sweep_agrees_on_every_common_pid(self):
        """Every pid both sweeps saw must have an identical cmdline."""
        mine = fast_sweep()
        theirs = psutil_sweep_lazy()
        disagreements = {
            pid: (mine[pid], theirs[pid])
            for pid in set(mine) & set(theirs)
            if mine[pid] != theirs[pid]
        }
        assert disagreements == {}

    def test_sweep_covers_most_readable_pids(self):
        """
        Coverage is high, but deliberately not total.

        ``cmd.py`` carries an explicit ``[MODIFIED] No permission fallback on >
        WINDOWS_8_1 because we don't need that precise``. psutil falls back to
        the slower ``NtQueryInformationProcess`` route when the PEB read is
        denied; this module returns ``[]`` and lets the sweep skip the process.
        So processes at a higher integrity level (Taskmgr, the audio device
        graph, vendor helper services) can be missing here while psutil still
        describes them. The floor is 0.8 rather than 1.0 for that reason.
        """
        mine = set(fast_sweep())
        readable = _pids_psutil_can_describe()

        assert readable, 'no readable pids at all -- the comparison is meaningless'
        covered = mine & readable
        assert len(covered) >= len(readable) * 0.8, (
            f'only {len(covered)}/{len(readable)} readable pids were swept'
        )

    def test_every_skipped_pid_is_denied_in_the_c_layer(self):
        """
        A pid the sweep skipped must be skipped for a permission reason.

        If the raw C call could read a skipped pid perfectly well, the skip
        would be a filter bug rather than the documented trade-off. The
        exception is allowed to be "access denied" *or* "already gone": the
        process may exit between the two reads.
        """
        mine = set(fast_sweep())
        skipped = _pids_psutil_can_describe() - mine
        if not skipped:
            pytest.skip(
                'no higher-integrity processes are running (likely an elevated '
                'shell), so the permission trade-off cannot be observed here'
            )

        for pid in sorted(skipped):
            with pytest.raises(OSError):
                raw_cmdline(pid)

    def test_sweep_does_not_invent_pids(self):
        """And it must not report pids that do not exist."""
        mine = set(fast_sweep())
        assert mine <= set(psutil.pids())

    def test_single_read_agrees_with_psutil(self):
        pid = psutil.Process().pid
        assert dict(process_iter())[pid] == psutil.Process(pid).cmdline()

    def test_child_cmdline_agrees_with_psutil(self, argv_child):
        proc, argv = argv_child()
        assert dict(process_iter())[proc.pid] == argv
        assert psutil.Process(proc.pid).cmdline() == argv


# =============================================================================
# The speedup floor, measured the same way every run
# =============================================================================


@pytest.mark.skipif(
    not psutil.WINDOWS,
    reason='the module is a Windows PEB fast path; the comparison is not meaningful elsewhere',
)
class TestSpeedupFloor:
    """
    A loose regression guard, not a specification.

    ``psutil.process_iter()`` gets faster with every release, so the honest
    comparison drifts. Asserting the docstring's 10x would make the suite fail
    for a reason the project does not control; asserting *some* advantage
    catches the day the module stops being worth its complexity.
    """

    @staticmethod
    def _best(func, repeat):
        """Best-of-N, because a loaded CI box only ever adds noise."""
        return min(timeit.repeat(func, number=1, repeat=repeat))

    def test_fast_sweep_beats_psutil_lazy_sweep(self):
        fast_sweep()
        psutil_sweep_lazy()

        fast = self._best(fast_sweep, repeat=15)
        slow = self._best(psutil_sweep_lazy, repeat=10)

        ratio = slow / fast
        assert ratio > MIN_SPEEDUP, (
            f'the fast sweep is only {ratio:.2f}x faster than psutil '
            f'(floor {MIN_SPEEDUP}x): fast={fast * 1000:.2f}ms slow={slow * 1000:.2f}ms'
        )

    def test_fast_sweep_beats_psutil_attrs_sweep(self):
        fast_sweep()
        psutil_sweep_with_attrs()

        fast = self._best(fast_sweep, repeat=15)
        slow = self._best(psutil_sweep_with_attrs, repeat=10)

        ratio = slow / fast
        assert ratio > MIN_SPEEDUP, (
            f'the fast sweep is only {ratio:.2f}x faster than '
            f"psutil.process_iter(['pid', 'cmdline']) (floor {MIN_SPEEDUP}x)"
        )

    def test_the_documented_10x_claim_is_reported(self, capsys):
        """
        Print the real ratio so the stale docstring is visible in CI output.

        This test never fails on the ratio: it exists to make the discrepancy
        between the "10+ times faster" comment and reality observable, rather
        than something a reader has to trust.
        """
        fast_sweep()
        psutil_sweep_lazy()

        fast = self._best(fast_sweep, repeat=15)
        slow = self._best(psutil_sweep_lazy, repeat=10)
        ratio = slow / fast

        with capsys.disabled():
            print(
                f'\n  process_iter(): {fast * 1000:.2f} ms   '
                f'psutil lazy sweep: {slow * 1000:.2f} ms   '
                f'ratio: {ratio:.2f}x  '
                f'(docstring claims 10x, psutil {psutil.__version__}, '
                f'{len(psutil.pids())} processes)'
            )

        assert ratio > 1.0, 'the fast path must at least win'
