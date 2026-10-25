"""Tests for the entry-layer msgspec structs and caches."""

import json
from datetime import UTC, datetime

import msgspec

from oas.config.entry.error import ConfigError
from oas.config.entry.model import (
    MOD_JSON_CACHE,
    ConfigEvents,
    ConfigSetEvent,
    DecoderCache,
    ModelConfigRef,
    ModelGroupRef,
    ModelNavRef,
    ModelTaskRef,
    ModJsonCacheTTL,
    TaskItem,
)


def test_config_events_event_builds_a_config_set_event():
    assert ConfigEvents.event('t', 'g', 'a', 1) == ConfigSetEvent(
        task='t', group='g', arg='a', value=1
    )


def test_config_events_failed_event_replaces_value_and_carries_the_error():
    event = ConfigSetEvent(task='t', group='g', arg='a', value=1)

    failed = ConfigEvents.failed_event(event, 'boom')

    assert (failed.task, failed.group, failed.arg) == ('t', 'g', 'a')
    assert failed.value is None
    assert isinstance(failed.error, ConfigError)
    assert failed.error.msg == 'boom'

    error = ConfigError('boom')
    reused = ConfigEvents.failed_event(event, error)

    assert reused.error is error


def test_config_set_event_error_defaults_to_none():
    event = ConfigSetEvent(task='t', group='g', arg='a', value=1)

    assert event.error is None


def test_model_config_ref_decodes_from_json():
    ref = msgspec.json.decode(
        b'{"task": ["A", "B"], "group": [["A", "g"]]}',
        type=ModelConfigRef,
    )

    assert ref.task == ['A', 'B']
    assert ref.group == [('A', 'g')]


def test_nested_model_refs_decode():
    nav = msgspec.json.decode(
        json.dumps(
            {
                'file': 'nav',
                'i18n': ['zh-CN'],
                'config': {'task': ['A'], 'group': []},
            }
        ).encode(),
        type=ModelNavRef,
    )
    group = msgspec.json.decode(
        b'{"file": "f", "cls": "G", "task": "A"}', type=ModelGroupRef
    )
    task = msgspec.json.decode(
        b'{"group": {}, "config": {"task": [], "group": []}}',
        type=ModelTaskRef,
    )

    assert nav.config.task == ['A']
    assert nav.i18n == ['zh-CN']
    assert (group.file, group.cls, group.task) == ('f', 'G', 'A')
    assert task.group == {}
    assert task.config.task == []


def test_task_item_str_uses_task_name_and_next_run():
    item = TaskItem('FindJade', datetime(2026, 10, 23, tzinfo=UTC))

    assert str(item) == (
        'Task(TaskName="FindJade", NextRun="2026-10-23 00:00:00+00:00")'
    )
    assert repr(item) == str(item)


def test_decoder_cache_is_a_singleton_with_cached_decoders():
    cache = DecoderCache()

    assert cache is DecoderCache()
    assert cache.MODEL_CONFIG_INDEX is cache.MODEL_CONFIG_INDEX
    assert cache.MODEL_TASK_INDEX is cache.MODEL_TASK_INDEX


def test_mod_json_cache_returns_default_for_missing_file(tmp_path):
    cache = ModJsonCacheTTL()

    assert cache.load_resource(str(tmp_path / 'missing.json')) == {}
    assert (
        cache.load_resource(str(tmp_path / 'missing.json'), default_factory=list) == []
    )


def test_mod_json_cache_returns_default_for_corrupt_file(tmp_path):
    file = tmp_path / 'broken.json'
    file.write_text('{ not json', encoding='utf-8')

    assert MOD_JSON_CACHE.load_resource(str(file)) == {}
