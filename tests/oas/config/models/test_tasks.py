import pytest
from pydantic import Field, ValidationError

from oas.config.models.args import Input, Switch
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import SchemaContext, SchemaRule, TaskBase, schema


class ExampleGroup(GroupBase):
    first: str = Input.str(default="first")
    second: str = Input.str(default="second")
    enabled: bool = Switch.field(default=True)


class ExampleTask(TaskBase):
    group: ExampleGroup = Field(default_factory=ExampleGroup)

    @classmethod
    @schema.hide("group.first", "group.second")
    @schema.icon("group", "settings")
    @schema.description("group.enabled", "Task-specific description")
    def schema_overrides(cls, rules: list[SchemaRule]) -> None:
        cls._pending_schema_rules.extend(rules)


def test_decorators_are_stored_on_the_function() -> None:
    function = ExampleTask.__dict__["schema_overrides"].__func__
    rules = function.__oas_schema_rules__

    assert [rule.target for rule in rules] == [
        "group.enabled",
        "group",
        "group.first",
        "group.second",
    ]


def test_task_schema_overrides_apply_to_multiple_paths_and_group() -> None:
    schema_data = ExampleTask.model_json_schema()
    group = schema_data["properties"]["group"]

    assert group["icon"] == "settings"
    assert group["properties"]["first"]["hide"] is True
    assert group["properties"]["second"]["hide"] is True
    assert group["properties"]["enabled"]["description"] == (
        "Task-specific description"
    )


def test_task_schema_overrides_do_not_mutate_shared_definition() -> None:
    schema_data = ExampleTask.model_json_schema()
    definition = ExampleGroup.model_json_schema()

    assert "icon" not in definition
    assert definition["properties"]["first"]["hide"] is False
    assert schema_data["properties"]["group"]["properties"]["first"]["hide"] is True


def test_task_schema_without_decorators_is_unchanged() -> None:
    class PlainTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    group = PlainTask.model_json_schema()["properties"]["group"]
    assert group["$ref"] == "#/$defs/ExampleGroup"


def test_schema_decorator_order_does_not_matter_for_different_keys() -> None:
    class ReversedTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.icon("group.first", "one")
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = ReversedTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "one"
    assert first["hide"] is True


@pytest.mark.parametrize(
    ("decorator", "args"),
    [
        (schema.hide, ("group.missing",)),
        (schema.icon, ("group.missing", "icon")),
    ],
)
def test_task_schema_override_rejects_missing_path(decorator, args) -> None:
    class InvalidTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @decorator(*args)
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    with pytest.raises(KeyError, match="schema override path does not exist"):
        InvalidTask.model_json_schema()


def test_schema_hide_rejects_non_boolean_value() -> None:
    class InvalidTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first", value="yes")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    with pytest.raises(TypeError, match="schema.hide value must be bool"):
        InvalidTask.model_json_schema()


def test_schema_icon_mapping_supports_different_values() -> None:
    class MappingTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.icon({"group.first": "one", "group.second": "two"})
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = MappingTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["first"]["icon"] == "one"
    assert properties["second"]["icon"] == "two"


def test_manual_schema_overrides_are_applied_and_cleared() -> None:
    class DynamicTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    DynamicTask.schema_overrides(
        [
            SchemaRule(
                target="group.enabled",
                property="icon",
                value="runtime",
            )
        ]
    )
    schema_data = DynamicTask.model_json_schema()
    enabled = schema_data["properties"]["group"]["properties"]["enabled"]

    assert enabled["icon"] == "runtime"
    assert DynamicTask._pending_schema_rules == []


def test_schema_rule_merge_keeps_existing_schema() -> None:
    class MergeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.merge(
            "group.first",
            {"hide": True, "icon": "star", "title": "First"},
        )
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = MergeTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["type"] == "Input"
    assert first["default"] == "first"
    assert first["hide"] is True
    assert first["icon"] == "star"
    assert first["title"] == "First"


def test_schema_rule_replace_replaces_the_complete_arg_schema() -> None:
    class ReplaceTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.replace(
            "group.first",
            {"type": "Switch", "default": False, "hide": True, "icon": "refresh"},
        )
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = ReplaceTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first == {
        "type": "Switch",
        "default": False,
        "hide": True,
        "icon": "refresh",
    }


