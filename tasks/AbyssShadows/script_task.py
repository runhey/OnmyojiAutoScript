# This Python file uses the following encoding: utf-8
# @brief    Ryou Dokan Toppa (阴阳竂道馆突破功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from datetime import datetime
from time import sleep

from future.backports.datetime import timedelta
from module.atom.click import RuleClick
from module.exception import TaskEnd
from module.logger import logger
from sympy.physics.units import hours
from sympy.plotting.intervalmath import interval
from sympy.strategies.core import switch
from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.AbyssShadows.config import AbyssShadows, EnemyType, AreaType, ClickArea, Code, AbyssShadowsDifficulty, \
    CodeList
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records, page_guild

# 单个首领/副将/精英 一次无法完成目标（一般是一次没打掉） 的情况下，最大战斗次数
MAX_BATTLE_COUNT = 2


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssShadowsAssets):
    # TODO 完善战斗次数限制
    boss_fight_count = 0  # 首领战斗次数
    general_fight_count = 0  # 副将战斗次数
    elite_fight_count = 0  # 精英战斗次数

    #
    cur_area = None
    #
    cur_preset = None
    # process list
    ps_list = []
    # 已完成 列表
    done_list = []
    # 已知的 已经被打完的  列表
    unavailable_list = []
    #
    switch_soul_done = False

    def run(self):
        """ 狭间暗域主函数

        :return:
        """
        cfg: AbyssShadows = self.config.abyss_shadows

        today = datetime.now().weekday()
        if today not in [4, 5, 6]:
            logger.info(f"Today is not abyss shadows day, exit")
            # 设置下次运行时间为本周五
            self.custom_next_run(task='AbyssShadows', custom_time=cfg.abyss_shadows_time.custom_run_time_friday,
                                 time_delta=4 - today)
            raise TaskEnd
        server_time = datetime.combine(datetime.now().date(), cfg.scheduler.server_update)
        if datetime.now() - server_time > timedelta(hours=2):
            # 超时两小时未开始,直接退出
            logger.info("")
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=True)
            raise TaskEnd

        # 进入狭间
        self.goto_abyss_shadows()

        # 尝试开启狭间
        if cfg.abyss_shadows_time.try_start_abyss_shadows:
            self.start_abyss_shadows()

        #
        self.update_list()
        _next = self.get_next()
        # TODO 增加等待时长
        if not self.select_boss(_next.get_areatype()):
            logger.warning("Failed to enter abyss shadows")
            self.goto_main()
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=False)
            raise TaskEnd

        # 等待可进攻时间  
        self.device.stuck_record_add('BATTLE_STATUS_S')
        # 集结中图片
        self.wait_until_appear(self.I_WAIT_TO_START, wait_time=2)
        # 切换御魂
        self.switch_soul_in_as()
        #
        self.wait_until_disappear(self.I_WAIT_TO_START)
        self.device.stuck_record_clear()

        self.process()

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        self.goto_main()

        # 设置下次运行时间
        # TODO 添加周四周五周六周天不同的处理方式
        self.set_next_run(task='AbyssShadows', finish=False, server=True, success=True)
        raise TaskEnd

    def update_list(self):
        # BUG 跨天可能有问题
        if self.config.model.abyss_shadows.saved_params.save_time != datetime.now().strftime("%Y-%m-%d"):
            logger.warning("there isn`t params saved today")
            return
        #
        self.ps_list = CodeList(self.config.model.abyss_shadows.process_manage.attack_order)
        #
        self.done_list = CodeList(self.config.model.abyss_shadows.saved_params.done)
        #
        self.unavailable_list = CodeList(self.config.model.abyss_shadows.saved_params.unavailable)

    def flash_list(self):
        self.ps_list.save_to_obj(self.config.model.abyss_shadows.process_manage.attack_order)
        self.done_list.save_to_obj(self.config.model.abyss_shadows.saved_params.done)
        self.unavailable_list.save_to_obj(self.config.model.abyss_shadows.saved_params.unavailable)
        self.config.model.abyss_shadows.saved_params.save_time = datetime.now().strftime("%Y-%m-%d")
        self.config.save()
        logger.info("Flash list done")

    def check_current_area(self) -> AreaType:
        ''' 获取当前区域
        :return AreaType
        '''
        while 1:
            self.screenshot()
            if self.appear(self.I_PEACOCK_AREA):
                return AreaType.PEACOCK
            elif self.appear(self.I_DRAGON_AREA):
                return AreaType.DRAGON
            elif self.appear(self.I_FOX_AREA):
                return AreaType.FOX
            elif self.appear(self.I_LEOPARD_AREA):
                return AreaType.LEOPARD
            else:
                continue

    def change_area(self, area_name: AreaType) -> bool:
        ''' 切换到下个区域
        :return
        '''
        while 1:
            self.screenshot()
            # 判断当前区域是否正确
            current_area = self.check_current_area()
            if current_area == area_name:
                break
            # 切换区域界面
            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                self.select_boss(area_name)
                logger.info(f"Switch to {area_name.name}")
                continue
            # 点击战报按钮
            if self.appear_then_click(self.I_CHANGE_AREA, interval=4):
                logger.info(f"Click {self.I_CHANGE_AREA.name}")
                continue

        return True

    def goto_main(self):
        ''' 保持好习惯，一个任务结束了就返回庭院，方便下一任务的开始或者是出错重启
        '''
        self.ui_get_current_page()
        logger.info("Exiting abyss_shadows")
        self.ui_goto(page_main)

    def goto_abyss_shadows(self) -> bool:
        ''' 进入狭间
        :return bool
        '''
        self.ui_get_current_page()
        logger.info("Entering abyss_shadows")
        self.ui_goto(page_guild)

        while 1:
            self.screenshot()
            # 进入神社
            if self.appear_then_click(self.I_RYOU_SHENSHE, interval=1):
                logger.info("Enter Shenshe")
                continue
            # 查找狭间
            if not self.appear(self.I_ABYSS_SHADOWS, threshold=0.8):
                self.swipe(self.S_TO_ABBSY_SHADOWS, interval=3)
                continue
            # 进入狭间
            if self.appear_then_click(self.I_ABYSS_SHADOWS):
                logger.info("Enter abyss_shadows")
                break
        return True

    def select_boss(self, area_name: AreaType) -> bool:
        ''' 选择暗域类型
        :return
        '''
        click_times = 0
        while 1:
            self.screenshot()
            # 区域图片与入口图片不一致，使用点击进去

            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                match area_name:
                    case AreaType.DRAGON:
                        is_click = self.click(self.C_ABYSS_DRAGON, interval=2)
                    case AreaType.PEACOCK:
                        is_click = self.click(self.C_ABYSS_PEACOCK, interval=2)
                    case AreaType.FOX:
                        is_click = self.click(self.C_ABYSS_FOX, interval=2)
                    case AreaType.LEOPARD:
                        is_click = self.click(self.C_ABYSS_LEOPARD, interval=2)
                if is_click:
                    click_times += 1
                    logger.info(f"Click {area_name.name} {click_times} times")
                if click_times >= 3:
                    logger.info(f"select boss: {area_name.name} failed")
                    return False
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                break
        self.cur_area = area_name
        return True

    def goto_enemy(self, item_code: Code) -> bool:
        # 前往当前区域 的某个 敌人
        click_area = item_code.get_enemy_click()
        logger.info(f"Click emeny area: {click_area.name}")
        # 点击战报
        while 1:
            self.screenshot()
            if self.appear(self.I_ABYSS_FIRE):
                break

            self.open_navigation()

            click_times = 0
            # 点击攻打区域,直到出现"前往"字样
            while 1:
                self.screenshot()
                # 如果点3次还没进去就表示目标已死亡,跳过
                if click_times >= 3:
                    logger.warning(f"Failed to click {click_area}")
                    return False
                # 出现前往按钮就退出
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    break
                if self.click(click_area, interval=1.5):
                    click_times += 1
                    continue
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    continue

            # 点击前往按钮,知道该按钮消失或出现"挑战"字样
            while 1:
                self.screenshot()
                if self.appear(self.I_ABYSS_FIRE):
                    break
                if self.appear(self.I_ENSURE_BUTTON):
                    self.click(self.I_ENSURE_BUTTON, interval=1)
                    continue
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    self.click(self.I_ABYSS_GOTO_ENEMY, interval=1)
                    continue
                if not self.wait_until_appear(self.I_ABYSS_FIRE, wait_time=10):
                    break
        return True

    def attack_enemy(self):
        # 点击战斗按钮
        while 1:
            self.screenshot()
            #
            if self.appear(self.I_ABYSS_ENEMY_FIRE):
                self.click(self.I_ABYSS_ENEMY_FIRE, interval=0.4)
                continue
            #
            if self.appear_then_click(self.I_ABYSS_FIRE, interval=1):
                continue
            # 挑战敌人后，如果是奖励次数上限，会出现确认框
            if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                continue
            #
            if self.appear(self.I_PREPARE_HIGHLIGHT):
                break
        return

    def start_abyss_shadows(self):
        # 尝试开启狭间暗域

        if not self.appear(self.I_SELECT_DIFFICULTY):
            logger.info("Failed to Open abyss_shadows ,cause not found I_SELECT_DIFFICULTY")
            return
        # 选择难度
        self.ui_click(self.I_SELECT_DIFFICULTY, stop=self.I_DIFFICULTY_EASY, interval=2)

        difficulty_btn = None
        match self.config.model.abyss_shadows.abyss_shadows_time.difficulty:
            case AbyssShadowsDifficulty.EASY:
                difficulty_btn = self.I_DIFFICULTY_EASY
            case AbyssShadowsDifficulty.HARD:
                difficulty_btn = self.I_DIFFICULTY_HARD
            case AbyssShadowsDifficulty.NORMAL:
                difficulty_btn = self.I_DIFFICULTY_NORMAL
        self.ui_click_until_disappear(difficulty_btn, interval=2)
        # 开始
        self.ui_click(self.I_BTN_START, stop=self.I_START_ENSURE, interval=2)
        self.ui_click_until_disappear(self.I_START_ENSURE, interval=2)

    def process(self):
        while True:
            self.update_list()
            next = self.get_next()
            if next is None:
                break
            self.execute(next)
            self.flash_list()

    def get_next(self) -> Code:
        # 获取下一个任务目标
        for ps in self.ps_list:
            if ps not in self.done_list and ps not in self.unavailable_list:
                return ps
        return None

    def open_navigation(self):
        while True:
            self.screenshot()
            if self.appear(self.I_ABYSS_MAP):
                break
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION,interval=1)
                continue
            if self.appear(self.I_ABYSS_FIRE) or self.appear(self.I_ABYSS_GOTO_ENEMY):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT,interval=2)
                continue


    def execute(self, item_code: Code):
        area = item_code.get_areatype()
        need_change_area = (self.cur_area is None) or (area == self.cur_area)
        if need_change_area:
            self.change_area(area)
            self.cur_area = area
        # 当前应当在正确的区域
        #
        # if not self.check_available(item_code):
        #     return

        if not self.goto_enemy(item_code):
            # 前往失败，添加进unavailable_list
            self.unavailable_list.append(item_code)
            return False

        battle_count = MAX_BATTLE_COUNT
        while battle_count > 0:
            self.attack_enemy()
            # 战斗
            suc = self.run_battle(item_code)
            if suc:
                break
            battle_count -= 1
        return True

    def run_battle(self, item_code: Code):
        success = False
        enemy = item_code.get_enemy_click()
        enemy_type = enemy.get_enemy_type()

        # 判断是否需要更换预设
        def get_preset(enemy_type):
            match enemy_type:
                case EnemyType.BOSS:
                    return self.config.model.abyss_shadows.process_manage.preset_boss
                case EnemyType.ELITE:
                    return self.config.model.abyss_shadows.process_manage.preset_elite
                case EnemyType.GENERAL:
                    return self.config.model.abyss_shadows.process_manage.preset_general

        preset = get_preset(enemy_type)
        if preset != self.cur_preset:
            self.switch_preset_team_with_str(preset)
            self.cur_preset = preset

        # 点击准备
        self.ui_click_until_disappear(self.I_PREPARE_HIGHLIGHT, interval=0.3)

        # 标记主怪
        is_need_mark_main = self.config.model.abyss_shadows.process_manage.is_need_mark_main()
        if is_need_mark_main:
            self.ui_click(self.I_MARK_MAIN, interval=1)

        # 生成退出条件
        def generate_quit_condition(enemy_type):
            strategy = None
            match enemy_type:
                case EnemyType.BOSS:
                    strategy = self.config.model.abyss_shadows.process_manage.strategy_boss
                case EnemyType.ELITE:
                    strategy = self.config.model.abyss_shadows.process_manage.strategy_elite
                case EnemyType.GENERAL:
                    strategy = self.config.model.abyss_shadows.process_manage.strategy_general
            return self.config.model.abyss_shadows.process_manage.parse_strategy(strategy)

        condition = generate_quit_condition(enemy_type)
        _cur_damage = 0
        self.device.screenshot_interval_set(1)
        while True:
            self.screenshot()
            if condition.is_need_damage_value():
                _cur_damage = self.O_DAMAGE.ocr_digit(self.device.image)
                logger.info(f"Damage Done: {_cur_damage}")
            if condition.is_valid(_cur_damage):
                self.device.screenshot_interval_set()
                self.quit_battle()
                break
            # 战斗胜利标志
            if self.appear_then_click(self.I_WIN, interval=1):
                self.device.screenshot_interval_set()
                continue
            # 战斗奖励标志
            if self.appear_then_click(self.I_REWARD, interval=1):
                self.device.screenshot_interval_set()
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.device.screenshot_interval_set()
                break
        if condition.is_passed():
            # 通过条件结束的,视其为 完成，加入完成队列
            self.done_list.append(item_code)
            success = True

        logger.info(f"{enemy_type.name} DONE")
        return success

    def quit_battle(self):
        # TODO quit
        self.ui_click(self.C_QUIT_AREA, self.I_EXIT_ENSURE, interval=2)
        self.ui_click_until_disappear(self.I_EXIT_ENSURE, interval=2)
        return

    def switch_preset_team_with_str(self, v: str):
        tmp = v.split(',')
        if not tmp or len(tmp) != 2:
            logger.error(f"Due to a configuration error (value: {v}), an error occurred while switch preset team.")
            return
        self.switch_preset_team(True, int(tmp[0]), int(tmp[1]))

    def switch_soul_in_as(self):
        if self.switch_soul_done:
            return
        if not self.config.model.abyss_shadows.switch_soul_config.enable:
            self.switch_soul_done = True
            return

        logger.info("start switch soul...")

        def switch_soul(v: str):
            l = v.split(',')
            if len(l) != 2:
                logger.error(f"Due to a configuration error (value: {v}), an error occurred while switch soul.")
                return
            self.switch_soul_one(int(l[0]), int(l[1]))

        self.ui_click_until_disappear(self.I_ABYSS_SHIKI, interval=2)

        switch_soul(self.config.model.abyss_shadows.process_manage.preset_boss)
        switch_soul(self.config.model.abyss_shadows.process_manage.preset_general)
        switch_soul(self.config.model.abyss_shadows.process_manage.preset_elite)
        self.switch_soul_done = True
        # 退出式神录
        from tasks.GameUi.assets import GameUiAssets as gua
        self.ui_click_until_disappear(gua.I_BACK_Y, interval=2)

    def check_available(self, item_code: Code):
        # TODO 设想使用平均亮度分辨 是否可用
        self.change_area(item_code.get_areatype())

        while True:
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION, interval=2)
                continue
            if self.appear(self.I_ABYSS_MAP):
                break

        return True


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    import cv2, numpy as np

    # config = Config('却把烟花嗅')
    # device = Device(config)

    image = cv2.imread('E:/5.png')
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    lower_green = np.array([167, 100, 200])
    upper_green = np.array([180, 225, 225])
    mask = cv2.inRange(hsv_image, lower_green, upper_green)
    res_img = cv2.bitwise_and(image, image, mask=mask)
    cv2.imshow('res', res_img)
    cv2.waitKey()

    # t = ScriptTask(config, device)
    # t.screenshot()
    # t.start_abyss_shadows()
