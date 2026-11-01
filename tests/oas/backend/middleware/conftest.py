"""Fixtures for the middleware suite."""

import pytest

from oas.backend.mpipe.token_backend import token_table
from oas.logger.writer import LogWriter

TEST_TOKEN = 'test-local-token'


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'


@pytest.fixture(autouse=True)
def clean_token_table():
    """
    Run every test on a clean token window.
    """
    token_table._tokens.clear()
    token_table.seed_from_supervisor((TEST_TOKEN,))
    yield
    token_table._tokens.clear()
    token_table.seed_from_supervisor((TEST_TOKEN,))


@pytest.fixture(autouse=True)
def mute_log_file():
    """
    Keep the test process from opening log files in the project log directory.

    The middleware does not log, but a leaked line from anything it drives
    would create log/{date}___main__.txt in the repository.
    """
    LogWriter().mute(fd=True)
    yield
    LogWriter().close_fd()
    LogWriter().mute_clear()
