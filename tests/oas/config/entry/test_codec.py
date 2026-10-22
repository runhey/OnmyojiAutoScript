"""Tests for the dict <-> MsgPack ``Codec``."""

import msgspec
import pytest

from oas.config.entry.codec import Codec


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"name": "group", "count": 3, "ratio": 0.5, "enabled": True},
        {"nothing": None, "items": [1, 2, 3], "nested": {"a": {"b": 1}}},
        {"bytes": b"\x00\x01", "text": "配置"},
    ],
)
def test_roundtrip(data):
    assert Codec.decode(Codec.encode(data)) == data


def test_empty_dict_is_the_reset_payload():
    assert Codec.decode(Codec.encode({})) == {}


def test_encode_requires_dict():
    with pytest.raises(TypeError, match="requires a dict"):
        Codec.encode([("a", 1)])


@pytest.mark.parametrize("value", ["text", 1, None, ["a"]])
def test_decode_requires_bytes(value):
    with pytest.raises(TypeError, match="requires bytes"):
        Codec.decode(value)


def test_decode_accepts_bytearray_and_memoryview():
    payload = Codec.encode({"count": 1})

    assert Codec.decode(bytearray(payload)) == {"count": 1}
    assert Codec.decode(memoryview(payload)) == {"count": 1}


def test_decode_rejects_corrupt_payload():
    with pytest.raises(ValueError, match="invalid MsgPack"):
        Codec.decode(b"\xc1")


@pytest.mark.parametrize("value", [[1, 2], 1, "text", None])
def test_decode_rejects_non_map_payload(value):
    with pytest.raises(ValueError, match="must be a map"):
        Codec.decode(msgspec.msgpack.encode(value))


def test_decode_accepts_a_msgpack_struct_payload():
    """Struct and dict share the same MsgPack map encoding."""

    class LegacyPayload(msgspec.Struct):
        name: str = "legacy"
        count: int = 8

    assert Codec.decode(msgspec.msgpack.encode(LegacyPayload())) == {
        "name": "legacy",
        "count": 8,
    }


def test_encode_rejects_non_dict_mapping_like_values():
    with pytest.raises(TypeError, match="requires a dict"):
        Codec.encode([("k", "v")])
    with pytest.raises(TypeError, match="requires a dict"):
        Codec.encode(None)


def test_encode_rejects_unencodable_value():
    with pytest.raises(TypeError):
        Codec.encode({"value": object()})


@pytest.mark.parametrize("payload", [b"", b"\xc1", b"\x81\xa1k"])
def test_decode_rejects_truncated_or_invalid_payload(payload):
    with pytest.raises(ValueError, match="invalid MsgPack"):
        Codec.decode(payload)


def test_decode_accepts_integer_keys_in_the_map():
    payload = msgspec.msgpack.encode({1: "one", 2: "two"})

    assert Codec.decode(payload) == {1: "one", 2: "two"}


def test_decode_rejects_trailing_bytes():
    payload = Codec.encode({"a": 1}) + b"\x00"

    with pytest.raises(ValueError, match="invalid MsgPack"):
        Codec.decode(payload)
