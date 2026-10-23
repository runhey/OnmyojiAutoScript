"""
Shared test configuration and fixtures for SQLite pool tests
"""

import os
import time

import pytest

from oas.db.conn import ConnectionPool, SqlitePool

# ============================================================================
# Test directory setup
# ============================================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(TEST_DIR, 'test_data')


def setup_test_dir():
    """Create test data directory if not exists"""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)


def cleanup_test_dir():
    """Clean up test data directory"""
    if os.path.exists(TEST_DATA_DIR):
        for file in os.listdir(TEST_DATA_DIR):
            file_path = os.path.join(TEST_DATA_DIR, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception:
                pass


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture(scope='session', autouse=True)
def test_environment():
    """Setup and teardown test environment"""
    setup_test_dir()
    yield
    cleanup_test_dir()


@pytest.fixture
def temp_db():
    """Create temporary database file"""
    db_path = os.path.join(TEST_DATA_DIR, f'test_{os.getpid()}_{id(temp_db)}.db')
    yield db_path
    # Cleanup - wait a bit for Windows to release file locks
    time.sleep(0.05)
    try:
        os.unlink(db_path)
    except FileNotFoundError, PermissionError, OSError:
        # On Windows, file may still be locked, it's ok
        pass


@pytest.fixture
def temp_db_in_subdir():
    """Create temporary database in subdirectory"""
    subdir = os.path.join(TEST_DATA_DIR, 'subdir')
    db_path = os.path.join(subdir, 'test.db')
    yield db_path
    # Cleanup - wait for Windows file locks
    time.sleep(0.05)
    try:
        os.unlink(db_path)
    except FileNotFoundError, PermissionError, OSError:
        pass
    try:
        os.rmdir(subdir)
    except FileNotFoundError, OSError:
        pass


@pytest.fixture
def pool(temp_db):
    """Create connection pool instance"""
    pool = ConnectionPool(temp_db, pool_size=4)
    yield pool
    pool.release_all()


@pytest.fixture
def sqlite_pool():
    """Create SqlitePool instance"""
    pool = SqlitePool(pool_size=4)
    yield pool
    pool.release_all()
