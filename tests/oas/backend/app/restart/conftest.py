"""
Fixtures for the restart package suite.

The suite drives the ported maintenance-flow package: the process-wide slot and
the process-wide resume file IO are reset around every test (a test that claims
the slot or publishes a resume file must not leak into the next one), and
AnyIO's pytest plugin needs the asyncio backend pinned here, like the
neighbouring suites do.
"""

import pytest

from oas.backend.app.restart.restart_manager import RESTART_MANAGER
from oas.backend.app.restart.resume_file import RESUME_FILES


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'


@pytest.fixture(autouse=True)
def clean_restart_state():
    """
    Run every test on a fresh flow slot and a fresh publication slot.

    The two singletons live for the whole process (the worker manager and the
    backend look them up by name), so a test that claims the slot or publishes
    a file would otherwise carry that state into the next one.
    """
    RESTART_MANAGER.reset()
    RESUME_FILES.reset()
    yield
    RESTART_MANAGER.reset()
    RESUME_FILES.reset()
