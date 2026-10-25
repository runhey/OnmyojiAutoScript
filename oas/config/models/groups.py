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

    @classmethod
    def validate_patch(cls, patch: Mapping[str, Any]) -> Self:
        """Validate a partial ``{arg: value}`` patch and return a new instance.

        Only the patched arguments are supplied, so every other field falls
        back to its default and model level validators run against defaults
        instead of the stored state (Alasio semantics).  Cross-argument
        adjustments therefore belong in :meth:`post_edit`, which runs on the
        merged state.  Pydantic ignores unknown arguments, so the caller still
        checks field existence itself.

        Args:
            patch: Arguments to validate.

        Returns:
            A new validated instance of this Group.
        """
        return cls.model_validate(dict(patch))

    def post_edit(self, old: Self, edits: Mapping[str, Any]) -> None:
        """Adjust other arguments after a successful edit, before the write.

        The hook runs on the merged Group state (``self`` already carries the
        new values), so it is the only place that sees both the stored state
        and the current edit.  Changes to other arguments are written back and
        reported to the caller as extra events; raise ``ValidationError`` to
        reject the whole edit.

        Args:
            old: Group state before the current edit.
            edits: Validated arguments changed by the current edit.
        """


class DynamicGroupBase(GroupBase):
    """Base class for groups whose instances can be managed dynamically."""

    __config_abstract__: ClassVar[bool] = True
