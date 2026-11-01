"""
Async test configuration for the topic suite.

Topics are async (their RPC methods and reactive properties run on the event
loop), so AnyIO's pytest plugin needs the backend here, like the reactive
suite pins it.
"""

import pytest


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio, the production backend"""
    return 'asyncio'
