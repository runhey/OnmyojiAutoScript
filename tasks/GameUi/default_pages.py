from __future__ import annotations

from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.Component.GeneralInvite.assets import GeneralInviteAssets
from tasks.Component.SwitchAccount.assets import SwitchAccountAssets
from tasks.Exploration.assets import ExplorationAssets
from tasks.GameUi.action import conditional_action, sequence
from tasks.Pets.assets import PetsAssets
from typing import Union

"""GameUi 全局页面定义。"""

import random

from module.atom.click import RuleClick
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.matcher import any_of, all_of
from tasks.GameUi.page_definition import Page
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.Restart.assets import RestartAssets
from tasks.RyouToppa.assets import RyouToppaAssets


def random_click(
    low: int | None = None,
    high: int | None = None,
    ltrb: tuple = (True, False, True, False),
) -> Union[RuleClick | list[RuleClick]]:
    """从常用结算点击区域中随机选择安全点击点。

    Args:
        low: 当需要返回点击序列时，序列长度的最小值。
        high: 当需要返回点击序列时，序列长度的最大值。
        ltrb: 允许参与随机的区域开关，依次对应左、上、右、下区域。

    Returns:
        单个 `RuleClick`，或一个由多个 `RuleClick` 组成的列表。
    """

    click_area_list = [GeneralBattleAssets.C_RANDOM_LEFT, GeneralBattleAssets.C_RANDOM_TOP,
                       GeneralBattleAssets.C_RANDOM_RIGHT, GeneralBattleAssets.C_RANDOM_BOTTOM]
    click = random.choice([item for item, enabled in zip(click_area_list, ltrb) if enabled])
    click.name = "SAFE_RANDOM_CLICK"
    if low is None or high is None:
        return click
    return [click for _ in range(random.randint(low, high))]


def handle_login_page(task) -> bool:
    from tasks.Restart.login import LoginHandler
    return LoginHandler(config=task.config, device=task.device).app_handle_login()


# 登录页。
page_login = Page(SwitchAccountAssets.I_CHECK_LOGIN_FORM, category="global")
page_login.add_enter_success_hooks(handle_login_page)

# 庭院主页(此处通过提高阈值来处理部分探索章节会识别成原始庭院的问题, 后续有其他更好方法需改善)
page_main = Page(GameUiAssets.I_CHECK_MAIN, category="global")
page_main.add_enter_success_hooks(
    GameUiAssets.I_AD_CLOSE_RED, GlobalGameAssets.I_UI_BACK_RED, RestartAssets.I_CANCEL_BATTLE,
    conditional_action(RestartAssets.I_LOGIN_COURTYARD, RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA),
)

# 庭院区域页面。
page_shikigami_records = Page(GameUiAssets.I_CHECK_RECORDS, category="global")
page_shikigami_records.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                                  action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_shikigami_records.add_enter_success_hooks(GlobalGameAssets.I_UI_CANCEL_SAMLL)
page_shikigami_records.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_shikigami_records->page_main")
page_main.connect(page_shikigami_records, GameUiAssets.I_MAIN_GOTO_SHIKIGAMI_RECORDS, key="page_main->page_shikigami_records")

page_onmyodo = Page(GameUiAssets.I_CHECK_ONMYODO, category="global")
page_onmyodo.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                        action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_onmyodo.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_onmyodo->page_main")
page_main.connect(page_onmyodo, GameUiAssets.I_MAIN_GOTO_ONMYODO, key="page_main->page_onmyodo")

page_friends = Page(GameUiAssets.I_CHECK_FRIENDS, category="global")
page_friends.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                        action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_friends.connect(page_main, GlobalGameAssets.I_UI_BACK_RED, key="page_friends->page_main")
page_friends.add_leave_failure_hooks(GlobalGameAssets.I_UI_BACK_RED)
page_main.connect(page_friends, GameUiAssets.I_MAIN_GOTO_FRIENDS, key="page_main->page_friends")

page_daily = Page(GameUiAssets.I_CHECK_DAILY, category="global")
page_daily.add_enter_failure_hooks(
    conditional_action(condition=GameUiAssets.I_CHECK_MAIN, action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA),
    conditional_action(condition=lambda task: not task.appear(GameUiAssets.I_CHECK_MAIN),
                       action=lambda task: task.ui_click(click=random_click(ltrb=(False, False, False, True)),
                                                         stop=GlobalGameAssets.I_UI_BACK_YELLOW)))
