import pytest

from oas.config.table.config import ConfigRow


def test_config_table_schema_uses_task_group_composite_primary_key(config_table):
    with config_table.cursor() as cursor:
        cursor.execute('PRAGMA table_info("config")')
        columns = cursor.fetchall()
    assert [row[1] for row in columns] == [
        "task", "group", "taskclass", "groupclass", "value"
    ]
    assert [(row[1], row[5]) for row in columns if row[5]] == [
        ("task", 1),
        ("group", 2),
    ]


def test_config_table_upsert_and_get_preserve_raw_bytes(config_table):
    first = config_table.upsert_group(
        "FindJadeTask", "daily", "SchedulerGroup", "scheduler", b"\x00\x81value"
    )
    assert isinstance(first, ConfigRow)
    assert first.value == b"\x00\x81value"
    assert (first.task, first.group) == ("daily", "scheduler")
    assert (first.taskclass, first.groupclass) == ("FindJadeTask", "SchedulerGroup")

    second = config_table.upsert_group(
        "FindJadeTask", "daily", "SchedulerGroup", "scheduler", b"updated"
    )
    assert (second.task, second.group) == (first.task, first.group)
    assert second.value == b"updated"
    assert len(config_table.select()) == 1


def test_config_table_identity_is_task_and_group_only(config_table):
    config_table.upsert_group("TaskA", "one", "GroupA", "main", b"a")
    config_table.upsert_group("TaskB", "one", "GroupB", "main", b"b")
    config_table.upsert_group("TaskA", "two", "GroupA", "main", b"c")
    config_table.upsert_group("TaskA", "one", "GroupA", "other", b"d")

    assert len(config_table.select()) == 3
    row = config_table.get_group("one", "main")
    assert row.value == b"b"
    assert (row.taskclass, row.groupclass) == ("TaskB", "GroupB")
    assert sorted(row.value for row in config_table.list_task_rows("one")) == [b"b", b"d"]


def test_config_table_list_groups_can_filter_group_class(config_table):
    config_table.upsert_group("Task", "instance", "GroupA", "one", b"a")
    config_table.upsert_group("Task", "instance", "GroupB", "two", b"b")

    rows = config_table.list_groups("instance", groupclass="GroupB")
    assert [(row.groupclass, row.group) for row in rows] == [("GroupB", "two")]


def test_config_table_missing_group_returns_none(config_table):
    assert config_table.get_group("instance", "missing") is None


def test_config_table_read_helpers_support_exact_events(config_table):
    config_table.upsert_group("Task", "a", "Group", "one", b"one")
    config_table.upsert_group("Task", "b", "Group", "two", b"two")

    class Event:
        taskclass = "Task"
        task = "b"
        groupclass = "Group"
        group = "two"

    rows = config_table.read_rows([Event()])
    assert [(row.task, row.group, row.taskclass, row.groupclass, row.value) for row in rows] == [
        ("b", "two", "Task", "Group", b"two")
    ]

    rows = config_table.read_task_rows(tasks=["a"], taskclasses=["Task"])
    assert [row.value for row in rows] == [b"one"]

    assert config_table.read_rows([]) == []


def test_config_table_delete_group_and_task(config_table):
    config_table.upsert_group("Task", "a", "Group", "one", b"one")
    config_table.upsert_group("Task", "a", "Group", "two", b"two")
    config_table.upsert_group("Task", "b", "Group", "one", b"three")

    config_table.delete_group("a", "one")
    assert config_table.get_group("a", "one") is None
    config_table.delete_task("a")
    assert config_table.list_task_rows("a") == []
    assert len(config_table.list_task_rows("b")) == 1


def test_config_table_rejects_non_bytes(config_table):
    with pytest.raises(TypeError, match="must be bytes"):
        config_table.upsert_group("Task", "a", "Group", "one", "text")


def test_config_row_requires_all_identity_and_value_fields():
    with pytest.raises(TypeError):
        ConfigRow(task="a", group="one", taskclass="Task", groupclass="Group")


def _seed(table):
    table.upsert_group("TaskA", "a", "GroupA", "main", b"a")
    table.upsert_group("TaskA", "a", "GroupA", "extra", b"b")
    table.upsert_group("TaskB", "b", "GroupB", "main", b"c")


def test_read_task_rows_rejects_bad_group_identity(config_table):
    with pytest.raises(ValueError, match="task and group"):
        config_table.read_task_rows(groups=[("only-task",)])


def test_read_task_rows_without_conditions_returns_all(config_table):
    _seed(config_table)

    assert len(config_table.read_task_rows()) == 3


def test_read_task_rows_filters_by_task_and_class(config_table):
    _seed(config_table)

    rows = config_table.read_task_rows(
        tasks=["a"], taskclasses=["TaskA"]
    )

    assert sorted(row.value for row in rows) == [b"a", b"b"]

    assert config_table.read_task_rows(taskclasses=["TaskB"])[0].value == b"c"


def test_read_task_rows_accepts_exact_group_identity(config_table):
    _seed(config_table)

    rows = config_table.read_task_rows(groups=[("a", "extra"), ("b", "main")])

    assert sorted(row.value for row in rows) == [b"b", b"c"]


def test_read_rows_empty_and_with_events(config_table):
    _seed(config_table)

    class Event:
        task = "a"
        group = "main"

    assert config_table.read_rows([]) == []
    assert [row.value for row in config_table.read_rows([Event()])] == [b"a"]


def test_get_data_version_returns_integer(config_table):
    version = config_table.get_data_version()

    assert isinstance(version, int)


def test_upsert_group_with_cursor_returns_and_persists(config_table):
    with config_table.cursor() as cursor:
        row = config_table.upsert_group(
            "TaskA", "a", "GroupA", "main", b"x", _cursor_=cursor
        )
        cursor.commit()

    assert row.value == b"x"
    assert config_table.get_group("a", "main").value == b"x"


def test_list_groups_filter_and_delete_task(config_table):
    _seed(config_table)

    assert len(config_table.list_groups("a", groupclass="GroupA")) == 2
    assert config_table.list_groups("a", groupclass="Missing") == []

    config_table.delete_task("a")
    assert config_table.list_task_rows("a") == []
    assert len(config_table.list_task_rows("b")) == 1
