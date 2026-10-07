from typing import Optional

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from oas.config.models.args import Option, OptionItem


class TextOption(Option):
    FAST = OptionItem.str("fast", title="快速", description="快速模式")
    SAFE = OptionItem.str("safe")


class AnotherTextOption(Option):
    FAST = OptionItem.str("fast")


class IntegerOption(Option):
    ONE = OptionItem.int(1)
    TWO = OptionItem.int(2)


class FloatOption(Option):
    HALF = OptionItem.float(0.5)
    ONE = OptionItem.float(1.0)


class BooleanOption(Option):
    ENABLED = OptionItem.bool(True)
    DISABLED = OptionItem.bool(False)


class Config(BaseModel):
    mode: TextOption


def test_option_behaves_like_an_enum():
    assert TextOption.FAST.name == "FAST"
    assert TextOption.FAST.value == "fast"
    assert TextOption.FAST.option_item.value == "fast"
    assert TextOption("fast") is TextOption.FAST
    assert TextOption(TextOption.FAST) is TextOption.FAST
    assert TextOption["FAST"] is TextOption.FAST
    assert list(TextOption) == [TextOption.FAST, TextOption.SAFE]
    assert list(reversed(TextOption)) == [TextOption.SAFE, TextOption.FAST]
    assert len(TextOption) == 2
    assert TextOption.FAST in TextOption
    assert "fast" in TextOption
    assert "unknown" not in TextOption
    assert repr(TextOption.FAST) == "TextOption.FAST"
    assert str(TextOption.FAST) == "fast"


def test_option_members_compare_by_option_type_and_value():
    assert TextOption.FAST == "fast"
    assert TextOption.FAST == TextOption("fast")
    assert TextOption.FAST != TextOption.SAFE
    assert TextOption.FAST != AnotherTextOption.FAST
    assert hash(TextOption.FAST) == hash("fast")


def test_option_lookup_errors_are_enum_like():
    with pytest.raises(ValueError, match="不是合法选项"):
        TextOption("unknown")
    with pytest.raises(KeyError):
        TextOption["UNKNOWN"]
    assert [] not in TextOption


def test_option_members_mapping_is_read_only():
    with pytest.raises(TypeError):
        TextOption.__members__["OTHER"] = TextOption.FAST


def test_option_rejects_duplicate_values():
    with pytest.raises(ValueError, match="duplicate option value"):

        class DuplicateOption(Option):
            FIRST = OptionItem.str("same")
            SECOND = OptionItem.str("same")


def test_option_rejects_mixed_core_types():
    with pytest.raises(TypeError, match="one core type"):

        class MixedOption(Option):
            TEXT = OptionItem.str("text")
            NUMBER = OptionItem.int(1)


def test_option_rejects_empty_subclass():
    with pytest.raises(TypeError, match="at least one OptionItem"):

        class EmptyOption(Option):
            pass


def test_option_rejects_inherited_members():
    with pytest.raises(TypeError, match="cannot inherit Option members"):

        class ChildOption(TextOption):
            EXTRA = OptionItem.str("extra")


def test_non_optionitem_attributes_are_not_members():
    class WithAttributeOption(Option):
        VALUE = OptionItem.str("value")
        LABEL = "not a member"

        def label(self):
            return self.name

    assert list(WithAttributeOption) == [WithAttributeOption.VALUE]
    assert WithAttributeOption.LABEL == "not a member"


def test_pydantic_accepts_raw_value_member_and_option_item():
    assert Config.model_validate({"mode": "fast"}).mode is TextOption.FAST
    assert Config.model_validate({"mode": TextOption.FAST}).mode is TextOption.FAST
    assert Config.model_validate({"mode": TextOption.FAST.option_item}).mode is TextOption.FAST


@pytest.mark.parametrize("value", ["unknown", None, "", [], {}, AnotherTextOption.FAST])
def test_pydantic_rejects_invalid_option_inputs(value):
    with pytest.raises(ValidationError):
        Config.model_validate({"mode": value})


@pytest.mark.parametrize(
    ("model_type", "value", "member"),
    [
        (IntegerOption, "1", IntegerOption.ONE),
        (FloatOption, 1, FloatOption.ONE),
        (BooleanOption, 1, BooleanOption.ENABLED),
        (BooleanOption, "true", BooleanOption.ENABLED),
    ],
)
def test_pydantic_keeps_default_loose_type_conversion(model_type, value, member):
    class ConfigModel(BaseModel):
        value: model_type

    assert ConfigModel.model_validate({"value": value}).value is member


def test_model_dump_always_serializes_underlying_values():
    config = Config(mode=TextOption.FAST)

    assert config.model_dump() == {"mode": "fast"}
    assert config.model_dump(mode="json") == {"mode": "fast"}
    assert config.model_dump_json() == '{"mode":"fast"}'
    assert TypeAdapter(TextOption).dump_python(TextOption.FAST) == "fast"
    assert TypeAdapter(TextOption).dump_json(TextOption.FAST) == b'"fast"'


