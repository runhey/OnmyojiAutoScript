"""Tests for the demonstration Task/Group models."""

import pytest

from oas.config.entry.store import TaskStore
from oas.config.models.groups import GroupBase
from oas.config.show.debug_models import (
    DebugExtraGroup,
    DebugGroup,
    DebugSecondTask,
    DebugTask,
)


@pytest.mark.parametrize("task_class", [DebugTask, DebugSecondTask])
def test_each_demo_task_has_exactly_two_distinct_group_classes(task_class):
    task = task_class()

    classes = {
        type(getattr(task, field_name))
        for field_name in task_class.model_fields
    }

    assert len(classes) == 2
    assert all(issubclass(cls, GroupBase) for cls in classes)


def test_debug_task_contains_the_two_demo_groups():
    task = DebugTask()

    assert isinstance(task.group, DebugGroup)
    assert isinstance(task.extra, DebugExtraGroup)
    assert list(task.to_dict()) == ["group", "extra"]


def test_debug_task_store_roundtrip(memory_config):
    task = DebugTask()

    TaskStore.save(":memory:", task, "DebugTask@debug")

    assert TaskStore.load(":memory:", DebugTask, "DebugTask@debug") == task