def test_schema_rule_delete_can_remove_property_or_complete_arg() -> None:
    class DeletePropertyTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.delete("group.first", "description")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = DeletePropertyTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert "description" not in first

    class DeleteNodeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.delete("group.second")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = DeleteNodeTask.model_json_schema()["properties"]["group"]["properties"]
    assert "second" not in properties


def test_schema_rule_when_controls_application() -> None:
    class ConditionalTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ConditionalTask.schema_overrides(
        [
            SchemaRule(
                target="group.second",
                property="hide",
                value=True,
                when=lambda context: context.task_type is ConditionalTask,
            )
        ]
    )
    properties = ConditionalTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["second"]["hide"] is True


def test_pending_rules_are_cleared_when_rule_application_fails() -> None:
    class InvalidDynamicTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidDynamicTask.schema_overrides(
        [SchemaRule(target="group.missing", property="hide", value=True)]
    )
    with pytest.raises(KeyError):
        InvalidDynamicTask.model_json_schema()
    assert InvalidDynamicTask._pending_schema_rules == []


@pytest.mark.parametrize(
    "rule",
    [
        SchemaRule("group.first", operation="set"),
        SchemaRule("group.first", operation="merge", value=[]),
        SchemaRule("group.first", operation="replace", value="not a mapping"),
    ],
)
def test_invalid_schema_rule_operations_raise(rule: SchemaRule) -> None:
    class InvalidOperationTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidOperationTask.schema_overrides([rule])
    with pytest.raises((TypeError, ValueError), match="(requires property|mapping|object)"):
        InvalidOperationTask.model_json_schema()


def test_schema_rule_rejects_invalid_definition() -> None:
    with pytest.raises(TypeError):
        SchemaRule("")
    with pytest.raises(ValueError):
        SchemaRule("group.first", operation="unknown")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SchemaRule("group.first", when="always")  # type: ignore[arg-type]


def test_schema_rule_defaults_and_dataclass_shape() -> None:
    rule = SchemaRule("group.first")
    assert rule.target == "group.first"
    assert rule.property is None
    assert rule.operation == "set"
    assert rule.value is None
    assert rule.when is None


def test_schema_rule_is_immutable() -> None:
    rule = SchemaRule("group.first", property="hide", value=True)
    with pytest.raises(AttributeError):
        rule.value = False  # type: ignore[misc]


@pytest.mark.parametrize("target", [None, 1, [], {}])
def test_schema_rule_rejects_non_string_target(target) -> None:
    with pytest.raises(TypeError, match="target"):
        SchemaRule(target)  # type: ignore[arg-type]


@pytest.mark.parametrize("property_name", ["", "  ", 1, [], {}])
def test_schema_rule_rejects_invalid_property(property_name) -> None:
    with pytest.raises(TypeError, match="property"):
        SchemaRule("group.first", property=property_name)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["append", "update", "", None, 1])
def test_schema_rule_rejects_unknown_operation(operation) -> None:
    with pytest.raises(ValueError, match="operation"):
        SchemaRule("group.first", operation=operation)  # type: ignore[arg-type]


def test_schema_rule_accepts_any_value_type() -> None:
    assert SchemaRule("group.first", property="x", value=None).value is None
    assert SchemaRule("group.first", property="x", value=1).value == 1
    assert SchemaRule("group.first", property="x", value=[]).value == []
    assert SchemaRule("group.first", property="x", value={"a": 1}).value == {"a": 1}


def test_schema_rule_when_accepts_callable() -> None:
    callback = lambda context: True
    assert SchemaRule("group.first", when=callback).when is callback


def test_schema_decorators_store_all_property_rules_on_function() -> None:
    class DecoratorTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.alias("group.first", value="first_alias")
        @schema.depends("group.second", value="group.first")
        @schema.description("group.enabled", value="enabled description")
        @schema.title("group.first", value="First title")
        @schema.icon("group.second", value="star")
        @schema.hide("group.enabled")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = DecoratorTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["enabled"]["hide"] is True
    assert properties["second"]["icon"] == "star"
    assert properties["first"]["title"] == "First title"
    assert properties["enabled"]["description"] == "enabled description"
    assert properties["second"]["depends"] == "group.first"
    assert properties["first"]["alias"] == "first_alias"


