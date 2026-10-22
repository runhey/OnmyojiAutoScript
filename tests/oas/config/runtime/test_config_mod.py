"""Tests for the decorator-driven ``config_*`` / ``cfg_*`` operations."""

import inspect
from typing import get_type_hints

import pytest
from pydantic import Field

from oas.config.entry.error import ConfigError
from oas.config.entry.mod_store import TaskStore
from oas.config.entry.model import ConfigResult, ConfigSetEvent, ModelConfigRef
from oas.config.models.args import Input
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_mod import ConfigMod
from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.db.conn import SQLITE_POOL

TASK = "RuntimeTestTask@default"
TASK_SECOND = "RuntimeTestTask@second"


class RuntimeTestGroup(GroupBase):
    count: int = Input.int(default=3, ge=0)
    name: str = Input.str(default="group")


class RuntimeTestExtraGroup(GroupBase):
    value: str = Input.str(default="extra")


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
    ConfigTable(":memory:").create_table()
    yield ConfigMod(":memory:")
    ConfigTable.singleton_remove(":memory:")
    KeyTable.singleton_remove(":memory:")
    SQLITE_POOL.delete_file(":memory:")


def _event(task: str, group: str, arg: str, value) -> ConfigSetEvent:
    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


# --------------------------------------------------------------------------
# config_read
# --------------------------------------------------------------------------


def test_config_read_fills_model_defaults(config_mod):
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )

    assert data == {
        TASK: {
            "main": {"count": 3, "name": "group"},
            "extra": {"value": "extra"},
        }
    }


def test_config_read_filters_requested_groups(config_mod):
    data = config_mod.config_read(
        ":memory:",
        ModelConfigRef(task=[], group=[(TASK, "main")]),
    )

    assert data == {TASK: {"main": {"count": 3, "name": "group"}}}


def test_config_read_resolves_stored_instance_name(config_mod):
    TaskStore(":memory:").save(RuntimeTestTask(), "RuntimeTestTask@daily")

    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=["RuntimeTestTask@daily"], group=[])
    )

    assert data["RuntimeTestTask@daily"]["main"]["count"] == 3


def test_config_read_ignores_unknown_task(config_mod):
    assert (
        config_mod.config_read(
            ":memory:", ModelConfigRef(task=["NoSuchTask@x"], group=[])
        )
        == {}
    )


# --------------------------------------------------------------------------
# config_set / config_batch_set
# --------------------------------------------------------------------------


def test_config_set_persists_value(config_mod):
    ok, events = config_mod.config_set(
        ":memory:", _event(TASK, "main", "count", 5)
    )

    assert ok is True
    assert events == [
        ConfigSetEvent(task=TASK, group="main", arg="count", value=5)
    ]
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 5


def test_config_set_rejects_invalid_value_and_keeps_stored_value(config_mod):
    config_mod.config_set(":memory:", _event(TASK, "main", "count", 5))

    ok, events = config_mod.config_set(
        ":memory:", _event(TASK, "main", "count", -1)
    )

    assert ok is False
    assert len(events) == 1
    assert isinstance(events[0].error, ConfigError)
    assert events[0].value == 5
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 5


def test_config_set_reports_unknown_group_and_field(config_mod):
    ok, events = config_mod.config_set(
        ":memory:", _event(TASK, "missing", "count", 1)
    )
    assert ok is False
    assert "No such group" in events[0].error.msg

    ok, events = config_mod.config_set(
        ":memory:", _event(TASK, "main", "missing", 1)
    )
    assert ok is False
    assert "No such field" in events[0].error.msg


def test_config_batch_set_writes_all_groups(config_mod):
    ok, events = config_mod.config_batch_set(
        ":memory:",
        [
            _event(TASK, "main", "count", 7),
            _event(TASK, "extra", "value", "changed"),
        ],
    )

    assert ok is True
    assert {(event.group, event.arg, event.value) for event in events} == {
        ("main", "count", 7),
        ("extra", "value", "changed"),
    }
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 7
    assert data[TASK]["extra"]["value"] == "changed"


def test_config_batch_set_rejects_whole_batch_on_error(config_mod):
    ok, _events = config_mod.config_batch_set(
        ":memory:",
        [
            _event(TASK, "main", "count", 8),
            _event(TASK, "main", "count", -1),
        ],
    )

    assert ok is False
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 3


