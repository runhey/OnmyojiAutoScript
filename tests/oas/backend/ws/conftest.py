"""
Fixtures for the ws layer tests.
"""

import anyio
import pytest

from oas.backend.anyio import AnyIO
from oas.backend.mpipe.token_backend import token_table
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.backend.ws.ws_server import WebsocketTopicServer
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
