"""Display and save example Button values and their JSON Schema."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.args import Button


class ButtonConfig(BaseModel):
    """Example configuration containing stateful boolean button fields."""

    selected: bool = Button.field(
        default=False,
        description='是否选中',
        icon='check',
    )
    active: bool = Button.field(
        default=True,
        description='是否激活',
        icon='power',
    )


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / 'show-tmp'


def export_button_json() -> dict:
    return ButtonConfig().model_dump(mode='json')


def export_button_schema() -> dict:
    return ButtonConfig.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    json_data = export_button_json()
    schema_data = export_button_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / 'button_json.json').write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    (OUTPUT_DIRECTORY / 'button_schema.json').write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    console.rule('Button JSON')
    console.print_json(data=json_data)
    console.rule('Button JSON Schema')
    console.print_json(data=schema_data)


if __name__ == '__main__':
    main()
