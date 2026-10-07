"""Display and save an example Time value and its JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Time


class TimeConfig(BaseModel):
    """Example configuration containing a time-of-day field."""

    run_time: Time = Time.field(
        default=Time(19, 0),
        description="每天运行时间",
        icon="clock",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_time_json() -> dict:
    return TimeConfig().model_dump(mode="json")


def export_time_schema() -> dict:
    return TimeConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_time_json()
    schema_data = export_time_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "time_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "time_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Time JSON")
    console.print_json(data=json_data)
    console.rule("Time JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
