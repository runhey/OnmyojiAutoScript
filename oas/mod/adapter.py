from typing import Any


# Alasio compatibility layer.
#
# The methods below mirror ``alasio.config.entry.mod_base.ModBase`` so an
# Alasio Mod can be mounted in OAS without changing its entry code.  They are
# deliberately *not* used by the OAS native configuration runtime, which
# resolves Task/Group models through ``oas.config.models.registry`` instead of
# Alasio's generated JSON indexes (``_index/*.json``).
class ModAdapter:
    """Alasio-compatible adapter for a mounted Mod entry.

    The object is intentionally duck typed.  Its constructor accepts an entry
    object that provides the attributes needed by the current Mod layer, such
    as ``name`` and ``root``.  It stores that object as a single internal
    value instead of copying entry fields onto ``self``.

    The index and model-loading methods are kept as interface points for
    Alasio-compatible adapters.  OAS does not use Alasio's JSON index files,
    so these methods intentionally have no implementation here.
    """

    def __init__(self, entry: Any, config_name: str | None = None):
        self._entry = entry
        self._config_name = config_name

    @property
    def entry(self) -> Any:
        """Return the original Mod entry object."""
        return self._entry

    @property
    def config_name(self) -> str | None:
        """Return the configuration database name bound to this adapter."""
        return self._config_name

    def __str__(self) -> str:
        return f'{self.__class__.__name__}(name="{self._entry.name}", root="{self._entry.root}")'

    def __bool__(self) -> bool:
        return True

    def nav_index_data(self) -> Any:
        """Interface for loading a Mod navigation index."""
        raise NotImplementedError

    def queue_index_data(self) -> Any:
        """Interface for loading a Mod queue index."""
        raise NotImplementedError

    def config_index_data(self) -> Any:
        """Interface for loading a Mod configuration index."""
        raise NotImplementedError

    def task_index_data(self) -> Any:
        """Interface for loading a Mod task index."""
        raise NotImplementedError

    def nav_config_json(self, file: str) -> Any:
        """Interface for loading a navigation configuration file."""
        raise NotImplementedError

    def nav_i18n_json(self, file: str) -> Any:
        """Interface for loading navigation translations."""
        raise NotImplementedError

    def get_group_model(self, file: str, cls: str) -> Any:
        """Interface for loading a Group model from a Mod source."""
        raise NotImplementedError
