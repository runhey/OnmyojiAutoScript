"""Display and save an example DateTime value and its JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import DateTime


class DateTimeConfig(BaseModel):
    """Example configuration containing an absolute datetime field."""

    next_run: DateTime = DateTime.field(
        default=DateTime(2026, 10, 7, 9, 0),
        # description="下一次运行时间",
        icon="calendar",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_date_time_json() -> dict:
    return DateTimeConfig().model_dump(mode="json")


def export_date_time_schema() -> dict:
    return DateTimeConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_date_time_json()
    schema_data = export_date_time_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "date_time_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "date_time_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("DateTime JSON")
    console.print_json(data=json_data)
    console.rule("DateTime JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
