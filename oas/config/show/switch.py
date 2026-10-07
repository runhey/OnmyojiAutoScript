"""Display and save example Switch values and their JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Switch


class SwitchConfig(BaseModel):
    """Example configuration containing boolean switch fields."""

    enabled: bool = Switch.field(
        default=False,
        description="是否启用",
        icon="power",
    )
    accepted: bool = Switch.field(
        default=True,
        description="是否接受条款",
        icon="check",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_switch_json() -> dict:
    return SwitchConfig().model_dump(mode="json")


def export_switch_schema() -> dict:
    return SwitchConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_switch_json()
    schema_data = export_switch_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "switch_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "switch_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Switch JSON")
    console.print_json(data=json_data)
    console.rule("Switch JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
