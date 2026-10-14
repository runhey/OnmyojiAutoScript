import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Button


class ButtonConfig(BaseModel):
    selected: bool = Button.field(
        default=False,
        description="是否选中",
        icon="check",
    )
    active: bool = Button.field(
        default=True,
        title="是否激活",
    )


def test_button_uses_native_bool_values_and_serializes_as_bool():
    model = ButtonConfig.model_validate({"selected": True, "active": False})

    assert isinstance(model.selected, bool)
    assert isinstance(model.active, bool)
    assert model.model_dump() == {"selected": True, "active": False}
    assert model.model_dump_json() == '{"selected":true,"active":false}'


def test_button_schema_uses_button_type_and_field_metadata():
    properties = ButtonConfig.model_json_schema()["properties"]

    assert properties["selected"] == {
        "default": False,
        "description": "是否选中",
        "hide": False,
        "icon": "check",
        "title": "Selected",
        "type": "Button",
    }
    assert properties["active"] == {
        "default": True,
        "hide": False,
        "title": "是否激活",
        "type": "Button",
    }


def test_button_requires_a_default_or_default_factory():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        Button.field(description="按钮")


def test_button_rejects_default_and_default_factory_together():
    with pytest.raises(TypeError, match="both default and default_factory"):
        Button.field(default=False, default_factory=lambda: True)


def test_button_accepts_explicit_false_and_none_defaults_at_factory_boundary():
    false_field = Button.field(default=False)
    none_field = Button.field(default=None)

    assert false_field.default is False
    assert none_field.default is None

    class OptionalButton(BaseModel):
        value: bool | None = none_field

    assert OptionalButton().value is None


@pytest.mark.parametrize("value", [None, "not-bool", [], {}, 1.5])
def test_button_rejects_invalid_values(value):
    class Model(BaseModel):
        value: bool = Button.field(default=False)

    with pytest.raises(ValidationError):
        Model.model_validate({"value": value})


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (False, False), (1, True), (0, False), ("true", True), ("false", False)],
)
def test_button_keeps_pydantic_bool_conversion(value, expected):
    class Model(BaseModel):
        value: bool = Button.field(default=False)

    assert Model.model_validate({"value": value}).value is expected


def test_button_default_factory_is_validated_and_not_written_to_schema():
    class Model(BaseModel):
        selected: bool = Button.field(default_factory=lambda: True)

    assert Model().selected is True
    schema = Model.model_json_schema()["properties"]["selected"]
    assert schema["type"] == "Button"
    assert "default" not in schema

    class InvalidModel(BaseModel):
        selected: bool = Button.field(default_factory=lambda: "invalid")

    with pytest.raises(ValidationError):
        InvalidModel()


def test_button_default_factory_runs_for_each_model_instance():
    calls = 0

    def make_value():
        nonlocal calls
        calls += 1
        return calls % 2 == 1

    class Model(BaseModel):
        selected: bool = Button.field(default_factory=make_value)

    assert Model().selected is True
    assert Model().selected is False


def test_button_metadata_uses_shared_fields_and_extra_precedence():
    class Model(BaseModel):
        selected: bool = Button.field(
            default=False,
            title="按钮",
            description="默认描述",
            hide=True,
            icon="default",
            alias="reserved",
            depends="mode=advanced",
            json_schema_extra={
                "type": "CustomButton",
                "hide": False,
                "icon": "override",
                "depends": "mode=safe",
                "x-ui": "button",
            },
        )

    schema = Model.model_json_schema()["properties"]["selected"]
    assert schema["type"] == "CustomButton"
    assert schema["title"] == "按钮"
    assert schema["description"] == "默认描述"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "mode=safe"
    assert schema["x-ui"] == "button"
    assert "alias" not in schema


def test_button_none_metadata_is_omitted():
    class Model(BaseModel):
        value: bool = Button.field(
            default=False,
            hide=None,
            description=None,
            icon=None,
            title=None,
            depends=None,
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "Button"
    assert "hide" not in schema
    assert "description" not in schema
    assert "icon" not in schema
    assert "depends" not in schema
    assert schema["title"] == "Value"


def test_button_json_schema_extra_must_be_a_mapping():
    with pytest.raises(TypeError, match="json_schema_extra must be a dictionary"):
        Button.field(default=False, json_schema_extra=[("type", "Button")])


def test_button_read_only_can_be_passed_as_extra_metadata():
    class Model(BaseModel):
        selected: bool = Button.field(
            default=False,
            json_schema_extra={"readOnly": True},
        )

    assert Model.model_json_schema()["properties"]["selected"]["readOnly"] is True


def test_button_supports_boolean_lists_as_plain_pydantic_fields():
    class Model(BaseModel):
        values: list[bool] = Button.field(default=[True, False])

    model = Model.model_validate({"values": [0, 1]})
    assert model.values == [False, True]
    assert Model.model_json_schema()["properties"]["values"]["type"] == "Button"
