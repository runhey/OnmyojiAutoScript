"""Load the OAS Mod entry and expose its configuration facade.

The loader resolves ``config_gui.py`` from ``ModEntryInfo.root`` and
``ModEntryInfo.path_config``.  Entry metadata remains the source of truth for
the module location.
"""

from typing import Any

from oas.mod.const import DICT_MOD_ENTRY
from oas.mod.info import ModEntryInfo
from oas.ext.file.loadpy import LOADPY_CACHE


class ModLoader:
    """Load one Mod entry and forward its public configuration API.

    ``ConfigGui`` owns the decorated methods.  The loader does not duplicate
    them; missing attributes are delegated to the loaded facade.
    """

    def __init__(self) -> None:
        self.entry = ModEntryInfo.oas()
        self.gui = self._load_gui()

    def _load_gui(self) -> Any:
        """Load and instantiate ``ConfigGui`` from the entry config directory.

        Returns:
            Any: The instantiated ``ConfigGui`` facade.

        Raises:
            ImportError: If the module cannot be loaded or does not define
                ``ConfigGui``.
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
        """Return the declared built-in Mod entries, keyed by Mod name.

        Upstream builds this from Alasio's ``_index/*.json`` folders: a self
        mod discovered at ``module/config/const.py`` plus every entry whose
        folder looks like a mod. OAS declares its mods in ``oas/mod/const.py``
        and resolves models through ``oas.config.models.registry`` instead of
        index files, so the declared name is the key and the only check is
        that the entry root exists.

        Returns:
            dict[str, ModEntryInfo]: Mod name to entry, empty when the root
                is missing.
        """
        return {
            name: entry
            for name, entry in DICT_MOD_ENTRY.items()
            if name and entry.root.exists()
        }

    def get_mod(self, name: str = 'oas') -> Any:
        """Return the loaded facade for the named built-in Mod.

        Args:
            name: Mod name. OAS currently supports only ``"oas"``.

        Returns:
            Any: The loaded ``ConfigGui`` facade.

        Raises:
            KeyError: If ``name`` is not the built-in OAS Mod name.
        """
        if name != self.entry.name:
            raise KeyError(f'No such mod: {name!r}')
        return self.gui

    def __getattr__(self, name: str) -> Any:
        """Forward API methods and attributes to the loaded ``ConfigGui``.

        Args:
            name: Attribute or decorated API method name.

        Returns:
            Any: The corresponding attribute bound to ``self.gui``.

        Raises:
            AttributeError: If the loaded facade has no such attribute.
        """
        return getattr(self.gui, name)

    def __dir__(self) -> list[str]:
        """Include delegated facade methods in introspection and IDE support.

        Returns:
            list[str]: Attribute names available on the loader and facade.
        """
        return sorted(set(super().__dir__()) | set(dir(self.gui)))


MOD_LOADER = ModLoader()
