"""Tests for the ConfigAccess runtime layer."""

import pytest
from pydantic import Field, ValidationError

from oas.config.entry.mod_store import TaskStore
from oas.config.entry.model import ConfigSetEvent
from oas.config.models.args import Input, Switch
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_access import ConfigAccess


class AccessGroup(GroupBase):
    count: int = Input.int(default=3, ge=0)
    name: str = Input.str(default="group")
    flag: bool = Switch.field(default=False)

    def apply(self, value: int) -> None:
        self.count = value

    apply._oas_batch_set = True  # type: ignore[attr-defined]


class AccessOtherGroup(GroupBase):
    value: str = Input.str(default="other")


class AccessTask(TaskBase):
    main: AccessGroup = Field(default_factory=AccessGroup)
    extra: AccessOtherGroup = Field(default_factory=AccessOtherGroup)
    dynamic: list[AccessOtherGroup] = Field(default_factory=list)
    label: str = Input.str(default="task")


@pytest.fixture
def access(memory_config):
    TaskStore(":memory:").save(AccessTask(), "AccessTask@default")
    return ConfigAccess(":memory:", "AccessTask@default")


def _stored():
    return TaskStore(":memory:").load(AccessTask, "AccessTask@default")


def test_cache_loads_rows_and_is_idempotent(access):
    assert access._config_cached is True
    assert set(access._dict_row) == {
        ("AccessTask@default", "main"),
        ("AccessTask@default", "extra"),
    }
    cached_rows = access._dict_row

    access.config_cache()

    assert access._dict_row is cached_rows
    assert set(access._dict_group) == {
        ("AccessTask@default", "main"),
        ("AccessTask@default", "extra"),
    }


def test_cache_is_skipped_for_template_config(memory_config):
    access = ConfigAccess(":memory:")
    access.is_template_config = True

    access.config_cache()

    assert access._config_cached is False


def test_config_changed_and_refresh(access):
    TaskStore(":memory:").save(
        AccessTask(main=AccessGroup(count=9)), "AccessTask@default"
    )
    # The pool may reuse the same SQLite connection, so force a stale
    # data-version token to exercise the change-detection branch.
    connection_id, _version = access._data_version
    access._data_version = (connection_id, -1)

    assert access.config_changed() is True
    assert access.refresh() is True
    assert access.main.count == 9
    assert access.config_changed() is False


def test_refresh_returns_false_when_unchanged(access):
    assert access.refresh() is False


def test_load_group_uses_defaults_for_missing_rows(memory_config):
    access = ConfigAccess(":memory:", "AccessTask@missing")

    assert access.main.count == 3
    assert access._load_group("AccessTask@missing", "main").name == "group"


def test_dynamic_and_non_group_fields_are_not_static_groups(access):
    assert access._load_group("AccessTask@default", "dynamic") is None
    assert access._load_group("AccessTask@default", "label") is None

    with pytest.raises(AttributeError):
        _ = access.dynamic
    with pytest.raises(AttributeError):
        _ = access.label


def test_corrupt_payload_returns_none(access):
    access._dict_row[("AccessTask@default", "main")] = b"\xc1"
    access._dict_group.pop(("AccessTask@default", "main"), None)

    assert access._load_group("AccessTask@default", "main") is None


def test_group_proxy_reads_and_writes(access):
    proxy = access.main

    assert proxy.count == 3
    assert str(proxy) == str(access._dict_group[("AccessTask@default", "main")])

    proxy.count = 7

    assert access.main.count == 7
    assert _stored().main.count == 7


def test_group_proxy_rejects_private_and_invalid_values(access):
    proxy = access.main

    with pytest.raises(AttributeError):
        proxy._private = 1
    with pytest.raises(ValidationError):
        proxy.count = -1
    assert proxy.count == 3


def test_group_proxy_wraps_batch_methods(access):
    access.main.apply(5)

    assert access.main.count == 5
    assert _stored().main.count == 5
    assert access._modified == {}


def test_batch_set_context_defers_and_saves(access):
    with access.batch_set():
        assert access._local.batch_depth == 1
        access.main.count = 1
        access.extra.value = "changed"
        assert access._modified
        assert _stored().main.count == 3

    assert access._local.batch_depth == 0
    assert access._modified == {}
    assert _stored().main.count == 1
    assert _stored().extra.value == "changed"


def test_nested_batch_set_saves_only_on_outermost_exit(access):
    with access.batch_set():
        with access.batch_set():
            access.main.count = 2
        assert _stored().main.count == 3
    assert _stored().main.count == 2


def test_batch_set_saves_even_when_body_raises(access):
    with pytest.raises(RuntimeError, match="boom"), access.batch_set():
        access.main.count = 4
        raise RuntimeError("boom")

    assert _stored().main.count == 4


