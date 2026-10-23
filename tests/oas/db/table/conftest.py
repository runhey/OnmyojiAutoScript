"""
Shared pytest fixtures and test models for Table testing
"""

import msgspec
import pytest

from oas.db.conn import SQLITE_POOL
from oas.db.table import Table

# ============================================================================
# Test Models
# ============================================================================


class User(msgspec.Struct):
    """Simple user model for testing"""

    id: int = 0
    name: str = ''
    age: int = 0
    email: str = ''


class Product(msgspec.Struct):
    """Product model with unique constraint for testing"""

    id: int = 0
    sku: str = ''
    name: str = ''
    price: float = 0.0
    stock: int = 0


# ============================================================================
# Test Table Classes
# ============================================================================


class UserTable(Table):
    """User table for testing"""

    TABLE_NAME = 'users'
    PRIMARY_KEY = 'id'
    AUTO_INCREMENT = 'id'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "name" TEXT NOT NULL,
            "age" INTEGER NOT NULL,
            "email" TEXT NOT NULL
        )
    """
    MODEL = User

    def select_count(self, **kwargs):
        """Count rows matching the condition"""
        return len(self.select(**kwargs))

    def select_by_pk(self, pk_value):
        """Select row by primary key"""
        return self.select_one(**{self.PRIMARY_KEY: pk_value})


class ProductTable(Table):
    """Product table with unique constraint for testing"""

    TABLE_NAME = 'products'
    PRIMARY_KEY = 'id'
    AUTO_INCREMENT = 'id'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "sku" TEXT NOT NULL UNIQUE,
            "name" TEXT NOT NULL,
            "price" REAL NOT NULL,
            "stock" INTEGER NOT NULL,
            UNIQUE ("sku", "name")
        )
    """
    MODEL = Product

    def select_count(self, **kwargs):
        """Count rows matching the condition"""
        return len(self.select(**kwargs))

    def select_by_pk(self, pk_value):
        """Select row by primary key"""
        return self.select_one(**{self.PRIMARY_KEY: pk_value})


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def temp_db():
    """
    Use an in-memory database for testing

    The shared connection pool keeps the same connection for the ':memory:'
    key, so every cursor sees the same database within one test.
    """
    db_path = ':memory:'
    yield db_path

    # Release all connections to this database
    # delete_file pops the pool entry and closes its connections, so the
    # next test gets a fresh in-memory database with no leftover data
    try:
        SQLITE_POOL.delete_file(db_path)
    except Exception:
        pass


@pytest.fixture
def user_table(temp_db):
    """Create a UserTable instance with an in-memory database"""
    table = UserTable(temp_db)
    table.create_table()
    yield table
    # Cleanup is handled by temp_db fixture


@pytest.fixture
def product_table(temp_db):
    """Create a ProductTable instance with an in-memory database"""
    table = ProductTable(temp_db)
    table.create_table()
    yield table


@pytest.fixture
def sample_users():
    """Sample user data for testing"""
    return [
        User(id=0, name='Alice', age=25, email='alice@example.com'),
        User(id=0, name='Bob', age=30, email='bob@example.com'),
        User(id=0, name='Charlie', age=35, email='charlie@example.com'),
        User(id=0, name='David', age=28, email='david@example.com'),
        User(id=0, name='Eve', age=32, email='eve@example.com'),
    ]


@pytest.fixture
def sample_products():
    """Sample product data for testing"""
    return [
        Product(id=0, sku='SKU001', name='Laptop', price=999.99, stock=10),
        Product(id=0, sku='SKU002', name='Mouse', price=29.99, stock=50),
        Product(id=0, sku='SKU003', name='Keyboard', price=79.99, stock=30),
        Product(id=0, sku='SKU004', name='Monitor', price=299.99, stock=15),
    ]
