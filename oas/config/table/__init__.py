"""Configuration database tables."""

from oas.config.table.config import ConfigRow, ConfigTable
from oas.config.table.key import JwtSecret, KeyTable, KeyValue
from oas.config.table.scan import ConfigExtra, ConfigFile, ConfigInfo, DndRequest, ScanTable

__all__ = [
    "ConfigExtra",
    "ConfigFile",
    "ConfigInfo",
    "ConfigRow",
    "ConfigTable",
    "DndRequest",
    "JwtSecret",
    "KeyTable",
    "KeyValue",
    "ScanTable",
]
