from oas.mod.info import ModEntryInfo


class ConfigConst:
    SCHEDULER_PRIORITY = """
    RestartDevice > RestartGame
    """


# default mod entry
# key: mod name, value: ModEntryInfo
DICT_MOD_ENTRY = {
    m.name: m
    for m in [
        ModEntryInfo(name='example_mod', root='ExampleMod'),
        ModEntryInfo(
            name='alas',
            root='AzurlaneAutoScript',
            asset_lang=dict.fromkeys(['cn', 'en', 'jp', 'tw']),
            gui_language=dict.fromkeys(['zh-CN', 'en-US', 'ja-JP', 'zh-TW']),
        ),
        ModEntryInfo(
            name='src',
            root='StarRailCopilot',
            asset_lang=dict.fromkeys(['cn', 'en']),
            gui_language=dict.fromkeys(['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'es-ES']),
        ),
        ModEntryInfo(
            name='oas',
            root='.',
            asset_lang=dict.fromkeys(['cn', 'en']),
            gui_language=dict.fromkeys(['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'es-ES']),
        ),
    ]
}
