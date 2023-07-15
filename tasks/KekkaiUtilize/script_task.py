# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from cached_property import cached_property

from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.logger import logger
from module.exception import TaskEnd

from tasks.GameUi.game_ui import GameUi
from tasks.Utils.config_enum import ShikigamiClass
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.KekkaiUtilize.config import UtilizeRule, SelectFriendList
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami


class ScriptTask(GameUi, ReplaceShikigami, KekkaiUtilizeAssets):

    def run(self):
        pass


    def check_guild_ap_or_assets(self, ap_enable: bool=True, assets_enable: bool=True) -> bool:
        """
        在寮的主界面 检查是否有收取体力或者是收取寮资金
        如果有就顺带收取
        :return:
        """
        if ap_enable or assets_enable:
            self.screenshot()
            if not self.appear(self.I_GUILD_AP) and not self.appear(self.I_GUILD_ASSETS):
                return False
        else:
            return False

        # 如果有就收取
        timer_check = Timer(2)
        timer_check.start()
        while 1:
            self.screenshot()

            # 获得奖励
            if self.ui_reward_appear_click():
                timer_check.reset()
                continue
            # 资金收取确认
            if self.appear_then_click(self.I_GUILD_ASSETS_RECEIVE, interval=0.5):
                timer_check.reset()
                continue

            # 收体力
            if self.appear_then_click(self.I_GUILD_AP, interval=0.5):
                timer_check.reset()
                continue
            # 收资金
            if self.appear_then_click(self.I_GUILD_ASSETS, interval=0.5):
                timer_check.reset()
                continue

            if timer_check.reached():
                break
        return True

    def goto_realm(self):
        """
        从寮的主界面进入寮结界
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_REALM_SHIN):
                break
            if self.appear(self.I_SHI_DEFENSE):
                break

            if self.appear_then_click(self.I_GUILD_REALM, interval=1):
                continue

    def check_box_ap_or_exp(self, ap_enable: bool=True, exp_enable: bool=True) -> bool:
        """
        顺路检查盒子
        :param ap_enable:
        :param exp_enable:
        :return:
        """

        # 退出到寮结界
        def _exit_to_realm():
            # 右上方关闭红色
            while 1:
                self.screenshot()
                if self.appear(self.I_REALM_SHIN):
                    break
                if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                    continue

        # 先是体力盒子
        def _check_ap_box():
            self.screenshot()
            appear = False
            if self.appear(self.I_BOX_AP):
                appear = True
            if not appear:
                return False
            # 点击盒子
            while 1:
                self.screenshot()

                if self.ui_reward_appear_click():
                    while 1:
                        # 等待动画结束
                        if not self.appear(self.I_UI_REWARD):
                            break
                    break
                if self.appear_then_click(self.I_BOX_AP, interval=1):
                    continue
                if self.appear_then_click(self.I_AP_EXTRACT, interval=2):
                    continue
            logger.info('Extract AP box finished')
            _exit_to_realm()


        # 经验盒子
        def _check_exp_box():
            self.screenshot()
            appear = False
            if self.appear(self.I_BOX_EXP):
                appear = True
            if not appear:
                return False

            while 1:
                self.screenshot()

                if self.appear_then_click(self.I_BOX_EXP, interval=1):
                    continue
                if self.appear_then_click(self.I_EXP_EXTRACT, interval=1):
                    continue

                # 如果出现结界皮肤， 表示收取好了
                if self.appear(self.I_REALM_SHIN) and not self.appear(self.I_BOX_EXP):
                    break
            _exit_to_realm()

        if ap_enable:
            _check_ap_box()
        if exp_enable:
            _check_exp_box()

    def check_utilize_harvest(self) -> bool:
        """
        在寮结界界面检查是否有收获
        :return: 如果没有返回False, 如果有就收菜返回True
        """
        self.screenshot()
        appear = self.appear(self.I_UTILIZE_EXP)
        if not appear:
            logger.info('No utilize harvest')
            return False

        # 收获
        self.ui_get_reward(self.I_UTILIZE_EXP)
        return True

    def realm_goto_grown(self):
        """
        进入式神育成界面
        :return:
        """
        while 1:
            self.screenshot()

            if self.in_shikigami_growth():
                break

            if self.appear_then_click(self.I_SHI_GROWN, interval=1):
                continue
        logger.info('Enter shikigami grown')

    def grown_goto_utilize(self):
        """
        从式神育成界面到 蹭卡界面
        :return:
        """
        self.screenshot()
        if not self.appear(self.I_UTILIZE_ADD):
            logger.info('No utilize add')
            return False

        while 1:
            self.screenshot()

            if self.appear(self.I_U_ENTER_REALM):
                break
            if self.appear_then_click(self.I_UTILIZE_ADD, interval=1):
                continue
        logger.info('Enter utilize')

    def switch_friend_list(self, friend: SelectFriendList = SelectFriendList.SAME_SERVER) -> bool:
        """
        切换不同的服务区
        :param friend:
        :return:
        """
        if friend == SelectFriendList.SAME_SERVER:
            check_image = self.I_UTILIZE_FRIEND_GROUP
        else:
            check_image = self.I_UTILIZE_ZONES_GROUP

        timer_click = Timer(1)
        timer_click.start()
        while 1:
            self.screenshot()
            if self.appear(check_image):
                break
            if timer_click.reached():
                timer_click.reset()
                x, y = check_image.coord()
                self.device.click(x=x, y=y, control_name=check_image.name)
        time.sleep(0.5)

    @cached_property
    def order_targets(self) -> ImageGrid:
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        if rule == UtilizeRule.DEFAULT:
            return ImageGrid([self.I_U_TAIKO_6, self.I_U_FISH_6, self.I_U_TAIKO_5, self.I_U_FISH_5,
                              self.I_U_TAIKO_4, self.I_U_FISH_4, self.I_U_TAIKO_3, self.I_U_FISH_3])
        elif rule == UtilizeRule.FISH:
            return ImageGrid([self.I_U_FISH_6, self.I_U_FISH_5, self.I_U_FISH_4, self.I_U_FISH_3,
                              self.I_U_TAIKO_6, self.I_U_TAIKO_5, self.I_U_TAIKO_4, self.I_U_TAIKO_3])
        elif rule == UtilizeRule.TAIKO:
            return ImageGrid([self.I_U_TAIKO_6, self.I_U_TAIKO_5, self.I_U_TAIKO_4, self.I_U_TAIKO_3,
                              self.I_U_FISH_6, self.I_U_FISH_5, self.I_U_FISH_4, self.I_U_FISH_3])
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')

if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)


