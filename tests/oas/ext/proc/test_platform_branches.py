"""
Platform-branch tests for ``oas.ext.proc``.

psutil picks its platform at import time, so on a Windows host the LINUX,
MACOS, BSD, SUNOS and AIX branches of ``cmd.py``/``nice.py``/``sig.py`` are
dead code -- and their C extensions are not even importable. These tests load a
private copy of the package against a faked psutil platform
(see ``conftest.load_fake_proc``) so every branch is actually executed.

The point is not coverage theatre. Two of these branches hold real logic that
no host-conditional skip would ever reach:

* the LINUX branch re-implements the ``/proc/<pid>/cmdline`` parsing, including
  the "args are space-separated even though the terminator is NUL" fallback for
  processes that call ``setproctitle()`` (psutil issue #1179)
* the SUNOS branch called ``get_procfs_path()`` without importing it, so it
  raised ``NameError`` on every call. ``test_sunos_*`` pins the fix.
"""

import sys

import psutil
import psutil._common as psutil_common
import pytest
from conftest import CallRecorder, FakeProcFile, stub_cext

# =============================================================================
# cmd.py -- LINUX branch: the /proc/<pid>/cmdline parsing
# =============================================================================


@pytest.fixture
def linux_cmd(load_fake_proc, monkeypatch):
    """
    The ``cmd`` module loaded as if the host were Linux, reading in memory.

    ``open_text`` and ``PROCFS_PATH`` are stubbed on *psutil* rather than on the
    loaded module, so that the module's own ``from psutil._common import ...``
    line is genuinely exercised. Assigning ``module.open_text`` after the load
    would work just as well and would hide a deleted import.

    Returns:
        (module, state): ``state['data']`` holds the raw bytes the next
            ``cmdline()`` call reads, and ``state['opened']`` records the paths
            that were passed to ``open_text``.
    """
    state = {'data': b'', 'opened': []}

    def open_text(path):
        state['opened'].append(path)
        return FakeProcFile(state['data'])

    monkeypatch.setattr(psutil, 'PROCFS_PATH', '/proc', raising=False)
    monkeypatch.setattr(psutil_common, 'open_text', open_text)

    module = load_fake_proc(
        {'LINUX', 'POSIX'},
        modules={'psutil._psutil_linux': stub_cext('psutil._psutil_linux')},
        module='cmd',
    )
    return module, state


class TestCmdLinuxBranch:
    """The LINUX branch parses /proc/<pid>/cmdline by hand."""

    def test_nul_separated_args(self, linux_cmd):
        """Args separated by NUL and NUL-terminated are split on NUL."""
        module, state = linux_cmd
        state['data'] = 'python\x00script.py\x00--flag\x00'
        assert module.get_cmdline(1234) == ['python', 'script.py', '--flag']

    def test_missing_terminator_switches_the_separator(self, linux_cmd):
        """
        A missing trailing NUL makes the parser assume space separation.

        This is the real upstream heuristic: ``sep`` is chosen from the last
        byte alone, so a NUL-separated cmdline without its terminator collapses
        into a single element that still contains the NUL bytes. Pinned here
        because it looks like a bug and is not one to "fix" silently.
        """
        module, state = linux_cmd
        state['data'] = 'python\x00script.py'
        assert module.get_cmdline(1234) == ['python\x00script.py']

    def test_space_separated_args(self, linux_cmd):
        """A process that rewrote its title has space-separated args."""
        module, state = linux_cmd
        state['data'] = 'python script.py --flag'
        assert module.get_cmdline(1234) == ['python', 'script.py', '--flag']

    def test_space_separated_with_trailing_space(self, linux_cmd):
        """A trailing space separator is stripped before splitting."""
        module, state = linux_cmd
        state['data'] = 'python script.py '
        assert module.get_cmdline(1234) == ['python', 'script.py']

    def test_single_arg_containing_spaces_is_split(self, linux_cmd):
        """
        psutil issue #1179: a NUL terminator with a single space-containing
        element means the args really are space-separated.
        """
        module, state = linux_cmd
        state['data'] = 'python script.py\x00'
        assert module.get_cmdline(1234) == ['python', 'script.py']

    def test_empty_data_returns_empty_list(self, linux_cmd):
        """An empty cmdline (zombie) yields [] instead of raising."""
        module, state = linux_cmd
        state['data'] = ''
        assert module.get_cmdline(1234) == []

    def test_reads_from_procfs_path(self, linux_cmd):
        """The file path is built from get_procfs_path() and the pid."""
        module, state = linux_cmd
        state['data'] = 'python\x00'
        module.get_cmdline(4321)
        assert state['opened'] == ['/proc/4321/cmdline']

    def test_custom_procfs_path_is_honoured(self, linux_cmd, monkeypatch):
        """A redirected PROCFS_PATH is used for the file lookup."""
        module, state = linux_cmd
        monkeypatch.setattr(psutil, 'PROCFS_PATH', '/host/proc')
        state['data'] = 'python\x00'
        module.get_cmdline(7)
        assert state['opened'] == ['/host/proc/7/cmdline']

    def test_non_ascii_bytes_survive(self, linux_cmd):
        """Bytes are decoded by open_text, and unicode args pass through."""
        module, state = linux_cmd
        state['data'] = 'python\x00--name=\u4e2d\u6587 \u53c2\u6570\x00'
        assert module.get_cmdline(1234) == ['python', '--name=\u4e2d\u6587 \u53c2\u6570']

    def test_missing_file_returns_empty_list(self, linux_cmd):
        """A vanished process (open_text raises) is swallowed into []."""
        module, _ = linux_cmd

        def boom(path):
            raise FileNotFoundError(path)

        module.open_text = boom
        assert module.get_cmdline(1234) == []


