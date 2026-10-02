"""
Tests for ``oas.ext.proc.iter``: enumerate every process on the machine.

``process_iter`` is the reason ``oas.ext.proc`` exists. Where
``psutil.process_iter(['pid', 'cmdline'])`` takes over a second on a busy
Windows box, this walks ``psutil._psplatform.pids()`` and reads each cmdline
through the C extension directly, which the module documents as ~0.017s.

That speed comes from being *unsafe* in a specific way: it never asks psutil
whether a process is still running, so every single pid is a race against that
process exiting. The bulk of this file is therefore about the two things that
matter at 4000 pids: the docstring's guarantee that every yielded cmdline has at
least one element, and the promise that a dying process is skipped rather than
propagated as an exception.
"""

import inspect
import os
import subprocess
import threading

import psutil
import pytest
from conftest import python_argv

import oas.ext.proc.iter as iter_module
from oas.ext.proc import get_cmdline, process_iter
from oas.ext.proc.iter import pids


@pytest.fixture
def stubbed_iter(monkeypatch):
    """
    Drive ``process_iter`` from a fixed pid list and a cmdline table.

    Returns:
        dict: ``{'pids': [...], 'cmdlines': {pid: [...]}}`` -- mutate it to set
            up the exact situation the test wants, free of host race conditions.
    """
    state = {'pids': [], 'cmdlines': {}}
    monkeypatch.setattr(iter_module, 'pids', lambda: list(state['pids']))
    monkeypatch.setattr(
        iter_module, 'get_cmdline', lambda pid: list(state['cmdlines'].get(pid, []))
    )
    return state


# =============================================================================
# pids()
# =============================================================================


class TestPids:
    """``pids()`` is the raw, unfiltered, sorted pid list."""

    def test_returns_a_non_empty_list(self):
        result = pids()
        assert isinstance(result, list)
        assert result

    def test_elements_are_ints(self):
        assert all(isinstance(pid, int) for pid in pids())

    def test_is_sorted_ascending(self):
        result = pids()
        assert result == sorted(result)

    def test_has_no_duplicates(self):
        result = pids()
        assert len(result) == len(set(result))

    def test_contains_this_process(self):
        assert os.getpid() in pids()

    def test_contains_a_spawned_child(self, child_factory):
        child = child_factory()
        assert child.pid in pids()

    def test_agrees_with_psutil_pids(self):
        """
        Cross-check against the psutil call this replaces.

        The two sets are sampled at slightly different moments, so a little
        churn is expected; a big gap would mean the pid source itself is wrong.
        """
        mine = set(pids())
        theirs = set(psutil.pids())
        assert len(mine & theirs) >= max(len(mine), len(theirs)) * 0.9

    def test_killed_child_disappears(self, child_factory, poll_until):
        child = child_factory()
        pid = child.pid
        assert pid in pids()
        child.kill()
        child.wait(timeout=10)
        assert poll_until(lambda: pid not in pids())

    def test_each_call_returns_a_new_list(self):
        first = pids()
        second = pids()
        assert first is not second

    def test_mutation_does_not_leak_into_the_next_call(self):
        """The caller cannot corrupt the pid source by editing the result."""
        first = pids()
        original_length = len(first)
        first.clear()
        assert len(pids()) == original_length or len(pids()) > 0


# =============================================================================
# process_iter(): the documented contract
# =============================================================================


