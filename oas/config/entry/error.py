"""Unified error object shared by configuration operations.

Alasio relied on ``msgspecerror.ErrorInfo`` to describe validation failures.
OAS validates with Pydantic, so the configuration layer keeps one small,
dependency-free error struct instead.  Both the ``config_*`` (Alasio
compatible) and ``cfg_*`` (OAS native) operation families use it, so callers
only need to understand one failure shape.
"""

from __future__ import annotations

import msgspec
from pydantic import ValidationError


class ConfigError(msgspec.Struct, omit_defaults=True):
    """One failed configuration operation.

    Attributes:
        msg: Human readable message.
        type: Stable error kind.  User input failures default to
            ``"INPUT_REJECTED"``; Pydantic validation failures carry the
            Pydantic error type such as ``"greater_than_equal"``.
    """

    msg: str
    type: str = 'INPUT_REJECTED'

    @classmethod
    def from_pydantic(cls, exc: ValidationError) -> ConfigError:
        """Build a :class:`ConfigError` from a Pydantic validation error."""
        errors = exc.errors()
        first = errors[0] if errors else {}
        return cls(
            msg=str(first.get('msg', exc)),
            type=str(first.get('type', 'INPUT_REJECTED')),
        )

    def __str__(self) -> str:
        return self.msg
