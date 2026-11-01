"""
Fixtures for the app tests.
"""

import pytest

from oas.backend.anyio import AnyIO
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.logger.writer import LogWriter


def reset_backend():
    """
    Unbind the loop bridge and clear the global context.
    """
    AnyIO.unbind_loop()
    GLOBAL_CONTEXT.global_task_group = None
    GLOBAL_CONTEXT.shutdown_event = None


@pytest.fixture(autouse=True)
def clean_backend():
    """
    Run every test without a bound loop and without an injected context.
    """
    reset_backend()
    yield
    reset_backend()


@pytest.fixture(autouse=True)
def mute_log_file():
    """
    Keep the test process from opening log files in the project log directory.

    The lifespan logs on startup and shutdown, and a line written by the test
    process itself (pytest reports its module name as "__main__") would
    otherwise create log/{date}___main__.txt in the repository.
    """
    LogWriter().mute(fd=True)
    yield
    # drop whatever fd the test left cached (real or fake) before unmuting
    LogWriter().close_fd()
    LogWriter().mute_clear()
