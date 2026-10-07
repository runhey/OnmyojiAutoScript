"""Display and save example Slider values and their JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Slider


class SliderConfig(BaseModel):
    """Example configuration containing integer and floating-point sliders."""

    age: int = Slider.int(
        default=18,
        ge=0,
        le=150,
        step=1,
        description="年龄",
        icon="user",
    )
    score: float = Slider.float(
        default=50.0,
        ge=0.0,
        le=100.0,
        step=0.5,
        description="分数",
        icon="chart",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_slider_json() -> dict:
    return SliderConfig().model_dump(mode="json")


def export_slider_schema() -> dict:
    return SliderConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_slider_json()
    schema_data = export_slider_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "slider_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "slider_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Slider JSON")
    console.print_json(data=json_data)
    console.rule("Slider JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
