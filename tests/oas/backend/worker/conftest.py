"""
Fixtures for the worker process tests.

These tests spawn a real child process over a real multiprocessing pipe, so
the manager singleton must be closed (no orphan child survives a test) and
the state source dropped between tests.
"""

import pytest

from oas.backend.topic._worker import BACKEND_WORKER_MANAGER, WorkerSource
from oas.logger.writer import LogWriter


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'


@pytest.fixture(autouse=True)
def clean_worker():
    """
    Close the manager before and after every test, then drop the singletons.

    close() terminates whatever child a test left running; the singletons
    (the manager and its state source) would otherwise carry state into the
    next test.
    """
    BACKEND_WORKER_MANAGER.close()
    WorkerSource.singleton_clear()
    yield
    BACKEND_WORKER_MANAGER.close()
    WorkerSource.singleton_clear()


@pytest.fixture(autouse=True)
def mute_log_file():
    """
    Keep the test process from opening log files in the project log directory.
    """
    LogWriter().mute(fd=True)
    yield
    LogWriter().close_fd()
    LogWriter().mute_clear()