def test_option_serializes_in_lists_and_dictionaries():
    class Container(BaseModel):
        modes: list[TextOption]
        named: dict[str, TextOption]

    container = Container(
        modes=[TextOption.FAST, TextOption.SAFE],
        named={"default": TextOption.FAST},
    )

    assert container.model_dump() == {
        "modes": ["fast", "safe"],
        "named": {"default": "fast"},
    }


def test_optional_option_serializes_none():
    class OptionalConfig(BaseModel):
        mode: Optional[TextOption] = None

    assert OptionalConfig().model_dump() == {"mode": None}


def test_option_field_exports_root_metadata_and_type():
    class ConfigModel(BaseModel):
        mode: TextOption = Option.field(
            title="模式",
            description="选择模式",
            hide=True,
            icon="mode",
            depends="kind:advanced",
            alias="reserved_alias",
            json_schema_extra={
                "hide": False,
                "icon": "override",
                "depends": "other:value",
                "alias": "schema_alias",
                "x-ui": "select",
            },
        )

    schema = ConfigModel.model_json_schema()["properties"]["mode"]

    assert schema["type"] == "Option"
    assert schema["title"] == "模式"
    assert schema["description"] == "选择模式"
    assert schema["hide"] is False
    assert schema["icon"] == "override"
    assert schema["depends"] == "other:value"
    assert schema["alias"] == "schema_alias"
    assert schema["x-ui"] == "select"


def test_option_field_alias_is_reserved_and_has_no_effect():
    class ConfigModel(BaseModel):
        mode: TextOption = Option.field(alias="mode_alias")

    schema = ConfigModel.model_json_schema()["properties"]["mode"]

    assert "alias" not in schema
    assert ConfigModel.model_validate({"mode": "fast"}).mode is TextOption.FAST


def test_option_field_default_requires_an_option_member():
    class ConfigModel(BaseModel):
        mode: TextOption = Option.field(default=TextOption.FAST)

    assert ConfigModel().mode is TextOption.FAST

    with pytest.raises(TypeError, match="must be an Option member"):
        Option.field(default="fast")


def test_option_field_default_factory_is_validated_by_pydantic():
    class ValidConfig(BaseModel):
        mode: TextOption = Option.field(default_factory=lambda: TextOption.SAFE)

    assert ValidConfig().mode is TextOption.SAFE

    class InvalidConfig(BaseModel):
        mode: TextOption = Option.field(default_factory=lambda: "unknown")

    with pytest.raises(ValidationError):
        InvalidConfig()


def test_option_field_rejects_default_and_default_factory_together():
    with pytest.raises(TypeError, match="both default and default_factory"):
        Option.field(
            default=TextOption.FAST,
            default_factory=lambda: TextOption.SAFE,
        )


def test_option_field_rejects_non_mapping_json_schema_extra():
    with pytest.raises(TypeError, match="json_schema_extra must be a dictionary"):
        Option.field(json_schema_extra=[("hide", True)])


def test_option_schema_has_const_default_and_independent_branches():
    schema = Config.model_json_schema()["properties"]["mode"]
    branches = schema["oneOf"]

    assert schema["type"] == "Option"
    assert [branch["const"] for branch in branches] == ["fast", "safe"]
    assert [branch["default"] for branch in branches] == ["fast", "safe"]
    assert branches[0]["title"] == "快速"
    assert branches[0]["description"] == "快速模式"
    assert branches[1]["title"] == "$text_option.safe.title"
    assert branches[1]["description"] == "$text_option.safe.description"
    assert all(branch["type"] == "string" for branch in branches)
    assert all(branch["readOnly"] is True for branch in branches)


@pytest.mark.parametrize(
    ("option_type", "json_type"),
    [
        (TextOption, "string"),
        (IntegerOption, "integer"),
        (FloatOption, "number"),
        (BooleanOption, "boolean"),
    ],
)
def test_option_schema_branch_type_matches_option_value_type(option_type, json_type):
    schema = TypeAdapter(option_type).json_schema()

    assert schema["type"] == "Option"
    assert all(branch["type"] == json_type for branch in schema["oneOf"])


def test_multiple_option_types_do_not_share_schema_metadata():
    text_schema = TypeAdapter(TextOption).json_schema()
    integer_schema = TypeAdapter(IntegerOption).json_schema()

    assert text_schema["oneOf"][0]["type"] == "string"
    assert integer_schema["oneOf"][0]["type"] == "integer"
    assert text_schema["oneOf"][0]["const"] == "fast"
    assert integer_schema["oneOf"][0]["const"] == 1
