import random
from time import sleep
from datetime import time, datetime, timedelta
from enum import Enum
import numpy as np

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from tasks.OrochiMoans.assets import OrochiMoansAssets
from tasks.OrochiMoans.config import OrochiMoans, UserStatus
from module.logger import logger
from module.exception import TaskEnd
from tasks.Dokan.assets import DokanAssets
from tasks.Dokan.utils import detect_safe_area2
from tasks.Orochi.assets import OrochiAssets

class OrochiMoansScene(Enum):
    '''
    FIXME 这些状态里，需要一个优先顺序
    '''
    # 未知界面（随机点击3次，以便跳过一些不支持的结算界面）
    OROCHI_SCENE_UNKNOWN = 0
    # 场景检测：组队界面（需要自己预先拉好队友）
    OROCHI_SCENE_TEAM = 1
    # 场景检测：进入御魂战斗，但未点开始
    OROCHI_SCENE_IN_FIELD = 2
    # 场景检测：御魂战斗进行中
    OROCHI_SCENE_FIGHTING = 3


class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, SwitchSoul, OrochiMoansAssets):
    in_orochi: bool = False
    current_scene: OrochiMoansScene = OrochiMoansScene.OROCHI_SCENE_UNKNOWN
    anti_detect_click_fixed_random_area: bool = True

    # 限制时间 
    limit_time: timedelta
    # 限制次数 
    limit_count: int = 30
    current_count: int = 0
    # 限制突破券
    limit_toppa_scrolls_enabled: bool = False
    limit_toppa_scrolls_count: int = 30
    current_toppa_scroll_count: int = 0
    # 只在第一次的时候会去点一下查看一下当前拥有的突破券数量
    is_first_check_toppa_scrolls: bool = True

    def run(self) -> bool:

        config: OrochiMoans = self.config.orochi_moans
        limit_time = config.orochi_moans_config.limit_time
        self.current_count = 0
        self.limit_count = config.orochi_moans_config.limit_count
        self.limit_time = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)
        # self.limit_toppa_scrolls_enabled = config.orochi_moans_config.limit_by_toppa_scrolls_enable
        # self.limit_toppa_scrolls_count = config.orochi_moans_config.limit_by_toppa_scrolls_count

        # 检测当前界面的场景（仅支持：组队界面、准备界面和战斗界面）, 如果检测到不能识别的场景，先随便点击三下，再次检测
        detect_count = 0
        while not self.in_orochi:
            self.in_orochi, self.current_scene = self.get_orochi_scene(False)
            logger.warning(f"try {detect_count}/3: self.in_orochi={self.in_orochi}, self.current_scene={self.current_scene}")
            sleep(1)
            detect_count += 1
            if detect_count >= 3:
                break

        # 如果不在可支持的场景界面，按正常的流程走
        if not self.in_orochi:
            self.orochi_switch_soul(config)
            self.orochi_open_soul_buf(config)

        # 开始战斗
        success = True
        match config.orochi_moans_config.user_status:
            case UserStatus.LEADER: success = self.run_leader(self.current_scene)
            # case UserStatus.MEMBER: success = self.run_member(self.current_scene)
            case _: logger.error('current version supports only running leader mode!')

        # 记得关掉
        if config.orochi_moans_config.soul_buff_enable:
            self.open_buff()
            self.soul(is_open=False)
            self.close_buff()
        # 下一次运行时间
        if success:
            self.set_next_run('OrochiMoans', finish=True, success=True)
        else:
            self.set_next_run('OrochiMoans', finish=False, success=False)

        raise TaskEnd

    def orochi_open_soul_buf(self, config: OrochiMoans):
        '''
        在庭院界面打开御魂加成（考虑放到组队成功、点击挑战前）
        '''
        self.ui_get_current_page()
        self.ui_goto(page_main)
        if config.orochi_moans_config.soul_buff_enable:
            self.open_buff()
            self.soul(is_open=True)
            self.close_buff()

    def orochi_switch_soul(self, config: OrochiMoans):
        '''
        切换御魂
        '''
        # 御魂切换方式一
        if config.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_soul.switch_group_team)

        # 御魂切换方式二
        if config.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(config.switch_soul.group_name,
                                         config.switch_soul.team_name)


    def orochi_enter(self) -> bool:
        logger.info('Enter orochi')
        while True:
            self.screenshot()
            if self.appear(OrochiAssets.I_FORM_TEAM):
                return True
            if self.appear_then_click(OrochiAssets.I_OROCHI, interval=1):
                continue

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST_NEW, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True

    def check_lock(self, lock: bool = True) -> bool:
        """
        检查是否锁定阵容, 要求在八岐大蛇界面
        :param lock:
        :return:
        """
        logger.info('Check lock: %s', lock)
        if lock:
            while 1:
                self.screenshot()
                if self.appear(OrochiAssets.I_OROCHI_LOCK):
                    return True
                if self.appear_then_click(OrochiAssets.I_OROCHI_UNLOCK, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(OrochiAssets.I_OROCHI_UNLOCK):
                    return True
                if self.appear_then_click(OrochiAssets.I_OROCHI_LOCK, interval=1):
                    continue

    def get_orochi_scene(self, reuse_screenshot: bool = True):
        '''
        识别御魂任务场景
        '''
        if not reuse_screenshot:
            self.screenshot()
        
        # 场景检测：组队界面（需要自己预先拉好队友）
        if self.is_in_prepare():
            return True, OrochiMoansScene.OROCHI_SCENE_IN_FIELD
        if self.is_in_battle():
            return True, OrochiMoansScene.OROCHI_SCENE_FIGHTING
        if self.appear(self.I_ADD_2):
            return True, OrochiMoansScene.OROCHI_SCENE_TEAM

        # if self.ensure_enter():
        #     return True, OrochiMoansScene.OROCHI_SCENE_TEAM

        return False, OrochiMoansScene.OROCHI_SCENE_UNKNOWN


    def run_leader(self, scene: OrochiMoansScene = OrochiMoansScene.OROCHI_SCENE_UNKNOWN):
        logger.info(f'Start run leader:scene={scene}')

        manual_start = False
        is_first = True

        # 未知界面启动，走正常流程
        if scene == OrochiMoansScene.OROCHI_SCENE_UNKNOWN:
            self.ui_get_current_page()
            self.ui_goto(page_soul_zones)
            self.orochi_enter()
            # 创建队伍
            logger.info('Create team')
            while 1:
                self.screenshot()
                if self.appear_then_click(OrochiAssets.I_FORM_TEAM, interval=1):
                    logger.info("111")
                    break

            logger.info("23423")
            layer = self.config.orochi_moans.orochi_moans_config.layer
            logger.info(f"finding Orochi layer: {layer}")
            self.check_layer(layer)

            # 创建房间
            self.create_room()
            self.ensure_private()
            self.create_ensure()
        # elif scene == OrochiMoansScene.OROCHI_SCENE_TEAM:
        #     is_first = False
        #     manual_start = True
        else:
            is_first = False
            manual_start = True

        success = True

        # 这个时候我已经进入房间了哦
        while 1:
            # logger.warning(f"manual_start={manual_start}, first={is_first}")
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(OrochiAssets.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if manual_start and not is_first:
                if self.check_and_skip_battle_result() == True:
                    self.check_and_invite(self.config.orochi_moans.invite_config.default_invite)
                    continue

            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.config.orochi_moans.invite_config.default_invite):
                continue

            # 次数达到上限
            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info('Orochi count limit out')
                    break
            # 时间达到上限
            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('Orochi time limit out')
                    break
            # 突破券达到上限
            if self.limit_toppa_scrolls_enabled and self.current_toppa_scroll_count >= self.limit_toppa_scrolls_count:
                if self.is_in_room():
                    logger.info('Toppa scrolls limit out: current={self.current_toppa_scrolls_count}/{self.limit_toppa_scrolls_limit}')
                    break

            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('Orochi task failed')
                    success = False
                    break
                continue

            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.config.orochi_moans.invite_config, is_first=False):
                    self.run_general_battle(config=self.config.orochi_moans.general_battle_config)
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this orochi task')
                    success = False
                    break
            else:
                if manual_start:
                    is_first = False
                    self.run_general_battle(config=self.config.orochi_moans.general_battle_config)
                else:
                    if not self.run_invite(config=self.config.orochi_moans.invite_config, is_first=True):
                        logger.warning('Invite failed and exit this orochi task')
                        success = False
                        break
                    else:
                        is_first = False
                        self.run_general_battle(config=self.config.orochi_moans.general_battle_config)

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        self.ui_get_current_page()
        self.ui_goto(page_main)

        return success

    def run_member(self, scene: OrochiMoansScene = OrochiMoansScene.OROCHI_SCENE_UNKNOWN):
        logger.info('Start run member')
        self.ui_get_current_page()

        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(OrochiAssets.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue
            # 次数达到上限
            if self.current_count >= self.limit_count:
                logger.info('Orochi count limit out')
                break
            # 时间达到上限
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Orochi time limit out')
                break
            # 突破券达到上限
            if self.limit_toppa_scrolls_enabled and self.current_toppa_scroll_count >= self.limit_toppa_scrolls_count:
                logger.info('Orochi task terminated due to toppa scrolls limit: current={self.current_toppa_scrolls_count}/{self.limit_toppa_scrolls_limit}')
                break

            if self.check_then_accept():
                continue

            if self.is_in_room():
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.config.orochi_moans.invite_config.wait_time):
                    self.run_general_battle(config=self.config.orochi_moans.general_battle_config)
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            elif self.check_take_over_battle(False, config=self.config.orochi_moans.general_battle_config):
                continue

        while 1:
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_GI_HOME) or self.appear(self.I_GI_EXPLORE):
                break
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass

        self.ui_get_current_page()
        self.ui_goto(page_main)

        return True

    def is_room_dead(self) -> bool:
        '''
        如果在探索界面或者是出现在组队界面，那就是可能房间死了
        '''
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False
    
    def check_and_skip_battle_result(self, reuse_screenshot: bool = True) -> bool:
        '''
        检查是否当前为各种战斗结算界面之一，如果是，点击以便跳过该界面。
        TODO 部分界面有顺序关系，考虑按顺序实现点击以避免不必要的匹配。
        '''
        if not reuse_screenshot:
            self.screenshot()

        # 打完后，第一个界面，左上角有一个统计，但是这个图不对，先跳过（跳过的结果是：会等界面超时自动跳转到：第二个界面，左下角有一个统计）
        if self.appear(self.I_STATISTICS, threshold=0.8):
            logger.info("OrochiMoans was started at {self.I_STATISTICS.name}")
            self.ui_click_until_disappear(self.I_STATISTICS, interval=0.5)
            return True

        # 打完后，第二个界面，左下角有一个统计
        if self.appear(self.I_REWARD_STATISTICS, threshold=0.8):
            logger.info("OrochiMoans was started at {self.I_REWARD_STATISTICS.name}")
            self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA2, interval=0.5)
            return True

        # 打完后，第三个界面，挑战成功
        if self.appear(self.I_WIN):
            action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
            self.click(click=action_click, interval=0.8)
            return True

        # 出现失败 就点击
        if self.appear_then_click(self.I_FALSE, threshold=0.8):
            logger.info("OrochiMoans was started at {self.I_FALSE.name}")
            return True

        # 领奖励
        if self.appear(self.I_REWARD, threshold=0.65):
            action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
            self.click(click=action_click, interval=1.2)
            logger.info("OrochiMoans was started at {self.I_REWARD.name}")
            return True

        # 领奖励出现金币
        if self.appear_then_click(self.I_REWARD_GOLD, threshold=0.8):
            logger.info("OrochiMoans was started at {self.I_REWARD_GOLD.name}")
            return True

        # 猫咪奖励
        if self.appear(OrochiAssets.I_PET_PRESENT):
            action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
            self.click(click=action_click, interval=0.6)
            return True

        return False
    
    def check_toppa_scroll(self, reuse_screenshot: bool = True) -> bool:
        '''
        检查突破券掉落
        '''
        if not reuse_screenshot:
            self.screenshot()

        # 匹配突破券
        if self.I_TOPPA_SCROLL.match(self.device.image):
            if self.is_first_check_toppa_scrolls:
                # 仅第一次发现突破券的时候去点击，以查看当前突破券数量
                self.click(self.I_TOPPA_SCROLL)
                self.screenshot()
                cu, res, total = self.O_TOPPA_SCROLL.ocr(self.device.image)
                logger.warning(f'toppa scroll, cu={cu}, res={res}, total={total}')
                if cu == 0 and cu + res == total:
                    self.current_toppa_scroll_count = cu
                self.is_first_check_toppa_scrolls = False
            else:
                self.current_toppa_scroll_count += 1
            return True

        return False

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        战斗等待，加入突破券统计
        :param random_click_swipt_enable: 
        :return: True 战斗成功, False 战斗失败
        """
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'

        # 战斗过程 随机点击和滑动 防封
        # logger.info("OrochiMoans battle_wait")

        while 1:
            self.screenshot()
            action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
            if self.appear_then_click(self.I_WIN, action=action_click ,interval=0.8):
                # 赢的那个鼓
                continue
            if self.appear(self.I_GREED_GHOST):
                # 检查突破券
                self.check_toppa_scroll()

                # 贪吃鬼
                logger.info('OrochiMoans battle_wait:Win battle')
                self.wait_until_appear(self.I_REWARD, wait_time=1.5)
                self.screenshot()
                if not self.appear(self.I_GREED_GHOST):
                    logger.warning('OrochiMoans battle_wait: Greedy ghost disappear. Maybe it is a false battle')
                    continue
                while 1:
                    self.screenshot()
                    action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                    if not self.appear(self.I_GREED_GHOST):
                        break
                    if self.click(action_click, interval=1.5):
                        continue
                return True
            if self.appear(self.I_REWARD):
                # 魂
                logger.info('OrochiMoans battle_wait: Win battle')
                # appear_greed_ghost = self.appear(self.I_GREED_GHOST)
                while 1:
                    self.screenshot()
                    action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                    if self.appear_then_click(self.I_REWARD, action=action_click, interval=1.5):
                        continue
                    if not self.appear(self.I_REWARD):
                        break
                return True

            if self.appear(self.I_FALSE):
                logger.warning('OrochiMoans battle_wait: False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

    def anti_detect(self, random_move: bool = True, random_click: bool = True, random_delay: bool = True):
        '''额外的防封测试

        准备找个号做做爬楼活动的每天300次试试
        '''
        res = False
        # 三个行为中，任何一个生效了都返回True, 否则返回False
        if random_move:
            self.random_click_swipt()
            res = True
        if random_click:
            # 0到2秒之间的随机浮点数
            sleep = random.uniform(0, 2)
            # 只保留2位小数
            sleep = round(sleep, 2)
            if self.anti_detect_click_fixed_random_area:
                # 多搞几个安全点击区域
                num = random.randint(0, 5)
                if num == 0:
                    self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA, interval=sleep)
                elif num == 1:
                    self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA2, interval=sleep)
                elif num == 2:
                    self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA3, interval=sleep)
                elif num == 3:
                    self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA, interval=sleep)
                else:
                    self.click(click=DokanAssets.C_DOKAN_RANDOM_CLICK_AREA2, interval=sleep)
            else:
                # 假设安全区域是绿色的  
                safe_color_lower = np.array([45, 25, 25])  # HSV颜色空间的绿色下界  
                safe_color_upper = np.array([90, 255, 255])  # HSV颜色空间的绿色上界
                pos = detect_safe_area2(self.device.image, safe_color_lower, safe_color_upper, 3, True)
                logger.info(f"random click area: {pos}, delay: {sleep}")
                self.click(pos)

            res = True
        if random_delay:
            # 0到2秒之间的随机浮点数
            sleep = random.uniform(0, 5)
            # 只保留2位小数
            sleep = round(sleep, 2)
            time.sleep(sleep)
            res = True
        return res


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
