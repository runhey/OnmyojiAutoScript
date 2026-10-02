"""
Poor yaml read/write module that preserves comments.

Unlike :mod:`oas.ext.file.yamlfile`, this module validates parsed yaml
with msgspec structs, and writes comments back into the yaml file.

Comments are defined on the validation model with msgspec annotations::

    class Config(msgspec.Struct):
        port: Annotated[int, Meta(extra={"help": "Port to listen on"})] = 8080

The yaml text is generated with pyyaml, then comment lines are inserted
above the line of each key that has help text. Keys are matched by their
full path in the yaml structure, so keys with the same name at different
depth won't be confused: ::

    # Port to listen on
    port: 8080

Nested structures and multiline strings are supported, pyyaml handles the
parsing and dumping.
"""

import re
from collections import deque
from typing import Generic, List, Type, TypeVar, Union

import msgspec
import yaml
from msgspec import NODEFAULT, Struct
from msgspec.msgpack import encode as msgpack_encode
from msgspec.structs import fields
from msgspecerror import ErrorInfo, get_class_annotation_dict, load_msgpack_with_default
from msgspecerror.parse_type import is_struct_type, origin_args

from oas.ext.cache import cached_property
from oas.ext.cache.msgspec_meta import get_field_metadata
from oas.ext.deep import deep_iter_diff, deep_set_with_error
from oas.ext.file.yamlfile import yaml_dumps, yaml_loads
from oas.ext.path.atomic import atomic_read_bytes, atomic_read_text, atomic_write

T_model = TypeVar('T_model', bound=Struct)


def _split_help(text):
    """
    Split help text into lines.
    Returns str if single line, list[str] if multiple lines.

    Args:
        text (str | list[str]):

    Returns:
        str | list[str]:
    """
    if not text:
        return ''
    rows = list(_split_help_iter(text))
    if not rows:
        return ''
    if len(rows) == 1:
        return rows[0]
    return rows


def _split_help_iter(text):
    t = type(text)
    if t is str:
        if '\n' in text:
            for row in text.splitlines():
                yield row.rstrip()
        else:
            yield text.rstrip()
    elif t is list:
        for row in text:
            yield from _split_help_iter(row)
    else:
        text = str(text)
        yield from _split_help_iter(text)


def build_help_map(model, prefix=()):
    """
    Build ``{path: help_text}`` mapping from model field annotations,
    path is a tuple of keys, e.g. ('port',), ('inner', 'port').
    Help text is parsed with ``_split_help``, multiline help becomes a list of lines.
    Nested struct fields are collected recursively

    Args:
        model (type): Subclass of msgspec.Struct
        prefix (tuple): Path prefix of the model, empty for the root model

    Returns:
        dict: {path: help_text}
    """
    out = {}
    metadata = get_field_metadata(model)
    annotations = get_class_annotation_dict(model)
    # Map python field name to encode name, as yaml keys are encode names
    encode_names = {f.name: f.encode_name for f in fields(model)}
    for name, hint in annotations.items():
        path = prefix + (encode_names.get(name, name),)
        meta = metadata.get(name)
        help_text = meta.extra.get('help') if meta else None
        if help_text:
            out[path] = _split_help(help_text)
        # Collect help texts of nested struct fields
        origin, args = origin_args(hint)
        if is_struct_type(origin):
            out.update(build_help_map(origin, prefix=path))
    return out


def iter_yaml_rows(text):
    """
    Iterate rows of yaml text, yield (key, row) for each line.

    key is the tuple path of the key line, e.g. ('port',), ('inner', 'port').
    Lines that are not key lines, such as block scalar content, comments
    and empty lines, have key None. row is the original line content.

    Args:
        text (str): yaml text

    Yields:
        tuple: (key, row)
    """
    regex_key = re.compile(r'^([^:]+):')
    regex_multiline_string = re.compile(r'^[|>][+-]?(?:\s+#.*)?$')

    # Stack of (indent, key) of parent mappings
    stack: "deque[tuple[int, str]]" = deque()
    # Indent of the current block scalar, None when not inside a block scalar
    block_indent = None
    for line in text.splitlines():
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not stripped:
            # Empty line, doesn't affect mapping path or block scalar
            yield None, line
            continue
        if block_indent is not None:
            if indent > block_indent:
                # Content line of block scalar
                yield None, line
                continue
            # Exited block scalar
            block_indent = None
        # Skip existing comments
        if stripped.startswith('#'):
            yield None, line
            continue
        result = regex_key.match(stripped)
        if not result:
            yield None, line
            continue
        key = result.group(1).strip()
        # Pop stack entries deeper than current indent
        while stack and indent <= stack[-1][0]:
            stack.pop()
        path = tuple([k for _, k in stack] + [key])
        stack.append((indent, key))
        # Check if this line starts a block scalar, e.g. 'desc: |-'
        rest = stripped[len(result.group(0)):].strip()
        if regex_multiline_string.match(rest):
            block_indent = indent
        yield path, line