page_daily.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_daily->page_main")
page_main.connect(page_daily, GameUiAssets.I_MAIN_GOTO_DAILY, key="page_main->page_daily")

page_mall = Page(GameUiAssets.I_CHECK_MALL, category="global")
page_mall.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                     action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_mall.add_enter_success_hooks(GameUiAssets.I_AD_CLOSE_RED, GlobalGameAssets.I_UI_BACK_RED, GlobalGameAssets.I_UI_CANCEL_SAMLL)
page_mall.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_mall->page_main")

page_mall_recommend = Page(GameUiAssets.I_CHECK_MALL_RECOMMEND, category="global")
page_mall_recommend.add_enter_success_hooks(GameUiAssets.I_AD_CLOSE_RED, GlobalGameAssets.I_UI_BACK_RED,
                                            GlobalGameAssets.I_UI_CANCEL_SAMLL)
page_mall_recommend.connect(page_mall, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_mall_recommend->page_mall")
page_main.connect(page_mall_recommend, GameUiAssets.I_MAIN_GOTO_MALL, key="page_main->page_mall_recommend")

page_guild = Page(GameUiAssets.I_CHECK_GUILD, category="global")
page_guild.add_enter_success_hooks(KekkaiUtilizeAssets.I_PLANT_TREE_CLOSE)
page_guild.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                      action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_guild.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_guild->page_main")
page_main.connect(page_guild, GameUiAssets.I_MAIN_GOTO_GUILD, key="page_main->page_guild")

page_shirin = Page(GameUiAssets.I_CHECK_SHRIN, category="global")
page_guild.connect(page_shirin, GameUiAssets.I_GUILD_TO_SHRIN, key="page_guild->page_shirin")
page_shirin.connect(page_guild, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_shirin->page_guild")

page_team = Page(GameUiAssets.I_CHECK_TEAM, category="global")
page_team.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                     action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_team.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_team->page_main")
page_main.connect(page_team, GameUiAssets.I_MAIN_GOTO_TEAM, key="page_main->page_team")

page_collection = Page(GameUiAssets.I_CHECK_COLLECTION, category="global")
page_collection.add_enter_success_hooks(GlobalGameAssets.I_UI_CANCEL_SAMLL)
page_collection.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                           action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_collection.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_collection->page_main")
page_main.connect(page_collection, GameUiAssets.I_MAIN_GOTO_COLLECTION, key="page_main->page_collection")

page_travel = Page(GameUiAssets.I_CHECK_TRAVEL, category="global")
page_travel.add_enter_failure_hooks(conditional_action(condition=GameUiAssets.I_CHECK_MAIN,
                                                       action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_travel.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_travel->page_main")
page_main.connect(page_travel, GameUiAssets.I_MAIN_GOTO_TRAVEL, key="page_main->page_travel")

page_pet = Page(any_of(PetsAssets.I_PET_CLAW, PetsAssets.I_PET_FEAST), category="global")
page_pet.connect(page_main, GlobalGameAssets.I_UI_BACK_CIRCLE, key="page_pet->page_main")
page_main.connect(page_pet, PetsAssets.I_PET_HOUSE, key="page_main->page_pet")
page_pet.add_enter_success_hooks(conditional_action(condition=lambda task: not task.appear(PetsAssets.I_PET_FEAST),
                                                    action=PetsAssets.I_PET_CLAW))

# 活动列表页。
page_act_list = Page(GameUiAssets.I_CHECK_ACT_LIST, category="global", priority=25)
page_act_list.add_enter_success_hooks(GameUiAssets.I_PAPER_DOLL_CLOSE)
page_main.connect(page_act_list, GameUiAssets.I_ACT_LIST_EXPAND, key="page_main->page_act_list")
page_act_list.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_list->page_main")

# 召唤页。
page_summon = Page(GameUiAssets.I_CHECK_SUMMON, category="global")
page_summon.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_summon->page_main")
page_main.connect(page_summon, GameUiAssets.I_MAIN_GOTO_SUMMON, key="page_main->page_summon")

# 町中主页。
page_town = Page(GameUiAssets.I_CHECK_TOWN, category="global")
page_town.connect(page_main, GameUiAssets.I_TOWN_GOTO_MAIN, key="page_town->page_main")
page_main.connect(page_town, GameUiAssets.I_MAIN_GOTO_TOWN, key="page_main->page_town")

# 町中区域页面。
page_entertainment = Page(GameUiAssets.I_CHECK_ENTERTAINMENT, category="global")
page_town.connect(
    page_entertainment,
    GameUiAssets.I_TOWN_GOTO_ENTERTAINMENT,
    key="page_town->page_entertainment",
)
page_entertainment.connect(
    page_town,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_entertainment->page_town",
)

page_duel = Page(GameUiAssets.I_CHECK_DUEL, category="global")
page_duel.connect(page_town, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_duel->page_town")
page_town.connect(page_duel, GameUiAssets.I_TOWN_GOTO_DUEL, key="page_town->page_duel")

page_demon_encounter = Page(GameUiAssets.I_CHECK_DEMON_ENCOUNTER_2, category="global")
page_demon_encounter.connect(page_town, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_demon_encounter->page_town")
page_town.connect(page_demon_encounter, GameUiAssets.I_TOWN_GOTO_DEMON_ENCOUNTER, key="page_town->page_demon_encounter")

# 现世逢魔页面。
page_demon_encounter_realworld = Page(GameUiAssets.I_CHECK_DEMON_ENCOUNTER_REALWORLD, category="global")
page_demon_encounter_realworld.connect(page_demon_encounter, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_demon_encounter_realworld->page_demon_encounter")
page_demon_encounter.connect(page_demon_encounter_realworld, GameUiAssets.I_DEMON_ENCOUNTER_REALWORLD_GOTO, key="page_demon_encounter->page_demon_encounter_realworld")

page_hunt = Page(GameUiAssets.I_CHECK_HUNT, category="global")
page_hunt.connect(page_town, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_hunt->page_town")
page_town.connect(page_hunt, GameUiAssets.I_TOWN_GOTO_HUNT, key="page_town->page_hunt")

page_hunt_kirin = Page(GameUiAssets.I_CHECK_HUNT_KIRIN, category="global")
page_hunt_kirin.connect(page_town, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_hunt_kirin->page_town")
page_town.connect(page_hunt_kirin, GameUiAssets.I_TOWN_GOTO_HUNT, key="page_town->page_hunt_kirin")

page_draft_duel = Page(GameUiAssets.I_CHECK_DRAFT_DUEL, category="global")
page_draft_duel.connect(page_town, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_draft_duel->page_town")
page_town.connect(page_draft_duel, GameUiAssets.I_TOWN_GOTO_DRAFT_DUEL, key="page_town->page_draft_duel")

page_hyakkiyakou = Page(GameUiAssets.I_CHECK_KYAKKIYAKOU, category="global")
page_hyakkiyakou.connect(page_town, GlobalGameAssets.I_UI_BACK_RED, key="page_hyakkiyakou->page_town")
page_town.connect(page_hyakkiyakou, GameUiAssets.I_TOWN_GOTO_HYAKKIYAKOU, key="page_town->page_hyakkiyakou")


# 探索主页。
page_exploration = Page(GameUiAssets.I_CHECK_EXPLORATION, category="global")
page_exploration.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_exploration->page_main")
page_exploration.add_enter_failure_hooks(ExplorationAssets.I_E_OPEN_FOLDER)
page_main.connect(page_exploration, GameUiAssets.I_MAIN_GOTO_EXPLORATION, key="page_main->page_exploration")

# 探索区域页面。
page_awake_zones = Page(GameUiAssets.I_CHECK_AWAKE, category="global")
page_awake_zones.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_awake_zones->page_exploration")
page_exploration.connect(page_awake_zones, GameUiAssets.I_EXPLORATION_GOTO_AWAKE_ZONE, key="page_exploration->page_awake_zones")

page_soul_zones = Page(GameUiAssets.I_CHECK_SOUL_ZONES, category="global")
page_soul_zones.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_soul_zones->page_exploration")
page_exploration.connect(page_soul_zones, GameUiAssets.I_EXPLORATION_GOTO_SOUL_ZONE, key="page_exploration->page_soul_zones")

page_realm_raid = Page(GameUiAssets.I_CHECK_REALM_RAID, category="global")
page_realm_raid.connect(page_exploration, GlobalGameAssets.I_UI_BACK_RED, key="page_realm_raid->page_exploration")
page_realm_raid.connect(page_shikigami_records, GameUiAssets.I_REALM_RAID_GOTO_SHIKIGAMI_RECORDS, key="page_realm_raid->page_shikigami_records")
page_exploration.connect(page_realm_raid, GameUiAssets.I_EXPLORATION_GOTO_REALM_RAID, key="page_exploration->page_realm_raid")

page_kekkai_toppa = Page(GameUiAssets.I_KEKKAI_TOPPA, category="global")
page_kekkai_toppa.connect(page_exploration, GlobalGameAssets.I_UI_BACK_RED, key="page_kekkai_toppa->page_exploration")
page_kekkai_toppa.connect(page_shikigami_records, GameUiAssets.I_REALM_RAID_GOTO_SHIKIGAMI_RECORDS, key="page_kekkai_toppa->page_shikigami_records")
page_realm_raid.connect(page_kekkai_toppa, RyouToppaAssets.I_RYOU_TOPPA, key="page_realm_raid->page_kekkai_toppa")
page_kekkai_toppa.connect(page_realm_raid, GameUiAssets.I_RYOUTOPPA_GOTO_REALMRAID, key="page_kekkai_toppa->page_realm_raid")

page_goryou_realm = Page(GameUiAssets.I_CHECK_GORYOU, category="global")
page_goryou_realm.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_goryou_realm->page_exploration")
page_exploration.connect(page_goryou_realm, GameUiAssets.I_EXPLORATION_GOTO_GORYOU_REALM, key="page_exploration->page_goryou_realm")

page_delegation = Page(GameUiAssets.I_CHECK_DELEGATION, category="global")
page_delegation.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_delegation->page_exploration")
page_exploration.connect(page_delegation, GameUiAssets.I_EXPLORATION_GOTO_DELEGATION, key="page_exploration->page_delegation")

page_secret_zones = Page(GameUiAssets.I_CHECK_SECRET_ZONES, category="global")
page_secret_zones.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_secret_zones->page_exploration")
page_exploration.connect(page_secret_zones, GameUiAssets.I_EXPLORATION_GOTO_SECRET_ZONES, key="page_exploration->page_secret_zones")

page_area_boss = Page(GameUiAssets.I_CHECK_AREA_BOSS, category="global")
page_area_boss.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_area_boss->page_exploration")
page_exploration.connect(page_area_boss, GameUiAssets.I_EXPLORATION_GOTO_AREA_BOSS, key="page_exploration->page_area_boss")

page_heian_kitan = Page(GameUiAssets.I_CHECK_HEIAN_KITAN, category="global")
page_heian_kitan.connect(page_exploration, GameUiAssets.I_CHECK_HEIAN_KITAN, key="page_heian_kitan->page_exploration")
page_exploration.connect(page_heian_kitan, GameUiAssets.I_EXPLORATION_GOTO_HEIAN_KITAN, key="page_exploration->page_heian_kitan")


def exploration_to_six_gates(task) -> bool:
    """探索前往六道之门, 处理不同入口情况"""
    if task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_MOON_SEA) or \
            task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_INCENSE_REALM) or \
            task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_SEASONRIFT_FOREST) or \
            task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_PURE_BUDDHA_REALM) or \
            task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_MANTRA_TOWER) or \
            task.appear_then_click(GameUiAssets.I_EXPLORATION_TO_PEACOCK_KINGDOM):
        return True
    return False

page_six_gates = Page(any_of(GameUiAssets.I_CHECK_MOON_SEA, GameUiAssets.I_CHECK_INCENSE_REALM,
                             GameUiAssets.I_CHECK_SEASONRIFT_FOREST, GameUiAssets.I_CHECK_PURE_BUDDHA_REALM,
                             GameUiAssets.I_CHECK_MANTRA_TOWER, GameUiAssets.I_CHECK_PEACOCK_KINGDOM),
                      category="global", priority=25)
page_six_gates.connect(page_exploration, GlobalGameAssets.I_UI_BACK_BLUE, key="page_six_gates->page_exploration")
page_exploration.connect(page_six_gates, action=exploration_to_six_gates, key="page_exploration->page_six_gates")

page_bondling_fairyland = Page(GameUiAssets.I_CHECK_BONDLING_FAIRYLAND, category="global")
page_bondling_fairyland.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_bondling_fairyland->page_exploration")
page_exploration.connect(
    page_bondling_fairyland,
    GameUiAssets.I_EXPLORATION_GOTO_BONDLING_FAIRYLAND,
    key="page_exploration->page_bondling_fairyland",
)

page_hero_test = Page(GameUiAssets.I_CHECK_HERO_TEST, category="global")
page_hero_test.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_hero_test->page_exploration")
page_exploration.connect(page_hero_test, GameUiAssets.I_EXPLORATION_GOTO_HERO_TEST, key="page_exploration->page_hero_test")


def handle_battle_page(task) -> bool:
    """处理进入战斗中页面后的默认 hook。

    Args:
        task: 当前触发页面 hook 的任务实例。

    Returns:
        bool: 通用战斗执行结果。
    """
    from tasks.Component.GeneralBattle.general_battle import run_task_or_default_general_battle
    return run_task_or_default_general_battle(task)


# 战斗相关页面
page_battle_prepare = Page(
    any_of(
        GeneralBattleAssets.I_BUFF,
        GeneralBattleAssets.I_PREPARE_HIGHLIGHT,
        GeneralBattleAssets.I_PREPARE_DARK,
        GeneralBattleAssets.I_PRESET,
        GeneralBattleAssets.I_PRESET_WIT_NUMBER,
    ),
    category="global",
    priority=25
)
page_battle_prepare.add_enter_success_hooks(handle_battle_page)

page_battle = Page(GeneralBattleAssets.I_BATTLE_INFO, category="global", priority=25)
page_battle.add_enter_success_hooks(handle_battle_page)

page_battle_result = Page(
    any_of(
        GeneralBattleAssets.I_WIN,
        GeneralBattleAssets.I_DE_WIN,
        GeneralBattleAssets.I_FALSE,
        GeneralBattleAssets.I_BATTLE_STATE_INFO
    ),
    category="global",
    priority=25
)
page_battle_result.add_enter_success_hooks(lambda _task: random_click())

page_reward = Page(
    any_of(
        GeneralBattleAssets.I_REWARD,
        GeneralBattleAssets.I_GB_SKIN_CONFIRM,
        GeneralBattleAssets.I_OVER_GHOST,
        GeneralBattleAssets.I_REWARD_STATISTICS,
        GeneralBattleAssets.I_REWARD_GOLD,
        GeneralBattleAssets.I_REWARD_EXP_SOUL_4,
        GeneralBattleAssets.I_REWARD_GOLD_SNAKE_SKIN,
        GeneralBattleAssets.I_REWARD_PURPLE_SNAKE_SKIN,
        GeneralBattleAssets.I_REWARD_SOUL_5,
        GeneralBattleAssets.I_REWARD_SOUL_6,
        GlobalGameAssets.I_UI_REWARD,
    ),
    category="global",
    priority=25
)

def handle_battle_reward_page(task) -> bool:
    """处理战斗奖励页面(页面跳转才会使用该逻辑)

    Args:
        task: 当前触发页面 hook 的任务实例。

    Returns:
        bool: 执行结果
    """
    if task.appear_then_click(GeneralBattleAssets.I_OVER_GHOST, interval=0.8):
        return True
    return task.click(random_click(), interval=0.8)

page_reward.add_enter_success_hooks(handle_battle_reward_page)

page_battle_team_exit = Page(GeneralBattleAssets.I_GB_CHECK_TEAM_EXIT, priority=75)
page_battle_team = Page(any_of(GeneralInviteAssets.I_GI_EMOJI_1, GeneralInviteAssets.I_GI_EMOJI_2,
                               GeneralInviteAssets.I_FIRE),
                        category="global", priority=25)
page_battle_team_exit.connect(page_battle_team, GlobalGameAssets.I_UI_CANCEL, key="page_battle_team_exit->page_battle_team")
page_battle_team.connect(page_battle_team_exit, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_battle_team->page_battle_team_exit")
