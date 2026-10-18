import pytest

from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.config.table.scan import ScanTable
from oas.db.conn import SQLITE_POOL


@pytest.fixture
def config_table():
    table = ConfigTable(":memory:")
    table.create_table()
    yield table
    ConfigTable.singleton_remove(":memory:")
    KeyTable.singleton_remove(":memory:")
    SQLITE_POOL.delete_file(":memory:")


@pytest.fixture
def scan_table(tmp_path, monkeypatch):
    from oas.ext import env
    from oas.ext.path import PathStr

    monkeypatch.setattr(env, "PROJECT_ROOT", PathStr.new(str(tmp_path)))
    table = ScanTable()
    table.create_table()
    yield table
    ScanTable.singleton_clear()
    SQLITE_POOL.delete_file(str(PathStr.new(str(tmp_path)) / "config" / "gui.db"))
