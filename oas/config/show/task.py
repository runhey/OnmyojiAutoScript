"""Display and save an example Task containing a complete Group."""

import json
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.models.tasks import SchemaRule
from oas.config.show.debug_models import DebugTask


console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / 'show-tmp'


def export_task_json() -> dict:
    """Return the example Task's serialized configuration."""

    return DebugTask().model_dump(mode='json')


def export_task_schema() -> dict:
    """Return the example Task's Pydantic JSON Schema."""

    DebugTask.schema_overrides(
        [
            SchemaRule(
                target='group.slider_int',
                operation='merge',
                value={'title': 'Task 专属整数滑块'},
            ),
            SchemaRule(
                target='group.cron',
                property='hide',
                value=True,
            ),
        ]
    )
    return DebugTask.model_json_schema()


def main() -> None:
    """Print and save the example Task JSON and JSON Schema."""

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    json_data = export_task_json()
    schema_data = export_task_schema()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / 'task_json.json').write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    (OUTPUT_DIRECTORY / 'task_schema.json').write_text(
        json.dumps(schema_data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    console.rule('Task JSON')
    console.print_json(data=json_data)
    console.rule('Task JSON Schema')
    console.print_json(data=schema_data)


if __name__ == '__main__':
    main()
