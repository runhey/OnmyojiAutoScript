import pytest
from pydantic import BaseModel

from oas.config.models.args import Option, OptionItem


@pytest.mark.parametrize(
    ("factory", "value", "core_type"),
    [
        (OptionItem.str, "fast", str),
        (OptionItem.int, 1, int),
        (OptionItem.float, 0.5, float),
        (OptionItem.bool, True, bool),
    ],
)
def test_factories_store_value_and_core_type(factory, value, core_type):
    item = factory(value)

    assert item.value == value
    assert item._core_type is core_type
    assert item.field_info.default == value


def test_option_item_repr_equality_and_hash():
    first = OptionItem.str("fast")
    same = OptionItem.str("fast")
    other = OptionItem.str("safe")

    assert repr(first) == "OptionItem('fast')"
    assert first == "fast"
    assert first == same
    assert first != other
    assert hash(first) == hash("fast")
    assert {first: "value"}[same] == "value"


@pytest.mark.parametrize(
    ("factory", "value", "message"),
    [
        (OptionItem.str, 1, "requires a str value"),
        (OptionItem.int, "1", "requires a int value"),
        (OptionItem.float, "0.5", "requires a float value"),
        (OptionItem.bool, 1, "requires a bool value"),
    ],
)
def test_factory_rejects_wrong_value_type(factory, value, message):
    with pytest.raises(TypeError, match=message):
        factory(value)


def test_option_item_rejects_default_argument_even_when_it_matches_value():
    with pytest.raises(TypeError, match="does not accept a default"):
        OptionItem.str("fast", default="fast")


def test_option_item_metadata_is_stored_in_field_info():
    item = OptionItem.str(
        "fast",
        title="快速",
        description="快速模式",
        hide=True,
        icon="bolt",
        alias="fast_mode",
    )

    assert item.field_info.title == "快速"
    assert item.field_info.description == "快速模式"
    assert item.field_info.json_schema_extra == {
        "hide": True,
        "icon": "bolt",
        "alias": "fast_mode",
        "readOnly": True,
    }


def test_option_item_none_metadata_is_not_exported():
    class OptionalMetadataOption(Option):
        VALUE = OptionItem.str(
            "value",
            title=None,
            description=None,
            hide=None,
            icon=None,
            alias=None,
        )

    class Config(BaseModel):
        value: OptionalMetadataOption

    branch = Config.model_json_schema()["properties"]["value"]["oneOf"][0]

    assert branch == {
        "const": "value",
        "default": "value",
        "readOnly": True,
        "type": "string",
    }


def test_option_item_generates_i18n_metadata_from_option_and_member_names():
    class GameModeOption(Option):
        FAST_MODE = OptionItem.str("fast")

    class Config(BaseModel):
        mode: GameModeOption

    branch = Config.model_json_schema()["properties"]["mode"]["oneOf"][0]

    assert branch["title"] == "$game_mode_option.fast_mode.title"
    assert branch["description"] == "$game_mode_option.fast_mode.description"


def test_explicit_metadata_overrides_generated_i18n_metadata():
    class ModeOption(Option):
        FAST = OptionItem.str(
            "fast",
            title="快速",
            description="快速模式",
        )

    class Config(BaseModel):
        mode: ModeOption

    branch = Config.model_json_schema()["properties"]["mode"]["oneOf"][0]

    assert branch["title"] == "快速"
    assert branch["description"] == "快速模式"


def test_option_item_json_schema_extra_overrides_ui_metadata_but_not_read_only():
    class ModeOption(Option):
        FAST = OptionItem.str(
            "fast",
            hide=False,
            icon="default",
            alias="default_alias",
            json_schema_extra={
                "hide": True,
                "icon": "override",
                "alias": "override_alias",
                "readOnly": False,
                "x-ui": "select",
            },
        )

    class Config(BaseModel):
        mode: ModeOption

    branch = Config.model_json_schema()["properties"]["mode"]["oneOf"][0]

    assert branch["hide"] is True
    assert branch["icon"] == "override"
    assert branch["alias"] == "override_alias"
    assert branch["readOnly"] is True
    assert branch["x-ui"] == "select"


def test_option_item_ignores_removed_metadata_arguments():
    item = OptionItem.str("fast", help="old", examples=["fast"], deprecated=True)

    assert "help" not in item.field_info.json_schema_extra
    assert item.field_info.examples is None
    assert item.field_info.deprecated is None


def test_option_item_rejects_non_mapping_json_schema_extra():
    with pytest.raises(TypeError, match="json_schema_extra must be a dictionary"):
        OptionItem.str("fast", json_schema_extra=[("hide", True)])

