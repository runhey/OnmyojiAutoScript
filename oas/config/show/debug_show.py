"""Print and save the three focused Option exports."""

import json
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.show.option_item import export_option_items
from oas.config.show.option import export_option_json, export_option_json_schema


console = Console(legacy_windows=False)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    option_item = export_option_items()
    option_json = export_option_json()
    option_json_schema = export_option_json_schema()
    data = {
        "option_item": option_item,
        "option_json": option_json,
        "option_json_schema": option_json_schema,
    }
    path = Path(__file__).resolve().parents[1] / "show-tmp" / (Path(__file__).stem + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=repr) + "\n", encoding="utf-8")

    console.rule("OptionItem")
    console.print_json(data=option_item, default=repr)
    console.rule("Option JSON")
    console.print_json(data=option_json)
    console.rule("Option JSON Schema")
    console.print_json(data=option_json_schema)


if __name__ == "__main__":
    main()



