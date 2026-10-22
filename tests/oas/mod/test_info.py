"""Tests for ModEntryInfo."""

from oas.mod.info import ModEntryInfo


def test_entry_info_defaults():
    info = ModEntryInfo(name="mod")

    assert info.root == ""
    assert info.path_config == "module/config"
    assert info.path_main == "module/main.py"
    assert info.path_assets == "assets"
    assert set(info.asset_ext) == {".png", ".gif"}
    assert set(info.asset_lang) == {"cn", "en"}
    assert set(info.gui_language) == {"zh-CN", "en-US"}
    assert set(info.task_entry_folders) == {"module", "tasks"}


def test_entry_info_copy_is_deep():
    info = ModEntryInfo(name="mod")
    copied = info.copy()

    copied.asset_lang["jp"] = None
    copied.task_entry_folders["extra"] = None

    assert "jp" not in info.asset_lang
    assert "extra" not in info.task_entry_folders
    assert copied is not info


def test_iter_asset_lang_yields_shared_then_configured_languages():
    info = ModEntryInfo(name="mod", asset_lang=dict.fromkeys(["cn", "en"]))

    assert list(info.iter_asset_lang()) == ["", "cn", "en"]


def test_oas_entry_points_at_the_config_package():
    info = ModEntryInfo.oas()

    assert info.name == "oas"
    assert info.path_config == "oas/config"
    assert "zh-CN" in info.gui_language
