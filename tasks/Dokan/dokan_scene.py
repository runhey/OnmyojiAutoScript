from enum import Enum

from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Dokan.assets import DokanAssets
from tasks.base_task import BaseTask


class DokanScene(Enum):
    # 未知界面
    RYOU_DOKAN_SCENE_UNKNOWN = 0
    # 进入道馆，集结中
    RYOU_DOKAN_SCENE_GATHERING = 1
    # 进入战场，等待用户点击开始战斗
    RYOU_DOKAN_SCENE_IN_FIELD = 2
    # 通常是失败了，并退出来到集结界面，可重新开始点击右下角挑战进入战斗
    RYOU_DOKAN_SCENE_START_CHALLENGE = 3
    # 失败次数超过上限，CD中
    RYOU_DOKAN_SCENE_CD = 4
    # 战斗进行中
    RYOU_DOKAN_SCENE_FIGHTING = 5
    # 馆主战第一阵容
    RYOU_DOKAN_SCENE_BATTLE_MASTER_FIRST = 6
    # 馆主战第二阵容
    RYOU_DOKAN_SCENE_BATTLE_MASTER_SECOND = 7
    # 加油进行中
    RYOU_DOKAN_SCENE_CHEERING = 8
    # 道馆是否投降投票
    RYOU_DOKAN_SCENE_ABANDON_VOTE = 9
    # 道馆投降后 投票再战还是保留赏金
    RYOU_DOKAN_SCENE_FAILED_VOTE = 10
    # 阴阳竂
    RYOU_DOKAN_RYOU = 11
    # 战斗结算，可能是打完小朋友了，也可能是失败了。
    RYOU_DOKAN_SCENE_BATTLE_OVER = 12
    # 等待BOSS战
    RYOU_DOKAN_SCENE_BOSS_WAITING = 13
    # 馆主战中,处于寮境
    RYOU_DOKAN_SCENE_MASTER_BATTLING = 14
    # 弹出窗口,道馆打完后,出现的排名
    RYOU_DOKAN_SCENE_TOPPA_RANK = 15
    # 道馆胜利后，出现的界面
    RYOU_DOKAN_SCENE_WIN = 16

    # 阴阳寮神社界面
    RYOU_DOKAN_SHENSHE = 17

    # 正在查找道馆,处于地图界面
    RYOU_DOKAN_SCENE_FINDING_DOKAN = 97
    # 已选择道馆,处于地图界面
    RYOU_DOKAN_SCENE_FOUND_DOKAN = 98
    # 道馆结束
    RYOU_DOKAN_SCENE_FINISHED = 99

    def __str__(self):
        return self.name.title()


