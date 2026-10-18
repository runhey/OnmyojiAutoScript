import datetime
import uuid
from typing import Any, Dict, List, Set, Tuple, Type, Union, get_args, get_origin

import msgspec

from oas.db.table import Table

# In Python 3.10+, the union type operator | can be used.
# This creates a `types.UnionType` object.
try:
    from types import UnionType
except ImportError:
    UnionType = Union  # Fallback for older Python versions


def _generate_value_for_type(type_hint, memo: "dict[Type, Any]"):
    """
    Recursively generates a sample value based on a type hint.
    This is the core worker function for generate_example.
    """
    # 1. Handle recursion: Check the memoization cache first to prevent infinite loops.
    if type_hint in memo:
        return memo[type_hint]

    # 2. Handle basic and common types first for efficiency and clarity.
    # These types do not have an 'origin' and are the most frequent cases.
    if type_hint is str:
        return "string_example"
    if type_hint is int:
        return 123
    if type_hint is float:
        return 45.67
    if type_hint is bool:
        return True
    if type_hint is bytes:
        return b"bytes_example"
    if type_hint is uuid.UUID:
        return uuid.uuid4()
    if type_hint is datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    if type_hint is Any:
        return "any_value"

    # 3. Handle nested msgspec models.
    # This must be checked before `get_origin` as classes don't have an origin.
    if isinstance(type_hint, type) and issubclass(type_hint, msgspec.Struct):
        # Cache a placeholder to handle direct recursion, then update it after generation.
        # memo[type_hint] = f"Generating {type_hint.__name__}..."
        instance = _generate_model_instance(type_hint, memo)
        memo[type_hint] = instance  # Update cache with the real instance
        return instance

    # 4. Handle string forward references (e.g., "MyClass").
    # `msgspec` typically resolves these, but this adds robustness.
    if isinstance(type_hint, str):
        # A simple resolver for built-in types represented as strings.
        builtin_map = {
            "str": str, "int": int, "float": float, "bool": bool, "bytes": bytes, "Any": Any,
        }
        resolved_type = builtin_map.get(type_hint)
        if resolved_type:
            # Recursively call with the resolved type.
            return _generate_value_for_type(resolved_type, memo)
        else:
            # Cannot resolve unknown custom class strings without more context.
            return f"unresolved_forward_ref_{type_hint}"

    # 5. Handle generic types from the `typing` module.
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle Union types (e.g., Union[str, int] or str | int) and Optional[T].
    if origin in (Union, UnionType):
        # Filter out NoneType and generate a value for the first remaining type.
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            return _generate_value_for_type(non_none_args[0], memo)
        return None  # Only NoneType was present (e.g., type hint is None)

    # Handle container types.
    if origin in (list, List):
        item_type = args[0] if args else Any
        return [_generate_value_for_type(item_type, memo)]

    if origin in (set, Set):
        item_type = args[0] if args else Any
        return {_generate_value_for_type(item_type, memo)}

    if origin in (tuple, Tuple):
        if not args:
            return ()
        # Handle variable-length tuples like `tuple[int, ...]`
        if len(args) == 2 and args[1] is Ellipsis:
            return (_generate_value_for_type(args[0], memo),)
        # Handle fixed-length tuples like `tuple[int, str]`
        return tuple(_generate_value_for_type(arg, memo) for arg in args)

    if origin in (dict, Dict):
        key_type = args[0] if args else Any
        value_type = args[1] if len(args) > 1 else Any
        return {
            _generate_value_for_type(key_type, memo): _generate_value_for_type(value_type, memo)
        }

    # 6. Fallback for any other unhandled types.
    try:
        # Attempt to call a zero-argument constructor.
        return type_hint()
    except (TypeError, AttributeError):
        # If it fails, we cannot generate a value.
        return None


def _generate_model_instance(cls: "Type[msgspec.Struct]", memo: "dict[Type, Any]") -> "msgspec.Struct":
    """
    Constructs an instance of a specific msgspec model class.
    """
    kwargs = {}
    # `msgspec.msg.fields` provides metadata for all fields in the model.
    for field in msgspec.structs.fields(cls):
        # Per the requirement, skip any field that has a default value or factory.
        # The model's __init__ will handle these automatically.
        if field.default is not msgspec.NODEFAULT or field.default_factory is not msgspec.NODEFAULT:
            continue

        # Generate a value for the required field.
        kwargs[field.name] = _generate_value_for_type(field.type, memo)

    return cls(**kwargs)


def generate_example(model_class: "Type[msgspec.Struct]") -> "msgspec.Struct":
    """
    Generates a sample data instance for any given msgspec model.

    This function populates all required fields (those without default values)
    with sample data. Optional fields or fields with default values are left
    to their defaults.

    Args:
        model_class: The msgspec.Msg subclass to generate an example for.

    Returns:
        An instance of `model_class` populated with sample data.
    """
    # Initialize the memoization cache to handle recursive data structures.
    memoization_cache = {}

    # Start the generation process by calling the main worker function.
    return _generate_model_instance(model_class, memoization_cache)


def validate_table(table_cls: Type[Table]):
    """
    Args:
        table_cls:
    """
    # test in memory
    table = table_cls(':memory:')
    # test CREATE_TABLE
    table.create_table()
    # test MODEL
    row = generate_example(table.MODEL)
    # test AUTO_INCREMENT
    table.insert_row(row)
    table.select_one()
    # test PRIMARY_KEY
    table.delete_row(row)
    # test TABLE_NAME
    table.drop_table()


