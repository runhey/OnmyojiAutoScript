"""Tests for built-in Mod entries."""

from oas.mod.const import DICT_MOD_ENTRY
from oas.mod.info import ModEntryInfo


def test_dict_mod_entry_contains_only_the_builtin_oas_mod():
    assert set(DICT_MOD_ENTRY) == {'oas'}
    assert DICT_MOD_ENTRY['oas'] == ModEntryInfo.oas()
    assert all(isinstance(info, ModEntryInfo) for info in DICT_MOD_ENTRY.values())
