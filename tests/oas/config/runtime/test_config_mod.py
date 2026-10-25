"""Tests for the decorator-driven ``config_*`` / ``cfg_*`` operations."""

import inspect
from typing import get_type_hints

import pytest
from pydantic import Field

from oas.config.entry import mod_config
from oas.config.entry.error import ConfigError
from oas.config.entry.model import ConfigSetEvent, ModelConfigRef
from oas.config.entry.store import TaskStore
from oas.config.models.args import Input
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_mod import ConfigMod
from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.db.conn import SQLITE_POOL

TASK = 'RuntimeTestTask@default'
TASK_SECOND = 'RuntimeTestTask@second'


class RuntimeTestGroup(GroupBase):
    count: int = Input.int(default=3, ge=0)
    name: str = Input.str(default='group')


class RuntimeTestExtraGroup(GroupBase):
    value: str = Input.str(default='extra')


class RuntimeTestTask(TaskBase):
    main: RuntimeTestGroup = Field(default_factory=RuntimeTestGroup)
    extra: RuntimeTestExtraGroup = Field(default_factory=RuntimeTestExtraGroup)


class RuntimeCopyTask(TaskBase):
    main: RuntimeTestGroup = Field(default_factory=RuntimeTestGroup)
    backup: RuntimeTestGroup = Field(default_factory=RuntimeTestGroup)


class RuntimeDynamicTask(TaskBase):
    groups: list[RuntimeTestExtraGroup] = Field(default_factory=list)


class RuntimePostEditGroup(GroupBase):
    mode: int = Input.int(default=1)
    result: int = Input.int(default=0)

    def post_edit(self, old, new):
        if self.mode == 2:
            self.result = 99


class RuntimePostEditTask(TaskBase):
    main: RuntimePostEditGroup = Field(default_factory=RuntimePostEditGroup)


@pytest.fixture
def config_mod():
    ConfigTable(':memory:').create_table()
    yield ConfigMod(':memory:')
    ConfigTable.singleton_remove(':memory:')
    KeyTable.singleton_remove(':memory:')
    SQLITE_POOL.delete_file(':memory:')


def _event(task: str, group: str, arg: str, value) -> ConfigSetEvent:
    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


# --------------------------------------------------------------------------
# config_read
# --------------------------------------------------------------------------


def test_config_read_fills_model_defaults(config_mod):
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))

    assert data == {
        TASK: {
            'main': {'count': 3, 'name': 'group'},
            'extra': {'value': 'extra'},
        }
    }


def test_config_read_filters_requested_groups(config_mod):
    data = config_mod.config_read(
        ':memory:',
        ModelConfigRef(task=[], group=[(TASK, 'main')]),
    )

    assert data == {TASK: {'main': {'count': 3, 'name': 'group'}}}


def test_config_read_resolves_stored_instance_name(config_mod):
    TaskStore.save(':memory:', RuntimeTestTask(), 'RuntimeTestTask@daily')

    data = config_mod.config_read(
        ':memory:', ModelConfigRef(task=['RuntimeTestTask@daily'], group=[])
    )

    assert data['RuntimeTestTask@daily']['main']['count'] == 3


def test_config_read_ignores_unknown_task(config_mod):
    assert (
        config_mod.config_read(
            ':memory:', ModelConfigRef(task=['NoSuchTask@x'], group=[])
        )
        == {}
    )


# --------------------------------------------------------------------------
# config_set / config_batch_set
# --------------------------------------------------------------------------


def test_config_set_persists_value(config_mod):
    ok, events = config_mod.config_set(':memory:', _event(TASK, 'main', 'count', 5))

    assert ok is True
    assert events == [ConfigSetEvent(task=TASK, group='main', arg='count', value=5)]
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 5


def test_config_set_rejects_invalid_value_and_keeps_stored_value(config_mod):
    config_mod.config_set(':memory:', _event(TASK, 'main', 'count', 5))

    ok, events = config_mod.config_set(':memory:', _event(TASK, 'main', 'count', -1))

    assert ok is False
    assert len(events) == 1
    assert isinstance(events[0].error, ConfigError)
    assert events[0].value == 5
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 5


