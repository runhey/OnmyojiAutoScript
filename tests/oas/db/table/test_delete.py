"""
Test DELETE operations: delete, delete_row
"""

import pytest
from conftest import User

from oas.db.table import TableError


def test_delete_by_kwargs(user_table, sample_users):
    """Test deleting rows by keyword arguments"""
    user_table.insert_row(sample_users)

    # Delete by name
    user_table.delete(name='Alice')

    # Verify deletion
    result = user_table.select_one(name='Alice')
    assert result is None

    # Other users should still exist
    count = user_table.select_count()
    assert count == 4


def test_delete_multiple_conditions(user_table, sample_users):
    """Test deleting with multiple conditions"""
    user_table.insert_row(sample_users)

    # Delete by name and age
    user_table.delete(name='Bob', age=30)

    # Verify deletion
    result = user_table.select_one(name='Bob')
    assert result is None

    count = user_table.select_count()
    assert count == 4


def test_delete_no_match(user_table, sample_users):
    """Test deleting when no rows match"""
    user_table.insert_row(sample_users)

    # Delete non-existent user
    user_table.delete(name='NonExistent')

    # All users should still exist
    count = user_table.select_count()
    assert count == 5


def test_delete_without_conditions_raises_error(user_table, sample_users):
    """Test that delete without conditions raises error"""
    user_table.insert_row(sample_users)

    with pytest.raises(TableError):
        user_table.delete()


def test_delete_with_cursor(user_table, sample_users):
    """Test deleting with provided cursor"""
    user_table.insert_row(sample_users)

    with user_table.cursor() as c:
        user_table.delete(name='Alice', _cursor_=c)
        user_table.delete(name='Bob', _cursor_=c)
        c.commit()

    # Verify deletions
    count = user_table.select_count()
    assert count == 3


def test_delete_row_single(user_table, sample_users):
    """Test deleting a single row by primary key"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')
    user_table.delete_row(user)

    # Verify deletion
    result = user_table.select_by_pk(user.id)
    assert result is None

    count = user_table.select_count()
    assert count == 0


def test_delete_row_multiple(user_table, sample_users):
    """Test deleting multiple rows by primary key"""
    user_table.insert_row(sample_users)

    # Get users to delete
    users_to_delete = user_table.select(_limit_=3)
    user_table.delete_row(users_to_delete)

    # Verify deletions
    count = user_table.select_count()
    assert count == 2


def test_delete_row_without_pk(user_table, sample_users):
    """Test that rows without valid PK are not deleted"""
    user_table.insert_row(sample_users[:2])

    # Try to delete with invalid PK
    invalid_user = User(id=0, name='Invalid', age=99, email='invalid@example.com')
    user_table.delete_row(invalid_user)

    # Nothing should be deleted
    count = user_table.select_count()
    assert count == 2


def test_delete_row_negative_pk(user_table, sample_users):
    """Test that rows with negative PK are not deleted"""
    user_table.insert_row(sample_users[:2])

    invalid_user = User(id=-1, name='Invalid', age=99, email='invalid@example.com')
    user_table.delete_row(invalid_user)

    # Nothing should be deleted
    count = user_table.select_count()
    assert count == 2


def test_delete_row_nonexistent_pk(user_table):
    """Test deleting a row with non-existent PK"""
    user = User(id=999, name='NonExistent', age=30, email='none@example.com')
    user_table.delete_row(user)

    # Should not raise error, just do nothing
    count = user_table.select_count()
    assert count == 0


def test_delete_row_multiple_with_invalid_pks(user_table, sample_users):
    """Test deleting list with some invalid PKs"""
    user_table.insert_row(sample_users[:3])

    users = user_table.select()

    # Mix valid and invalid PKs
    to_delete = [
        users[0],  # Valid
        User(id=0, name='Invalid', age=99, email='invalid@example.com'),  # Invalid
        users[1],  # Valid
    ]

    user_table.delete_row(to_delete)

    # Only 2 should be deleted
    count = user_table.select_count()
    assert count == 1


def test_delete_row_with_cursor(user_table, sample_users):
    """Test delete_row with provided cursor"""
    user_table.insert_row(sample_users[:3])

    users = user_table.select()

    with user_table.cursor() as c:
        user_table.delete_row(users[:2], _cursor_=c)
        c.commit()

    count = user_table.select_count()
    assert count == 1


def test_delete_row_empty_list(user_table, sample_users):
    """Test deleting empty list"""
    user_table.insert_row(sample_users)

    user_table.delete_row([])

    # Nothing should be deleted
    count = user_table.select_count()
    assert count == 5


def test_delete_all_matching_rows(user_table):
    """Test deleting all rows matching a condition"""
    # Insert users with same age
    users = [
        User(id=0, name=f'User{i}', age=25, email=f'user{i}@example.com')
        for i in range(5)
    ]
    user_table.insert_row(users)

    # Delete all with age=25
    user_table.delete(age=25)

    count = user_table.select_count()
    assert count == 0


def test_delete_with_special_characters(user_table):
    """Test deleting with special characters in values"""
    user = User(id=0, name="O'Brien", age=30, email='obrien@example.com')
    user_table.insert_row(user)

    user_table.delete(name="O'Brien")

    result = user_table.select_one(name="O'Brien")
    assert result is None


def test_delete_with_unicode(user_table):
    """Test deleting with Unicode data"""
    user = User(id=0, name='张三', age=25, email='zhangsan@example.com')
    user_table.insert_row(user)

    user_table.delete(name='张三')

    result = user_table.select_one(name='张三')
    assert result is None


def test_delete_in_transaction(user_table, sample_users):
    """Test multiple deletes in a transaction"""
    user_table.insert_row(sample_users)

    with user_table.cursor() as c:
        user_table.delete(name='Alice', _cursor_=c)
        user_table.delete(name='Bob', _cursor_=c)
        user_table.delete(name='Charlie', _cursor_=c)
        c.commit()

    count = user_table.select_count()
    assert count == 2


def test_delete_and_reinsert(user_table):
    """Test deleting and reinserting with same data"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    inserted = user_table.select_one(name='Alice')
    original_id = inserted.id

    # Delete
    user_table.delete_row(inserted)

    # Reinsert
    user_table.insert_row(user)

    # Should get a new ID
    reinserted = user_table.select_one(name='Alice')
    assert reinserted.id != original_id


