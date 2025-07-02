# This Python file uses the following encoding: utf-8
# @brief    AbyssShadows(阴阳竂狭间暗域功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
from time import sleep

from datetime import datetime

from future.backports.datetime import timedelta
from module.exception import TaskEnd, RequestHumanTakeover
from module.base.timer import Timer
from module.logger import logger
from module.config.config import Config
from module.device.device import Device
from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.AbyssShadows.config import AbyssShadows, EnemyType, AreaType, Code, AbyssShadowsDifficulty, \
    CodeList, IndexMap
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_guild

# 单个首领/副将/精英 一次无法完成目标（一般是一次没打掉） 的情况下，最大战斗次数
MAX_BATTLE_COUNT = 2


class AbyssShadowsFinished(Exception):
    pass


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssShadowsAssets):
    #
    min_count = {
        EnemyType.BOSS: 2,  # 最少首领战斗次数
        EnemyType.GENERAL: 4,  # 最少副将战斗次数
        EnemyType.ELITE: 6  # 最少精英战斗次数
    }

    def __init__(self, config: Config, device: Device):
        super().__init__(config, device)
        # 当前所用队伍预设
        self.cur_preset = None
        # process list
        self.ps_list: CodeList = CodeList('')
        # 已完成 列表
        self.done_list: CodeList = CodeList('')
        # 已知的 已经被打完的  列表
        self.unavailable_list: CodeList = CodeList('')
        # 是否已经切换过御魂
        self.switch_soul_done = False

    def run(self):
        """ 狭间暗域主函数

        :return:
        """
        cfg: AbyssShadows = self.config.abyss_shadows

        today = datetime.now().weekday()
        if today not in [4, 5, 6]:
            # 非周五六日，直接退出
            logger.info(f"Today is not abyss shadows day, exit")
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=True)
            raise TaskEnd
        server_time = datetime.combine(datetime.now().date(), cfg.scheduler.server_update)
        if datetime.now() - server_time > timedelta(hours=2):
            # 超时两小时未开始,直接退出
            logger.info("Timeout threshold: 2h (force quit if not started)")
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=True)
            raise TaskEnd

        # 进入狭间
        self.goto_abyss_shadows()

        # 尝试开启狭间
        if cfg.abyss_shadows_time.try_start_abyss_shadows:
            self.start_abyss_shadows()

        try:
            self.init_list_from_cfg()
            # 判断各个区域是否可用
            available_areas, unavailable_areas = self.detect_area_status()
            for area in unavailable_areas:
                self.unavailable_list += CodeList(IndexMap[area.name].value)
            if unavailable_areas:
                self.flash_list()

            # 获取需要进入的区域类型
            _next = self.get_next()
            if _next is None:
                raise AbyssShadowsFinished
            area_enter = _next.get_areatype()

            # 通过能否进入，检测狭间是否开启
            if not self.select_boss(area_enter):
                logger.warning("Failed to enter abyss shadows")
                self.goto_main()
                self.set_next_run(task='AbyssShadows', finish=False, server=False, success=False)
                raise TaskEnd

            # 集结中图片
            self.wait_until_appear(self.I_WAIT_TO_START, wait_time=2)

            # 检查活动是否结束
            if self.appear(self.I_CHECK_FINISH):
                logger.info(f"{self.I_CHECK_FINISH} appear,abyss shadows finished")
                raise AbyssShadowsFinished
            # 切换御魂
            self.switch_soul_in_as()
            #
            self.device.stuck_record_add('BATTLE_STATUS_S')
            # 等待战斗开始
            self.wait_until_appear(self.I_IS_ATTACK, wait_time=180)
            self.device.stuck_record_clear()
            #
            self.process()
        except AbyssShadowsFinished:
            logger.info("Abyss shadows finished with Exception AbyssShadowsFinished")
            pass
        logger.info("Abyss shadows process done")

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        self.goto_main()

        # 设置下次运行时间
        self.set_next_run(task='AbyssShadows', finish=True, server=True, success=True)

        self.clear_saved_params()

        raise TaskEnd

    def init_list_from_cfg(self):
        if datetime.today().strftime('%Y-%m-%d') != self.config.model.abyss_shadows.saved_params.save_date:
            logger.info("Today is not saved date, clear saved params")
            self.clear_saved_params()
        #
        self.ps_list = CodeList(self.config.model.abyss_shadows.process_manage.attack_order)
        #
        self.done_list = CodeList(self.config.model.abyss_shadows.saved_params.done)
        #
        self.unavailable_list = CodeList(self.config.model.abyss_shadows.saved_params.unavailable)
        logger.info(f"update list done!{self.done_list=} {self.unavailable_list=}")

    def flash_list(self):
        """
            NOTE 导致该任务运行过程中，从前端修改的配置将会丢失
        @return:
        """
        # BUG 跨天会出问题
        self.config.model.abyss_shadows.saved_params.save_date = datetime.today().strftime('%Y-%m-%d')
        self.config.model.abyss_shadows.saved_params.done = self.done_list.parse2str()
        self.config.model.abyss_shadows.saved_params.unavailable = self.unavailable_list.parse2str()

        self.config.save()
        logger.info(f"Flash list done!{self.done_list=} {self.unavailable_list=}")

    def clear_saved_params(self):
        self.config.model.abyss_shadows.saved_params.done = ''
        self.config.model.abyss_shadows.saved_params.unavailable = ''
        self.config.save()
        logger.info("Clear saved params done")

    def check_current_area(self) -> AreaType:
        """ 获取当前区域
        :return AreaType
        """
        while 1:
            self.screenshot()
            # 关闭战报界面
            if self.appear(self.I_ABYSS_MAP_EXIT):
                self.click(self.I_ABYSS_MAP_EXIT, interval=2)
                continue
            if self.appear(self.I_ABYSS_ENEMY_INFO_EXIT):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue
            if not self.appear(self.I_ABYSS_NAVIGATION):
                # 确定不在战报界面后依旧没有在某一区域，则返回None
                return None
            if self.appear(self.I_PEACOCK_AREA):
                return AreaType.PEACOCK
            elif self.appear(self.I_DRAGON_AREA):
                return AreaType.DRAGON
            elif self.appear(self.I_FOX_AREA):
                return AreaType.FOX
            elif self.appear(self.I_LEOPARD_AREA):
                return AreaType.LEOPARD

    def change_area(self, area_name: AreaType) -> bool:
        """ 切换到下个区域,不管成功与否,只要存在可用区域,就进入,不会停留在选择区域页面
        :return
        """
        # 确保进入区域,有 切换区域 按钮
        while 1:
            self.screenshot()
            # 如果出现挑战完成，直接退出
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished

            if self.appear(self.I_ABYSS_NAVIGATION) or self.appear(self.I_CHANGE_AREA):
                break
            #
            if self.appear(self.I_ABYSS_MAP_EXIT):
                self.click(self.I_ABYSS_MAP_EXIT, interval=2)
                continue
            #
            if self.appear(self.I_ABYSS_ENEMY_INFO_EXIT):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue

        # 判断当前区域是否正确
        current_area = self.check_current_area()
        if current_area == area_name:
            return True

        # 切换到选择区域界面
        while 1:
            self.screenshot()
            # 如果出现挑战完成，直接退出
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished

            # 出现切换区域界面
            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                break
            # 点击切换区域按钮
            if self.appear_then_click(self.I_CHANGE_AREA, interval=4):
                logger.info(f"Click {self.I_CHANGE_AREA.name}")
                continue

        # 判断区域是否可用，并进入一个区域
        available_areas, unavailable_areas = self.detect_area_status()
        success = area_name in available_areas
        if not success:
            # 更新配置
            for area in unavailable_areas:
                self.unavailable_list += CodeList(IndexMap[area.name].value)

        if available_areas is None or available_areas == []:
            # 所有区域均不可用
            raise AbyssShadowsFinished

        if not success:
            # 原参数表示的 区域 已完成，则选择第一个未完成的区域
            area_name = available_areas[0]

        self.select_boss(area_name)
        logger.info(f"Switch to {area_name.name}")

        return success

    def goto_main(self):
        """ 保持好习惯，一个任务结束了就返回庭院，方便下一任务的开始或者是出错重启
        """
        # 可能在狭间，也可能在其他界面
        timer_quit_abyss_shadows = Timer(16)
        timer_quit_abyss_shadows.start()
        while 1:
            self.screenshot()
            if timer_quit_abyss_shadows.reached():
                logger.info("timer_quit_abyss_shadows reached,")
                break
            if self.appear(self.I_ABYSS_NAVIGATION) or self.appear(self.I_CHECK_FINISH):
                break
            if self.appear(self.I_CHECK_SUMMON):
                break
            if self.appear(self.I_ABYSS_DRAGON) or self.appear(self.I_ABYSS_DRAGON_OVER):
                # 在切换区域界面
                self.device.click(x=600, y=600)
                self.wait_until_appear(self.I_ABYSS_NAVIGATION, wait_time=2)
                continue
            if self.appear_then_click(self.I_ABYSS_MAP_EXIT, interval=2):
                continue
            if self.appear_then_click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue

        #
        logger.info("Exiting abyss_shadows")
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def goto_abyss_shadows(self) -> bool:
        """ 进入狭间
        :return bool
        """
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
        """ 选择暗域类型
        :return
        """
        click_times = 0
        while 1:
            self.screenshot()
            # 区域图片与入口图片不一致，使用点击进去
            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                is_click = False
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
        return True

    def goto_enemy(self, item_code: Code) -> bool:
        # 前往当前区域 的某个 敌人
        click_area = item_code.get_enemy_click()
        logger.info(f"Click emeny area: {click_area.name}")
        # 点击前往按钮的次数，阴阳师BUG:点击后不动，
        # 所以如果失败了，在点击前，尝试使用左下方的摇杆移动一点点
        count_click_goto_enemy = 0
        # 点击战报
        while 1:
            self.screenshot()
            if self.appear(self.I_ABYSS_FIRE):
                break
            # 尝试使用左下方摇杆移动
            if count_click_goto_enemy > 0 and self.appear(self.I_ABYSS_NAVIGATION):
                self.move_a_little()
            # 打开导航页面
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
                if self.appear(self.I_CHECK_FINISH):
                    raise AbyssShadowsFinished
                if self.appear(self.I_ABYSS_FIRE):
                    break
                if self.appear(self.I_ENSURE_BUTTON):
                    self.click(self.I_ENSURE_BUTTON, interval=1)
                    continue
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    self.click(self.I_ABYSS_GOTO_ENEMY, interval=1)
                    count_click_goto_enemy += 1
                    continue
                if not self.wait_until_appear(self.I_ABYSS_FIRE, wait_time=10):
                    break
        return True

    def attack_enemy(self):
        # 点击战斗按钮
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished
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
        self.wait_until_appear(self.I_SELECT_DIFFICULTY, wait_time=2)
        if not self.appear(self.I_SELECT_DIFFICULTY):
            logger.info("Failed to Open abyss_shadows ,cause not found I_SELECT_DIFFICULTY")
            return
        if not self.appear(self.I_BTN_START):
            logger.info("Failed to Open abyss_shadows ,cause not found I_BTN_START")
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
            self.init_list_from_cfg()
            _next = self.get_next()
            if _next is None:
                break
            self.execute(_next)
            self.flash_list()

    def get_next(self) -> [Code, None]:
        # 获取下一个任务目标
        for ps in self.ps_list:
            if ps not in self.done_list and ps not in self.unavailable_list:
                return ps

        if not self.config.model.abyss_shadows.abyss_shadows_time.try_complete_enemy_count:
            #
            logger.info("All done, don`t need to fix 246")
            return None

        # 已配置的已完成,若未打满奖励,尝试补全
        # 统计已完成的各类型数量
        done_counts = {
            EnemyType.BOSS: 0,
            EnemyType.GENERAL: 0,
            EnemyType.ELITE: 0
        }

        for code in self.done_list:
            enemy_type = code.get_enemy_type()
            done_counts[enemy_type] += 1

        need_boss = done_counts[EnemyType.BOSS] < self.min_count[EnemyType.BOSS]
        need_general = done_counts[EnemyType.GENERAL] < self.min_count[EnemyType.GENERAL]
        need_elite = done_counts[EnemyType.ELITE] < self.min_count[EnemyType.ELITE]

        logger.info(f"Need boss: {need_boss}, need general: {need_general}, need elite: {need_elite}")
        all_possible_codes = []
        for area in AreaType:
            area_code = IndexMap[area.name].value  # 如 DRAGON -> 'A'
            for num in ['1', '2', '3', '4', '5', '6']:
                all_possible_codes.append(Code(f"{area_code}-{num}"))

        for code in all_possible_codes:
            if code in self.done_list or code in self.unavailable_list:
                continue

            enemy_type = code.get_enemy_type()

            if enemy_type == EnemyType.BOSS and need_boss:
                return code
            elif enemy_type == EnemyType.GENERAL and need_general:
                return code
            elif enemy_type == EnemyType.ELITE and need_elite:
                return code

        return None

    def open_navigation(self):
        while True:
            self.screenshot()
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished
            if self.appear(self.I_ABYSS_MAP):
                break
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION, interval=1)
                continue
            if self.appear(self.I_ABYSS_FIRE) or self.appear(self.I_ABYSS_GOTO_ENEMY):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue

    def execute(self, item_code: Code):
        area = item_code.get_areatype()

        if not self.change_area(area):
            return False
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
            self.device.stuck_record_clear()
            if suc:
                break
            battle_count -= 1
        logger.info(f"{item_code} push into done_list")
        self.done_list.append(item_code)
        return True

    def run_battle(self, item_code: Code):
        success = False
        enemy_type = item_code.get_enemy_type()

        # 判断是否需要更换预设
        def get_preset(_enemy_type: EnemyType):
            match _enemy_type:
                case EnemyType.BOSS:
                    return self.config.model.abyss_shadows.process_manage.preset_boss
                case EnemyType.GENERAL:
                    return self.config.model.abyss_shadows.process_manage.preset_general
                case EnemyType.ELITE:
                    return self.config.model.abyss_shadows.process_manage.preset_elite

        preset = get_preset(enemy_type)
        if preset != self.cur_preset:
            logger.info(f"enemyType{enemy_type}--Switch preset to {preset} and {self.cur_preset=}")
            self.switch_preset_team_with_str(preset)
            self.cur_preset = preset

        # 点击准备
        _timer_battle = Timer(180)
        self.wait_until_appear(self.I_PREPARE_HIGHLIGHT, wait_time=3)
        self.ui_click_until_disappear(self.I_PREPARE_HIGHLIGHT, interval=0.6)
        _timer_battle.start()

        # 生成退出条件
        # 因为条件中可能是时间相关,所以在点击准备按钮后直接生成,尽量减小误差
        condition = self.config.model.abyss_shadows.process_manage.generate_quit_condition(enemy_type)
        logger.info(f"enemyType{enemy_type}--{condition}")

        # 标记主怪
        is_need_mark_main = self.config.model.abyss_shadows.process_manage.is_need_mark_main(enemy_type)
        if is_need_mark_main:
            logger.info(f"enemyType{enemy_type}--Mark main")
            # 需要处理主怪没了的情况,增加最大次数
            count_click_mark_main = 0
            while count_click_mark_main < 5:
                if self.appear(self.I_MARK_MAIN):
                    break
                if self.click(self.C_MARK_MAIN, interval=1):
                    count_click_mark_main += 1
                    self.wait_until_appear(self.I_MARK_MAIN, wait_time=1)
                    continue

        # 绿标
        # self.green_mark(True,GreenMarkType.GREEN_LEFT1)

        _cur_damage = 0
        need_check_damage = condition.is_need_damage_value()
        self.device.screenshot_interval_set(1)
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while True:
            self.screenshot()
            if need_check_damage:
                _cur_damage = self.O_DAMAGE.ocr_digit(self.device.image)
            if condition.is_valid(_cur_damage):
                logger.info(f"Condition Validated,try to quit battle")
                self.device.screenshot_interval_set()
                self.quit_battle()
                break
            if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=3):
                # 正常来讲，此处不应该出现准备按钮，以防万一
                self.device.stuck_record_add("BATTLE_STATUS_S")
                _timer_battle.reset()
                continue
            # 战斗胜利标志
            if self.appear_then_click(self.I_WIN, interval=1):
                self.device.screenshot_interval_set()
                need_check_damage = False
                continue
            # 战斗奖励标志
            if self.appear_then_click(self.I_REWARD, interval=1):
                self.device.screenshot_interval_set()
                need_check_damage = False
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.device.screenshot_interval_set()
                break
        if condition.is_passed() or (not _timer_battle.reached()):
            # 通过条件结束的,视其为完成
            # 条件未通过且战斗时间不足3分钟的,极大可能是打死了,视之为完成
            success = True

        logger.info(f"{enemy_type.name} DONE")
        return success

    def quit_battle(self):
        logger.info("Quitting battle")
        while True:
            self.screenshot()
            if self.appear(self.I_EXIT_ENSURE):
                self.click(self.I_EXIT_ENSURE, interval=1)
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                break
            if self.appear(self.I_WIN):
                self.click(self.I_WIN, interval=1)
                continue
            if self.appear(self.I_REWARD):
                self.click(self.I_REWARD, interval=1)
                continue
            if self.appear(self.I_EXIT):
                self.click(self.I_EXIT, interval=1)
                continue
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
        if not self.config.model.abyss_shadows.process_manage.enable_switch_soul_in_as:
            self.switch_soul_done = True
            return

        logger.info("start switch soul...")

        def switch_soul(_v: str):
            l = _v.split(',')
            if len(l) != 2:
                logger.error(f"Due to a configuration error (value: {_v}), an error occurred while switch soul.")
                raise RequestHumanTakeover
            self.run_switch_soul((int(l[0]), int(l[1])))

        self.ui_click_until_disappear(self.I_ABYSS_SHIKI, interval=2)
        soul_set: set[str] = set()
        soul_set.add(self.config.model.abyss_shadows.process_manage.preset_boss)
        soul_set.add(self.config.model.abyss_shadows.process_manage.preset_general)
        soul_set.add(self.config.model.abyss_shadows.process_manage.preset_elite)

        for v in soul_set:
            switch_soul(v)

        self.switch_soul_done = True
        # 退出式神录
        from tasks.GameUi.assets import GameUiAssets as gua
        self.ui_click_until_disappear(gua.I_BACK_Y, interval=2)

    def check_available(self, item_code: Code):
        # 判断该怪物是否可用
        # TODO 设想使用平均亮度分辨 是否可用
        self.change_area(item_code.get_areatype())

        while True:
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION, interval=2)
                continue
            if self.appear(self.I_ABYSS_MAP):
                break

        return True

    def detect_area_status(self):
        # 在切换区域界面检查各个区域是否可用
        #
        available_areas = []
        unavailable_areas = []
        self.screenshot()
        for area in AreaType:
            if self.is_area_done(area):
                unavailable_areas.append(area)
                # self.unavailable_list += CodeList(IndexMap[area.name].value)
                logger.info(f"{area.name} unavailable")
                continue
            available_areas.append(area)
            logger.info(f"{area.name} available")
        return available_areas, unavailable_areas

    def is_area_done(self, area_type: AreaType):
        # 不再切换区域界面直接返回
        if not self.appear(self.I_ABYSS_DRAGON) and not self.appear(self.I_ABYSS_DRAGON_OVER):
            return False
        #
        res_img = self.device.image

        match area_type:
            case AreaType.DRAGON:
                ocr_res = self.O_DRAGON_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.FOX:
                ocr_res = self.O_FOX_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.LEOPARD:
                ocr_res = self.O_LEOPARD_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.PEACOCK:
                ocr_res = self.O_PEACOCK_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1

        return False

    def move_a_little(self):
        radius = 150
        # 寮里面摇杆的中心点
        p1 = (197, 568)
        import random
        dx, dy = random.randint(-radius, radius), random.randint(-radius, radius)
        self.device.swipe_adb(p1, (p1[0] + dx, p1[1] + dy), duration=0.5)
        logger.info(f"Swipe {p1} to {(p1[0] + dx, p1[1] + dy)}")


