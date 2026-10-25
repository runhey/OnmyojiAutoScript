from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

UNSET = object()


class ConfigBase(BaseModel):
    """Base class for all OAS configuration models."""

    # Validate on assignment so that every mutation path (post_edit hooks,
    # overrides, cross-task setters) rejects an invalid value instead of
    # silently storing it.
    model_config = ConfigDict(validate_assignment=True)

    __config_abstract__: ClassVar[bool] = True

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Register completed Task and Group subclasses.

        Pydantic calls this hook while creating a model class, after the
        model fields are available.  It is never called when a model instance
        is constructed.
        """
        super().__pydantic_init_subclass__(**kwargs)
        if cls.__dict__.get('__config_abstract__', False):
            return

        from oas.config.models.registry import config_model_registry

        try:
            from oas.config.models.groups import GroupBase
            from oas.config.models.tasks import TaskBase
        except ImportError:
            # The base classes themselves can be created while their module is
            # still importing.  They are abstract and must not be registered.
            return

        if issubclass(cls, TaskBase):
            config_model_registry.register_task(cls)
        elif issubclass(cls, GroupBase):
            config_model_registry.register_group(cls)


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
) -> Any:
    """Build shared field metadata for temporal component types."""
    if default is UNSET and default_factory is None:
        raise TypeError(f'{component_type}.field requires default or default_factory')
    if default is not UNSET and default_factory is not None:
        raise TypeError(
            f'{component_type}.field cannot set both default and default_factory'
        )

    field_kwargs = dict(kwargs)
    field_kwargs['validate_default'] = True
    if default_factory is not None:
        field_kwargs['default_factory'] = default_factory
    else:
        field_kwargs['default'] = default
    generated = {'type': component_type}
    if read_only is not None:
        generated['readOnly'] = read_only
    field_kwargs['json_schema_extra'] = build_field_schema_extra(
        hide=hide,
        icon=icon,
        alias=alias,
        depends=depends,
        json_schema_extra=json_schema_extra,
        **generated,
    )
    if description is not None:
        field_kwargs['description'] = description
    if title is not None:
        field_kwargs['title'] = title
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
        raise TypeError('json_schema_extra must be a dictionary')

    extra = dict(generated)
    if hide is not None:
        extra['hide'] = hide
    if icon is not None:
        extra['icon'] = icon
    if depends is not None:
        extra['depends'] = depends
    # ``alias`` remains reserved for future Pydantic alias support.  It is
    # intentionally not emitted unless supplied through json_schema_extra.
    del alias
    extra.update(json_schema_extra or {})
    return extra


def boolean_component_field(
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
    json_schema_extra: dict[str, Any] | None,
    kwargs: dict[str, Any],
) -> Any:
    """Build shared field metadata for boolean UI components."""
    if default is UNSET and default_factory is None:
        raise TypeError(f'{component_type}.field requires default or default_factory')
    if default is not UNSET and default_factory is not None:
        raise TypeError(
            f'{component_type}.field cannot set both default and default_factory'
        )

    field_kwargs = dict(kwargs)
    if default_factory is not None:
        field_kwargs['default_factory'] = default_factory
    else:
        field_kwargs['default'] = default
    field_kwargs['validate_default'] = True
    field_kwargs['json_schema_extra'] = build_field_schema_extra(
        hide=hide,
        icon=icon,
        alias=alias,
        depends=depends,
        json_schema_extra=json_schema_extra,
        type=component_type,
    )
    if description is not None:
        field_kwargs['description'] = description
    if title is not None:
        field_kwargs['title'] = title
    return Field(**field_kwargs)
