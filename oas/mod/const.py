from oas.mod.info import ModEntryInfo


class ConfigConst:
    SCHEDULER_PRIORITY = """
    RestartDevice > RestartGame
    """


# default mod entry
# key: mod name, value: ModEntryInfo
DICT_MOD_ENTRY = {m.name: m for m in [ModEntryInfo.oas()]}
