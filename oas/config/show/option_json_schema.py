"""Display and save the JSON Schema exported from the example Option field."""

import json
from pathlib import Path
import sys

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.show.debug_models import Config


console = Console(legacy_windows=False)


def export_option_json_schema() -> dict:
    return Config.model_json_schema()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = export_option_json_schema()
    path = Path(__file__).resolve().parents[1] / "show-tmp" / (Path(__file__).stem + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print_json(data=data)


if __name__ == "__main__":
    main()