def insert_comments_iter(rows, help_map):
    """
    Iterate (key, row) pairs, yield the comment lines of keys that have
    help text before the row

    Args:
        rows (Iterable): (key, row) pairs from ``iter_yaml_rows()``
        help_map (dict): {path: help_text}, path is a tuple of keys

    Yields:
        str: comment lines of keys with help text, and rows
    """
    for key, row in rows:
        if key and key in help_map:
            help_text = help_map[key]
            # _split_help returns a list of lines for multiline help, str for single line
            comments = [help_text] if isinstance(help_text, str) else help_text
            indent = row[:len(row) - len(row.lstrip())]
            for comment in comments:
                yield f'{indent}# {comment}'
        yield row


def insert_comments(text, help_map):
    """
    Insert comment lines above the line of each key that has help text,
    keys are matched by their full path in the yaml structure

    Args:
        text (str): yaml text
        help_map (dict): {path: help_text}, path is a tuple of keys
            e.g. ('port',), ('inner', 'port'). Comment is inserted above the line of the key

    Returns:
        str: yaml text with comments inserted
    """
    if not help_map:
        return text
    lines = list(insert_comments_iter(iter_yaml_rows(text), help_map))
    if lines:
        return '\n'.join(lines) + '\n'
    return text


class YamlConfig(Generic[T_model]):
    """
    Yaml config reader/writer with msgspec validation and comment preservation.

    Comments are defined on the validation model fields with
    ``Annotated[str, Meta(extra={"help": "xxx"})]``, and written into the
    yaml file above the line of the field key, matched by the full key path.

    Attributes:
        file (str): YAML file path
        model (type[T_model]): Subclass of msgspec.Struct
        data (T_model): Validated data, use ``self.data.attr`` to access fields
        errors (list[ErrorInfo | Exception]): Errors or exceptions of the last read or
            validate, empty if none. Exceptions are read failures such as
            FileNotFoundError, UnicodeDecodeError and yaml.YAMLError
        help_map (dict): {path: help_text} mapping of the model, path is a tuple of keys,
            cached as cached_property

    Args:
        file (str): YAML file path
        model (type[T_model]): Subclass of msgspec.Struct to validate config data.
            All fields must have default values, so the model can be default constructed
    """

    def __init__(self, file, model: Type[T_model]):
        self.file = file
        self.model: Type[T_model] = model
        self.errors: "List[Union[ErrorInfo, Exception]]" = []
        # Model must be a msgspec struct
        if not isinstance(model, type) or not issubclass(model, Struct):
            raise TypeError(f'Model must be a subclass of msgspec.Struct, got {model!r}')
        # Model must be default constructible, all fields need default values
        try:
            model()
        except Exception as e:
            raise ValueError(
                f'Model {model.__name__} must be default constructible, '
                f'all fields need default values: {e}'
            ) from e
        self.data: T_model = self.read()
        if self.errors:
            self.write()

    @cached_property
    def help_map(self):
        """
        {path: help_text} mapping of the model, path is a tuple of keys
        """
        return build_help_map(self.model)

    @staticmethod
    def _log_errors(errors):
        """
        Log each error or exception as a warning

        Args:
            errors (list[ErrorInfo | Exception]): Errors to log
        """
        for error in errors:
            print(f'Invalid deploy config value: {error}')

    def read(self) -> T_model:
        """
        Read yaml file and validate with model,
        fields that fail validation fall back to defaults.
        Read failures are recorded in self.errors and also fall back to defaults

        Returns:
            T_model: self.data
        """
        try:
            text = atomic_read_bytes(self.file)
        except (FileNotFoundError, UnicodeDecodeError) as e:
            # File not found or not utf-8 encoded, use defaults
            self.errors = [e]
            self.data = self.model()
            self._log_errors(self.errors)
            return self.data
        try:
            data = yaml_loads(text)
        except yaml.YAMLError as e:
            # Invalid yaml, use defaults
            self.errors = [e]
            self.data = self.model()
            self._log_errors(self.errors)
            return self.data
        if data is None:
            # Empty content or only comments, use defaults
            data = {}
        obj, errors = load_msgpack_with_default(msgpack_encode(data), self.model)
        if obj is NODEFAULT:
            # Shouldn't happen, model is checked default constructible in __init__
            obj = self.model()
        self.errors = errors
        if errors:
            self._log_errors(errors)
        self.data = obj
        return self.data

    def validate(self):
        """
        Validate current self.data with the model, reusing the same loading
        logic as read(), fields that fail validation fall back to defaults

        Returns:
            bool: True if self.data is valid, False if errors were found
        """
        obj, errors = load_msgpack_with_default(msgpack_encode(self.data), self.model)
        if obj is NODEFAULT:
            # Shouldn't happen, model is checked default constructible in __init__
            obj = self.model()
        self.data = obj
        self.errors = errors
        if errors:
            self._log_errors(errors)
            return False
        return True

    def set(self, key, value):
        """
        Set value at the key path of data with model validation.

        The current data is converted to a builtin dict with
        ``msgspec.to_builtins``, value is set at the key path with
        ``deep_set_with_error``, then the dict is validated back into the
        model with ``msgspec.convert``. On success self.data is replaced with
        the validated model and True is returned, on failure the exception is
        recorded in self.errors and logged, and self.data is left unchanged.

        Args:
            key (tuple[str]): Key path in the yaml structure, keys are encode
                names of model fields, e.g. ('port',), ('inner', 'port')
            value: Value to set at the key path, must be valid for the type
                of the field at the path

        Returns:
            bool: True if the value was set, False if the key path doesn't
                exist or validation failed
        """
        if not key:
            error = ValueError(f'Key path must not be empty, got {key!r}')
            self.errors = [error]
            self._log_errors(self.errors)
            return False
        data = msgspec.to_builtins(self.data)
        try:
            deep_set_with_error(data, key, value)
        except (KeyError, TypeError, IndexError):
            error = KeyError(f'Key path {key!r} does not exist in data')
            self.errors = [error]
            self._log_errors(self.errors)
            return False
        try:
            obj = msgspec.convert(data, self.model)
        except Exception as e:
            self.errors = [e]
            self._log_errors(self.errors)
            return False
        self.data = obj
        self.errors = []
        return True

    def write(self, skip_same=True):
        """
        Write self.data into yaml file, comments are inserted above the line
        of each key from ``Meta(extra={"help": ...})`` annotations, matched
        by the full key path

        Args:
            skip_same (bool): True to skip writing if existing content is the same
                as content to write. This would reduce disk write but add disk read

        Returns:
            bool: if write
        """
        # yaml_dumps from yamlfile returns utf-8 bytes, decode into str
        data = msgspec.to_builtins(self.data)
        text = yaml_dumps(data).decode('utf-8')
        text = insert_comments(text, self.help_map)
        if skip_same:
            try:
                old = atomic_read_text(self.file)
            except (FileNotFoundError, UnicodeDecodeError):
                old = None
            if text == old:
                return False

        print(f'Write config {self.file}')
        atomic_write(self.file, text)
        return True

    def _secrete_value(self, path):
        """
        Args:
            path (tuple[str]):

        Returns:
            Any: Any value to override value displayed in show()
                NODEFAULT to display current value
        """
        return msgspec.NODEFAULT

    def show(self):
        """
        Log all settings that are different from the default values, like::

            Showing deploy config of xxx
              Webapp.Lang = 'zh-CN'
            (rest of the config is the same as default)

        Key paths are joined with dots, e.g. ``Webapp.Lang``. When no setting
        differs from the default, ``(config is the same as default)`` is
        logged instead of the rest line.
        """
        print(f'Showing deploy config of {self.file}')
        default = msgspec.to_builtins(self.model())
        data = msgspec.to_builtins(self.data)
        count = 0
        for path, _, after in deep_iter_diff(default, data):
            secret = self._secrete_value(path)
            if secret is not msgspec.NODEFAULT:
                after = secret
            print(f'  {".".join(path)} = {after!r}')
            count += 1
        if count:
            print('(rest of the config is the same as default)')
        else:
            print('(config is the same as default)')
