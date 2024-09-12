# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from cached_property import cached_property

from module.logger import logger
from module.base.timer import Timer


from tasks.Component.GeneralInvite.config_invite import InviteConfig, InviteNumber, FindMode
from tasks.Exploration.base import BaseExploration, UpType, Scene
from tasks.Exploration.config import ChooseRarity, AutoRotate, UserStatus

class SoloExploration(BaseExploration):
    INVITE_FLAG_OFF = (157, 109, 83)
    INVITE_FLAG_ON = (227, 193, 153)

    @cached_property
    def _invite_config(self) -> InviteConfig:
        return InviteConfig(
            invite_number=InviteNumber.ONE,
            friend_1=self._config.invite_config.friend_1,
            friend_2='',
            find_mode=self._config.invite_config.find_mode,
            wait_time=self._config.invite_config.wait_time,
            default_invite=False
        )

    def run_solo(self):
        logger.hr('solo')
        explore_init = False
        search_fail_cnt = 0

        while 1:
            self.screenshot()
            scene = self.get_current_scene()

            #
            if scene == Scene.WORLD:
                if self.appear(self.I_TREASURE_BOX_CLICK):
                    # 宝箱
                    logger.info('Treasure box appear, get it.')
                    self.ui_click_until_disappear(self.I_TREASURE_BOX_CLICK)
                if self.check_exit():
                    break
                self.open_expect_level()
                explore_init = False
                continue
            #
            elif scene == Scene.ENTRANCE:
                if self.check_exit():
                    break
                self.ui_click(self.I_E_EXPLORATION_CLICK, stop=self.I_E_SETTINGS_BUTTON)
                explore_init = False
                continue
            #
            elif scene == Scene.MAIN:
                if not explore_init:
                    self.ui_click(self.I_E_AUTO_ROTATE_OFF, stop=self.I_E_AUTO_ROTATE_ON)
                    if self._config.exploration_config.auto_rotate == AutoRotate.yes:
                        self.enter_settings_and_do_operations()
                    explore_init = True
                    continue
                # 小纸人
                if self.appear(self.I_BATTLE_REWARD):
                    if self.ui_get_reward(self.I_BATTLE_REWARD):
                        continue
                # boss
                if self.appear(self.I_BOSS_BATTLE_BUTTON):
                    if self.fire(self.I_BOSS_BATTLE_BUTTON):
                        logger.info(f'Boss battle, minions cnt {self.minions_cnt}')
                    continue
                # 小怪
                fight_button = self.search_up_fight()
                if fight_button is not None:
                    if self.fire(fight_button):
                        logger.info(f'Fight, minions cnt {self.minions_cnt}')
                    continue
                # 向后拉,寻找怪
                if search_fail_cnt >= 4:
                    search_fail_cnt = 0
                    if self.appear(self.I_SWIPE_END):
                        self.quit_explore()
                        continue
                    if self.swipe(self.S_SWIPE_BACKGROUND_RIGHT, interval=3):
                        continue
                else:
                    search_fail_cnt += 1
            #
            elif scene == Scene.BATTLE_PREPARE or scene == Scene.BATTLE_FIGHTING:
                self.check_take_over_battle(is_screenshot=False, config=self._config.general_battle_config)
            elif scene == Scene.UNKNOWN:
                continue

    def run_leader(self):
        logger.hr('leader')
        explore_init = False
        search_fail_cnt = 0
        friend_leave_timer = Timer(10)

        while 1:
            self.screenshot()
            scene = self.get_current_scene()
            # 探索大世界
            if scene == Scene.WORLD:
                self.wait_until_stable(self.I_CHECK_EXPLORATION)
                if self.appear(self.I_TREASURE_BOX_CLICK):
                    # 宝箱
                    logger.info('Treasure box appear, get it.')
                    self.wait_until_stable(self.I_UI_CANCEL, timer=Timer(0.6, 1))
                    while 1:
                        self.screenshot()
                        if self.appear(self.I_REWARD):
                            self.ui_click_until_disappear(self.I_REWARD)
                            logger.info('Get reward.')
                            break
                        if self.ui_reward_appear_click():
                            continue
                        if self.appear_then_click(self.I_UI_CANCEL, interval=0.8):
                            continue
                        if self.appear_then_click(self.I_TREASURE_BOX_CLICK, interval=1):
                            continue
                if self.check_exit():
                    self.wait_until_stable(self.I_UI_CANCEL, timer=Timer(0.6, 2))
                    if self.appear(self.I_UI_CANCEL):
                        self.ui_click_until_disappear(self.I_UI_CANCEL)
                    break
                if self.appear(self.I_UI_CONFIRM):
                    self.ui_click_until_disappear(self.I_UI_CONFIRM)
                    # 可以加一下，清空第一次 explore_init
                    continue
                self.open_expect_level()
                explore_init = False
                continue

            # 邀请好友, 非常有可能是后面邀请好友，然后直接跳到组队了
            elif scene == Scene.ENTRANCE:
                while 1:
                    self.screenshot()
                    if self.is_in_room():
                        break
                    if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE, interval=0.5):
                        continue
                    if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE_2, interval=0.5):
                        continue
                    if self.appear_then_click(self.I_EXP_CREATE_TEAM, interval=1):
                        continue
                    if self.appear_then_click(self.I_EXP_CREATE_ENSURE, interval=2):
                        continue
            #
            elif scene == Scene.TEAM:
                self.wait_until_stable(self.I_ADD_2, timer=Timer(0.8, 1))
                if self.appear(self.I_FIRE, threshold=0.8) and not self.appear(self.I_ADD_2):
                    self.ui_click_until_disappear(self.I_FIRE, interval=1)
                    continue
                if self.appear(self.I_ADD_2) and self.run_invite(config=self._invite_config, is_first=True):
                    continue
                else:
                    logger.warning('Invite failed, quit')
                    while 1:
                        self.screenshot()
                        if self.appear(self.I_CHECK_EXPLORATION):
                            break
                        if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                            continue
                        if self.appear_then_click(self.I_UI_BACK_RED, interval=0.7):
                            continue
                        if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                            continue
                    break
            ##
            elif scene == Scene.MAIN:
                if not explore_init:
                    self.ui_click(self.I_E_AUTO_ROTATE_OFF, stop=self.I_E_AUTO_ROTATE_ON)
                    if self._config.exploration_config.auto_rotate == AutoRotate.yes:
                        self.enter_settings_and_do_operations()
                    friend_leave_timer = Timer(10)
                    explore_init = True
                    continue
                # 小纸人
                if self.appear(self.I_BATTLE_REWARD):
                    if self.ui_get_reward(self.I_BATTLE_REWARD):
                        continue
                # 中途有人跑路
                if not self.appear(self.I_TEAM_EMOJI):
                    if not friend_leave_timer.started():
                        logger.warning('Mate leave, start timer')
                        friend_leave_timer = Timer(10)
                        friend_leave_timer.start()
                    elif friend_leave_timer.started() and friend_leave_timer.reached():
                        logger.warning('Mate leave timer reached')
                        logger.warning('Exit team')
                        self.quit_explore()
                        continue
                # boss
                if self.appear(self.I_BOSS_BATTLE_BUTTON):
                    if self.fire(self.I_BOSS_BATTLE_BUTTON):
                        logger.info(f'Boss battle, minions cnt {self.minions_cnt}')
                    continue
                # 小怪
                fight_button = self.search_up_fight()
                if fight_button is not None:
                    if self.fire(fight_button):
                        logger.info(f'Fight, minions cnt {self.minions_cnt}')
                    continue
                # 向后拉,寻找怪
                if search_fail_cnt >= 4:
                    search_fail_cnt = 0
                    if self.appear(self.I_SWIPE_END):
                        self.quit_explore()
                        continue
                    if self.swipe(self.S_SWIPE_BACKGROUND_RIGHT, interval=4.5):
                        continue
                else:
                    search_fail_cnt += 1
            #
            elif scene == Scene.BATTLE_PREPARE or scene == Scene.BATTLE_FIGHTING:
                self.check_take_over_battle(is_screenshot=False, config=self._config.general_battle_config)
            elif scene == Scene.UNKNOWN:
                continue

    def run_member(self):
        logger.hr('member')
        explore_init = False
        wait_timer = Timer(50)
        friend_leave_timer = Timer(10)

        while 1:
            self.screenshot()
            scene = self.get_current_scene()
            #
            if scene == Scene.WORLD:
                if self.appear(self.I_TREASURE_BOX_CLICK):
                    # 宝箱
                    logger.info('Treasure box appear, get it.')
                    self.ui_click_until_disappear(self.I_TREASURE_BOX_CLICK)
                if self.check_exit():
                    break
                if self.check_then_accept():
                    pass
                if wait_timer.started() and wait_timer.reached():
                    logger.warning('Wait timer reached')
                    break

                explore_init = False
                continue
            #
            elif scene == Scene.ENTRANCE:
                self.ui_click_until_disappear(self.I_UI_BACK_RED)
            #
            elif scene == Scene.TEAM:
                continue
            #
            elif scene == Scene.MAIN:
                if not explore_init:
                    self.ui_click(self.I_E_AUTO_ROTATE_OFF, stop=self.I_E_AUTO_ROTATE_ON)
                    if self._config.exploration_config.auto_rotate == AutoRotate.yes:
                        self.enter_settings_and_do_operations()
                    explore_init = True
                    continue
                # 小纸人
                if self.appear(self.I_BATTLE_REWARD):
                    if self.ui_get_reward(self.I_BATTLE_REWARD):
                        continue
                #
                if not self.appear(self.I_TEAM_EMOJI):
                    logger.warning('Team emoji not appear')
                    if not friend_leave_timer.started():
                        logger.warning('Mate leave, start timer')
                        friend_leave_timer = Timer(10)
                        friend_leave_timer.start()
                    elif friend_leave_timer.started() and friend_leave_timer.reached():
                        logger.warning('Mate leave timer reached')
                        logger.warning('Exit team')
                        self.quit_explore()
                        wait_timer = Timer(50)
                        wait_timer.start()
                        continue
            #
            elif scene == Scene.BATTLE_PREPARE or scene == Scene.BATTLE_FIGHTING:
                self.check_take_over_battle(is_screenshot=False, config=self._config.general_battle_config)
            elif scene == Scene.UNKNOWN:
                continue

    def invite_friend(self, name: str = None, find_mode: FindMode = FindMode.AUTO_FIND) -> bool:
        logger.info('Click add to invite friend')
        # 点击＋号
        while 1:
            self.screenshot()
            if self.appear(self.I_LOAD_FRIEND):
                break
            if self.appear(self.I_INVITE_ENSURE):
                break
            if self.appear_then_click(self.I_ADD_2, interval=1):
                continue
            if self.appear_then_click(self.I_ADD_5_4, interval=1):
                continue

        friend_class = []
        class_ocr = [self.O_F_LIST_1, self.O_F_LIST_2, self.O_F_LIST_3, self.O_F_LIST_4]
        class_index = 0
        list_1 = self.O_F_LIST_1.ocr(self.device.image)
        list_2 = self.O_F_LIST_2.ocr(self.device.image)
        list_3 = self.O_F_LIST_3.ocr(self.device.image)
        list_4 = self.O_F_LIST_4.ocr(self.device.image)
        list_1 = list_1.replace(' ', '').replace('、', '')
        list_2 = list_2.replace(' ', '').replace('、', '')
        list_3 = list_3.replace(' ', '').replace('、', '')
        if list_1 is not None and list_1 != '' and list_1 in self.friend_class:
            friend_class.append(list_1)
        if list_2 is not None and list_2 != '' and list_2 in self.friend_class:
            friend_class.append(list_2)
        if list_3 is not None and list_3 != '' and list_3 in self.friend_class:
            friend_class.append(list_3)
        if list_4 is not None and list_4 != '' and list_4 in self.friend_class:
            friend_class.append(list_4)
        for i in range(len(friend_class)):
            if friend_class[i] == '蔡友':
                friend_class[i] = '寮友'
            elif friend_class[i] == '路区':
                friend_class[i] = '跨区'
            elif friend_class[i] == '察友':
                friend_class[i] = '寮友'
            elif friend_class[i] == '区':
                friend_class[i] = '跨区'
        logger.info(f'Friend class: {friend_class}')

        is_select: bool = False  # 是否选中了好友
        if find_mode == FindMode.RECENT_FRIEND:
            logger.info('Find recent friend')
            # 获取’最近‘在friend_class中的index
            if '最近' not in friend_class:
                logger.warning('No recent friend')
                return False
            recent_index = friend_class.index('最近')
            while recent_index == 1:
                self.screenshot()
                if self.appear(self.I_FLAG_2_ON):
                    break
                if self.appear_then_click(self.I_FLAG_2_OFF, interval=1):
                    continue

            logger.info(f'Now find friend in ”最近“')
            sleep(1)
            if not is_select:
                if self.detect_select(name):
                    is_select = True
            sleep(1)
            if not is_select:
                if self.detect_select(name):
                    is_select = True

        for index in range(len(friend_class)):
            # 如果不是自动寻找，就跳过
            if find_mode != FindMode.AUTO_FIND:
                continue
            # 如果已经选中了好友，就不需要再选中了
            if is_select:
                continue
            # 首先切换到不同的好友列表
            while index == 0:
                self.screenshot()
                if self.I_FLAG_1_ON.match_mean_color(self.device.image, self.INVITE_FLAG_ON, 10):
                    break
                if self.click(self.I_FLAG_1_OFF, interval=1):
                    continue
            while index == 1:
                self.screenshot()
                if self.I_FLAG_2_ON.match_mean_color(self.device.image, self.INVITE_FLAG_ON, 10):
                    break
                if self.click(self.I_FLAG_2_OFF, interval=1):
                    continue
            while index == 2:
                self.screenshot()
                if self.I_FLAG_3_ON.match_mean_color(self.device.image, self.INVITE_FLAG_ON, 10):
                    break
                if self.click(self.I_FLAG_3_OFF, interval=1):
                    continue
            while index == 3:
                self.screenshot()
                if self.I_FLAG_4_ON.match_mean_color(self.device.image, self.INVITE_FLAG_ON, 10):
                    break
                if self.click(self.I_FLAG_4_OFF, interval=1):
                    continue

            # 选中好友， 在这里游戏获取在线的好友并不是很快，根据不同的设备会有不同的时间，而且没有什么元素提供我们来判断
            # 所以这里就直接等待一段时间
            logger.info(f'Now find friend in {friend_class[index]}')
            sleep(1)
            if not is_select:
                if self.detect_select(name):
                    is_select = True
            sleep(1)
            if not is_select:
                if self.detect_select(name):
                    is_select = True

        # 点击确定
        logger.info('Click invite ensure')
        if not self.appear(self.I_INVITE_ENSURE):
            logger.warning('No appear invite ensure while invite friend')
        while 1:
            self.screenshot()
            if not self.appear(self.I_INVITE_ENSURE):
                break
            if self.appear_then_click(self.I_INVITE_ENSURE):
                continue
        # 哪怕没有找到好友也有点击 确认 以退出好友列表
        if not is_select:
            logger.warning('No find friend')
            # 这个时候任务运行失败
            logger.info('Task failed')
            return False

        return True


class ScriptTask(SoloExploration):
    def run(self):
        logger.hr('exploration')
        random_click_cnt = 0
        while 1:
            self.screenshot()
            scene = self.get_current_scene()
            if random_click_cnt >= 2:
                break
            if scene == Scene.UNKNOWN:
                logger.warning('Unknown scene, random click')
                if self.click(self.C_SAFE_RANDOM, interval=1.5):
                    random_click_cnt += 1
                continue
            else:
                break

        if scene == Scene.UNKNOWN:
            self.pre_process()

        match self._config.exploration_config.user_status:
            case UserStatus.ALONE: self.run_solo()
            case UserStatus.LEADER: self.run_leader()
            case UserStatus.MEMBER: self.run_member()
            case _: self.run_solo()

        self.post_process()


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()

