# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import random

from tasks.base_task import BaseTask
from tasks.GeneralBattle.config_general_battle import GreenMarkType, GeneralBattleConfig
from tasks.GeneralBattle.assets import GeneralBattleAssets
from module.logger import logger



class GeneralBattle(BaseTask, GeneralBattleAssets):
    """
    使用这个通用的战斗必须要求这个任务的config有config_general_battle
    """

    def run_general_battle(self, config: dict=None) -> bool:
        """
        运行脚本
        :return:
        """
        if config is None:
            config = GeneralBattleConfig().dict()

        # if isinstance(config, GeneralBattle):
        #     logger.error(f"config is not GeneralBattle type, config: {config}")
        #     config = GeneralBattle().dict()

        # 如果没有锁定队伍。那么可以根据配置设定队伍
        if not config.lock_team_enable:
            logger.info("lock team is not enable")
            # 如果启动更换队伍
            if config.preset_enable:
                logger.info("preset is enable")
                # 点击预设按钮
                logger.info("click preset button")
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_PRESET, threshold=0.8):
                        continue
                    if self.appear(self.I_PRESET_ENSURE):
                        break
                # 选择预设组
                logger.info("select preset group")
                x, y = None, None
                match config.preset_group:
                    case 1: x, y = self.C_PRESET_GROUP_1.coord()
                    case 2: x, y = self.C_PRESET_GROUP_2.coord()
                    case 3: x, y = self.C_PRESET_GROUP_3.coord()
                    case 4: x, y = self.C_PRESET_GROUP_4.coord()
                    case 5: x, y = self.C_PRESET_GROUP_5.coord()
                    case 6: x, y = self.C_PRESET_GROUP_6.coord()
                    case 7: x, y = self.C_PRESET_GROUP_7.coord()
                    case _: x, y = self.C_PRESET_GROUP_1.coord()
                self.device.click(x, y)

                # 选择预设的队伍
                logger.info("select preset team")
                time.sleep(0.5)
                match config.preset_team:
                    case 1: x, y = self.C_PRESET_TEAM_1.coord()
                    case 2: x, y = self.C_PRESET_TEAM_2.coord()
                    case 3: x, y = self.C_PRESET_TEAM_3.coord()
                    case 4: x, y = self.C_PRESET_TEAM_4.coord()
                    case _: x, y = self.C_PRESET_TEAM_1.coord()
                self.device.click(x, y)

                # 点击预设确认
                logger.info("click preset ensure")
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_PRESET_ENSURE, threshold=0.8):
                        continue
                    if not self.appear(self.I_PRESET_ENSURE):
                        break

            # 点击buff按钮
            if config.buff_enable:
                logger.info("buff is enable")
                logger.info("click buff button")
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_BUFF, interval=1.5):
                        continue
                    if self.appear(self.I_BUFF_AWAKEN) or self.appear(self.I_BUFF_SOUL):
                        break


            # 点击准备按钮
            self.wait_until_appear(self.I_PREPARE_HIGHLIGHT)
            logger.info("click prepare button")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                    continue
                if not self.appear(self.I_PRESET):
                    break

            # 照顾一下某些模拟器慢的
            time.sleep(0.1)

        # 绿标
        if config.green_enable:
            logger.info("green is enable")
            x, y = None, None
            match config.green_mark:
                case GreenMarkType.GREEN_LEFT1: x, y = self.C_GREEN_LEFT_1.coord()
                case GreenMarkType.GREEN_LEFT2: x, y = self.C_GREEN_LEFT_2.coord()
                case GreenMarkType.GREEN_LEFT3: x, y = self.C_GREEN_LEFT_3.coord()
                case GreenMarkType.GREEN_LEFT4: x, y = self.C_GREEN_LEFT_4.coord()
                case GreenMarkType.GREEN_LEFT5: x, y = self.C_GREEN_LEFT_5.coord()
                case GreenMarkType.GREEN_MAIN: x, y = self.C_GREEN_MAIN.coord()

            # 判断有无坐标的偏移
            self.appear_then_click(self.I_LOCAL)
            time.sleep(0.3)
            # 点击绿标
            self.device.click(x, y)

        # 战斗过程 随机点击和滑动 防封
        logger.info("battle process")
        win: bool = False
        while 1:
            self.screenshot()
            # 如果出现赢 就点击
            if self.appear(self.I_WIN, threshold=0.6):
                logger.info("Battle result is win")
                win = True
                break

            # 如果出现失败 就点击，返回False
            if self.appear(self.I_FALSE, threshold=0.6):
                logger.info("Battle result is false")
                win = False
                break

            # 如果领奖励
            if self.appear(self.I_REWARD, threshold=0.6):
                win = True
                break
            # 如果开启战斗过程随机滑动
            if config.random_click_swipt_enable:
                time.sleep(0.4)  # 这样的好像不对
                if 0 <= random.randint(0, 500) <= 3:  # 百分之4的概率
                    rand_type = random.randint(0, 2)
                    match rand_type:
                        case 0:
                            self.click(self.C_RANDOM_CLICK, interval=20)
                        case 1:
                            self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
                        case 2:
                            self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)

        # 再次确认战斗结果
        logger.info("reconfirm the results of the battle")
        while 1:
            self.screenshot()
            if win:
                # 点击赢了
                if self.appear_then_click(self.I_WIN):
                    continue
                if not self.appear(self.I_WIN):
                    break
            else:
                # 如果失败且 点击失败后
                if self.appear_then_click(self.I_FALSE, threshold=0.6):
                    continue
                if not self.appear(self.I_FALSE, threshold=0.6):
                    return False
        # 最后保证能点击 获得奖励
        self.wait_until_appear(self.I_REWARD)
        logger.info("get reward")
        while 1:
            self.screenshot()
            # 如果出现领奖励
            if self.appear_then_click(self.I_REWARD, interval=1.5):
                continue
            if not self.appear(self.I_REWARD):
                break

        if win:
            return True
        else:
            return False

