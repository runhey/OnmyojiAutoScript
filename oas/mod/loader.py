"""Load the OAS Mod entry and expose its decorated configuration API."""

from typing import Any

from oas.ext.file.loadpy import LOADPY_CACHE
from oas.mod.const import DICT_MOD_ENTRY
from oas.mod.info import ModEntryInfo


class ModLoader:
    """Load ``ConfigGui`` and forward its Mixin methods directly."""

    def __init__(self) -> None:
        self.entry = ModEntryInfo.oas()
        self.gui = self._load_gui()

    def _load_gui(self) -> Any:
        """Load ``ConfigGui`` from the configured Mod entry directory.

        Returns:
            Any: The instantiated ``ConfigGui`` facade.

        Raises:
            ImportError: If ``config_gui.py`` does not define ``ConfigGui``.
        """
        file = self.entry.root.joinpath(self.entry.path_config).joinpath(
            'config_gui.py'
        )
        module = LOADPY_CACHE.get(file)
        try:
            config_gui = module.ConfigGui
        except AttributeError as exc:
            raise ImportError(f'Module {file} must define ConfigGui') from exc
        return config_gui()

    @property
    def dict_mod(self) -> 'dict[str, ModEntryInfo]':
        """Return declared Mod entries keyed by Mod name."""
        return {
            name: entry
            for name, entry in DICT_MOD_ENTRY.items()
            if name and entry.root.exists()
        }

    def get_mod(self, name: str = 'oas') -> Any:
        """Return the loaded ``ConfigGui`` for a declared Mod name.

        Args:
            name: Mod name. OAS currently supports ``"oas"``.

        Returns:
            Any: The loaded ``ConfigGui`` instance.

        Raises:
            KeyError: If ``name`` is not declared.
        """
        if name != self.entry.name:
            raise KeyError(f'No such mod: {name!r}')
        return self.gui

    def __getattr__(self, name: str) -> Any:
        """Forward decorated ``menu_*`` and ``config_*`` methods to ConfigGui.

        Args:
            name: Attribute or method name exposed by the loaded facade.

        Returns:
            Any: The corresponding bound attribute.
        """
        return getattr(self.gui, name)

    def __dir__(self) -> list[str]:
        """Include delegated facade members in introspection."""
        return sorted(set(super().__dir__()) | set(dir(self.gui)))


MOD_LOADER = ModLoader()
