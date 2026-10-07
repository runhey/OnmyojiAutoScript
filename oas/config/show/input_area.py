"""Display and save example InputArea values and their JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import InputArea


class InputAreaConfig(BaseModel):
    """Example configuration containing multiline string inputs."""

    bio: str = InputArea.str(
        default="A multiline\nintroduction.",
        min_length=1,
        max_length=500,
        description="简介",
        icon="document",
    )
    note: str = InputArea.secret_str(
        default="A private\nmultiline note.",
        min_length=1,
        max_length=500,
        description="私密备注",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_input_area_json() -> dict:
    return InputAreaConfig().model_dump(mode="json")


def export_input_area_schema() -> dict:
    return InputAreaConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_input_area_json()
    schema_data = export_input_area_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "input_area_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "input_area_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("InputArea JSON")
    console.print_json(data=json_data)
    console.rule("InputArea JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
