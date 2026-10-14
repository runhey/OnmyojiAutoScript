"""Models used by the local configuration export demonstrations."""

import sys
from pathlib import Path

from pydantic import BaseModel, Field

# The directory name contains a hyphen, so these files are run directly rather
# than as a package module. Add the repository root for the absolute import.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import (
    Cron,
    DateTime,
    Input,
    InputArea,
    Option,
    OptionItem,
    Options,
    Slider,
    Switch,
    Time,
    TimeDelta,
)
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import SchemaRule, TaskBase, schema


class Priority(Option):
    HIGH = OptionItem.str(
        "high",
        title="高优先级",
        description="最紧急",
        icon="fire",
        alias="priority_high",
        hide=False,
    )
    MEDIUM = OptionItem.str(
        "medium",
        title="中优先级",
        hide=True,
    )
    LOW = OptionItem.str(
        "low",
        title="低优先级",
    )


class Config(BaseModel):
    priority: Priority = Option.field()
    priority_low: Priority = Option.field(
        description="选个优先级",
        icon="priority",
        alias="priority",
        hide=True,
        default=Priority.LOW,
        depends="one depends: {}"
    )


class DebugOptions(Options):
    """Multi-select options used by the Group demonstration."""

    FIRST = OptionItem.str("first", title="第一项")
    SECOND = OptionItem.str("second", title="第二项")


class DebugGroup(GroupBase):
    """Example Group containing every currently supported argument family."""

    input_int: int = Input.int(
        default=18,
        ge=0,
        le=150,
        description="整数输入",
        icon="number",
    )
    input_float: float = Input.float(
        default=3.14,
        ge=0.0,
        description="浮点输入",
        icon="decimal",
    )
    input_str: str = Input.str(
        default="hello",
        min_length=1,
        description="单行文本",
        icon="text",
    )
    input_secret: str = Input.secret_str(
        default="secret",
        description="密码输入",
        icon="lock",
    )
    input_area: str = InputArea.str(
        default="第一行\n第二行",
        description="多行文本",
        icon="align-left",
    )
    input_area_secret: str = InputArea.secret_str(
        default="private\ntext",
        description="多行密码",
        icon="lock",
    )
    switch: bool = Switch.field(
        default=True,
        description="开关",
        icon="toggle",
    )
    slider_int: int = Slider.int(
        default=5,
        ge=0,
        le=10,
        step=1,
        description="整数滑块",
        icon="sliders",
    )
    slider_float: float = Slider.float(
        default=0.5,
        ge=0.0,
        le=1.0,
        step=0.1,
        description="浮点滑块",
        icon="sliders",
    )
    option: Priority = Option.field(
        default=Priority.MEDIUM,
        description="单选",
        icon="list",
    )
    options: DebugOptions = Options.field(
        default=[DebugOptions.FIRST],
        description="多选",
        icon="list-check",
    )
    time: Time = Time.field(
        default=Time(9, 30),
        description="时间",
        icon="clock",
    )
    time_delta: TimeDelta = TimeDelta.field(
        default=TimeDelta(hours=1),
        description="时间间隔",
        icon="timer",
    )
    date_time: DateTime = DateTime.field(
        default=DateTime(2026, 10, 8, 9, 0),
        description="日期时间",
        icon="calendar",
    )
    cron: Cron = Cron.field(
        default=Cron("*/5 * * * *"),
        description="Cron 表达式",
        icon="calendar-clock",
    )


class DebugTask(TaskBase):
    """Example Task containing the complete demonstration Group."""

    group: DebugGroup = Field(
        default_factory=DebugGroup,
        description="包含全部参数类型的示例组",
    )

    @classmethod
    @schema.hide("group.input_float", "group.input_area_secret")
    @schema.icon("group", "settings")
    @schema.description("group.switch", "Task 专属的开关说明")
    def schema_overrides(cls, rules: list[SchemaRule]) -> None:
        """Demonstrate Task-local Group schema overrides."""

        cls._pending_schema_rules.extend(rules)

