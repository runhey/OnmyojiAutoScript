from typing import Any


UNSET = object()


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
