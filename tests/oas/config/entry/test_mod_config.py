"""Tests for the modconfig decorator contract and adapter lifecycle."""

import inspect
from typing import ClassVar, get_type_hints

import pytest

from oas.config.entry.mod_config import modconfig
from oas.config.models.args import Input
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_mod import ConfigMod
from oas.config.table.config import ConfigTable
from oas.mod.adapter import ModAdapter
from oas.mod.info import ModEntryInfo

PUBLIC_METHODS = [
    "config_read",
    "config_batch_set",
    "config_set",
    "config_batch_reset",
    "config_reset",
    "config_group_batch_reset",
    "config_group_reset",
    "cfg_task_add",
    "cfg_task_del",
    "cfg_task_copy",
    "cfg_task_reset",
    "cfg_group_add",
    "cfg_group_del",
    "cfg_group_copy",
    "cfg_group_reset",
    "cfg_arg_get",
    "cfg_arg_set",
    "cfg_arg_batch_set",
    "cfg_arg_reset",
    "cfg_arg_batch_reset",
]
INTERNAL_METHODS = ["_config_snapshot", "_config_data_version"]


class DecoratorGroup(GroupBase):
    count: int = Input.int(default=1)


class DecoratorTask(TaskBase):
    main: DecoratorGroup


@pytest.mark.parametrize("name", PUBLIC_METHODS + INTERNAL_METHODS)
def test_public_signature_hides_result(name):
    method = getattr(ConfigMod, name)
    signature = inspect.signature(method)

    assert list(signature.parameters)[:2] == ["self", "config_name"]
    assert "result" not in signature.parameters
    assert "result" not in get_type_hints(method)
    assert "result" in inspect.signature(method.__wrapped__).parameters


def test_shared_adapter_is_created_lazily_and_reused(memory_config):
    mod = ConfigMod(":memory:")

    assert "__mod_adapter__" not in mod.__dict__

    mod._config_data_version(":memory:")
    adapter = mod.__dict__["__mod_adapter__"]

    assert isinstance(adapter, ModAdapter)
    assert adapter.config_name == ":memory:"
    assert adapter.entry is ConfigMod.__entry_info__

    mod._config_data_version(":memory:")
    assert mod.__dict__["__mod_adapter__"] is adapter


def test_shared_adapter_rejects_missing_entry_info():
    class NoEntry:
        config_name = ":memory:"

        def read(self, result, config_name):
            return result

    NoEntry.read = modconfig._decorate(
        NoEntry.read, lambda target, config_name: "result"
    )

    with pytest.raises(AttributeError, match="__entry_info__"):
        NoEntry().read(":memory:")


def test_shared_adapter_rejects_missing_config_name():
    class NoConfig:
        __entry_info__ = ModEntryInfo.oas()

        def read(self, result, config_name):
            return result

    NoConfig.read = modconfig._decorate(
        NoConfig.read, lambda target, config_name: "result"
    )

    with pytest.raises(AttributeError, match="config_name"):
        NoConfig().read(":memory:")


class Dummy:
    __entry_info__ = ModEntryInfo.oas()
    config_name = ":memory:"

    def read(self, result, config_name):
        return result


Dummy.read = modconfig._decorate(
    Dummy.read, lambda target, config_name: ("impl", config_name)
)


def test_result_is_injected_and_returned():
    assert Dummy().read(":memory:") == ("impl", ":memory:")


def test_shared_adapter_rejects_non_adapter_value():
    dummy = Dummy()
    dummy.read(":memory:")
    dummy.__mod_adapter__ = object()

    with pytest.raises(TypeError, match="ModAdapter"):
        dummy.read(":memory:")


def test_shared_adapter_rejects_changed_config_name():
    dummy = Dummy()
    dummy.read(":memory:")
    dummy.config_name = "other"

    with pytest.raises(ValueError, match="different config_name"):
        dummy.read("other")


def test_decorate_requires_callable():
    with pytest.raises(TypeError, match="must decorate a callable"):
        modconfig._decorate(object(), lambda target: None)


class Ordered:
    __entry_info__ = ModEntryInfo.oas()
    config_name = ":memory:"
    calls: ClassVar[list[str]] = []

    def read(self, result, config_name):
        Ordered.calls.append("method")
        return result


def _ordered_impl(target, config_name):
    Ordered.calls.append("impl")
    return "result"


Ordered.read = modconfig._decorate(Ordered.read, _ordered_impl)


def test_implementation_runs_before_the_method_body():
    Ordered.calls.clear()

    assert Ordered().read(":memory:") == "result"
    assert Ordered.calls == ["impl", "method"]


def test_internal_snapshot_reads_rows(memory_config):
    ConfigTable(":memory:").upsert_group(
        "DecoratorTask",
        "DecoratorTask@one",
        "DecoratorGroup",
        "main",
        b"\x80",
    )
    mod = ConfigMod(":memory:")

    rows, version = mod._config_snapshot(":memory:")

    assert [row.task for row in rows] == ["DecoratorTask@one"]
    assert isinstance(version, tuple)
    assert len(version) == 2
    assert mod._config_data_version(":memory:")[1] == version[1]


def test_internal_data_version_on_empty_table(memory_config):
    version = ConfigMod(":memory:")._config_data_version(":memory:")

    assert isinstance(version, tuple)
    assert len(version) == 2
