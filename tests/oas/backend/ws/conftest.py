"""
Fixtures for the ws layer tests.
"""

import anyio
import pytest

from oas.backend.anyio import AnyIO
from oas.backend.mpipe.token_backend import token_table
from oas.backend.topic._worker import (
    BACKEND_WORKER_MANAGER,
    BackendWorkerManager,
    WorkerSource,
)
from oas.backend.topic.log import Log, LogCache
from oas.backend.topic.mod import ModHistory, ModHistorySource, ModList, ModListSource
from oas.backend.topic.restart import Restart, RestartSource
from oas.backend.topic.scan import ConfigScan, ConfigScanSource
from oas.backend.topic.state import ConnState
from oas.backend.topic.worker import Worker
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.config.table.scan import ScanTable
from oas.db.conn import SQLITE_POOL
from oas.ext import env
from oas.ext.path import PathStr
from oas.logger.writer import LogWriter

from ws_helpers import TEST_TOKEN, TestSource, TestTopic


def reset_backend():
    """
    Fresh bridge, global context, connection registry, topic singletons and
    token window for one test.
    """
    AnyIO.unbind_loop()
    GLOBAL_CONTEXT.global_task_group = None
    GLOBAL_CONTEXT.shutdown_event = None
    WebsocketTopicServer.active.clear()
    WebsocketTopicServer.server_terminated = anyio.Event()
    TestTopic.singleton_clear()
    TestTopic.source = None
    # the default topic every connection registers
    ConnState.singleton_clear()
    # the other ported topics and their sources (ModList / ModHistory are
    # TTL caches, RestartSource and LogCache are resident)
    ModList.singleton_clear()
    ModHistory.singleton_clear()
    ModListSource.singleton_clear()
    ModHistorySource.singleton_clear()
    Restart.singleton_clear()
    RestartSource.singleton_clear()
    Log.singleton_clear()
    LogCache.singleton_clear()
    # the worker manager owns child processes and reports into WorkerSource:
    # terminate whatever a test started, then drop the singletons
    BACKEND_WORKER_MANAGER.close()
    Worker.singleton_clear()
    WorkerSource.singleton_clear()
    BackendWorkerManager.singleton_clear()
    # the token table has no public reset: the tests own the whole window
    token_table._tokens.clear()
    token_table.seed_from_supervisor((TEST_TOKEN,))


@pytest.fixture(autouse=True)
def clean_backend():
    """
    Run every test on a clean backend state.
    """
    reset_backend()
    yield
    reset_backend()


@pytest.fixture
def source():
    """
    One test source, shared by every connection of the test.
    """
    src = TestSource()
    TestTopic.source = src
    return src


@pytest.fixture(autouse=True)
def mute_log_file():
    """
    Keep the test process from opening log files in the project log directory.

    The ws layer logs on connection errors and the lifespan logs on startup
    and shutdown; a line written by the test process itself (pytest reports
    its module name as "__main__") would otherwise create
    log/{date}___main__.txt in the repository.
    """
    LogWriter().mute(fd=True)
    yield
    # drop whatever fd the test left cached (real or fake) before unmuting
    LogWriter().close_fd()
    LogWriter().mute_clear()


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """
    Isolate the repository config directory, as tests/oas/config does: the
    scan reads and writes ``config/*.db`` under ``env.PROJECT_ROOT``.

    Yields:
        PathStr: The temporary project root
    """
    root = PathStr.new(str(tmp_path))
    monkeypatch.setattr(env, 'PROJECT_ROOT', root)
    (tmp_path / 'config').mkdir(parents=True, exist_ok=True)

    ConfigScan.singleton_clear()
    ConfigScanSource.singleton_clear()
    ScanTable.singleton_clear()
    # the table must exist before the source scans (see tests/oas/config)
    ScanTable().create_table()

    yield root

    ConfigScan.singleton_clear()
    ConfigScanSource.singleton_clear()
    ScanTable.singleton_clear()
    ConfigTable.singleton_clear()
    KeyTable.singleton_clear()
    for path in (root / 'config').iter_files(ext='.db'):
        SQLITE_POOL.delete_file(str(path))
