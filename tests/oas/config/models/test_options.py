import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from oas.config.models.args import OptionItem, Options


class Prioritys(Options):
    HIGH = OptionItem.str("high", title="高")
    LOW = OptionItem.str("low", icon="low")


class Levels(Options):
    ONE = OptionItem.int(1)
    TWO = OptionItem.int(2)


class Config(BaseModel):
    prioritys: Prioritys = Options.field(
        description="多个优先级",
        icon="tag",
        default=[Prioritys.HIGH],
    )


def test_options_is_enum_like_and_allows_empty_abstract_base():
    assert list(Prioritys) == [Prioritys.HIGH, Prioritys.LOW]
    assert Prioritys("high") is Prioritys.HIGH
    assert Prioritys["LOW"] is Prioritys.LOW
    assert Prioritys.HIGH in Prioritys
    assert "low" in Prioritys
    assert Options.__members__ == {}


def test_options_validates_raw_values_members_and_option_items():
    model = Config.model_validate(
        {
            "prioritys": [
                "high",
                Prioritys.LOW,
                Prioritys.HIGH.option_item,
            ]
        }
    )

    assert model.prioritys == [
        Prioritys.HIGH,
        Prioritys.LOW,
        Prioritys.HIGH,
    ]
    assert all(isinstance(member, Prioritys) for member in model.prioritys)


@pytest.mark.parametrize(
    "value",
    [
        "high",
        1,
        True,
        None,
        {},
        {"value": "high"},
        [None],
        [{}],
        [1],
        ["unknown"],
        ["high", "unknown"],
        [Levels.ONE],
        [OptionItem.int(1)],
        [["high"]],
    ],
)
def test_options_rejects_invalid_inputs(value):
    with pytest.raises(ValidationError):
        Config.model_validate({"prioritys": value})


@pytest.mark.parametrize("value", [None, [], {}, ["high"], Levels.ONE])
def test_options_constructor_rejects_non_member_values(value):
    with pytest.raises(ValueError, match="不是合法选项"):
        Prioritys(value)


def test_options_constructor_rejects_a_member_from_another_options_type():
    with pytest.raises(ValueError, match="不是合法选项"):
        Prioritys(Levels.ONE)


def test_options_name_lookup_rejects_unknown_member_name():
    with pytest.raises(KeyError):
        Prioritys["MISSING"]


def test_options_serializes_to_a_list_of_underlying_values():
    model = Config(prioritys=[Prioritys.HIGH, Prioritys.LOW])

    assert model.model_dump() == {"prioritys": ["high", "low"]}
    assert model.model_dump(mode="json") == {"prioritys": ["high", "low"]}
    assert model.model_dump_json() == '{"prioritys":["high","low"]}'
    assert TypeAdapter(Prioritys).dump_python(model.prioritys) == ["high", "low"]
    assert TypeAdapter(Prioritys).dump_json(model.prioritys) == b'["high","low"]'


def test_options_field_default_is_a_member_list_and_is_validated():
    assert Config().prioritys == [Prioritys.HIGH]

    with pytest.raises(TypeError, match="list of members"):
        Options.field(default=Prioritys.HIGH)
    with pytest.raises(TypeError, match="list of members"):
        Options.field(default=["high"])


def test_options_field_default_factory_is_validated():
    class ValidConfig(BaseModel):
        prioritys: Prioritys = Options.field(
            default_factory=lambda: [Prioritys.LOW]
        )

    assert ValidConfig().prioritys == [Prioritys.LOW]

    class InvalidConfig(BaseModel):
        prioritys: Prioritys = Options.field(default_factory=lambda: ["unknown"])

    with pytest.raises(ValidationError):
        InvalidConfig()

    class ScalarDefaultConfig(BaseModel):
        prioritys: Prioritys = Options.field(default_factory=lambda: Prioritys.HIGH)

    with pytest.raises(ValidationError):
        ScalarDefaultConfig()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default": "high"},
        {"default": (Prioritys.HIGH,)},
        {"default": [Prioritys.HIGH, "low"]},
        {"default": [Levels.ONE]},
        {"default": [OptionItem.int(1)]},
    ],
)
def test_options_field_rejects_malformed_defaults(kwargs):
    with pytest.raises(TypeError, match="list of members"):
        Prioritys.field(**kwargs)


def test_options_schema_is_array_with_option_items():
    schema = Config.model_json_schema()["properties"]["prioritys"]

    assert schema["type"] == "Options"
    assert schema["description"] == "多个优先级"
    assert schema["icon"] == "tag"
    assert schema["items"]["type"] == "Option"
    assert [branch["const"] for branch in schema["items"]["oneOf"]] == [
        "high",
        "low",
    ]
    assert schema["items"]["oneOf"][0]["title"] == "高"
    assert schema["items"]["oneOf"][1]["icon"] == "low"


def test_different_options_types_keep_independent_item_types_and_schema():
    adapter = TypeAdapter(Levels)
    assert adapter.validate_python(["1", 2]) == [Levels.ONE, Levels.TWO]
    schema = adapter.json_schema()
    assert schema["type"] == "Options"
    assert schema["items"]["type"] == "Option"
    assert all(branch["type"] == "integer" for branch in schema["items"]["oneOf"])


def test_options_rejects_inherited_members_and_empty_concrete_types():
    with pytest.raises(TypeError, match="cannot inherit Option members"):

        class ChildPrioritys(Prioritys):
            EXTRA = OptionItem.str("extra")

    with pytest.raises(TypeError, match="at least one OptionItem"):

        class EmptyPrioritys(Options):
            pass


def test_options_rejects_duplicate_member_values():
    with pytest.raises(ValueError, match="duplicate option value"):

        class DuplicatePrioritys(Options):
            FIRST = OptionItem.str("same")
            SECOND = OptionItem.str("same")


def test_options_rejects_mixed_member_value_types():
    with pytest.raises(TypeError, match="one core type"):

        class MixedOptions(Options):
            TEXT = OptionItem.str("text")
            NUMBER = OptionItem.int(1)


def test_abstract_options_type_cannot_validate_unknown_members():
    with pytest.raises(ValueError, match="不是合法选项"):
        TypeAdapter(Options).validate_python(["anything"])
