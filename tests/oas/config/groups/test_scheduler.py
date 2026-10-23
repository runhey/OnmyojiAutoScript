"""Tests for the reusable scheduler Group."""

import pytest
from pydantic import ValidationError

from oas.config.groups.scheduler import SchedulerGroup
from oas.config.models.args import DateTime, Time, TimeDelta


def test_defaults():
    group = SchedulerGroup()

    assert group.enable is False
    assert group.next_run == DateTime(2023, 1, 1)
    assert group.priority == 5
    assert group.success_interval == TimeDelta(days=1)
    assert group.failure_interval == TimeDelta(days=1)
    assert group.server_update == Time(9, 0)
    assert group.delay_date == 1
    assert group.float_time == Time(0, 0)


def test_to_dict_uses_component_serializers():
    data = SchedulerGroup().to_dict()

    assert data['next_run'] == '2023-01-01 00:00:00'
    assert data['success_interval'] == '01 00:00:00'
    assert data['server_update'] == '09:00:00'
    assert data['float_time'] == '00:00:00'


def test_from_dict_roundtrip():
    group = SchedulerGroup.from_dict(
        {
            'enable': True,
            'priority': 9,
            'server_update': '06:30:00',
            'success_interval': '02 03:04:05',
        }
    )

    assert group.enable is True
    assert group.priority == 9
    assert group.server_update == Time(6, 30)
    assert group.success_interval == TimeDelta(days=2, hours=3, minutes=4, seconds=5)


def test_schema_covers_every_field():
    schema = SchedulerGroup.model_json_schema()

    assert set(schema['properties']) == set(SchedulerGroup.model_fields)
    assert schema['properties']['server_update']['type'] == 'Time'
    assert schema['properties']['success_interval']['type'] == 'TimeDelta'


@pytest.mark.parametrize(
    'payload',
    [
        {'priority': 'not-an-int'},
        {'server_update': '25:00:00'},
        {'server_update': '09:60:00'},
        {'success_interval': 'not-an-interval'},
        {'failure_interval': '1 24:00:00'},
        {'delay_date': 0},
        {'delay_date': 32},
        {'next_run': 'not-a-date'},
        {'float_time': '9'},
    ],
)
def test_from_dict_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        SchedulerGroup.from_dict(payload)


@pytest.mark.parametrize('payload', [None, [], 1, 'text'])
def test_from_dict_rejects_non_mappings(payload):
    with pytest.raises(ValidationError):
        SchedulerGroup.from_dict(payload)


def test_from_dict_ignores_unknown_fields():
    group = SchedulerGroup.from_dict({'unknown': 1})

    assert group == SchedulerGroup()


def test_from_dict_accepts_empty_payload():
    assert SchedulerGroup.from_dict({}) == SchedulerGroup()
