"""
Test SELECT operations: select, select_one, select_by_sql, select_one_by_sql
"""
from conftest import User


def test_select_all(user_table, sample_users):
    """Test selecting all rows"""
    # Insert sample data
    user_table.insert_row(sample_users)

    # Select all
    results = user_table.select()
    assert len(results) == 5
    assert all(isinstance(user, User) for user in results)


def test_select_with_kwargs(user_table, sample_users):
    """Test selecting with keyword arguments"""
    user_table.insert_row(sample_users)

    # Select by name
    results = user_table.select(name='Alice')
    assert len(results) == 1
    assert results[0].name == 'Alice'

    # Select by age
    results = user_table.select(age=30)
    assert len(results) == 1
    assert results[0].name == 'Bob'


def test_select_with_multiple_conditions(user_table, sample_users):
    """Test selecting with multiple conditions"""
    user_table.insert_row(sample_users)

    results = user_table.select(name='Alice', age=25)
    assert len(results) == 1
    assert results[0].name == 'Alice'
    assert results[0].age == 25


def test_select_with_limit(user_table, sample_users):
    """Test selecting with LIMIT"""
    user_table.insert_row(sample_users)

    results = user_table.select(_limit_=3)
    assert len(results) == 3


def test_select_with_offset(user_table, sample_users):
    """Test selecting with OFFSET"""
    user_table.insert_row(sample_users)

    # Get all to see the order
    all_results = user_table.select(_orderby_='id')

    # Get with offset
    results = user_table.select(_limit_=2, _offset_=2, _orderby_='id')
    assert len(results) == 2
    assert results[0].id == all_results[2].id


def test_select_with_orderby(user_table, sample_users):
    """Test selecting with ORDER BY"""
    user_table.insert_row(sample_users)

    results = user_table.select(_orderby_='age')
    ages = [user.age for user in results]
    assert ages == sorted(ages)


def test_select_with_orderby_desc(user_table, sample_users):
    """Test selecting with ORDER BY DESC"""
    user_table.insert_row(sample_users)

    results = user_table.select(_orderby_desc_='age')
    ages = [user.age for user in results]
    assert ages == sorted(ages, reverse=True)


def test_select_with_groupby(user_table):
    """Test selecting with GROUP BY"""
    # Insert users with duplicate ages
    users = [
        User(id=0, name='Alice', age=25, email='alice@example.com'),
        User(id=0, name='Bob', age=25, email='bob@example.com'),
        User(id=0, name='Charlie', age=30, email='charlie@example.com'),
    ]
    user_table.insert_row(users)

    # This should group by age and return representative rows
    results = user_table.select(_groupby_='age', _orderby_='age')
    assert len(results) == 2  # Two unique ages


def test_select_one(user_table, sample_users):
    """Test selecting one row"""
    user_table.insert_row(sample_users)

    result = user_table.select_one(name='Alice')
    assert result is not None
    assert isinstance(result, User)
    assert result.name == 'Alice'


def test_select_one_not_found(user_table, sample_users):
    """Test select_one when no match found"""
    user_table.insert_row(sample_users)

    result = user_table.select_one(name='NonExistent')
    assert result is None


def test_select_one_empty_table(user_table):
    """Test select_one on empty table"""
    result = user_table.select_one(name='Alice')
    assert result is None


def test_select_one_with_orderby(user_table, sample_users):
    """Test select_one with ORDER BY (gets first after ordering)"""
    user_table.insert_row(sample_users)

    # Get youngest user
    result = user_table.select_one(_orderby_='age')
    assert result is not None
    assert result.age == 25

    # Get oldest user
    result = user_table.select_one(_orderby_desc_='age')
    assert result is not None
    assert result.age == 35


def test_select_one_with_offset(user_table, sample_users):
    """Test select_one with OFFSET"""
    user_table.insert_row(sample_users)

    # Get second user when ordered by age
    result = user_table.select_one(_orderby_='age', _offset_=1)
    assert result is not None
    assert result.age == 28  # Second youngest


def test_select_with_custom_cursor(user_table, sample_users):
    """Test select using a custom cursor"""
    user_table.insert_row(sample_users)

    with user_table.cursor() as c:
        results = user_table.select(name='Alice', _cursor_=c)
        assert len(results) == 1
        assert results[0].name == 'Alice'


def test_select_empty_result(user_table):
    """Test select when no results match"""
    results = user_table.select(name='NonExistent')
    assert results == []
    assert isinstance(results, list)


def test_select_all_fields_present(user_table, sample_users):
    """Test that all fields are properly returned"""
    user_table.insert_row(sample_users[:1])

    result = user_table.select_one(name='Alice')
    assert result.id > 0  # Auto-generated
    assert result.name == 'Alice'
    assert result.age == 25
    assert result.email == 'alice@example.com'


def test_select_multiple_orderby_fields(user_table):
    """Test selecting with multiple ORDER BY fields"""
    # Insert users with same age but different names
    users = [
        User(id=0, name='Zoe', age=25, email='zoe@example.com'),
        User(id=0, name='Alice', age=25, email='alice@example.com'),
        User(id=0, name='Bob', age=30, email='bob@example.com'),
    ]
    user_table.insert_row(users)

    # Order by age then name
    results = user_table.select(_orderby_=['age', 'name'])
    assert results[0].name == 'Alice'  # age=25, name='Alice'
    assert results[1].name == 'Zoe'  # age=25, name='Zoe'
    assert results[2].name == 'Bob'  # age=30


def test_select_with_limit_orderby_offset_combined(user_table, sample_users):
    """Test complex select with multiple parameters"""
    user_table.insert_row(sample_users)

    # Get 2nd and 3rd oldest users
    results = user_table.select(
        _orderby_='age',
        _limit_=2,
        _offset_=1
    )
    assert len(results) == 2
    # Should get ages: 28, 30 (skipping 25)
    assert results[0].age == 28
    assert results[1].age == 30


