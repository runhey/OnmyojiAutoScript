import pytest

from oas.config.table.config import ConfigRow, ConfigTable


def test_config_table_schema_contains_four_part_identity(config_table):
    with config_table.cursor() as cursor:
        cursor.execute('PRAGMA table_info("config")')
        columns = cursor.fetchall()
    assert [row[1] for row in columns] == [
        "id", "taskclass", "task", "groupclass", "group", "value"
    ]


def test_config_table_upsert_and_get_preserve_raw_bytes(config_table):
    first = config_table.upsert_group(
        "FindJadeTask", "daily", "SchedulerGroup", "scheduler", b"\x00\x81value"
    )
    assert isinstance(first, ConfigRow)
    assert first.id > 0
    assert first.value == b"\x00\x81value"

    second = config_table.upsert_group(
        "FindJadeTask", "daily", "SchedulerGroup", "scheduler", b"updated"
    )
    assert second.id == first.id
    assert second.value == b"updated"
    assert len(config_table.select()) == 1


def test_config_table_identity_includes_class_and_instance_names(config_table):
    config_table.upsert_group("TaskA", "one", "GroupA", "main", b"a")
    config_table.upsert_group("TaskB", "one", "GroupA", "main", b"b")
    config_table.upsert_group("TaskA", "two", "GroupA", "main", b"c")
    config_table.upsert_group("TaskA", "one", "GroupB", "main", b"d")

    assert len(config_table.select()) == 4
    assert config_table.get_group("TaskA", "one", "GroupA", "main").value == b"a"
    assert [row.value for row in config_table.list_task_rows("TaskA", "one")] == [b"a", b"d"]


def test_config_table_list_groups_can_filter_group_class(config_table):
    config_table.upsert_group("Task", "instance", "GroupA", "one", b"a")
    config_table.upsert_group("Task", "instance", "GroupB", "two", b"b")

    rows = config_table.list_groups("Task", "instance", groupclass="GroupB")
    assert [(row.groupclass, row.group) for row in rows] == [("GroupB", "two")]


def test_config_table_missing_group_returns_none(config_table):
    assert config_table.get_group("Task", "instance", "Group", "missing") is None


def test_config_table_read_helpers_support_exact_events(config_table):
    config_table.upsert_group("Task", "a", "Group", "one", b"one")
    config_table.upsert_group("Task", "b", "Group", "two", b"two")

    class Event:
        taskclass = "Task"
        task = "b"
        groupclass = "Group"
        group = "two"

    rows = config_table.read_rows([Event()])
    assert [(row.task, row.group, row.value) for row in rows] == [("b", "two", b"two")]

    rows = config_table.read_task_rows(tasks=["a"], taskclasses=["Task"])
    assert [row.value for row in rows] == [b"one"]

    assert config_table.read_rows([]) == []


def test_config_table_delete_group_and_task(config_table):
    config_table.upsert_group("Task", "a", "Group", "one", b"one")
    config_table.upsert_group("Task", "a", "Group", "two", b"two")
    config_table.upsert_group("Task", "b", "Group", "one", b"three")

    config_table.delete_group("Task", "a", "Group", "one")
    assert config_table.get_group("Task", "a", "Group", "one") is None
    config_table.delete_task("Task", "a")
    assert config_table.list_task_rows("Task", "a") == []
    assert len(config_table.list_task_rows("Task", "b")) == 1


def test_config_table_rejects_non_bytes(config_table):
    with pytest.raises(TypeError, match="must be bytes"):
        config_table.upsert_group("Task", "a", "Group", "one", "text")


def test_config_row_requires_all_identity_and_value_fields():
    with pytest.raises(TypeError):
        ConfigRow(taskclass="Task", task="a", groupclass="Group", group="one")
