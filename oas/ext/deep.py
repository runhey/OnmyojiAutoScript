from collections import deque

# deep_* functions are used for access nested dictionary.
# They target for high performance so code are complicated to read
# In general performance practise, time costs are as below:
# - When key exists
#   try: dict[key] except KeyError << dict.get(key) < if key in dict: dict[key]
# - When not key exists
#   if key in dict: dict[key] < dict.get(key) <<< try: dict[key] except KeyError

OP_ADD = 'add'
OP_SET = 'set'
OP_DEL = 'del'


def deep_get(d, keys, default=None):
    """
    Get value from nested dict and list

    To get from a list, keys must contain int index, must not be keys='item.0' where index is '0' in str

    Args:
        d (dict | list):
        keys (str | list | tuple | deque): Such as ['Scheduler', 'NextRun', 'value']
        default: Default return if key not found.

    Returns:
        Value on given keys
    """
    # 240 + 30 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return d
    # No such key
    except KeyError:
        return default
    # No such key
    except IndexError:
        return default
    # Input `keys` is not iterable or input `d` is not dict
    # list indices must be integers or slices, not str
    except TypeError:
        return default


def deep_get_with_error(d, keys):
    """
    Get value from nested dict and list, raise KeyError if key not exists

    Args:
        d (dict | list):
        keys (str | list | tuple | deque): Such as ['Scheduler', 'NextRun', 'value']

    Returns:
        Value on given keys

    Raises:
        KeyError: If key not exists
    """
    # 240 + 30 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return d
    # No such key
    # except KeyError:
    #     raise
    # No such key
    except IndexError:
        raise KeyError
    # Input `keys` is not iterable or input `d` is not dict
    # list indices must be integers or slices, not str
    except TypeError:
        raise KeyError


def deep_exist(d, keys):
    """
    Check if keys exists in nested dict or list

    Args:
        d (dict | list):
        keys (str | list | tuple | deque): Such as `Scheduler.NextRun.value`

    Returns:
        bool: If key exists
    """
    # 240 + 30 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return True
    # No such key
    except KeyError:
        return False
    # No such key
    except IndexError:
        return False
    # Input `keys` is not iterable or input `d` is not dict
    # list indices must be integers or slices, not str
    except TypeError:
        return False


def deep_set(d, keys, value):
    """
    Set value into nested dict safely, imitating deep_get().
    Write operations assume dict only: a list met on the key path is treated
    as a dict and replaced, so never write into a list.

    Note that always use:
        # This guarantee d is dict and deep_set() success
        d = deep_set(d, keys, value)
    don't use:
        deep_set(d, keys, value)

    Args:
        d (dict | list):
        keys (str | list | tuple | deque)
        value:

    Returns:
        dict:
    """
    # 150 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    raw_d = d
    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                # if key in dict: dict[key] > dict.get > dict.setdefault > try dict[key] except
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:
                # `d` is not dict
                exist = False
                d = {}
                try:
                    prev_d[prev_k2] = {prev_k: d}
                except TypeError:
                    try:
                        # `prev_d` is not dict, usually because `raw_d` is not dict
                        prev_d = {prev_k: d}
                        raw_d = prev_d
                    except TypeError:
                        # `prev_k` is not hashable, cannot build a dict
                        if type(raw_d) is dict:
                            return raw_d
                        return {}

            prev_k2 = prev_k
            prev_k = k

    # Input `keys` is not iterable, treat as empty list
    except TypeError:
        pass
    # Input `keys` is empty list
    if first:
        # `raw_d` is dict
        if type(raw_d) is dict:
            return raw_d
        # `raw_d` is not dict, return a dict
        return {}

    # Last key, set value
    try:
        d[prev_k] = value
        return raw_d
    # Last value `d` is not dict
    except TypeError:
        try:
            prev_d[prev_k2] = {prev_k: value}
            return raw_d
        except TypeError:
            try:
                # `prev_d` is not dict, usually because `raw_d` is not dict
                return {prev_k: value}
            except TypeError:
                # `prev_k` is not hashable, cannot build a dict
                if type(raw_d) is dict:
                    return raw_d
                return {}


