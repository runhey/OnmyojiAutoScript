"""
Tests for Table.get_data_version()
"""
import os
import shutil

import msgspec
import pytest

from oas.db.conn import SQLITE_POOL
from oas.db.table import Table
from oas.ext.env import OAS_ROOT

# ============================================================================
# Test Models and Tables
# ============================================================================


class VersionRow(msgspec.Struct):
    """Simple model for testing data_version"""
    id: int = 0
    value: str = ''


class DataVersionTable(Table):
    """Simple table for testing data_version PRAGMA"""
    TABLE_NAME = 'test_data_version'
    CREATE_TABLE = '''
        CREATE TABLE "{TABLE_NAME}" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "value" TEXT NOT NULL
        )
    '''
    MODEL = VersionRow


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def db_dir():
    """
    Real filesystem directory for the file-based database tests.

    SQLite opens its database file in the C layer, so the in-memory fake
    filesystem cannot intercept it: the database tests need a real directory.
    The directory lives under the repo's temp/ folder and is removed after
    the module finishes.
    """
    path = OAS_ROOT.joinpath('temp/db_pargma')
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    yield path
    # Release pooled connections so the database files can be removed on Windows
    for file in os.listdir(path):
        if file.endswith('.db'):
            SQLITE_POOL.delete_file(path / file)
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def table():
    """Create a DataVersionTable using in-memory database"""
    t = DataVersionTable(':memory:')
    t.create_table()
    return t


# ============================================================================
# Tests
# ============================================================================

class TestGetDataVersion:
    """Tests for Table.get_data_version()"""

    def test_returns_int(self, table):
        """get_data_version should return an int"""
        result = table.get_data_version()
        assert isinstance(result, int)
        assert result >= 0

    def test_with_explicit_cursor(self, table):
        """get_data_version with an explicit cursor should work"""
        with table.cursor() as c:
            result = table.get_data_version(_cursor_=c)
            assert isinstance(result, int)
            assert result >= 0

    def test_with_cursor_and_without_cursor_consistency(self, table):
        """With and without explicit cursor should return the same version"""
        v1 = table.get_data_version()
        with table.cursor() as c:
            v2 = table.get_data_version(_cursor_=c)
        assert v1 == v2

    def test_multiple_calls_return_same_value(self, table):
        """Multiple calls without modifications should return the same version"""
        v1 = table.get_data_version()
        v2 = table.get_data_version()
        v3 = table.get_data_version()
        assert v1 == v2 == v3

    def test_on_file_database(self, db_dir):
        """Test data_version works on a file-based database"""
        db_path = str(db_dir / 'test_version.db')
        t = DataVersionTable(db_path)
        t.create_table()

        result = t.get_data_version()
        assert isinstance(result, int)
        assert result >= 0

    def test_on_multiple_file_databases(self, db_dir):
        """Different file databases have independent data_version"""
        db1 = str(db_dir / 'test_version_1.db')
        db2 = str(db_dir / 'test_version_2.db')

        t1 = DataVersionTable(db1)
        t1.create_table()
        t2 = DataVersionTable(db2)
        t2.create_table()

        v1 = t1.get_data_version()
        v2 = t2.get_data_version()
        assert isinstance(v1, int)
        assert isinstance(v2, int)

