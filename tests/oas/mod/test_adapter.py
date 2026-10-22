"""Tests for the Mod adapter."""

import pytest

from oas.mod.adapter import ModAdapter


class FakeEntry:
    name = "fake"
    root = "C:/fake"


def test_mod_adapter_stores_entry_and_config_name():
    entry = FakeEntry()
    adapter = ModAdapter(entry, "default")

    assert adapter.entry is entry
    assert adapter.config_name == "default"
    assert bool(adapter) is True
    assert str(adapter) == 'ModAdapter(name="fake", root="C:/fake")'


@pytest.mark.parametrize(
    "method, args",
    [
        ("nav_index_data", ()),
        ("queue_index_data", ()),
        ("config_index_data", ()),
        ("task_index_data", ()),
        ("nav_config_json", ("file",)),
        ("nav_i18n_json", ("file",)),
        ("get_group_model", ("file", "Cls")),
    ],
)
def test_mod_adapter_interfaces_are_not_implemented(method, args):
    with pytest.raises(NotImplementedError):
        getattr(ModAdapter(FakeEntry()), method)(*args)
