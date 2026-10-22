"""Tests for GroupBase.to_dict() / from_dict()."""

import msgspec
import pytest
from pydantic import ValidationError

from oas.config.models.args import (
    Cron,
    DateTime,
    Input,
    Option,
    OptionItem,
    Options,
    Switch,
    Time,
    TimeDelta,
)
from oas.config.models.groups import GroupBase


class GroupIoPriority(Option):
    LOW = OptionItem.str("low", title="低")
    HIGH = OptionItem.str("high", title="高")


class GroupIoModes(Options):
    ALPHA = OptionItem.str("alpha", title="甲")
    BETA = OptionItem.str("beta", title="乙")


class GroupIoAll(GroupBase):
    """Group covering every persisted argument family."""

    name: str = Input.str(default="group", min_length=1)
    count: int = Input.int(default=3, ge=0)
    ratio: float = Input.float(default=0.5, ge=0.0)
    enabled: bool = Switch.field(default=True)
    mode: GroupIoPriority = Option.field(default=GroupIoPriority.LOW)
    modes: GroupIoModes = Options.field(default=[GroupIoModes.ALPHA])
    time: Time = Time.field(default=Time(9, 0))
    delta: TimeDelta = TimeDelta.field(default=TimeDelta(hours=1))
    date: DateTime = DateTime.field(default=DateTime(2026, 1, 1))
    cron: Cron = Cron.field(default=Cron("*/5 * * * *"))


def test_to_dict_matches_pydantic_python_dump():
    group = GroupIoAll()

    data = group.to_dict()

    assert data == group.model_dump(mode="python")
    assert data["time"] == "09:00:00"
    assert data["delta"] == "00 01:00:00"
    assert data["date"] == "2026-01-01 00:00:00"
    assert data["cron"] == "*/5 * * * *"
    assert data["mode"] == "low"
    assert data["modes"] == ["alpha"]


def test_to_dict_is_msgpack_encodable():
    data = GroupIoAll().to_dict()

    # No custom encoder hook is needed for any persisted argument family.
    assert msgspec.msgpack.decode(msgspec.msgpack.encode(data)) == data


def test_from_dict_roundtrip_preserves_values():
    group = GroupIoAll(
        name="roundtrip",
        count=9,
        ratio=1.25,
        enabled=False,
        mode=GroupIoPriority.HIGH,
        modes=[GroupIoModes.BETA],
        time=Time(21, 15),
        delta=TimeDelta(days=2, hours=3),
        date=DateTime(2027, 2, 3, 4, 5, 6),
        cron=Cron("0 12 * * 1-5"),
    )

    restored = GroupIoAll.from_dict(group.to_dict())

    assert restored == group


def test_from_dict_uses_defaults_for_missing_arguments():
    restored = GroupIoAll.from_dict({"count": 7})

    assert restored.count == 7
    assert restored.name == "group"
    assert restored.mode == GroupIoPriority.LOW


def test_from_dict_ignores_unknown_arguments():
    data = GroupIoAll().to_dict()
    data["removed_arg"] = 1

    assert GroupIoAll.from_dict(data) == GroupIoAll()


def test_from_dict_rejects_invalid_argument_value():
    with pytest.raises(ValidationError):
        GroupIoAll.from_dict({"count": -1})


def test_from_dict_returns_the_called_subclass():
    class GroupIoSubclass(GroupIoAll):
        pass

    restored = GroupIoSubclass.from_dict({"count": 2})

    assert type(restored) is GroupIoSubclass


class GroupErrOption(Option):
    A = OptionItem.str("a")
    B = OptionItem.str("b")


class GroupErrGroup(GroupBase):
    count: int = Input.int(default=1, ge=0)
    time: Time = Time.field(default=Time(0, 0))
    cron: Cron = Cron.field(default=Cron("* * * * *"))
    mode: GroupErrOption = Option.field(default=GroupErrOption.A)


@pytest.mark.parametrize(
    "payload",
    [
        {"count": -1},
        {"count": "not-an-int"},
        {"time": "99:00:00"},
        {"cron": "not-a-cron"},
        {"mode": "missing"},
    ],
)
def test_from_dict_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        GroupErrGroup.from_dict(payload)


@pytest.mark.parametrize("payload", [None, [], 1, "text"])
def test_from_dict_rejects_non_mappings(payload):
    with pytest.raises(ValidationError):
        GroupErrGroup.from_dict(payload)


def test_from_dict_ignores_unknown_fields():
    group = GroupErrGroup.from_dict({"unknown": 1})

    assert group == GroupErrGroup()


def test_from_dict_accepts_valid_option_value():
    group = GroupErrGroup.from_dict({"mode": "b"})

    assert group.mode == GroupErrOption.B
