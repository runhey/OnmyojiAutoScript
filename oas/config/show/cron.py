"""Display and save an example Cron value and its JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Cron


class CronConfig(BaseModel):
    """Example configuration containing a cron schedule field."""

    schedule: Cron = Cron.field(
        default=Cron("*/5 * * * *"),
        icon="calendar",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_cron_json() -> dict:
    return CronConfig().model_dump(mode="json")


def export_cron_schema() -> dict:
    return CronConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_cron_json()
    schema_data = export_cron_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "cron_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "cron_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Cron JSON")
    console.print_json(data=json_data)
    console.rule("Cron JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
