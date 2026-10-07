from collections.abc import Callable
from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo

UNSET = object()


def temporal_field(
    component_type: str,
    *,
    default: Any,
    default_factory: Callable[[], Any] | None,
    hide: bool | None,
    description: str | None,
    icon: str | None,
    title: str | None,
    alias: str | None,
    depends: str | None,
    read_only: bool | None,
    json_schema_extra: dict[str, Any] | None,
    kwargs: dict[str, Any],
) -> FieldInfo:
    """Build shared field metadata for temporal component types."""
    if default is UNSET and default_factory is None:
        raise TypeError(
            f"{component_type}.field requires default or default_factory"
        )
    if default is not UNSET and default_factory is not None:
        raise TypeError(
            f"{component_type}.field cannot set both default and default_factory"
        )

    field_kwargs = dict(kwargs)
    field_kwargs["validate_default"] = True
    if default_factory is not None:
        field_kwargs["default_factory"] = default_factory
    else:
        field_kwargs["default"] = default
    generated = {"type": component_type}
    if read_only is not None:
        generated["readOnly"] = read_only
    field_kwargs["json_schema_extra"] = build_field_schema_extra(
        hide=hide,
        icon=icon,
        alias=alias,
        depends=depends,
        json_schema_extra=json_schema_extra,
        **generated,
    )
    if description is not None:
        field_kwargs["description"] = description
    if title is not None:
        field_kwargs["title"] = title
    return Field(**field_kwargs)


def build_field_schema_extra(
    *,
    hide: bool | None = False,
    icon: str | None = None,
    alias: str | None = None,
    depends: str | None = None,
    json_schema_extra: dict[str, Any] | None = None,
    **generated: Any,
) -> dict[str, Any]:
    """Build shared UI metadata for Option and Input fields."""

    if json_schema_extra is not None and not isinstance(json_schema_extra, dict):
        raise TypeError("json_schema_extra must be a dictionary")

    extra = dict(generated)
    if hide is not None:
        extra["hide"] = hide
    if icon is not None:
        extra["icon"] = icon
    if depends is not None:
        extra["depends"] = depends
    # ``alias`` remains reserved for future Pydantic alias support.  It is
    # intentionally not emitted unless supplied through json_schema_extra.
    del alias
    extra.update(json_schema_extra or {})
    return extra