def test_save_restores_modified_when_persistence_raises(
    access, monkeypatch
):
    access.auto_save = False
    access.main.count = 1
    access.extra.value = "x"
    assert len(access._modified) == 2

    monkeypatch.setattr(
        access,
        "config_batch_set",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db")),
    )
    with pytest.raises(RuntimeError, match="db"):
        access.save()
    assert len(access._modified) == 2


def test_save_restores_modified_when_persistence_fails(access, monkeypatch):
    access.auto_save = False
    access.main.count = 1
    access.extra.value = "x"

    monkeypatch.setattr(
        access, "config_batch_set", lambda *args, **kwargs: (False, [])
    )

    assert access.save() is False
    assert len(access._modified) == 2


def test_save_with_no_modified_returns_false(access):
    assert access.save() is False


def test_override_applies_in_memory_and_clear_restores(access):
    previous = access.override(main_count=10)

    assert previous == ({"main": {"count": 3}}, {})
    assert access.main.count == 10
    assert _stored().main.count == 3

    access.override(TIMEOUT=5)
    assert access.TIMEOUT == 5

    access.override_clear()

    assert access.main.count == 3
    assert "TIMEOUT" not in access.__dict__


def test_override_ignores_invalid_value(access):
    previous = access.override(main_count=-1)

    assert previous[0] == {}
    assert access.main.count == 3


def test_temporary_restores_after_exit(access):
    with access.temporary(main_count=11):
        assert access.main.count == 11

    assert access.main.count == 3


def test_temporary_restores_after_exception(access):
    with pytest.raises(RuntimeError, match="boom"), access.temporary(main_count=12):
        assert access.main.count == 12
        raise RuntimeError("boom")

    assert access.main.count == 3


def test_bound_and_bound_get(access):
    assert ("main", "count") in access.bound
    assert ("extra", "value") in access.bound
    assert access.bound_get("main", "count") == 3
    assert access.bound_get("missing", "count", default="d") == "d"


def test_cross_get_and_cross_set(access):
    assert access.cross_get("AccessTask@default", "extra", "value") == "other"
    assert access.cross_get("MissingTask", "extra", "value", "d") == "d"

    access.cross_set("AccessTask@default", "extra", "value", "updated")

    assert access.cross_get("AccessTask@default", "extra", "value") == "updated"
    assert _stored().extra.value == "updated"

    access.cross_set("AccessTask@default", "extra", "value", object())
    assert access.cross_get("AccessTask@default", "extra", "value") == "updated"


def test_getattr_unknown_group_raises(access):
    with pytest.raises(AttributeError):
        _ = access.no_such_group


def test_release_clears_runtime_state(access):
    access._modified[("t", "g", "a")] = ConfigSetEvent("t", "g", "a", 1)
    access._local.batch_depth = 2

    access.release()

    assert access._config_cached is False
    assert access._dict_row == {}
    assert access._dict_group == {}
    assert access._modified == {}
    assert access._local.batch_depth == 0


def test_access_without_task_has_no_groups(memory_config):
    access = ConfigAccess(":memory:")

    assert access.task == ""
    with pytest.raises(AttributeError):
        _ = access.main


def test_task_class_and_group_class_resolution(access):
    assert access._task_class("AccessTask@default") is AccessTask
    assert access._task_class("NoSuchTask@default") is None
    assert access._task_class("AccessTask") is AccessTask
    assert access._group_class(AccessTask, "main") is AccessGroup
    assert access._group_class(AccessTask, "dynamic") is None
    assert access._group_class(AccessTask, "label") is None


class AccessErrGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)

    def apply(self, value: int) -> None:
        self.count = value

    apply._oas_batch_set = True  # type: ignore[attr-defined]

    def apply_alasio(self, value: int) -> None:
        self.count = value

    apply_alasio._alasio_batch_set = True  # type: ignore[attr-defined]


class AccessErrOther(GroupBase):
    value: str = Input.str(default="other")


class AccessErrTask(TaskBase):
    main: AccessErrGroup = Field(default_factory=AccessErrGroup)
    extra: AccessErrOther = Field(default_factory=AccessErrOther)


class AccessErrListTask(TaskBase):
    groups: list[AccessErrGroup] | None = None


@pytest.fixture
def access_errors(memory_config):
    TaskStore(":memory:").save(AccessErrTask(), "AccessErrTask@default")
    return ConfigAccess(":memory:", "AccessErrTask@default")


def _stored_errors():
    return TaskStore(":memory:").load(AccessErrTask, "AccessErrTask@default")


def test_set_group_arg_rejects_missing_group_and_field(access_errors):
    with pytest.raises(AttributeError, match="no such group"):
        access_errors._set_group_arg("AccessErrTask@default", "missing", "count", 1)
    with pytest.raises(AttributeError, match="no such field"):
        access_errors._set_group_arg("AccessErrTask@default", "main", "missing", 1)