# =============================================================================
# cmd.py -- the thin per-platform wrappers
# =============================================================================


class TestCmdWindowsBranch:
    """The Windows branch reads the cmdline out of the target's PEB."""

    @pytest.fixture
    def windows_cmd(self, load_fake_proc):
        recorder = CallRecorder(result=['C:\\app.exe', '--arg'])
        module = load_fake_proc(
            {'WINDOWS'},
            modules={
                'psutil._psutil_windows': stub_cext(
                    'psutil._psutil_windows', proc_cmdline=recorder
                )
            },
            module='cmd',
        )
        return module, recorder

    def test_delegates_to_proc_cmdline_with_peb(self, windows_cmd):
        """proc_cmdline is called with use_peb=True -- the fast path."""
        module, recorder = windows_cmd
        module.get_cmdline(1234)
        assert recorder.last_call == ((1234,), {'use_peb': True})

    def test_result_is_passed_through_unchanged(self, windows_cmd):
        """The C extension's list is returned as-is."""
        module, _ = windows_cmd
        assert module.get_cmdline(1234) == ['C:\\app.exe', '--arg']

    def test_get_executable_returns_first_element(self, windows_cmd):
        """get_executable is cmdline[0]."""
        module, _ = windows_cmd
        assert module.get_executable(1234) == 'C:\\app.exe'


class TestCmdMacosBranch:
    """The macOS branch uses the same entry point without the PEB flag."""

    def test_delegates_without_peb_kwarg(self, load_fake_proc):
        recorder = CallRecorder(result=['/usr/bin/app'])
        module = load_fake_proc(
            {'MACOS', 'POSIX'},
            modules={
                'psutil._psutil_osx': stub_cext('psutil._psutil_osx', proc_cmdline=recorder)
            },
            module='cmd',
        )
        assert module.get_cmdline(99) == ['/usr/bin/app']
        assert recorder.last_call == ((99,), {})


class TestCmdBsdBranch:
    """The BSD branch splits into OpenBSD, NetBSD and the rest."""

    @pytest.fixture
    def bsd(self, load_fake_proc):
        def build(**flags):
            recorder = CallRecorder(result=['/usr/bin/app', 'x'])
            module = load_fake_proc(
                {'BSD', 'POSIX', *flags},
                modules={
                    'psutil._psutil_bsd': stub_cext('psutil._psutil_bsd', proc_cmdline=recorder)
                },
                module='cmd',
            )
            return module, recorder

        return build

    def test_openbsd_pid_zero_short_circuits(self, bsd):
        """OpenBSD pid 0 crashes the C extension, so it returns [] instead."""
        module, recorder = bsd(OPENBSD=True)
        assert module.get_cmdline(0) == []
        assert recorder.call_count == 0

    def test_openbsd_nonzero_pid_delegates(self, bsd):
        """Any other pid on OpenBSD still goes to the C extension."""
        module, recorder = bsd(OPENBSD=True)
        assert module.get_cmdline(42) == ['/usr/bin/app', 'x']
        assert recorder.last_call == ((42,), {})

    def test_netbsd_delegates(self, bsd):
        """NetBSD hits the documented truncated-string path."""
        module, recorder = bsd(NETBSD=True)
        assert module.get_cmdline(42) == ['/usr/bin/app', 'x']
        assert recorder.last_call == ((42,), {})

    def test_freebsd_delegates(self, bsd):
        """Neither OpenBSD nor NetBSD takes the plain else."""
        module, recorder = bsd()
        assert module.get_cmdline(42) == ['/usr/bin/app', 'x']
        assert recorder.call_count == 1


