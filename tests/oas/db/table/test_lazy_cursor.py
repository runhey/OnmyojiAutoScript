"""
Test LazyCursor: lazy execution of SQL statements
"""
import pytest

from oas.db.table import LazyCursor


def test_lazy_cursor_creation(user_table):
    """Test creating a lazy cursor"""
    lazy = user_table.cursor(lazy=True)

    assert isinstance(lazy, LazyCursor)
    assert lazy.table == user_table
    assert lazy.query == []


def test_lazy_cursor_context_manager(user_table):
    """Test using lazy cursor as context manager"""
    with user_table.cursor(lazy=True) as lazy:
        assert isinstance(lazy, LazyCursor)


def test_lazy_cursor_captures_execute(user_table):
    """Test that lazy cursor captures execute calls"""
    lazy = user_table.cursor(lazy=True)

    sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
    params = {'name': 'Alice', 'age': 25, 'email': 'alice@example.com'}

    lazy.execute(sql, params)

    # Should be captured, not executed
    assert len(lazy.query) == 1
    assert lazy.query[0] == ('execute', sql, params)


def test_lazy_cursor_captures_executemany(user_table):
    """Test that lazy cursor captures executemany calls"""
    lazy = user_table.cursor(lazy=True)

    sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
    params = [
        {'name': 'Alice', 'age': 25, 'email': 'alice@example.com'},
        {'name': 'Bob', 'age': 30, 'email': 'bob@example.com'},
    ]

    lazy.executemany(sql, params)

    assert len(lazy.query) == 1
    assert lazy.query[0] == ('executemany', sql, params)


def test_lazy_cursor_captures_executescript(user_table):
    """Test that lazy cursor captures executescript calls"""
    lazy = user_table.cursor(lazy=True)

    sql = 'CREATE TABLE test (id INTEGER); DROP TABLE test;'

    lazy.executescript(sql)

    assert len(lazy.query) == 1
    assert lazy.query[0][0] == 'executescript'
    assert lazy.query[0][1] == sql


def test_lazy_cursor_multiple_operations(user_table):
    """Test capturing multiple operations"""
    lazy = user_table.cursor(lazy=True)

    lazy.execute('SELECT * FROM users', {})
    lazy.execute('SELECT * FROM users WHERE name=:name', {'name': 'Alice'})
    lazy.executemany('INSERT INTO users VALUES (:name)', [{'name': 'Bob'}])

    assert len(lazy.query) == 3


def test_lazy_cursor_commit_executes_all(user_table, sample_users):
    """Test that commit executes all captured queries"""
    lazy = user_table.cursor(lazy=True)

    # Insert using lazy cursor
    for user in sample_users[:2]:
        sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
        params = {'name': user.name, 'age': user.age, 'email': user.email}
        lazy.execute(sql, params)

    # Nothing should be in database yet
    count = user_table.select_count()
    assert count == 0

    # Commit
    lazy.commit()

    # Now should be in database
    count = user_table.select_count()
    assert count == 2


def test_lazy_cursor_commit_empty_does_nothing(user_table):
    """Test that commit with empty query does nothing"""
    lazy = user_table.cursor(lazy=True)

    # Commit without any operations
    lazy.commit()  # Should not raise error

    count = user_table.select_count()
    assert count == 0


def test_lazy_cursor_fetchone_raises_error(user_table):
    """Test that fetchone raises error on lazy cursor"""
    lazy = user_table.cursor(lazy=True)

    with pytest.raises(RuntimeError, match='should not call fetchone'):
        lazy.fetchone()


def test_lazy_cursor_fetchall_raises_error(user_table):
    """Test that fetchall raises error on lazy cursor"""
    lazy = user_table.cursor(lazy=True)

    with pytest.raises(RuntimeError, match='should not call fetchall'):
        lazy.fetchall()


def test_lazy_cursor_with_insert_row(user_table, sample_users):
    """Test using lazy cursor with table operations"""
    # Note: This tests the integration, not just the cursor itself
    # We need to manually build the insert SQL since insert_row doesn't support lazy cursor

    lazy = user_table.cursor(lazy=True)

    for user in sample_users[:3]:
        sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
        params = {'name': user.name, 'age': user.age, 'email': user.email}
        lazy.execute(sql, params)

    lazy.commit()

    count = user_table.select_count()
    assert count == 3


def test_lazy_cursor_transaction_like_behavior(user_table, sample_users):
    """Test lazy cursor provides transaction-like behavior"""
    lazy = user_table.cursor(lazy=True)

    # Add multiple operations
    for user in sample_users:
        sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
        params = {'name': user.name, 'age': user.age, 'email': user.email}
        lazy.execute(sql, params)

    # Nothing committed yet
    assert user_table.select_count() == 0

    # Commit all at once
    lazy.commit()

    # All should be inserted
    assert user_table.select_count() == 5


def test_lazy_cursor_preserves_order(user_table):
    """Test that lazy cursor executes queries in order"""
    lazy = user_table.cursor(lazy=True)

    # Insert in specific order
    users = [
        ('Alice', 25),
        ('Bob', 30),
        ('Charlie', 35),
    ]

    for name, age in users:
        sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
        params = {'name': name, 'age': age, 'email': f'{name.lower()}@example.com'}
        lazy.execute(sql, params)

    lazy.commit()

    # Verify order (by checking IDs are sequential)
    results = user_table.select(_orderby_='id')
    assert [r.name for r in results] == ['Alice', 'Bob', 'Charlie']


