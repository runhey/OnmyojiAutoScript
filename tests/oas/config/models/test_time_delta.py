from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import TimeDelta


class TimeDeltaConfig(BaseModel):
    interval: TimeDelta = TimeDelta.field(
        default=TimeDelta(hours=6),
        description="重试间隔",
        icon="timer",
    )


def test_time_delta_preserves_native_api_and_serializes_seconds():
    model = TimeDeltaConfig.model_validate({"interval": "03 02:04:05"})

    assert isinstance(model.interval, TimeDelta)
    assert isinstance(model.interval, timedelta)
    assert model.interval.days == 3
    assert model.interval.seconds == (2 * 3600 + 4 * 60 + 5)
    assert model.interval + timedelta(hours=1) == timedelta(
        days=3, hours=3, minutes=4, seconds=5
    )
    assert model.model_dump() == {"interval": "03 02:04:05"}
    assert model.model_dump_json() == '{"interval":"03 02:04:05"}'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00 00:00:00", "00 00:00:00"),
        ("1 2:3:4", "01 02:03:04"),
        ("12 23:59:59", "12 23:59:59"),
        (timedelta(days=2, minutes=30), "02 00:30:00"),
        (TimeDelta(days=4, seconds=5), "04 00:00:05"),
    ],
)
def test_time_delta_accepts_supported_inputs(value, expected):
    model = TimeDeltaConfig.model_validate({"interval": value})

    assert isinstance(model.interval, TimeDelta)
    assert model.model_dump()["interval"] == expected


def test_time_delta_legacy_constructor_is_available():
    interval = TimeDelta(days=2, hours=3, minutes=4, seconds=5)

    assert isinstance(interval, timedelta)
    assert interval == timedelta(days=2, hours=3, minutes=4, seconds=5)


def test_time_delta_schema_uses_component_type_and_field_metadata():
    schema = TimeDeltaConfig.model_json_schema()["properties"]["interval"]

    assert schema == {
        "default": "00 06:00:00",
        "description": "重试间隔",
        "hide": False,
        "icon": "timer",
        "title": "Interval",
        "type": "TimeDelta",
    }
    assert "input" not in schema
    assert "format" not in schema


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1 day",
        "1 02:00:00junk",
        "01 24:00:00",
        "01 00:60:00",
        "01 00:00:60",
        "01-02:00:00",
        None,
        True,
        1,
        1.5,
        [],
        {},
    ],
)
def test_time_delta_rejects_invalid_user_input(value):
    with pytest.raises(ValidationError, match="TimeDelta|interval"):
        TimeDeltaConfig.model_validate({"interval": value})


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"microseconds": 1}, "microsecond"),
        ({"milliseconds": 1}, "microsecond"),
        ({"seconds": 0.000001}, "microsecond"),
    ],
)
def test_time_delta_constructor_rejects_subsecond_values(kwargs, message):
    with pytest.raises(ValueError, match=message):
        TimeDelta(**kwargs)


@pytest.mark.parametrize("value", ["-01 02:00:00", timedelta(days=-1, hours=-2)])
def test_time_delta_supports_negative_values(value):
    model = TimeDeltaConfig.model_validate({"interval": value})

    assert model.model_dump()["interval"] == "-01 02:00:00"


def test_time_delta_rejects_invalid_default_value():
    class InvalidDefaultConfig(BaseModel):
        interval: TimeDelta = TimeDelta.field(default="01 24:00:00")

    with pytest.raises(ValidationError, match="Invalid interval value"):
        InvalidDefaultConfig()


def test_time_delta_rejects_invalid_default_factory_result():
    class InvalidFactoryConfig(BaseModel):
        interval: TimeDelta = TimeDelta.field(default_factory=lambda: object())

    with pytest.raises(ValidationError, match="TimeDelta requires"):
        InvalidFactoryConfig()


def test_time_delta_default_factory_is_validated_and_not_in_schema():
    class FactoryConfig(BaseModel):
        interval: TimeDelta = TimeDelta.field(default_factory=lambda: "01 02:00:00")

    model = FactoryConfig()

    assert isinstance(model.interval, TimeDelta)
    assert model.model_dump() == {"interval": "01 02:00:00"}
    assert "default" not in FactoryConfig.model_json_schema()["properties"]["interval"]


def test_time_delta_field_requires_exactly_one_default_form():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        TimeDelta.field()
    with pytest.raises(TypeError, match="cannot set both default and default_factory"):
        TimeDelta.field(default=TimeDelta(1), default_factory=lambda: TimeDelta(2))


def test_time_delta_composes_in_lists_optional_values_and_dictionaries():
    class CompositeConfig(BaseModel):
        intervals: list[TimeDelta]
        optional: TimeDelta | None = None
        named: dict[str, TimeDelta]

    model = CompositeConfig.model_validate(
        {
            "intervals": ["01 02:00:00", TimeDelta(hours=3)],
            "named": {"retry": "00 00:05:00"},
        }
    )

    assert all(isinstance(item, TimeDelta) for item in model.intervals)
    assert model.model_dump() == {
        "intervals": ["01 02:00:00", "00 03:00:00"],
        "optional": None,
        "named": {"retry": "00 00:05:00"},
    }