class TestCmdSunosBranch:
    """
    The SUNOS branch previously raised NameError.

    ``get_procfs_path`` was only imported by the LINUX branch, so calling
    ``cmdline()`` here blew up before it ever reached the C extension.

    ``PROCFS_PATH`` is stubbed on psutil, not on the loaded module: if the
    fixture supplied ``module.get_procfs_path`` itself, these tests would pass
    even with the import deleted -- which is exactly the bug they exist to
    catch.
    """

    @pytest.fixture
    def sunos_cmd(self, load_fake_proc, monkeypatch):
        recorder = CallRecorder(result=('app', 'app --flag'))
        monkeypatch.setattr(psutil, 'PROCFS_PATH', '/proc', raising=False)
        module = load_fake_proc(
            {'SUNOS', 'POSIX'},
            modules={
                'psutil._psutil_sunos': stub_cext(
                    'psutil._psutil_sunos', proc_name_and_args=recorder
                )
            },
            module='cmd',
        )
        return module, recorder

    def test_sunos_does_not_raise_name_error(self, sunos_cmd):
        """The fix: get_procfs_path is importable in this branch too."""
        module, _ = sunos_cmd
        assert module.get_cmdline(1234) == ['app', '--flag']

    def test_sunos_passes_procfs_path_to_cext(self, sunos_cmd):
        """The resolved procfs path is forwarded to proc_name_and_args."""
        module, recorder = sunos_cmd
        module.get_cmdline(1234)
        assert recorder.last_call == ((1234, '/proc'), {})

    def test_sunos_splits_second_tuple_element(self, sunos_cmd):
        """Only element [1] is split -- element [0] is the process name."""
        module, recorder = sunos_cmd
        recorder.result = ('ignored', 'a b c')
        assert module.get_cmdline(1) == ['a', 'b', 'c']


class TestCmdAixBranch:
    """The AIX branch is a plain delegation to proc_args."""

    def test_delegates_to_proc_args(self, load_fake_proc):
        recorder = CallRecorder(result=['/usr/bin/app'])
        module = load_fake_proc(
            {'AIX', 'POSIX'},
            modules={'psutil._psutil_aix': stub_cext('psutil._psutil_aix', proc_args=recorder)},
            module='cmd',
        )
        assert module.get_cmdline(11) == ['/usr/bin/app']
        assert recorder.last_call == ((11,), {})


class TestUnsupportedPlatform:
    """Every module refuses to load on a platform psutil does not cover."""

    @pytest.mark.parametrize('module', ['cmd', 'nice', 'sig'])
    def test_not_implemented_error(self, load_fake_proc, module):
        """With no platform flag set, the module raises at import time."""
        with pytest.raises(NotImplementedError, match='is not supported'):
            load_fake_proc(set(), module=module)

    def test_message_names_the_platform(self, load_fake_proc):
        """The error message carries sys.platform, which makes it diagnosable."""
        with pytest.raises(NotImplementedError) as excinfo:
            load_fake_proc(set(), module='cmd')
        assert sys.platform in str(excinfo.value)


# =============================================================================
# nice.py -- one branch per platform
# =============================================================================


class TestNiceLinuxBranch:
    """Linux uses the posix getpriority/setpriority syscalls."""

    @pytest.fixture
    def linux_nice(self, load_fake_proc):
        get = CallRecorder(result=0)
        set_ = CallRecorder()
        module = load_fake_proc(
            {'LINUX', 'POSIX'},
            modules={
                'psutil._psutil_posix': stub_cext(
                    'psutil._psutil_posix', getpriority=get, setpriority=set_
                )
            },
            module='nice',
        )
        return module, get, set_

    def test_nice_get_delegates(self, linux_nice):
        module, get, _ = linux_nice
        assert module.nice_get(5) == 0
        assert get.last_call == ((5,), {})

    def test_lower_priority_uses_nice_10(self, linux_nice):
        """On Unix 'lower' means nice=10."""
        module, _, set_ = linux_nice
        assert module.set_lower_process_priority(5) == (True, None)
        assert set_.last_call == ((5, 10), {})

    def test_lowest_priority_uses_nice_19(self, linux_nice):
        """On Unix 'lowest' means nice=19."""
        module, _, set_ = linux_nice
        assert module.set_lowest_process_priority(5) == (True, None)
        assert set_.last_call == ((5, 19), {})


