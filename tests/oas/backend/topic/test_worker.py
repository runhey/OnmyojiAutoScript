"""
Unit tests of the Worker topic, its source and the event router of the
backend worker manager.

The topic's RPCs only resolve a config into a declared mod and forward the
call to the manager; the tests drive them with a recording stand-in, so the
argument order and the fields the adapter unpacks are pinned without spawning
a process. The real spawn is covered by
tests/oas/backend/worker/test_worker_spawn.py, the wire format by
tests/oas/backend/ws/test_ws_worker.py.
"""

import pytest

from oas.backend.reactive.event import RpcValueError
from oas.backend.topic import worker as worker_topic
from oas.backend.topic._worker import BACKEND_WORKER_MANAGER, WorkerSource
from oas.backend.topic.log import LogCache
from oas.backend.topic.scan import ConfigScanSource
from oas.backend.topic.worker import Worker, get_mod
from oas.backend.worker.event import ConfigEvent
from oas.config.table.scan import ConfigInfo
from oas.mod.info import ModEntryInfo

pytestmark = pytest.mark.anyio

CONN_ID = 'test-conn'
CONFIG_NAME = 'oas1'
MOD_NAME = 'oas'


class FakeManager:
    """
    Records what the topic forwards, instead of spawning a worker.

    Only the five methods the Worker RPCs call are implemented, with the
    manager's signatures.
    """

    def __init__(self):
        self.calls = []
        self.result = (True, '')

    def _record(self, name, *args):
        self.calls.append((name, *args))
        return self.result

    def worker_start(self, mod, config):
        return self._record('start', mod.name, config)

    def worker_scheduler_stop(self, config, restart_resume=False):
        return self._record('scheduler_stop', config, restart_resume)

    def worker_scheduler_continue(self, config):
        return self._record('scheduler_continue', config)

    def worker_kill(self, config, restart_resume=False):
        return self._record('kill', config, restart_resume)

    def worker_force_kill(self, config, restart_resume=False):
        return self._record('force_kill', config, restart_resume)


@pytest.fixture(autouse=True)
def clear_singletons():
    """
    The source, its manager and the log cache all outlive a test.
    """
    WorkerSource.singleton_clear()
    LogCache.singleton_clear()
    yield
    WorkerSource.singleton_clear()
    LogCache.singleton_clear()


@pytest.fixture
def config_data(monkeypatch):
    """
    The scan cache get_mod reads, without a config directory on disk.
    """
    ConfigScanSource.singleton_clear()
    monkeypatch.setattr(
        ConfigScanSource(),
        'data',
        {CONFIG_NAME: ConfigInfo(CONFIG_NAME, MOD_NAME, 0, 1)},
    )
    yield
    ConfigScanSource.singleton_clear()


@pytest.fixture
def fake_manager(monkeypatch):
    """
    Replace the module level manager the RPCs call.
    """
    manager = FakeManager()
    monkeypatch.setattr(worker_topic, 'BACKEND_WORKER_MANAGER', manager)
    return manager


async def test_source_sets_deletes_and_deduplicates_states():
    """
    The source keeps the state of every running config and drops the ones
    that are idle, which is what the frontend reads as "not running".
    """
    source = WorkerSource()
    assert source.TOPIC_NAME == 'Worker'

    assert source._apply((CONFIG_NAME, 'running')) is True
    assert source.data == {CONFIG_NAME: 'running'}
    # the same state twice is not an update
    assert source._apply((CONFIG_NAME, 'running')) is False

    event = source._convert((CONFIG_NAME, 'running'))
    assert (event.t, event.o, event.k, event.v) == (
        'Worker',
        'set',
        (CONFIG_NAME,),
        'running',
    )

    # idle means "not running": the entry is deleted
    assert source._apply((CONFIG_NAME, 'idle')) is True
    assert CONFIG_NAME not in source.data
    assert source._apply((CONFIG_NAME, 'idle')) is False

    event = source._convert((CONFIG_NAME, 'idle'))
    assert (event.t, event.o, event.k) == ('Worker', 'del', (CONFIG_NAME,))


async def test_manager_forwards_a_worker_state_event_to_the_source():
    """
    on_worker_state is the seam the worker recv thread calls: it locks and
    forwards whatever the pipe reported.
    """
    BACKEND_WORKER_MANAGER.on_config_event(
        ConfigEvent(t='Worker', c=CONFIG_NAME, v='scheduler-waiting')
    )
    assert WorkerSource().data == {CONFIG_NAME: 'scheduler-waiting'}