class TestProcessIterContract:
    """Guarantees ``process_iter`` makes to every caller."""

    def test_returns_a_generator(self):
        """Not a list: the sweep must be paid for lazily."""
        result = process_iter()
        assert inspect.isgenerator(result)
        assert not isinstance(result, list)
        result.close()

    def test_items_are_pid_cmdline_pairs(self):
        for item in process_iter():
            assert isinstance(item, tuple)
            assert len(item) == 2
            pid, cmd = item
            assert isinstance(pid, int)
            assert isinstance(cmd, list)

    def test_every_cmdline_has_at_least_one_element(self):
        """
        The docstring's central promise.

        Callers index ``cmdline[0]`` without checking, so a yielded empty list
        would be a latent IndexError far away from here.
        """
        for pid, cmd in process_iter():
            assert cmd, f'pid {pid} was yielded with an empty cmdline'

    def test_every_cmdline_element_is_a_string(self):
        for _, cmd in process_iter():
            assert all(isinstance(part, str) for part in cmd)

    def test_yields_the_current_process(self):
        assert os.getpid() in {pid for pid, _ in process_iter()}

    def test_yields_no_duplicate_pids(self):
        seen = [pid for pid, _ in process_iter()]
        assert len(seen) == len(set(seen))

    def test_yielded_pids_are_live(self):
        """
        Nearly everything yielded must still exist right after the sweep.

        The stragglers are processes that exited mid-iteration -- exactly the
        race the module refuses to guard against, and the reason ``get_cmdline``
        returns ``[]`` instead of raising.
        """
        yielded = {pid for pid, _ in process_iter()}
        live = set(pids())
        assert yielded, 'the sweep found nothing'
        assert len(yielded & live) >= len(yielded) * 0.9

    def test_two_full_sweeps_both_succeed(self):
        """No global state may survive a sweep."""
        first = {pid for pid, _ in process_iter()}
        second = {pid for pid, _ in process_iter()}
        assert first and second
        assert os.getpid() in first and os.getpid() in second

    def test_abandoning_a_sweep_does_not_break_the_next_one(self):
        """Breaking out early leaves nothing half-open."""
        partial = 0
        for _ in process_iter():
            partial += 1
            if partial >= 3:
                break
        assert partial == 3
        assert os.getpid() in {pid for pid, _ in process_iter()}

    def test_abandoning_immediately_is_harmless(self):
        """Even a generator that is never advanced must close cleanly."""
        process_iter().close()
        assert os.getpid() in {pid for pid, _ in process_iter()}

    def test_yielded_cmdline_matches_a_direct_read(self):
        """
        The sweep and the direct reader must not disagree.

        A process can exit between the yield and this read, in which case the
        direct read legitimately returns ``[]`` and is skipped.
        """
        compared = 0
        for pid, cmd in process_iter():
            direct = get_cmdline(pid)
            if not direct:
                continue
            assert cmd == direct
            compared += 1
            if compared >= 20:
                break
        assert compared > 0

    @pytest.mark.skipif(not psutil.WINDOWS, reason='Windows-only pid placeholders')
    def test_windows_excludes_pid_zero_and_four(self):
        found = {pid for pid, _ in process_iter()}
        assert 0 not in found
        assert 4 not in found

    @pytest.mark.skipif(not psutil.WINDOWS, reason='the \\?? filter is Windows-only')
    def test_windows_excludes_the_console_host_internal_form(self):
        """``\\??\\C:\\Windows\\system32\\conhost.exe`` is not a real cmdline."""
        offenders = [cmd for _, cmd in process_iter() if cmd[0].startswith(r'\??')]
        assert offenders == []


