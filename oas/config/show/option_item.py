"""Display and save the serializable definition stored by each OptionItem."""

import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.show.debug_models import Priority


console = Console(legacy_windows=False)


def export_option_items() -> dict[str, dict[str, Any]]:
    result = {}
    for name, member in Priority.__members__.items():
        field_info = member.option_item.field_info
        result[name] = {
            "value": member.value,
            "title": field_info.title,
            "description": field_info.description,
            "default": field_info.default,
            "json_schema_extra": field_info.json_schema_extra,
        }
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = export_option_items()
    path = Path(__file__).resolve().parents[1] / "show-tmp" / (Path(__file__).stem + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=repr) + "\n", encoding="utf-8")
    console.print_json(data=data, default=repr)


if __name__ == "__main__":
    main()