def test_select_by_sql_all(user_table, sample_users):
    """Test select_by_sql to get all rows"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users'
    results = user_table.select_by_sql(sql)
    assert len(results) == 5
    assert all(isinstance(user, User) for user in results)


def test_select_by_sql_with_params(user_table, sample_users):
    """Test select_by_sql with parameters"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users WHERE age > ?'
    results = user_table.select_by_sql(sql, [28])
    assert len(results) == 3
    assert all(user.age > 28 for user in results)


def test_select_by_sql_with_dict_params(user_table, sample_users):
    """Test select_by_sql with dict parameters"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users WHERE name = :name AND age = :age'
    results = user_table.select_by_sql(sql, {'name': 'Alice', 'age': 25})
    assert len(results) == 1
    assert results[0].name == 'Alice'


def test_select_by_sql_with_orderby(user_table, sample_users):
    """Test select_by_sql with ORDER BY"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users ORDER BY age DESC'
    results = user_table.select_by_sql(sql)
    ages = [user.age for user in results]
    assert ages == sorted(ages, reverse=True)


def test_select_by_sql_with_limit(user_table, sample_users):
    """Test select_by_sql with LIMIT"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users LIMIT 3'
    results = user_table.select_by_sql(sql)
    assert len(results) == 3


def test_select_by_sql_complex_query(user_table, sample_users):
    """Test select_by_sql with complex query"""
    user_table.insert_row(sample_users)

    sql = '''
        SELECT * FROM users
        WHERE age >= :min_age AND age <= :max_age
        ORDER BY age
    '''
    results = user_table.select_by_sql(sql, {'min_age': 28, 'max_age': 32})
    assert len(results) == 3
    assert results[0].age == 28
    assert results[2].age == 32


def test_select_by_sql_with_cursor(user_table, sample_users):
    """Test select_by_sql with custom cursor"""
    user_table.insert_row(sample_users)

    with user_table.cursor() as c:
        sql = 'SELECT * FROM users WHERE name = ?'
        results = user_table.select_by_sql(sql, ['Alice'], _cursor_=c)
        assert len(results) == 1


def test_select_one_by_sql(user_table, sample_users):
    """Test select_one_by_sql"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users WHERE name = ?'
    result = user_table.select_one_by_sql(sql, ['Alice'])
    assert result is not None
    assert isinstance(result, User)
    assert result.name == 'Alice'


def test_select_one_by_sql_not_found(user_table, sample_users):
    """Test select_one_by_sql when no match"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users WHERE name = ?'
    result = user_table.select_one_by_sql(sql, ['NonExistent'])
    assert result is None


def test_select_one_by_sql_with_dict_params(user_table, sample_users):
    """Test select_one_by_sql with dict parameters"""
    user_table.insert_row(sample_users)

    sql = 'SELECT * FROM users WHERE name = :name'
    result = user_table.select_one_by_sql(sql, {'name': 'Bob'})
    assert result is not None
    assert result.name == 'Bob'


def test_select_one_by_sql_first_match(user_table):
    """Test select_one_by_sql returns first match"""
    # Insert users with same age
    users = [
        User(id=0, name='Alice', age=25, email='alice@example.com'),
        User(id=0, name='Bob', age=25, email='bob@example.com'),
    ]
    user_table.insert_row(users)

    sql = 'SELECT * FROM users WHERE age = ? ORDER BY name'
    result = user_table.select_one_by_sql(sql, [25])
    assert result is not None
    assert result.name == 'Alice'  # First alphabetically


def test_select_one_by_sql_with_cursor(user_table, sample_users):
    """Test select_one_by_sql with custom cursor"""
    user_table.insert_row(sample_users)

    with user_table.cursor() as c:
        sql = 'SELECT * FROM users WHERE age = ?'
        result = user_table.select_one_by_sql(sql, [30], _cursor_=c)
        assert result is not None
        assert result.age == 30


def test_select_by_sql_empty_result(user_table):
    """Test select_by_sql with no matches"""
    sql = 'SELECT * FROM users WHERE name = ?'
    results = user_table.select_by_sql(sql, ['NonExistent'])
    assert results == []


def test_select_by_sql_no_params(user_table, sample_users):
    """Test select_by_sql without parameters"""
    user_table.insert_row(sample_users[:1])

    sql = 'SELECT * FROM users'
    results = user_table.select_by_sql(sql)
    assert len(results) == 1


def test_select_one_by_sql_no_params(user_table, sample_users):
    """Test select_one_by_sql without parameters"""
    user_table.insert_row(sample_users[:1])

    sql = 'SELECT * FROM users LIMIT 1'
    result = user_table.select_one_by_sql(sql)
    assert result is not None


def test_select_count_using_sql(user_table, sample_users):
    """Test counting rows using select_one_by_sql"""
    user_table.insert_row(sample_users)

    # Note: This won't work directly because COUNT returns a different schema
    # But we can test that the query executes
    sql = 'SELECT * FROM users'
    results = user_table.select_by_sql(sql)
    assert len(results) == 5


def test_select_by_primary_key_using_sql(user_table, sample_users):
    """Test selecting by primary key using SQL"""
    user_table.insert_row(sample_users)

    # Get first user's ID
    all_users = user_table.select(_orderby_='id', _limit_=1)
    first_id = all_users[0].id

    # Select by PK using SQL
    sql = 'SELECT * FROM users WHERE id = ?'
    result = user_table.select_one_by_sql(sql, [first_id])
    assert result is not None
    assert result.id == first_id

