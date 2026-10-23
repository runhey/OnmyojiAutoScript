"""Tests for built-in Mod entries."""

from oas.mod.const import DICT_MOD_ENTRY
from oas.mod.info import ModEntryInfo


def test_dict_mod_entry_contains_the_builtin_mods():
    assert {'example_mod', 'alas', 'src', 'oas'} <= set(DICT_MOD_ENTRY)
    assert all(isinstance(info, ModEntryInfo) for info in DICT_MOD_ENTRY.values())
