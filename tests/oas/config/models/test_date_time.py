from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import DateTime


class DateTimeConfig(BaseModel):
    next_run: DateTime = DateTime.field(
        default=DateTime(2026, 10, 7, 9),
        description="下一次运行时间",
        icon="calendar",
    )


def test_date_time_preserves_native_api_and_serializes_seconds():
    model = DateTimeConfig.model_validate({"next_run": "2026-10-07T12:34:56"})

    assert isinstance(model.next_run, DateTime)
    assert isinstance(model.next_run, datetime)
    assert model.next_run.year == 2026
    assert model.next_run.hour == 12
    assert model.model_dump() == {"next_run": "2026-10-07 12:34:56"}
    assert model.model_dump_json() == '{"next_run":"2026-10-07 12:34:56"}'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-07 09:00:00", "2026-10-07 09:00:00"),
        ("2026-10-07T09:00:00", "2026-10-07 09:00:00"),
        (datetime(2026, 10, 7, 9), "2026-10-07 09:00:00"),  # noqa: DTZ001
        (DateTime(2026, 10, 7, 9), "2026-10-07 09:00:00"),
    ],
)
def test_date_time_accepts_supported_inputs(value, expected):
    model = DateTimeConfig.model_validate({"next_run": value})

    assert isinstance(model.next_run, DateTime)
    assert model.model_dump()["next_run"] == expected


def test_date_time_legacy_constructor_and_classmethod_are_available():
    constructed = DateTime(2026, 10, 7, 9, 30)
    parsed = DateTime.fromisoformat("2026-10-07 09:30:00")

    assert isinstance(constructed, datetime)
    assert isinstance(parsed, DateTime)
    assert parsed == constructed


def test_date_time_schema_uses_component_type_and_field_metadata():
    schema = DateTimeConfig.model_json_schema()["properties"]["next_run"]

    assert schema == {
        "default": "2026-10-07 09:00:00",
        "description": "下一次运行时间",
        "hide": False,
        "icon": "calendar",
        "title": "Next Run",
        "type": "DateTime",
    }
    assert "input" not in schema
    assert "format" not in schema


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2026-10-07",
        "2026-10-07 25:00:00",
        "2026-10-07 00:60:00",
        "2026-10-07 00:00:60",
        "2026-10-07 00:00:00junk",
        "not-a-datetime",
        None,
        True,
        1,
        1.5,
        [],
        {},
    ],
)
def test_date_time_rejects_invalid_user_input(value):
    with pytest.raises(ValidationError, match="DateTime|datetime"):
        DateTimeConfig.model_validate({"next_run": value})


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-07 09:00:00.000001",
        datetime(2026, 10, 7, microsecond=1),  # noqa: DTZ001
    ],
)
def test_date_time_rejects_nonzero_microseconds(value):
    with pytest.raises((ValidationError, ValueError), match="microsecond"):
        DateTimeConfig.model_validate({"next_run": value})


def test_date_time_rejects_timezone_information():
    aware = datetime(2026, 10, 7, 9).replace(tzinfo=UTC)  # noqa: DTZ001

    with pytest.raises((ValidationError, ValueError), match="timezone"):
        DateTimeConfig.model_validate({"next_run": aware})


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((2026, 13, 1), "month"),
        ((2026, 1, 32), "day"),
        ((2026, 1, 1, 24), "hour"),
        ((2026, 1, 1, 0, 60), "minute"),
        ((2026, 1, 1, 0, 0, 60), "second"),
        ((2026, 1, 1, 0, 0, 0, 1), "microsecond"),
        ((2026, 1, 1, 0, 0, 0, 0, UTC), "timezone"),
    ],
)
def test_date_time_constructor_rejects_invalid_values(args, message):
    with pytest.raises(ValueError, match=message):
        DateTime(*args)


def test_date_time_rejects_invalid_default_value():
    class InvalidDefaultConfig(BaseModel):
        next_run: DateTime = DateTime.field(default="2026-10-07")

    with pytest.raises(ValidationError, match="Invalid datetime value"):
        InvalidDefaultConfig()


def test_date_time_rejects_invalid_default_factory_result():
    class InvalidFactoryConfig(BaseModel):
        next_run: DateTime = DateTime.field(default_factory=lambda: object())

    with pytest.raises(ValidationError, match="DateTime requires"):
        InvalidFactoryConfig()


def test_date_time_default_factory_is_validated_and_not_in_schema():
    class FactoryConfig(BaseModel):
        next_run: DateTime = DateTime.field(
            default_factory=lambda: "2026-10-07 01:02:03"
        )

    model = FactoryConfig()

    assert isinstance(model.next_run, DateTime)
    assert model.model_dump() == {"next_run": "2026-10-07 01:02:03"}
    assert "default" not in FactoryConfig.model_json_schema()["properties"]["next_run"]


def test_date_time_field_requires_exactly_one_default_form():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        DateTime.field()
    with pytest.raises(TypeError, match="cannot set both default and default_factory"):
        DateTime.field(
            default=DateTime(2026, 1, 1),
            default_factory=lambda: DateTime(2026, 1, 2),
        )


def test_date_time_composes_in_lists_optional_values_and_dictionaries():
    class CompositeConfig(BaseModel):
        dates: list[DateTime]
        optional: DateTime | None = None
        named: dict[str, DateTime]

    model = CompositeConfig.model_validate(
        {
            "dates": ["2026-01-01 00:00:00", DateTime(2026, 1, 2)],
            "named": {"start": "2026-01-03T00:00:00"},
        }
    )

    assert all(isinstance(item, DateTime) for item in model.dates)
    assert model.model_dump() == {
        "dates": ["2026-01-01 00:00:00", "2026-01-02 00:00:00"],
        "optional": None,
        "named": {"start": "2026-01-03 00:00:00"},
    }
