"""Tests for ConfigBase registration and shared field helpers."""

import pytest
from pydantic import ValidationError

from oas.config.models.args import Input
from oas.config.models.base import (
    UNSET,
    boolean_component_field,
    build_field_schema_extra,
    temporal_field,
)
from oas.config.models.groups import GroupBase
from oas.config.models.registry import config_model_registry


class BaseTestGroup(GroupBase):
    value: str = Input.str(default='base')


class BaseTestAbstractGroup(GroupBase):
    __config_abstract__ = True


class BaseTestAssignGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)


def test_concrete_group_is_registered():
    assert config_model_registry.find_groups('BaseTestGroup') == (BaseTestGroup,)


def test_abstract_group_is_not_registered():
    assert config_model_registry.find_groups('BaseTestAbstractGroup') == ()


def test_unknown_arguments_are_ignored_and_not_dumped():
    group = BaseTestGroup.model_validate({'value': 'x', 'unknown': 1})

    assert group.value == 'x'
    assert group.to_dict() == {'value': 'x'}


def test_assignment_is_validated_and_keeps_the_old_value():
    group = BaseTestAssignGroup()

    group.count = 5
    assert group.count == 5

    with pytest.raises(ValidationError):
        group.count = -1
    assert group.count == 5


def test_model_copy_update_is_not_a_validated_patch():
    """``model_copy(update=...)`` skips validation - use ``validate_patch``."""
    group = BaseTestAssignGroup()

    assert group.model_copy(update={'count': -1}).count == -1
    with pytest.raises(ValidationError):
        BaseTestAssignGroup.validate_patch({'count': -1})


def test_build_field_schema_extra_merges_ui_metadata():
    extra = build_field_schema_extra(
        hide=True,
        icon='star',
        depends='mode',
        json_schema_extra={'custom': 1},
        type='Input',
    )

    assert extra == {
        'type': 'Input',
        'hide': True,
        'icon': 'star',
        'depends': 'mode',
        'custom': 1,
    }


def test_build_field_schema_extra_user_extra_wins():
    extra = build_field_schema_extra(
        hide=True,
        icon='star',
        depends='mode',
        json_schema_extra={'hide': False, 'icon': 'changed', 'depends': 'other'},
    )

    assert extra['hide'] is False
    assert extra['icon'] == 'changed'
    assert extra['depends'] == 'other'


def test_build_field_schema_extra_alias_is_not_emitted():
    extra = build_field_schema_extra(alias='alias')

    assert 'alias' not in extra


def test_build_field_schema_extra_rejects_non_mapping_extra():
    with pytest.raises(TypeError, match='must be a dictionary'):
        build_field_schema_extra(json_schema_extra=[])


def _temporal(**kwargs):
    options = {
        'default': UNSET,
        'default_factory': None,
        'hide': None,
        'description': None,
        'icon': None,
        'title': None,
        'alias': None,
        'depends': None,
        'read_only': None,
        'json_schema_extra': None,
        'kwargs': {},
    }
    options.update(kwargs)
    return temporal_field('Time', **options)


def test_temporal_field_requires_default_or_factory():
    with pytest.raises(TypeError, match='requires default or default_factory'):
        _temporal()


def test_temporal_field_rejects_both_default_forms():
    with pytest.raises(TypeError, match='cannot set both'):
        _temporal(default=1, default_factory=lambda: 2)


def test_temporal_field_adds_component_metadata():
    info = _temporal(default=1, hide=True, icon='clock', read_only=True)

    assert info.json_schema_extra == {
        'type': 'Time',
        'readOnly': True,
        'hide': True,
        'icon': 'clock',
    }


def _boolean(**kwargs):
    options = {
        'default': UNSET,
        'default_factory': None,
        'hide': None,
        'description': None,
        'icon': None,
        'title': None,
        'alias': None,
        'depends': None,
        'json_schema_extra': None,
        'kwargs': {},
    }
    options.update(kwargs)
    return boolean_component_field('Switch', **options)


def test_boolean_component_field_requires_default_or_factory():
    with pytest.raises(TypeError, match='requires default or default_factory'):
        _boolean()


def test_boolean_component_field_rejects_both_default_forms():
    with pytest.raises(TypeError, match='cannot set both'):
        _boolean(default=True, default_factory=lambda: False)


def test_boolean_component_field_adds_component_metadata():
    info = _boolean(default=False, description='开关', title='启用')

    assert info.json_schema_extra == {'type': 'Switch'}
    assert info.description == '开关'
    assert info.title == '启用'
