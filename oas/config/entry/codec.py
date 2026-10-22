"""MsgPack codec for configuration dict payloads.

``Codec`` only converts a plain Python dict to the bytes stored in the
configuration database and back.  Model validation stays in Pydantic: the
dict comes from ``GroupBase.to_dict()`` / ``TaskBase.to_dict()`` and is
consumed by the matching ``from_dict()`` classmethods.
"""

from __future__ import annotations

from typing import Any

import msgspec


class Codec:
    """Convert configuration dictionaries to and from MsgPack bytes."""

    @staticmethod
    def encode(data: dict[str, Any]) -> bytes:
        """Encode one configuration dict as MsgPack bytes."""

        if not isinstance(data, dict):
            raise TypeError("Codec.encode requires a dict")
        return msgspec.msgpack.encode(data)

    @staticmethod
    def decode(blob: bytes) -> dict[str, Any]:
        """Decode MsgPack bytes into one configuration dict."""

        if not isinstance(blob, (bytes, bytearray, memoryview)):
            raise TypeError("Codec.decode requires bytes")
        try:
            data = msgspec.msgpack.decode(bytes(blob))
        except msgspec.DecodeError as exc:
            raise ValueError(f"invalid MsgPack payload: {exc}") from exc
        if not isinstance(data, dict):
            # The payload is stored data, not a caller type error.
            raise ValueError(  # noqa: TRY004
                f"MsgPack payload must be a map, got {type(data).__name__}"
            )
        return data
