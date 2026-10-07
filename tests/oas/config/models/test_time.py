from datetime import UTC, time

import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Time


class TimeConfig(BaseModel):
    run_time: Time = Time.field(
        default=Time(19, 0),
        description="每天运行时间",
        icon="clock",
    )


def test_time_preserves_datetime_time_api_and_serializes_seconds():
    model = TimeConfig.model_validate({"run_time": "09:30"})

    assert isinstance(model.run_time, Time)
    assert isinstance(model.run_time, time)
    assert (model.run_time.hour, model.run_time.minute, model.run_time.second) == (
        9,
        30,
        0,
    )
    assert model.model_dump() == {"run_time": "09:30:00"}
    assert model.model_dump_json() == '{"run_time":"09:30:00"}'


def test_time_accepts_time_objects_and_legacy_constructor():
    model = TimeConfig.model_validate({"run_time": time(12, 5)})
    legacy = Time(7, 8, 9)

    assert isinstance(model.run_time, Time)
    assert model.run_time == Time(12, 5)
    assert legacy.hour == 7
    assert legacy.minute == 8
    assert legacy.second == 9
    assert Time(hour=18, minute=20) == time(18, 20)


def test_time_schema_uses_component_type_and_field_metadata():
    schema = TimeConfig.model_json_schema()["properties"]["run_time"]

    assert schema == {
        "default": "19:00:00",
        "description": "每天运行时间",
        "hide": False,
        "icon": "clock",
        "title": "Run Time",
        "type": "Time",
    }
    assert "input" not in schema
    assert "format" not in schema


@pytest.mark.parametrize("value", ["09:30:00.000001", time(9, 30, microsecond=1)])
def test_time_rejects_nonzero_microseconds(value):
    with pytest.raises((ValidationError, ValueError), match="(microsecond|Invalid time value)"):
        TimeConfig.model_validate({"run_time": value})


def test_time_rejects_timezone_information():
    aware = time(9, 30).replace(tzinfo=UTC)

    with pytest.raises((ValidationError, ValueError), match="timezone"):
        TimeConfig.model_validate({"run_time": aware})


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        123,
        12.5,
        [],
        {},
        "",
        "abc",
        "1:02",
        "09:3",
        "24:00",
        "09:60",
        "09:00:60",
        "09:00:00junk",
        "09:00+08:00",
    ],
)
def test_time_rejects_invalid_user_input(value):
    with pytest.raises(ValidationError, match="Time"):
        TimeConfig.model_validate({"run_time": value})


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((24, 0), "hour"),
        ((0, 60), "minute"),
        ((0, 0, 60), "second"),
        ((0, 0, 0, 1), "microsecond"),
        ((0, 0, 0, 0, UTC), "timezone"),
    ],
)
def test_time_constructor_rejects_invalid_values(args, message):
    with pytest.raises(ValueError, match=message):
        Time(*args)


def test_time_rejects_invalid_default_value_when_model_is_created():
    class InvalidDefaultConfig(BaseModel):
        run_time: Time = Time.field(default="24:00")

    with pytest.raises(ValidationError, match="Invalid time value"):
        InvalidDefaultConfig()


def test_time_rejects_invalid_default_factory_result():
    class InvalidFactoryConfig(BaseModel):
        run_time: Time = Time.field(default_factory=lambda: 123)

    with pytest.raises(ValidationError, match="Time requires"):
        InvalidFactoryConfig()


def test_time_default_factory_is_validated_and_not_in_schema():
    class FactoryConfig(BaseModel):
        run_time: Time = Time.field(default_factory=lambda: "06:15")

    model = FactoryConfig()

    assert isinstance(model.run_time, Time)
    assert model.model_dump() == {"run_time": "06:15:00"}
    assert "default" not in FactoryConfig.model_json_schema()["properties"]["run_time"]


def test_time_field_requires_exactly_one_default_form():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        Time.field()
    with pytest.raises(TypeError, match="cannot set both default and default_factory"):
        Time.field(default=Time(1), default_factory=lambda: Time(2))


def test_time_composes_in_lists_optional_values_and_dictionaries():
    class CompositeConfig(BaseModel):
        times: list[Time]
        optional: Time | None = None
        named: dict[str, Time]

    model = CompositeConfig.model_validate(
        {
            "times": ["01:02", Time(3, 4)],
            "named": {"start": "05:06:07"},
        }
    )

    assert all(isinstance(item, Time) for item in model.times)
    assert model.model_dump() == {
        "times": ["01:02:00", "03:04:00"],
        "optional": None,
        "named": {"start": "05:06:07"},
    }
