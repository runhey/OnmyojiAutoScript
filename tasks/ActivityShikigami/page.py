from tasks.ActivityShikigami.assets import ActivityShikigamiAssets as asa
from tasks.GameUi.page import Page, page_main
from tasks.GlobalGame.assets import GlobalGameAssets as gga
from tasks.GameUi.assets import GameUiAssets as G
from tasks.Component.RightActivity.assets import RightActivityAssets as RAA
from tasks.base_task import BaseTask as BT

# ************************************* 活动部分 *****************************************#

# 活动列表页 act_list
# page_act_list = Page(G.I_CHECK_ACT_LIST)
# page_act_list.additional = [G.I_PAPER_DOLL_CLOSE]
# page_act_list.link(button=G.I_BACK_ACT_LIST, destination=page_main)
# page_main.link(button=G.I_ACT_LIST_EXPAND, destination=page_act_list)
# # 活动列表页爬塔活动
# page_act_list_climb_act = Page(asa.I_CHECK_ACT_LIST_CLIMB_ACT)
# page_act_list.link(button=G.L_ACT_LIST_OCR, destination=page_act_list_climb_act)
# page_act_list_climb_act.link(button=G.I_BACK_ACT_LIST, destination=page_main)

# 爬塔活动主要界面
page_climb_act = Page(asa.I_TO_BATTLE_MAIN)
page_climb_act.additional = [gga.I_UI_REWARD, asa.I_SKIP_BUTTON, asa.I_RED_EXIT]
page_climb_act.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=[asa.I_SHI, RAA.I_TOGGLE_BUTTON], destination=page_climb_act)

# page_act_list_climb_act.link(button=G.I_ACT_LIST_GOTO_ACT, destination=page_climb_act)
# # 爬塔活动副界面
# page_climb_act_2 = Page(asa.I_CHECK_BATTLE_2)
# page_climb_act_2.additional = [asa.I_ACT_MAP_SWITCH, asa.I_PASS_ACT_LOCAT, asa.I_SKIP_BUTTON, asa.I_RED_EXIT,
#                                asa.I_RED_EXIT_2]
# page_climb_act_2.link(button=G.I_BACK_BATTLE, destination=page_climb_act)
# page_climb_act.link(button=asa.I_BATTLE, destination=page_climb_act_2)
# # 门票爬塔活动界面
# page_climb_act_pass = Page(asa.I_AP_ACTIVITY)
# page_climb_act_pass.additional = [asa.I_SKIP_BUTTON, gga.I_UI_REWARD, asa.I_RED_EXIT, ]
# page_climb_act_pass.link(button=G.I_BACK_Y, destination=page_climb_act_2)
# page_climb_act_2.link(button=asa.I_ENTRY_ACTIVITY, destination=page_climb_act_pass)
# # 体力爬塔活动界面
# page_climb_act_ap = Page(asa.I_AP)
# page_climb_act_ap.additional = [asa.O_ENTRY_ACTIVITY, asa.I_SKIP_BUTTON, asa.I_TOGGLE_BUTTON, gga.I_UI_REWARD,
#                                 asa.I_RED_EXIT]
# page_climb_act_ap.link(button=G.I_BACK_Y, destination=page_climb_act_2)
# page_climb_act_2.link(button=asa.O_ENTRY_ACTIVITY, destination=page_climb_act_ap)
# # 体力, 门票互相跳转
# # page_climb_act_ap.link(button=asa.I_SWITCH, destination=page_climb_act_pass)
# # page_climb_act_pass.link(button=asa.I_SWITCH, destination=page_climb_act_ap)
# # 100体爬塔活动界面
# page_climb_act_ap100 = Page(asa.I_CHECK_AP100)
# page_climb_act_2.link(button=asa.O_ENTER_AP100, destination=page_climb_act_ap100)
# page_climb_act_ap100.link(button=G.I_BACK_Y, destination=page_climb_act_2)
# # 爬塔活动boss战界面
# page_climb_act_boss = Page(asa.I_CHECK_BOSS)
# page_climb_act_boss.additional = [BT.I_UI_BACK_RED, asa.I_SKIP_BUTTON]
# page_climb_act_boss.link(button=G.I_BACK_Y, destination=page_climb_act)
# page_climb_act.link(button=asa.I_BOSS, destination=page_climb_act_boss)
# # 爬塔活动加成界面
# page_climb_act_buff = Page(asa.I_CHECK_BUFF)
# page_climb_act_buff.additional = [BT.I_UI_BACK_RED, asa.I_SKIP_BUTTON]
# page_climb_act_buff.link(button=G.I_BACK_Y, destination=page_climb_act)
# page_climb_act.link(button=asa.I_BUFF_CHANGE_BUTTON, destination=page_climb_act_buff)
#
# page_reward.link(button=random_click(), destination=page_climb_act_pass)
# page_reward.link(button=random_click(), destination=page_climb_act_ap)
# page_reward.link(button=random_click(), destination=page_climb_act_boss)
#
# page_failed.link(button=random_click(), destination=page_climb_act_pass)
# page_failed.link(button=random_click(), destination=page_climb_act_ap)
# page_failed.link(button=random_click(), destination=page_climb_act_boss)
