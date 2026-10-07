from datetime import datetime

import pytest
from cron_converter import Cron as CronConverter
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Cron


class CronConfig(BaseModel):
    schedule: Cron = Cron.field(
        default=Cron("0 9 * * MON-FRI"),
        description="执行计划",
        icon="calendar",
    )


def test_cron_preserves_string_api_and_serializes_canonical_expression():
    model = CronConfig.model_validate({"schedule": " 0 9 * * MON-FRI "})

    assert isinstance(model.schedule, Cron)
    assert isinstance(model.schedule, str)
    assert isinstance(model.schedule.cron_obj, CronConverter)
    assert str(model.schedule) == "0 9 * * 1-5"
    assert model.schedule.minute == "0"
    assert model.schedule.hour == "9"
    assert model.schedule.day_of_the_month == "*"
    assert model.schedule.month == "*"
    assert model.schedule.day_of_the_week == "1-5"
    assert model.model_dump() == {"schedule": "0 9 * * 1-5"}
    assert model.model_dump_json() == '{"schedule":"0 9 * * 1-5"}'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("*/5 * * * *", "*/5 * * * *"),
        ("0 0 * * 7", "0 0 * * 0"),
        ("0 0 * JAN MON", "0 0 * 1 1"),
        (Cron("15 8 * * 1-5"), "15 8 * * 1-5"),
    ],
)
def test_cron_accepts_supported_inputs(value, expected):
    model = CronConfig.model_validate({"schedule": value})

    assert isinstance(model.schedule, Cron)
    assert str(model.schedule) == expected


def test_cron_constructor_and_schedule_api_are_available():
    cron = Cron("15 8 * * 1-5")
    next_run = cron.next_after(datetime(2024, 1, 1, 7, 0))  # noqa: DTZ001

    assert next_run == datetime(2024, 1, 1, 8, 15)  # noqa: DTZ001
    assert (
        cron.schedule(start_date=datetime(2024, 1, 1, 7, 0))  # noqa: DTZ001
        .next()
        == next_run
    )
    assert cron.next_run.endswith(":00+00:00")


def test_cron_schema_uses_component_type_and_field_metadata():
    schema = CronConfig.model_json_schema()["properties"]["schedule"]

    assert schema == {
        "default": "0 9 * * 1-5",
        "description": "执行计划",
        "hide": False,
        "icon": "calendar",
        "title": "Schedule",
        "type": "Cron",
    }
    assert "input" not in schema
    assert "format" not in schema


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "* * * *",
        "* * * * * *",
        "@daily",
        "60 0 * * *",
        "0 24 * * *",
        "0 0 32 * *",
        "0 0 * 13 *",
        "*/0 * * * *",
        "0 0 * * ?",
        None,
        True,
        1,
        1.5,
        [],
        {},
    ],
)
def test_cron_rejects_invalid_user_input(value):
    with pytest.raises(ValidationError, match="Cron|cron"):
        CronConfig.model_validate({"schedule": value})


def test_cron_rejects_invalid_constructor_values():
    with pytest.raises(ValueError, match="Cron requires"):
        Cron(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must contain 5"):
        Cron("0 0 * *")
    with pytest.raises(ValueError, match="out of range"):
        Cron("60 0 * * *")


def test_cron_rejects_invalid_default_value():
    class InvalidDefaultConfig(BaseModel):
        schedule: Cron = Cron.field(default="0 0 * *")

    with pytest.raises(ValidationError, match="Cron expression must contain 5"):
        InvalidDefaultConfig()


def test_cron_rejects_invalid_default_factory_result():
    class InvalidFactoryConfig(BaseModel):
        schedule: Cron = Cron.field(default_factory=lambda: object())

    with pytest.raises(ValidationError, match="Cron requires"):
        InvalidFactoryConfig()


def test_cron_default_factory_is_validated_and_not_in_schema():
    class FactoryConfig(BaseModel):
        schedule: Cron = Cron.field(default_factory=lambda: "0 0 * * 7")

    model = FactoryConfig()

    assert isinstance(model.schedule, Cron)
    assert model.model_dump() == {"schedule": "0 0 * * 0"}
    assert "default" not in FactoryConfig.model_json_schema()["properties"]["schedule"]


def test_cron_field_requires_exactly_one_default_form():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        Cron.field()
    with pytest.raises(TypeError, match="cannot set both default and default_factory"):
        Cron.field(default=Cron("0 0 * * *"), default_factory=lambda: Cron("0 1 * * *"))


def test_cron_composes_in_lists_optional_values_and_dictionaries():
    class CompositeConfig(BaseModel):
        schedules: list[Cron]
        optional: Cron | None = None
        named: dict[str, Cron]

    model = CompositeConfig.model_validate(
        {
            "schedules": ["0 0 * * *", Cron("0 12 * * *")],
            "named": {"night": "0 22 * * *"},
        }
    )

    assert all(isinstance(item, Cron) for item in model.schedules)
    assert model.model_dump() == {
        "schedules": ["0 0 * * *", "0 12 * * *"],
        "optional": None,
        "named": {"night": "0 22 * * *"},
    }
