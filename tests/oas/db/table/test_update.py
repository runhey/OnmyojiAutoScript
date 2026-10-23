"""
Test UPDATE operations: update_row with various configurations
"""

import pytest
from conftest import Product, User

from oas.db.table import TableError


def test_update_single_row(user_table, sample_users):
    """Test updating a single row"""
    user_table.insert_row(sample_users)

    # Get a user to update
    user = user_table.select_one(name='Alice')
    assert user is not None

    # Update age
    updated_user = User(id=user.id, name='Alice', age=30, email=user.email)
    user_table.update_row(updated_user)

    # Verify update
    result = user_table.select_by_pk(user.id)
    assert result.age == 30


def test_update_multiple_rows(user_table, sample_users):
    """Test updating multiple rows"""
    user_table.insert_row(sample_users)

    # Get all users and update their ages
    users = user_table.select()
    updated_users = [
        User(id=u.id, name=u.name, age=u.age + 5, email=u.email) for u in users
    ]

    user_table.update_row(updated_users)

    # Verify updates
    results = user_table.select(_orderby_='id')
    for original, updated in zip(sample_users, results):
        assert updated.age == original.age + 5


def test_update_specific_fields(user_table, sample_users):
    """Test updating only specific fields"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')
    original_email = user.email

    # Update only age
    updated_user = User(
        id=user.id, name='Alice Updated', age=30, email='newemail@example.com'
    )
    user_table.update_row(updated_user, updates='age')

    # Verify only age was updated
    result = user_table.select_by_pk(user.id)
    assert result.age == 30
    assert result.name == 'Alice'  # Should not change
    assert result.email == original_email  # Should not change


def test_update_multiple_fields(user_table, sample_users):
    """Test updating multiple specific fields"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')
    original_email = user.email

    # Update name and age
    updated_user = User(
        id=user.id, name='Alice Updated', age=30, email='newemail@example.com'
    )
    user_table.update_row(updated_user, updates=['name', 'age'])

    # Verify
    result = user_table.select_by_pk(user.id)
    assert result.name == 'Alice Updated'
    assert result.age == 30
    assert result.email == original_email  # Should not change


def test_update_with_cursor(user_table, sample_users):
    """Test updating with a provided cursor"""
    user_table.insert_row(sample_users[:2])

    users = user_table.select()
    updated_users = [
        User(id=u.id, name=f'{u.name} Updated', age=u.age, email=u.email) for u in users
    ]

    with user_table.cursor() as c:
        user_table.update_row(updated_users, _cursor_=c)
        c.commit()

    # Verify
    results = user_table.select()
    assert all('Updated' in u.name for u in results)


def test_update_without_pk(user_table, sample_users):
    """Test that rows without PK are not updated"""
    user_table.insert_row(sample_users[:1])

    # Try to update with pk=0 (invalid)
    invalid_user = User(id=0, name='No PK', age=99, email='nopk@example.com')
    user_table.update_row(invalid_user)

    # Verify nothing changed
    count = user_table.select_count(age=99)
    assert count == 0


def test_update_negative_pk(user_table, sample_users):
    """Test that rows with negative PK are not updated"""
    user_table.insert_row(sample_users[:1])

    # Try to update with negative pk
    invalid_user = User(id=-1, name='Negative PK', age=99, email='neg@example.com')
    user_table.update_row(invalid_user)

    # Verify nothing changed
    count = user_table.select_count(age=99)
    assert count == 0


def test_update_multiple_rows_filter_by_pk(user_table, sample_users):
    """Test updating list with some rows having invalid PKs"""
    user_table.insert_row(sample_users[:2])

    users = user_table.select()

    # Mix valid and invalid PKs
    updates = [
        User(id=users[0].id, name='Valid', age=100, email='valid@example.com'),
        User(id=0, name='Invalid', age=200, email='invalid@example.com'),  # Invalid
        User(id=users[1].id, name='Valid2', age=101, email='valid2@example.com'),
    ]

    user_table.update_row(updates)

    # Only valid PKs should be updated
    assert user_table.select_count(age=100) == 1
    assert user_table.select_count(age=101) == 1
    assert user_table.select_count(age=200) == 0


def test_update_no_fields_raises_error(user_table, sample_users):
    """Test that updating with no fields raises error"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    # Try to update with primary key as the only update field
    with pytest.raises(TableError):
        user_table.update_row(user, updates='id')


def test_update_all_fields_except_pk(user_table, sample_users):
    """Test updating all fields except primary key"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    # Update all fields (default behavior)
    updated = User(
        id=user.id, name='Alice Updated', age=99, email='updated@example.com'
    )
    user_table.update_row(updated)

    result = user_table.select_by_pk(user.id)
    assert result.name == 'Alice Updated'
    assert result.age == 99
    assert result.email == 'updated@example.com'