def test_schema_decorator_mapping_preserves_per_path_values() -> None:
    class MappingTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.title({"group.first": "One", "group.second": "Two"})
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = MappingTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["first"]["title"] == "One"
    assert properties["second"]["title"] == "Two"


def test_schema_operation_decorators_create_expected_operations() -> None:
    class OperationDecoratorTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.set("group.first", "icon", "star")
        @schema.merge("group.enabled", {"icon": "toggle", "title": "Enabled"})
        @schema.delete("group.second", "description")
        @schema.replace("group.first", {"type": "Switch", "default": False})
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = OperationDecoratorTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["first"] == {"type": "Switch", "default": False, "icon": "star"}
    assert "description" not in properties["second"]
    assert properties["enabled"]["icon"] == "toggle"
    assert properties["enabled"]["title"] == "Enabled"


@pytest.mark.parametrize(
    "decorator_factory",
    [
        lambda: schema.hide(),
        lambda: schema.icon(""),
        lambda: schema.title("  "),
        lambda: schema.description(1),
        lambda: schema.depends([]),
        lambda: schema.alias({}),
    ],
)
def test_schema_property_decorators_reject_invalid_paths(decorator_factory) -> None:
    with pytest.raises(TypeError):
        decorator_factory()


def test_schema_mapping_cannot_combine_with_value() -> None:
    with pytest.raises(TypeError, match="mapping"):
        schema.icon({"group.first": "one"}, value="two")


def test_schema_decorator_does_not_wrap_or_inject_function_arguments() -> None:
    class SignatureTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    function = SignatureTask.__dict__["schema_overrides"].__func__
    assert list(function.__annotations__) == ["rules", "return"]
    assert not hasattr(function, "__wrapped__")


def test_staticmethod_decorator_rules_are_exported() -> None:
    class StaticTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @staticmethod
        @schema.hide("group.first")
        def schema_overrides(rules: list[SchemaRule]) -> None:
            StaticTask._pending_schema_rules.extend(rules)

    first = StaticTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["hide"] is True


def test_hook_is_not_called_automatically_during_schema_export() -> None:
    class NoCallTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            raise AssertionError("schema_overrides must be called explicitly")

    first = NoCallTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["hide"] is True


def test_manual_rules_override_decorator_rules() -> None:
    class PrecedenceTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first", value=False)
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    PrecedenceTask.schema_overrides([SchemaRule("group.first", property="hide", value=True)])
    first = PrecedenceTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["hide"] is True


def test_manual_rules_are_applied_in_registration_order() -> None:
    class OrderedTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    OrderedTask.schema_overrides(
        [
            SchemaRule("group.first", property="title", value="first"),
            SchemaRule("group.first", property="title", value="last"),
        ]
    )
    first = OrderedTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["title"] == "last"


def test_manual_empty_rules_are_safe() -> None:
    class EmptyRulesTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    EmptyRulesTask.schema_overrides([])
    EmptyRulesTask.model_json_schema()
    assert EmptyRulesTask._pending_schema_rules == []


def test_pending_rules_are_not_reused_on_second_export() -> None:
    class RepeatTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    RepeatTask.schema_overrides([SchemaRule("group.first", property="icon", value="one")])
    first_export = RepeatTask.model_json_schema()
    second_export = RepeatTask.model_json_schema()
    assert first_export["properties"]["group"]["properties"]["first"]["icon"] == "one"
    assert second_export["properties"]["group"]["$ref"] == "#/$defs/ExampleGroup"


def test_parent_and_child_function_rules_are_combined_in_mro_order() -> None:
    class ParentTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.title("group.first", value="parent")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    class ChildTask(ParentTask):
        @classmethod
        @schema.title("group.first", value="child")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = ChildTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["title"] == "child"


def test_parent_rules_are_not_applied_to_unrelated_task() -> None:
    class ParentTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    class OtherTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    assert ParentTask.model_json_schema()["properties"]["group"]["properties"]["first"]["hide"] is True
    other_schema = OtherTask.model_json_schema()
    assert other_schema["properties"]["group"]["$ref"] == "#/$defs/ExampleGroup"
    assert ExampleGroup.model_json_schema()["properties"]["first"]["hide"] is False