class TestNiceWindowsBranch:
    """Windows uses priority classes instead of nice values."""

    @pytest.fixture
    def windows_nice(self, load_fake_proc):
        get = CallRecorder(result=psutil.NORMAL_PRIORITY_CLASS)
        set_ = CallRecorder()
        module = load_fake_proc(
            {'WINDOWS'},
            modules={
                'psutil._psutil_windows': stub_cext(
                    'psutil._psutil_windows',
                    proc_priority_get=get,
                    proc_priority_set=set_,
                )
            },
            module='nice',
        )
        return module, get, set_

    def test_nice_get_delegates(self, windows_nice):
        module, get, _ = windows_nice
        assert module.nice_get(5) == psutil.NORMAL_PRIORITY_CLASS
        assert get.last_call == ((5,), {})

    def test_lower_uses_below_normal_class(self, windows_nice):
        module, _, set_ = windows_nice
        module.set_lower_process_priority(5)
        assert set_.last_call == ((5, psutil.BELOW_NORMAL_PRIORITY_CLASS), {})

    def test_lowest_uses_idle_class(self, windows_nice):
        module, _, set_ = windows_nice
        module.set_lowest_process_priority(5)
        assert set_.last_call == ((5, psutil.IDLE_PRIORITY_CLASS), {})


@pytest.mark.parametrize(
    'platform_flags, cext_name',
    [
        (('MACOS', 'POSIX'), 'psutil._psutil_osx'),
        (('BSD', 'POSIX'), 'psutil._psutil_bsd'),
        (('AIX', 'POSIX'), 'psutil._psutil_aix'),
    ],
)
class TestNicePosixDelegates:
    """macOS, BSD and AIX all share the posix cext under the cext_posix name."""

    def test_lower_and_lowest_map_to_nice_10_and_19(
        self, load_fake_proc, platform_flags, cext_name
    ):
        set_ = CallRecorder()
        module = load_fake_proc(
            set(platform_flags),
            # macOS/BSD/AIX import _psutil_posix, but cmd.py's platform flag
            # decides which C module exists; only the posix one is used here.
            modules={
                'psutil._psutil_posix': stub_cext(
                    'psutil._psutil_posix',
                    getpriority=CallRecorder(result=0),
                    setpriority=set_,
                )
            },
            module='nice',
        )
        module.set_lower_process_priority(7)
        module.set_lowest_process_priority(7)
        assert set_.calls == [((7, 10), {}), ((7, 19), {})]


class TestNiceSunosBranch:
    """SunOS special-cases pid 2 and 3 and reads the rest from cext_posix."""

    @pytest.fixture
    def sunos_nice(self, load_fake_proc):
        basic_info = CallRecorder(result=[-1, -1, 5])
        posix_get = CallRecorder(result=3)
        posix_set = CallRecorder()
        cext_sunos = stub_cext('pssunos_cext', proc_basic_info=basic_info)
        module = load_fake_proc(
            {'SUNOS', 'POSIX'},
            modules={
                'psutil._psutil_posix': stub_cext(
                    'psutil._psutil_posix', getpriority=posix_get, setpriority=posix_set
                ),
                'psutil._pssunos': stub_cext(
                    'psutil._pssunos',
                    cext=cext_sunos,
                    get_procfs_path=lambda: '/proc',
                    proc_info_map={'nice': 2},
                ),
            },
            module='nice',
        )
        return module, basic_info, posix_get, posix_set

    @pytest.mark.parametrize('pid', [2, 3])
    def test_special_pids_read_from_basic_info(self, sunos_nice, pid):
        """pid 2 and 3 have no priority of their own on SunOS."""
        module, basic_info, posix_get, _ = sunos_nice
        assert module.nice_get(pid) == 5
        assert basic_info.last_call == ((pid, '/proc'), {})
        assert posix_get.call_count == 0

    def test_other_pid_uses_posix(self, sunos_nice):
        module, basic_info, posix_get, _ = sunos_nice
        assert module.nice_get(42) == 3
        assert basic_info.call_count == 0
        assert posix_get.last_call == ((42,), {})

    @pytest.mark.parametrize('pid', [2, 3])
    def test_special_pids_refuse_to_be_lowered(self, sunos_nice, pid):
        """Setting the priority of pid 2/3 raises AccessDenied."""
        module, _, _, posix_set = sunos_nice
        ok, err = module.set_lower_process_priority(pid)
        assert ok is False
        assert isinstance(err, psutil.AccessDenied)
        assert posix_set.call_count == 0

    def test_other_pid_is_settable(self, sunos_nice):
        module, _, _, posix_set = sunos_nice
        assert module.set_lower_process_priority(42) == (True, None)
        assert posix_set.last_call == ((42, 10), {})