def test_set_group_arg_rejects_invalid_value_without_mutating(access_errors):
    with pytest.raises(ValidationError):
        access_errors._set_group_arg("AccessErrTask@default", "main", "count", -1)

    assert access_errors.main.count == 1
    assert _stored_errors().main.count == 1


def test_proxy_rejects_unknown_attribute(access_errors):
    with pytest.raises(AttributeError):
        _ = access_errors.main.missing


def test_proxy_rejects_unknown_field_assignment(access_errors):
    with pytest.raises(AttributeError, match="no such field"):
        access_errors.main.missing = 1


def test_proxy_rejects_private_assignment(access_errors):
    with pytest.raises(AttributeError):
        access_errors.main._x = 1


def test_proxy_rejects_invalid_assignment(access_errors):
    with pytest.raises(ValidationError):
        access_errors.main.count = -1

    assert access_errors.main.count == 1


def test_alasio_batch_method_marker_is_wrapped(access_errors):
    access_errors.main.apply_alasio(5)

    assert access_errors.main.count == 5
    assert _stored_errors().main.count == 5
    assert access_errors._modified == {}


def test_load_group_returns_none_for_unknown_task_and_group(access_errors):
    assert access_errors._load_group("NoSuchTask@x", "main") is None
    assert access_errors._load_group("AccessErrTask@default", "missing") is None


def test_group_class_rejects_union_of_group_lists():
    assert ConfigAccess._group_class(AccessErrListTask, "groups") is None


def test_cross_set_ignores_unknown_group_field_and_invalid_value(access_errors):
    access_errors.cross_set("AccessErrTask@default", "missing", "count", 2)
    access_errors.cross_set("AccessErrTask@default", "main", "missing", 2)
    access_errors.cross_set("AccessErrTask@default", "main", "count", -1)

    assert access_errors.main.count == 1
    assert access_errors._modified == {}
    assert _stored_errors().main.count == 1


def test_cross_get_missing_returns_default(access_errors):
    assert access_errors.cross_get("NoSuchTask@x", "main", "count", "d") == "d"
    assert access_errors.cross_get("AccessErrTask@default", "main", "missing", "d") == "d"


def test_temporary_with_invalid_value_is_a_noop(access_errors):
    with access_errors.temporary(main_count=-1):
        assert access_errors.main.count == 1

    assert access_errors.main.count == 1


def test_nested_temporary_restores_inner_then_outer(access_errors):
    with access_errors.temporary(main_count=2):
        assert access_errors.main.count == 2
        with access_errors.temporary(main_count=3):
            assert access_errors.main.count == 3
        assert access_errors.main.count == 2
    assert access_errors.main.count == 1


def test_save_single_event_raises_and_restores(access_errors, monkeypatch):
    access_errors.auto_save = False
    access_errors.main.count = 2
    assert len(access_errors._modified) == 1

    monkeypatch.setattr(
        access_errors,
        "config_set",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db")),
    )

    with pytest.raises(RuntimeError, match="db"):
        access_errors.save()
    assert len(access_errors._modified) == 1


def test_save_single_event_failure_restores(access_errors, monkeypatch):
    access_errors.auto_save = False
    access_errors.main.count = 2
    monkeypatch.setattr(access_errors, "config_set", lambda *args, **kwargs: (False, []))

    assert access_errors.save() is False
    assert len(access_errors._modified) == 1


def test_save_single_event_success_clears_and_persists(access_errors):
    access_errors.auto_save = False
    access_errors.main.count = 2

    assert access_errors.save() is True
    assert access_errors._modified == {}
    assert _stored_errors().main.count == 2


def test_batch_set_with_auto_save_disabled_does_not_write(access_errors):
    access_errors.auto_save = False

    with access_errors.batch_set():
        access_errors.main.count = 2

    assert access_errors._modified
    assert _stored_errors().main.count == 1


def test_config_changed_is_false_for_template_and_uncached(memory_config):
    template = ConfigAccess(":memory:")
    template.is_template_config = True
    assert template.config_changed() is False

    uncached = ConfigAccess(":memory:")
    assert uncached._config_cached is False
    assert uncached.config_changed() is False


def test_init_task_with_unknown_task_caches_nothing(memory_config):
    access_errors = ConfigAccess(":memory:", "NoSuchTask@default")

    assert access_errors._task_class("NoSuchTask@default") is None
    assert access_errors._dict_group == {}
    assert access_errors.bound == {}


def test_access_without_task_has_empty_bound(memory_config):
    assert ConfigAccess(":memory:").bound == {}


def test_release_with_pending_changes_does_not_raise(access_errors):
    access_errors.auto_save = False
    access_errors.main.count = 2
    access_errors._local.batch_depth = 1

    access_errors.release()

    assert access_errors._modified == {}
    assert access_errors._local.batch_depth == 0
