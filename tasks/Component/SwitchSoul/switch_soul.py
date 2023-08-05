# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from module.base.timer import Timer
from tasks.base_task import BaseTask
from tasks.Component.GeneralInvite.assets import GeneralInviteAssets
from tasks.Component.GeneralInvite.config_invite import InviteConfig, InviteNumber, FindMode
from tasks.Component.SwitchSoul.assets import SwitchSoulAssets
from module.logger import logger


def switch_parser(switch_str: str) -> tuple:
    switch_list = switch_str.split(',')
    if len(switch_list) != 2:
        raise ValueError('Switch_str must be 2 length')
    return int(switch_list[0]), int(switch_list[1])

class SwitchSoul(BaseTask, SwitchSoulAssets):

    def run_switch_soul(self, target: tuple or list[tuple]):
        """
        保证在式神录的界面
        :return:
        """
        if isinstance(target, str):
            try:
                target = switch_parser(target)
            except ValueError:
                logger.error('Switch soul config error')
                return
        self.click_preset()
        self.switch_souls(target)

    def click_preset(self) -> None:
        """
        点击预设
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_SOU_SWITCH_1):
                break
            if self.appear(self.I_SOU_SWITCH_2):
                break
            if self.appear(self.I_SOU_SWITCH_3):
                break
            if self.appear(self.I_SOU_SWITCH_4):
                break
            if self.appear(self.I_SOU_TEAM_PRESENT):
                break
            if self.appear_then_click(self.I_SOUL_PRESET, interval=1):
                continue
        logger.info('Click preset in switch soul')

    def switch_soul_one(self, group: int, team: int) -> None:
        """
        设置一个队伍的预设御魂
        :param group: 只能是[1-7]
        :param team: 只能是[1-4]
        :return:
        """

        def get_group_assets(group: int) -> tuple:
            match = {
                1: tuple([self.C_SOU_GROUP_1, self.I_SOU_CHECK_GROUP_1]),
                2: tuple([self.C_SOU_GROUP_2, self.I_SOU_CHECK_GROUP_2]),
                3: tuple([self.C_SOU_GROUP_3, self.I_SOU_CHECK_GROUP_3]),
                4: tuple([self.C_SOU_GROUP_4, self.I_SOU_CHECK_GROUP_4]),
                5: tuple([self.C_SOU_GROUP_5, self.I_SOU_CHECK_GROUP_5]),
                6: tuple([self.C_SOU_GROUP_6, self.I_SOU_CHECK_GROUP_6]),
                7: tuple([self.C_SOU_GROUP_7, self.I_SOU_CHECK_GROUP_7]),
            }
            return match[group]

        def get_team_asset(team: int):
            match = {
                1: self.I_SOU_SWITCH_1,
                2: self.I_SOU_SWITCH_2,
                3: self.I_SOU_SWITCH_3,
                4: self.I_SOU_SWITCH_4,
            }
            return match[team]

        if group < 1 or group > 7:
            raise ValueError('Switch soul_one group must be in [1-7]')
        if team < 1 or team > 4:
            raise ValueError('Switch soul_one team must be in [1-4]')
        # 这一步是选择组
        target_click, target_check = get_group_assets(group)
        # while 1:
        #     self.screenshot()
        #     if self.click(target_click, interval=1):
        #         continue
        #     if self.appear(target_check):
        #         break
        # 2023.8.5 修改为无反馈的点击切换
        for i in range(2):
            self.click(target_click)
            sleep(0.5)
        # 点击队伍
        target_team = get_team_asset(team)
        for i in range(3):
            sleep(0.8)
            self.screenshot()
            if self.appear_then_click(self.I_SOU_SWITCH_SURE, interval=1):
                continue
            if not self.appear_then_click(target_team, interval=1):
                logger.warning(f'Click team {team} failed in group {group}')
        logger.info(f'Switch soul_one group {group} team {team}')

    def switch_souls(self, target: tuple or list[tuple]) -> None:
        """
        切换御魂
        :param target: [(1, 1), (2, 2), (3, 3), (4, 4)]  或者是单独的一个元组(4, 4) 第一个是组, 第二个是队伍
        :return:
        """
        if isinstance(target, tuple):
            target = [target]
        for group, team in target:
            group = int(group)
            team = int(team)
            self.switch_soul_one(group, team)

    def exit_shikigami_records(self) -> None:
        """
        退出式神录的界面
        :return:
        """
        while 1:
            self.screenshot()
            if not self.appear(self.I_SOU_CHECK_IN):
                break
            if self.appear_then_click(self.I_RECORD_SOUL_BACK, interval=1):
                continue
        logger.info('Exit shikigami records')

    def run_switch_soul_by_name(self, groupName, teamName):
        """
        保证在式神录的界面
        :return:
        """
        if isinstance(groupName, str) and isinstance(teamName, str):
            self.click_preset()
            self.switch_soul_by_name(groupName, teamName)

    def switch_soul_by_name(self, groupName, teamName):
        """
        保证在式神录的界面
        :return:
        """
        # 滑动至分组最上层
        while 1:
            self.screenshot()
            compare1 = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            text1 = str([result.ocr_text for result in compare1])
            # 向上滑动
            self.swipe(self.S_SS_GROUP_SWIPE_UP, 6)
            self.screenshot()
            compare2 = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            text2 = str([result.ocr_text for result in compare2])
            # 相等时 滑动到最上层
            if text1 == text2:
                break

        # 判断有无目标分组
        while 1:
            self.screenshot()
            # 获取当前分组名
            results = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            text1 = [result.ocr_text for result in results]
            # 判断当前分组有无目标分组
            result = set(text1).intersection({groupName})
            # 有则跳出检测
            if result and len(result) > 0:
                break
            self.swipe(self.S_SS_GROUP_SWIPE_DOWN)

        # 选中分组
        while 1:
            self.screenshot()
            self.O_SS_GROUP_NAME.keyword = groupName
            if self.ocr_appear_click(self.O_SS_GROUP_NAME):
                break

        # 滑动至阵容最上层
        while 1:
            self.screenshot()
            compare1 = self.O_SS_TEAM_NAME.detect_and_ocr(self.device.image)
            text1 = str([result.ocr_text for result in compare1])
            # 向上滑动
            self.swipe(self.S_SS_TEAM_SWIPE_DOWN, 6)
            self.screenshot()
            compare2 = self.O_SS_TEAM_NAME.detect_and_ocr(self.device.image)
            text2 = str([result.ocr_text for result in compare2])
            # 相等时 说明滑动到最上层
            if text1 == text2:
                break
        # 判断当前分组有无目标阵容
        while 1:
            self.screenshot()
            # 获取当前阵容名
            results = self.O_SS_TEAM_NAME.detect_and_ocr(self.device.image)
            text1 = [result.ocr_text for result in results]
            # 判断当前分组有无目标阵容
            result = set(text1).intersection({teamName})
            # 有则跳出检测
            if result and len(result) > 0:
                break
            self.swipe(self.S_SS_TEAM_SWIPE_UP)

        # 选中分组
        while 1:
            self.screenshot()
            self.O_SS_TEAM_NAME.keyword = teamName
            if self.ocr_appear_click(self.O_SS_TEAM_NAME):
                break
        # 切换御魂
        for i in range(5):
            sleep(0.8)
            self.screenshot()
            if self.appear_then_click(self.I_SOU_CLICK_PRESENT, interval=1):
                continue
            if self.appear_then_click(self.I_SOU_SWITCH_SURE, interval=1):
                break
        logger.info(f'Switch soul_one group {groupName} team {teamName}')

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    s = SwitchSoul(c, d)

    s.click_preset()
    # s.switch_soul_one(2, 1)
    s.switch_soul_by_name('契灵', '茨球')
