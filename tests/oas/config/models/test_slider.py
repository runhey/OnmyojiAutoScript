import math

import pytest
from pydantic import BaseModel, ValidationError

from oas.config.models.args import Slider


class SliderConfig(BaseModel):
    age: int = Slider.int(
        default=18,
        ge=0,
        le=150,
        step=1,
        description="年龄",
        icon="user",
    )
    score: float = Slider.float(
        default=50.0,
        gt=0.0,
        lt=100.0,
        step=0.5,
        description="分数",
    )


def test_slider_uses_native_numeric_values_and_serialization():
    model = SliderConfig.model_validate({"age": 20, "score": 75.5})

    assert isinstance(model.age, int)
    assert isinstance(model.score, float)
    assert model.model_dump() == {"age": 20, "score": 75.5}
    assert model.model_dump_json() == '{"age":20,"score":75.5}'


def test_slider_schema_uses_slider_type_input_and_numeric_constraints():
    properties = SliderConfig.model_json_schema()["properties"]

    assert properties["age"] == {
        "default": 18,
        "description": "年龄",
        "minimum": 0,
        "hide": False,
        "icon": "user",
        "input": "int",
        "maximum": 150,
        "multipleOf": 1,
        "title": "Age",
        "type": "Slider",
    }
    assert properties["score"]["type"] == "Slider"
    assert properties["score"]["input"] == "float"
    assert properties["score"]["exclusiveMinimum"] == 0.0
    assert properties["score"]["exclusiveMaximum"] == 100.0
    assert properties["score"]["multipleOf"] == 0.5


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (Slider.int, {"default": 0}),
        (Slider.float, {"default": 0.0}),
    ],
)
def test_slider_requires_step(factory, kwargs):
    with pytest.raises(TypeError, match="requires step"):
        factory(**kwargs)


@pytest.mark.parametrize("factory", [Slider.int, Slider.float])
@pytest.mark.parametrize("step", [0, -1])
def test_slider_rejects_non_positive_step(factory, step):
    with pytest.raises(ValueError, match="greater than zero"):
        factory(default=0, step=step)


def test_integer_slider_rejects_negative_float_step_as_wrong_type():
    with pytest.raises(TypeError, match="Slider.int step must be an int"):
        Slider.int(default=0, step=-0.5)


@pytest.mark.parametrize("step", [1.0, True, "1", 1.5, None])
def test_integer_slider_requires_an_exact_integer_step(step):
    with pytest.raises(TypeError, match="Slider.int step must be an int"):
        Slider.int(default=0, step=step)


@pytest.mark.parametrize("step", [True, False, "0.5", None, object()])
def test_float_slider_rejects_invalid_step_types(step):
    with pytest.raises(TypeError, match="Slider.float step must be an int or float"):
        Slider.float(default=0.0, step=step)


@pytest.mark.parametrize("step", [math.nan, math.inf, -math.inf])
def test_float_slider_rejects_non_finite_steps(step):
    with pytest.raises(ValueError, match="finite"):
        Slider.float(default=0.0, step=step)


def test_slider_rejects_explicit_multiple_of_to_keep_step_as_the_api():
    with pytest.raises(TypeError, match="uses step instead of multiple_of"):
        Slider.int(default=0, step=1, multiple_of=2)


@pytest.mark.parametrize("factory", [Slider.str, Slider.secret_str])
def test_slider_rejects_string_factories(factory):
    with pytest.raises(TypeError, match="does not support"):
        factory(default="", step=1)


def test_slider_requires_default_or_default_factory():
    with pytest.raises(TypeError, match="requires default or default_factory"):
        Slider.int(step=1)


def test_slider_rejects_default_and_default_factory_together():
    with pytest.raises(TypeError, match="both default and default_factory"):
        Slider.float(default=0.0, default_factory=lambda: 1.0, step=0.5)


def test_slider_accepts_zero_defaults_and_default_factory():
    class Model(BaseModel):
        integer: int = Slider.int(default=0, step=1)
        decimal: float = Slider.float(default_factory=lambda: 0.0, step=0.1)

    assert Model().model_dump() == {"integer": 0, "decimal": 0.0}
    assert "default" not in Model.model_json_schema()["properties"]["decimal"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", -1),
        ("age", 151),
        ("age", 1.5),
        ("score", 0.0),
        ("score", 100.0),
        ("score", 1.25),
        ("score", None),
        ("score", "invalid"),
    ],
)
def test_slider_rejects_invalid_values(field, value):
    data = SliderConfig().model_dump()
    data[field] = value

    with pytest.raises(ValidationError):
        SliderConfig.model_validate(data)


@pytest.mark.parametrize(
    ("factory", "annotation", "default", "step", "constraint"),
    [
        (Slider.int, int, None, 1, {}),
        (Slider.int, int, "bad", 1, {}),
        (Slider.int, int, 1, 1, {"ge": 2}),
        (Slider.float, float, None, 0.5, {}),
        (Slider.float, float, "bad", 0.5, {}),
        (Slider.float, float, 1.0, 0.5, {"le": 0.0}),
    ],
)
def test_slider_invalid_defaults_raise_when_model_is_instantiated(
    factory, annotation, default, step, constraint
):
    class Model(BaseModel):
        value: annotation = factory(default=default, step=step, **constraint)

    with pytest.raises(ValidationError):
        Model()


def test_slider_default_factory_result_is_validated():
    class InvalidModel(BaseModel):
        value: int = Slider.int(default_factory=lambda: "bad", step=1)

    with pytest.raises(ValidationError):
        InvalidModel()


def test_slider_metadata_and_json_schema_extra_precedence():
    class Model(BaseModel):
        value: int = Slider.int(
            default=0,
            step=1,
            title="数值",
            description="描述",
            hide=True,
            icon="slider",
            depends="mode=advanced",
            readOnly=True,
            json_schema_extra={
                "type": "CustomSlider",
                "input": "custom",
                "multipleOf": 5,
                "hide": False,
                "icon": "override",
                "depends": "mode=safe",
                "readOnly": False,
            },
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "CustomSlider"
    assert schema["input"] == "custom"
    assert schema["multipleOf"] == 5
    assert schema["title"] == "数值"
    assert schema["description"] == "描述"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "mode=safe"
    assert schema["readOnly"] is False


def test_slider_none_metadata_is_omitted():
    class Model(BaseModel):
        value: float = Slider.float(
            default=0.0,
            step=0.1,
            hide=None,
            description=None,
            icon=None,
            title=None,
            depends=None,
        )

    schema = Model.model_json_schema()["properties"]["value"]
    assert schema["type"] == "Slider"
    assert "hide" not in schema
    assert "description" not in schema
    assert "icon" not in schema
    assert "depends" not in schema


def test_slider_default_factory_is_not_in_schema():
    class Model(BaseModel):
        value: int = Slider.int(default_factory=lambda: 10, step=1)

    assert "default" not in Model.model_json_schema()["properties"]["value"]


def test_slider_rejects_list_defaults_and_values():
    class InvalidDefault(BaseModel):
        value: int = Slider.int(default=[1, 2], step=1)

    with pytest.raises(ValidationError):
        InvalidDefault()

    class Model(BaseModel):
        value: int = Slider.int(default=0, step=1)

    with pytest.raises(ValidationError):
        Model.model_validate({"value": [1, 2]})