# =============================================================================
# sig.py -- POSIX signals vs the Windows force-kill
# =============================================================================


class _FakeSignal:
    """
    A stand-in for the ``signal`` module.

    ``signal.SIGKILL`` does not exist on Windows, so the POSIX branch loaded on
    this host would die of AttributeError before reaching any logic under test.
    The values are the real POSIX ones.
    """

    SIGTERM = 15
    SIGKILL = 9


class _FakeOs:
    """Just enough of ``os`` for ``sig._send_signal``."""

    def __init__(self, recorder):
        self._recorder = recorder

    def kill(self, pid, sig):
        return self._recorder(pid, sig)


class TestSigPosixBranch:
    """On POSIX, terminate and kill are two different signals."""

    @pytest.fixture
    def posix_sig(self, load_fake_proc, monkeypatch):
        module = load_fake_proc({'LINUX', 'POSIX'}, module='sig')
        recorder = CallRecorder()
        monkeypatch.setattr(module, 'os', _FakeOs(recorder))
        monkeypatch.setattr(module, 'signal', _FakeSignal)
        return module, recorder

    def test_terminate_sends_sigterm(self, posix_sig):
        module, recorder = posix_sig
        assert module.process_terminate(4242) == (True, None)
        assert recorder.last_call == ((4242, _FakeSignal.SIGTERM), {})

    def test_kill_sends_sigkill(self, posix_sig):
        module, recorder = posix_sig
        assert module.process_kill(4242) == (True, None)
        assert recorder.last_call == ((4242, _FakeSignal.SIGKILL), {})

    def test_sigterm_and_sigkill_differ(self, posix_sig):
        """The two entry points must not collapse into one signal."""
        module, recorder = posix_sig
        module.process_terminate(1)
        module.process_kill(1)
        signals = [call[0][1] for call in recorder.calls]
        assert signals == [_FakeSignal.SIGTERM, _FakeSignal.SIGKILL]

    def test_negative_pid_is_rejected(self, posix_sig):
        """A negative pid would signal a process group."""
        module, recorder = posix_sig
        ok, err = module.process_kill(-1)
        assert ok is False
        assert isinstance(err, ValueError)
        assert recorder.call_count == 0

    def test_pid_zero_is_rejected(self, posix_sig):
        """pid 0 would signal every process in the caller's group."""
        module, recorder = posix_sig
        ok, err = module.process_terminate(0)
        assert ok is False
        assert isinstance(err, ValueError)
        assert 'PID 0' in str(err)
        assert recorder.call_count == 0


class TestSigWindowsBranch:
    """On Windows both entry points force-kill: there is no SIGTERM."""

    @pytest.fixture
    def windows_sig(self, load_fake_proc):
        recorder = CallRecorder()
        module = load_fake_proc(
            {'WINDOWS'},
            modules={
                'psutil._psutil_windows': stub_cext(
                    'psutil._psutil_windows', proc_kill=recorder
                )
            },
            module='sig',
        )
        return module, recorder

    def test_terminate_uses_proc_kill(self, windows_sig):
        module, recorder = windows_sig
        assert module.process_terminate(1234) == (True, None)
        assert recorder.last_call == ((1234,), {})

    def test_kill_uses_proc_kill(self, windows_sig):
        module, recorder = windows_sig
        assert module.process_kill(1234) == (True, None)
        assert recorder.last_call == ((1234,), {})

    def test_terminate_is_an_alias_for_kill(self, windows_sig):
        """
        The documented Windows contract: terminate == kill.

        Both entry points force-kill through the very same C call -- Windows has
        no SIGTERM to be graceful with. This is checked behaviourally, not by
        comparing code objects, because they are two separate ``def``s.
        """
        module, recorder = windows_sig
        module.process_terminate(1)
        module.process_kill(1)
        assert recorder.calls == [((1,), {}), ((1,), {})]
        assert recorder.call_count == 2


# =============================================================================
# iter.py -- the Windows-only filters
# =============================================================================


