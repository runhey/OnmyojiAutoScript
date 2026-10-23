import os.path
from copy import deepcopy

from msgspec import Struct, field

from oas.ext import env
from oas.ext.path.calc import joinnormpath


class ModEntryInfo(Struct):
    """
    ModEntryInfo
    """

    # mod name
    name: str
    # absolute path to mod root folder, or relative path from running folder to mod root folder
    # default to ""
    root: str = ''
    # relative path from mod root to config folder,
    # where you have config.index.json, nav.index.json, model.index.json, and all config definitions
    path_config: str = 'module/config'
    # relative path from mod root to mod scheduler
    path_main: str = 'module/main.py'
    # relative path from mod root to assets folder
    path_assets: str = 'assets'
    # valid file extension of assets
    # png is commonly used because jpg is a lossy compression
    asset_ext: dict[str, None] = field(
        default_factory=lambda: dict.fromkeys(['.png', '.gif'])
    )
    # valid lang (or server) of assets
    # ASSETS_LANG must not in ASSETS_EXT, must not be empty string, must not be a digit
    asset_lang: dict[str, None] = field(
        default_factory=lambda: dict.fromkeys(['cn', 'en'])
    )
    # valid languages on GUI
    gui_language: dict[str, None] = field(
        default_factory=lambda: dict.fromkeys(['zh-CN', 'en-US'])
    )
    # folders to scan for task entry functions, relative to mod root
    # default to scan "module" and "tasks" folders
    task_entry_folders: dict[str, None] = field(
        default_factory=lambda: dict.fromkeys(['module', 'tasks'])
    )

    def copy(self):
        """
        Returns:
            ModEntryInfo:
        """
        return deepcopy(self)

    def exist(self):
        """
        Returns:
            bool:
        """
        # Mod must have config.index.json
        file = joinnormpath(self.root, self.path_config)
        file = joinnormpath(file, '_index/config.index.json')
        return os.path.exists(file)

    def iter_asset_lang(self):
        """
        Yields:
            str: share first, then asset_lang
        """
        yield ''
        yield from self.asset_lang

    @classmethod
    def alasio(cls):
        return cls(
            name='alasio',
            root=env.OAS_ROOT,
            path_config='oas/config',
            gui_language=dict.fromkeys(['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'en-ES']),
        )

    @classmethod
    def oas(cls):
        """Return the built-in OAS Mod entry description."""
        return cls(
            name='oas',
            root=env.OAS_ROOT,
            path_config='oas/config',
            gui_language=dict.fromkeys(['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'en-ES']),
        )
