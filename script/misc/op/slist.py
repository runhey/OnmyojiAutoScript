from collections import defaultdict
from typing import Generic, Iterator, TypeVar

T = TypeVar('T')


class Slist(Generic[T]):
    def __init__(self, items: "list[T]"):
        """
        A proxy of list of items
        Can act like a simple in-memory database table
        """
        self.items: "list[T]" = items
        self.index: "dict[tuple, Slist[T]]" = {}

    def __iter__(self) -> "Iterator[T]":
        return iter(self.items)

    def __getitem__(self, item):
        if isinstance(item, int):
            # get item
            return self.items[item]
        else:
            # slice
            return Slist(self.items[item])

    def __contains__(self, item):
        return item in self.items

    def __str__(self):
        # show the same as list
        items = ', '.join([str(item) for item in self])
        return f'[{items}]'

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return len(self.items) > 0

    @property
    def count(self):
        """
        Returns:
            int:
        """
        return len(self.items)

    @staticmethod
    def _match_item(item, kwargs):
        """
        Check if an item matches `kwargs`
        """
        for k, v in kwargs.items():
            item_v = getattr(item, k)
            if item_v != v:
                return False
        return True

    def select(self, **kwargs) -> "Slist[T]":
        """
        Select items that have given attribute

        Examples:
            devices = Slist([
                Device(serial='127.0.0.1:5555'),
                Device(serial='127.0.0.1:16384'),
            ])
            device = devices.select(serial='127.0.0.1:5555')
        """
        match = self._match_item
        return Slist([grid for grid in self.items if match(grid, kwargs)])

    def index_create(self, *attrs):
        """
        Create index on given attrs
        note that you can only have one index
        """
        index = defaultdict(list)
        for item in self.items:
            key = tuple(getattr(item, attr) for attr in attrs)
            index[key].append(item)

        index = {k: Slist(v) for k, v in index.items()}
        self.index = index

    def index_select(self, *values) -> "Slist[T]":
        """
        Select items that have given attribute by index
        `index_create()` needs to be called before index_select()
        If you have tons of `select()` calls, create index then select index will be faster

        Examples:
            waypoints = Slist(...)
            waypoints.index_create('domain', 'route')
            route = waypoints.index_select('Combat', 'Herta_StorageZone_F1_X252Y84')
        """
        try:
            return self.index[values]
        except KeyError:
            return Slist([])

    def filter(self, func) -> "Slist[T]":
        """
        Filter items by a function.

        Args:
            func (callable): Function that receives an item as argument, and returns a bool.
        """
        return Slist([item for item in self.items if func(item)])

    def set(self, **kwargs):
        """
        Set attribute to each item.

        Args:
            **kwargs:
        """
        for item in self.items:
            for key, value in kwargs.items():
                setattr(item, key, value)

    def get(self, attr):
        """
        Get an attribute from each item.

        Args:
            attr (str): Attribute name.

        Returns:
            list[Any]:
        """
        return [getattr(item, attr) for item in self.items]

    def call(self, func, **kwargs):
        """
        Call a function in reach item, and get results.

        Args:
            func (str): Function name to call.
            **kwargs:

        Returns:
            list:
        """
        return [getattr(item, func)(**kwargs) for item in self.items]

    def first_or_none(self) -> "T | None":
        """
        Get first item or None
        """
        try:
            return self.items[0]
        except IndexError:
            return None

    def add(self, items: "Slist[T] | list[T] | T") -> "Slist[T]":
        """
        Add item or a list of items
        """
        if isinstance(items, Slist):
            items = self.items + items.items
            return Slist(items)
        if isinstance(items, list):
            items = self.items + items
            return Slist(items)
        else:
            items = self.items + [items]
            return Slist(items)

    def remove(self, items: "Slist[T] | list[T] | T") -> "Slist[T]":
        """
        Remove item or a list of items
        """
        if isinstance(items, Slist):
            items = [item for item in self.items if item not in items.items]
            return Slist(items)
        if isinstance(items, list):
            items = [item for item in self.items if item not in items]
            return Slist(items)
        else:
            items = [item for item in self.items if item != items]
            return Slist(items)

    def sort(self, *attrs) -> "Slist[T]":
        """
        Args:
            *attrs (str): Attribute name to sort.
        """
        if not self.items:
            return self
        if len(attrs):
            def item_key(item):
                return tuple(getattr(item, attr) for attr in attrs)

            items = sorted(self.items, key=item_key)
            return Slist(items)
        else:
            return self
