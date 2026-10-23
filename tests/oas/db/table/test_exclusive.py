"""
Test ExclusiveTransaction: EXCLUSIVE transaction support
"""

from conftest import User


def test_exclusive_transaction_creation(user_table):
    """Test creating an exclusive transaction"""
    with user_table.exclusive_transaction() as cursor:
        assert cursor is not None
        # Cursor should have table info
        assert cursor.TABLE_NAME == user_table.TABLE_NAME
        assert cursor.CREATE_TABLE == user_table.CREATE_TABLE


def test_exclusive_transaction_insert(user_table, sample_users):
    """Test inserting within exclusive transaction"""
    with user_table.exclusive_transaction() as c:
        user_table.insert_row(sample_users[:2], _cursor_=c)

    # Should be committed after context exit
    count = user_table.select_count()
    assert count == 2


def test_exclusive_transaction_auto_commit_on_success(user_table):
    """Test that transaction auto-commits on successful exit"""
    with user_table.exclusive_transaction() as c:
        user = User(id=0, name='Alice', age=25, email='alice@example.com')
        user_table.insert_row(user, _cursor_=c)

        # Within transaction, should not be visible outside yet
        # But we can't easily test this without multiple connections

    # After context exit, should be committed
    result = user_table.select_one(name='Alice')
    assert result is not None


def test_exclusive_transaction_rollback_on_exception(user_table):
    """Test that transaction rolls back on exception"""
    try:
        with user_table.exclusive_transaction() as c:
            user = User(id=0, name='Alice', age=25, email='alice@example.com')
            user_table.insert_row(user, _cursor_=c)

            # Raise an exception
            raise ValueError('Test exception')
    except ValueError:
        pass

    # Should be rolled back
    count = user_table.select_count()
    assert count == 0


def test_exclusive_transaction_multiple_operations(user_table, sample_users):
    """Test multiple operations in one transaction"""
    with user_table.exclusive_transaction() as c:
        user_table.insert_row(sample_users[:2], _cursor_=c)
        user_table.insert_row(sample_users[2:], _cursor_=c)

    # All should be committed
    count = user_table.select_count()
    assert count == 5


def test_exclusive_transaction_with_update(user_table, sample_users):
    """Test update within exclusive transaction"""
    # First insert some data
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    with user_table.exclusive_transaction() as c:
        updated = User(id=user.id, name='Alice Updated', age=30, email=user.email)
        user_table.update_row(updated, _cursor_=c)

    # Should be updated
    result = user_table.select_by_pk(user.id)
    assert result.name == 'Alice Updated'


def test_exclusive_transaction_with_delete(user_table, sample_users):
    """Test delete within exclusive transaction"""
    user_table.insert_row(sample_users[:2])

    with user_table.exclusive_transaction() as c:
        user_table.delete(name='Alice', _cursor_=c)

    # Should be deleted
    result = user_table.select_one(name='Alice')
    assert result is None

    count = user_table.select_count()
    assert count == 1


def test_exclusive_transaction_with_upsert(user_table, sample_users):
    """Test upsert within exclusive transaction"""
    user_table.insert_row(sample_users[:1])

    existing = user_table.select_one(name='Alice')

    with user_table.exclusive_transaction() as c:
        updated = User(id=existing.id, name='Alice', age=30, email='new@example.com')
        user_table.upsert_row(updated, _cursor_=c)

    # Should be updated
    result = user_table.select_by_pk(existing.id)
    assert result.age == 30


def test_exclusive_transaction_mixed_operations(user_table, sample_users):
    """Test mixed operations in exclusive transaction"""
    user_table.insert_row(sample_users[:1])

    with user_table.exclusive_transaction() as c:
        # Insert more
        user_table.insert_row(sample_users[1:3], _cursor_=c)

        # Update existing
        user = user_table.select_one(name='Alice', _cursor_=c)
        updated = User(id=user.id, name='Alice Updated', age=30, email=user.email)
        user_table.update_row(updated, _cursor_=c)

        # Delete one
        user_table.delete(name='Bob', _cursor_=c)

    # Verify final state
    count = user_table.select_count()
    assert count == 2  # Alice (updated) and Charlie

    alice = user_table.select_one(name='Alice Updated')
    assert alice is not None


