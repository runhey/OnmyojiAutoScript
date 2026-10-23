"""Tests for the unified ``ConfigError`` struct."""

import msgspec
import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from oas.config.entry.error import ConfigError


class ErrorModel(BaseModel):
    count: int = Field(ge=0)


def _validation_error(value: int = -1) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        ErrorModel(count=value)
    return caught.value


def test_defaults():
    error = ConfigError('boom')

    assert error.msg == 'boom'
    assert error.type == 'INPUT_REJECTED'
    assert (error.task, error.group, error.arg) == ('', '', '')
    assert error.loc == ()
    assert str(error) == 'boom'


def test_from_pydantic_uses_the_first_error():
    exc = _validation_error()

    error = ConfigError.from_pydantic(exc, task='t', group='g', arg='count')

    first = exc.errors()[0]
    assert error.msg == str(first['msg'])
    assert error.type == str(first['type'])
    assert error.task == 't'
    assert error.group == 'g'
    assert error.arg == 'count'
    assert error.loc == tuple(first['loc'])


def test_from_pydantic_fills_loc_from_arg_when_pydantic_has_none():
    with pytest.raises(ValidationError) as caught:
        TypeAdapter(int).validate_python('not-an-int')

    error = ConfigError.from_pydantic(caught.value, arg='count')

    assert error.loc == ('count',)


def test_error_roundtrips_through_msgpack():
    error = ConfigError('boom', type='greater_than_equal', task='t', arg='count')

    encoded = msgspec.msgpack.encode(error)
    decoded = msgspec.msgpack.decode(encoded, type=ConfigError)

    assert decoded == error


def test_omit_defaults_omits_empty_fields():
    encoded = msgspec.msgpack.encode(ConfigError('boom'))

    # Only ``msg`` is non-default; ``type`` defaults are omitted.
    decoded = msgspec.msgpack.decode(encoded)
    assert decoded == {'msg': 'boom'}
