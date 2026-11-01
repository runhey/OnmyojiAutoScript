from oas.config.runtime.config_mod import ConfigModMixin
from oas.config.runtime.menu_mod import MenuModMixin


class ConfigGui(ConfigModMixin, MenuModMixin):
    """Stateless GUI facade; every operation receives ``config_name``."""

    pass
