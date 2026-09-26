from collections import deque

TYPE_LIST_LIKE = (list, tuple, set, deque, frozenset)
TYPE_NOT_ITERABLE = (str, bytes, int, float, dict)


def _iter_item(item):
    """
    Recursively yield individual items from a potentially nested iterable.

    Strings, bytes, and dicts are treated as atomic values (not flatten).
    Other iterables (list, tuple, set, frozenset, generator, range, etc.) are recursively flattened.
    Non-iterable items are yielded as-is.

    Args:
        item: The item to iterate over.

    Yields:
        Individual atomic items from nested structures.
    """
    if isinstance(item, TYPE_LIST_LIKE):
        for sub in item:
            yield from _iter_item(sub)
    elif isinstance(item, TYPE_NOT_ITERABLE):
        yield item
    else:
        try:
            for sub in item:
                yield from _iter_item(sub)
        except TypeError:
            yield item


def listify(item):
    """
    Flatten a potentially nested structure into a flat list.

    This function recursively flattens all nested iterables (list, tuple,
    set, generator, etc.) while treating strings, bytes, and dicts as
    atomic values.

    Examples:
        >>> listify(1)
        [1]
        >>> listify([1, [2, 3], [[4]]])
        [1, 2, 3, 4]
        >>> listify('hello')
        ['hello']
        >>> listify({'a': 1})
        [{'a': 1}]
        >>> listify(None)
        [None]
        >>> listify([1, 'abc', [2, 3]])
        [1, 'abc', 2, 3]

    Args:
        item: The item to flatten.

    Returns:
        list: A flat list of atomic items.
    """
    if isinstance(item, TYPE_LIST_LIKE):
        return list(_iter_item(item))
    if isinstance(item, TYPE_NOT_ITERABLE):
        return [item]
    # iter it anyway
    try:
        return list(_iter_item(item))
    except TypeError:
        return [item]
