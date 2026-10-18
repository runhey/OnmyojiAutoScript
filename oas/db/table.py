import sqlite3
from typing import Generic, TypeVar

import msgspec
from msgspec.structs import asdict

from oas.db.conn import SQLITE_POOL, SqlitePoolCursor
from oas.ext.cache import cached_property

T_model = TypeVar('T_model', bound=msgspec.Struct)


class TableError(Exception):
    """
    Raised when subclass of Table is not defined property
    """


def row_has_pk(row: T_model):
    """
    Whether row with PRIMARY_KEY value > 0
    """
    try:
        return row.id > 0
    except AttributeError:
        # Row does not have PRIMARY_KEY
        return False


def row_drop_zero_pk(row: dict):
    try:
        if row['id'] <= 0:
            row['id'] = None
    except KeyError:
        pass
    return row


class LazyCursor:
    def __init__(self, table):
        """
        LazyCursor is a cursor wrapper that lazy executes sql.
        `execute()` and `executemany()` calls will be captured into self.query, then run at `commit()`
        if self.query is empty, `commit()` will do nothing

        Args:
            table (Table):
        """
        self.table = table
        self.query = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return

    def execute(self, sql, param=None):
        self.query.append(('execute', sql, param))

    def executemany(self, sql, param=None):
        self.query.append(('executemany', sql, param))

    def executescript(self, sql):
        self.query.append(('executescript', sql, None))

    def create_table(self):
        self.query.append(('create_table', None, None))
        return True

    def rollback(self):
        self.query.clear()

    def fetchone(self):
        raise RuntimeError('You should not call fetchone() in LazyCursor')

    def fetchall(self):
        raise RuntimeError('You should not call fetchall() in LazyCursor')

    def commit(self):
        if not self.query:
            return

        with self.table.cursor() as cursor:
            for func, sql, param in self.query:
                if func == 'execute':
                    cursor.execute(sql, param)
                elif func == 'executemany':
                    cursor.executemany(sql, param)
                elif func == 'executescript':
                    cursor.executescript(sql)
                elif func == 'create_table':
                    cursor.create_table()
            cursor.commit()

        self.query.clear()


