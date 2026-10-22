"""Display the configuration model classes registered in this process.

Importing ``debug_models`` intentionally loads the demonstration Task and Group
classes, which lets the model registration hooks run before the registry is
printed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console(legacy_windows=False)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "show-tmp"
OUTPUT_FILE = OUTPUT_DIRECTORY / "registry.json"


def print_registry(registry) -> None:
    """Print registered Task and Group classes in a readable hierarchy."""

    data = dict(registry.data)
    console.print(
        Panel(
            f"[bold cyan]{len(registry.task_classes)}[/bold cyan] TaskClass  ·  "
            f"[bold green]{len(registry.group_classes)}[/bold green] GroupClass",
            title="Configuration Model Registry",
            border_style="bright_blue",
            expand=False,
        )
    )

    console.print("\n[bold]Task → Group relationships[/bold]")
    tasks = sorted(registry.task_classes.items())
    if not tasks:
        console.print("(none)")
    else:
        tree = Tree("[bold cyan]TaskClass[/bold cyan]")
        for task_name, task_type in tasks:
            task_branch = tree.add(
                f"[bold cyan]{task_name}[/bold cyan] "
                f"[dim]({task_type.__module__}.{task_type.__qualname__})[/dim]"
            )
            group_names = data.get(task_name, [])
            if not group_names:
                task_branch.add("[dim](no GroupClass fields)[/dim]")
                continue
            for group_name in group_names:
                group_type = registry.group_index[(task_name, group_name)]
                task_branch.add(
                    f"[green]{group_name}[/green] "
                    f"[dim]({group_type.__module__}.{group_type.__qualname__})[/dim]"
                )
        console.print(tree)

    console.print("\n[bold]GroupClass index[/bold]")
    groups = sorted(registry.group_classes.items())
    if not groups:
        console.print("(none)")
    else:
        group_table = Table(
            show_header=True,
            header_style="bold green",
            box=None,
            padding=(0, 2),
        )
        group_table.add_column("GroupClass", style="green")
        group_table.add_column("Python class", style="dim")
        for group_name, group_type in groups:
            group_table.add_row(
                group_name,
                f"{group_type.__module__}.{group_type.__qualname__}",
            )
        console.print(group_table)

    console.print("\n[bold]Serialized registry data[/bold]")
    console.print_json(data=data)


def main() -> None:
    """Load the local demonstration models and print the registry contents."""

    # Keep this file runnable both as a module and as a standalone script.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from oas.config.models.registry import config_model_registry
    from oas.config.show.debug_models import DebugGroup, DebugTask  # noqa: F401

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(dict(config_model_registry.data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print_registry(config_model_registry)


if __name__ == "__main__":
    main()
