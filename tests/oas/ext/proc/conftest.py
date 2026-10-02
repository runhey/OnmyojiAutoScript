"""
Shared fixtures for the ``oas.ext.proc`` tests.

``oas.ext.proc`` wraps psutil's platform C extensions directly instead of going
through ``psutil.Process``, so almost everything is testable against *real*
processes: the tests spawn short-lived children and read their real cmdlines
rather than mocking psutil. That is why the module exists at all -- it is the
fast path used to enumerate and kill emulator processes.

The one thing a real host cannot reach is the *other* platforms' code. psutil
decides the platform when it is imported, and on Windows the POSIX C extensions
do not merely behave differently, they do not exist::

    >>> import psutil._psutil_linux
    ModuleNotFoundError: No module named 'psutil._psutil_linux'

``load_fake_proc`` closes that gap. It forces psutil's platform flags, injects
stub C-extension modules into ``sys.modules`` and imports a *private copy* of
the whole ``oas.ext.proc`` package under a throwaway name. Because the real
``oas.ext.proc`` modules are never reloaded, their identity is preserved -- the
re-export identity asserted in ``test_proc_api.py`` cannot be broken by a
platform test that ran first.
"""

import importlib.util
import os
import subprocess
import sys
import time
import types
import uuid

import psutil
import pytest

import oas.ext.proc as _real_proc

PROC_DIR = os.path.dirname(os.path.abspath(_real_proc.__file__))

#: Every psutil platform flag the modules branch on, plus the BSD sub-flags.
PSUTIL_FLAGS = ('LINUX', 'WINDOWS', 'MACOS', 'BSD', 'SUNOS', 'AIX', 'POSIX', 'OPENBSD', 'NETBSD')

_FAKE_ALIAS_ROOT = '_oas_fake_proc'

#: Child code that stays alive until the test teardown kills it.
SLEEP_CODE = 'import time; time.sleep(30.0)'


# =============================================================================
# Real-process helpers
# =============================================================================


def python_argv(extra=(), code=SLEEP_CODE):
    """
    Build a ``python -c <code> [extra...]`` argv.

    Args:
        extra (Iterable[str]): extra arguments, appended verbatim
        code (str): the program the child runs

    Returns:
        list[str]: argv that starts a live child
    """
    return [sys.executable, '-c', code, *extra]


@pytest.fixture
def child_factory():
    """
    Spawn short-lived children that are always killed and reaped afterwards.

    Returns:
        callable: spawn(argv=None) -> subprocess.Popen
            With no argv the child runs SLEEP_CODE.
    """
    spawned = []

    def spawn(argv=None):
        proc = subprocess.Popen(argv if argv is not None else python_argv())
        spawned.append(proc)
        return proc

    yield spawn

    for proc in spawned:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - a stuck child
            pass


@pytest.fixture
def dead_pid(child_factory):
    """
    A pid that is guaranteed to be dead.

    The child is killed *and* reaped before the pid is handed out, so a
    ``NoSuchProcess``-style error is the expected outcome. The OS may recycle
    the pid later, which is why the tests that use this assert "returns an
    empty result and never raises" rather than a specific error path.

    Returns:
        int: the dead pid
    """
    proc = child_factory()
    pid = proc.pid
    proc.kill()
    proc.wait(timeout=10)
    return pid


@pytest.fixture
def unique_token():
    """A string that cannot collide with any other live process on the host."""
    return f'oas-proc-{uuid.uuid4().hex}'


@pytest.fixture
def argv_child(child_factory, unique_token):
    """
    Spawn a child whose full argv is known exactly.

    Returns:
        callable: make(extra=()) -> (subprocess.Popen, list[str])
            The argv is ``python -c SLEEP_CODE <unique_token> <extra...>``,
            which makes ``get_cmdline(child.pid) == argv`` a valid assertion.
    """
    def make(extra=()):
        argv = python_argv(extra=(unique_token, *extra))
        return child_factory(argv), argv

    return make


