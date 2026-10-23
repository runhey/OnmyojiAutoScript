"""Database bases used by configuration tables."""

from oas.db.table import Table
from oas.ext import env
from oas.ext.singleton import Singleton, SingletonNamed


class ConfigDB(Table, metaclass=SingletonNamed):
    """Open one SQLite database per configuration name."""

    @classmethod
    def config_file(cls, config_name: str):
        if config_name == ':memory:':
            return ':memory:'
        return env.PROJECT_ROOT / 'config' / f'{config_name}.db'

    def __init__(self, config_name: str):
        self.config_name = config_name
        super().__init__(self.config_file(config_name))


class GuiDB(Table, metaclass=Singleton):
    """Open the shared GUI metadata database."""

    def __init__(self):
        super().__init__(env.PROJECT_ROOT / 'config' / 'gui.db')


# Explicit aliases make migration from Alasio straightforward.
AlasioConfigDB = ConfigDB
AlasioGuiDB = GuiDB


__all__ = [
    'AlasioConfigDB',
    'AlasioGuiDB',
    'ConfigDB',
    'GuiDB',
]