if __name__ == "__main__":
    import cv2, numpy as np
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas')
    device = Device(config)

    # image = cv2.imread('E:/f.png')
    # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #
    # hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    #
    # lower_green = np.array([9, 128, 180])
    # upper_green = np.array([30, 210, 255])
    # mask = cv2.inRange(hsv_image, lower_green, upper_green)
    # res_img = cv2.bitwise_and(image, image, mask=mask)
    # res_img = cv2.cvtColor(res_img, cv2.COLOR_RGB2BGR)
    # cv2.imshow('res', res_img)
    # cv2.waitKey()

    t = ScriptTask(config, device)
    radius = 150
    p1 = (197, 568)
    import random

    while True:
        dx, dy = random.randint(-radius, radius), random.randint(-radius, radius)
        t.device.swipe_adb(p1, (p1[0] + dx, p1[1] + dy), duration=0.5)
        logger.info(f"Swipe {p1} to {(p1[0] + dx, p1[1] + dy)}")
        sleep(5)

    # area_type = AreaType.DRAGON
    # t.unavailable_list += CodeList(IndexMap[area_type.name].value)
    # print(f"{t.unavailable_list=}")
    # t.screenshot()

    # cv2.imshow("origin", t.device.image)
    # cv2.waitKey()

    # res = t.O_TEST_PRE.ocr(image)
    # print(res)
    # damage = t.O_DAMAGE.ocr(res_img)
    # print(damage)

    # t.done_list = CodeList('A-4')
    # t.unavailable_list  = CodeList('D-3')
    # t.flash_list()

    # code = Code('D-1')
    # a = code.get_enemy_type()
    # b = code.get_enemy_click()
    # c = code.get_areatype()
    # print(a, b, c)
    #
    # t.is_area_done(AreaType.DRAGON)
    # t.screenshot()
    # t.start_abyss_shadows()
    # hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    #
    # lower_green = np.array([9, 128, 180])
    # upper_green = np.array([30, 210, 255])
    # mask = cv2.inRange(hsv_image, lower_green, upper_green)
    # res_img = cv2.bitwise_and(image, image, mask=mask)
    # res_img = cv2.cvtColor(res_img, cv2.COLOR_RGB2BGR)
