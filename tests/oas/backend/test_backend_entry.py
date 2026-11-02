"""
Tests for the backend child entry (``oas/backend/entry.py``).

The entry runs in the backend child: it stashes the pipe on ``builtins``, tells
the supervisor the spawn handshake is done, seeds the token window, then hands
over to the server layer. Every test replaces the entry callable, so no server
is started here; the served chain (spawn -> bind -> token -> stop) is covered by
the probe in ``.portcheck/probe_entry.py``.
"""

import builtins
import io
import os
import signal
import sys

import pytest

from oas.backend.entry import backend_process_entry
from oas.backend.mpipe.token_backend import token_table


class FakeConn:
    """
    Pipe end stub: records what the backend sends, or fails like a broken pipe.
    """

    def __init__(self, fail=False):
        """
        Args:
            fail (bool): Raise EOFError from send_bytes, like a dead supervisor
        """
        self.sent = []
        self.fail = fail

    def send_bytes(self, data):
        """
        Args:
            data (bytes): The message the backend sends
        """
        if self.fail:
            raise EOFError('supervisor gone')
        self.sent.append(data)


@pytest.fixture(autouse=True)
def clean_process_state(monkeypatch):
    """
    Undo the process-wide edits backend_process_entry makes.
    """
    monkeypatch.setattr(builtins, '__mpipe_conn__', None, raising=False)
    stdin = sys.stdin
    tokens = token_table._tokens
    yield
    sys.stdin = stdin
    token_table._tokens = tokens


def test_entry_stashes_the_pipe_and_signals_the_spawn():
    """
    The first thing the child does is publish the pipe and report the spawn
    handshake, so the supervisor may start its stdin listener.
    """
    conn = FakeConn()
    calls = []

    def entry_fn(args):
        calls.append(args)

    backend_process_entry(conn, ['--root', 'x'], entry_fn)

    assert builtins.__mpipe_conn__ is conn
    assert conn.sent == [b'command:spawned']
    assert calls == [['--root', 'x']]


def test_entry_absorbs_a_dead_supervisor():
    """
    A supervisor that already exited must not stop the backend from serving.
    """
    conn = FakeConn(fail=True)
    calls = []

    backend_process_entry(conn, None, lambda args: calls.append(args))

    assert builtins.__mpipe_conn__ is conn
    assert len(calls) == 1


def test_entry_seeds_the_token_window_before_the_backend_runs():
    """
    The spawn args carry the announced-and-acked tokens, and the child is their
    single writer: the table must already hold them when the server starts, so
    a request that arrives during startup is checked against them.
    """
    seen = []

    def entry_fn(args):
        seen.append((token_table.verify('T1'), token_table.verify('T2')))

    backend_process_entry(FakeConn(), None, entry_fn, tokens=('T1', 'T2'))

    assert seen == [(True, True)]


def test_entry_ignores_signals_on_win32_only(monkeypatch):
    """
    On win32 the signal reaches the whole process group, so the backend ignores
    SIGINT / SIGBREAK and waits for the supervisor's stop command; elsewhere it
    takes them, like upstream.
    """
    installed = []
    monkeypatch.setattr(signal, 'signal', lambda sig, handler: installed.append(sig))

    monkeypatch.setattr(sys, 'platform', 'win32')
    backend_process_entry(FakeConn(), None, lambda args: None)
    assert installed == [signal.SIGINT, signal.SIGBREAK]

    installed.clear()
    monkeypatch.setattr(sys, 'platform', 'linux')
    backend_process_entry(FakeConn(), None, lambda args: None)
    assert installed == []


def test_entry_points_stdin_at_devnull():
    """
    The child inherits the supervisor's stdin pipe and never reads it, so point
    it at devnull instead of leaving it able to steal commands.
    """
    assert sys.stdin is not None

    backend_process_entry(FakeConn(), None, lambda args: None)

    assert isinstance(sys.stdin, io.TextIOWrapper)
    assert sys.stdin.name == os.devnull


def test_entry_reports_a_fatal_backend_error(capsys):
    """
    An unexpected error is printed and swallowed: the supervisor owns the
    restart decision, so the child must not add a second failure path.
    """

    def entry_fn(args):
        raise RuntimeError('boom')

    backend_process_entry(FakeConn(), None, entry_fn)

    captured = capsys.readouterr()
    assert '[Backend] Fatal error: boom' in captured.out
    # the traceback goes to stderr, it is the diagnostic half of the report
    assert 'RuntimeError: boom' in captured.err
