# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_shikigami_records, page_main
from tasks.Component.Costume.config import ShikigamiType
from tasks.Component.SwitchSoul.assets import SwitchSoulAssets
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.SoulsTidy.assets import SoulsTidyAssets
from tasks.SoulsTidy.script_task import ScriptTask as SoulsTidyTask


class ScriptTask(GameUi, SwitchSoul, SwitchSoulAssets, SoulsTidyAssets):
    """
    快速回归测试：验证幕间（式神录）皮肤映射是否正确生效。
    路径：主页 -> 式神录；并在式神录中检测御魂切换与御魂整理的关键识别点。
    """

    def run(self):
        # 定位并进入式神录
        self.ui_get_current_page()
        self.ui_goto(page_shikigami_records)

        # 关键识别点统计
        images_count = [
            # GameUi - 式神录判定
            [self.I_CHECK_RECORDS, 0],
            # SwitchSoul - 预设/面板关键元素（不做实际切换，仅检测图标出现）
            [self.I_SOUL_PRESET, 0],
            [self.I_SOU_CHECK_IN, 0],
            [self.I_SOU_TEAM_PRESENT, 0],
            [self.I_SOU_SWITCH_1, 0],
            [self.I_SOU_SWITCH_2, 0],
            [self.I_SOU_SWITCH_3, 0],
            [self.I_SOU_SWITCH_4, 0],
            [self.I_SOU_SWITCH_SURE, 0],
            # SoulsTidy - 御魂页面关键元素
            [self.I_ST_SOULS, 0],
            [self.I_ST_REPLACE, 0],
            [self.I_ST_TIDY, 0],
            [self.I_ST_GREED, 0],
        ]

        logger.hr('Shikigami Costume Test Start')
        timer = Timer(5)
        timer.start()
        while 1:
            self.screenshot()
            logger.info('Detecting images on Shikigami Records...')

            for i in images_count:
                if self.appear(i[0]):
                    i[1] += 1

            if timer.reached():
                logger.info('Five seconds test over')
                break

        print('--------------------------------------------------------')
        print('%-32s   %s' % ('Image', 'Count'))
        for i in images_count:
            print('%-32s %3d times' % (i[0], i[1]))
        logger.info('Shikigami Costume Test Done')

        # 测试御魂切换功能 (1-7组，每组1-4切换)
        self.test_switch_soul_all_groups()
        
        # 测试御魂奉纳功能
        self.test_souls_tidy_donation()

    def set_costume(self, costume: ShikigamiType = ShikigamiType.COSTUME_SHIKIGAMI_DEFAULT):
        self.config.model.global_game.costume_config.costume_shikigami_type = costume
        self.check_costume()
        logger.info('Set shikigami costume to %s' % self.config.model.global_game.costume_config.costume_shikigami_type)

    def test_switch_soul_all_groups(self):
        """
        测试御魂切换功能：测试1-7组，每组1-4切换
        """
        logger.hr('Switch Soul Test - All Groups')
        
        # 进入式神录
        self.ui_get_current_page()
        self.ui_goto(page_shikigami_records)
        
        # 点击预设按钮
        self.click_preset()
        
        # 测试1-7组，每组1-4切换
        for group in range(1, 8):  # 1-7组
            for team in range(1, 5):  # 1-4队
                logger.info(f'Testing group {group}, team {team}')
                try:
                    self.switch_soul_one(group, team)
                    logger.info(f'Successfully switched to group {group}, team {team}')
                except Exception as e:
                    logger.error(f'Failed to switch to group {group}, team {team}: {e}')
        
        # 退出式神录
        self.exit_shikigami_records()
        logger.info('Switch Soul Test - All Groups completed')

    def test_souls_tidy_donation(self):
        """
        测试御魂奉纳功能
        """
        logger.hr('Souls Tidy Donation Test')
        
        # 进入式神录
        self.ui_get_current_page()
        self.ui_goto(page_shikigami_records)
        
        # 进入御魂界面
        souls_tidy_task = SoulsTidyTask(self.config, self.device)
        souls_tidy_task.goto_souls()
        
        # 检查御魂界面关键元素
        detection_count = 0
        timer = Timer(5)
        timer.start()
        while 1:
            self.screenshot()
            logger.info('Detecting souls tidy interface elements...')
            
            # 检查御魂界面元素
            if self.appear(self.I_ST_GREED):
                detection_count += 1
                logger.info('Detected I_ST_GREED')
            if self.appear(self.I_ST_TIDY):
                detection_count += 1
                logger.info('Detected I_ST_TIDY')
            if self.appear(self.I_ST_REPLACE):
                detection_count += 1
                logger.info('Detected I_ST_REPLACE')
            if self.appear(self.I_ST_BONGNA):
                detection_count += 1
                logger.info('Detected I_ST_BONGNA')
                
            if timer.reached():
                logger.info('Souls tidy detection test over')
                break
        
        logger.info(f'Detected {detection_count} souls tidy interface elements')
        
        # 退回到式神录
        souls_tidy_task.back_records()
        
        # 退出式神录
        self.ui_get_current_page()
        self.ui_goto(page_main)
        logger.info('Souls Tidy Donation Test completed')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.set_costume(ShikigamiType.COSTUME_SHIKIGAMI_4)
    # t.set_costume(ShikigamiType.COSTUME_SHIKIGAMI_DEFAULT)
    t.run()
