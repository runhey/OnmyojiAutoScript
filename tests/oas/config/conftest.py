"""Shared fixtures for ``tests/oas/config``."""

import pytest

from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.db.conn import SQLITE_POOL


@pytest.fixture
def memory_config():
    """Prepare the named ``:memory:`` config database and clean it up."""

    ConfigTable(':memory:').create_table()
    yield
    ConfigTable.singleton_remove(':memory:')
    KeyTable.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')
