import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Input


class InputConfig(BaseModel):
    age: int = Input.int(
        ge=0,
        le=150,
        description="年龄",
        icon="user",
        default=18,
    )
    score: float = Input.float(
        gt=0,
        le=100,
        multiple_of=0.5,
        default=99.5,
    )
    name: str = Input.str(
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z]+$",
        default="Alice",
    )
    password: str = Input.secret_str(min_length=8, default="password")


def test_input_uses_native_python_types_and_serializes_plain_values():
    config = InputConfig()

    assert isinstance(config.age, int)
    assert isinstance(config.score, float)
    assert isinstance(config.name, str)
    assert isinstance(config.password, str)
    assert config.model_dump() == {
        "age": 18,
        "score": 99.5,
        "name": "Alice",
        "password": "password",
    }
    assert config.model_dump_json() == (
        '{"age":18,"score":99.5,"name":"Alice","password":"password"}'
    )


def test_input_schema_uses_custom_component_type_and_native_constraints():
    schema = InputConfig.model_json_schema()["properties"]

    assert schema["age"] == {
        "default": 18,
        "description": "年龄",
        "hide": False,
        "icon": "user",
        "input": "int",
        "maximum": 150,
        "minimum": 0,
        "title": "Age",
        "type": "Input",
    }
    assert schema["score"]["type"] == "Input"
    assert schema["score"]["input"] == "float"
    assert schema["score"]["exclusiveMinimum"] == 0
    assert schema["score"]["maximum"] == 100
    assert schema["score"]["multipleOf"] == 0.5
    assert schema["name"]["input"] == "str"
    assert schema["name"]["minLength"] == 1
    assert schema["name"]["maxLength"] == 50
    assert schema["name"]["pattern"] == r"^[a-zA-Z]+$"
    assert schema["password"]["type"] == "Input"
    assert schema["password"]["input"] == "secret_str"
    assert schema["password"]["writeOnly"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", -1),
        ("age", 151),
        ("score", 0),
        ("score", 100.5),
        ("score", 99.25),
        ("name", ""),
        ("name", "Alice123"),
        ("name", "a" * 51),
        ("password", "short"),
    ],
)
def test_input_constraints_raise_validation_error(field, value):
    data = InputConfig().model_dump()
    data[field] = value

    with pytest.raises(ValidationError):
        InputConfig.model_validate(data)


def test_input_default_factory_is_validated_and_not_in_schema():
    class FactoryConfig(BaseModel):
        age: int = Input.int(default_factory=lambda: 20, ge=0)
        password: str = Input.secret_str(default_factory=lambda: "password")

    assert FactoryConfig().model_dump() == {"age": 20, "password": "password"}
    schema = FactoryConfig.model_json_schema()["properties"]
    assert "default" not in schema["age"]
    assert "default" not in schema["password"]

    class InvalidFactoryConfig(BaseModel):
        age: int = Input.int(default_factory=lambda: -1, ge=0)

    with pytest.raises(ValidationError):
        InvalidFactoryConfig()


def test_input_rejects_default_and_default_factory_together():
    with pytest.raises(TypeError, match="both default and default_factory"):
        Input.int(default=1, default_factory=lambda: 2)


def test_input_field_metadata_and_json_schema_extra_precedence():
    class MetadataConfig(BaseModel):
        value: int = Input.int(
            default=0,
            title="数值",
            description="默认描述",
            hide=True,
            icon="number",
            alias="reserved_alias",
            depends="mode=advanced",
            readOnly=True,
            json_schema_extra={
                "hide": False,
                "icon": "override",
                "depends": "other=enabled",
                "readOnly": False,
                "x-ui": "input",
            },
        )

    schema = MetadataConfig.model_json_schema()["properties"]["value"]
    assert schema["type"] == "Input"
    assert schema["input"] == "int"
    assert schema["title"] == "数值"
    assert schema["description"] == "默认描述"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "other=enabled"
    assert schema["readOnly"] is False
    assert schema["x-ui"] == "input"
    assert "alias" not in schema


