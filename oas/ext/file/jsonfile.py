from collections import deque
from json import JSONDecodeError, JSONEncoder, dumps, loads

from oas.ext.path.atomic import atomic_read_bytes, atomic_write


def json_loads(data):
    """
    Args:
        data (bytes):

    Returns:
        Any:
    """
    return loads(data)


def json_dumps(obj):
    """
    Dump anything to json in bytes.

    Args:
        obj (Any):

    Returns:
        bytes:
    """
    data = dumps(obj, indent=2, ensure_ascii=False, sort_keys=False, default=str)
    data = data.encode('utf-8')
    return data


class ValueProxy:
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(f'{self.__class__.__name__}({self.value})')

    def __bool__(self):
        return bool(self.value)

    def __getitem__(self, item):
        return self.value[item]

    def __setitem__(self, key, value):
        self.value[key] = value

    def __delitem__(self, key):
        del self.value[key]

    def __eq__(self, other):
        return self.value == other

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __contains__(self, item):
        return item in self.value

    def items(self):
        return self.value.items()

    def keys(self):
        return self.value.keys()

    def values(self):
        return self.value.values()

    def get(self, key, default=None):
        return self.value.get(key, default)


class NoIndent(ValueProxy):
    """
    Wrapper class to mark value as no indent
    """

    def __str__(self):
        # A magic unique placeholder, note that "τ" is U+03C4
        return f'No|1NdEnτ-{id(self)}'


class NoIndentNoSpace(ValueProxy):
    """
    Wrapper class to mark value as no indent and no space
    """

    def __str__(self):
        # A magic unique placeholder, note that "τ" is U+03C4, "æ" is ae
        return f'No|1NdEnτ-n0SpaCæ-{id(self)}'


class CustomIndentEncoder(JSONEncoder):
    """
    A custom json encoder to handle NoIndent objects.
    We encode NoIndent objects to placeholders in json first,
    then replace placeholders with the actual inline content.
    """

    def __init__(self, *args, **kwargs):
        self.raw_kwargs = kwargs.copy()
        # Store "default", if "default" is given to JSONEncoder our default() won't be called
        self.default_func = kwargs.pop('default', None)
        super().__init__(*args, **kwargs)
        self.to_replace = deque()

    def default(self, obj):
        # Override default to encode NoIndent as placeholder
        typ = type(obj)
        if typ is NoIndent or typ is NoIndentNoSpace:
            placeholder = str(obj)
            self.to_replace.append((placeholder, obj))
            return placeholder

        # fallback to default
        func = self.default_func
        if func is None:
            return super().default(obj)
        else:
            return func(obj)

    def encode(self, o):
        o = super().encode(o)

        to_replace = self.to_replace
        noindent = self.raw_kwargs
        # kwargs for NoIndent
        # Ignore "indent", because this is a CustomIndentEncoder
        noindent.pop('indent', None)
        noindent.pop('separators', None)
        # kwargs for NoIndentNoSpace
        noindent_nospace = noindent.copy()
        noindent_nospace['separators'] = (',', ':')
        # Dump content with CustomIndentEncoder to handle nested NoIndent
        cls = self.__class__

        # Replace placeholder with the actual inline content
        for placeholder, obj in to_replace:
            # placeholder is a string, it will be quoted in json output
            placeholder = f'"{placeholder}"'
            objtype = type(obj)
            if objtype is NoIndent:
                value = dumps(obj.value, cls=cls, **noindent)
            elif objtype is NoIndentNoSpace:
                value = dumps(obj.value, cls=cls, **noindent_nospace)
            else:
                # this shouldn't happen
                continue
            o = o.replace(placeholder, value)

        return o


def json_dumps_custom_indent(obj):
    """
    Dump anything to json in bytes.
    You can mark objects with NoIndent, NoIndentNoSpace

    Args:
        obj (Any):

    Returns:
        bytes:

    Examples:
        data = {
            'area': NoIndent([100, 100, 200, 200]),
            'color': NoIndentNoSpace([255, 255, 255]),
        }
        print(json_dumps_custom_indent(data))
        # b'{\n  "area": [100, 100, 200, 200],\n  "color": [255,255,255]\n}'
    """
    data = dumps(
        obj, cls=CustomIndentEncoder,
        indent=2, ensure_ascii=False, sort_keys=False, default=str)
    data = data.encode('utf-8')
    return data


def read_json(file, default_factory=dict):
    """
    Read json from file, return default when having error

    Args:
        file (str):
        default_factory (callable):

    Returns:
        Any:
    """
    try:
        data = atomic_read_bytes(file)
    except FileNotFoundError:
        return default_factory()
    try:
        return json_loads(data)
    except JSONDecodeError:
        return default_factory()


def write_json(file, obj, dumper=json_dumps, skip_same=False):
    """
    Encode obj to json and write into file

    Args:
        file (str):
        obj (Any):
        dumper (callable): Dumper function that receive any and return bytes.
        skip_same (bool):
            True to skip writing if existing content is the same as content to write.
            This would reduce disk write but add disk read.

    Returns:
        bool: if write
    """
    data = dumper(obj)
    if skip_same:
        try:
            old = atomic_read_bytes(file)
            if data == old:
                return False
        except FileNotFoundError:
            pass

    atomic_write(file, data)
    return True


def write_json_custom_indent(file, obj, skip_same=False):
    """
    Encode obj to json and write into file, with custom indent.
    You can mark objects with NoIndent, NoIndentNoSpace

    Args:
        file (str):
        obj (Any):
        skip_same (bool):
            True to skip writing if existing content is the same as content to write.
            This would reduce disk write but add disk read.

    Returns:
        bool: if write
    """
    return write_json(file, obj, dumper=json_dumps_custom_indent, skip_same=skip_same)
