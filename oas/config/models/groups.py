"""Base models for reusable configuration groups."""

from oas.config.models.base import ConfigBase


class GroupBase(ConfigBase):
    """Base class for a reusable group of related configuration fields."""


class DynamicGroupBase(GroupBase):
    """Base class for groups whose instances can be managed dynamically."""