def test_input_read_only_is_opt_in_and_secret_is_write_only():
    class ReadOnlyConfig(BaseModel):
        editable: str = Input.str(default="value")
        locked: str = Input.str(default="value", readOnly=True)
        secret: str = Input.secret_str(default="value")

    properties = ReadOnlyConfig.model_json_schema()["properties"]
    assert "readOnly" not in properties["editable"]
    assert properties["locked"]["readOnly"] is True
    assert properties["secret"]["writeOnly"] is True


def test_input_rejects_non_mapping_json_schema_extra():
    with pytest.raises(TypeError, match="json_schema_extra must be a dictionary"):
        Input.str(default="", json_schema_extra=[("input", "str")])


@pytest.mark.parametrize(
    "factory",
    [Input.int, Input.float, Input.str, Input.secret_str],
)
def test_input_requires_default_or_default_factory(factory):
    with pytest.raises(TypeError, match="requires default or default_factory"):
        factory()


def test_input_accepts_explicit_empty_defaults():
    class EmptyConfig(BaseModel):
        text: str = Input.str(default="")
        number: int | None = Input.int(default=None)

    assert EmptyConfig().model_dump() == {"text": "", "number": None}


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "value"),
    [
        (Input.int, int, 0, 12),
        (Input.float, float, 0.0, 12.5),
        (Input.str, str, "", "hello"),
        (Input.secret_str, str, "", "secret-value"),
    ],
)
def test_each_input_factory_accepts_valid_runtime_values(
    factory, annotation, default, value
):
    class Model(BaseModel):
        value: annotation = factory(default=default)

    model = Model.model_validate({"value": value})
    assert model.value == value


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "value"),
    [
        (Input.int, int, 0, None),
        (Input.int, int, 0, 1.5),
        (Input.int, int, 0, []),
        (Input.int, int, 0, {}),
        (Input.float, float, 0.0, None),
        (Input.float, float, 0.0, []),
        (Input.float, float, 0.0, {}),
        (Input.str, str, "", None),
        (Input.str, str, "", 123),
        (Input.str, str, "", True),
        (Input.str, str, "", []),
        (Input.secret_str, str, "", None),
        (Input.secret_str, str, "", 123),
        (Input.secret_str, str, "", {}),
    ],
)
def test_each_input_factory_rejects_invalid_runtime_values(
    factory, annotation, default, value
):
    class Model(BaseModel):
        value: annotation = factory(default=default)

    with pytest.raises(ValidationError):
        Model.model_validate({"value": value})


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "constraint", "valid", "invalid"),
    [
        (Input.int, int, 1, {"gt": 0}, 1, 0),
        (Input.int, int, 1, {"ge": 1}, 1, 0),
        (Input.int, int, 1, {"lt": 2}, 1, 2),
        (Input.int, int, 1, {"le": 1}, 1, 2),
        (Input.float, float, 1.5, {"gt": 1.0}, 1.5, 1.0),
        (Input.float, float, 1.5, {"ge": 1.5}, 1.5, 1.4),
        (Input.float, float, 1.5, {"lt": 2.0}, 1.5, 2.0),
        (Input.float, float, 1.5, {"le": 1.5}, 1.5, 1.6),
        (Input.int, int, 2, {"multiple_of": 2}, 4, 3),
        (Input.float, float, 1.5, {"multiple_of": 0.5}, 2.0, 1.25),
    ],
)
def test_numeric_constraints_accept_boundary_and_reject_invalid_values(
    factory, annotation, default, constraint, valid, invalid
):
    class Model(BaseModel):
        value: annotation = factory(default=default, **constraint)

    assert Model.model_validate({"value": valid}).value == valid
    with pytest.raises(ValidationError):
        Model.model_validate({"value": invalid})


