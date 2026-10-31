"""
Async test configuration for the reactive suite.

The backend runs on asyncio (FastAPI + Uvicorn) and the loop bridge
(oas.backend.anyio.AnyIO) stores an asyncio loop, so the source tests
must run on the asyncio backend. AnyIO's pytest plugin selects the backend
through this fixture.

No loop is bound here on purpose: AnyIO.loop() captures the running loop
on the first subscribe, and the suite exercises that no-lifespan fallback
instead of the FastAPI lifespan.
"""

import pytest


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'