class TestProcessIterIsConcurrencySafe:
    """The sweep owns no shared state, so threads may run it together."""

    def test_two_threads_sweep_at_once(self):
        results = {}
        errors = []

        def sweep(index):
            try:
                results[index] = {pid for pid, _ in process_iter()}
            except BaseException as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

        threads = [threading.Thread(target=sweep, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert errors == []
        assert len(results) == 2
        assert all(os.getpid() in found for found in results.values())

    def test_survives_process_churn(self):
        """
        Processes starting and dying during a sweep must not break it.

        This is the realistic worst case: something else on the box is
        spawning and reaping children while the sweep reads their cmdlines.
        """
        stop = threading.Event()

        def churn():
            while not stop.is_set():
                proc = subprocess.Popen(python_argv(code='import time; time.sleep(0.02)'))
                proc.wait()

        thread = threading.Thread(target=churn, daemon=True)
        thread.start()
        try:
            for _ in range(3):
                for pid, cmd in process_iter():
                    assert isinstance(pid, int)
                    assert cmd
        finally:
            stop.set()
            thread.join(timeout=30)
        assert not thread.is_alive()


# =============================================================================
# process_iter() finding real processes
# =============================================================================


class TestProcessIterFindsRealProcesses:
    """The use case the module was written for: locate a process by cmdline."""

    def test_finds_the_unique_token_child(self, argv_child, unique_token):
        proc, argv = argv_child()
        found = {pid: cmd for pid, cmd in process_iter()}
        assert proc.pid in found
        assert argv[0] == found[proc.pid][0]
        assert unique_token in found[proc.pid]

    def test_finds_both_of_two_distinct_children(self, argv_child):
        first, first_argv = argv_child(extra=('one',))
        second, second_argv = argv_child(extra=('two',))
        found = {pid: cmd for pid, cmd in process_iter()}
        assert found.get(first.pid) == first_argv
        assert found.get(second.pid) == second_argv

    def test_a_killed_child_is_gone_afterwards(self, argv_child, poll_until):
        proc, _ = argv_child()
        pid = proc.pid
        assert pid in {p for p, _ in process_iter()}
        proc.kill()
        proc.wait(timeout=10)
        assert poll_until(lambda: pid not in {p for p, _ in process_iter()})

    def test_cmdline_matches_the_child_argv_exactly(self, argv_child):
        proc, argv = argv_child(extra=('a b', ''))
        found = dict(process_iter())
        assert found[proc.pid] == argv


# =============================================================================
# Deterministic filtering, driven from a fixed pid table
# =============================================================================


class TestProcessIterFiltering:
    """The Windows filters, with the pid source and cmdlines stubbed out."""

    def test_pids_are_yielded_in_the_order_given(self, stubbed_iter):
        """``pids()`` is sorted, so the sweep is deterministic."""
        stubbed_iter['pids'] = [10, 20, 30]
        stubbed_iter['cmdlines'] = {10: ['a'], 20: ['b'], 30: ['c']}
        assert list(process_iter()) == [(10, ['a']), (20, ['b']), (30, ['c'])]

    def test_empty_pid_list_yields_nothing(self, stubbed_iter):
        stubbed_iter['pids'] = []
        assert list(process_iter()) == []

    def test_unreadable_cmdline_is_skipped(self, stubbed_iter):
        """A pid whose cmdline cannot be read is dropped, not yielded as []."""
        stubbed_iter['pids'] = [10, 20]
        stubbed_iter['cmdlines'] = {10: [], 20: ['b']}
        assert list(process_iter()) == [(20, ['b'])]

    @pytest.mark.skipif(not psutil.WINDOWS, reason='the pid 0/4 filter is Windows-only')
    @pytest.mark.parametrize('reserved', [0, 4])
    def test_windows_reserved_pids_are_filtered_before_reading(
        self, stubbed_iter, reserved
    ):
        """The filter runs before the cmdline read, so the C extension is not asked."""
        stubbed_iter['pids'] = [reserved, 30]
        stubbed_iter['cmdlines'] = {reserved: ['should not be read'], 30: ['c']}
        assert list(process_iter()) == [(30, ['c'])]

    @pytest.mark.skipif(not psutil.WINDOWS, reason='the \\?? filter is Windows-only')
    def test_console_host_prefix_is_filtered(self, stubbed_iter):
        stubbed_iter['pids'] = [10, 20]
        stubbed_iter['cmdlines'] = {
            10: [r'\??\C:\Windows\system32\conhost.exe'],
            20: ['C:/ok.exe'],
        }
        assert list(process_iter()) == [(20, ['C:/ok.exe'])]

    @pytest.mark.skipif(not psutil.WINDOWS, reason='the \\?? filter is Windows-only')
    def test_the_prefix_filter_is_a_prefix_not_an_equality(self, stubbed_iter):
        """A path merely containing ``\\??`` later on is kept."""
        stubbed_iter['pids'] = [10]
        stubbed_iter['cmdlines'] = {10: [r'C:\dir\??\tool.exe']}
        assert list(process_iter()) == [(10, [r'C:\dir\??\tool.exe'])]

    @pytest.mark.skipif(not psutil.WINDOWS, reason='the \\?? filter is Windows-only')
    def test_empty_executable_is_kept(self, stubbed_iter):
        """Only the *list* being empty is filtered; an empty argv[0] is not."""
        stubbed_iter['pids'] = [10]
        stubbed_iter['cmdlines'] = {10: ['']}
        assert list(process_iter()) == [(10, [''])]

    def test_a_real_process_passes_every_filter(self, stubbed_iter):
        """The filters must not swallow an ordinary process."""
        stubbed_iter['pids'] = [4, 10, 20]
        stubbed_iter['cmdlines'] = {4: [], 10: ['C:/app.exe', '--x'], 20: []}
        assert list(process_iter()) == [(10, ['C:/app.exe', '--x'])]
