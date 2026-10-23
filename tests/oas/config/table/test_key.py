import msgspec
import pytest

from oas.config.table.key import JwtSecret, KeyTable, KeyValue


class Metadata(msgspec.Struct):
    enabled: bool = False
    name: str = ''


def test_key_table_raw_values_round_trip(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    assert table.get_value('missing', b'fallback') == b'fallback'
    table.set_value('blob', b'\x00\xff')
    assert table.get_value('blob') == b'\x00\xff'


def test_key_table_msgpack_model_round_trip(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    table.set('metadata', Metadata(enabled=True, name='demo'))
    assert table.get('metadata', Metadata) == Metadata(enabled=True, name='demo')


def test_key_table_get_missing_model_uses_default(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    assert table.get('missing', Metadata) == Metadata()


def test_key_table_mod_is_utf8_text(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    table.mod_set('测试模块')
    assert table.mod_get() == '测试模块'


def test_key_table_mod_invalid_bytes_returns_empty(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    table.set_value('Mod', b'\xff')
    assert table.mod_get() == ''


def test_jwt_secret_is_binary_and_persisted(config_table):
    table = KeyTable(':memory:')
    table.create_table()
    first = table.jwt_secret
    second = table.jwt_secret
    assert isinstance(first, bytes)
    assert len(first) == 32
    assert second == first
    assert isinstance(table.get('JwtSecret', JwtSecret), JwtSecret)


def test_set_value_requires_bytes(config_table):
    table = KeyTable(':memory:')

    with pytest.raises(TypeError, match='must be bytes'):
        table.set_value('k', 'text')


def test_mod_set_requires_text(config_table):
    table = KeyTable(':memory:')

    with pytest.raises(TypeError, match='must be str'):
        table.mod_set(b'bytes')


def test_get_value_missing_returns_default(config_table):
    table = KeyTable(':memory:')

    assert table.get_value('missing') is None
    assert table.get_value('missing', b'fallback') == b'fallback'


def test_get_missing_model_uses_struct_defaults(config_table):
    table = KeyTable(':memory:')

    assert table.get('missing', JwtSecret) == JwtSecret()


def test_corrupt_msgpack_value_raises(config_table):
    table = KeyTable(':memory:')
    table.set_value('bad', b'\xc1')

    with pytest.raises(msgspec.DecodeError):
        table.get('bad', KeyValue)


def test_set_and_get_model_roundtrip(config_table):
    table = KeyTable(':memory:')
    value = KeyValue(key='k', value=b'v')

    table.set('k', value)

    assert table.get('k', KeyValue) == value


def test_mod_roundtrip_and_empty_default(config_table):
    table = KeyTable(':memory:')
    assert table.mod_get() == ''

    table.mod_set('demo')
    assert table.mod_get() == 'demo'


def test_jwt_secret_is_stable_and_32_bytes(config_table):
    table = KeyTable(':memory:')

    first = table.jwt_secret
    second = table.jwt_secret

    assert first == second
    assert len(first) == 32
    assert JwtSecret().secret == b''
