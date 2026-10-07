import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Switch


class SwitchConfig(BaseModel):
    enabled: bool = Switch.field(default=False, description="是否启用", icon="power")
    accepted: bool = Switch.field(default=True, title="接受条款")


def test_switch_uses_native_bool_values_and_serializes_as_bool():
    model = SwitchConfig.model_validate({"enabled": True, "accepted": False})

    assert isinstance(model.enabled, bool)
    assert isinstance(model.accepted, bool)
    assert model.model_dump() == {"enabled": True, "accepted": False}
    assert model.model_dump_json() == '{"enabled":true,"accepted":false}'


def test_switch_schema_uses_switch_type_and_field_metadata():
    properties = SwitchConfig.model_json_schema()["properties"]

    assert properties["enabled"] == {
        "default": False,
        "description": "是否启用",
        "hide": False,
        "icon": "power",
        "title": "Enabled",
        "type": "Switch",
    }
    assert properties["accepted"] == {
        "default": True,
        "hide": False,
        "title": "接受条款",
        "type": "Switch",
    }
    assert "input" not in properties["enabled"]


def test_switch_requires_a_default_or_default_factory():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        Switch.field(description="必填")


def test_switch_rejects_default_and_default_factory_together():
    with pytest.raises(TypeError, match="both default and default_factory"):
        Switch.field(default=False, default_factory=lambda: True)


def test_switch_accepts_explicit_false_and_none_defaults_at_factory_boundary():
    false_field = Switch.field(default=False)
    none_field = Switch.field(default=None)

    assert false_field.default is False
    assert none_field.default is None

    class OptionalSwitch(BaseModel):
        value: bool | None = none_field

    assert OptionalSwitch().value is None


@pytest.mark.parametrize("value", [None, "not-bool", [], {}, 1.5])
def test_switch_rejects_invalid_values(value):
    class Model(BaseModel):
        value: bool = Switch.field(default=False)

    with pytest.raises(ValidationError):
        Model.model_validate({"value": value})


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (False, False), (1, True), (0, False), ("true", True), ("false", False)],
)
def test_switch_keeps_pydantic_bool_conversion(value, expected):
    class Model(BaseModel):
        value: bool = Switch.field(default=False)

    assert Model.model_validate({"value": value}).value is expected


def test_switch_default_factory_is_validated_and_not_written_to_schema():
    class Model(BaseModel):
        enabled: bool = Switch.field(default_factory=lambda: True)

    assert Model().enabled is True
    schema = Model.model_json_schema()["properties"]["enabled"]
    assert schema["type"] == "Switch"
    assert "default" not in schema

    class InvalidModel(BaseModel):
        enabled: bool = Switch.field(default_factory=lambda: "invalid")

    with pytest.raises(ValidationError):
        InvalidModel()


def test_switch_default_factory_runs_for_each_model_instance():
    calls = 0

    def make_value():
        nonlocal calls
        calls += 1
        return calls % 2 == 1

    class Model(BaseModel):
        enabled: bool = Switch.field(default_factory=make_value)

    assert Model().enabled is True
    assert Model().enabled is False


def test_switch_metadata_uses_shared_fields_and_extra_precedence():
    class Model(BaseModel):
        enabled: bool = Switch.field(
            default=False,
            title="开关",
            description="默认描述",
            hide=True,
            icon="default",
            alias="reserved",
            depends="mode=advanced",
            json_schema_extra={
                "type": "CustomSwitch",
                "hide": False,
                "icon": "override",
                "depends": "mode=safe",
                "x-ui": "checkbox",
            },
        )

    schema = Model.model_json_schema()["properties"]["enabled"]
    assert schema["type"] == "CustomSwitch"
    assert schema["title"] == "开关"
    assert schema["description"] == "默认描述"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "mode=safe"
    assert schema["x-ui"] == "checkbox"
    assert "alias" not in schema
    assert "input" not in schema


def test_switch_none_metadata_is_omitted():
    class Model(BaseModel):
        value: bool = Switch.field(
            default=False,
            hide=None,
            description=None,
            icon=None,
            title=None,
            depends=None,
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "Switch"
    assert "hide" not in schema
    assert "description" not in schema
    assert "icon" not in schema
    assert "depends" not in schema
    # Pydantic synthesizes a title from the field name when title is omitted.
    assert schema["title"] == "Value"


def test_switch_json_schema_extra_must_be_a_mapping():
    with pytest.raises(TypeError, match="json_schema_extra must be a dictionary"):
        Switch.field(default=False, json_schema_extra=[("type", "Switch")])


def test_switch_read_only_can_be_passed_as_extra_metadata():
    class Model(BaseModel):
        enabled: bool = Switch.field(
            default=False,
            json_schema_extra={"readOnly": True},
        )

    assert Model.model_json_schema()["properties"]["enabled"]["readOnly"] is True


def test_switch_supports_boolean_lists_as_plain_pydantic_fields():
    class Model(BaseModel):
        values: list[bool] = Switch.field(default=[True, False])

    model = Model.model_validate({"values": [0, 1]})
    assert model.values == [False, True]
    assert Model.model_json_schema()["properties"]["values"]["type"] == "Switch"