def _truncate_repr(obj, max_length=200):
    """
    Return the repr of `obj`, cut to `max_length` characters with a trailing
    '...' if it is too long. Used to keep error messages readable when a huge
    value is met.

    Args:
        obj: Object to repr
        max_length (int): Max length of the repr before cutting. Defaults to 200

    Returns:
        str: repr of `obj`, or its first `max_length` characters plus '...'
    """
    text = repr(obj)
    if len(text) > max_length:
        text = f'{text[:max_length]}...'
    return text


def deep_set_no_replace(d, keys, value):
    """
    Set value into nested dict safely, imitating deep_set().
    Missing levels are created as dicts, but unlike deep_set() a level that is
    not a dict is never replaced with a dict: the write is attempted eagerly
    and a TypeError telling the key and the value at it is raised instead.
    Write operations are duck typed, a level stays usable as long as it
    supports the key path: a list indexed by int works like deep_get(), a list
    indexed by the str key of a 'a.0.b' key path raises TypeError.
    Only the value at the last key is overwritten and the root is never
    rebuilt, so the return value is always the same object as `d`.
    Note that `d` is partially modified if an error is raised, levels before
    the error have been created.

    Args:
        d (dict):
        keys (str | list | tuple | deque): Such as ['Scheduler', 'NextRun', 'value']
        value:

    Returns:
        dict: The same object as `d`, modified in place

    Raises:
        TypeError: If a level on the key path does not support the write, the
            message tells which key is not a dict and the value at it, such as
            ``expected dict at key 'a', got int: 1``, a value longer than 200
            characters is truncated. The TypeError of python is chained as
            ``e.__cause__``. Also raised if `keys` is not iterable
        IndexError: If `keys` is empty, or a key is out of index of a list
    """
    # 140 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    raw_d = d
    first = True
    prev_k = None
    key_d = None
    try:
        for k in keys:
            if first:
                prev_k = k
                first = False
                continue
            try:
                # Missing key, create a sub dict and step into it
                sub = d[prev_k]
            except KeyError:
                sub = {}
                d[prev_k] = sub
            # `key_d` is the key whose value is `d`
            key_d = prev_k
            d = sub
            prev_k = k
        # keys is empty
        if first:
            raise IndexError('deep_set_no_replace() keys is empty')
        d[prev_k] = value
        return raw_d
    # `d` is not a dict on the key path, write ops assume dict only,
    # do not replace the level with a dict
    except TypeError as e:
        if first or type(d) is dict:
            # `keys` is not iterable, or `prev_k` is not hashable
            raise
        # A huge value is cut to keep the message readable
        value_repr = _truncate_repr(d)
        if key_d is None:
            # `d` is `raw_d`, the root is not a dict
            raise TypeError(
                f'deep_set_no_replace() expected dict, got {type(d).__name__}: {value_repr}') from e
        raise TypeError(
            f'deep_set_no_replace() expected dict at key {key_d!r}, got {type(d).__name__}: {value_repr}'
        ) from e
    # Input `keys` out of index
    except IndexError:
        raise


