"""庭院菜单主题。原地更新共享规则，保持导航图持有的对象引用有效。"""
from copy import deepcopy

from tasks.Component.Costume.config import ThemeType
from tasks.Component.CostumeTheme.assets import CostumeThemeAssets
from tasks.GameUi.assets import GameUiAssets


_THEME_NAMES = (
    'I_MAIN_SCROLL_CLOSE',
    'I_MAIN_GOTO_COLLECTION', 'I_MAIN_GOTO_TRAVEL',
    'I_MAIN_GOTO_TEAM', 'I_MAIN_GOTO_GUILD', 'I_MAIN_GOTO_MALL',
    'I_MAIN_GOTO_DAILY', 'I_MAIN_GOTO_FRIENDS', 'I_MAIN_GOTO_ONMYODO',
    'I_MAIN_GOTO_SHIKIGAMI_RECORDS',
)
# Capture pristine defaults before any task can select a menu theme.
_DEFAULT_RULES = {name: deepcopy(getattr(GameUiAssets, name)) for name in _THEME_NAMES}
_THEME_RULES = {
    ThemeType.COSTUME_THEME_DEFAULT: _DEFAULT_RULES,
    ThemeType.COSTUME_THEME_XINYU_MINGXIAO: {
        # Entry icons use the shared GameUi defaults, not theme-specific copies.
        **_DEFAULT_RULES,
        'I_MAIN_SCROLL_CLOSE': CostumeThemeAssets.I_MAIN_SCROLL_CLOSE_2,
    },
}


def apply_theme(theme_type: ThemeType) -> None:
    rules = _THEME_RULES[theme_type]
    for name, source in rules.items():
        target = getattr(GameUiAssets, name)
        # Reset cached image/name/features and match state as well as file/ROI.
        # Do NOT replace the object: page transitions retain references to it.
        target.__dict__.clear()
        target.__dict__.update(deepcopy(source.__dict__))