def test_delete_by_multiple_values(user_table, sample_users):
    """Test deleting with exact match on multiple fields"""
    user_table.insert_row(sample_users)

    # Delete Alice specifically
    user_table.delete(name='Alice', age=25, email='alice@example.com')

    result = user_table.select_one(name='Alice')
    assert result is None


def test_delete_partial_batch(user_table, sample_users):
    """Test deleting some rows from a batch"""
    user_table.insert_row(sample_users)

    # Get first 3 users
    users = user_table.select(_limit_=3, _orderby_='id')

    # Delete them
    user_table.delete_row(users)

    # Should have 2 left
    count = user_table.select_count()
    assert count == 2


def test_delete_and_verify_cascade(user_table, sample_users):
    """Test that delete actually removes rows from database"""
    user_table.insert_row(sample_users)

    initial_count = user_table.select_count()

    user_table.delete(age=25)

    after_count = user_table.select_count()

    assert after_count < initial_count
    assert after_count == initial_count - 1


def test_delete_row_large_batch(user_table):
    """Test deleting a large batch of rows"""
    users = [
        User(id=0, name=f'User{i}', age=20 + i, email=f'user{i}@example.com')
        for i in range(100)
    ]
    user_table.insert_row(users)

    # Get all users
    all_users = user_table.select()

    # Delete first 50
    user_table.delete_row(all_users[:50])

    count = user_table.select_count()
    assert count == 50


def test_delete_with_zero_values(user_table):
    """Test deleting with zero values"""
    user = User(id=0, name='Zero Age', age=0, email='zero@example.com')
    user_table.insert_row(user)

    user_table.delete(age=0)

    result = user_table.select_one(name='Zero Age')
    assert result is None


def test_delete_preserves_other_rows(user_table, sample_users):
    """Test that delete only affects matching rows"""
    user_table.insert_row(sample_users)

    # Get all names before
    names_before = {u.name for u in user_table.select()}

    # Delete one
    user_table.delete(name='Alice')

    # Get all names after
    names_after = {u.name for u in user_table.select()}

    # Check that only Alice is gone
    assert 'Alice' not in names_after
    assert names_before - {'Alice'} == names_after


def test_delete_by_integer_field(user_table, sample_users):
    """Test deleting by integer field"""
    user_table.insert_row(sample_users)

    # Delete all 30-year-olds
    user_table.delete(age=30)

    result = user_table.select_one(age=30)
    assert result is None

    # Others should still exist
    count = user_table.select_count()
    assert count == 4


def test_delete_row_then_insert_same_data(user_table):
    """Test that after delete_row, can insert same data with new ID"""
    user = User(id=0, name='Test', age=25, email='test@example.com')
    user_table.insert_row(user)

    first = user_table.select_one(name='Test')
    first_id = first.id

    # Delete
    user_table.delete_row(first)

    # Insert again
    user_table.insert_row(user)

    second = user_table.select_one(name='Test')
    assert second.id > first_id
    assert second.name == first.name