def deep_set_with_error(d, keys, value):
    """
    Set value into nested dict strictly, raise on any error. Unlike deep_set(),
    it does not create missing keys and does not repair non-dict intermediate
    levels: the whole key path must already exist as dicts, otherwise an error
    is raised. Similar to deep_pop() but writes instead of pops.

    Note that always use:
        # This guarantee d is dict and deep_set_with_error() success
        d = deep_set_with_error(d, keys, value)
    don't use:
        deep_set_with_error(d, keys, value)

    Args:
        d (dict | list):
        keys (str | list | tuple | deque)
        value:

    Returns:
        dict:

    Raises:
        KeyError: If a key on the path does not exist
        TypeError: If a non-dict is met on the key path, or `keys` is not
            iterable
        IndexError: If keys is empty
    """
    if type(keys) is str:
        keys = keys.split('.')

    raw_d = d
    first = True
    prev_k = None
    try:
        for k in keys:
            if first:
                prev_k = k
                first = False
                continue
            d = d[prev_k]
            prev_k = k
        # keys is empty
        if first:
            raise IndexError('deep_set_with_error() keys is empty')
        # Write ops assume dict only, do not set into list
        if type(d) is not dict:
            raise TypeError(
                f'deep_set_with_error() expected dict at key {prev_k!r}, got {type(d).__name__}')
        # The last key must already exist, like deep_pop()
        if prev_k not in d:
            raise KeyError(prev_k)
        d[prev_k] = value
        return raw_d
    # No such key
    except KeyError:
        raise
    # Input `keys` is not iterable or input `d` is not dict
    # list indices must be integers or slices, not str
    except TypeError:
        raise
    # Input `keys` out of index
    except IndexError:
        raise


def deep_default(d, keys, value):
    """
    Set value into nested dict safely, imitating deep_get().
    Write operations assume dict only: a list met on the key path is treated
    as a dict and replaced, so never write into a list.

    Note that always use:
        # This guarantee d is dict and deep_default() success
        d = deep_default(d, keys, value)
    don't use:
        deep_default(d, keys, value)

    Args:
        d (dict | list):
        keys (str | list | tuple | deque)
        value:

    Returns:
        dict:
    """
    # 150 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    raw_d = d
    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                # if key in dict: dict[key] > dict.get > dict.setdefault > try dict[key] except
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:
                # `d` is not dict
                exist = False
                d = {}
                try:
                    prev_d[prev_k2] = {prev_k: d}
                except TypeError:
                    try:
                        # `prev_d` is not dict, usually because `raw_d` is not dict
                        prev_d = {prev_k: d}
                        raw_d = prev_d
                    except TypeError:
                        # `prev_k` is not hashable, cannot build a dict
                        if type(raw_d) is dict:
                            return raw_d
                        return {}

            prev_k2 = prev_k
            prev_k = k

    # Input `keys` is not iterable, treat as empty list
    except TypeError:
        pass
    # Input `keys` is empty list
    if first:
        # `raw_d` is dict
        if type(raw_d) is dict:
            return raw_d
        # `raw_d` is not dict, return a dict
        return {}

    # Last key, set value
    try:
        d.setdefault(prev_k, value)
        return raw_d
    # Last value `d` is not dict, or `prev_k` is not hashable
    except (AttributeError, TypeError):
        try:
            prev_d[prev_k2] = {prev_k: value}
            return raw_d
        except TypeError:
            try:
                # `prev_d` is not dict, usually because `raw_d` is not dict
                return {prev_k: value}
            except TypeError:
                # `prev_k` is not hashable, cannot build a dict
                if type(raw_d) is dict:
                    return raw_d
                return {}


def deep_pop(d, keys, default=None):
    """
    Pop value from nested dict
    Write operations assume dict only: popping from a list returns default
    without modifying the list.

    Args:
        d (dict | list):
        keys (str | list | tuple | deque)
        default:
    """
    if type(keys) is str:
        keys = keys.split('.')

    try:
        first = True
        prev_k = None
        for k in keys:
            if first:
                prev_k = k
                first = False
                continue
            d = d[prev_k]
            prev_k = k
        # keys is empty, keys[-1] would raise IndexError
        if first:
            return default
        # Write ops are dict only, do not pop from list
        if type(d) is not dict:
            return default
        return d.pop(prev_k)
    # No such key
    except KeyError:
        return default
    # Input `keys` is not iterable or input `d` is not dict
    # list indices must be integers or slices, not str
    except TypeError:
        return default
    # Input `keys` out of index
    except IndexError:
        return default
    # Last `d` is not dict
    except AttributeError:
        return default


