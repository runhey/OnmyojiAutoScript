import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import InputArea


class InputAreaConfig(BaseModel):
    bio: str = InputArea.str(
        default="Default\nbio",
        min_length=1,
        max_length=500,
        pattern=r"^[a-zA-Z \n]+$",
        description="简介",
        icon="document",
    )
    note: str = InputArea.secret_str(
        default="private\nnote",
        min_length=1,
        max_length=100,
        description="私密备注",
    )


def test_input_area_uses_native_string_types_and_plain_serialization():
    model = InputAreaConfig.model_validate(
        {"bio": "Hello\nworld", "note": "private\nnote"}
    )

    assert isinstance(model.bio, str)
    assert isinstance(model.note, str)
    assert model.model_dump() == {
        "bio": "Hello\nworld",
        "note": "private\nnote",
    }
    assert model.model_dump_json() == (
        '{"bio":"Hello\\nworld","note":"private\\nnote"}'
    )


def test_input_area_schema_uses_input_area_type_for_both_factories():
    properties = InputAreaConfig.model_json_schema()["properties"]

    assert properties["bio"]["type"] == "InputArea"
    assert properties["bio"]["input"] == "str"
    assert properties["bio"]["minLength"] == 1
    assert properties["bio"]["maxLength"] == 500
    assert properties["bio"]["pattern"] == r"^[a-zA-Z \n]+$"
    assert properties["bio"]["description"] == "简介"
    assert properties["bio"]["icon"] == "document"
    assert properties["note"]["type"] == "InputArea"
    assert properties["note"]["input"] == "secret_str"
    assert properties["note"]["minLength"] == 1
    assert properties["note"]["maxLength"] == 100
    assert properties["note"]["writeOnly"] is True


@pytest.mark.parametrize("factory", [InputArea.str, InputArea.secret_str])
def test_input_area_string_factories_require_a_default(factory):
    with pytest.raises(TypeError, match="requires default or default_factory"):
        factory()


@pytest.mark.parametrize("factory", [InputArea.str, InputArea.secret_str])
def test_input_area_string_factories_reject_both_default_forms(factory):
    with pytest.raises(TypeError, match="both default and default_factory"):
        factory(default="value", default_factory=lambda: "other")


def test_input_area_accepts_explicit_empty_default():
    class Model(BaseModel):
        value: str = InputArea.str(default="")
        secret: str = InputArea.secret_str(default="")

    assert Model().model_dump() == {"value": "", "secret": ""}


def test_input_area_preserves_multiple_newlines_and_blank_lines():
    class Model(BaseModel):
        value: str = InputArea.str(default="first\n\nthird")

    model = Model.model_validate({"value": "first\n\nthird"})
    assert model.value.splitlines() == ["first", "", "third"]
    assert model.model_dump() == {"value": "first\n\nthird"}
    assert model.model_dump_json() == '{"value":"first\\n\\nthird"}'


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bio", ""),
        ("bio", "123"),
        ("bio", "a" * 501),
        ("note", ""),
        ("note", "n" * 101),
        ("note", 123),
        ("note", None),
    ],
)
def test_input_area_rejects_invalid_values(field, value):
    data = InputAreaConfig().model_dump()
    data[field] = value

    with pytest.raises(ValidationError):
        InputAreaConfig.model_validate(data)


def test_input_area_default_factory_is_validated():
    class ValidModel(BaseModel):
        bio: str = InputArea.str(default_factory=lambda: "bio")
        note: str = InputArea.secret_str(default_factory=lambda: "note")

    assert ValidModel().model_dump() == {"bio": "bio", "note": "note"}
    properties = ValidModel.model_json_schema()["properties"]
    assert "default" not in properties["bio"]
    assert "default" not in properties["note"]

    class InvalidModel(BaseModel):
        note: str = InputArea.secret_str(default_factory=lambda: 123)

    with pytest.raises(ValidationError):
        InvalidModel()


def test_input_area_default_factory_is_called_for_each_instance():
    calls = 0

    def make_note():
        nonlocal calls
        calls += 1
        return f"note-{calls}"

    class Model(BaseModel):
        note: str = InputArea.secret_str(default_factory=make_note)

    assert Model().note == "note-1"
    assert Model().note == "note-2"


def test_input_area_metadata_and_extra_precedence():
    class Model(BaseModel):
        value: str = InputArea.secret_str(
            default="secret",
            title="备注",
            description="描述",
            hide=True,
            icon="note",
            depends="mode=advanced",
            readOnly=True,
            json_schema_extra={
                "type": "CustomArea",
                "input": "custom",
                "hide": False,
                "icon": "override",
                "depends": "mode=safe",
                "writeOnly": False,
                "readOnly": False,
                "x-ui": "textarea",
            },
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "CustomArea"
    assert schema["input"] == "custom"
    assert schema["title"] == "备注"
    assert schema["description"] == "描述"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "mode=safe"
    assert schema["writeOnly"] is False
    assert schema["readOnly"] is False
    assert schema["x-ui"] == "textarea"


def test_input_area_none_metadata_is_omitted():
    class Model(BaseModel):
        value: str = InputArea.str(
            default="",
            hide=None,
            description=None,
            icon=None,
            title=None,
            depends=None,
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "InputArea"
    assert "hide" not in schema
    assert "description" not in schema
    assert "icon" not in schema
    assert "depends" not in schema


def test_input_area_read_only_is_opt_in():
    class Model(BaseModel):
        normal: str = InputArea.str(default="normal")
        locked: str = InputArea.str(default="locked", readOnly=True)

    properties = Model.model_json_schema()["properties"]
    assert "readOnly" not in properties["normal"]
    assert properties["locked"]["readOnly"] is True


@pytest.mark.parametrize("factory", [InputArea.int, InputArea.float])
def test_input_area_rejects_numeric_factories(factory):
    with pytest.raises(TypeError, match="does not support"):
        factory(default=1)


def test_input_area_does_not_provide_numeric_schema_inputs():
    assert InputArea._type_name == "InputArea"
    assert not hasattr(InputArea, "_make_int")
    assert not hasattr(InputArea, "_make_float")


def test_input_area_supports_string_list_fields_without_an_inputareas_type():
    class Model(BaseModel):
        values: list[str] = InputArea.str(default=["one", "two"])

    model = Model.model_validate({"values": ["three", "four"]})
    assert model.values == ["three", "four"]
    schema = Model.model_json_schema()["properties"]["values"]
    assert schema["type"] == "InputArea"
    assert schema["input"] == "str"
