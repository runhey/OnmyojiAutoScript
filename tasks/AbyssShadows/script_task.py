# This Python file uses the following encoding: utf-8
# @brief    Ryou Dokan Toppa (阴阳竂道馆突破功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from datetime import datetime
import random
import numpy as np
from enum import Enum
from cached_property import cached_property
from time import sleep

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.config_base import ConfigBase, Time
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_kekkai_toppa, page_shikigami_records, page_guild
from tasks.RealmRaid.assets import RealmRaidAssets

from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.utils import point2str
from module.base.timer import Timer
from module.exception import GamePageUnknownError
from pathlib import Path
from tasks.AbyssShadows.config import AbyssShadows
from tasks.AbyssShadows.assets import AbyssShadowsAssets

class AreaType:
    """ 暗域类型 """
    DRAGON = AbyssShadowsAssets.I_ABYSS_DRAGON  # 神龙暗域
    PEACOCK = AbyssShadowsAssets.I_ABYSS_PEACOCK  # 孔雀暗域
    FOX = AbyssShadowsAssets.I_ABYSS_FOX  # 白藏主暗域
    LEOPARD = AbyssShadowsAssets.I_ABYSS_LEOPARD # 黑豹暗域

    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__

class EmemyType(Enum):

    """ 敌人类型 """
    BOSS = 1  #  首领
    GENERAL = 2  #  副将
    ELITE = 3  #  精英


class CilckArea:
    """ 点击区域 """
    GENERAL_1 = AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA
    GENERAL_2 = AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA
    ELITE_1 = AbyssShadowsAssets.C_ELITE_1_CLICK_AREA
    ELITE_2 = AbyssShadowsAssets.C_ELITE_2_CLICK_AREA
    ELITE_3 = AbyssShadowsAssets.C_ELITE_3_CLICK_AREA
    BOSS= AbyssShadowsAssets.C_BOSS_CLICK_AREA

    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssShadowsAssets):
    

    boss_fight_count = 0  # 首领战斗次数
    general_fight_count = 0  # 副将战斗次数
    elite_fight_count = 0  # 精英战斗次数
    
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
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=False)
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
            find_list = [EmemyType.BOSS, EmemyType.GENERAL, EmemyType.ELITE]
            for enemy_type in find_list:
                # 寻找敌人并开始战斗,
                if not self.find_enemy(enemy_type):
                    logger.warning(f"Failed to find {enemy_type.name} enemy, exit")
                    break
            logger.info(f"Current fight times: boss {self.boss_fight_count} times, general {self.general_fight_count}  times, elite {self.elite_fight_count} times")
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
            self.set_next_run(task='AbyssShadows', finish=True, server=True, success=True)
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
            if self.appear_then_click(self.I_CHANGE_AREA,interval=4):
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
            if self.appear_then_click(self.I_RYOU_SHENSHE,interval=1):
                logger.info("Enter Shenshe")
                continue
            # 查找狭间
            if not self.appear(self.I_ABYSS_SHADOWS, threshold=0.8):
                self.swipe(self.S_TO_ABBSY_SHADOWS,interval=3)
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
                    case AreaType.DRAGON: is_click = self.click(self.C_ABYSS_DRAGON,interval=2)
                    case AreaType.PEACOCK: is_click = self.click(self.C_ABYSS_PEACOCK,interval=2)
                    case AreaType.FOX: is_click = self.click(self.C_ABYSS_FOX,interval=2)
                    case AreaType.LEOPARD: is_click = self.click(self.C_ABYSS_LEOPARD,interval=2)
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

    def find_enemy(self, enemy_type: EmemyType) -> bool:
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
            if self.appear_then_click(self.I_ABYSS_NAVIGATION,interval=1):
                continue
 
        match enemy_type:
            case EmemyType.BOSS: success = self.run_boss_fight()
            case EmemyType.GENERAL: success = self.run_general_fight()
            case EmemyType.ELITE: success = self.run_elite_fight()
            
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
        suceess = True
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
                logger.info(f"Find abyss map, exit")
                break
        click_times = 0
        # 点击攻打区域
        while 1:
            self.screenshot()
            
            # 如果点3次还没进去就表示目标已死亡,跳过
            if click_times >= 3:
                logger.warning(f"Failed to click {click_area}")
                return 
            # 出现前往按钮就退出
            if self.appear(self.I_ABYSS_GOTO_ENEMY):
                break
            if self.click(click_area,interval=1.5):
                click_times += 1
                continue
            if self.appear_then_click(self.I_ENSURE_BUTTON,interval=1):
                continue
            # TODO 有时出现bug，点了前往之后不动，需要再点一次，带解决

        
        # 点击前往按钮
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_ABYSS_GOTO_ENEMY,interval=1):
                # 点击敌人后，如果是不同区域会确认框，点击确认                
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                # 跑动画比较花时间
                sleep(3)
                continue
            if self.appear(self.I_ABYSS_FIRE):
                break
        logger.info(f"Click {self.I_ABYSS_GOTO_ENEMY.name}")
        
        # 点击战斗按钮
        self.wait_until_appear(self.I_ABYSS_FIRE)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_ABYSS_FIRE,interval=1):
                  
                logger.info(f"Click {self.I_ABYSS_FIRE.name}")        
                # 挑战敌人后，如果是奖励次数上限，会出现确认框   
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    logger.info(f"Click {self.I_ENSURE_BUTTON.name}")
                continue
            if self.appear(self.I_PREPARE_HIGHLIGHT):
                break
            
        return suceess

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



if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('zhu')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