def dict_update(d, new):
    """
    Safely do dict.update()

    Args:
        d (dict):
        new (dict):

    Returns:

    """
    try:
        d.update(new)
        return d
    except AttributeError:
        # AttributeError: 'NoneType' object has no attribute 'update'
        return new
    except TypeError:
        # `new` is not dict
        if type(new) is dict:
            return new
        return d


def dict_copy(d):
    """
    Safely do dict.copy(), return {} if `d` is not a dict
    Shallow copy only: nested dicts and lists are shared with the source

    Args:
        d (dict): Dict to copy

    Returns:
        dict: Shallow copy of `d`, or {} if `d` is not a dict
    """
    # Use exact type check, do not call copy() on dict subclasses or other
    # objects that happen to implement a copy() method (list, set, ...)
    if type(d) is not dict:
        return {}
    return d.copy()


def deep_iter_depth1(data):
    """
    Equivalent to data.items() but suppress error if data is not a dict

    Args:
        data:

    Yields:
        tuple[Any, Any]: key, value
    """
    try:
        yield from data.items()
    except AttributeError:
        # `data` is not dict
        return


def deep_keys_depth1(data):
    """
    Equivalent to data.keys() but suppress error if data is not a dict

    Args:
        data:

    Yields:
        Any:
    """
    try:
        yield from data.keys()
    except AttributeError:
        # `data` is not dict
        return


def deep_values_depth1(data):
    """
    Equivalent to data.values() but suppress error if data is not a dict

    Args:
        data:

    Yields:
        Any:
    """
    try:
        yield from data.values()
    except AttributeError:
        # `data` is not dict
        return


def deep_iter_depth2(data):
    """
    Iter key and value in nested dict of depth 2
    A simplified deep_iter

    Args:
        data:

    Yields:
        tuple[Any, Any, Any]: key1, key2, value
    """
    try:
        for k1, v1 in data.items():
            try:
                for k2, v2 in v1.items():
                    yield k1, k2, v2
            except AttributeError:
                # `v1` is not dict
                continue
    except AttributeError:
        # `data` is not dict
        return


def deep_keys_depth2(data):
    """
    Iter key in nested dict of depth 2
    A simplified deep_iter

    Args:
        data:

    Yields:
        Any:
    """
    try:
        for k1, v1 in data.items():
            try:
                for k2 in v1.keys():
                    yield k1, k2
            except AttributeError:
                # `v1` is not dict
                continue
    except AttributeError:
        # `data` is not dict
        return


def deep_values_depth2(data):
    """
    Iter value in nested dict of depth 2
    A simplified deep_iter

    Args:
        data:

    Yields:
        Any:
    """
    try:
        for v1 in data.values():
            try:
                yield from v1.values()
            except AttributeError:
                # `v1` is not dict
                continue
    except AttributeError:
        # `data` is not dict
        return


def deep_iter(data, min_depth=None, depth=None, max_recursion=1000):
    """
    Iter key and value in nested dict
    300us on alas.json depth=3 (530+ rows)
    Can only iter dict
    Note that a circular reference raises RecursionError when there is no depth
    limit, pass a bigger `max_recursion` to iterate a legit deep dict

    Args:
        data:
        min_depth: Minimal depth of the keys to yield, defaults to `depth`,
            only the deepest level is yielded then. Defaults to 1 if `depth`
            is None, so values of all depths are yielded
        depth: Max depth to iterate, None means unlimited
        max_recursion: Max depth of an unlimited iteration, defaults to 1000,
            the default recursion limit of python. Deeper data raises
            RecursionError, pass a bigger value to iterate a legit deep dict

    Yields:
        tuple[tuple[Any, ...], Any]: tuple[key], value
    """
    if min_depth is None:
        min_depth = 1 if depth is None else depth
    assert min_depth >= 1
    assert depth is None or min_depth <= depth

    # Equivalent to dict.items()
    try:
        if depth == 1:
            for k, v in data.items():
                yield (k,), v
            return
        # Iter first depth
        elif min_depth == 1:
            q = deque()
            for k, v in data.items():
                key = (k,)
                if type(v) is dict:
                    q.append((key, v))
                else:
                    yield key, v
        # Iter target depth only
        else:
            q = deque()
            for k, v in data.items():
                key = (k,)
                if type(v) is dict:
                    q.append((key, v))
    except AttributeError:
        # `data` is not dict
        return

    # Iter depths
    current = 2
    while q:
        new_q = deque()
        # max depth
        if current == depth:
            for key, data in q:
                for k, v in data.items():
                    yield key + (k,), v
        # in target depth, or unlimited depth
        elif depth is None or min_depth <= current < depth:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + (k,)
                    if type(v) is dict:
                        new_q.append((subkey, v))
                    else:
                        yield subkey, v
        # Haven't reached min depth
        else:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + (k,)
                    if type(v) is dict:
                        new_q.append((subkey, v))
        q = new_q
        current += 1
        # `q` is not empty means there is still a level to iterate
        if depth is None and current > max_recursion and q:
            raise RecursionError(
                f'deep_iter() iterated deeper than max_recursion={max_recursion}, maybe a circular reference')