def test_update_preserves_primary_key(user_table, sample_users):
    """Test that primary key is never changed during update"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')
    original_id = user.id

    # Update with new data
    updated = User(id=user.id, name='Updated', age=99, email='updated@example.com')
    user_table.update_row(updated)

    result = user_table.select_by_pk(original_id)
    assert result is not None
    assert result.id == original_id


def test_update_nonexistent_pk(user_table):
    """Test updating a non-existent primary key"""
    # Try to update a user that doesn't exist
    user = User(id=999, name='NonExistent', age=30, email='none@example.com')
    user_table.update_row(user)

    # Verify nothing was added
    result = user_table.select_by_pk(999)
    assert result is None


def test_update_empty_list(user_table):
    """Test updating with empty list"""
    # Should do nothing without error
    user_table.update_row([])

    count = user_table.select_count()
    assert count == 0


def test_update_tuple_of_fields(user_table, sample_users):
    """Test updating with tuple of field names"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    updated = User(id=user.id, name='Updated', age=99, email='new@example.com')
    user_table.update_row(updated, updates=('name', 'age'))

    result = user_table.select_by_pk(user.id)
    assert result.name == 'Updated'
    assert result.age == 99
    assert result.email == user.email  # Should not change


def test_update_with_special_characters(user_table):
    """Test updating with special characters"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    inserted = user_table.select_one(name='Alice')

    # Update with special characters
    updated = User(id=inserted.id, name="O'Brien", age=30, email='o"brien@example.com')
    user_table.update_row(updated)

    result = user_table.select_by_pk(inserted.id)
    assert result.name == "O'Brien"
    assert result.email == 'o"brien@example.com'


def test_update_unicode(user_table):
    """Test updating with Unicode data"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.insert_row(user)

    inserted = user_table.select_one(name='Alice')

    updated = User(id=inserted.id, name='张三', age=30, email='zhangsan@example.com')
    user_table.update_row(updated)

    result = user_table.select_by_pk(inserted.id)
    assert result.name == '张三'


def test_update_float_values(product_table, sample_products):
    """Test updating float values"""
    product_table.insert_row(sample_products[:1])

    product = product_table.select_one(sku='SKU001')

    updated = Product(
        id=product.id, sku='SKU001', name='Laptop', price=1099.99, stock=5
    )
    product_table.update_row(updated)

    result = product_table.select_by_pk(product.id)
    assert result.price == 1099.99
    assert result.stock == 5


def test_update_to_zero_values(user_table, sample_users):
    """Test updating to zero values"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    # Update age to 0
    updated = User(id=user.id, name=user.name, age=0, email=user.email)
    user_table.update_row(updated)

    result = user_table.select_by_pk(user.id)
    assert result.age == 0


def test_update_in_transaction(user_table, sample_users):
    """Test multiple updates in a single transaction"""
    user_table.insert_row(sample_users[:3])

    users = user_table.select()

    with user_table.cursor() as c:
        for user in users:
            updated = User(
                id=user.id, name=f'{user.name} TX', age=user.age, email=user.email
            )
            user_table.update_row(updated, _cursor_=c)
        c.commit()

    # Verify all updated
    results = user_table.select()
    assert all('TX' in u.name for u in results)


def test_update_large_batch(user_table):
    """Test updating a large batch of rows"""
    users = [
        User(id=0, name=f'User{i}', age=20, email=f'user{i}@example.com')
        for i in range(100)
    ]
    user_table.insert_row(users)

    all_users = user_table.select()
    updated_users = [
        User(id=u.id, name=u.name, age=30, email=u.email) for u in all_users
    ]

    user_table.update_row(updated_users)

    # Verify all updated
    count = user_table.select_count(age=30)
    assert count == 100


def test_update_only_changed_fields(user_table, sample_users):
    """Test efficient update by specifying only changed fields"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')
    original_name = user.name
    original_email = user.email

    # Only update age (pass any values for other fields, they won't be updated)
    updated = User(id=user.id, name='Ignored', age=99, email='ignored@example.com')
    user_table.update_row(updated, updates='age')

    result = user_table.select_by_pk(user.id)
    assert result.age == 99
    assert result.name == original_name
    assert result.email == original_email


def test_update_respects_field_list_order(user_table, sample_users):
    """Test that field order in updates list doesn't matter"""
    user_table.insert_row(sample_users[:1])

    user = user_table.select_one(name='Alice')

    # Update with fields in different order
    updated = User(id=user.id, name='Updated', age=99, email='new@example.com')
    user_table.update_row(updated, updates=['email', 'name'])  # Reverse order

    result = user_table.select_by_pk(user.id)
    assert result.name == 'Updated'
    assert result.email == 'new@example.com'
    assert result.age == user.age  # Should not change