def test_config_set_runs_post_edit(config_mod):
    ok, events = config_mod.config_set(
        ":memory:", _event("RuntimePostEditTask@default", "main", "mode", 2),
        post_edit=True,
    )

    assert ok is True
    assert {(event.arg, event.value) for event in events} == {
        ("mode", 2),
        ("result", 99),
    }
    data = config_mod.config_read(
        ":memory:",
        ModelConfigRef(task=["RuntimePostEditTask@default"], group=[]),
    )
    assert data["RuntimePostEditTask@default"]["main"] == {
        "mode": 2,
        "result": 99,
    }


# --------------------------------------------------------------------------
# config_reset / config_batch_reset
# --------------------------------------------------------------------------


def test_config_reset_restores_default(config_mod):
    config_mod.config_set(":memory:", _event(TASK, "main", "count", 9))

    event = config_mod.config_reset(
        ":memory:", _event(TASK, "main", "count", 0)
    )

    assert event is not None
    assert event.value == 3
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 3


def test_config_reset_returns_none_for_unknown_group(config_mod):
    assert (
        config_mod.config_reset(
            ":memory:", _event(TASK, "missing", "count", 0)
        )
        is None
    )


def test_config_batch_reset_only_touches_requested_args(config_mod):
    config_mod.config_batch_set(
        ":memory:",
        [
            _event(TASK, "main", "count", 7),
            _event(TASK, "main", "name", "kept"),
        ],
    )

    events = config_mod.config_batch_reset(
        ":memory:", [_event(TASK, "main", "count", 0)]
    )

    assert [(event.arg, event.value) for event in events] == [("count", 3)]
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"] == {"count": 3, "name": "kept"}


# --------------------------------------------------------------------------
# config_group_reset / config_group_batch_reset
# --------------------------------------------------------------------------


def test_config_group_reset_returns_every_default(config_mod):
    config_mod.config_batch_set(
        ":memory:",
        [
            _event(TASK, "main", "count", 7),
            _event(TASK, "main", "name", "changed"),
        ],
    )

    events = config_mod.config_group_reset(
        ":memory:", _event(TASK, "main", "", None)
    )

    assert {event.arg for event in events} == {"count", "name"}
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"] == {"count": 3, "name": "group"}


def test_config_group_batch_reset_deduplicates_groups(config_mod):
    events = config_mod.config_group_batch_reset(
        ":memory:",
        [
            _event(TASK, "main", "", None),
            _event(TASK, "main", "", None),
            _event(TASK, "extra", "", None),
        ],
    )

    assert {(event.group, event.arg) for event in events} == {
        ("main", "count"),
        ("main", "name"),
        ("extra", "value"),
    }


# --------------------------------------------------------------------------
# cfg_task_*
# --------------------------------------------------------------------------


def test_cfg_task_add_creates_taskclass_at_default(config_mod):
    result = config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    assert isinstance(result, ConfigResult)
    assert result.success is True
    assert result.error is None
    assert {event.task for event in result.events} == {TASK}
    rows = ConfigTable(":memory:").list_task_rows(TASK)
    assert {row.group for row in rows} == {"main", "extra"}
    assert {row.taskclass for row in rows} == {"RuntimeTestTask"}


def test_cfg_task_add_honours_custom_name(config_mod):
    result = config_mod.cfg_task_add(":memory:", "RuntimeTestTask", "second")

    assert result.success is True
    assert ConfigTable(":memory:").get_group(TASK_SECOND, "main") is not None