async def test_manager_forwards_a_log_event_to_the_log_cache():
    """
    The Log branch is the pipe's other producer and needs no loop: with no
    subscriber the cache only keeps the line.
    """
    BACKEND_WORKER_MANAGER.on_config_event(
        ConfigEvent(
            t='Log', c=CONFIG_NAME, v={'t': 1.0, 'l': 'INFO', 'm': 'from-worker'}
        )
    )
    assert [event.v['m'] for event in LogCache(CONFIG_NAME)._cache] == ['from-worker']


async def test_manager_warns_about_a_topic_of_an_unported_producer(monkeypatch):
    """
    The Preview / TaskQueue / TaskRunning / ConfigArg branches land with
    their topics; until then they take upstream's warning fallback.
    """
    warned = []
    monkeypatch.setattr(
        'oas.backend.topic._worker.logger.warning', lambda msg: warned.append(msg)
    )
    BACKEND_WORKER_MANAGER.on_config_event(ConfigEvent(t='Preview', c=CONFIG_NAME))
    assert warned == ['Unknown topic event: Preview']


async def test_get_mod_resolves_the_declared_mod_of_a_config(config_data):
    """
    get_mod reads the live scan cache, so the caller must not rescan.
    """
    mod = get_mod(CONFIG_NAME)
    assert isinstance(mod, ModEntryInfo)
    assert mod.name == MOD_NAME
    assert mod.root


async def test_get_mod_rejects_an_unknown_config(config_data):
    with pytest.raises(RpcValueError) as exc:
        get_mod('nope')
    assert 'No such config "nope"' in str(exc.value)


async def test_get_mod_rejects_a_config_of_an_undeclared_mod(config_data, monkeypatch):
    monkeypatch.setattr(
        ConfigScanSource(),
        'data',
        {CONFIG_NAME: ConfigInfo(CONFIG_NAME, 'ghost', 0, 1)},
    )
    with pytest.raises(RpcValueError) as exc:
        get_mod(CONFIG_NAME)
    assert f'No such mod "ghost" from config "{CONFIG_NAME}"' in str(exc.value)


@pytest.mark.parametrize(
    'method,args,expected',
    [
        ('start', (CONFIG_NAME,), ('start', MOD_NAME, CONFIG_NAME)),
        ('scheduler_stop', (CONFIG_NAME,), ('scheduler_stop', CONFIG_NAME, False)),
        ('scheduler_stop', (CONFIG_NAME, True), ('scheduler_stop', CONFIG_NAME, True)),
        ('scheduler_continue', (CONFIG_NAME,), ('scheduler_continue', CONFIG_NAME)),
        ('kill', (CONFIG_NAME,), ('kill', CONFIG_NAME, False)),
        ('kill', (CONFIG_NAME, True), ('kill', CONFIG_NAME, True)),
        ('force_kill', (CONFIG_NAME,), ('force_kill', CONFIG_NAME, False)),
        ('force_kill', (CONFIG_NAME, True), ('force_kill', CONFIG_NAME, True)),
    ],
)
async def test_rpc_forwards_to_the_manager(
    config_data, fake_manager, method, args, expected
):
    """
    Every RPC validates the config, then forwards to the manager on a worker
    thread (the call itself is synchronous and blocks).
    """
    topic = Worker(CONN_ID, None)
    await getattr(topic, method)(*args)
    assert fake_manager.calls == [expected]


async def test_rpc_error_of_the_manager_becomes_an_rpc_value_error(
    config_data, fake_manager
):
    """
    The manager answers (False, message); the topic turns it into the error
    the frontend shows, as upstream does.
    """
    fake_manager.result = (False, 'worker is busy')
    topic = Worker(CONN_ID, None)
    with pytest.raises(RpcValueError) as exc:
        await topic.start(CONFIG_NAME)
    assert 'worker is busy' in str(exc.value)


async def test_rpc_validates_the_config_before_calling_the_manager(fake_manager):
    """
    No such config: the manager must not be reached at all.
    """
    ConfigScanSource.singleton_clear()
    topic = Worker(CONN_ID, None)
    with pytest.raises(RpcValueError):
        await topic.start('nope')
    assert fake_manager.calls == []


async def test_topic_without_a_config_directory_has_an_empty_snapshot():
    """
    The topic is passive: its snapshot is whatever the manager reported, also
    without a config, and it never reinitialises a source.
    """
    ConfigScanSource.singleton_clear()
    topic = Worker(CONN_ID, None)
    source = await topic.get_source()
    assert source is WorkerSource()
    assert source.data == {}
