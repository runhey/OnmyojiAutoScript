"""Menu operations exposed by the Mod runtime.

This class only declares the public API.  Every method receives a ``result``
as its second positional argument; the ``modmenu`` decorator computes that
result, and the method returns it unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from oas.config.entry.mod_menu import modmenu


class MenuMod:
    """Menu CRUD operations exposed by the Mod runtime.

    Implementations live in :class:`oas.config.entry.mod_menu.modmenu`.
    ``modmenu`` mounts one ``MenuEntry`` per instance, so this class only has
    to carry the configuration name.

    Full parameter, return-value, and error documentation lives on the
    corresponding ``modmenu.menu_*`` decorator factory; each method below only
    returns the decorator-computed ``result``.
    """

    def __init__(self, config_name: str):
        self.config_name = config_name

    # ------------------------------------------------------------------
    # Scheme operations
    # ------------------------------------------------------------------

    @modmenu.menu_scheme_list()
    def menu_scheme_list(
        self,
        result: list[dict[str, Any]],
        config_name: str,
    ) -> list[dict[str, Any]]:
        """List every menu scheme with its groups and tasks."""
        return result

    @modmenu.menu_scheme_get()
    def menu_scheme_get(
        self,
        result: dict[str, Any],
        config_name: str,
        name: str,
    ) -> dict[str, Any]:
        """Read one scheme; a missing scheme raises ``KeyError``."""
        return result

    @modmenu.menu_scheme_add()
    def menu_scheme_add(
        self,
        result: dict[str, Any],
        config_name: str,
        name: str,
        groups: Mapping[str, Sequence[str]] | None = None,
        *,
        order: int | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        """Create a scheme and its groups in one transaction."""
        return result

    @modmenu.menu_scheme_update()
    def menu_scheme_update(
        self,
        result: dict[str, Any],
        config_name: str,
        name: str,
        *,
        new_name: str | None = None,
        order: int | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        """Rename, reorder, or change the default flag of a scheme."""
        return result

    @modmenu.menu_scheme_delete()
    def menu_scheme_delete(
        self,
        result: bool,
        config_name: str,
        name: str,
    ) -> bool:
        """Delete a scheme; a missing scheme raises ``KeyError``."""
        return result

    @modmenu.menu_scheme_copy()
    def menu_scheme_copy(
        self,
        result: dict[str, Any],
        config_name: str,
        source: str,
        target: str,
    ) -> dict[str, Any]:
        """Copy a scheme to the end of the scheme list."""
        return result

    @modmenu.menu_scheme_replace()
    def menu_scheme_replace(
        self,
        result: dict[str, Any],
        config_name: str,
        name: str,
        groups: Mapping[str, Sequence[str]],
    ) -> dict[str, Any]:
        """Replace the groups of an existing scheme."""
        return result

    @modmenu.menu_scheme_seed()
    def menu_scheme_seed(
        self,
        result: list[dict[str, Any]],
        config_name: str,
        menus: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    ) -> list[dict[str, Any]]:
        """Create the default menu schemes that do not exist yet."""
        return result

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    @modmenu.menu_group_get()
    def menu_group_get(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
    ) -> dict[str, Any]:
        """Read one group inside a scheme."""
        return result

    @modmenu.menu_group_add()
    def menu_group_add(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        tasks: Sequence[str] = (),
        *,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        """Create a group and its tasks in one transaction."""
        return result

    @modmenu.menu_group_update()
    def menu_group_update(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        *,
        new_group: str | None = None,
        order: int | None = None,
        title: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> dict[str, Any]:
        """Rename, reorder, or edit the metadata of a group."""
        return result

    @modmenu.menu_group_delete()
    def menu_group_delete(
        self,
        result: bool,
        config_name: str,
        scheme: str,
        group: str,
    ) -> bool:
        """Delete a group and its tasks."""
        return result

    @modmenu.menu_group_copy()
    def menu_group_copy(
        self,
        result: dict[str, Any],
        config_name: str,
        source_scheme: str,
        source_group: str,
        target_scheme: str,
        target_group: str,
    ) -> dict[str, Any]:
        """Copy a group, including its metadata, to the end of a scheme."""
        return result

    @modmenu.menu_group_move()
    def menu_group_move(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Move a group to another position inside the same scheme."""
        return result

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    @modmenu.menu_task_get()
    def menu_task_get(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        task: str,
    ) -> dict[str, Any]:
        """Read one task inside a group."""
        return result

    @modmenu.menu_task_add()
    def menu_task_add(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        task: str,
        *,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Append or insert a task in a group."""
        return result

    @modmenu.menu_task_delete()
    def menu_task_delete(
        self,
        result: bool,
        config_name: str,
        scheme: str,
        group: str,
        task: str,
    ) -> bool:
        """Delete a task from a group."""
        return result

    @modmenu.menu_task_copy()
    def menu_task_copy(
        self,
        result: dict[str, Any],
        config_name: str,
        source_scheme: str,
        source_group: str,
        task: str,
        target_scheme: str,
        target_group: str,
        *,
        new_task: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Copy a task to another group."""
        return result

    @modmenu.menu_task_move()
    def menu_task_move(
        self,
        result: dict[str, Any],
        config_name: str,
        scheme: str,
        group: str,
        task: str,
        *,
        target_group: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        """Move a task within its group, or to another group."""
        return result
