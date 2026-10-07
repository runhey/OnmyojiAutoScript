"""Display and save an example Option value and its JSON Schema."""

import json
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.show.debug_models import Config, Priority


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_option_json() -> dict:
    return Config(priority=Priority.HIGH).model_dump(mode="json")


def export_option_json_schema() -> dict:
    return Config.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_option_json()
    schema_data = export_option_json_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "option_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "option_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Option JSON")
    console.print_json(data=json_data)
    console.rule("Option JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