def deep_keys(data, min_depth=None, depth=None, max_recursion=1000):
    """
    Iter key in nested dict
    Can only iter dict
    Note that a circular reference raises RecursionError when there is no depth
    limit, pass a bigger `max_recursion` to iterate a legit deep dict

    Args:
        data:
        min_depth: Minimal depth of the keys to yield, defaults to `depth`,
            only the deepest level is yielded then. Defaults to 1 if `depth`
            is None, so keys of all depths are yielded
        depth: Max depth to iterate, None means unlimited
        max_recursion: Max depth of an unlimited iteration, defaults to 1000,
            the default recursion limit of python. Deeper data raises
            RecursionError, pass a bigger value to iterate a legit deep dict

    Yields:
        tuple[Any, ...]: tuple[key]
    """
    if min_depth is None:
        min_depth = 1 if depth is None else depth
    assert min_depth >= 1
    assert depth is None or min_depth <= depth

    # Equivalent to dict.items()
    try:
        if depth == 1:
            for k, v in data.items():
                yield (k,)
            return
        # Iter first depth
        elif min_depth == 1:
            q = deque()
            for k, v in data.items():
                key = (k,)
                if type(v) is dict:
                    q.append((key, v))
                else:
                    yield key
        # Iter target depth only
        else:
            q = deque()
            for k, v in data.items():
                key = (k,)
                if type(v) is dict:
                    q.append((key, v))
    except AttributeError:
        # `data` is not dict
        return

    # Iter depths
    current = 2
    while q:
        new_q = deque()
        # max depth
        if current == depth:
            for key, data in q:
                for k in data.keys():
                    yield key + (k,)
        # in target depth, or unlimited depth
        elif depth is None or min_depth <= current < depth:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + (k,)
                    if type(v) is dict:
                        new_q.append((subkey, v))
                    else:
                        yield subkey
        # Haven't reached min depth
        else:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + (k,)
                    if type(v) is dict:
                        new_q.append((subkey, v))
        q = new_q
        current += 1
        # `q` is not empty means there is still a level to iterate
        if depth is None and current > max_recursion and q:
            raise RecursionError(
                f'deep_keys() iterated deeper than max_recursion={max_recursion}, maybe a circular reference')


