"""Models used only by the local Option export demonstrations."""

import sys
from pathlib import Path

from pydantic import BaseModel

# The directory name contains a hyphen, so these files are run directly rather
# than as a package module. Add the repository root for the absolute import.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Option, OptionItem


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



