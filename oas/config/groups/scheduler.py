"""Reusable scheduling configuration Group."""

from oas.config.models.args import DateTime, Input, Switch, Time, TimeDelta
from oas.config.models.groups import GroupBase


class SchedulerGroup(GroupBase):
    """Shared scheduler settings used by Tasks.

    The fields and defaults match ``tasks.Component.config_scheduler.Scheduler``.
    A Task can reuse this Group and apply Task-specific schema overrides without
    changing the shared scheduler definition.
    """

    enable: bool = Switch.field(default=False, description="enable_help")
    next_run: DateTime = DateTime.field(
        default=DateTime.fromisoformat("2023-01-01 00:00:00"),
        description="next_run_help",
    )
    priority: int = Input.int(default=5, description="priority_help")

    success_interval: TimeDelta = TimeDelta.field(
        default=TimeDelta(days=1),
        description="success_interval_help",
    )
    failure_interval: TimeDelta = TimeDelta.field(
        default=TimeDelta(days=1),
        description="failure_interval_help",
    )
    server_update: Time = Time.field(
        default=Time(hour=9, minute=0, second=0),
        description="server_update_help",
    )
    delay_date: int = Input.int(
        default=1,
        ge=1,
        le=31,
        description="delay_date_help",
    )
    float_time: Time = Time.field(
        default=Time(hour=0, minute=0, second=0),
        description="float_time_help",
    )
