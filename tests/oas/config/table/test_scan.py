from pathlib import Path

import pytest

from oas.backend.reactive.event import RpcValueError
from oas.config.table.key import KeyTable
from oas.config.table.scan import (
    ConfigExtra,
    DndRequest,
    validate_config_name,
)


@pytest.mark.parametrize("name", ["", ".", "..", "gui", "webapp", ":memory:", "template1"])
def test_validate_config_name_rejects_reserved_names(name):
    assert validate_config_name(name)


@pytest.mark.parametrize("name", ["default", "my_config", "测试"])
def test_validate_config_name_accepts_normal_names(name):
    assert validate_config_name(name) == ""


def test_scan_table_is_backed_by_gui_db(scan_table):
    assert Path(str(scan_table.file)).name == "gui.db"
    scan_table.insert_row(scan_table.MODEL("default", "mod", 1, 1))
    assert scan_table.select_rows()["default"].mod == "mod"


def test_scan_table_scan_adds_config_files_and_reads_mod(scan_table, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    KeyTable("first").mod_set("demo")
    record = scan_table.scan()
    assert record["first"].mod == "demo"
    assert record["first"].gid == 1
    assert record["first"].iid == 1


def test_scan_table_ignores_config_files_without_mod(scan_table, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    from oas.config.table.config import ConfigTable

    ConfigTable("orphan").create_table()
    assert "orphan" not in scan_table.scan()


def test_scan_table_config_lifecycle(scan_table, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    scan_table.config_add("one", "mod-a")
    assert KeyTable("one").mod_get() == "mod-a"
    scan_table.scan()
    assert "one" in scan_table.select_rows()

    scan_table.config_copy("one", "two")
    assert KeyTable("two").mod_get() == "mod-a"
    scan_table.config_rename("two", "renamed")
    assert KeyTable("renamed").mod_get() == "mod-a"
    scan_table.config_del("renamed")
    assert not (config_dir / "renamed.db").exists()


def test_scan_table_dnd_resorts_positions(scan_table):
    scan_table.insert_row(scan_table.MODEL("a", "m", 1, 1))
    scan_table.insert_row(scan_table.MODEL("b", "m", 2, 1))
    scan_table.config_dnd([DndRequest("b", 1, 0.5)])
    rows = scan_table.select_rows()
    assert rows["b"].gid == 1
    assert rows["a"].gid == 1
    assert rows["b"].iid == 1
    assert rows["a"].iid == 2


def test_scan_table_dnd_can_swap_groups_without_unique_conflict(scan_table):
    scan_table.insert_row(scan_table.MODEL("a", "m", 1, 1))
    scan_table.insert_row(scan_table.MODEL("b", "m", 2, 1))

    scan_table.config_dnd([
        DndRequest("a", 2, 1),
        DndRequest("b", 1, 1),
    ])

    rows = scan_table.select_rows()
    assert (rows["a"].gid, rows["a"].iid) == (2, 1)
    assert (rows["b"].gid, rows["b"].iid) == (1, 1)


def test_scan_table_dnd_rejects_invalid_config_name(scan_table):
    with pytest.raises(RpcValueError):
        scan_table.config_dnd([DndRequest("gui", 1, 1)])


def test_scan_table_dnd_rejects_missing_config(scan_table):
    with pytest.raises(RpcValueError, match="does not exist"):
        scan_table.config_dnd([DndRequest("missing", 1, 1)])


def test_scan_table_copy_rejects_same_source_and_target(scan_table, tmp_path):
    scan_table.config_add("one", "mod-a")
    with pytest.raises(RpcValueError, match="same as source"):
        scan_table.config_copy("one", "one")


def test_scan_table_delete_leaves_stale_row_until_scan(scan_table, tmp_path):
    name = "delete_later"
    KeyTable.singleton_remove(name)
    scan_table.config_add(name, "mod-a")
    scan_table.scan()
    assert name in scan_table.select_rows()
    scan_table.config_del(name)
    assert name in scan_table.select_rows()
    assert name not in scan_table.scan()


def test_scan_models_are_binary_metadata_models():
    assert ConfigExtra() == ConfigExtra(startup=False)
    assert DndRequest("name", 1, 1).name == "name"


def test_config_add_rejects_protected_name(scan_table):
    with pytest.raises(RpcValueError, match="protected"):
        scan_table.config_add("gui", "mod")


def test_config_add_rejects_existing_config(scan_table):
    scan_table.config_add("scan_add_dup", "mod")

    with pytest.raises(RpcValueError, match="already exists"):
        scan_table.config_add("scan_add_dup", "mod")


def test_config_rename_rejects_same_name(scan_table):
    scan_table.config_add("scan_rename_same", "mod")

    with pytest.raises(RpcValueError, match="same as old"):
        scan_table.config_rename("scan_rename_same", "scan_rename_same")


def test_config_rename_rejects_missing_source(scan_table):
    with pytest.raises(RpcValueError, match="does not exist"):
        scan_table.config_rename("scan_rename_missing", "scan_rename_target")


def test_config_rename_rejects_existing_target(scan_table):
    scan_table.config_add("scan_rename_a", "mod")
    scan_table.config_add("scan_rename_b", "mod")

    with pytest.raises(RpcValueError, match="already exists"):
        scan_table.config_rename("scan_rename_a", "scan_rename_b")


def test_config_copy_rejects_missing_source(scan_table):
    with pytest.raises(RpcValueError, match="not found"):
        scan_table.config_copy("scan_copy_missing", "scan_copy_target")


def test_config_copy_rejects_existing_target(scan_table):
    scan_table.config_add("scan_copy_a", "mod")
    scan_table.config_add("scan_copy_b", "mod")

    with pytest.raises(RpcValueError, match="already exists"):
        scan_table.config_copy("scan_copy_a", "scan_copy_b")


def test_config_delete_rejects_protected_name(scan_table):
    with pytest.raises(RpcValueError, match="protected"):
        scan_table.config_del("template-x")


def test_config_dnd_with_empty_requests_is_noop(scan_table):
    scan_table.config_dnd([])

    assert scan_table.select_rows() == {}


def test_config_dnd_rejects_duplicate_missing_names(scan_table):
    with pytest.raises(RpcValueError, match="does not exist"):
        scan_table.config_dnd(
            [DndRequest("scan_dnd_missing", 1, 1), DndRequest("scan_dnd_missing", 1, 2)]
        )