def test_numeric_schema_exports_all_constraint_names():
    class Model(BaseModel):
        integer: int = Input.int(
            default=2,
            gt=0,
            ge=1,
            lt=10,
            le=9,
            multiple_of=2,
        )
        decimal: float = Input.float(
            default=2.5,
            gt=0.0,
            ge=1.0,
            lt=10.0,
            le=9.0,
            multiple_of=0.5,
        )

    properties = Model.model_json_schema()["properties"]
    assert properties["integer"] == {
        "default": 2,
        "exclusiveMinimum": 0,
        "minimum": 1,
        "exclusiveMaximum": 10,
        "maximum": 9,
        "multipleOf": 2,
        "hide": False,
        "input": "int",
        "title": "Integer",
        "type": "Input",
    }
    assert properties["decimal"]["exclusiveMinimum"] == 0.0
    assert properties["decimal"]["minimum"] == 1.0
    assert properties["decimal"]["exclusiveMaximum"] == 10.0
    assert properties["decimal"]["maximum"] == 9.0
    assert properties["decimal"]["multipleOf"] == 0.5


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "constraint", "valid", "invalid"),
    [
        (Input.str, str, "a", {"min_length": 1}, "a", ""),
        (Input.str, str, "a", {"max_length": 2}, "ab", "abc"),
        (Input.str, str, "abc", {"pattern": r"^[a-z]+$"}, "abc", "ABC"),
        (Input.secret_str, str, "password", {"min_length": 8}, "password", "short"),
        (
            Input.secret_str,
            str,
            "abc",
            {"max_length": 3, "pattern": r"^[a-z]+$"},
            "abc",
            "ABCD",
        ),
    ],
)
def test_string_constraints_accept_and_reject_values(
    factory, annotation, default, constraint, valid, invalid
):
    class Model(BaseModel):
        value: annotation = factory(default=default, **constraint)

    assert Model.model_validate({"value": valid}).value == valid
    with pytest.raises(ValidationError):
        Model.model_validate({"value": invalid})