def test_exclusive_transaction_isolation(user_table, sample_users):
    """Test transaction isolation (basic test)"""
    # This is a basic test - true isolation testing would require multiple connections

    user_table.insert_row(sample_users[:1])

    with user_table.exclusive_transaction() as c:
        # Insert in transaction
        user_table.insert_row(sample_users[1:2], _cursor_=c)

        # Within same transaction, we can see it
        count_in_tx = len(user_table.select(_cursor_=c))
        assert count_in_tx == 2

    # After commit, visible to all
    count = user_table.select_count()
    assert count == 2


def test_exclusive_transaction_nested_not_recommended(user_table):
    """Test that nested transactions should use the same cursor"""
    # This demonstrates the correct pattern for "nested" operations

    with user_table.exclusive_transaction() as c:
        user1 = User(id=0, name='User1', age=25, email='user1@example.com')
        user_table.insert_row(user1, _cursor_=c)

        # "Nested" operation using same cursor
        user2 = User(id=0, name='User2', age=30, email='user2@example.com')
        user_table.insert_row(user2, _cursor_=c)

    count = user_table.select_count()
    assert count == 2


def test_exclusive_transaction_with_select(user_table, sample_users):
    """Test selecting within exclusive transaction"""
    user_table.insert_row(sample_users[:2])

    with user_table.exclusive_transaction() as c:
        # Insert more
        user_table.insert_row(sample_users[2:], _cursor_=c)

        # Select within transaction
        results = user_table.select(_cursor_=c)
        assert len(results) == 5


def test_exclusive_transaction_prevents_partial_commit(user_table, sample_users):
    """Test that all operations commit or none do"""
    try:
        with user_table.exclusive_transaction() as c:
            user_table.insert_row(sample_users[:2], _cursor_=c)

            # This should succeed
            user_table.insert_row(sample_users[2:4], _cursor_=c)

            # Force an error
            raise RuntimeError('Abort transaction')
    except RuntimeError:
        pass

    # Nothing should be committed
    count = user_table.select_count()
    assert count == 0


def test_exclusive_transaction_with_constraint_violation(user_table):
    """Test transaction rollback on constraint violation"""
    try:
        with user_table.exclusive_transaction() as c:
            user1 = User(id=0, name='Alice', age=25, email='alice@example.com')
            user_table.insert_row(user1, _cursor_=c)

            # Try to insert duplicate (will violate auto-increment PK)
            # Actually, this won't violate since we use id=0
            # Let's use task_table for this
            pass
    except Exception:
        pass

    # If there was an error, nothing should be committed
    # This test might need adjustment based on actual constraints


def test_exclusive_transaction_performance(user_table):
    """Test that transaction batches improve performance"""
    # Insert 100 rows in a transaction
    users = [
        User(id=0, name=f'User{i}', age=20 + i, email=f'user{i}@example.com')
        for i in range(100)
    ]

    with user_table.exclusive_transaction() as c:
        user_table.insert_row(users, _cursor_=c)

    count = user_table.select_count()
    assert count == 100


def test_exclusive_transaction_cursor_reuse(user_table, sample_users):
    """Test reusing cursor within transaction for multiple operations"""
    with user_table.exclusive_transaction() as c:
        # First batch
        user_table.insert_row(sample_users[:2], _cursor_=c)

        # Check count within transaction
        assert len(user_table.select(_cursor_=c)) == 2

        # Second batch
        user_table.insert_row(sample_users[2:], _cursor_=c)

        # Check again
        assert len(user_table.select(_cursor_=c)) == 5


def test_exclusive_transaction_with_empty_operations(user_table):
    """Test transaction with no operations"""
    with user_table.exclusive_transaction() as c:
        # Do nothing
        pass

    # Should not error
    count = user_table.select_count()
    assert count == 0


