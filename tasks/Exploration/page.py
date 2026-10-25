from tasks.Exploration.assets import ExplorationAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import all_of, page_exploration
from tasks.GameUi.page_definition import Page


def inherit_transitions(source: Page, *targets: Page) -> None:
    """把 source 的全部出边复制给 targets（tab 页继承大地图出口，动作与 tab 状态无关）。

    跳过目标页自身（自环防护），若目标页已有到同一目的地的边则不重复添加。
    """
    for target in targets:
        for transition in source.transitions:
            if transition.destination == target:
                continue
            if any(item.destination == transition.destination for item in target.transitions):
                continue
            target.connect(
                transition.destination,
                transition.action,
                cost=transition.cost,
                on_enter_success=transition.on_enter_success,
                on_enter_failure=transition.on_enter_failure,
                on_leave_success=transition.on_leave_success,
                on_leave_failure=transition.on_leave_failure,
            )


# 探索大地图 · 主线 tab（"章"字锚点，优先级高于 page_exploration 的兜底识别）
page_mainline = Page(all_of(GameUiAssets.I_CHECK_EXPLORATION, ExplorationAssets.I_CHECK_MAIN_TITLE), priority=60)
# 探索大地图 · 玩法 tab（"御魂"标题锚点）
page_gameplay = Page(all_of(GameUiAssets.I_CHECK_EXPLORATION, ExplorationAssets.I_CHECK_PLAY_TITLE), priority=60)

# 大地图 tab 互切（固定坐标点击，幂等）
page_mainline.connect(page_gameplay, ExplorationAssets.C_CLICK_PALY_TITLE, key="page_mainline->page_gameplay")
page_gameplay.connect(page_mainline, ExplorationAssets.C_CLICK_MAIN_TITLE, key="page_gameplay->page_mainline")

# 大地图通用态 -> tab 桥接边：page_exploration 是入口桥 + 导航缓存页，
# tab 页必须从这里可达才能从庭院方向进入，也保证 tab 页能切回通用态。
page_exploration.connect(page_mainline, ExplorationAssets.C_CLICK_MAIN_TITLE, key="page_exploration->page_mainline")
page_exploration.connect(page_gameplay, ExplorationAssets.C_CLICK_PALY_TITLE, key="page_exploration->page_gameplay")

# tab 页继承大地图全部出口（回庭院、各区域入口等），此后 page_exploration 新增出边自动跟随
inherit_transitions(page_exploration, page_mainline, page_gameplay)
