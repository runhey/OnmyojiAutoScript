"""
Test INSERT operations: insert_row with single and multiple rows
"""
import pytest
from conftest import Product, User, UserTable


def test_insert_single_row(user_table):
    """Test inserting a single row"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    # Verify insertion
    result = user_table.select_one(name='Alice')
    assert result is not None
    assert result.name == 'Alice'
    assert result.age == 25
    assert result.email == 'alice@example.com'
    assert result.id > 0  # Auto-generated


def test_insert_multiple_rows(user_table, sample_users):
    """Test inserting multiple rows at once"""
    user_table.insert_row(sample_users)

    # Verify all inserted
    results = user_table.select()
    assert len(results) == 5

    # Check names
    names = {user.name for user in results}
    assert names == {'Alice', 'Bob', 'Charlie', 'David', 'Eve'}


def test_insert_auto_increment(user_table):
    """Test that auto-increment works correctly"""
    users = [
        User(id=0, name='User1', age=20, email='user1@example.com'),
        User(id=0, name='User2', age=21, email='user2@example.com'),
        User(id=0, name='User3', age=22, email='user3@example.com'),
    ]
    user_table.insert_row(users)

    # Retrieve and check IDs are sequential
    results = user_table.select(_orderby_='id')
    assert results[0].id > 0
    assert results[1].id == results[0].id + 1
    assert results[2].id == results[1].id + 1


def test_insert_with_cursor(user_table, sample_users):
    """Test inserting using a provided cursor"""
    with user_table.cursor() as c:
        user_table.insert_row(sample_users[:2], _cursor_=c)
        user_table.insert_row(sample_users[2:], _cursor_=c)
        c.commit()

    # Verify all inserted
    results = user_table.select()
    assert len(results) == 5


def test_insert_empty_list(user_table):
    """Test inserting an empty list does nothing"""
    user_table.insert_row([])

    count = user_table.select_count()
    assert count == 0


def test_insert_with_unique_constraint(product_table):
    """Test unique constraint violation"""
    product1 = Product(id=0, sku='SKU001', name='Product 1', price=10.0, stock=5)
    product_table.insert_row(product1)

    # Try to insert with duplicate SKU
    product2 = Product(id=0, sku='SKU001', name='Product 2', price=20.0, stock=10)

    with pytest.raises(Exception):  # sqlite3.IntegrityError
        product_table.insert_row(product2)


def test_insert_preserves_data_types(user_table):
    """Test that data types are preserved after insert"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    result = user_table.select_one(name='Alice')
    assert isinstance(result.name, str)
    assert isinstance(result.age, int)
    assert isinstance(result.email, str)
    assert isinstance(result.id, int)


def test_insert_special_characters(user_table):
    """Test inserting data with special characters"""
    user = User(
        id=0,
        name="O'Brien",
        age=30,
        email='o"brien@example.com'
    )
    user_table.insert_row(user)

    result = user_table.select_one(name="O'Brien")
    assert result is not None
    assert result.name == "O'Brien"
    assert result.email == 'o"brien@example.com'


def test_insert_unicode(user_table):
    """Test inserting Unicode data"""
    user = User(id=0, name='张三', age=25, email='zhangsan@example.com')
    user_table.insert_row(user)

    result = user_table.select_one(name='张三')
    assert result is not None
    assert result.name == '张三'


def test_insert_with_transaction_commit(user_table, sample_users):
    """Test manual transaction commit"""
    with user_table.cursor() as c:
        user_table.insert_row(sample_users[:2], _cursor_=c)
        # Don't commit yet

        # Check within transaction
        results = user_table.select(_cursor_=c)
        assert len(results) == 2

        # Commit
        c.commit()

    # Verify after transaction
    results = user_table.select()
    assert len(results) == 2


def test_insert_large_batch(user_table):
    """Test inserting a large batch of rows"""
    users = [
        User(id=0, name=f'User{i}', age=20 + i, email=f'user{i}@example.com')
        for i in range(100)
    ]

    user_table.insert_row(users)

    count = user_table.select_count()
    assert count == 100


def test_insert_then_select_by_pk(user_table):
    """Test inserting and then selecting by primary key"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    # Get the inserted user to find its ID
    result = user_table.select_one(name='Alice')
    assert result is not None

    # Select by PK
    by_pk = user_table.select_by_pk(result.id)
    assert by_pk is not None
    assert by_pk.id == result.id
    assert by_pk.name == 'Alice'


def test_insert_default_values(user_table):
    """Test that default values from model are respected"""
    # User struct has default values
    user = User(name='Alice', email='alice@example.com')  # age defaults to 0
    user_table.insert_row(user)

    result = user_table.select_one(name='Alice')
    assert result is not None
    assert result.age == 0


def test_insert_single_then_multiple(user_table, sample_users):
    """Test mixing single and multiple inserts"""
    # Insert single
    user_table.insert_row(sample_users[0])

    # Insert multiple
    user_table.insert_row(sample_users[1:])

    # Verify all inserted
    count = user_table.select_count()
    assert count == 5


def test_insert_float_values(product_table):
    """Test inserting float values"""
    product = Product(id=0, sku='SKU001', name='Laptop', price=999.99, stock=10)
    product_table.insert_row(product)

    result = product_table.select_one(sku='SKU001')
    assert result is not None
    assert result.price == 999.99


def test_insert_zero_values(user_table):
    """Test inserting zero values (which are valid)"""
    user = User(id=0, name='Zero Age', age=0, email='zero@example.com')
    user_table.insert_row(user)

    result = user_table.select_one(name='Zero Age')
    assert result is not None
    assert result.age == 0


def test_insert_in_new_table(temp_db):
    """Test insert in freshly created table"""

    table = UserTable(temp_db)
    # Don't call create_table manually - it should auto-create

    user = User(id=0, name='First User', age=30, email='first@example.com')
    table.insert_row(user)

    result = table.select_one(name='First User')
    assert result is not None


def test_insert_respects_column_order(user_table):
    """Test that insert works regardless of field order in struct"""
    # This tests that the SQL generation correctly maps fields
    user = User(
        email='test@example.com',
        name='Test User',
        age=25,
        id=0
    )
    user_table.insert_row(user)

    result = user_table.select_one(name='Test User')
    assert result is not None
    assert result.email == 'test@example.com'
    assert result.age == 25

