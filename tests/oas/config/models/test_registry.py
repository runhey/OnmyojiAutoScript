import pytest
from pydantic import Field

from oas.config.models.args import Input
from oas.config.models.groups import DynamicGroupBase, GroupBase
from oas.config.models.registry import ConfigModelRegistry, config_model_registry
from oas.config.models.tasks import TaskBase


class RegistryTestGroup(GroupBase):
    value: str = Input.str(default='value')


class RegistryTestDynamicGroup(DynamicGroupBase):
    value: int = Input.int(default=1)


class RegistryTestTask(TaskBase):
    group: RegistryTestGroup
    dynamic: RegistryTestDynamicGroup


def test_registry_is_a_singleton():
    assert ConfigModelRegistry() is config_model_registry


def test_registry_stores_concrete_groups_only():
    assert config_model_registry.find_groups('RegistryTestGroup') == (
        RegistryTestGroup,
    )
    assert config_model_registry.find_groups('RegistryTestDynamicGroup') == (
        RegistryTestDynamicGroup,
    )
    assert config_model_registry.find_groups('GroupBase') == ()
    assert config_model_registry.find_groups('DynamicGroupBase') == ()


def test_registry_stores_task_to_group_classes_and_fields():
    assert config_model_registry.groups_for(RegistryTestTask) == (
        RegistryTestGroup,
        RegistryTestDynamicGroup,
    )
    assert (
        config_model_registry.group_for_field(RegistryTestTask, 'group')
        is RegistryTestGroup
    )
    assert (
        config_model_registry.group_for_field(RegistryTestTask, 'dynamic')
        is RegistryTestDynamicGroup
    )
    assert config_model_registry.group_for_field(RegistryTestTask, 'missing') is None


def test_registry_does_not_change_when_task_instance_is_created():
    before = config_model_registry.find_tasks('RegistryTestTask')
    RegistryTestTask(group={'value': 'new'}, dynamic={'value': 2})
    assert (
        config_model_registry.find_tasks('RegistryTestTask')
        == before
        == (RegistryTestTask,)
    )


class RegExtraA(GroupBase):
    value: str = Input.str(default='a')


class RegExtraB(GroupBase):
    value: int = Input.int(default=1)


class RegExtraTask(TaskBase):
    first: RegExtraA = Field(default_factory=RegExtraA)
    second: RegExtraB = Field(default_factory=RegExtraB)
    many: list[RegExtraA] = Field(default_factory=list)
    maybe: RegExtraB | None = None


def test_task_with_two_group_classes():
    assert config_model_registry.groups_for_task('RegExtraTask') == (
        RegExtraA,
        RegExtraB,
    )
    assert config_model_registry.group_for_field(RegExtraTask, 'first') is RegExtraA
    assert config_model_registry.group_for_field(RegExtraTask, 'second') is RegExtraB


def test_generic_group_annotations_resolve_to_the_group_class():
    assert config_model_registry.group_for_field(RegExtraTask, 'many') is RegExtraA
    assert config_model_registry.group_for_field(RegExtraTask, 'maybe') is RegExtraB


def test_filter_menu_keeps_registered_tasks_and_order():
    filtered = config_model_registry.filter_menu(
        {
            'Script': ['RegExtraTask', 'MissingTask'],
            'Empty': ['MissingTask'],
        }
    )

    assert filtered == {'Script': ['RegExtraTask']}


def test_unknown_task_class_raises_key_error():
    with pytest.raises(KeyError):
        config_model_registry.get_task_class('NoSuchTaskClass')


def test_unknown_group_class_raises_key_error():
    with pytest.raises(KeyError):
        config_model_registry.get_group_class('RegExtraTask', 'NoSuchGroupClass')


def test_groups_for_unknown_task_raises_key_error():
    with pytest.raises(KeyError):
        config_model_registry.groups_for_task('NoSuchTaskClass')


def test_task_fields_and_groups_are_read_only():
    with pytest.raises(TypeError):
        config_model_registry.task_fields[RegExtraTask] = {}
    with pytest.raises(TypeError):
        config_model_registry.groups['RegExtraA'] = (RegExtraA,)


def test_qualified_name_includes_module_and_qualname():
    assert config_model_registry.qualified_name(RegExtraTask) == (
        f'{RegExtraTask.__module__}.{RegExtraTask.__qualname__}'
    )


class RegMoreGroup(GroupBase):
    value: str = Input.str(default='v')


class RegMoreTask(TaskBase):
    main: RegMoreGroup = Field(default_factory=RegMoreGroup)


class RegMoreEmptyTask(TaskBase):
    pass


def test_find_unknown_returns_empty_tuples():
    assert config_model_registry.find_tasks('MissingTask') == ()
    assert config_model_registry.find_groups('MissingGroup') == ()


def test_groups_for_unknown_task_returns_empty_tuple():
    assert config_model_registry.groups_for('MissingTask') == ()


def test_group_for_non_group_field_returns_none():
    assert config_model_registry.group_for_field(RegMoreTask, 'missing') is None


def test_task_without_groups_has_empty_metadata():
    assert config_model_registry.groups_for_task('RegMoreEmptyTask') == ()
    assert config_model_registry.task_fields[RegMoreEmptyTask] == {}
    assert config_model_registry.data['RegMoreEmptyTask'] == []


def test_data_snapshot_does_not_expose_mutable_lists():
    first = config_model_registry.data['RegMoreTask']
    first.append('injected')

    assert config_model_registry.data['RegMoreTask'] == ['RegMoreGroup']


def test_filter_menu_empty_and_all_unknown():
    assert config_model_registry.filter_menu({}) == {}
    assert config_model_registry.filter_menu({'X': ['Missing']}) == {}


def test_group_index_contains_task_group_pairs():
    assert (
        config_model_registry.group_index[('RegMoreTask', 'RegMoreGroup')]
        is RegMoreGroup
    )


def test_registered_task_lookup_returns_the_class():
    assert config_model_registry.find_tasks('RegMoreTask') == (RegMoreTask,)
    assert config_model_registry.is_task_registered('RegMoreTask') is True
    assert config_model_registry.is_task_registered('RegMoreEmptyTask') is True
