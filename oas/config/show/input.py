"""Display and save example Input values and their JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Input


class InputConfig(BaseModel):
    """Example configuration containing every supported Input factory."""

    age: int = Input.int(
        ge=0,
        le=150,
        description="年龄",
        icon="user",
        default=18,
    )
    score: float = Input.float(
        ge=0.0,
        le=100.0,
        description="分数",
        default=95.5,
    )
    name: str = Input.str(
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z]+$",
        description="姓名",
        default="Alice",
    )
    password: str = Input.secret_str(
        min_length=8,
        description="密码",
        default="password",
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"


def export_input_json() -> dict:
    return InputConfig().model_dump(mode="json")


def export_input_schema() -> dict:
    return InputConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    json_data = export_input_json()
    schema_data = export_input_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "input_json.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIRECTORY / "input_schema.json").write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    console.rule("Input JSON")
    console.print_json(data=json_data)
    console.rule("Input JSON Schema")
    console.print_json(data=schema_data)


if __name__ == "__main__":
    main()