class TestIterWindowsBranch:
    """``process_iter`` filters noise on Windows."""

    @pytest.fixture
    def windows_iter(self, load_fake_proc, monkeypatch):
        module = load_fake_proc(
            {'WINDOWS'},
            modules={
                'psutil._psutil_windows': stub_cext(
                    'psutil._psutil_windows', pids=lambda: [0, 4, 8, 9, 10]
                )
            },
        )
        state = {'pids': [0, 4, 8, 9, 10], 'cmdlines': {}}
        monkeypatch.setattr(module.iter, 'pids', lambda: list(state['pids']))
        monkeypatch.setattr(
            module.iter, 'get_cmdline', lambda pid: list(state['cmdlines'].get(pid, []))
        )
        return module.iter, state

    def test_pid_zero_and_four_are_skipped(self, windows_iter):
        """0 and 4 are taskmgr placeholders, not real processes."""
        module, state = windows_iter
        state['cmdlines'] = {0: ['System Idle'], 4: ['System'], 8: ['C:/a.exe']}
        assert list(module.process_iter()) == [(8, ['C:/a.exe'])]

    def test_empty_cmdline_is_skipped(self, windows_iter):
        """A process whose cmdline cannot be read is skipped, not yielded."""
        module, state = windows_iter
        state['cmdlines'] = {8: [], 9: ['C:/b.exe']}
        assert list(module.process_iter()) == [(9, ['C:/b.exe'])]

    def test_conhost_prefix_is_skipped(self, windows_iter):
        """\\??\\ paths are the console host's internal form."""
        module, state = windows_iter
        state['cmdlines'] = {8: [r'\??\C:\Windows\system32\conhost.exe'], 9: ['C:/ok.exe']}
        assert list(module.process_iter()) == [(9, ['C:/ok.exe'])]

    def test_empty_first_element_is_yielded(self, windows_iter):
        """An empty argv[0] is not filtered: only \\?? and emptiness of the list are."""
        module, state = windows_iter
        state['cmdlines'] = {8: ['']}
        assert list(module.process_iter()) == [(8, [''])]

    def test_filters_do_not_hide_a_real_process(self, windows_iter):
        """The unique-token child survives every filter."""
        module, state = windows_iter
        state['cmdlines'] = {
            0: ['System Idle'], 4: ['System'], 8: [],
            9: ['C:/win.exe'], 10: ['python.exe', '--token'],
        }
        assert list(module.process_iter()) == [
            (9, ['C:/win.exe']),
            (10, ['python.exe', '--token']),
        ]

    def test_empty_pid_list_yields_nothing(self, windows_iter):
        module, state = windows_iter
        state['pids'] = []
        assert list(module.process_iter()) == []


class TestIterNonWindowsBranch:
    """The non-Windows branch has no filters beyond readability."""

    @pytest.fixture
    def posix_iter(self, load_fake_proc, monkeypatch):
        # The package __init__ pulls in every submodule, so a faked LINUX host
        # needs the stubs for nice.py and cmd.py as well, not just iter.py.
        module = load_fake_proc(
            {'LINUX', 'POSIX'},
            modules={
                'psutil._psutil_linux': stub_cext('psutil._psutil_linux'),
                'psutil._psutil_posix': stub_cext(
                    'psutil._psutil_posix',
                    getpriority=CallRecorder(result=0),
                    setpriority=CallRecorder(),
                ),
            },
        )
        state = {'pids': [8, 9], 'cmdlines': {}}
        monkeypatch.setattr(module.iter, 'pids', lambda: list(state['pids']))
        monkeypatch.setattr(
            module.iter, 'get_cmdline', lambda pid: list(state['cmdlines'].get(pid, []))
        )
        return module.iter, state

    def test_no_pid_is_filtered(self, posix_iter):
        """PID 0 and 4 are ordinary on POSIX."""
        module, state = posix_iter
        state['pids'] = [0, 4, 8]
        state['cmdlines'] = {0: ['sched'], 4: ['kthreadd'], 8: ['init']}
        assert list(module.process_iter()) == [
            (0, ['sched']),
            (4, ['kthreadd']),
            (8, ['init']),
        ]

    def test_empty_cmdline_is_skipped(self, posix_iter):
        module, state = posix_iter
        state['cmdlines'] = {8: [], 9: ['init']}
        assert list(module.process_iter()) == [(9, ['init'])]

    def test_conhost_prefix_is_not_filtered(self, posix_iter):
        """The \\?? filter is Windows-only."""
        module, state = posix_iter
        state['cmdlines'] = {8: [r'\??\weird'], 9: []}
        assert list(module.process_iter()) == [(8, [r'\??\weird'])]