def test_lazy_cursor_can_commit_multiple_times(user_table, sample_users):
    """Test that lazy cursor can commit multiple batches"""
    lazy = user_table.cursor(lazy=True)

    # First batch
    sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
    params = {'name': sample_users[0].name, 'age': sample_users[0].age,
              'email': sample_users[0].email}
    lazy.execute(sql, params)
    lazy.commit()

    assert user_table.select_count() == 1

    # Second batch
    params = {'name': sample_users[1].name, 'age': sample_users[1].age,
              'email': sample_users[1].email}
    lazy.execute(sql, params)
    lazy.commit()

    assert user_table.select_count() == 2


def test_lazy_cursor_clears_after_commit(user_table):
    """Test that query list is cleared after commit"""
    lazy = user_table.cursor(lazy=True)

    sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
    params = {'name': 'Test', 'age': 25, 'email': 'test@example.com'}
    lazy.execute(sql, params)

    assert len(lazy.query) == 1

    lazy.commit()

    assert len(lazy.query) == 0


def test_lazy_cursor_with_updates(user_table, sample_users):
    """Test lazy cursor with UPDATE statements"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    lazy = user_table.cursor(lazy=True)

    sql = 'UPDATE users SET age = :age WHERE id = :id'
    params = {'age': 30, 'id': user.id}
    lazy.execute(sql, params)

    # Not updated yet
    result = user_table.select_by_pk(user.id)
    assert result.age == 25

    # Commit
    lazy.commit()

    # Now updated
    result = user_table.select_by_pk(user.id)
    assert result.age == 30


def test_lazy_cursor_with_deletes(user_table, sample_users):
    """Test lazy cursor with DELETE statements"""
    user_table.insert_row(sample_users[:2])

    lazy = user_table.cursor(lazy=True)

    sql = 'DELETE FROM users WHERE name = :name'
    lazy.execute(sql, {'name': 'Alice'})

    # Not deleted yet
    assert user_table.select_count() == 2

    # Commit
    lazy.commit()

    # Now deleted
    assert user_table.select_count() == 1


def test_lazy_cursor_mixed_operations(user_table, sample_users):
    """Test lazy cursor with mixed INSERT/UPDATE/DELETE"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    lazy = user_table.cursor(lazy=True)

    # Insert
    lazy.execute(
        'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)',
        {'name': 'Bob', 'age': 30, 'email': 'bob@example.com'}
    )

    # Update
    lazy.execute(
        'UPDATE users SET age = :age WHERE id = :id',
        {'age': 26, 'id': user.id}
    )

    # Delete (will delete what we just inserted after commit)
    lazy.execute(
        'DELETE FROM users WHERE name = :name',
        {'name': 'Bob'}
    )

    # Commit all
    lazy.commit()

    # Should have 1 user (Alice) with updated age, Bob should be deleted
    assert user_table.select_count() == 1
    result = user_table.select_by_pk(user.id)
    assert result.age == 26


def test_lazy_cursor_with_executemany_batch(user_table):
    """Test lazy cursor with executemany for batch operations"""
    lazy = user_table.cursor(lazy=True)

    sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
    params = [
        {'name': f'User{i}', 'age': 20 + i, 'email': f'user{i}@example.com'}
        for i in range(10)
    ]

    lazy.executemany(sql, params)

    # Nothing inserted yet
    assert user_table.select_count() == 0

    # Commit
    lazy.commit()

    # All inserted
    assert user_table.select_count() == 10


def test_lazy_cursor_context_manager_no_commit(user_table):
    """Test that context manager exit doesn't auto-commit"""
    with user_table.cursor(lazy=True) as lazy:
        sql = 'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)'
        params = {'name': 'Test', 'age': 25, 'email': 'test@example.com'}
        lazy.execute(sql, params)
        # Don't commit

    # Should not be in database
    count = user_table.select_count()
    assert count == 0


def test_lazy_cursor_reusable(user_table):
    """Test that lazy cursor can be reused for multiple commit cycles"""
    lazy = user_table.cursor(lazy=True)

    # First cycle
    lazy.execute(
        'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)',
        {'name': 'User1', 'age': 25, 'email': 'user1@example.com'}
    )
    lazy.commit()
    assert user_table.select_count() == 1

    # Clear query manually for reuse (implementation dependent)
    lazy.query = []

    # Second cycle
    lazy.execute(
        'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)',
        {'name': 'User2', 'age': 30, 'email': 'user2@example.com'}
    )
    lazy.commit()
    assert user_table.select_count() == 2


def test_lazy_cursor_performance_batch_insert(user_table):
    """Test that lazy cursor can handle large batches"""
    lazy = user_table.cursor(lazy=True)

    # Add 100 inserts
    for i in range(100):
        lazy.execute(
            'INSERT INTO users (name, age, email) VALUES (:name, :age, :email)',
            {'name': f'User{i}', 'age': 20 + i, 'email': f'user{i}@example.com'}
        )

    # Commit all at once
    lazy.commit()

    assert user_table.select_count() == 100

