"""Tests for the mutable runtime state defaults."""

from oas.config.runtime.config_state import ConfigAccessState


def test_state_defaults():
    state = ConfigAccessState("default")

    assert state.config_name == "default"
    assert state.task == ""
    assert state.auto_save is True
    assert state.is_template_config is False
    assert state._config_cached is False
    assert state._data_version == (0, 0)
    assert state._dict_row == {}
    assert state._dict_group == {}
    assert state._modified == {}
    assert state._override_config == {}
    assert state._override_const == {}
    assert state._override_prev_config == {}
    assert state._local.batch_depth == 0


def test_state_keeps_task_name():
    state = ConfigAccessState("default", "Task@one")

    assert state.task == "Task@one"


def test_template_config_disables_auto_save():
    state = ConfigAccessState("template-default")

    assert state.is_template_config is True
    assert state.auto_save is False


def test_non_template_prefix_still_enables_auto_save():
    state = ConfigAccessState("my-template")

    assert state.is_template_config is False
    assert state.auto_save is True