class Table(Generic[T_model]):
    # Tables should override these
    TABLE_NAME = ''
    # SQL to create the table
    # when executing any sql, table will be auto created
    # Example:
    #     CREATE TABLE "{TABLE_NAME}" (
    #         "id" INTEGER NOT NULL,
    #         "task" TEXT NOT NULL,
    #         "group" TEXT NOT NULL,
    #         "value" BLOB NOT NULL,
    #         PRIMARY KEY ("id"),
    #         UNIQUE ("task", "group")
    #     )
    # If CREATE_TABLE is f-string, CREATE_TABLE is a static SQL
    # If CREATE_TABLE is normal string, CREATE_TABLE will fill in {TABLE_NAME} dynamically,
    #   so you can operate multiple tables that have the same schema
    # Note that table must have "id" in INTEGER and as PRIMARY_KEY and AUTO_INCREMENT
    CREATE_TABLE = ''
    # msgspec model of the table row
    # You need to ensure MODEL matches the schema in CREATE_TABLE
    # Note that you should define like:
    #   MODEL = ConfigTable
    # instead of
    #   MODEL: ConfigTable
    MODEL: type[T_model]

    def __init__(self, file):
        """
        Args:
            file (str): Absolute filepath to database or ":memory:" for in-memory database
                Due to connection pool, in-memory database is shared,
                meaning every ":memory:" connect returns the same db.
        """
        self.file = file

    def cursor(self, lazy=False):
        """
        Create a cursor to operate sqlite

        Args:
            lazy (bool): True to create a LazyCursor.
                LazyCursor is a cursor wrapper that lazy executes sql.
                `execute()` and `executemany()` calls will be captured into self.query, then run at `commit()`
                if self.query is empty, `commit()` will do nothing

        Returns:
            SqlitePoolCursor:
        """
        if lazy:
            return LazyCursor(self)

        cursor = SQLITE_POOL.cursor(self.file)
        # copy CREATE_TABLE to cursor, so it can auto create table if table not exists
        cursor.TABLE_NAME = self.TABLE_NAME
        cursor.CREATE_TABLE = self.CREATE_TABLE
        return cursor

    def exclusive_transaction(self):
        """
        Provides a cursor within a single EXCLUSIVE transaction.
        Commits on successful exit, rolls back on exception.

        Usage:
            with self.exclusive_transaction() as cursor:
                # IMPORTANT: reuse this cursor
                self.execute_one_or_many(..., _cursor_=c)
                self.execute_one_or_many(..., _cursor_=c)
        """
        transaction = SQLITE_POOL.exclusive_transaction(self.file)
        # copy CREATE_TABLE to cursor, so it can auto create table if table not exists
        transaction.cursor.TABLE_NAME = self.TABLE_NAME
        transaction.cursor.CREATE_TABLE = self.CREATE_TABLE
        return transaction

    def create_table(self):
        """
        Table is auto created, but you can still create it manually.

        Returns:
            bool: If created

        Raises:
            sqlite3.OperationalError
        """
        if not self.CREATE_TABLE:
            raise TableError(f'Table {self.__class__.__name__} has no CREATE_TABLE defined')
        with self.cursor() as c:
            return c.create_table()

    def drop_table(self):
        """
        Drop current table
        """
        if not self.TABLE_NAME:
            raise TableError(f'Table {self.__class__.__name__} has no TABLE_NAME defined')
        with self.cursor() as c:
            c.execute(f'DROP TABLE IF EXISTS "{self.TABLE_NAME}"')

    @staticmethod
    def sql_select_kwargs_to_condition(kwargs):
        """
        Convert **kwarg query to sql query condition.
        To avoid SQL injection, VALUES are variables that reference the key

        Returns:
            str: "task"=:task AND "group"=:group AND ...
        """
        conditions = [f'"{k}"=:{k}' for k in kwargs.keys()]
        conditions = ' AND '.join(conditions)
        return conditions

    @staticmethod
    def sql_expr_groupby(fields):
        """
        Args:
            fields (str | list[str] | tuple[str,...]):

        Returns:
            str: GROUP BY "field1","field2"
        """
        if isinstance(fields, str):
            sql = f'"{fields}"'
        else:
            sql = ','.join([f'"{k}"' for k in fields])
        return f' GROUP BY {sql}'

    @staticmethod
    def sql_expr_orderby(fields, asc=True):
        """
        Args:
            fields (str | list[str] | tuple[str,...]):
            asc (bool): True for ASC, False for DESC

        Returns:
            str: ORDER BY "field1","field2"
                ORDER BY "field1","field2" DESC
        """
        if isinstance(fields, str):
            sql = f'"{fields}"'
        else:
            sql = ','.join([f'"{k}"' for k in fields])
        if asc:
            return f' ORDER BY {sql}'
        else:
            return f' ORDER BY {sql} DESC'

    def sql_select_expr(self, sql='', _groupby_='', _orderby_='', _orderby_desc_='', _limit_=0, _offset_=0):
        """
        Args:
            sql (str): Prev SQL
            _groupby_ (str | list[str] | tuple[str,...]):
            _orderby_ (str | list[str] | tuple[str,...]):
            _orderby_desc_ (str | list[str] | tuple[str,...]):
            _limit_ (int):
            _offset_ (int):

        Returns:
            str: ` GROUP BY "field1","field2" ORDER BY "field1","field2" LIMIT 3 OFFSET 3`
        """
        if not sql:
            sql = f'SELECT "{self.TABLE_NAME}"'
        if _groupby_:
            sql += self.sql_expr_groupby(_groupby_)
        if _orderby_:
            sql += self.sql_expr_orderby(_orderby_)
        elif _orderby_desc_:
            sql += self.sql_expr_orderby(_orderby_desc_, asc=False)
        if _limit_ > 0:
            sql += f' LIMIT {_limit_}'
        if _offset_ > 0:
            sql += f' OFFSET {_offset_}'
        return sql

    def select(
            self,
            _cursor_=None,
            _groupby_='',
            _orderby_='',
            _orderby_desc_='',
            _limit_=0,
            _offset_=0,
            **kwargs
    ) -> list[T_model]:
        """
        Query table in a pythonic way
        Equivalent to:
            SELECT * FROM {table_name} WHERE key1=value1 AND ...

        Args:
            _cursor_ (SqlitePoolCursor | None): to reuse cursor
            _groupby_ (str | list[str] | tuple[str,...]):
            _orderby_ (str | list[str] | tuple[str,...]):
            _orderby_desc_ (str | list[str] | tuple[str,...]):
            _limit_ (int):
            _offset_ (int):
            **kwargs: Anything to query

        Examples:
            rows = table.select(task='Main')
        """
        # generate sql
        if kwargs:
            conditions = self.sql_select_kwargs_to_condition(kwargs)
            sql = f'SELECT * FROM "{self.TABLE_NAME}" WHERE {conditions}'
            sql = self.sql_select_expr(
                sql, _groupby_=_groupby_, _orderby_=_orderby_, _orderby_desc_=_orderby_desc_,
                _limit_=_limit_, _offset_=_offset_)
        else:
            sql = f'SELECT * FROM "{self.TABLE_NAME}"'
            sql = self.sql_select_expr(
                sql, _groupby_=_groupby_, _orderby_=_orderby_, _orderby_desc_=_orderby_desc_,
                _limit_=_limit_, _offset_=_offset_)

        # query
        if _cursor_ is None:
            with self.cursor() as c:
                c.execute(sql, kwargs)
                result = c.fetchall()
        else:
            _cursor_.execute(sql, kwargs)
            result = _cursor_.fetchall()

        # convert to msgspec model
        try:
            model = self.MODEL
        except AttributeError:
            raise TableError(f'Table {self.__class__.__name__} has no MODEL defined')
        result = [model(**row) for row in result]
        return result

    def select_one(
            self,
            _cursor_=None,
            _groupby_='',
            _orderby_='',
            _orderby_desc_='',
            _offset_=0,
            **kwargs
    ) -> T_model | None:
        """
        Query table in a pythonic way
        Return one row of data, or None if not found

        Equivalent to:
            SELECT * FROM {table_name} WHERE key1=value1 AND ... LIMIT 1

        Args:
            _cursor_ (SqlitePoolCursor | None): to reuse cursor
            _groupby_ (str | list[str] | tuple[str,...]):
            _orderby_ (str | list[str] | tuple[str,...]):
            _orderby_desc_ (str | list[str] | tuple[str,...]):
            _offset_ (int):
            **kwargs: Anything to query

        Examples:
            row = table.select_first(task='Main')
        """
        # generate sql
        if kwargs:
            conditions = self.sql_select_kwargs_to_condition(kwargs)
            sql = f'SELECT * FROM "{self.TABLE_NAME}" WHERE {conditions}'
            sql = self.sql_select_expr(
                sql, _groupby_=_groupby_, _orderby_=_orderby_, _orderby_desc_=_orderby_desc_,
                _limit_=1, _offset_=_offset_)
        else:
            sql = f'SELECT * FROM "{self.TABLE_NAME}"'
            sql = self.sql_select_expr(
                sql, _groupby_=_groupby_, _orderby_=_orderby_, _orderby_desc_=_orderby_desc_,
                _limit_=1, _offset_=_offset_)

        # query
        if _cursor_ is None:
            with self.cursor() as c:
                c.execute(sql, kwargs)
                result = c.fetchone()
        else:
            _cursor_.execute(sql, kwargs)
            result = _cursor_.fetchone()

        # convert to msgspec model
        if result is not None:
            try:
                model = self.MODEL
            except AttributeError:
                raise TableError(f'Table {self.__class__.__name__} has no MODEL defined')
            result = model(**result)
        return result

    def select_by_sql(self, sql, params=None, _cursor_=None) -> list[T_model]:
        """
        Query database by raw sql

        Args:
            sql (str):
            params (list[Any], tuple[Any], dict[str, Any]):
                sql parameters to avoid sql injection
            _cursor_ (SqlitePoolCursor | None): to reuse cursor
        """
        if _cursor_ is None:
            with self.cursor() as c:
                if params is None:
                    c.execute(sql)
                else:
                    c.execute(sql, params)
                result = c.fetchall()
        else:
            if params is None:
                _cursor_.execute(sql)
            else:
                _cursor_.execute(sql, params)
            result = _cursor_.fetchall()

        # convert to msgspec model
        try:
            model = self.MODEL
        except AttributeError:
            raise TableError(f'Table {self.__class__.__name__} has no MODEL defined')
        result = [model(**row) for row in result]
        return result

    def select_one_by_sql(self, sql, params=None, _cursor_=None) -> T_model | None:
        """
        Args:
            sql (str):
            params (list[Any], tuple[Any], dict[str, Any]):
                sql parameters to avoid sql injection
            _cursor_ (SqlitePoolCursor | None): to reuse cursor
        """
        if _cursor_ is None:
            with self.cursor() as c:
                if params is None:
                    c.execute(sql)
                else:
                    c.execute(sql, params)
                result = c.fetchone()
        else:
            if params is None:
                _cursor_.execute(sql)
            else:
                _cursor_.execute(sql, params)
            result = _cursor_.fetchone()

        # convert to msgspec model
        if result is not None:
            try:
                model = self.MODEL
            except AttributeError:
                raise TableError(f'Table {self.__class__.__name__} has no MODEL defined')
            result = model(**result)
        return result

    @cached_property
    def field_names(self):
        """
        Returns:
            list[str]: All field names of model
        """
        try:
            model = self.MODEL
        except AttributeError:
            raise TableError(f'Table {self.__class__.__name__} has no MODEL defined')
        return [field.name for field in msgspec.structs.fields(model)]

    @cached_property
    def sql_insert_columns_placeholders(self):
        """
        Generate sql column, so you can use them in
            INSERT INTO {table_name} ({columns}) VALUES ({placeholders})
        AUTO_INCREMENT field will be ignored.

        Returns:
            str: "task","group",...
        """
        fields = self.field_names
        # get non auto increment fields (id is implicitly auto increment)
        columns = [name for name in fields if name != 'id']
        # :task,:group,...
        placeholders = ','.join([f':{k}' for k in columns])
        # "task","group",...
        columns = ",".join([f'"{k}"' for k in columns])
        return columns, placeholders

    def insert_row(
            self,
            rows: T_model | list[T_model],
            _cursor_: SqlitePoolCursor | None = None,
    ):
        """
        Insert one row of data or a list of data, with auto commit

        You can also input an existing cursor to manage transaction yourself
        with table.cursor() as cursor:
            try:
                cursor.insert(row, _cursor_=cursor)
                cursor.insert([row2, row3], _cursor_=cursor)
                # don't forget to commit
                cursor.commit()
            except sqlite3.Error:
                cursor.rollback()
        """
        columns, placeholders = self.sql_insert_columns_placeholders
        sql = f'INSERT INTO {self.TABLE_NAME} ({columns}) VALUES ({placeholders})'
        self.execute_one_or_many(sql, rows, _cursor_=_cursor_)

    def execute_one_or_many(
            self,
            sql: str,
            rows: T_model | list[T_model],
            _cursor_: SqlitePoolCursor | None = None,
            drop_no_pk=False,
            drop_zero_pk=False,
    ):
        """
        Args:
            sql:
            rows:
            _cursor_:
            drop_no_pk: True to drop rows without PRIMARY_KEY
            drop_zero_pk: True to set row.id == 0 to None,
        """
        if isinstance(rows, list):
            if drop_no_pk:
                if drop_zero_pk:
                    rows = [row_drop_zero_pk(asdict(row)) for row in rows if row_has_pk(row)]
                else:
                    rows = [asdict(row) for row in rows if row_has_pk(row)]
            else:
                if drop_zero_pk:
                    rows = [row_drop_zero_pk(asdict(row)) for row in rows]
                else:
                    rows = [asdict(row) for row in rows]
            if not rows:
                return
            # execute
            if _cursor_ is None:
                with self.cursor() as c:
                    try:
                        c.executemany(sql, rows)
                        c.commit()
                    except sqlite3.Error:
                        c.rollback()
                        raise
            else:
                _cursor_.executemany(sql, rows)
        else:
            if not drop_no_pk:
                pass
            else:
                # filter rows with PRIMARY_KEY
                if not row_has_pk(rows):
                    return
            rows = asdict(rows)
            if drop_zero_pk:
                rows = row_drop_zero_pk(rows)
            # execute
            if _cursor_ is None:
                with self.cursor() as c:
                    try:
                        c.execute(sql, rows)
                        c.commit()
                    except sqlite3.Error:
                        c.rollback()
                        raise
            else:
                _cursor_.execute(sql, rows)

    def update_row(
            self,
            rows: T_model | list[T_model],
            updates: str | list[str] | tuple[str,...] = '',
            _cursor_: SqlitePoolCursor | None = None,
    ):
        """
        Update rows by PRIMARY_KEY.
        Rows with PRIMARY_KEY value <= 0 won't be updated.

        Args:
            rows:
            updates: fields to update,
                default to empty string meaning all fields except PRIMARY_KEY will be updated
            _cursor_:
        """
        # format updates
        if not updates:
            updates = [name for name in self.field_names if name != 'id']
        elif isinstance(updates, str):
            updates = [updates] if updates != 'id' else []
        else:
            updates = [name for name in updates if name != 'id']
        if not updates:
            # no update fields?
            raise TableError(f'Trying to do update_row() but no update fields, updates={updates}')

        # "task"=:task,"group"=:group,...
        set_clause = ','.join([f'"{field}"=:{field}' for field in updates])
        sql = f'UPDATE "{self.TABLE_NAME}" SET {set_clause} WHERE "id"=:id'

        self.execute_one_or_many(sql, rows, _cursor_=_cursor_, drop_no_pk=True)

    def upsert_row(
            self,
            rows: T_model | list[T_model],
            conflicts: str | list[str] | tuple[str,...] = '',
            updates: str | list[str] | tuple[str,...] = '',
            _cursor_: SqlitePoolCursor | None = None,
    ):
        """
        Upsert rows.

        Args:
            rows:
            conflicts: fields on conflict
                default to empty string meaning conflicts=PRIMARY_KEY
                If `conflicts` and `updates` have the same field, respect `conflicts` first
            updates: fields to update,
                default to empty string meaning all fields except PRIMARY_KEY will be updated

            _cursor_:
        """
        # format conflicts
        if not conflicts:
            conflicts = ['id']
        else:
            if isinstance(conflicts, str):
                conflicts = [conflicts]
            else:
                conflicts = list(conflicts)
        if not conflicts:
            # no conflict fields?
            raise TableError(f'Trying to do upsert_row() but no conflict fields, '
                                   f'conflicts={conflicts}, updates={updates}')

        # format updates
        if not updates:
            updates = [name for name in self.field_names if name != 'id' and name not in conflicts]
        elif isinstance(updates, str):
            if updates in conflicts:
                # update the conflicted field?
                raise TableError(f'Trying to do upsert_row() but updates==conflicts'
                                       f'conflicts={conflicts}, updates={updates}')
            updates = [updates] if updates != 'id' else []
        else:
            updates = [name for name in updates if name != 'id' and name not in conflicts]
        if not updates:
            # no update fields?
            raise TableError(f'Trying to do upsert_row() but no update fields, '
                                   f'conflicts={conflicts}, updates={updates}')

        # build sql
        # insert all columns including PRIMARY KEY but PK=None to have an auto increment PK
        fields = self.field_names
        columns = ",".join([f'"{k}"' for k in fields])
        placeholders = ','.join([f':{k}' for k in fields])
        # "task","group",...
        conflict_clause = ','.join([f'"{field}"' for field in conflicts])
        # "task"=excluded."task","group"=excluded."group",...
        update_clause = ','.join([f'"{field}"=excluded."{field}"' for field in updates])
        sql = f'INSERT INTO "{self.TABLE_NAME}" ({columns}) VALUES ({placeholders}) ' \
              f'ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_clause}'

        self.execute_one_or_many(sql, rows, _cursor_=_cursor_, drop_zero_pk=True)

    def delete(self, _cursor_: SqlitePoolCursor | None = None, **kwargs):
        """
        Delete in a pythonic way
        Equivalent to:
            DELETE FROM {table_name} WHERE key1=value1 AND ...

        Args:
            _cursor_ (SqlitePoolCursor | None): to reuse cursor
            **kwargs: Anything to query for deletion

        Examples:
            table.delete(task='Main')
            table.delete(task='Main', group='test')
        """
        if not kwargs:
            # delete without condition?
            raise TableError('Delete without conditions is not allowed for safety')

        conditions = self.sql_select_kwargs_to_condition(kwargs)
        sql = f'DELETE FROM "{self.TABLE_NAME}" WHERE {conditions}'

        if _cursor_ is None:
            with self.cursor() as c:
                c.execute(sql, kwargs)
                c.commit()
        else:
            _cursor_.execute(sql, kwargs)

    def delete_row(
            self,
            rows: T_model | list[T_model],
            _cursor_: SqlitePoolCursor | None = None,
    ):
        """
        Delete rows by PRIMARY_KEY.
        Rows with PRIMARY_KEY value <= 0 won't be deleted.
        """
        sql = f'DELETE FROM "{self.TABLE_NAME}" WHERE "id"=:id'

        self.execute_one_or_many(sql, rows, _cursor_=_cursor_, drop_no_pk=True)

    def execute_fetchone(self, sql, _cursor_: SqlitePoolCursor | None = None):
        """
        Args:
            sql (str):
            _cursor_:

        Returns:
            Any
        """
        if _cursor_ is None:
            with self.cursor() as c:
                c.execute(sql)
                result = c.fetchone()
        else:
            _cursor_.execute(sql)
            result = _cursor_.fetchone()
        return result

    def get_data_version(self, _cursor_: SqlitePoolCursor | None = None):
        """
        Returns:
            int:
        """
        return self.execute_fetchone('PRAGMA data_version;', _cursor_=_cursor_)[0]