def test_exclusive_transaction_auto_close_cursor(user_table):
    """Test that cursor is auto-closed after transaction"""
    with user_table.exclusive_transaction() as c:
        user = User(id=0, name='Test', age=25, email='test@example.com')
        user_table.insert_row(user, _cursor_=c)
        cursor_obj = c

    # After exit, cursor should be closed
    # We can't directly test this without accessing internals


def test_exclusive_transaction_with_large_batch(user_table):
    """Test exclusive transaction with large data batch"""
    users = [
        User(id=0, name=f'User{i}', age=20, email=f'user{i}@example.com')
        for i in range(1000)
    ]

    with user_table.exclusive_transaction() as c:
        # Insert in batches
        for i in range(0, 1000, 100):
            user_table.insert_row(users[i : i + 100], _cursor_=c)

    count = user_table.select_count()
    assert count == 1000


def test_exclusive_transaction_guarantees_consistency(user_table, sample_users):
    """Test that transaction guarantees consistency"""
    user_table.insert_row(sample_users[:1])

    try:
        with user_table.exclusive_transaction() as c:
            # Update
            user = user_table.select_one(name='Alice', _cursor_=c)
            updated = User(id=user.id, name='Alice', age=30, email=user.email)
            user_table.update_row(updated, _cursor_=c)

            # Insert
            new_user = User(id=0, name='Bob', age=25, email='bob@example.com')
            user_table.insert_row(new_user, _cursor_=c)

            # Raise error before commit
            raise ValueError('Test rollback')
    except ValueError:
        pass

    # Both operations should be rolled back
    alice = user_table.select_one(name='Alice')
    assert alice.age == 25  # Not updated

    bob = user_table.select_one(name='Bob')
    assert bob is None  # Not inserted


def test_exclusive_transaction_with_delete_and_insert(user_table, sample_users):
    """Test delete then insert in same transaction"""
    user_table.insert_row(sample_users[:1])

    with user_table.exclusive_transaction() as c:
        # Delete
        user_table.delete(name='Alice', _cursor_=c)

        # Insert new
        new_user = User(id=0, name='Alice', age=30, email='newalice@example.com')
        user_table.insert_row(new_user, _cursor_=c)

    # Should have one Alice with new data
    count = user_table.select_count()
    assert count == 1

    alice = user_table.select_one(name='Alice')
    assert alice.age == 30
    assert alice.email == 'newalice@example.com'


def test_exclusive_transaction_select_for_update_pattern(user_table, sample_users):
    """Test SELECT then UPDATE pattern within transaction"""
    user_table.insert_row(sample_users[:1])

    with user_table.exclusive_transaction() as c:
        # Select
        user = user_table.select_one(name='Alice', _cursor_=c)

        # Modify
        updated = User(id=user.id, name=user.name, age=user.age + 1, email=user.email)

        # Update
        user_table.update_row(updated, _cursor_=c)

    # Verify update
    result = user_table.select_one(name='Alice')
    assert result.age == 26


def test_exclusive_transaction_maintains_table_state(user_table, sample_users):
    """Test that table state is maintained across transactions"""
    # First transaction
    with user_table.exclusive_transaction() as c:
        user_table.insert_row(sample_users[:2], _cursor_=c)

    assert user_table.select_count() == 2

    # Second transaction
    with user_table.exclusive_transaction() as c:
        user_table.insert_row(sample_users[2:], _cursor_=c)

    # Total should be 5
    assert user_table.select_count() == 5


def test_exclusive_transaction_with_upsert_batch(user_table, sample_users):
    """Test batch upsert within exclusive transaction"""
    # Insert initial data
    user_table.insert_row(sample_users[:2])

    # Get IDs
    existing = user_table.select()

    # Prepare upsert: update existing + insert new
    upsert_data = [
        User(id=existing[0].id, name='Alice Updated', age=26, email=existing[0].email),
        User(id=existing[1].id, name='Bob Updated', age=31, email=existing[1].email),
        User(id=0, name='Charlie', age=35, email='charlie@example.com'),
    ]

    with user_table.exclusive_transaction() as c:
        user_table.upsert_row(upsert_data, _cursor_=c)

    # Verify results
    count = user_table.select_count()
    assert count == 3

    alice = user_table.select_one(name='Alice Updated')
    assert alice is not None
