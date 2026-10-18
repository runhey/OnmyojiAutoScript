"""
Test basic table operations: create_table, drop_table, field_names, etc.
"""

from conftest import User, UserTable

from oas.db.table import Table, row_has_pk


def test_create_table(user_table, temp_db):
    """Test creating a table"""
    # Table is already created in fixture
    # Try creating again should not raise error
    assert user_table.create_table() is False  # Already exists

    # Verify table exists by querying
    with user_table.cursor() as c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                  (user_table.TABLE_NAME,))
        result = c.fetchone()
        assert result is not None
        assert result['name'] == 'users'


def test_drop_table(user_table):
    """Test dropping a table"""
    # Verify table exists
    with user_table.cursor() as c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                  (user_table.TABLE_NAME,))
        assert c.fetchone() is not None

    # Drop table
    user_table.drop_table()

    # Verify table no longer exists
    with user_table.cursor() as c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                  (user_table.TABLE_NAME,))
        assert c.fetchone() is None


def test_table_name(user_table):
    """Test TABLE_NAME property"""
    assert user_table.TABLE_NAME == 'users'


def test_primary_key(user_table):
    """Test PRIMARY_KEY property"""
    assert user_table.PRIMARY_KEY == 'id'


def test_auto_increment(user_table):
    """Test AUTO_INCREMENT property"""
    assert user_table.AUTO_INCREMENT == 'id'


def test_field_names(user_table):
    """Test field_names cached property"""
    field_names = user_table.field_names
    assert isinstance(field_names, list)
    assert 'id' in field_names
    assert 'name' in field_names
    assert 'age' in field_names
    assert 'email' in field_names
    assert len(field_names) == 4


def test_sql_insert_columns_placeholders(user_table):
    """Test SQL insert columns and placeholders generation"""
    columns, placeholders = user_table.sql_insert_columns_placeholders

    # Should exclude AUTO_INCREMENT field (id)
    assert 'id' not in columns
    assert 'name' in columns
    assert 'age' in columns
    assert 'email' in columns

    # Check placeholders format
    assert ':name' in placeholders
    assert ':age' in placeholders
    assert ':email' in placeholders


def test_sql_select_kwargs_to_condition():
    """Test converting kwargs to SQL condition"""
    result = Table.sql_select_kwargs_to_condition({'name': 'Alice', 'age': 25})
    assert '"name"=:name' in result
    assert '"age"=:age' in result
    assert 'AND' in result


def test_sql_expr_groupby():
    """Test GROUP BY expression generation"""
    # Single field
    result = Table.sql_expr_groupby('name')
    assert result == ' GROUP BY "name"'

    # Multiple fields
    result = Table.sql_expr_groupby(['name', 'age'])
    assert result == ' GROUP BY "name","age"'

    result = Table.sql_expr_groupby(('name', 'age'))
    assert result == ' GROUP BY "name","age"'


def test_sql_expr_orderby():
    """Test ORDER BY expression generation"""
    # Single field ASC
    result = Table.sql_expr_orderby('name', asc=True)
    assert result == ' ORDER BY "name"'

    # Single field DESC
    result = Table.sql_expr_orderby('name', asc=False)
    assert result == ' ORDER BY "name" DESC'

    # Multiple fields ASC
    result = Table.sql_expr_orderby(['name', 'age'], asc=True)
    assert result == ' ORDER BY "name","age"'

    # Multiple fields DESC
    result = Table.sql_expr_orderby(['name', 'age'], asc=False)
    assert result == ' ORDER BY "name","age" DESC'


def test_cursor_creation(user_table):
    """Test cursor creation"""
    with user_table.cursor() as c:
        assert c is not None
        assert c.TABLE_NAME == 'users'
        assert c.CREATE_TABLE != ''


def test_cursor_lazy(user_table):
    """Test lazy cursor creation"""
    lazy_cursor = user_table.cursor(lazy=True)
    assert lazy_cursor is not None
    assert hasattr(lazy_cursor, 'query')
    assert lazy_cursor.query == []


def test_auto_create_table_on_execute(temp_db):
    """Test that table is auto-created when executing SQL"""

    # Create table instance without calling create_table
    table = UserTable(temp_db)

    # Insert should auto-create table
    user = User(id=0, name='Test', age=25, email='test@example.com')
    table.insert_row(user)

    # Verify table exists
    with table.cursor() as c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                  (table.TABLE_NAME,))
        assert c.fetchone() is not None


def test_table_with_memory_db(user_table):
    """Test table operations with in-memory database"""
    assert user_table.file == ':memory:'

    # Should be able to perform operations
    user = User(id=0, name='Memory Test', age=30, email='memory@example.com')
    user_table.insert_row(user)

    result = user_table.select_one(name='Memory Test')
    assert result is not None
    assert result.name == 'Memory Test'


def test_row_has_pk(user_table):
    """Test _row_has_pk method"""

    # User with valid PK
    user_with_pk = User(id=5, name='Test', age=25, email='test@example.com')
    assert row_has_pk(user_with_pk) is True

    # User without PK (id=0)
    user_without_pk = User(id=0, name='Test', age=25, email='test@example.com')
    assert row_has_pk(user_without_pk) is False

    # User with negative PK
    user_negative_pk = User(id=-1, name='Test', age=25, email='test@example.com')
    assert row_has_pk(user_negative_pk) is False


def test_sql_select_expr_basic(user_table):
    """Test basic SQL select expression"""
    sql = user_table.sql_select_expr()
    assert 'SELECT' in sql
    assert user_table.TABLE_NAME in sql


def test_sql_select_expr_with_groupby(user_table):
    """Test SQL select expression with GROUP BY"""
    sql = user_table.sql_select_expr(_groupby_='name')
    assert 'GROUP BY "name"' in sql

    sql = user_table.sql_select_expr(_groupby_=['name', 'age'])
    assert 'GROUP BY "name","age"' in sql


def test_sql_select_expr_with_orderby(user_table):
    """Test SQL select expression with ORDER BY"""
    sql = user_table.sql_select_expr(_orderby_='name')
    assert 'ORDER BY "name"' in sql


def test_sql_select_expr_with_orderby_desc(user_table):
    """Test SQL select expression with ORDER BY DESC"""
    sql = user_table.sql_select_expr(_orderby_desc_='age')
    assert 'ORDER BY "age" DESC' in sql


def test_sql_select_expr_with_limit(user_table):
    """Test SQL select expression with LIMIT"""
    sql = user_table.sql_select_expr(_limit_=10)
    assert 'LIMIT 10' in sql


def test_sql_select_expr_with_offset(user_table):
    """Test SQL select expression with OFFSET"""
    sql = user_table.sql_select_expr(_limit_=10, _offset_=5)
    assert 'LIMIT 10 OFFSET 5' in sql


def test_sql_select_expr_combined(user_table):
    """Test SQL select expression with multiple options"""
    sql = user_table.sql_select_expr(
        _groupby_='status',
        _orderby_='priority',
        _limit_=20,
        _offset_=10
    )
    assert 'GROUP BY "status"' in sql
    assert 'ORDER BY "priority"' in sql
    assert 'LIMIT 20' in sql
    assert 'OFFSET 10' in sql