@pytest.fixture
def poll_until():
    """
    Poll a predicate until it holds, without ever sleeping longer than asked.

    Returns:
        callable: poll_until(predicate, timeout=5.0, interval=0.01) -> bool
    """
    def poll(predicate, timeout=5.0, interval=0.01):
        deadline = time.monotonic() + timeout
        while True:
            if predicate():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(interval)

    return poll


# =============================================================================
# Faked-platform helpers
# =============================================================================


class CallRecorder:
    """
    A stand-in for a C-extension callable that records how it was called.

    Args:
        result: value returned by every call
        error: exception instance (or class) raised by every call instead

    Attributes:
        calls (list[tuple[tuple, dict]]): one entry per call
    """

    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            # ``raise`` accepts both an instance and a class, and re-raising the
            # same instance is what the "err is the very exception" assertions
            # in test_nice/test_sig rely on.
            raise self.error
        return self.result

    @property
    def call_count(self):
        return len(self.calls)

    @property
    def last_call(self):
        """The most recent ``(args, kwargs)`` pair."""
        return self.calls[-1]


def stub_cext(name, **members):
    """
    Build a stub psutil C-extension module carrying the given members.

    Args:
        name (str): the dotted module name, e.g. ``psutil._psutil_linux``
        **members: attributes to set on the stub

    Returns:
        types.ModuleType: the stub, ready for ``load_fake_proc(modules=...)``
    """
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


class FakeProcFile:
    """
    A stand-in for the file object ``psutil._common.open_text`` returns.

    Only ``read()`` and the context-manager protocol are used by the LINUX
    branch of ``cmd.py``, so that is all this implements.
    """

    def __init__(self, data):
        self.data = data
        self.closed = False

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.closed = True
        return False


@pytest.fixture
def load_fake_proc(monkeypatch):
    """
    Import a private copy of ``oas.ext.proc`` bound to a faked psutil platform.

    Every psutil platform flag is forced to exactly what ``flags`` says, the
    stub C extensions are installed into ``sys.modules`` (and onto the
    ``psutil`` module, which is what ``import psutil.X as Y`` actually binds),
    and then ``__init__.py`` -- or a single submodule -- is executed under a
    throwaway module name. The throwaway modules are dropped on teardown.

    Returns:
        callable: load(flags=(), modules=None, module=None) -> module
            flags (Iterable[str]): psutil flags to turn **on**; all others off
            modules (dict[str, ModuleType]): stubs keyed by psutil dotted name
            module (str): load only this submodule instead of the package
                ``__init__``. Needed for the per-file ``NotImplementedError``
                branches, because the package ``__init__`` would trip over the
                first submodule that has no platform to bind to.
    """
    aliases = []

    def load(flags=(), modules=None, module=None):
        for flag in PSUTIL_FLAGS:
            monkeypatch.setattr(psutil, flag, flag in flags, raising=False)

        for dotted, stub in (modules or {}).items():
            monkeypatch.setitem(sys.modules, dotted, stub)
            parent, _, leaf = dotted.rpartition('.')
            if parent == 'psutil':
                monkeypatch.setattr(psutil, leaf, stub, raising=False)

        suffix = module or '__init__'
        alias = f'{_FAKE_ALIAS_ROOT}_{suffix}_{len(aliases)}'
        aliases.append(alias)
        path = os.path.join(PROC_DIR, f'{suffix}.py')

        if module is None:
            spec = importlib.util.spec_from_file_location(
                alias, path, submodule_search_locations=[PROC_DIR]
            )
        else:
            spec = importlib.util.spec_from_file_location(alias, path)

        loaded = importlib.util.module_from_spec(spec)
        # The parent must be importable by name for the relative imports
        # (``from .cmd import get_cmdline``) inside the package to resolve.
        sys.modules[alias] = loaded
        spec.loader.exec_module(loaded)
        return loaded

    yield load

    for alias in aliases:
        for name in [n for n in sys.modules if n == alias or n.startswith(alias + '.')]:
            del sys.modules[name]