def test_set_property_none_is_rejected_at_export() -> None:
    class InvalidSetTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidSetTask.schema_overrides([SchemaRule("group.first", operation="set", value=True)])
    with pytest.raises(ValueError, match="requires property"):
        InvalidSetTask.model_json_schema()


def test_merge_preserves_existing_properties() -> None:
    class MergeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    MergeTask.schema_overrides([SchemaRule("group.first", operation="merge", value={"icon": "star"})])
    first = MergeTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "star"
    assert first["default"] == "first"
    assert first["type"] == "Input"


def test_merge_property_target_requires_an_object() -> None:
    class InvalidMergeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidMergeTask.schema_overrides([SchemaRule("group.first", property="type", operation="merge", value={"x": 1})])
    with pytest.raises(TypeError, match="object"):
        InvalidMergeTask.model_json_schema()


def test_delete_missing_property_is_idempotent() -> None:
    class DeleteTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    DeleteTask.schema_overrides([SchemaRule("group.first", property="not_present", operation="delete")])
    schema_data = DeleteTask.model_json_schema()
    assert "not_present" not in schema_data["properties"]["group"]["properties"]["first"]


def test_replace_group_node_replaces_only_the_selected_branch() -> None:
    class ReplaceGroupTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ReplaceGroupTask.schema_overrides([SchemaRule("group", operation="replace", value={"type": "object", "title": "New"})])
    schema_data = ReplaceGroupTask.model_json_schema()
    assert schema_data["properties"]["group"] == {"type": "object", "title": "New"}


def test_when_receives_schema_context() -> None:
    contexts: list[object] = []

    class ContextTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    def condition(context):
        contexts.append(context)
        return context.task_type is ContextTask and context.target == "group.first" and context.property == "icon" and isinstance(context.schema, dict)

    ContextTask.schema_overrides([SchemaRule("group.first", property="icon", value="star", when=condition)])
    first = ContextTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "star"
    assert len(contexts) == 1


def test_when_false_skips_rule() -> None:
    class ConditionalTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ConditionalTask.schema_overrides([SchemaRule("group.first", property="icon", value="never", when=lambda context: False)])
    schema_data = ConditionalTask.model_json_schema()
    assert schema_data["properties"]["group"]["$ref"] == "#/$defs/ExampleGroup"


def test_when_exception_propagates_and_pending_rules_clear() -> None:
    class ConditionalTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    def condition(context):
        raise RuntimeError("condition failed")

    ConditionalTask.schema_overrides([SchemaRule("group.first", property="icon", value="bad", when=condition)])
    with pytest.raises(RuntimeError, match="condition failed"):
        ConditionalTask.model_json_schema()
    assert ConditionalTask._pending_schema_rules == []


def test_ref_branch_override_does_not_mutate_group_schema() -> None:
    class RefTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    RefTask.schema_overrides([SchemaRule("group.first", property="icon", value="star")])
    task_schema = RefTask.model_json_schema()
    group_schema = ExampleGroup.model_json_schema()
    assert "icon" in task_schema["properties"]["group"]["properties"]["first"]
    assert "icon" not in group_schema["properties"]["first"]


def test_model_dump_is_unaffected_by_schema_rules() -> None:
    class DumpTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    DumpTask.schema_overrides([SchemaRule("group.first", property="icon", value="star")])
    assert DumpTask().model_dump() == {"group": {"first": "first", "second": "second", "enabled": True}}


def test_schema_rules_do_not_change_runtime_validation() -> None:
    class ValidationTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ValidationTask.schema_overrides([SchemaRule("group.first", operation="replace", value={"type": "integer"})])
    ValidationTask.model_json_schema()
    with pytest.raises(ValidationError):
        ValidationTask(group={"first": 1, "second": "ok", "enabled": True})


def test_hide_supports_multiple_paths_with_one_value() -> None:
    class MultiHideTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first", "group.second")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = MultiHideTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["first"]["hide"] is True
    assert properties["second"]["hide"] is True


def test_property_decorator_supports_trailing_value_form() -> None:
    class TrailingValueTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.icon("group.first", "star")
        @schema.title("group.second", "Second")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    properties = TrailingValueTask.model_json_schema()["properties"]["group"]["properties"]
    assert properties["first"]["icon"] == "star"
    assert properties["second"]["title"] == "Second"


def test_schema_decorator_rejects_empty_mapping() -> None:
    with pytest.raises(TypeError, match="path|mapping"):
        schema.icon({})


