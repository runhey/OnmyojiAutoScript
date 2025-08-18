# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from cached_property import cached_property
from datetime import timedelta, datetime

from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.logger import logger

from module.exception import TaskEnd, GameStuckError
from ppocronnx.predict_system import BoxedResult


from tasks.GameUi.game_ui import GameUi
from tasks.Utils.config_enum import ShikigamiClass
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.KekkaiUtilize.config import UtilizeRule, SelectFriendList
from tasks.KekkaiUtilize.utils import CardClass, target_to_card_class
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami
from tasks.GameUi.page import page_main, page_guild


class ScriptTask(GameUi, ReplaceShikigami, KekkaiUtilizeAssets):

    def run(self):
        con = self.config.kekkai_utilize.utilize_config
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        # 收体力或者资金
        # 进入寮主页会有一个动画，等一等，让小纸人跑一会儿
        time.sleep(3)
        self.check_guild_ap_or_assets(ap_enable=con.guild_ap_enable, assets_enable=con.guild_assets_enable)
        # 进入寮结界
        self.goto_realm()
        # 顺带收体力盒子或者是经验盒子
        time.sleep(1)
        self.check_box_ap_or_exp(con.box_ap_enable, con.box_exp_enable, con.box_exp_waste)

        # 收菜看看
        self.check_utilize_harvest()
        self.realm_goto_grown()
        # 无论收不收到菜，都会进入看看至少看一眼时间还剩多少
        self.screenshot()
        if not self.appear(self.I_UTILIZE_ADD):
            remaining_time = self.O_UTILIZE_RES_TIME.ocr(self.device.image)
            if not isinstance(remaining_time, timedelta):
                logger.warning('Ocr remaining time error')
            logger.info(f'Utilize remaining time: {remaining_time}')
            # 执行失败，推出下一次执行为失败的时间间隔
            logger.info('Utilize failed, exit')
            self.back_guild()
            next_time = datetime.now() + remaining_time
            self.set_next_run(task='KekkaiUtilize', success=False, finish=True, target=next_time)
            raise TaskEnd
        if not self.grown_goto_utilize():
            logger.info('Utilize failed, exit')
        success = self.run_utilize(con.select_friend_list, con.shikigami_class, con.shikigami_order)
        self.back_guild()
        if success:
            self.set_next_run(task='KekkaiUtilize', success=True, finish=True)
        else:
            self.set_next_run(
                task='KekkaiUtilize',
                success=False,
                finish=False,
                target=datetime.now() + timedelta(minutes=5)
            )
        raise TaskEnd

    def check_guild_ap_or_assets(self, ap_enable: bool = True, assets_enable: bool = True) -> bool:
        """
        在寮的主界面 检查是否有收取体力或者是收取寮资金
        如果有就顺带收取
        :return:
        """
        if ap_enable or assets_enable:
            # 尝试移动寻找体力或资金
            try_find_ap = 0
            while try_find_ap < 3:
                self.screenshot()
                try_find_ap += 1
                if self.appear(self.I_GUILD_AP) or self.appear(self.I_GUILD_ASSETS):
                    logger.info('Find ap or assets')
                    break
                else:
                    logger.info('Try find ap or assets')
                    self.swipe(self.S_GUILD_FIND_AP)
            # 如果未找到则返回False
            if not self.appear(self.I_GUILD_AP) and not self.appear(self.I_GUILD_ASSETS):
                logger.info('No ap or assets to collect')
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

            # 资金收取确认
            if self.appear_then_click(self.I_GUILD_ASSETS_RECEIVE, interval=0.5):
                timer_check.reset()
                continue

            # 收体力
            if self.appear_then_click(self.I_GUILD_AP, interval=1.5):
                timer_check.reset()
                continue
            # 收资金
            if self.appear_then_click(self.I_GUILD_ASSETS, interval=1.5, threshold=0.6):
                timer_check.reset()
                continue

            if timer_check.reached():
                break
        logger.info('Collect ap or assets success')
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

    def check_box_ap_or_exp(self, ap_enable: bool = True, exp_enable: bool = True, exp_waste: bool = True) -> bool:
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
        def _check_ap_box(appear: bool = False):
            if not appear:
                return False
            # 点击盒子
            timer_ap = Timer(6)
            timer_ap.start()
            while 1:
                self.screenshot()

                if self.appear(self.I_UI_REWARD):
                    while 1:
                        self.screenshot()
                        if not self.appear(self.I_UI_REWARD):
                            break
                        if self.appear_then_click(self.I_UI_REWARD, self.C_UI_REWARD, interval=1, threshold=0.6):
                            continue
                    logger.info('Reward box')
                    break

                if self.appear_then_click(self.I_BOX_AP, interval=1):
                    continue
                if self.appear_then_click(self.I_AP_EXTRACT, interval=2):
                    continue
                if timer_ap.reached():
                    logger.warning('Extract ap box timeout')
                    break
            logger.info('Extract AP box finished')
            _exit_to_realm()

        # 经验盒子
        def _check_exp_box(appear: bool = False):
            if not appear:
                logger.info('No exp box')
                return False

            time_exp = Timer(12)
            time_exp.start()
            while 1:
                self.screenshot()
                # 如果出现结界皮肤， 表示收取好了
                if self.appear(self.I_REALM_SHIN) and not self.appear(self.I_BOX_EXP, threshold=0.6):
                    break
                # 如果出现收取确认，表明进入到了有满级的
                if self.appear(self.I_UI_CONFIRM):
                    self.screenshot()
                    if not self.appear(self.I_UI_CANCEL):
                        logger.info('No cancel button')
                        continue
                    if exp_waste:
                        check_button = self.I_UI_CONFIRM
                    else:
                        check_button = self.I_UI_CANCEL
                    while 1:
                        self.screenshot()
                        if not self.appear(check_button):
                            break
                        if self.appear_then_click(check_button, interval=1):
                            continue
                    break

                if self.appear(self.I_EXP_EXTRACT):
                    # 如果达到今日领取的最大，就不领取了
                    cur, res, totol = self.O_BOX_EXP.ocr(self.device.image)
                    if cur != 0 and totol != 0 and cur == totol and cur + res == totol:
                        logger.info('Exp box reach max do not collect')
                        break
                    # 开启招财上宾后，上限增加20%，数值位置有偏移
                    cur, res, totol = self.O_BOX_EXP_ZCSB.ocr(self.device.image)
                    if cur != 0 and totol != 0 and cur == totol * 1.2 and cur + res == totol:
                        logger.info('Exp box reach max do not collect')
                        break
                if self.appear_then_click(self.I_BOX_EXP, threshold=0.6, interval=1):
                    continue
                if self.appear_then_click(self.I_EXP_EXTRACT, interval=1):
                    continue

                if time_exp.reached():
                    logger.warning('Extract exp box timeout')
                    break
            _exit_to_realm()

        self.screenshot()
        box_ap = self.appear(self.I_BOX_AP)
        box_exp = self.appear(self.I_BOX_EXP, threshold=0.6) or self.appear(self.I_BOX_EXP_MAX, threshold=0.6)
        if ap_enable:
            _check_ap_box(box_ap)
        if exp_enable:
            _check_exp_box(box_exp)

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
            logger.warning('No utilize add')
            return False

        while 1:
            self.screenshot()

            if self.appear(self.I_U_ENTER_REALM):
                break
            if self.appear_then_click(self.I_UTILIZE_ADD, interval=2):
                continue
        logger.info('Enter utilize')
        return True

    def switch_friend_list(self, friend: SelectFriendList = SelectFriendList.SAME_SERVER) -> bool:
        """
        切换不同的服务区
        :param friend:
        :return:
        """
        logger.info('Switch friend list to %s', friend)
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
        if friend == SelectFriendList.DIFFERENT_SERVER:
            time.sleep(1)
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

    @cached_property
    def order_cards(self) -> list[CardClass]:
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        result = []
        if rule == UtilizeRule.DEFAULT:
            result = [CardClass.TAIKO6, CardClass.FISH6, CardClass.TAIKO5, CardClass.FISH5,
                      CardClass.TAIKO4, CardClass.FISH4, CardClass.TAIKO3, CardClass.FISH3]
        elif rule == UtilizeRule.FISH:
            result = [CardClass.FISH6, CardClass.FISH5, CardClass.FISH4, CardClass.FISH3,
                      CardClass.TAIKO6, CardClass.TAIKO5, CardClass.TAIKO4, CardClass.TAIKO3]
        elif rule == UtilizeRule.TAIKO:
            result = [CardClass.TAIKO6, CardClass.TAIKO5, CardClass.TAIKO4, CardClass.TAIKO3,
                      CardClass.FISH6, CardClass.FISH5, CardClass.FISH4, CardClass.FISH3]
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')
        return result

    def run_utilize(self, friend: SelectFriendList = SelectFriendList.SAME_SERVER,
                    shikigami_class: ShikigamiClass = ShikigamiClass.N,
                    shikigami_order: int = 7) -> bool:
        """
        执行寄养
        :param shikigami_class:
        :param friend:
        :param rule:
        :return:
        """
        def _current_select_best(last_best: CardClass or None) -> CardClass | None:
            """
            当前选中的最好的卡,(会自动和记录的最好的比较)
            包括点击这种卡
            :return: 返回当前选中的最好的卡， 如果什么的都没有，返回None
            """
            self.screenshot()
            target = self.order_targets.find_anyone(self.device.image)
            if target is None:
                logger.info('No target card found')
                return None
            card_class = target_to_card_class(target)
            logger.info('Current find best card: %s', target)
            # 如果当前的卡比记录的最好的卡还要好,那么就更新最好的卡
            if last_best is not None:
                last_index = self.order_cards.index(last_best)
                current_index = self.order_cards.index(card_class)
                if current_index >= last_index:
                    # 不比上一张卡好就退出不执行操作，相同星级卡亦跳过
                    logger.info('Current card is not better than last best card')
                    return last_best
            logger.info('Current select card: %s', card_class)

            self.appear_then_click(target, interval=0.3)
            # 验证这张卡 的等级是否一致
            # while 1:
            #     self.screenshot()
            return card_class
        def select_friend(friend_name: str) -> bool:
            """
            尝试在当前界面中识别并选择指定名称的好友
            :param friend_name: 要选择的好友名称
            :return: 成功选择返回True
            """
            logger.info(f"尝试选择好友: {friend_name}")
            original_filter = self.O_UTILIZE_F_LIST.filter
            try:
                # 替换为自定义filter
                self.O_UTILIZE_F_LIST.filter = self.filter
                while 1:
                    self.screenshot()
                    self.O_UTILIZE_F_LIST.keyword = friend_name
                    if self.ocr_appear_click(self.O_UTILIZE_F_LIST):
                        logger.info(f"成功选择好友: {friend_name}")
                        return True
                    else:
                        return False
            finally:
                # 恢复原始filter方法，防止副作用
                self.O_UTILIZE_F_LIST.filter = original_filter

        logger.hr('Start utilize')
        self.switch_friend_list(friend)
        self.swipe(self.S_U_END, interval=3)
        if friend == SelectFriendList.SAME_SERVER:
            self.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)
            self.switch_friend_list(SelectFriendList.SAME_SERVER)
        else:
            self.switch_friend_list(SelectFriendList.SAME_SERVER)
            self.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)

        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        friend_name = self.config.kekkai_utilize.utilize_config.utilize_friend
        if rule == UtilizeRule.FRIEND:
            swipe_count = 0
            while 1:
                self.screenshot()
                if select_friend(friend_name):
                    break

                # 超过十次就退出
                if swipe_count > 10:
                    logger.warning('Swipe count is more than 10')
                    break

                # 一直向下滑动
                self.swipe(self.S_U_UP, interval=0.9)
                swipe_count += 1
                time.sleep(3)

        else:
            card_best = None
            swipe_count = 0
            while 1:
                self.screenshot()
                current_card = _current_select_best(card_best)

                if current_card is None:
                    break
                else:
                    card_best = current_card

                # 超过十次就退出
                if swipe_count > 10:
                    logger.warning('Swipe count is more than 10')
                    break

                # 一直向下滑动
                self.swipe(self.S_U_UP, interval=0.9)
                swipe_count += 1
                time.sleep(3)
            # 最好的结界卡
            logger.info('End best card is %s', card_best)

        # 进入结界
        self.screenshot()
        if not self.appear(self.I_U_ENTER_REALM):
            logger.warning('Cannot find enter realm button')
            # 可能是滑动的时候出错
            logger.warning('The best reason is that the swipe is wrong')
            return False
        TIMEOUT_SEC = 120          # 超时时长（秒）
        start_time = time.time()   # 记录起始时间
        while 1:
            # ——1. 先做超时检查——
            if time.time() - start_time > TIMEOUT_SEC:
                logger.error('寄养等待超过 2 分钟，自动退出')
                raise GameStuckError('寄养超时（>120 s）')
            self.screenshot()
            if self.appear(self.I_CHECK_FRIEND_REALM_1):
                self.wait_until_stable(self.I_CHECK_FRIEND_REALM_1)
                logger.info('Appear enter friend realm button')
                break
            if self.appear(self.I_CHECK_FRIEND_REALM_3):
                self.wait_until_stable(self.I_CHECK_FRIEND_REALM_3)
                logger.info('Appear enter friend realm button')
                break

            if self.appear_then_click(self.I_CHECK_FRIEND_REALM_2, interval=1.5):
                logger.info('Click too fast to enter the friend\'s realm pool')
                continue
            if self.appear_then_click(self.I_U_ENTER_REALM, interval=2.5):
                time.sleep(0.5)
                continue
        logger.info('Enter friend realm')

        # 切换式神的类型
        self.switch_shikigami_class(shikigami_class)
        # 判断好友的有两个位置还是一个坑位
        stop_image = None
        self.screenshot()
        if self.appear(self.I_U_ADD_1):  # 右侧第一个有（无论左侧有没有）
            stop_image = self.I_U_ADD_1
        elif self.appear(self.I_U_ADD_2) and not self.appear(self.I_U_ADD_1):  # 右侧第二个有 但是最左边的没有，这表示只留有一个坑位
            stop_image = self.I_U_ADD_2
        if not stop_image:
            # 没有坑位可能是其他人的手速太快了抢占了
            logger.warning('Cannot find stop image')
            logger.warning('Maybe other people is faster than you')
            return False

        self.set_shikigami(shikigami_order, stop_image)
        return True

    def filter(self, boxed_results: list[BoxedResult], keyword: str=None) -> list or None:
        """
        使用ocr获取结果后和keyword进行匹配. 返回匹配的index list
        :param keyword: 如果不指定默认适用对象的keyword
        :param boxed_results:
        :return:
        """
        # 首先先将所有的ocr的str顺序拼接起来, 然后再进行匹配
        logger.info(f"重写的filter方法")
        result = None
        strings = [boxed_result.ocr_text for boxed_result in boxed_results]
        concatenated_string = "".join(strings)
        if keyword is None:
            keyword = self.keyword
        if keyword in concatenated_string:
            result = [index for index, word in enumerate(strings) if keyword in word]
        else:
            result = None

        if result is not None:
            # logger.info("Filter result: %s" % result)
            return result
        else:
            return None

        # 如果适用顺序拼接还是没有匹配到，那可能是竖排的，使用单个字节的keyword进行匹配
        indices = []
        # 对于keyword中的每一个字符，都要在strings中进行匹配
        # 如果这个字符在strings中的某一个string中，那么就记录这个string的index
        max_index = len(strings) - 1
        for index, char in enumerate(keyword):
            for i, string in enumerate(strings):
                if char not in string:
                    continue
                if i <= max_index:
                    indices.append(i)
                    break
        if indices:
            # 剔除掉重复的index
            indices = list(set(indices))
            return indices
        else:
            return None

    def back_guild(self):
        """
        回到寮的界面
        :return:
        """
        while 1:
            self.screenshot()

            if self.appear(self.I_GUILD_INFO):
                break
            if self.appear(self.I_GUILD_REALM):
                break

            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1):
                continue


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
    # t.screenshot()
    # print(t.appear(t.I_BOX_EXP, threshold=0.6))
    # print(t.appear(t.I_BOX_EXP_MAX, threshold=0.6))