def test_cfg_task_add_rejects_duplicate_and_unknown_class(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    duplicate = config_mod.cfg_task_add(":memory:", "RuntimeTestTask")
    assert duplicate.success is False
    assert "already exists" in duplicate.error.msg

    unknown = config_mod.cfg_task_add(":memory:", "NoSuchTask")
    assert unknown.success is False
    assert "Unregistered" in unknown.error.msg


def test_cfg_task_del_removes_all_rows(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    result = config_mod.cfg_task_del(":memory:", TASK)

    assert result.success is True
    assert ConfigTable(":memory:").list_task_rows(TASK) == []
    assert config_mod.cfg_task_del(":memory:", TASK).success is False


def test_cfg_task_copy_keeps_current_values(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")
    config_mod.cfg_arg_set(":memory:", TASK, "main", "count", 7)

    result = config_mod.cfg_task_copy(":memory:", TASK, "copy")

    assert result.success is True
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=["RuntimeTestTask@copy"], group=[])
    )
    assert data["RuntimeTestTask@copy"]["main"]["count"] == 7


def test_cfg_task_reset_restores_defaults(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")
    config_mod.cfg_arg_set(":memory:", TASK, "main", "count", 7)

    result = config_mod.cfg_task_reset(":memory:", TASK)

    assert result.success is True
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 3


# --------------------------------------------------------------------------
# cfg_group_*
# --------------------------------------------------------------------------


def test_cfg_group_del_and_add_roundtrip(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    assert config_mod.cfg_group_del(":memory:", TASK, "main").success is True
    assert ConfigTable(":memory:").get_group(TASK, "main") is None

    result = config_mod.cfg_group_add(
        ":memory:", TASK, "main", "RuntimeTestGroup"
    )
    assert result.success is True
    assert ConfigTable(":memory:").get_group(TASK, "main") is not None


def test_cfg_group_add_rejects_unknown_group_and_duplicate(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    duplicate = config_mod.cfg_group_add(
        ":memory:", TASK, "main", "RuntimeTestGroup"
    )
    assert duplicate.success is False
    assert "already exists" in duplicate.error.msg

    unknown = config_mod.cfg_group_add(
        ":memory:", TASK, "missing", "RuntimeTestGroup"
    )
    assert unknown.success is False
    assert "dynamic Group" in unknown.error.msg


def test_cfg_group_copy_between_fields(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeCopyTask@default")
    config_mod.cfg_arg_set(":memory:", "RuntimeCopyTask@default", "main", "count", 7)
    config_mod.cfg_group_del(":memory:", "RuntimeCopyTask@default", "backup")

    result = config_mod.cfg_group_copy(
        ":memory:", "RuntimeCopyTask@default", "main", "backup"
    )

    assert result.success is True
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=["RuntimeCopyTask@default"], group=[])
    )
    assert data["RuntimeCopyTask@default"]["backup"]["count"] == 7


def test_cfg_group_reset_restores_defaults(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")
    config_mod.cfg_arg_set(":memory:", TASK, "main", "count", 7)

    result = config_mod.cfg_group_reset(":memory:", TASK, "main")

    assert result.success is True
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 3


def test_cfg_group_add_rejects_dynamic_field(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeDynamicTask")

    result = config_mod.cfg_group_add(
        ":memory:",
        "RuntimeDynamicTask@default",
        "groups",
        "RuntimeTestExtraGroup",
    )

    assert result.success is False
    assert "dynamic Group" in result.error.msg


def test_group_operations_do_not_load_the_whole_task(config_mod, monkeypatch):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")
    calls = []
    original = TaskStore.load

    def counted(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(TaskStore, "load", counted)

    assert config_mod.cfg_arg_set(
        ":memory:", TASK, "main", "count", 4
    ).success
    assert config_mod.cfg_arg_get(
        ":memory:", TASK, "main", "count"
    ).value == 4
    assert config_mod.cfg_group_reset(":memory:", TASK, "main").success
    assert config_mod.config_set(
        ":memory:", _event(TASK, "main", "count", 5)
    )[0]

    assert calls == []


# --------------------------------------------------------------------------
# cfg_arg_*
# --------------------------------------------------------------------------


def test_cfg_arg_get_set_reset(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    read = config_mod.cfg_arg_get(":memory:", TASK, "main", "count")
    assert read.success is True
    assert read.value == 3

    written = config_mod.cfg_arg_set(":memory:", TASK, "main", "count", 7)
    assert written.success is True
    assert written.value == 7

    reset = config_mod.cfg_arg_reset(":memory:", TASK, "main", "count")
    assert reset.success is True
    assert reset.value == 3


def test_cfg_arg_get_returns_default_on_missing(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    result = config_mod.cfg_arg_get(
        ":memory:", TASK, "main", "missing", default="fallback"
    )

    assert result.success is False
    assert result.value == "fallback"
    assert result.error is not None


def test_cfg_arg_batch_set_and_reset(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    written = config_mod.cfg_arg_batch_set(
        ":memory:",
        [
            _event(TASK, "main", "count", 7),
            _event(TASK, "extra", "value", "changed"),
        ],
    )
    assert written.success is True
    assert {(event.group, event.arg, event.value) for event in written.events} == {
        ("main", "count", 7),
        ("extra", "value", "changed"),
    }

    reset = config_mod.cfg_arg_batch_reset(
        ":memory:",
        [
            _event(TASK, "main", "count", 0),
            _event(TASK, "extra", "value", ""),
        ],
    )
    assert reset.success is True
    data = config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    )
    assert data[TASK]["main"]["count"] == 3
    assert data[TASK]["extra"]["value"] == "extra"


def test_cfg_arg_set_reports_validation_error(config_mod):
    config_mod.cfg_task_add(":memory:", "RuntimeTestTask")

    result = config_mod.cfg_arg_set(":memory:", TASK, "main", "count", -1)

    assert result.success is False
    assert isinstance(result.error, ConfigError)
    assert result.events[0].value == 3


# --------------------------------------------------------------------------
# Decorator contract / API surface
# --------------------------------------------------------------------------


def test_decorator_injects_result_into_the_method(config_mod):
    assert config_mod.config_read(
        ":memory:", ModelConfigRef(task=[TASK], group=[])
    ) == {TASK: {"main": {"count": 3, "name": "group"}, "extra": {"value": "extra"}}}


def test_cfg_api_is_typed_and_uses_unified_result():
    expected = {
        "cfg_task_add",
        "cfg_task_copy",
        "cfg_task_del",
        "cfg_task_reset",
        "cfg_group_add",
        "cfg_group_copy",
        "cfg_group_del",
        "cfg_group_reset",
        "cfg_arg_batch_reset",
        "cfg_arg_batch_set",
        "cfg_arg_get",
        "cfg_arg_reset",
        "cfg_arg_set",
    }
    names = {name for name in dir(ConfigMod) if name.startswith("cfg_")}
    assert names == expected

    for name in names:
        method = getattr(ConfigMod, name)
        hints = get_type_hints(method)
        assert hints["return"] is ConfigResult, name
        parameters = list(inspect.signature(method).parameters)
        assert "result" not in parameters, name
        assert parameters[1] == "config_name", name


def test_cfg_task_add_defaults_to_default_name():
    signature = inspect.signature(ConfigMod.cfg_task_add)

    assert signature.parameters["name"].default == "default"
    assert signature.parameters["taskclass"].default is inspect.Parameter.empty


class EdgeGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    value: str = Input.str(default="v")


class EdgeFailPostGroup(GroupBase):
    count: int = Input.int(default=1)

    def post_edit(self, old, requested):
        raise ValueError("post_edit rejected")


class EdgeTask(TaskBase):
    main: EdgeGroup = Field(default_factory=EdgeGroup)
    extra: EdgeGroup = Field(default_factory=EdgeGroup)


class EdgeFailPostTask(TaskBase):
    main: EdgeFailPostGroup = Field(default_factory=EdgeFailPostGroup)


def _edge_event(task, group, arg, value):
    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


@pytest.fixture
def edge_mod(memory_config):
    return ConfigMod(":memory:")


def test_empty_batches_are_noops(edge_mod):
    assert edge_mod.config_batch_set(":memory:", []) == (True, [])
    assert edge_mod.config_batch_reset(":memory:", []) == []
    assert edge_mod.config_group_batch_reset(":memory:", []) == []


def test_batch_set_duplicate_arg_uses_last_value(edge_mod):
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "one")

    ok, _results = edge_mod.config_batch_set(
        ":memory:",
        [
            _edge_event("EdgeTask@one", "main", "count", 2),
            _edge_event("EdgeTask@one", "main", "count", 3),
        ],
    )

    assert ok is True
    assert edge_mod.cfg_arg_get(":memory:", "EdgeTask@one", "main", "count").value == 3


def test_batch_set_rolls_back_all_groups_on_error(edge_mod):
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "one")

    ok, _results = edge_mod.config_batch_set(
        ":memory:",
        [
            _edge_event("EdgeTask@one", "main", "count", 5),
            _edge_event("EdgeTask@one", "extra", "count", -1),
        ],
    )

    assert ok is False
    assert edge_mod.cfg_arg_get(":memory:", "EdgeTask@one", "main", "count").value == 1
    assert edge_mod.cfg_arg_get(":memory:", "EdgeTask@one", "extra", "value").value == "v"


def test_post_edit_failure_does_not_write(edge_mod):
    edge_mod.cfg_task_add(":memory:", "EdgeFailPostTask", "one")

    result = edge_mod.cfg_arg_set(
        ":memory:",
        "EdgeFailPostTask@one",
        "main",
        "count",
        2,
        post_edit=True,
    )

    assert result.success is False
    assert "post_edit failed" in result.error.msg
    assert (
        edge_mod.cfg_arg_get(":memory:", "EdgeFailPostTask@one", "main", "count").value
        == 1
    )


def test_task_add_rejects_invalid_instance_names(edge_mod):
    empty = edge_mod.cfg_task_add(":memory:", "EdgeTask", "")
    with_at = edge_mod.cfg_task_add(":memory:", "EdgeTask", "a@b")

    assert empty.success is False
    assert "task name" in empty.error.msg
    assert with_at.success is False
    assert "@" in with_at.error.msg


def test_task_copy_rejects_existing_target(edge_mod):
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "one")
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "two")

    result = edge_mod.cfg_task_copy(":memory:", "EdgeTask@one", "two")

    assert result.success is False
    assert "already exists" in result.error.msg


def test_group_copy_across_tasks(edge_mod):
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "one")
    edge_mod.cfg_task_add(":memory:", "EdgeTask", "two")
    edge_mod.cfg_arg_set(":memory:", "EdgeTask@one", "main", "value", "copied")
    # ``cfg_task_add`` seeds every group, so make the target row absent first.
    assert edge_mod.cfg_group_del(":memory:", "EdgeTask@two", "extra").success is True

    result = edge_mod.cfg_group_copy(
        ":memory:",
        "EdgeTask@one",
        "main",
        "extra",
        "EdgeTask@two",
    )

    assert result.success is True
    assert (
        edge_mod.cfg_arg_get(":memory:", "EdgeTask@two", "extra", "value").value
        == "copied"
    )


def test_unknown_task_and_group_operations_fail(edge_mod):
    assert edge_mod.cfg_task_del(":memory:", "EdgeTask@missing").success is False
    assert edge_mod.cfg_task_reset(":memory:", "EdgeTask@missing").success is False
    assert (
        edge_mod.cfg_group_del(":memory:", "EdgeTask@missing", "main").success
        is False
    )
    assert (
        edge_mod.cfg_group_reset(":memory:", "EdgeTask@missing", "nope").success
        is False
    )


class MoreErrGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    value: str = Input.str(default="v")


class MoreErrTask(TaskBase):
    main: MoreErrGroup = Field(default_factory=MoreErrGroup)
    extra: MoreErrGroup = Field(default_factory=MoreErrGroup)
    dynamic: list[MoreErrGroup] = Field(default_factory=list)


def _more_event(task, group, arg, value):
    from oas.config.entry.model import ConfigSetEvent

    return ConfigSetEvent(task=task, group=group, arg=arg, value=value)


@pytest.fixture
def more_mod(memory_config):
    return ConfigMod(":memory:")


def test_config_set_unknown_task_reports_error(more_mod):
    ok, events = more_mod.config_set(
        ":memory:", _more_event("NoSuchTask@missing", "main", "count", 2)
    )

    assert ok is False
    assert events[0].error is not None


def test_config_set_unknown_group_and_field_report_errors(more_mod):
    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")

    ok, events = more_mod.config_set(
        ":memory:", _more_event("MoreErrTask@one", "missing", "count", 2)
    )
    assert ok is False
    assert events[0].error is not None

    ok, events = more_mod.config_set(
        ":memory:", _more_event("MoreErrTask@one", "main", "missing", 2)
    )
    assert ok is False
    assert events[0].error is not None


def test_config_read_empty_ref_and_unknown_task(more_mod):
    assert more_mod.config_read(":memory:", ModelConfigRef(task=[], group=[])) == {}
    assert (
        more_mod.config_read(
            ":memory:", ModelConfigRef(task=["NoSuchTask@missing"], group=[])
        )
        == {}
    )


def test_config_reset_unknown_task_returns_none(more_mod):
    assert (
        more_mod.config_reset(
            ":memory:", _more_event("NoSuchTask@missing", "main", "count", 1)
        )
        is None
    )


def test_config_group_reset_unknown_group_returns_empty(more_mod):
    assert (
        more_mod.config_group_reset(
            ":memory:", _more_event("NoSuchTask@missing", "main", "count", 1)
        )
        == []
    )
    assert more_mod.config_group_batch_reset(":memory:", []) == []


def test_cfg_arg_set_unknown_task_group_and_field(more_mod):
    assert (
        more_mod.cfg_arg_set(
            ":memory:", "NoSuchTask@missing", "main", "count", 2
        ).success
        is False
    )

    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")
    assert (
        more_mod.cfg_arg_set(
            ":memory:", "MoreErrTask@one", "missing", "count", 2
        ).success
        is False
    )
    assert (
        more_mod.cfg_arg_set(
            ":memory:", "MoreErrTask@one", "main", "missing", 2
        ).success
        is False
    )


def test_cfg_arg_set_invalid_value_leaves_default(more_mod):
    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")

    result = more_mod.cfg_arg_set(
        ":memory:", "MoreErrTask@one", "main", "count", -1
    )

    assert result.success is False
    assert (
        more_mod.cfg_arg_get(":memory:", "MoreErrTask@one", "main", "count").value
        == 1
    )


def test_cfg_group_add_rejects_missing_task_mismatch_and_dynamic(more_mod):
    assert (
        more_mod.cfg_group_add(
            ":memory:", "NoSuchTask@missing", "main", "MoreErrGroup"
        ).success
        is False
    )

    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")
    assert (
        more_mod.cfg_group_add(
            ":memory:", "MoreErrTask@one", "main", "WrongGroup"
        ).success
        is False
    )
    assert (
        more_mod.cfg_group_add(
            ":memory:", "MoreErrTask@one", "dynamic", "MoreErrGroup"
        ).success
        is False
    )


def test_cfg_group_copy_rejects_same_source_and_missing_targets(more_mod):
    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")
    more_mod.cfg_task_add(":memory:", "MoreErrTask", "two")
    more_mod.cfg_group_del(":memory:", "MoreErrTask@two", "extra")

    assert (
        more_mod.cfg_group_copy(
            ":memory:", "MoreErrTask@one", "main", "main"
        ).success
        is False
    )
    assert (
        more_mod.cfg_group_copy(
            ":memory:",
            "MoreErrTask@one",
            "main",
            "extra",
            "NoSuchTask@missing",
        ).success
        is False
    )
    assert (
        more_mod.cfg_group_copy(
            ":memory:", "MoreErrTask@one", "main", "missing", "MoreErrTask@two"
        ).success
        is False
    )


def test_cfg_task_copy_rejects_missing_source_self_and_invalid_name(more_mod):
    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")

    assert (
        more_mod.cfg_task_copy(
            ":memory:", "NoSuchTask@missing", "two"
        ).success
        is False
    )
    assert (
        more_mod.cfg_task_copy(":memory:", "MoreErrTask@one", "one").success
        is False
    )
    assert (
        more_mod.cfg_task_copy(":memory:", "MoreErrTask@one", "a@b").success
        is False
    )


def test_cfg_task_and_group_missing_operations(more_mod):
    assert more_mod.cfg_task_del(":memory:", "NoSuchTask@missing").success is False
    assert more_mod.cfg_task_reset(":memory:", "NoSuchTask@missing").success is False
    assert (
        more_mod.cfg_group_del(
            ":memory:", "NoSuchTask@missing", "main"
        ).success
        is False
    )
    assert (
        more_mod.cfg_group_reset(
            ":memory:", "NoSuchTask@missing", "missing"
        ).success
        is False
    )


def test_cfg_arg_batch_set_empty_and_invalid(more_mod):
    assert more_mod.cfg_arg_batch_set(":memory:", []).success is True

    more_mod.cfg_task_add(":memory:", "MoreErrTask", "one")
    result = more_mod.cfg_arg_batch_set(
        ":memory:",
        [
            _more_event("MoreErrTask@one", "main", "count", 2),
            _more_event("MoreErrTask@one", "extra", "count", -1),
        ],
    )

    assert result.success is False
    assert (
        more_mod.cfg_arg_get(":memory:", "MoreErrTask@one", "main", "count").value
        == 1
    )


def test_cfg_arg_get_missing_returns_default(more_mod):
    assert (
        more_mod.cfg_arg_get(
            ":memory:", "NoSuchTask@missing", "main", "count", default=42
        ).value
        == 42
    )