def test_schema_decorator_rejects_non_string_mapping_key() -> None:
    with pytest.raises(TypeError, match="path"):
        schema.icon({1: "icon"})


def test_schema_replace_decorator_rejects_non_mapping_value() -> None:
    with pytest.raises((TypeError, ValueError)):
        schema.replace("group.first", "not a mapping")  # type: ignore[arg-type]


def test_manual_hide_type_validation() -> None:
    class InvalidHideTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidHideTask.schema_overrides(
        [SchemaRule("group.first", property="hide", value="yes")]
    )
    with pytest.raises(TypeError, match="schema.hide"):
        InvalidHideTask.model_json_schema()
    assert InvalidHideTask._pending_schema_rules == []


def test_manual_string_metadata_type_validation() -> None:
    class InvalidMetadataTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidMetadataTask.schema_overrides(
        [SchemaRule("group.first", property="icon", value=1)]
    )
    with pytest.raises(TypeError, match="schema.icon"):
        InvalidMetadataTask.model_json_schema()
    assert InvalidMetadataTask._pending_schema_rules == []


def test_delete_complete_node_removes_only_target_property() -> None:
    class DeleteNodeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    DeleteNodeTask.schema_overrides([SchemaRule("group.second", operation="delete")])
    properties = DeleteNodeTask.model_json_schema()["properties"]["group"]["properties"]
    assert "first" in properties
    assert "second" not in properties


def test_missing_path_error_clears_pending_rules() -> None:
    class MissingPathTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    MissingPathTask.schema_overrides(
        [SchemaRule("group.missing", property="hide", value=True)]
    )
    with pytest.raises(KeyError):
        MissingPathTask.model_json_schema()
    assert MissingPathTask._pending_schema_rules == []


def test_each_task_subclass_has_an_independent_pending_buffer() -> None:
    class FirstTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    class SecondTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    FirstTask.schema_overrides([SchemaRule("group.first", property="icon", value="one")])
    assert len(FirstTask._pending_schema_rules) == 1
    assert SecondTask._pending_schema_rules == []
    SecondTask.model_json_schema()
    assert len(FirstTask._pending_schema_rules) == 1
    FirstTask.model_json_schema()
    assert FirstTask._pending_schema_rules == []


def test_class_rules_are_not_added_to_pending_buffer() -> None:
    class ClassOnlyTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    ClassOnlyTask.model_json_schema()
    assert ClassOnlyTask._pending_schema_rules == []


def test_schema_export_is_stable_across_repeated_calls() -> None:
    class StableTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.icon("group.first", value="star")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    assert StableTask.model_json_schema() == StableTask.model_json_schema()


def test_schema_context_has_no_task_instance_for_class_export() -> None:
    contexts: list[SchemaContext] = []

    class ContextTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    def condition(context):
        contexts.append(context)
        return True

    ContextTask.schema_overrides(
        [SchemaRule("group.first", property="icon", value="star", when=condition)]
    )
    ContextTask.model_json_schema()
    assert contexts[0].task_instance is None


def test_when_can_skip_a_missing_path_without_error() -> None:
    class ConditionalMissingTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ConditionalMissingTask.schema_overrides(
        [
            SchemaRule(
                "group.missing",
                property="hide",
                value=True,
                when=lambda context: False,
            )
        ]
    )
    ConditionalMissingTask.model_json_schema()
    assert ConditionalMissingTask._pending_schema_rules == []


def test_parent_pending_rules_do_not_leak_into_child() -> None:
    class ParentTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    class ChildTask(ParentTask):
        pass

    ParentTask.schema_overrides([SchemaRule("group.first", property="icon", value="parent")])
    ChildTask.model_json_schema()
    assert len(ParentTask._pending_schema_rules) == 1
    assert ChildTask._pending_schema_rules == []


def test_replace_failure_clears_pending_rules() -> None:
    class InvalidReplaceTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidReplaceTask.schema_overrides(
        [SchemaRule("group.first", operation="replace", value="invalid")]
    )
    with pytest.raises(TypeError, match="replace"):
        InvalidReplaceTask.model_json_schema()
    assert InvalidReplaceTask._pending_schema_rules == []


