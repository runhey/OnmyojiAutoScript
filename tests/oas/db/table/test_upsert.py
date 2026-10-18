"""
Test UPSERT operations: insert or update on conflict
"""
import pytest
from conftest import Product, User

from oas.db.table import TableError


def test_upsert_insert_new_row(user_table):
    """Test upsert when row doesn't exist (should insert)"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')
    user_table.upsert_row(user)

    result = user_table.select_one(name='Alice')
    assert result is not None
    assert result.age == 25


def test_upsert_update_existing_row(user_table, sample_users):
    """Test upsert when row exists (should update)"""
    user_table.insert_row(sample_users[:1])

    # Get the inserted user
    existing = user_table.select_one(name='Alice')

    # Upsert with same PK
    updated = User(id=existing.id, name='Alice Updated', age=30, email='updated@example.com')
    user_table.upsert_row(updated)

    # Should have updated, not inserted
    count = user_table.select_count()
    assert count == 1

    result = user_table.select_by_pk(existing.id)
    assert result.name == 'Alice Updated'
    assert result.age == 30


def test_upsert_with_unique_constraint(product_table):
    """Test upsert with unique constraint conflict"""
    product1 = Product(id=0, sku='SKU001', name='Product 1', price=10.0, stock=5)
    product_table.insert_row(product1)

    # Upsert with same SKU but different ID
    product2 = Product(id=0, sku='SKU001', name='Updated Product', price=20.0, stock=10)
    product_table.upsert_row(product2, conflicts='sku')

    # Should have updated, not inserted
    count = product_table.select_count()
    assert count == 1

    result = product_table.select_one(sku='SKU001')
    assert result.name == 'Updated Product'
    assert result.price == 20.0
    assert result.stock == 10


def test_upsert_multiple_rows(user_table, sample_users):
    """Test upserting multiple rows"""
    # Insert first batch
    user_table.insert_row(sample_users[:2])

    # Get their IDs
    existing = user_table.select()

    # Prepare upsert batch: update existing + insert new
    upsert_data = [
        User(id=existing[0].id, name='Alice Updated', age=26, email='alice2@example.com'),
        User(id=existing[1].id, name='Bob Updated', age=31, email='bob2@example.com'),
        User(id=0, name='Charlie', age=35, email='charlie@example.com'),
    ]

    user_table.upsert_row(upsert_data)

    # Should have 3 rows total
    count = user_table.select_count()
    assert count == 3

    # Verify updates
    alice = user_table.select_one(name='Alice Updated')
    assert alice.age == 26


def test_upsert_with_specific_updates(product_table):
    """Test upsert updating only specific fields"""
    product = Product(id=0, sku='SKU001', name='Original', price=10.0, stock=5)
    product_table.insert_row(product)

    # Upsert with conflict on SKU, update only price
    updated = Product(id=0, sku='SKU001', name='Should Not Change', price=20.0, stock=999)
    product_table.upsert_row(updated, conflicts='sku', updates='price')

    result = product_table.select_one(sku='SKU001')
    assert result.name == 'Original'  # Should not change
    assert result.price == 20.0  # Should update
    assert result.stock == 5  # Should not change


def test_upsert_with_multiple_conflict_fields(product_table):
    """Test upsert with multiple conflict fields"""
    # This tests ON CONFLICT (field1, field2)
    product = Product(id=0, sku='SKU001', name='Product', price=10.0, stock=5)
    product_table.insert_row(product)

    # Upsert with conflicts on multiple fields
    updated = Product(id=0, sku='SKU001', name='Product', price=20.0, stock=10)
    product_table.upsert_row(updated, conflicts=['sku', 'name'], updates='price')

    # Note: This might insert or update depending on whether both fields match
    result = product_table.select_one(sku='SKU001', name='Product')
    assert result is not None
    assert result.price == 20.0  # Should update
    assert result.stock == 5  # Should not change


def test_upsert_with_multiple_update_fields(user_table, sample_users):
    """Test upsert updating multiple specific fields"""
    user_table.insert_row(sample_users[:1])

    existing = user_table.select_one(name='Alice')
    original_email = existing.email

    # Upsert updating only name and age
    updated = User(id=existing.id, name='Alice Updated', age=30, email='new@example.com')
    user_table.upsert_row(updated, updates=['name', 'age'])

    result = user_table.select_by_pk(existing.id)
    assert result.name == 'Alice Updated'
    assert result.age == 30
    assert result.email == original_email  # Should not change


def test_upsert_default_conflicts_to_pk(user_table, sample_users):
    """Test that upsert defaults conflicts to PRIMARY_KEY"""
    user_table.insert_row(sample_users[:1])

    existing = user_table.select_one(name='Alice')

    # Upsert without specifying conflicts (should use PK)
    updated = User(id=existing.id, name='Alice Updated', age=30, email='updated@example.com')
    user_table.upsert_row(updated)

    count = user_table.select_count()
    assert count == 1

    result = user_table.select_by_pk(existing.id)
    assert result.name == 'Alice Updated'


def test_upsert_with_cursor(user_table, sample_users):
    """Test upsert with provided cursor"""
    with user_table.cursor() as c:
        user_table.upsert_row(sample_users[:2], _cursor_=c)
        c.commit()

    count = user_table.select_count()
    assert count == 2


def test_upsert_empty_list(user_table):
    """Test upserting empty list"""
    user_table.upsert_row([])

    count = user_table.select_count()
    assert count == 0


def test_upsert_preserves_auto_increment(user_table):
    """Test that upsert preserves auto-increment sequence"""
    user1 = User(id=0, name='User1', age=20, email='user1@example.com')
    user_table.upsert_row(user1)

    first = user_table.select_one(name='User1')
    first_id = first.id

    # Upsert another
    user2 = User(id=0, name='User2', age=21, email='user2@example.com')
    user_table.upsert_row(user2)

    second = user_table.select_one(name='User2')
    assert second.id > first_id


def test_upsert_conflict_update_error_conditions(user_table):
    """Test error when conflicts and updates have issues"""
    user = User(id=0, name='Alice', age=25, email='alice@example.com')

    # Error: trying to update the conflict field
    with pytest.raises(TableError):
        user_table.upsert_row(user, conflicts='id', updates='id')


def test_upsert_insert_multiple_then_update(user_table):
    """Test inserting multiple rows then updating them via upsert"""
    users = [
        User(id=0, name=f'User{i}', age=20 + i, email=f'user{i}@example.com')
        for i in range(5)
    ]
    user_table.upsert_row(users)

    # Get their IDs
    inserted = user_table.select(_orderby_='name')

    # Update all via upsert
    updates = [
        User(id=u.id, name=u.name, age=u.age + 10, email=u.email)
        for u in inserted
    ]
    user_table.upsert_row(updates)

    # Verify still 5 rows with updated ages
    count = user_table.select_count()
    assert count == 5

    results = user_table.select()
    assert all(u.age >= 30 for u in results)


def test_upsert_with_special_characters(user_table):
    """Test upsert with special characters"""
    user = User(id=0, name="O'Brien", age=25, email='obrien@example.com')
    user_table.upsert_row(user)

    # Upsert again to update
    inserted = user_table.select_one(name="O'Brien")
    updated = User(id=inserted.id, name="O'Brien", age=30, email='obrien2@example.com')
    user_table.upsert_row(updated)

    count = user_table.select_count()
    assert count == 1

    result = user_table.select_by_pk(inserted.id)
    assert result.age == 30


def test_upsert_with_unicode(user_table):
    """Test upsert with Unicode data"""
    user = User(id=0, name='张三', age=25, email='zhangsan@example.com')
    user_table.upsert_row(user)

    inserted = user_table.select_one(name='张三')
    updated = User(id=inserted.id, name='张三', age=30, email='updated@example.com')
    user_table.upsert_row(updated)

    result = user_table.select_by_pk(inserted.id)
    assert result.age == 30


def test_upsert_large_batch(user_table):
    """Test upserting a large batch with mixed operations (insert + update)"""
    # Step 1: Insert 100 initial records
    initial_users = [
        User(id=0, name=f'User{i}', age=20, email=f'user{i}@example.com')
        for i in range(100)
    ]
    user_table.upsert_row(initial_users)
    assert user_table.select_count() == 100

    # Step 2: Mixed upsert - update first 50, insert 50 new
    inserted = user_table.select(_orderby_='id')

    # Update first 50 (change age to 30)
    updates = [
        User(id=inserted[i].id, name=inserted[i].name, age=30, email=inserted[i].email)
        for i in range(50)
    ]

    # Insert 50 new (age 25)
    new_inserts = [
        User(id=0, name=f'NewUser{i}', age=25, email=f'newuser{i}@example.com')
        for i in range(50)
    ]

    # Mixed upsert: 50 updates + 50 inserts
    mixed_batch = updates + new_inserts
    user_table.upsert_row(mixed_batch)

    # Verify results
    assert user_table.select_count() == 150  # 100 original + 50 new
    assert user_table.select_count(age=30) == 50  # Updated records
    assert user_table.select_count(age=25) == 50  # New records
    assert user_table.select_count(age=20) == 50  # Unchanged records

    # Verify updates worked correctly
    for i in range(50):
        user = user_table.select_by_pk(inserted[i].id)
        assert user.age == 30  # Should be updated


def test_upsert_conflict_on_non_pk_field(product_table):
    """Test upsert with conflict on non-primary-key field"""
    product1 = Product(id=0, sku='SKU001', name='Product 1', price=10.0, stock=5)
    product_table.insert_row(product1)

    # Different ID but same SKU - should update existing
    product2 = Product(id=0, sku='SKU001', name='Updated', price=20.0, stock=10)
    product_table.upsert_row(product2, conflicts='sku')

    # Should only have 1 row
    assert product_table.select_count() == 1

    result = product_table.select_one(sku='SKU001')
    assert result.name == 'Updated'


def test_upsert_tuple_conflicts_and_updates(user_table, sample_users):
    """Test upsert with tuple for conflicts and updates"""
    user_table.insert_row(sample_users[:1])

    existing = user_table.select_one(name='Alice')

    updated = User(id=existing.id, name='Updated', age=30, email='new@example.com')
    user_table.upsert_row(updated, conflicts=('id',), updates=('name', 'age'))

    result = user_table.select_by_pk(existing.id)
    assert result.name == 'Updated'
    assert result.age == 30
    assert result.email == existing.email  # Should not change


def test_upsert_in_transaction(user_table, sample_users):
    """Test multiple upserts in a transaction"""
    with user_table.cursor() as c:
        user_table.upsert_row(sample_users[:2], _cursor_=c)

        # Update one of them
        existing = user_table.select(_cursor_=c)
        updated = User(id=existing[0].id, name='Updated', age=99, email=existing[0].email)
        user_table.upsert_row(updated, _cursor_=c)

        c.commit()

    # Should have 2 rows, one updated
    assert user_table.select_count() == 2
    assert user_table.select_count(age=99) == 1


def test_upsert_all_fields_except_conflicts(product_table):
    """Test that upsert updates all fields except conflict fields by default"""
    product = Product(id=0, sku='SKU001', name='Original', price=10.0, stock=5)
    product_table.insert_row(product)

    # Upsert with conflict on sku (default updates should be all except id and sku)
    updated = Product(id=0, sku='SKU001', name='Updated', price=20.0, stock=10)
    product_table.upsert_row(updated, conflicts='sku')

    result = product_table.select_one(sku='SKU001')
    assert result.sku == 'SKU001'  # Conflict field unchanged
    assert result.name == 'Updated'
    assert result.price == 20.0
    assert result.stock == 10

