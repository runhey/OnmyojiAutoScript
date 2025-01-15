# This Python file uses the following encoding: utf-8
# @brief    Ryou Dokan Toppa (阴阳竂道馆突破功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from datetime import datetime
from time import sleep

from module.exception import TaskEnd
from module.logger import logger
from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.AbyssShadows.config import AbyssShadows, EnemyType, AreaType, CilckArea, AbyssShadowsDifficulty
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records, page_guild


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssShadowsAssets):
    boss_fight_count = 0  # 首领战斗次数
    general_fight_count = 0  # 副将战斗次数
    elite_fight_count = 0  # 精英战斗次数

    #
    cur_area = None
    #
    cur_preset = None

    def run(self):
        """ 狭间暗域主函数

        :return:
        """
        cfg: AbyssShadows = self.config.abyss_shadows

        if cfg.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(cfg.switch_soul_config.switch_group_team)
        if cfg.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(cfg.switch_soul_config.group_name, cfg.switch_soul_config.team_name)
        today = datetime.now().weekday()
        if today not in [4, 5, 6]:
            logger.info(f"Today is not abyss shadows day, exit")
            # 设置下次运行时间为本周五
            self.custom_next_run(task='AbyssShadows', custom_time=cfg.abyss_shadows_time.custom_run_time_friday,
                                 time_delta=4 - today)
            raise TaskEnd
        success = True
        # 进入狭间
        self.goto_abyss_shadows()
        # 第一次默认选择神龙暗域
        if not self.select_boss(AreaType.DRAGON):
            logger.warning("Failed to enter abyss shadows")
            self.goto_main()
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=False)
            raise TaskEnd

        # 等待可进攻时间  
        self.device.stuck_record_add('BATTLE_STATUS_S')
        # 集结中图片
        self.wait_until_disappear(self.I_WAIT_TO_START)
        self.device.stuck_record_clear()

        # 准备攻打精英、副将、首领
        while 1:
            # 点击战报按钮
            find_list = [EnemyType.BOSS, EnemyType.GENERAL, EnemyType.ELITE]
            for enemy_type in find_list:
                # 寻找敌人并开始战斗,
                if not self.find_enemy(enemy_type):
                    logger.warning(f"Failed to find {enemy_type.name} enemy, exit")
                    break
            logger.info(
                f"Current fight times: boss {self.boss_fight_count} times, general {self.general_fight_count}  times, elite {self.elite_fight_count} times")
            # 正常应该打完一个区域了，检查攻打次数，如没打够则切换到下一个区域，默认神龙 -> 孔雀 -> 白藏主 -> 黑豹
            if self.boss_fight_count >= 2 and self.general_fight_count >= 4 and self.elite_fight_count >= 6:
                success = True
                break
            else:
                current_area = self.check_current_area()
                logger.info(f"Current area is {current_area}, switch to next area")
                if current_area == AreaType.DRAGON:
                    self.change_area(AreaType.PEACOCK)
                    continue
                elif current_area == AreaType.PEACOCK:
                    self.change_area(AreaType.FOX)
                    continue
                elif current_area == AreaType.FOX:
                    self.change_area(AreaType.LEOPARD)
                    continue
                else:
                    logger.warning("All enemy types have been defeated, but not enough emeny to fight, exit")
                    break

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        self.goto_main()

        # 设置下次运行时间
        if success:
            if today == 4:
                # 周五推迟到周六
                logger.info(f"The next abyss shadows day is Saturday")
                self.custom_next_run(task='AbyssShadows', custom_time=cfg.abyss_shadows_time.custom_run_time_saturday,
                                     time_delta=1)
            elif today == 5:
                # 周六推迟到周日
                logger.info(f"The next abyss shadows day is Sunday")
                self.custom_next_run(task='AbyssShadows', custom_time=cfg.abyss_shadows_time.custom_run_time_sunday,
                                     time_delta=1)
            elif today == 6:
                # 周日推迟到下周五
                logger.info(f"The next abyss shadows day is Friday")
                self.custom_next_run(task='AbyssShadows', custom_time=cfg.abyss_shadows_time.custom_run_time_friday,
                                     time_delta=5)
        else:
            self.set_next_run(task='AbyssShadows', finish=True, server=True, success=False)
        raise TaskEnd

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
            if self.appear(self.I_ABYSS_DRAGON):
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

            if self.appear(self.I_ABYSS_DRAGON):
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

    def find_enemy(self, enemy_type: EnemyType) -> bool:
        ''' 寻找敌人,并开始寻路进入战斗
        :return 是否找到敌人，若目标已死亡则返回False，否则返回True
        True 找到敌人，并已经战斗完成
        '''
        print(f"Find enemy: {enemy_type}")
        while 1:
            self.screenshot()
            # 点击战报按钮
            if self.appear(self.I_ABYSS_MAP):
                break
            if self.appear_then_click(self.I_ABYSS_NAVIGATION, interval=1):
                continue

        match enemy_type:
            case EnemyType.BOSS:
                success = self.run_boss_fight()
            case EnemyType.GENERAL:
                success = self.run_general_fight()
            case EnemyType.ELITE:
                success = self.run_elite_fight()

        return success

    def run_boss_fight(self) -> bool:
        ''' 首领战斗
        只要进入了战斗都返回成功
        :return 
        '''
        if self.boss_fight_count >= 2:
            logger.info(f"boss fight count {self.boss_fight_count} times, skip")
            return True
        success = True
        logger.info(f"Run boss fight")
        if self.click_emeny_area(CilckArea.BOSS):
            logger.info(f"Click {CilckArea.BOSS.name}")
            self.run_general_battle_back()
            self.boss_fight_count += 1
            logger.info(f'Fight, boss_fight_count {self.boss_fight_count} times')
        else:
            success = False
        return success

    def run_general_fight(self) -> bool:
        ''' 副将战斗
        :return 
        '''
        general_list = [CilckArea.GENERAL_1, CilckArea.GENERAL_2]
        logger.info(f"Run general fight")
        for general in general_list:
            # 副将战斗次数达到4个时，退出循环
            if self.general_fight_count >= 4:
                logger.info(f"general fight count {self.general_fight_count} times, skip")
                break
            if self.click_emeny_area(general):
                logger.info(f"Click {general.name}")
                self.general_fight_count += 1
                self.run_general_battle_back()
                logger.info(f'Fight, general_fight_count {self.general_fight_count} times')
        return True

    def run_elite_fight(self) -> bool:
        ''' 精英战斗
        :return 
        '''
        elite_list = [CilckArea.ELITE_1, CilckArea.ELITE_2, CilckArea.ELITE_3]
        logger.info(f"Run elite fight")
        for elite in elite_list:
            # 精英战斗次数达到6个时，退出循环
            if self.elite_fight_count >= 6:
                logger.info(f"Elite fight count {self.elite_fight_count} times, skip")
                break
            if self.click_emeny_area(elite):
                logger.info(f"Click {elite.name}")
                self.elite_fight_count += 1
                self.run_general_battle_back()
                logger.info(f'Fight, elite_fight_count {self.elite_fight_count} times')
        return True

    def click_emeny_area(self, click_area: CilckArea) -> bool:
        success = True
        ''' 点击敌人区域
        
        :return 
        '''
        logger.info(f"Click emeny area: {click_area.name}")
        # 点击战报
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_ABYSS_NAVIGATION, interval=1.5):
                logger.info(f"Click {self.I_ABYSS_NAVIGATION.name}")
                continue
            if self.appear(self.I_ABYSS_MAP):
                logger.info("Find abyss map, exit")

            click_times = 0
            # 点击攻打区域
            while 1:
                self.screenshot()
                # 如果点3次还没进去就表示目标已死亡,跳过
                if click_times >= 3:
                    logger.warning(f"Failed to click {click_area}")
                    success = False
                    return success
                # 出现前往按钮就退出
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    break
                if self.click(click_area, interval=1.5):
                    click_times += 1
                    continue
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    continue

            # 点击前往按钮
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_ABYSS_GOTO_ENEMY, interval=1):
                    logger.info(f"Click {self.I_ABYSS_GOTO_ENEMY.name}")
                    self.wait_until_appear(self.I_ENSURE_BUTTON, wait_time=1)
                    # 点击敌人后，如果是不同区域会确认框，点击确认                
                    if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                        logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                    # 跑动画比较花时间
                    sleep(3)
                    continue
                else:
                    break

            # 如果遇到点击前往按钮后不动的 bug，则再次尝试进入
            if self.wait_until_appear(self.I_ABYSS_FIRE, wait_time=20):
                break
            logger.warning("Failed to enter fire")

        # 点击战斗按钮
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_ABYSS_FIRE, interval=1):

                logger.info(f"Click {self.I_ABYSS_FIRE.name}")
                # 挑战敌人后，如果是奖励次数上限，会出现确认框   
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                continue
            if self.appear(self.I_PREPARE_HIGHLIGHT):
                break

        return success

    def run_general_battle_back(self) -> bool:
        """
        重写父类方法，因为狭间暗域的准备和战斗流程不一样
        进入挑战然后直接返回
        :param config:
        :return:
        """
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
            if self.appear_then_click(self.I_WIN, interval=1.5):
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                break
        logger.info(f"Click {self.I_EXIT_ENSURE.name}")

        return True

    def start_abyss_shadows(self):
        # 尝试开启狭间暗域
        self.ui_goto(page_guild)
        from tasks.Dokan.assets import DokanAssets as da
        self.ui_click_until_disappear(da.I_RYOU_SHENSHE)
        self.ui_click_until_smt_disappear(self.C_ABYSS_SHENSHE_ENTER_ABYSS, stop=da.I_RYOU_DOKAN, interval=1)
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
        #
        ps_list = self.config.model.abyss_shadows.process_manage.parse_order()
        #
        done_list = self.config.model.abyss_shadows.saved_params.done.split(";")
        #
        unavailable_list = self.config.model.abyss_shadows.saved_params.unavailable.split(";")

        def get_next():
            for ps in ps_list:
                if ps not in done_list and ps not in unavailable_list:
                    return ps
            return None

        def process_item(item):

            return

        while True:
            next = get_next()
            if next is None:
                break
            process_item(next)

    def open_navigation(self):
        self.ui_click(self.I_ABYSS_NAVIGATION, self.I_ABYSS_MAP, interval=1)

    def goto(self, item):
        self.open_navigation()
        code, area, enemy = item
        need_change_area = area == self.cur_area
        if need_change_area:
            self.change_area(area)
        #

        self.open_navigation()
        if not self.click_emeny_area(enemy):
            # 该单位不可用
            self.config.model.abyss_shadows.saved_params.unavailable += f"{code};"
            return False
        # 战斗
        self.run_battle(enemy)
        # 战后统计

    def run_battle(self, enemy):
        enemy_type = None
        match enemy:
            case AbyssShadowsAssets.C_BOSS_CLICK_AREA:
                enemy_type = EnemyType.BOSS
            case AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA | AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA:
                enemy_type = EnemyType.GENERAL
            case AbyssShadowsAssets.C_ELITE_1_CLICK_AREA | AbyssShadowsAssets.C_ELITE_2_CLICK_AREA | AbyssShadowsAssets.C_ELITE_3_CLICK_AREA:
                enemy_type = EnemyType.ELITE
            case _:
                enemy_type = EnemyType.BOSS

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
            self.switch_preset_team(preset)

        # 点击准备
        self.ui_click_until_disappear(self.I_PREPARE_HIGHLIGHT, interval=0.3)

        # 标记主怪
        is_need_mark_main=self.config.model.abyss_shadows.process_manage.is_need_mark_main()
        if is_need_mark_main:
            self.ui_click(self.I_MARK_MAIN, interval=0.3)

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
        cur_damage = 0
        self.device.screenshot_interval_set(1)
        while True:
            self.screenshot()
            if condition.is_valid(cur_damage):
                self.quit_battle()
                break
            cur_damage = self.O_DAMAGE.ocr_digit(self.device.image)
        self.device.screenshot_interval_set()

    def quit_battle(self):
        # TODO quit
        pass

    def update_state(self, item, info):
        pass


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('却把烟花嗅')
    device = Device(config)
    t = ScriptTask(config, device)
    t.screenshot()
    t.start_abyss_shadows()