def test_string_schema_exports_all_constraint_names_for_secret_string():
    class Model(BaseModel):
        value: str = Input.secret_str(
            default="password",
            min_length=8,
            max_length=32,
            pattern=r"^[a-z]+$",
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "Input"
    assert schema["input"] == "secret_str"
    assert schema["minLength"] == 8
    assert schema["maxLength"] == 32
    assert schema["pattern"] == r"^[a-z]+$"
    assert schema["writeOnly"] is True


@pytest.mark.parametrize(
    ("factory", "annotation", "factory_value"),
    [
        (Input.int, int, "wrong"),
        (Input.int, int, 1.5),
        (Input.float, float, None),
        (Input.float, float, "wrong"),
        (Input.str, str, 123),
        (Input.str, str, None),
        (Input.secret_str, str, 123),
        (Input.secret_str, str, None),
    ],
)
def test_each_input_default_factory_result_is_validated(
    factory, annotation, factory_value
):
    class Model(BaseModel):
        value: annotation = factory(default_factory=lambda: factory_value)

    with pytest.raises(ValidationError):
        Model()


@pytest.mark.parametrize("factory", [Input.int, Input.float, Input.str, Input.secret_str])
def test_each_input_factory_rejects_both_default_forms(factory):
    with pytest.raises(TypeError, match="both default and default_factory"):
        factory(default=0, default_factory=lambda: 1)


@pytest.mark.parametrize("factory", [Input.int, Input.float, Input.str, Input.secret_str])
def test_each_input_factory_rejects_missing_default(factory):
    with pytest.raises(TypeError, match="requires default or default_factory"):
        factory()


def test_input_default_values_are_validated_by_pydantic():
    class InvalidInteger(BaseModel):
        value: int = Input.int(default=None)

    class InvalidString(BaseModel):
        value: str = Input.str(default=123)

    with pytest.raises(ValidationError):
        InvalidInteger()
    with pytest.raises(ValidationError):
        InvalidString()


def test_input_factory_accepts_zero_false_and_empty_string_defaults():
    class Model(BaseModel):
        integer: int = Input.int(default=0)
        decimal: float = Input.float(default=0.0)
        text: str = Input.str(default="")
        secret: str = Input.secret_str(default="")

    assert Model().model_dump() == {
        "integer": 0,
        "decimal": 0.0,
        "text": "",
        "secret": "",
    }


def test_input_default_factory_is_called_per_model_instance():
    calls = 0

    def make_value():
        nonlocal calls
        calls += 1
        return calls

    class Model(BaseModel):
        value: int = Input.int(default_factory=make_value)

    first = Model()
    second = Model()
    assert first.value == 1
    assert second.value == 2


def test_input_default_factory_is_not_written_to_schema():
    class Model(BaseModel):
        integer: int = Input.int(default_factory=lambda: 1)
        text: str = Input.str(default_factory=lambda: "text")

    properties = Model.model_json_schema()["properties"]
    assert "default" not in properties["integer"]
    assert "default" not in properties["text"]
    assert "required" not in Model.model_json_schema()


def test_input_none_metadata_is_omitted_when_explicitly_disabled():
    class Model(BaseModel):
        value: str = Input.str(
            default="",
            hide=None,
            description=None,
            icon=None,
            title=None,
            depends=None,
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert "hide" not in schema
    assert "description" not in schema
    assert "icon" not in schema
    assert "depends" not in schema
    # Pydantic may still synthesize a title from the Python field name.
    assert schema["type"] == "Input"


def test_input_json_schema_extra_can_override_generated_component_metadata():
    class Model(BaseModel):
        value: str = Input.secret_str(
            default="secret",
            json_schema_extra={
                "type": "CustomInput",
                "input": "custom",
                "writeOnly": False,
                "hide": True,
                "x-extra": "value",
            },
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "CustomInput"
    assert schema["input"] == "custom"
    assert schema["writeOnly"] is False
    assert schema["hide"] is True
    assert schema["x-extra"] == "value"


def test_input_read_only_can_be_true_or_false_without_being_added_by_default():
    class Model(BaseModel):
        normal: str = Input.str(default="normal")
        locked: str = Input.str(default="locked", readOnly=True)
        writable: str = Input.str(default="writable", readOnly=False)

    properties = Model.model_json_schema()["properties"]
    assert "readOnly" not in properties["normal"]
    assert properties["locked"]["readOnly"] is True
    assert properties["writable"]["readOnly"] is False


def test_secret_string_serializes_plaintext_even_when_write_only():
    class Model(BaseModel):
        password: str = Input.secret_str(default="plain-password")

    model = Model()
    assert model.password == "plain-password"
    assert model.model_dump() == {"password": "plain-password"}
    assert model.model_dump_json() == '{"password":"plain-password"}'


def test_input_alias_is_reserved_and_does_not_change_model_input_name():
    class Model(BaseModel):
        value: int = Input.int(default=1, alias="other_name")

    assert Model.model_validate({"value": 2}).value == 2
    assert "other_name" not in Model.model_json_schema()["properties"]


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "constraint"),
    [
        (Input.int, int, 1, {"gt": 2}),
        (Input.int, int, 1, {"ge": 2}),
        (Input.float, float, 1.0, {"lt": 1.0}),
        (Input.float, float, 1.0, {"le": 0.0}),
        (Input.str, str, "", {"min_length": 1}),
        (Input.str, str, "long", {"max_length": 2}),
        (Input.str, str, "ABC", {"pattern": r"^[a-z]+$"}),
    ],
)
def test_invalid_defaults_raise_when_model_is_instantiated(
    factory, annotation, default, constraint
):
    class Model(BaseModel):
        value: annotation = factory(default=default, **constraint)

    with pytest.raises(ValidationError):
        Model()