def test_config_set_reports_unknown_group_and_field(config_mod):
    ok, events = config_mod.config_set(':memory:', _event(TASK, 'missing', 'count', 1))
    assert ok is False
    assert 'No such group' in events[0].error.msg

    ok, events = config_mod.config_set(':memory:', _event(TASK, 'main', 'missing', 1))
    assert ok is False
    assert 'No such field' in events[0].error.msg


def test_config_batch_set_writes_all_groups(config_mod):
    ok, events = config_mod.config_batch_set(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 7),
            _event(TASK, 'extra', 'value', 'changed'),
        ],
    )

    assert ok is True
    assert {(event.group, event.arg, event.value) for event in events} == {
        ('main', 'count', 7),
        ('extra', 'value', 'changed'),
    }
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 7
    assert data[TASK]['extra']['value'] == 'changed'


def test_config_batch_set_rejects_whole_batch_on_error(config_mod):
    ok, _events = config_mod.config_batch_set(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 8),
            _event(TASK, 'main', 'count', -1),
        ],
    )

    assert ok is False
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 3


def test_config_set_runs_post_edit(config_mod):
    ok, events = config_mod.config_set(
        ':memory:',
        _event('RuntimePostEditTask@default', 'main', 'mode', 2),
        post_edit=True,
    )

    assert ok is True
    assert {(event.arg, event.value) for event in events} == {
        ('mode', 2),
        ('result', 99),
    }
    data = config_mod.config_read(
        ':memory:',
        ModelConfigRef(task=['RuntimePostEditTask@default'], group=[]),
    )
    assert data['RuntimePostEditTask@default']['main'] == {
        'mode': 2,
        'result': 99,
    }


def test_config_set_post_edit_without_a_hook(config_mod):
    ok, events = config_mod.config_set(
        ':memory:',
        _event(TASK, 'main', 'count', 4),
        post_edit=True,
    )

    assert ok is True
    assert [(event.arg, event.value) for event in events] == [('count', 4)]


def test_operation_failure_carries_a_config_error():
    ok, events = mod_config._failure(ConfigError('nope'))

    assert ok is False
    assert isinstance(events[0].error, ConfigError)
    assert events[0].error.msg == 'nope'
    assert events[0].task == ''


# --------------------------------------------------------------------------
# config_reset / config_batch_reset
# --------------------------------------------------------------------------


def test_config_reset_restores_default(config_mod):
    config_mod.config_set(':memory:', _event(TASK, 'main', 'count', 9))

    event = config_mod.config_reset(':memory:', _event(TASK, 'main', 'count', 0))

    assert event is not None
    assert event.value == 3
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 3


def test_config_reset_returns_none_for_unknown_group(config_mod):
    assert (
        config_mod.config_reset(':memory:', _event(TASK, 'missing', 'count', 0)) is None
    )


def test_config_batch_reset_only_touches_requested_args(config_mod):
    config_mod.config_batch_set(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 7),
            _event(TASK, 'main', 'name', 'kept'),
        ],
    )

    events = config_mod.config_batch_reset(
        ':memory:', [_event(TASK, 'main', 'count', 0)]
    )

    assert [(event.arg, event.value) for event in events] == [('count', 3)]
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main'] == {'count': 3, 'name': 'kept'}


# --------------------------------------------------------------------------
# config_group_reset / config_group_batch_reset
# --------------------------------------------------------------------------


def test_config_group_reset_returns_every_default(config_mod):
    config_mod.config_batch_set(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 7),
            _event(TASK, 'main', 'name', 'changed'),
        ],
    )

    events = config_mod.config_group_reset(':memory:', _event(TASK, 'main', '', None))

    assert {event.arg for event in events} == {'count', 'name'}
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main'] == {'count': 3, 'name': 'group'}


def test_config_group_batch_reset_deduplicates_groups(config_mod):
    events = config_mod.config_group_batch_reset(
        ':memory:',
        [
            _event(TASK, 'main', '', None),
            _event(TASK, 'main', '', None),
            _event(TASK, 'extra', '', None),
        ],
    )

    assert {(event.group, event.arg) for event in events} == {
        ('main', 'count'),
        ('main', 'name'),
        ('extra', 'value'),
    }


