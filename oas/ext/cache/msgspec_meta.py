import msgspec
from typing_extensions import get_type_hints


class FieldMetadata(msgspec.Struct):
    """Metadata extracted from msgspec.Meta annotations on a struct field."""

    extra: dict = {}
    extra_json_schema: dict = {}


def get_field_metadata(cls: type) -> "dict[str, FieldMetadata]":
    """Return {field_name: FieldMetadata} for all fields with msgspec.Meta.

    Extracts ``extra`` and ``extra_json_schema`` from all ``msgspec.Meta``
    annotations on the fields of a ``msgspec.Struct`` (or any class using
    ``Annotated`` + ``Meta``). Multiple ``Meta`` objects on the same field
    are merged in order (later keys override earlier ones).

    Args:
        cls: A msgspec Struct subclass (or any class with annotated fields).

    Returns:
        A mapping from field name to a :class:`FieldMetadata` instance.
        Fields without any ``Meta`` metadata are omitted.
    """
    result = {}
    hints = get_type_hints(cls, include_extras=True)
    for name, hint in hints.items():
        extra = {}
        extra_json_schema = {}

        if hasattr(hint, "__metadata__"):
            for m in hint.__metadata__:
                if not isinstance(m, msgspec.Meta):
                    continue
                if m.extra:
                    extra.update(m.extra)
                if m.extra_json_schema:
                    extra_json_schema.update(m.extra_json_schema)

        result[name] = FieldMetadata(
            extra=extra,
            extra_json_schema=extra_json_schema,
        )

    return result
