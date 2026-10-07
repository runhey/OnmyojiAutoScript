"""Display and save the JSON and JSON Schema for a multi-select Option field."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import OptionItem, Options


class Prioritys(Options):
    """Example multi-select option used by this export script."""

    HIGH = OptionItem.str("high", title="高优先级", icon="fire")
    MEDIUM = OptionItem.str("medium", title="中优先级")
    LOW = OptionItem.str("low",)


class OptionsConfig(BaseModel):
    """Example configuration where all Priority options are multi-selectable."""

    prioritys: Prioritys = Options.field(
        description="选多个优先级",
        icon="tag",
        default=[Prioritys.HIGH, Prioritys.LOW],
        depends="test depends",
        alias='alias',
        hide=True,
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_options_json() -> dict:
    return OptionsConfig().model_dump(mode="json")


def export_options_schema() -> dict:
    return OptionsConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_options_json()
    schema_data = export_options_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "options_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "options_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Options JSON")
    console.print_json(data=json_data)
    console.rule("Options JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