class DokanSceneDetector(DokanAssets, BaseTask, GeneralBattleAssets):
    def get_current_scene(self, reuse_screenshot: bool = True) -> tuple[bool, DokanScene]:
        """
        检测当前场景
        @type reuse_screenshot: object
        @return 从道馆地图开始,及其后面的所有道馆界面,都返回True
                一般界面,如庭院,式神录等 都返回False
        """
        if not reuse_screenshot:
            self.screenshot()
        # logger.info(f"get_current_scene={reuse_screenshot}")
        # 场景检测：阴阳竂
        if self.appear(self.I_SCENE_RYOU, threshold=0.8):
            return False, DokanScene.RYOU_DOKAN_RYOU
        # 场景检测：神社
        if self.appear(self.I_SCENE_SHENSHE, threshold=0.8):
            return False, DokanScene.RYOU_DOKAN_SHENSHE
        # 状态, 判断是否正在查找道馆
        if self.appear(self.I_RYOU_DOKAN_FINDING_DOKAN):
            return True, DokanScene.RYOU_DOKAN_SCENE_FINDING_DOKAN
        # 状态, 判断是否已查找到道馆
        if self.appear(self.I_RYOU_DOKAN_FOUND_DOKAN):
            return True, DokanScene.RYOU_DOKAN_SCENE_FOUND_DOKAN

        # 状态：判断是否集结中
        if self.appear(self.I_RYOU_DOKAN_GATHERING, threshold=0.95):
            return True, DokanScene.RYOU_DOKAN_SCENE_GATHERING

        # 状态：是否在等待馆主战
        if self.appear(self.I_DOKAN_BOSS_WAITING):
            return True, DokanScene.RYOU_DOKAN_SCENE_BOSS_WAITING
        # 状态: 馆主战开始,且可以挑战
        if self.appear(self.I_RYOU_DOKAN_MASTER_BATTLE) and self.appear(self.I_RYOU_DOKAN_START_CHALLENGE):
            return True, DokanScene.RYOU_DOKAN_SCENE_MASTER_BATTLING

        # 馆主战斗中,未开始战斗状态
        if self.appear(self.I_RYOU_DOKAN_BATTLE_MASTER_FIRST) and \
                self.appear(self.I_PREPARE_HIGHLIGHT):
            return True, DokanScene.RYOU_DOKAN_SCENE_BATTLE_MASTER_FIRST
        if self.appear(self.I_RYOU_DOKAN_BATTLE_MASTER_SECOND) and \
                self.appear(self.I_PREPARE_HIGHLIGHT):
            return True, DokanScene.RYOU_DOKAN_SCENE_BATTLE_MASTER_SECOND

        # 状态：达到失败次数，CD中
        if self.appear(self.I_RYOU_DOKAN_CD):
            return True, DokanScene.RYOU_DOKAN_SCENE_CD

        # 状态：检查右下角有没有挑战？通常是失败了，并退出来到集结界面，可重新开始点击右下角挑战进入战斗
        if self.appear(self.I_RYOU_DOKAN_START_CHALLENGE):
            return True, DokanScene.RYOU_DOKAN_SCENE_START_CHALLENGE

        # 状态：进入战斗，待开始
        if self.appear(self.I_RYOU_DOKAN_IN_FIELD):
            return True, DokanScene.RYOU_DOKAN_SCENE_IN_FIELD
        # 状态：战斗结算，可能是打完小朋友了，也可能是失败了。
        if self.appear(self.I_RYOU_DOKAN_BATTLE_OVER) or self.appear(GeneralBattleAssets.I_WIN) \
                or self.appear(GeneralBattleAssets.I_FALSE):
            return True, DokanScene.RYOU_DOKAN_SCENE_BATTLE_OVER

        # # 状态：加油中，左下角有鼓
        # if self.appear_then_click(self.I_RYOU_DOKAN_CHEERING, threshold=0.8) or self.appear(
        #         self.I_RYOU_DOKAN_CHEERING_GRAY, threshold=0.8):
        #     return True, DokanScene.RYOU_DOKAN_SCENE_CHEERING
        # # 状态：战斗中，左上角的加油图标
        # if self.appear(self.I_RYOU_DOKAN_FIGHTING, threshold=0.8):
        #     return True, DokanScene.RYOU_DOKAN_SCENE_FIGHTING
        # if self.appear(self.I_RYOU_DOKAN_FAILED_VOTE_NO):
        #     return True, DokanScene.RYOU_DOKAN_SCENE_FAILED_VOTE_NO

        # 打完道馆后,弹出的排名界面
        if self.appear(self.I_RYOU_DOKAN_TOPPA_RANK):
            return True, DokanScene.RYOU_DOKAN_SCENE_TOPPA_RANK
        # 放弃突破投票,右侧俩 按钮:放弃/继续
        if self.appear(self.I_RYOU_DOKAN_ABANDONED_TOPPA_CONTINUE):
            return True, DokanScene.RYOU_DOKAN_SCENE_ABANDON_VOTE
        # 放弃后投票,右侧俩按钮: 保留赏金/再战道馆
        if self.appear(self.I_RYOU_DOKAN_FAILED_VOTE_KEEP_BOUNTY):
            return True, DokanScene.RYOU_DOKAN_SCENE_FAILED_VOTE
        # 状态：胜利
        if self.appear(self.I_RYOU_DOKAN_WIN) or self.appear(self.I_RYOU_DOKAN_SPOILS_OF_DOKAN):
            return True, DokanScene.RYOU_DOKAN_SCENE_WIN

        # 状态：道馆已经结束 在寮境,底部有 "今日可挑战机会" 字样
        if (self.appear(self.I_RYOU_DOKAN_CENTER_TOP) and
                (self.appear(self.I_RYOU_DOKAN_TODAY_ATTACK_COUNT)
                 or self.appear(self.I_RYOU_DOKAN_REMAIN_ATTACK_COUNT_DONE))):
            return True, DokanScene.RYOU_DOKAN_SCENE_FINISHED

        return False, DokanScene.RYOU_DOKAN_SCENE_UNKNOWN
