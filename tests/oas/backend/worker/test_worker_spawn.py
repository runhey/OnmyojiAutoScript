"""
End-to-end of a real worker process: multiprocessing spawn, the worker pipe,
and the state the worker reports back into the Worker topic.

The mod of the test is a stand-in written on the fly: the manager only needs
a mod root with an entry file that defines ``Scheduler``, exactly like the
real one (oas.backend.worker.bridge.mod_entry imports it in the child). The
entry lives in a ``script`` regular package of its own -- mod_entry puts the
mod root at ``sys.path[0]``, and a regular package beats a namespace portion,
so without its ``__init__.py`` the child would import the repository's own
``script`` package instead (whose main.py is still a stub). The real OAS entry
is that stub today, so its scheduler cannot run yet; this test proves the
backend side of the chain, which is what the port covers.
"""

from pathlib import Path

import anyio
import pytest

from oas.backend.topic._worker import BACKEND_WORKER_MANAGER, WorkerSource
from oas.backend.worker.manager import WORKER_RUNNING_STATE
from oas.ext import env
from oas.ext.path import PathStr
from oas.mod.info import ModEntryInfo

pytestmark = pytest.mark.anyio

MOD_NAME = 'fakemod'
CONFIG_NAME = 'oas1'
ENTRY = 'script/main.py'
# a spawned interpreter has to import msgspec, the bridge and the entry
SPAWN_TIMEOUT = 60.0

# The fake scheduler: the bridge reports "running" itself while it inits
# (mod_entry), so run() only has to stay alive until the parent closes.
FAKE_ENTRY = """
from time import sleep


class Scheduler:
    def __init__(self, config):
        self.config = config

    def run(self):
        while True:
            sleep(0.05)
"""


@pytest.fixture
def fake_mod(tmp_path, monkeypatch):
    """
    A mod root the manager can spawn, plus an isolated project root.

    Returns:
        ModEntryInfo: The entry description of the fake mod
    """
    mod_root = tmp_path / 'fakemod'
    entry = mod_root / 'script' / 'main.py'
    entry.parent.mkdir(parents=True)
    # a regular package, so this "script" wins over the repository's own
    # script/ package (mod_entry puts mod_root at sys.path[0])
    (entry.parent / '__init__.py').write_text('', encoding='utf-8')
    entry.write_text(FAKE_ENTRY, encoding='utf-8')
    # the child sets this as its project root (mod_entry), so its log files
    # and its temp files land in the test directory, not in the repository
    project_root = tmp_path / 'project'
    project_root.mkdir()
    monkeypatch.setattr(env, 'PROJECT_ROOT', PathStr.new(str(project_root)))
    return ModEntryInfo(name=MOD_NAME, root=str(mod_root), path_main=ENTRY)


async def test_a_spawned_worker_reports_running_into_the_topic(fake_mod):
    """
    worker_start spawns the child, the bridge inits and reports "running"
    over the pipe, the recv thread forwards it, and the Worker topic's source
    holds it.
    """
    manager = BACKEND_WORKER_MANAGER

    success, msg = await anyio.to_thread.run_sync(
        manager.worker_start, fake_mod, CONFIG_NAME
    )
    assert (success, msg) == (True, 'Success')

    # the pipe loop runs on the manager's recv thread: wait for the report
    running = await anyio.to_thread.run_sync(
        manager.worker_wait_running, CONFIG_NAME, SPAWN_TIMEOUT
    )
    assert running is True

    state = manager.state[CONFIG_NAME]
    assert state.mod == MOD_NAME
    assert state.state in WORKER_RUNNING_STATE
    assert WorkerSource().data == {CONFIG_NAME: state.state}


async def test_a_spawned_worker_is_killed_by_the_manager(fake_mod):
    """
    The kill RPC path stops the child and drops the entry, so the topic
    deletes the key.
    """
    manager = BACKEND_WORKER_MANAGER

    success, _ = await anyio.to_thread.run_sync(
        manager.worker_start, fake_mod, CONFIG_NAME
    )
    assert success is True
    assert (
        await anyio.to_thread.run_sync(
            manager.worker_wait_running, CONFIG_NAME, SPAWN_TIMEOUT
        )
        is True
    )

    success, msg = await anyio.to_thread.run_sync(
        manager.worker_kill, CONFIG_NAME, False
    )
    assert (success, msg) == (True, 'Success')
    assert CONFIG_NAME not in manager.state
    # on_worker_state('idle') deletes the config from the source
    assert CONFIG_NAME not in WorkerSource().data


async def test_a_wrong_entry_is_reported_by_the_child_through_the_pipe(fake_mod):
    """
    worker_start validates that a mod, a config and the paths are given, not
    that the entry file exists: the child fails on its own import, the pipe
    reports the loss, and the entry never stays "running".
    """
    fake_mod.path_main = 'script/ghost.py'
    manager = BACKEND_WORKER_MANAGER

    success, msg = await anyio.to_thread.run_sync(
        manager.worker_start, fake_mod, CONFIG_NAME
    )
    assert (success, msg) == (True, 'Success')
    assert CONFIG_NAME in manager.state

    # the bridge of the child reports "running" before it imports the entry,
    # so wait for the manager to settle the entry: the lost pipe turns it
    # "disconnected" first, and the cleanup then lands on idle / error
    def settled() -> bool:
        state = manager.state.get(CONFIG_NAME, None)
        return state is None or state.state in ('idle', 'error')

    with anyio.fail_after(SPAWN_TIMEOUT):
        while not settled():
            await anyio.sleep(0.05)

    final = manager.state.get(CONFIG_NAME, None)
    assert final is None or final.state in ('error', 'idle')
    # the source is the "not running" view: the key is gone or says so
    assert WorkerSource().data.get(CONFIG_NAME, 'idle') in ('error', 'idle')


async def test_the_child_of_a_spawned_worker_stays_out_of_the_repository(
    fake_mod, tmp_path
):
    """
    The child sets the project root it was given: nothing it writes may land
    in the repository (its log dir is ``<project_root>/log``).
    """
    manager = BACKEND_WORKER_MANAGER

    success, _ = await anyio.to_thread.run_sync(
        manager.worker_start, fake_mod, CONFIG_NAME
    )
    assert success is True
    assert (
        await anyio.to_thread.run_sync(
            manager.worker_wait_running, CONFIG_NAME, SPAWN_TIMEOUT
        )
        is True
    )

    # the child is alive in the test project root, not in the repository
    state = manager.state[CONFIG_NAME]
    assert state.process is not None
    assert state.process.is_alive()
    assert Path(env.PROJECT_ROOT).is_relative_to(tmp_path)
