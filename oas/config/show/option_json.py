"""Display and save the JSON exported from the example Option field."""

import json
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from oas.config.show.debug_models import Config, Priority


console = Console(legacy_windows=False)


def export_option_json() -> str:
    return Config(priority=Priority.HIGH).model_dump_json()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw_json = export_option_json()
    data = json.loads(raw_json)
    path = Path(__file__).resolve().parents[1] / "show-tmp" / (Path(__file__).stem + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print_json(json=raw_json)


if __name__ == "__main__":
    main()



