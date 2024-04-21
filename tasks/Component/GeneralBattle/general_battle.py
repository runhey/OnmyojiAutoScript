# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import random

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType, GeneralBattleConfig
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBuff.config_buff import BuffClass
from tasks.Component.GeneralBuff.general_buff import GeneralBuff

from module.logger import logger


class GeneralBattle(GeneralBuff, GeneralBattleAssets):
    """
    使用这个通用的战斗必须要求这个任务的config有config_general_battle
    """

    def run_general_battle(self, config: GeneralBattleConfig = None, buff: BuffClass or list[BuffClass] = None) -> bool:
        """
        运行脚本
        :return:
        """
        # 本人选择的策略是只要进来了就算一次，不管是不是打完了
        logger.hr("General battle start", 2)
        self.current_count += 1
        logger.info(f"Current count: {self.current_count}")
        if config is None:
            config = GeneralBattleConfig()

        # 如果没有锁定队伍。那么可以根据配置设定队伍
        if not config.lock_team_enable:
            logger.info("Lock team is not enable")
            # 如果更换队伍
            if self.current_count == 1:
                self.switch_preset_team(config.preset_enable, config.preset_group, config.preset_team)

            # 打开buff
            self.check_buff(buff)

            # 点击准备按钮
            self.wait_until_appear(self.I_PREPARE_HIGHLIGHT)
            self.wait_until_appear(self.I_BUFF)
            occur_prepare_button = False
            while 1:
                self.screenshot()
                if not self.appear(self.I_BUFF):
                    break
                if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                    occur_prepare_button = True
                    continue
                # if occur_prepare_button and self.ocr_appear_click(self.O_BATTLE_PREPARE, interval=2):
                #     continue
            logger.info("Click prepare ensure button")

            # 照顾一下某些模拟器慢的
            time.sleep(0.1)

        # 绿标
        self.wait_until_disappear(self.I_BUFF)
        if self.is_in_battle(False):
            self.green_mark(config.green_enable, config.green_mark)

        win = self.battle_wait(config.random_click_swipt_enable)
        if win:
            return True
        else:
            return False

    def run_general_battle_back(self, config: GeneralBattleConfig = None) -> bool:
        """
        进入挑战然后直接返回
        :param config:
        :return:
        """
        # 如果没有锁定队伍那么在点击准备后才退出的
        if not config.lock_team_enable:
            # 点击准备按钮
            self.wait_until_appear(self.I_PREPARE_HIGHLIGHT)
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                    continue
                if not self.appear(self.I_PRESET):
                    break
            logger.info(f"Click {self.I_PREPARE_HIGHLIGHT.name}")

        # 点击返回
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT, interval=1.5):
                continue
            if self.appear(self.I_EXIT_ENSURE):
                break
        logger.info(f"Click {self.I_EXIT.name}")

        # 点击返回确认
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT_ENSURE, interval=1.5):
                continue
            if self.appear(self.I_FALSE):
                break
        logger.info(f"Click {self.I_EXIT_ENSURE.name}")

        # 点击失败确认
        self.wait_until_appear(self.I_FALSE)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FALSE, interval=1.5):
                continue
            if not self.appear(self.I_FALSE):
                break
        logger.info(f"Click {self.I_FALSE.name}")

        return True

    def exit_battle(self, skip_first: bool = False) -> bool:
        """
        在战斗的时候强制退出战斗
        :return:
        """
        if skip_first:
            self.screenshot()

        if not self.appear(self.I_EXIT):
            return False

        # 点击返回
        logger.info(f"Click {self.I_EXIT.name}")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT, interval=1.5):
                continue
            if self.appear(self.I_EXIT_ENSURE):
                break

        # 点击返回确认
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_EXIT_ENSURE, interval=1.5):
                continue
            if self.appear_then_click(self.I_FALSE, interval=1.5):
                continue
            if not self.appear(self.I_EXIT):
                break

        return True

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        等待战斗结束 ！！！
        很重要 这个函数是原先写的， 优化版本在tasks/Secret/script_task下。本着不改动原先的代码的原则，所以就不改了
        :param random_click_swipt_enable:
        :return:
        """
        # 有的时候是长战斗，需要在设置stuck检测为长战斗
        # 但是无需取消设置，因为如果有点击或者滑动的话 handle_control_check会自行取消掉
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        win: bool = False
        while 1:
            self.screenshot()
            # 如果出现赢 就点击, 第二个是针对封魔的图片
            if self.appear(self.I_WIN, threshold=0.8) or self.appear(self.I_DE_WIN):
                logger.info("Battle result is win")
                if self.appear(self.I_DE_WIN):
                    self.ui_click_until_disappear(self.I_DE_WIN)
                win = True
                break

            # 如果出现失败 就点击，返回False
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                win = False
                break

            # 如果领奖励
            if self.appear(self.I_REWARD, threshold=0.6):
                win = True
                break

            # 如果领奖励出现金币
            if self.appear(self.I_REWARD_GOLD, threshold=0.8):
                win = True
                break
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

        # 再次确认战斗结果
        logger.info("Reconfirm the results of the battle")
        while 1:
            self.screenshot()
            if win:
                # 点击赢了
                action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
                if self.appear_then_click(self.I_WIN, action=action_click, interval=0.5):
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
        if not self.wait_until_appear(self.I_REWARD):
            # 有些的战斗没有下面的奖励，所以直接返回
            logger.info("There is no reward, Exit battle")
            return win
        logger.info("Get reward")
        while 1:
            self.screenshot()
            # 如果出现领奖励
            action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
            if self.appear_then_click(self.I_REWARD, action=action_click, interval=1.5) or \
                    self.appear_then_click(self.I_REWARD_GOLD, action=action_click, interval=1.5):
                continue
            if not self.appear(self.I_REWARD) and not self.appear(self.I_REWARD_GOLD):
                break

        return win

    def green_mark(self, enable: bool = False, mark_mode: GreenMarkType = GreenMarkType.GREEN_MAIN):
        """
        绿标， 如果不使能就直接返回
        :param enable:
        :param mark_mode:
        :return:
        """
        if enable:
            logger.info("Green is enable")
            x, y = None, None
            match mark_mode:
                case GreenMarkType.GREEN_LEFT1:
                    x, y = self.C_GREEN_LEFT_1.coord()
                    logger.info("Green left 1")
                case GreenMarkType.GREEN_LEFT2:
                    x, y = self.C_GREEN_LEFT_2.coord()
                    logger.info("Green left 2")
                case GreenMarkType.GREEN_LEFT3:
                    x, y = self.C_GREEN_LEFT_3.coord()
                    logger.info("Green left 3")
                case GreenMarkType.GREEN_LEFT4:
                    x, y = self.C_GREEN_LEFT_4.coord()
                    logger.info("Green left 4")
                case GreenMarkType.GREEN_LEFT5:
                    x, y = self.C_GREEN_LEFT_5.coord()
                    logger.info("Green left 5")
                case GreenMarkType.GREEN_MAIN:
                    x, y = self.C_GREEN_MAIN.coord()
                    logger.info("Green main")

            # 等待那个准备的消失
            while 1:
                self.screenshot()
                if not self.appear(self.I_PREPARE_HIGHLIGHT):
                    break

            # 判断有无坐标的偏移
            self.appear_then_click(self.I_LOCAL)
            time.sleep(0.3)
            # 点击绿标
            self.device.click(x, y)

    def switch_preset_team(self, enable: bool = False, preset_group: int = 1, preset_team: int = 1):
        """
        切换预设的队伍， 要求是在不锁定队伍时的情况下
        :param enable:
        :param preset_group:
        :param preset_team:
        :return:
        """
        if not enable:
            logger.info("Preset is disable")
            return None

        logger.info("Preset is enable")
        # 点击预设按钮
        while 1:
            self.screenshot()

            if self.appear(self.I_PRESET_ENSURE):
                break
            # 首个队伍没有满足5个式神，未出现预设按钮的情况下跳出循环
            if self.appear(self.I_PRESENT_LESS_THAN_5):
                break
            if self.appear_then_click(self.I_PRESET, threshold=0.8, interval=1):
                continue
        logger.info("Click preset button")

        # 选择预设组
        x, y = None, None
        match preset_group:
            case 1:
                x, y = self.C_PRESET_GROUP_1.coord()
            case 2:
                x, y = self.C_PRESET_GROUP_2.coord()
            case 3:
                x, y = self.C_PRESET_GROUP_3.coord()
            case 4:
                x, y = self.C_PRESET_GROUP_4.coord()
            case 5:
                x, y = self.C_PRESET_GROUP_5.coord()
            case 6:
                x, y = self.C_PRESET_GROUP_6.coord()
            case 7:
                x, y = self.C_PRESET_GROUP_7.coord()
            case _:
                x, y = self.C_PRESET_GROUP_1.coord()
        self.device.click(x, y)
        logger.info("Select preset group")

        # 选择预设的队伍
        time.sleep(0.5)
        match preset_team:
            case 1:
                x, y = self.C_PRESET_TEAM_1.coord()
            case 2:
                x, y = self.C_PRESET_TEAM_2.coord()
            case 3:
                x, y = self.C_PRESET_TEAM_3.coord()
            case 4:
                x, y = self.C_PRESET_TEAM_4.coord()
            case _:
                x, y = self.C_PRESET_TEAM_1.coord()
        self.device.click(x, y)
        logger.info("Select preset team")

        # 点击预设确认
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_PRESET_ENSURE, threshold=0.8):
                continue
            if not self.appear(self.I_PRESET_ENSURE):
                break
        logger.info("Click preset ensure")

    def random_click_swipt(self):
        if 0 <= random.randint(0, 500) <= 3:  # 百分之4的概率
            rand_type = random.randint(0, 2)
            match rand_type:
                case 0:
                    self.click(self.C_RANDOM_CLICK, interval=20)
                case 1:
                    self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
                case 2:
                    self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
            # 重新设置为长战斗
            self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            time.sleep(0.4)  # 这样的好像不对

    # 判断是否在战斗中
    def is_in_battle(self, is_screenshot: bool = True) -> bool:
        """
        判断是否在战斗中
        :return:
        """
        if is_screenshot:
            self.screenshot()
        if self.appear(self.I_FRIENDS) or \
                self.appear(self.I_WIN) or \
                self.appear(self.I_FALSE) or \
                self.appear(self.I_REWARD):
            return True
        else:
            return False

    def is_in_prepare(self, is_screenshot: bool = True) -> bool:
        """
        判断是否在准备中
        :return:
        """
        if is_screenshot:
            self.screenshot()
        if self.appear(self.I_BUFF):
            return True
        elif self.appear(self.I_PREPARE_HIGHLIGHT):
            return True
        elif self.appear(self.I_PREPARE_DARK):
            return True
        elif self.appear(self.I_PRESET):
            return True
        else:
            return False

    def check_take_over_battle(self, is_screenshot: bool, config: GeneralBattleConfig) -> bool or None:
        """
        中途接入战斗，并且接管
        :return:  赢了返回True， 输了返回False, 不是在战斗中返回None
        """
        if is_screenshot:
            self.screenshot()
        if not self.is_in_battle():
            return None

        if self.is_in_prepare(False):
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                    continue
                if not self.appear(self.I_BUFF):
                    break

            # 被接管的战斗，只有准备阶段才可以点绿标。
            # 因为如果是战斗中，无法保证点击的时候是否出现动画
            self.wait_until_disappear(self.I_BUFF)
            self.green_mark(config.green_enable, config.green_mark)

        return self.battle_wait(config.random_click_swipt_enable)

    def check_lock(self, enable: bool, lock_image, unlock_image):
        """
        检测是否锁定队伍，
        :param enable:
        :param lock_image:
        :param unlock_image:
        :return:
        """
        if enable:
            logger.info("Lock team")
            while 1:
                self.screenshot()
                if self.appear(lock_image):
                    break
                if self.appear_then_click(unlock_image, interval=1):
                    continue
        else:
            logger.info("Unlock team")
            while 1:
                self.screenshot()
                if self.appear(unlock_image):
                    break
                if self.appear_then_click(lock_image, interval=1):
                    continue

    def check_buff(self, buff: BuffClass or list[BuffClass] = None):
        """
        检测是否开启buff
        :param buff:
        :return:
        """
        if not buff:
            return
        logger.info(f'Open buff {buff}')
        self.ui_click(self.I_BUFF, self.I_CLOUD, interval=2)
        if isinstance(buff, BuffClass):
            buff = [buff]
        match_method = {
            BuffClass.AWAKE: (self.awake, True),
            BuffClass.SOUL: (self.soul, True),
            BuffClass.GOLD_50: (self.gold_50, True),
            BuffClass.GOLD_100: (self.gold_100, True),
            BuffClass.EXP_50: (self.exp_50, True),
            BuffClass.EXP_100: (self.exp_100, True),
            BuffClass.AWAKE_CLOSE: (self.awake, False),
            BuffClass.SOUL_CLOSE: (self.soul, False),
            BuffClass.GOLD_50_CLOSE: (self.gold_50, False),
            BuffClass.GOLD_100_CLOSE: (self.gold_100, False),
            BuffClass.EXP_50_CLOSE: (self.exp_50, False),
            BuffClass.EXP_100_CLOSE: (self.exp_100, False),
        }
        for b in buff:
            func, is_open = match_method[b]
            func(is_open)
            time.sleep(0.1)
        logger.info(f'Open buff success')
        while 1:
            self.screenshot()
            if not self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF, interval=1):
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = GeneralBattle(c, d)

    t.check_buff([BuffClass.EXP_50, BuffClass.GOLD_50])
