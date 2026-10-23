"""Default UI menu layout for registered configuration Tasks."""

from __future__ import annotations

# The insertion order of this mapping is the default order shown by the UI.
# A Task must be listed here to be displayed in the default menu.
DEFAULT_MENU: dict[str, list[str]] = {
    'Script': ['Script', 'Restart', 'GlobalGame', 'DebugSecondTask', 'DebugTask'],
    'Soul Zones': [
        'Orochi',
        'Sougenbi',
        'FallenSun',
        'EternitySea',
        'SixRealms',
    ],
    'Daily Task': [
        'DailyTrifles',
        'AreaBoss',
        'GoldYoukai',
        'ExperienceYoukai',
        'Nian',
        'TalismanPass',
        'DemonEncounter',
        'Pets',
        'SoulsTidy',
        'Delegation',
        'WantedQuests',
        'Tako',
        'AutoCheckinBigGod',
    ],
    'Liver Emperor Exclusive': [
        'BondlingFairyland',
        'EvoZone',
        'GoryouRealm',
        'Exploration',
        'Hyakkiyakou',
        'HeroTest',
        'FindJade',
        'MemoryScrolls',
    ],
    'Guild': [
        'KekkaiUtilize',
        'KekkaiActivation',
        'RealmRaid',
        'RyouToppa',
        'Dokan',
        'CollectiveMissions',
        'Hunt',
        'AbyssShadows',
        'GuildBanquet',
        'DemonRetreat',
        'GuildActivityMonitor',
    ],
    'Weekly Task': [
        'TrueOrochi',
        'RichMan',
        'Secret',
        'WeeklyTrifles',
        'MysteryShop',
        'Duel',
    ],
    'Activity Task': [
        'ActivityShikigami',
        'MetaDemon',
        'FrogBoss',
        'FloatParade',
        'Quiz',
        'KittyShop',
        'DyeTrials',
        'BudokaiTournament',
    ],
}