# --------------------------------------------------------------------------
# cfg_task_*
# --------------------------------------------------------------------------


def test_cfg_task_add_creates_taskclass_at_default(config_mod):
    result = config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    assert isinstance(result, tuple)
    ok, events = result
    assert isinstance(events, list)
    assert ok is True
    assert events[0].error is None
    assert {event.task for event in events} == {TASK}
    rows = ConfigTable(':memory:').list_task_rows(TASK)
    assert {row.group for row in rows} == {'main', 'extra'}
    assert {row.taskclass for row in rows} == {'RuntimeTestTask'}


def test_cfg_task_add_honours_custom_name(config_mod):
    ok, _events = config_mod.cfg_task_add(':memory:', 'RuntimeTestTask', 'second')

    assert ok is True
    assert ConfigTable(':memory:').get_group(TASK_SECOND, 'main') is not None


def test_cfg_task_add_rejects_duplicate_and_unknown_class(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')
    assert ok is False
    assert 'already exists' in events[0].error.msg

    ok, events = config_mod.cfg_task_add(':memory:', 'NoSuchTask')
    assert ok is False
    assert 'Unregistered' in events[0].error.msg


def test_cfg_task_del_removes_all_rows(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, _events = config_mod.cfg_task_del(':memory:', TASK)

    assert ok is True
    assert ConfigTable(':memory:').list_task_rows(TASK) == []
    assert config_mod.cfg_task_del(':memory:', TASK)[0] is False


def test_cfg_task_copy_keeps_current_values(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')
    config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', 7)

    ok, _events = config_mod.cfg_task_copy(':memory:', TASK, 'copy')

    assert ok is True
    data = config_mod.config_read(
        ':memory:', ModelConfigRef(task=['RuntimeTestTask@copy'], group=[])
    )
    assert data['RuntimeTestTask@copy']['main']['count'] == 7


def test_cfg_task_reset_restores_defaults(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')
    config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', 7)

    ok, _events = config_mod.cfg_task_reset(':memory:', TASK)

    assert ok is True
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 3


# --------------------------------------------------------------------------
# cfg_group_*
# --------------------------------------------------------------------------


def test_cfg_group_del_and_add_roundtrip(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    assert config_mod.cfg_group_del(':memory:', TASK, 'main')[0] is True
    assert ConfigTable(':memory:').get_group(TASK, 'main') is None

    ok, _events = config_mod.cfg_group_add(':memory:', TASK, 'main', 'RuntimeTestGroup')
    assert ok is True
    assert ConfigTable(':memory:').get_group(TASK, 'main') is not None


def test_cfg_group_add_rejects_unknown_group_and_duplicate(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_group_add(':memory:', TASK, 'main', 'RuntimeTestGroup')
    assert ok is False
    assert 'already exists' in events[0].error.msg

    ok, events = config_mod.cfg_group_add(
        ':memory:', TASK, 'missing', 'RuntimeTestGroup'
    )
    assert ok is False
    assert 'No such group' in events[0].error.msg


def test_cfg_group_copy_between_fields(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeCopyTask@default')
    config_mod.cfg_arg_set(':memory:', 'RuntimeCopyTask@default', 'main', 'count', 7)
    config_mod.cfg_group_del(':memory:', 'RuntimeCopyTask@default', 'backup')

    ok, _events = config_mod.cfg_group_copy(
        ':memory:', 'RuntimeCopyTask@default', 'main', 'backup'
    )

    assert ok is True
    data = config_mod.config_read(
        ':memory:', ModelConfigRef(task=['RuntimeCopyTask@default'], group=[])
    )
    assert data['RuntimeCopyTask@default']['backup']['count'] == 7


def test_cfg_group_reset_restores_defaults(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')
    config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', 7)

    ok, _events = config_mod.cfg_group_reset(':memory:', TASK, 'main')

    assert ok is True
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 3


DYNAMIC = 'RuntimeDynamicTask@default'


def test_cfg_group_add_appends_a_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')

    ok, events = config_mod.cfg_group_add(
        ':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup'
    )

    assert ok is True
    assert [event.group for event in events] == ['groups@0']
    assert events[0].arg == 'value'
    assert ConfigTable(':memory:').get_group(DYNAMIC, 'groups@0') is not None


def test_cfg_group_add_inserts_a_dynamic_instance_at_index(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    for _ in range(2):
        config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')

    ok, _events = config_mod.cfg_group_add(
        ':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup', index=1
    )

    assert ok is True
    assert sorted(
        row.group for row in ConfigTable(':memory:').list_task_rows(DYNAMIC)
    ) == ['groups@0', 'groups@1', 'groups@2']
    assert len(TaskStore.load(':memory:', RuntimeDynamicTask, DYNAMIC).groups) == 3


def test_cfg_group_add_rejects_out_of_range_and_conflicting_index(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')

    ok, events = config_mod.cfg_group_add(
        ':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup', index=1
    )
    assert ok is False
    assert 'out of range' in events[0].error.msg

    ok, events = config_mod.cfg_group_add(
        ':memory:', DYNAMIC, 'groups@2', 'RuntimeTestExtraGroup', index=1
    )
    assert ok is False
    assert 'Conflicting index' in events[0].error.msg


def test_cfg_group_del_resequences_a_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    for _value in ('a', 'b', 'c'):
        config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')
    config_mod.cfg_arg_batch_set(
        ':memory:',
        [
            _event(DYNAMIC, 'groups@0', 'value', 'a'),
            _event(DYNAMIC, 'groups@1', 'value', 'b'),
            _event(DYNAMIC, 'groups@2', 'value', 'c'),
        ],
    )

    ok, events = config_mod.cfg_group_del(':memory:', DYNAMIC, 'groups@1')

    assert ok is True
    assert [event.group for event in events] == ['groups@0', 'groups@1']
    stored = TaskStore.load(':memory:', RuntimeDynamicTask, DYNAMIC)
    assert [group.value for group in stored.groups] == ['a', 'c']


def test_cfg_group_del_rejects_a_missing_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')

    ok, events = config_mod.cfg_group_del(':memory:', DYNAMIC, 'groups@0')

    assert ok is False
    assert 'No such Group instance' in events[0].error.msg


def test_cfg_group_reset_resets_one_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')
    config_mod.cfg_arg_set(':memory:', DYNAMIC, 'groups@0', 'value', 'changed')

    ok, events = config_mod.cfg_group_reset(':memory:', DYNAMIC, 'groups@0')

    assert ok is True
    assert events[0].value == 'extra'
    stored = TaskStore.load(':memory:', RuntimeDynamicTask, DYNAMIC)
    assert [group.value for group in stored.groups] == ['extra']


def test_cfg_group_copy_appends_a_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')
    config_mod.cfg_arg_set(':memory:', DYNAMIC, 'groups@0', 'value', 'copied')

    ok, _events = config_mod.cfg_group_copy(':memory:', DYNAMIC, 'groups@0', 'groups')

    assert ok is True
    stored = TaskStore.load(':memory:', RuntimeDynamicTask, DYNAMIC)
    assert [group.value for group in stored.groups] == ['copied', 'copied']


def test_cfg_group_copy_rejects_mixing_static_and_dynamic(config_mod):
    config_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')

    ok, events = config_mod.cfg_group_copy(
        ':memory:', 'MoreErrTask@one', 'main', 'dynamic'
    )

    assert ok is False
    assert 'static Group and a dynamic Group list' in events[0].error.msg


def test_cfg_task_copy_copies_dynamic_instances(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')

    ok, _events = config_mod.cfg_task_copy(':memory:', DYNAMIC, 'copy')

    assert ok is True
    stored = TaskStore.load(':memory:', RuntimeDynamicTask, 'RuntimeDynamicTask@copy')
    assert len(stored.groups) == 1


def test_dynamic_address_errors(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')

    ok, events = config_mod.cfg_arg_set(':memory:', DYNAMIC, 'groups', 'value', 'x')
    assert ok is False
    assert 'Dynamic Group requires an index' in events[0].error.msg

    ok, events = config_mod.cfg_arg_get(':memory:', DYNAMIC, 'groups@4', 'value')
    assert ok is False
    assert 'No such Group instance' in events[0].error.msg


def test_static_group_rejects_an_index_address(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_arg_set(':memory:', TASK, 'main@0', 'count', 4)

    assert ok is False
    assert 'Static Group does not take an index' in events[0].error.msg


def test_config_set_addresses_a_dynamic_instance(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeDynamicTask')
    config_mod.cfg_group_add(':memory:', DYNAMIC, 'groups', 'RuntimeTestExtraGroup')

    ok, events = config_mod.config_set(
        ':memory:', _event(DYNAMIC, 'groups@0', 'value', 'set')
    )

    assert ok is True
    assert events[0].group == 'groups@0'
    stored = TaskStore.load(':memory:', RuntimeDynamicTask, DYNAMIC)
    assert stored.groups[0].value == 'set'


def test_group_operations_do_not_load_the_whole_task(config_mod, monkeypatch):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')
    calls = []
    original = TaskStore.load

    def counted(config_name, *args, **kwargs):
        calls.append((config_name, *args))
        return original(config_name, *args, **kwargs)

    monkeypatch.setattr(TaskStore, 'load', counted)

    assert config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', 4)[0]
    ok, events = config_mod.cfg_arg_get(':memory:', TASK, 'main', 'count')
    assert events[0].value == 4
    assert config_mod.cfg_group_reset(':memory:', TASK, 'main')[0]
    assert config_mod.config_set(':memory:', _event(TASK, 'main', 'count', 5))[0]

    assert calls == []


# --------------------------------------------------------------------------
# cfg_arg_*
# --------------------------------------------------------------------------


def test_cfg_arg_get_set_reset(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_arg_get(':memory:', TASK, 'main', 'count')
    assert ok is True
    assert events[0].value == 3

    ok, events = config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', 7)
    assert ok is True
    assert events[0].value == 7

    ok, events = config_mod.cfg_arg_reset(':memory:', TASK, 'main', 'count')
    assert ok is True
    assert events[0].value == 3


def test_cfg_arg_get_returns_default_on_missing(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_arg_get(
        ':memory:', TASK, 'main', 'missing', default='fallback'
    )

    assert ok is False
    assert events[0].value == 'fallback'
    assert events[0].error is not None


def test_cfg_arg_batch_set_and_reset(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_arg_batch_set(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 7),
            _event(TASK, 'extra', 'value', 'changed'),
        ],
    )
    assert ok is True
    assert {(event.group, event.arg, event.value) for event in events} == {
        ('main', 'count', 7),
        ('extra', 'value', 'changed'),
    }

    ok, _events = config_mod.cfg_arg_batch_reset(
        ':memory:',
        [
            _event(TASK, 'main', 'count', 0),
            _event(TASK, 'extra', 'value', ''),
        ],
    )
    assert ok is True
    data = config_mod.config_read(':memory:', ModelConfigRef(task=[TASK], group=[]))
    assert data[TASK]['main']['count'] == 3
    assert data[TASK]['extra']['value'] == 'extra'


def test_cfg_arg_set_reports_validation_error(config_mod):
    config_mod.cfg_task_add(':memory:', 'RuntimeTestTask')

    ok, events = config_mod.cfg_arg_set(':memory:', TASK, 'main', 'count', -1)

    assert ok is False
    assert isinstance(events[0].error, ConfigError)
    assert events[0].value == 3


# --------------------------------------------------------------------------
# Decorator contract / API surface
# --------------------------------------------------------------------------


def test_decorator_injects_result_into_the_method(config_mod):
    assert config_mod.config_read(
        ':memory:', ModelConfigRef(task=[TASK], group=[])
    ) == {TASK: {'main': {'count': 3, 'name': 'group'}, 'extra': {'value': 'extra'}}}


def test_cfg_api_is_typed_and_uses_unified_result():
    expected = {
        'cfg_task_add',
        'cfg_task_copy',
        'cfg_task_del',
        'cfg_task_reset',
        'cfg_group_add',
        'cfg_group_copy',
        'cfg_group_del',
        'cfg_group_reset',
        'cfg_arg_batch_reset',
        'cfg_arg_batch_set',
        'cfg_arg_get',
        'cfg_arg_reset',
        'cfg_arg_set',
    }
    names = {name for name in dir(ConfigMod) if name.startswith('cfg_')}
    assert names == expected

    expected_return = tuple[bool, list[ConfigSetEvent]]
    expected_raw_return = 'tuple[bool, list[ConfigSetEvent]]'

    for name in names:
        method = getattr(ConfigMod, name)
        hints = get_type_hints(method)
        # The source uses deferred annotations, so the public signature keeps
        # the raw annotation text while ``get_type_hints`` resolves it.
        assert hints['return'] == expected_return, name
        raw_return = inspect.signature(method).return_annotation
        assert raw_return in (expected_return, expected_raw_return), name
        parameters = list(inspect.signature(method).parameters)
        assert 'result' not in parameters, name
        assert parameters[1] == 'config_name', name


def test_cfg_task_add_defaults_to_default_name():
    signature = inspect.signature(ConfigMod.cfg_task_add)

    assert signature.parameters['name'].default == 'default'
    assert signature.parameters['taskclass'].default is inspect.Parameter.empty


class EdgeGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    value: str = Input.str(default='v')


class EdgeFailPostGroup(GroupBase):
    count: int = Input.int(default=1)

    def post_edit(self, old, requested):
        raise ValueError('post_edit rejected')


class EdgeTask(TaskBase):
    main: EdgeGroup = Field(default_factory=EdgeGroup)
    extra: EdgeGroup = Field(default_factory=EdgeGroup)


class EdgeFailPostTask(TaskBase):
    main: EdgeFailPostGroup = Field(default_factory=EdgeFailPostGroup)


def _edge_event(task, group, arg, value):
    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


@pytest.fixture
def edge_mod(memory_config):
    return ConfigMod(':memory:')


def test_empty_batches_are_noops(edge_mod):
    assert edge_mod.config_batch_set(':memory:', []) == (True, [])
    assert edge_mod.config_batch_reset(':memory:', []) == []
    assert edge_mod.config_group_batch_reset(':memory:', []) == []


def test_batch_set_duplicate_arg_uses_last_value(edge_mod):
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'one')

    ok, _results = edge_mod.config_batch_set(
        ':memory:',
        [
            _edge_event('EdgeTask@one', 'main', 'count', 2),
            _edge_event('EdgeTask@one', 'main', 'count', 3),
        ],
    )

    assert ok is True
    _ok, events = edge_mod.cfg_arg_get(':memory:', 'EdgeTask@one', 'main', 'count')
    assert events[0].value == 3


def test_batch_set_rolls_back_all_groups_on_error(edge_mod):
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'one')

    ok, _results = edge_mod.config_batch_set(
        ':memory:',
        [
            _edge_event('EdgeTask@one', 'main', 'count', 5),
            _edge_event('EdgeTask@one', 'extra', 'count', -1),
        ],
    )

    assert ok is False
    _ok, events = edge_mod.cfg_arg_get(':memory:', 'EdgeTask@one', 'main', 'count')
    assert events[0].value == 1
    _ok, events = edge_mod.cfg_arg_get(':memory:', 'EdgeTask@one', 'extra', 'value')
    assert events[0].value == 'v'


def test_post_edit_failure_does_not_write(edge_mod):
    edge_mod.cfg_task_add(':memory:', 'EdgeFailPostTask', 'one')

    ok, events = edge_mod.cfg_arg_set(
        ':memory:',
        'EdgeFailPostTask@one',
        'main',
        'count',
        2,
        post_edit=True,
    )

    assert ok is False
    assert 'post_edit failed' in events[0].error.msg
    _ok, events = edge_mod.cfg_arg_get(
        ':memory:', 'EdgeFailPostTask@one', 'main', 'count'
    )
    assert events[0].value == 1


def test_task_add_rejects_invalid_instance_names(edge_mod):
    ok, events = edge_mod.cfg_task_add(':memory:', 'EdgeTask', '')

    assert ok is False
    assert 'task name' in events[0].error.msg

    ok, events = edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'a@b')

    assert ok is False
    assert '@' in events[0].error.msg


def test_task_copy_rejects_existing_target(edge_mod):
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'one')
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'two')

    ok, events = edge_mod.cfg_task_copy(':memory:', 'EdgeTask@one', 'two')

    assert ok is False
    assert 'already exists' in events[0].error.msg


def test_group_copy_across_tasks(edge_mod):
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'one')
    edge_mod.cfg_task_add(':memory:', 'EdgeTask', 'two')
    edge_mod.cfg_arg_set(':memory:', 'EdgeTask@one', 'main', 'value', 'copied')
    # ``cfg_task_add`` seeds every group, so make the target row absent first.
    assert edge_mod.cfg_group_del(':memory:', 'EdgeTask@two', 'extra')[0] is True

    ok, _events = edge_mod.cfg_group_copy(
        ':memory:',
        'EdgeTask@one',
        'main',
        'extra',
        'EdgeTask@two',
    )

    assert ok is True
    _ok, events = edge_mod.cfg_arg_get(':memory:', 'EdgeTask@two', 'extra', 'value')
    assert events[0].value == 'copied'


def test_unknown_task_and_group_operations_fail(edge_mod):
    assert edge_mod.cfg_task_del(':memory:', 'EdgeTask@missing')[0] is False
    assert edge_mod.cfg_task_reset(':memory:', 'EdgeTask@missing')[0] is False
    assert edge_mod.cfg_group_del(':memory:', 'EdgeTask@missing', 'main')[0] is False
    assert edge_mod.cfg_group_reset(':memory:', 'EdgeTask@missing', 'nope')[0] is False


class MoreErrGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    value: str = Input.str(default='v')


class MoreErrTask(TaskBase):
    main: MoreErrGroup = Field(default_factory=MoreErrGroup)
    extra: MoreErrGroup = Field(default_factory=MoreErrGroup)
    dynamic: list[MoreErrGroup] = Field(default_factory=list)


def _more_event(task, group, arg, value):
    from oas.config.entry.model import ConfigSetEvent

    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


@pytest.fixture
def more_mod(memory_config):
    return ConfigMod(':memory:')


def test_config_set_unknown_task_reports_error(more_mod):
    ok, events = more_mod.config_set(
        ':memory:', _more_event('NoSuchTask@missing', 'main', 'count', 2)
    )

    assert ok is False
    assert events[0].error is not None


def test_config_set_unknown_group_and_field_report_errors(more_mod):
    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')

    ok, events = more_mod.config_set(
        ':memory:', _more_event('MoreErrTask@one', 'missing', 'count', 2)
    )
    assert ok is False
    assert events[0].error is not None

    ok, events = more_mod.config_set(
        ':memory:', _more_event('MoreErrTask@one', 'main', 'missing', 2)
    )
    assert ok is False
    assert events[0].error is not None


def test_config_read_empty_ref_and_unknown_task(more_mod):
    assert more_mod.config_read(':memory:', ModelConfigRef(task=[], group=[])) == {}
    assert (
        more_mod.config_read(
            ':memory:', ModelConfigRef(task=['NoSuchTask@missing'], group=[])
        )
        == {}
    )


def test_config_reset_unknown_task_returns_none(more_mod):
    assert (
        more_mod.config_reset(
            ':memory:', _more_event('NoSuchTask@missing', 'main', 'count', 1)
        )
        is None
    )


def test_config_group_reset_unknown_group_returns_empty(more_mod):
    assert (
        more_mod.config_group_reset(
            ':memory:', _more_event('NoSuchTask@missing', 'main', 'count', 1)
        )
        == []
    )
    assert more_mod.config_group_batch_reset(':memory:', []) == []


def test_cfg_arg_set_unknown_task_group_and_field(more_mod):
    assert (
        more_mod.cfg_arg_set(':memory:', 'NoSuchTask@missing', 'main', 'count', 2)[0]
        is False
    )

    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')
    assert (
        more_mod.cfg_arg_set(':memory:', 'MoreErrTask@one', 'missing', 'count', 2)[0]
        is False
    )
    assert (
        more_mod.cfg_arg_set(':memory:', 'MoreErrTask@one', 'main', 'missing', 2)[0]
        is False
    )


def test_cfg_arg_set_invalid_value_leaves_default(more_mod):
    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')

    ok, _events = more_mod.cfg_arg_set(
        ':memory:', 'MoreErrTask@one', 'main', 'count', -1
    )

    assert ok is False
    _ok, events = more_mod.cfg_arg_get(':memory:', 'MoreErrTask@one', 'main', 'count')
    assert events[0].value == 1


def test_cfg_group_add_rejects_missing_task_and_mismatch(more_mod):
    assert (
        more_mod.cfg_group_add(
            ':memory:', 'NoSuchTask@missing', 'main', 'MoreErrGroup'
        )[0]
        is False
    )

    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')
    assert (
        more_mod.cfg_group_add(':memory:', 'MoreErrTask@one', 'main', 'WrongGroup')[0]
        is False
    )
    ok, events = more_mod.cfg_group_add(
        ':memory:', 'MoreErrTask@one', 'dynamic', 'MoreErrGroup'
    )
    assert ok is True
    assert {event.group for event in events} == {'dynamic@0'}
    assert {event.arg for event in events} == {'count', 'value'}


def test_cfg_group_copy_rejects_same_source_and_missing_targets(more_mod):
    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')
    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'two')
    more_mod.cfg_group_del(':memory:', 'MoreErrTask@two', 'extra')

    assert (
        more_mod.cfg_group_copy(':memory:', 'MoreErrTask@one', 'main', 'main')[0]
        is False
    )
    assert (
        more_mod.cfg_group_copy(
            ':memory:',
            'MoreErrTask@one',
            'main',
            'extra',
            'NoSuchTask@missing',
        )[0]
        is False
    )
    assert (
        more_mod.cfg_group_copy(
            ':memory:', 'MoreErrTask@one', 'main', 'missing', 'MoreErrTask@two'
        )[0]
        is False
    )


def test_cfg_task_copy_rejects_missing_source_self_and_invalid_name(more_mod):
    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')

    assert more_mod.cfg_task_copy(':memory:', 'NoSuchTask@missing', 'two')[0] is False
    assert more_mod.cfg_task_copy(':memory:', 'MoreErrTask@one', 'one')[0] is False
    assert more_mod.cfg_task_copy(':memory:', 'MoreErrTask@one', 'a@b')[0] is False


def test_cfg_task_and_group_missing_operations(more_mod):
    assert more_mod.cfg_task_del(':memory:', 'NoSuchTask@missing')[0] is False
    assert more_mod.cfg_task_reset(':memory:', 'NoSuchTask@missing')[0] is False
    assert more_mod.cfg_group_del(':memory:', 'NoSuchTask@missing', 'main')[0] is False
    assert (
        more_mod.cfg_group_reset(':memory:', 'NoSuchTask@missing', 'missing')[0]
        is False
    )


def test_cfg_arg_batch_set_empty_and_invalid(more_mod):
    assert more_mod.cfg_arg_batch_set(':memory:', [])[0] is True

    more_mod.cfg_task_add(':memory:', 'MoreErrTask', 'one')
    ok, _events = more_mod.cfg_arg_batch_set(
        ':memory:',
        [
            _more_event('MoreErrTask@one', 'main', 'count', 2),
            _more_event('MoreErrTask@one', 'extra', 'count', -1),
        ],
    )

    assert ok is False
    _ok, events = more_mod.cfg_arg_get(':memory:', 'MoreErrTask@one', 'main', 'count')
    assert events[0].value == 1


def test_cfg_arg_get_missing_returns_default(more_mod):
    _ok, events = more_mod.cfg_arg_get(
        ':memory:', 'NoSuchTask@missing', 'main', 'count', default=42
    )

    assert events[0].value == 42
