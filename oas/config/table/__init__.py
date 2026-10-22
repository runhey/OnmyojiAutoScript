"""Configuration database tables."""

from oas.config.table.config import ConfigRow as ConfigRow
from oas.config.table.config import ConfigTable as ConfigTable
from oas.config.table.key import JwtSecret as JwtSecret
from oas.config.table.key import KeyTable as KeyTable
from oas.config.table.key import KeyValue as KeyValue
from oas.config.table.menu import MenuGroupRow as MenuGroupRow
from oas.config.table.menu import MenuGroupTable as MenuGroupTable
from oas.config.table.menu import MenuSchemeRow as MenuSchemeRow
from oas.config.table.menu import MenuSchemeTable as MenuSchemeTable
from oas.config.table.menu import MenuTaskRow as MenuTaskRow
from oas.config.table.menu import MenuTaskTable as MenuTaskTable
from oas.config.table.scan import ConfigExtra as ConfigExtra
from oas.config.table.scan import ConfigFile as ConfigFile
from oas.config.table.scan import ConfigInfo as ConfigInfo
from oas.config.table.scan import DndRequest as DndRequest
from oas.config.table.scan import ScanTable as ScanTable