def test_schema_context_contains_all_export_context_fields() -> None:
    task_type = type("ContextTask", (TaskBase,), {})
    schema_data = {"type": "object"}
    context = SchemaContext(
        task_type=task_type,
        schema=schema_data,
        task_instance=None,
        target="group.first",
        property="icon",
    )

    assert context.task_type is task_type
    assert context.schema is schema_data
    assert context.task_instance is None
    assert context.target == "group.first"
    assert context.property == "icon"


def test_schema_context_is_immutable() -> None:
    context = SchemaContext(task_type=TaskBase, schema={})
    with pytest.raises(AttributeError):
        context.target = "group.first"  # type: ignore[misc]


@pytest.mark.parametrize("decorator", [schema.hide, schema.icon, schema.title, schema.description])
def test_property_decorator_requires_a_path(decorator) -> None:
    with pytest.raises(TypeError, match="path"):
        decorator()


@pytest.mark.parametrize("path", [None, 1, [], {}, "", "   "])
def test_property_decorator_rejects_invalid_path_values(path) -> None:
    with pytest.raises(TypeError, match="path|mapping"):
        schema.hide(path)  # type: ignore[arg-type]


def test_property_decorator_rejects_non_callable_target() -> None:
    decorator = schema.hide("group.first")
    with pytest.raises(TypeError, match="method"):
        decorator(123)


def test_property_decorator_keeps_classmethod_descriptor() -> None:
    class DescriptorTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @schema.hide("group.first")
        @classmethod
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    descriptor = DescriptorTask.__dict__["schema_overrides"]
    assert isinstance(descriptor, classmethod)
    assert descriptor.__func__.__oas_schema_rules__[0].property == "hide"
    assert DescriptorTask.model_json_schema()["properties"]["group"]["properties"]["first"]["hide"] is True


def test_property_decorator_keeps_staticmethod_descriptor() -> None:
    class DescriptorTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @schema.hide("group.first")
        @staticmethod
        def schema_overrides(rules: list[SchemaRule]) -> None:
            DescriptorTask._pending_schema_rules.extend(rules)

    descriptor = DescriptorTask.__dict__["schema_overrides"]
    assert isinstance(descriptor, staticmethod)
    assert descriptor.__func__.__oas_schema_rules__[0].property == "hide"
    assert DescriptorTask.model_json_schema()["properties"]["group"]["properties"]["first"]["hide"] is True


def test_decorator_rules_are_stored_as_a_tuple() -> None:
    class TupleTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.hide("group.first")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    rules = TupleTask.__dict__["schema_overrides"].__func__.__oas_schema_rules__
    assert isinstance(rules, tuple)
    assert isinstance(rules[0], SchemaRule)


def test_schema_rule_hash_and_repr_are_available() -> None:
    rule = SchemaRule("group.first", property="hide", value=True)
    assert hash(rule) == hash(SchemaRule("group.first", property="hide", value=True))
    assert "group.first" in repr(rule)


def test_schema_rule_equality_includes_all_fields() -> None:
    base = SchemaRule("group.first", property="hide", value=True)
    assert base == SchemaRule("group.first", property="hide", value=True)
    assert base != SchemaRule("group.first", property="hide", value=False)
    assert base != SchemaRule("group.second", property="hide", value=True)
    assert base != SchemaRule("group.first", operation="delete", property="hide")


def test_schema_rule_mapping_values_are_not_shared_with_decorator_input() -> None:
    replacement = {"type": "Switch"}

    decorator = schema.replace("group.first", replacement)
    replacement["icon"] = "changed-after-decoration"

    class CopyTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @decorator
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = CopyTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first == {"type": "Switch"}


def test_schema_merge_decorator_copies_mapping_value() -> None:
    metadata = {"icon": "initial"}
    decorator = schema.merge("group.first", metadata)
    metadata["title"] = "added-later"

    class CopyTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @decorator
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    first = CopyTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "initial"
    assert first["title"] != "added-later"


def test_set_rule_can_assign_none_to_a_schema_property() -> None:
    class NoneTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    NoneTask.schema_overrides([SchemaRule("group.first", property="icon", value=None)])
    first = NoneTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert "icon" in first
    assert first["icon"] is None


