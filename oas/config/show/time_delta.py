"""Display and save an example TimeDelta value and its JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import TimeDelta


class TimeDeltaConfig(BaseModel):
    """Example configuration containing an elapsed-time field."""

    interval: TimeDelta = TimeDelta.field(
        default=TimeDelta(hours=6),
        # description="失败后的重试间隔",
        icon="timer",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_time_delta_json() -> dict:
    return TimeDeltaConfig().model_dump(mode="json")


def export_time_delta_schema() -> dict:
    return TimeDeltaConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_time_delta_json()
    schema_data = export_time_delta_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "time_delta_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "time_delta_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("TimeDelta JSON")
    console.print_json(data=json_data)
    console.rule("TimeDelta JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
