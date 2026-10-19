import msgspec

from oas.config.table.key import JwtSecret, KeyTable


class Metadata(msgspec.Struct):
    enabled: bool = False
    name: str = ""


def test_key_table_raw_values_round_trip(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    assert table.get_value("missing", b"fallback") == b"fallback"
    table.set_value("blob", b"\x00\xff")
    assert table.get_value("blob") == b"\x00\xff"


def test_key_table_msgpack_model_round_trip(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    table.set("metadata", Metadata(enabled=True, name="demo"))
    assert table.get("metadata", Metadata) == Metadata(enabled=True, name="demo")


def test_key_table_get_missing_model_uses_default(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    assert table.get("missing", Metadata) == Metadata()


def test_key_table_mod_is_utf8_text(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    table.mod_set("测试模块")
    assert table.mod_get() == "测试模块"


def test_key_table_mod_invalid_bytes_returns_empty(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    table.set_value("Mod", b"\xff")
    assert table.mod_get() == ""


def test_jwt_secret_is_binary_and_persisted(config_table):
    table = KeyTable(":memory:")
    table.create_table()
    first = table.jwt_secret
    second = table.jwt_secret
    assert isinstance(first, bytes)
    assert len(first) == 32
    assert second == first
    assert isinstance(table.get("JwtSecret", JwtSecret), JwtSecret)
