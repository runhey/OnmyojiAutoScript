"""
Fixtures for the auth suite.

The token window is isolated like the ws suite does it, and the JWT secret is
stubbed by the parent conftest (tests/oas/backend/conftest.py) so no test
touches the key table of the repository.
"""

import pytest

from oas.backend.mpipe.token_backend import token_table
from oas.logger.writer import LogWriter

TEST_TOKEN = 'test-local-token'


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'


def seed_token_table():
    """
    One valid local token, the way the supervisor seeds the window.
    """
    # the token table has no public reset: the tests own the whole window
    token_table._tokens.clear()
    token_table.seed_from_supervisor((TEST_TOKEN,))


@pytest.fixture(autouse=True)
def clean_token_table():
    """
    Run every test on a clean token window.
    """
    seed_token_table()
    yield
    seed_token_table()


@pytest.fixture(autouse=True)
def mute_log_file():
    """
    Keep the test process from opening log files in the project log directory.

    The fail2ban and login paths log on failures, and a line written by the
    test process itself (pytest reports its module name as "__main__") would
    otherwise create log/{date}___main__.txt in the repository.
    """
    LogWriter().mute(fd=True)
    yield
    LogWriter().close_fd()
    LogWriter().mute_clear()
