"""Base models for reusable configuration groups."""

from collections.abc import Mapping
from typing import Any, ClassVar, Self

from oas.config.models.base import ConfigBase


class GroupBase(ConfigBase):
    """Base class for a reusable group of related configuration fields."""

    __config_abstract__: ClassVar[bool] = True

    def to_dict(self) -> dict[str, Any]:
        """Return this Group as a plain Python dict."""
        return self.model_dump(mode='python')

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a validated Group from a plain Python dict."""
        return cls.model_validate(data)


class DynamicGroupBase(GroupBase):
    """Base class for groups whose instances can be managed dynamically."""

    __config_abstract__: ClassVar[bool] = True