def test_replace_rule_with_property_replaces_only_that_property() -> None:
    class PropertyReplaceTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    PropertyReplaceTask.schema_overrides(
        [SchemaRule("group.first", property="type", operation="replace", value={"kind": "integer"})]
    )
    first = PropertyReplaceTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["type"] == {"kind": "integer"}
    assert first["default"] == "first"


def test_delete_rule_can_remove_the_root_group_property() -> None:
    class DeleteGroupTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    DeleteGroupTask.schema_overrides([SchemaRule("group", operation="delete")])
    assert "group" not in DeleteGroupTask.model_json_schema()["properties"]


def test_merge_rule_can_update_the_complete_target_node() -> None:
    class MergeNodeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    MergeNodeTask.schema_overrides(
        [SchemaRule("group.first", operation="merge", value={"icon": "star"})]
    )
    first = MergeNodeTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "star"
    assert first["default"] == "first"


def test_merge_rule_rejects_a_scalar_target_property() -> None:
    class InvalidMergeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidMergeTask.schema_overrides(
        [SchemaRule("group.first", property="type", operation="merge", value={"format": "x"})]
    )
    with pytest.raises(TypeError, match="object"):
        InvalidMergeTask.model_json_schema()


def test_rule_order_is_shared_between_decorated_and_pending_rules() -> None:
    class OrderedTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.title("group.first", value="decorator")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    OrderedTask.schema_overrides(
        [SchemaRule("group.first", property="title", value="pending")]
    )
    first = OrderedTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["title"] == "pending"


def test_export_without_pending_rules_does_not_mutate_pending_buffer() -> None:
    class NoPendingTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    assert NoPendingTask._pending_schema_rules == []
    NoPendingTask.model_json_schema()
    assert NoPendingTask._pending_schema_rules == []


def test_failed_when_callback_clears_pending_rules_before_next_export() -> None:
    class CallbackTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    CallbackTask.schema_overrides(
        [SchemaRule("group.first", property="icon", value="bad", when=lambda _: 1 / 0)]
    )
    with pytest.raises(ZeroDivisionError):
        CallbackTask.model_json_schema()
    assert CallbackTask._pending_schema_rules == []
    assert CallbackTask.model_json_schema()["properties"]["group"]["$ref"] == "#/$defs/ExampleGroup"


def test_parent_decorator_rules_apply_when_child_does_not_override_hook() -> None:
    class ParentTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

        @classmethod
        @schema.icon("group.first", value="parent")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    class ChildTask(ParentTask):
        pass

    first = ChildTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["icon"] == "parent"


def test_child_decorator_rules_do_not_modify_parent_schema() -> None:
    class ParentTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    class ChildTask(ParentTask):
        @classmethod
        @schema.icon("group.first", value="child")
        def schema_overrides(cls, rules: list[SchemaRule]) -> None:
            cls._pending_schema_rules.extend(rules)

    child = ChildTask.model_json_schema()
    parent = ParentTask.model_json_schema()
    assert child["properties"]["group"]["properties"]["first"]["icon"] == "child"
    group_ref = parent["properties"]["group"]["$ref"]
    parent_group = parent["$defs"][group_ref.rsplit("/", 1)[-1]]
    assert "icon" not in parent_group["properties"]["first"]


def test_rule_target_must_be_dotted_schema_path_not_arbitrary_text() -> None:
    class InvalidPathTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    InvalidPathTask.schema_overrides([SchemaRule("group.first.not_a_property", property="hide", value=True)])
    with pytest.raises(KeyError):
        InvalidPathTask.model_json_schema()


def test_when_false_prevents_validation_of_the_rule_value() -> None:
    class ConditionalTypeTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    ConditionalTypeTask.schema_overrides(
        [SchemaRule("group.first", property="hide", value=False, when=lambda _: False)]
    )
    schema_data = ConditionalTypeTask.model_json_schema()
    group_ref = schema_data["properties"]["group"]["$ref"]
    first = schema_data["$defs"][group_ref.rsplit("/", 1)[-1]]["properties"]["first"]
    assert first["hide"] is False


def test_multiple_rules_can_target_the_same_node() -> None:
    class MultiRuleTask(TaskBase):
        group: ExampleGroup = Field(default_factory=ExampleGroup)

    MultiRuleTask.schema_overrides(
        [
            SchemaRule("group.first", property="hide", value=True),
            SchemaRule("group.first", property="icon", value="star"),
            SchemaRule("group.first", property="title", value="First"),
        ]
    )
    first = MultiRuleTask.model_json_schema()["properties"]["group"]["properties"]["first"]
    assert first["hide"] is True
    assert first["icon"] == "star"
    assert first["title"] == "First"


class TaskIoMainGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)


class TaskIoExtraGroup(GroupBase):
    value: str = Input.str(default="extra")


class TaskIoTask(TaskBase):
    main: TaskIoMainGroup = Field(default_factory=TaskIoMainGroup)
    extra: TaskIoExtraGroup = Field(default_factory=TaskIoExtraGroup)
    label: str = Input.str(default="task")
    dynamic: list[TaskIoExtraGroup] = Field(default_factory=list)


class TaskIoDefaultedTask(TaskBase):
    main: TaskIoMainGroup = Field(
        default_factory=lambda: TaskIoMainGroup(count=8)
    )


class TaskIoRequiredTask(TaskBase):
    main: TaskIoMainGroup


def test_to_dict_only_exports_single_group_fields():
    task = TaskIoTask()

    data = task.to_dict()

    assert list(data) == ["main", "extra"]
    assert data["main"] == task.main.to_dict()
    assert data["extra"] == task.extra.to_dict()
    assert "label" not in data
    assert "dynamic" not in data


def test_to_dict_omits_non_empty_dynamic_group_lists():
    task = TaskIoTask(dynamic=[TaskIoExtraGroup(value="one")])

    data = task.to_dict()

    assert list(data) == ["main", "extra"]


def test_from_dict_roundtrip():
    task = TaskIoTask(
        main=TaskIoMainGroup(count=6),
        extra=TaskIoExtraGroup(value="kept"),
    )

    assert TaskIoTask.from_dict(task.to_dict()) == task


def test_from_dict_uses_task_default_factory_for_missing_group():
    task = TaskIoDefaultedTask.from_dict({})

    assert task.main.count == 8


def test_from_dict_builds_required_group_from_empty_payload():
    task = TaskIoRequiredTask.from_dict({"main": {}})

    assert task.main == TaskIoMainGroup()


def test_from_dict_ignores_unknown_groups():
    data = dict(TaskIoTask().to_dict())
    data["removed_group"] = {"value": "x"}

    assert TaskIoTask.from_dict(data) == TaskIoTask()


def test_from_dict_rejects_invalid_group_payload():
    with pytest.raises(ValidationError):
        TaskIoTask.from_dict({"main": {"count": -1}})


def test_from_dict_rejects_non_mapping_group_payload():
    with pytest.raises(ValidationError):
        TaskIoTask.from_dict({"main": ["not", "a", "mapping"]})


def test_from_dict_rejects_missing_required_group():
    # ``from_dict`` adds no fallback: only Pydantic defaults fill missing
    # fields, and a Group without a default has none.
    with pytest.raises(ValidationError):
        TaskIoRequiredTask.from_dict({})



class TaskErrGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)


class TaskErrTask(TaskBase):
    main: TaskErrGroup = Field(default_factory=TaskErrGroup)
    dynamic: list[TaskErrGroup] = Field(default_factory=list)
    label: int = Input.int(default=0)


@pytest.mark.parametrize("payload", [None, [], 1, "text"])
def test_from_dict_rejects_non_mappings(payload):
    with pytest.raises(ValidationError):
        TaskErrTask.from_dict(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"main": "not-a-group"},
        {"main": {"count": -1}},
        {"dynamic": "not-a-list"},
        {"label": "not-an-int"},
    ],
)
def test_from_dict_rejects_invalid_fields(payload):
    with pytest.raises(ValidationError):
        TaskErrTask.from_dict(payload)


def test_from_dict_ignores_unknown_groups_on_task_with_dynamic():
    assert TaskErrTask.from_dict({"removed": {"count": 2}}) == TaskErrTask()


def test_from_dict_accepts_dynamic_group_dicts():
    task = TaskErrTask.from_dict({"dynamic": [{"count": 3}]})

    assert len(task.dynamic) == 1
    assert task.dynamic[0].count == 3


def test_to_dict_still_omits_dynamic_groups():
    task = TaskErrTask.from_dict({"dynamic": [{"count": 3}]})

    assert "dynamic" not in task.to_dict()
    assert list(task.to_dict()) == ["main"]