def deep_values(data, min_depth=None, depth=None, max_recursion=1000):
    """
    Iter value in nested dict
    Can only iter dict
    Note that a circular reference raises RecursionError when there is no depth
    limit, pass a bigger `max_recursion` to iterate a legit deep dict

    Args:
        data:
        min_depth: Minimal depth of the values to yield, defaults to `depth`,
            only the deepest level is yielded then. Defaults to 1 if `depth`
            is None, so values of all depths are yielded
        depth: Max depth to iterate, None means unlimited
        max_recursion: Max depth of an unlimited iteration, defaults to 1000,
            the default recursion limit of python. Deeper data raises
            RecursionError, pass a bigger value to iterate a legit deep dict

    Yields:
        Any: Value
    """
    if min_depth is None:
        min_depth = 1 if depth is None else depth
    assert min_depth >= 1
    assert depth is None or min_depth <= depth

    # Equivalent to dict.items()
    try:
        if depth == 1:
            for v in data.values():
                yield v
            return
        # Iter first depth
        elif min_depth == 1:
            q = deque()
            for v in data.values():
                if type(v) is dict:
                    q.append(v)
                else:
                    yield v
        # Iter target depth only
        else:
            q = deque()
            for v in data.values():
                if type(v) is dict:
                    q.append(v)
    except AttributeError:
        # `data` is not dict
        return

    # Iter depths
    current = 2
    while q:
        new_q = deque()
        # max depth
        if current == depth:
            for data in q:
                for v in data.values():
                    yield v
        # in target depth, or unlimited depth
        elif depth is None or min_depth <= current < depth:
            for data in q:
                for v in data.values():
                    if type(v) is dict:
                        new_q.append(v)
                    else:
                        yield v
        # Haven't reached min depth
        else:
            for data in q:
                for v in data.values():
                    if type(v) is dict:
                        new_q.append(v)
        q = new_q
        current += 1
        # `q` is not empty means there is still a level to iterate
        if depth is None and current > max_recursion and q:
            raise RecursionError(
                f'deep_values() iterated deeper than max_recursion={max_recursion}, maybe a circular reference')


def deep_iter_diff(before, after):
    """
    Iter diff between 2 dict.
    Pretty fast to compare 2 deeply nested dict,
    time cost increases with the number of differences.

    Args:
        before:
        after:

    Yields:
        tuple[str, ...]: Key path
        Any: Value in before, or None if not exists
        Any: Value in after, or None if not exists
    """
    try:
        if before == after:
            return
    except RecursionError:
        # Circular reference or too deep to compare: fall through to diff
        pass
    if type(before) is not dict or type(after) is not dict:
        yield (), before, after
        return

    # Guard against circular references
    visited = set()
    queue = deque([((), before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            pair = (id(d1), id(d2))
            if pair in visited:
                # Circular reference: already compared, skip to avoid infinite loop
                continue
            visited.add(pair)
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    # Safe to access d1[key], because key came from the union of both
                    # If it's not in d2 then it's in d1
                    yield path + (key,), d1[key], None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield path + (key,), None, val2
                    continue
                # Compare dict first, which is pretty fast
                try:
                    diff = val1 != val2
                except RecursionError:
                    # Too deep to compare, treat as different
                    diff = True
                if diff:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + (key,), val1, val2))
                    else:
                        yield path + (key,), val1, val2
        queue = new_queue
        if not queue:
            break


def deep_iter_patch(before, after):
    """
    Iter patch event from before to after, like creating a json-patch
    Pretty fast to compare 2 deeply nested dict,
    time cost increases with the number of differences.

    Args:
        before:
        after:

    Yields:
        str: OP_ADD, OP_SET, OP_DEL
        tuple[str, ...]: Key path
        Any: Value in after,
            or None of event is OP_DEL
    """
    try:
        if before == after:
            return
    except RecursionError:
        # Circular reference or too deep to compare: fall through to patch
        pass
    if type(before) is not dict or type(after) is not dict:
        yield OP_SET, (), after
        return

    # Guard against circular references
    visited = set()
    queue = deque([((), before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            pair = (id(d1), id(d2))
            if pair in visited:
                # Circular reference: already compared, skip to avoid infinite loop
                continue
            visited.add(pair)
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    yield OP_DEL, path + (key,), None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield OP_ADD, path + (key,), val2
                    continue
                # Compare dict first, which is pretty fast
                try:
                    diff = val1 != val2
                except RecursionError:
                    # Too deep to compare, treat as different
                    diff = True
                if diff:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + (key,), val1, val2))
                    else:
                        yield OP_SET, path + (key,), val2
        queue = new_queue
        if not queue:
            break
