"""Tests for ``TaskStore`` persistence."""

import pytest
from pydantic import Field

from oas.config.entry.codec import Codec
from oas.config.entry.mod_store import TaskStore
from oas.config.models.args import Input
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.table.config import ConfigTable


class StoreGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    name: str = Input.str(default="group")


class StoreExtraGroup(GroupBase):
    value: str = Input.str(default="extra")


class StoreTask(TaskBase):
    main: StoreGroup = Field(default_factory=StoreGroup)
    extra: StoreExtraGroup = Field(default_factory=StoreExtraGroup)


@pytest.fixture
def store(memory_config):
    return TaskStore(":memory:")


def _rows(task: str):
    return {
        row.group: row for row in ConfigTable(":memory:").list_task_rows(task)
    }


def test_save_writes_one_row_per_group(store):
    task = StoreTask(main=StoreGroup(count=4), extra=StoreExtraGroup(value="x"))

    store.save(task, "StoreTask@first")

    rows = _rows("StoreTask@first")
    assert set(rows) == {"main", "extra"}
    assert rows["main"].taskclass == "StoreTask"
    assert rows["main"].groupclass == "StoreGroup"
    assert rows["extra"].groupclass == "StoreExtraGroup"
    assert Codec.decode(rows["main"].value) == task.main.to_dict()


def test_save_and_load_roundtrip(store):
    task = StoreTask(main=StoreGroup(count=7, name="saved"))

    store.save(task, "StoreTask@first")

    assert store.load(StoreTask, "StoreTask@first") == task


def test_save_updates_in_place_without_duplicating_rows(store):
    store.save(StoreTask(), "StoreTask@first")
    store.save(StoreTask(main=StoreGroup(count=9)), "StoreTask@first")

    assert len(_rows("StoreTask@first")) == 2
    assert store.load(StoreTask, "StoreTask@first").main.count == 9


def test_save_deletes_groups_that_are_no_longer_declared(store):
    ConfigTable(":memory:").upsert_group(
        "StoreTask",
        "StoreTask@first",
        "StoreGroup",
        "removed",
        Codec.encode(StoreGroup().to_dict()),
    )

    store.save(StoreTask(), "StoreTask@first")

    assert "removed" not in _rows("StoreTask@first")


def test_save_only_touches_its_own_task_instance(store):
    store.save(StoreTask(), "StoreTask@first")
    store.save(StoreTask(main=StoreGroup(count=5)), "StoreTask@second")

    assert store.load(StoreTask, "StoreTask@first").main.count == 1
    assert store.load(StoreTask, "StoreTask@second").main.count == 5


def test_load_uses_defaults_for_missing_groups(store):
    task = store.load(StoreTask, "StoreTask@missing")

    assert task == StoreTask()


def test_load_ignores_unknown_group_rows(store):
    ConfigTable(":memory:").upsert_group(
        "StoreTask",
        "StoreTask@first",
        "StoreGroup",
        "removed",
        Codec.encode(StoreGroup(count=99).to_dict()),
    )

    assert store.load(StoreTask, "StoreTask@first") == StoreTask()


def test_load_ignores_a_stale_taskclass_column(store):
    ConfigTable(":memory:").upsert_group(
        "OldTaskClass",
        "StoreTask@first",
        "OldGroupClass",
        "main",
        Codec.encode(StoreGroup(count=6).to_dict()),
    )

    assert store.load(StoreTask, "StoreTask@first").main.count == 6


@pytest.mark.parametrize("method", ["save", "load"])
def test_empty_task_name_is_rejected(store, method):
    with pytest.raises(ValueError, match="must not be empty"):
        if method == "save":
            store.save(StoreTask(), "")
        else:
            store.load(StoreTask, "")


def test_save_rolls_back_all_rows_when_encoding_fails(
    store, monkeypatch
):
    original = Codec.encode
    calls = {"count": 0}

    def flaky(data):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("encode failed")
        return original(data)

    monkeypatch.setattr(Codec, "encode", staticmethod(flaky))

    with pytest.raises(RuntimeError, match="encode failed"):
        store.save(StoreTask(), "StoreTask@first")

    assert _rows("StoreTask@first") == {}


def test_load_rejects_a_corrupt_row(store):
    ConfigTable(":memory:").upsert_group(
        "StoreTask",
        "StoreTask@first",
        "StoreGroup",
        "main",
        b"\xc1",
    )

    with pytest.raises(ValueError, match="invalid MsgPack"):
        store.load(StoreTask, "StoreTask@first")


class StoreMoreGroup(GroupBase):
    count: int = Input.int(default=1)


class StoreMoreTask(TaskBase):
    main: StoreMoreGroup = Field(default_factory=StoreMoreGroup)
    dynamic: list[StoreMoreGroup] = Field(default_factory=list)


def test_dynamic_groups_are_not_persisted(memory_config):
    store = TaskStore(":memory:")
    task = StoreMoreTask(dynamic=[StoreMoreGroup(count=9)])

    store.save(task, "StoreMoreTask@one")

    rows = ConfigTable(":memory:").list_task_rows("StoreMoreTask@one")

    assert [row.group for row in rows] == ["main"]
    assert store.load(StoreMoreTask, "StoreMoreTask@one").dynamic == []


def test_payload_unknown_fields_are_ignored(memory_config):
    ConfigTable(":memory:").upsert_group(
        "StoreMoreTask",
        "StoreMoreTask@one",
        "StoreMoreGroup",
        "main",
        Codec.encode({"count": 2, "removed": 1}),
    )

    assert TaskStore(":memory:").load(StoreMoreTask, "StoreMoreTask@one").main.count == 2


def test_empty_payload_uses_group_defaults(memory_config):
    ConfigTable(":memory:").upsert_group(
        "StoreMoreTask",
        "StoreMoreTask@one",
        "StoreMoreGroup",
        "main",
        Codec.encode({}),
    )

    assert (
        TaskStore(":memory:").load(StoreMoreTask, "StoreMoreTask@one").main.count
        == 1
    )


def test_save_auto_creates_the_table(memory_config):
    table = ConfigTable(":memory:")
    table.drop_table()

    TaskStore(":memory:").save(StoreMoreTask(), "StoreMoreTask@one")

    assert len(table.list_task_rows("StoreMoreTask@one")) == 1
