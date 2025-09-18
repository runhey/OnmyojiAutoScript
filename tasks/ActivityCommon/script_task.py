# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import os
import random
from datetime import datetime, timedelta, time
from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.Restart.assets import RestartAssets

""" 活动通用 """


class ScriptTask(GameUi, SwitchSoul, GeneralBattle):

    def run(self) -> None:

        config = self.config.activity_common
        # 切换御魂
        if config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_soul_config.switch_group_team)
        if config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                config.switch_soul_config.group_name,
                config.switch_soul_config.team_name
            )

        self.ui_get_current_page()
        self.ui_goto(page_main)

        # 进入活动 开始战斗
        self.start_activity()

        # 回到庭院
        self.ui_get_current_page()
        self.ui_goto(page_main)

        if config.activity_common_config.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

        self.set_next_run(task=self.config.task.command, success=True, finish=True)
        raise TaskEnd

    def start_activity(self):
        config = self.config.activity_common.activity_common_config
        limit_time = config.limit_time
        enable = config.enable
        if enable:
            # 限制次数
            self.limit_count = config.limit_count
            # 限制时间
            self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

        # 加载所有图片
        goto_activity_templates = self._load_image_template("gotoActivity")
        battle_templates = self._load_image_template("战斗")

        challenge = RuleImage(
            roi_front=(1100, 540, 170, 170),
            roi_back=(1100, 540, 170, 170),
            threshold=0.8,
            method="Template matching",
            file="./tasks/ActivityCommon/gotoActivity/挑战.png"
        )
        battle_templates.append(challenge)

        # 进入挑战界面
        goto_activity = False
        while not goto_activity:
            self.screenshot()
            # 获得奖励
            if self.ui_reward_appear_click():
                continue
            # 误点聊天频道会自动关闭
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                continue
            for goto_template in goto_activity_templates:
                if os.path.basename(goto_template.file) == '挑战.png':
                    self.screenshot()
                    if self.appear(goto_template):
                        goto_activity = True
                        break
                else:
                    if self.appear_then_click(goto_template, interval=1):
                        break

        # 开始战斗
        logger.hr("已在挑战界面", 1)
        click_count = 0
        click_count_max = 8
        last_clicked_file = None  # 记录上一次点击的文件名
        over_task = False
        while 1:
            self.screenshot()
            # 获得奖励
            if self.ui_reward_appear_click():
                continue
            # 误点聊天频道会自动关闭
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                continue

            # 开始战斗循环识图
            for image_template in battle_templates:
                current_file = os.path.basename(image_template.file)

                if current_file == '挑战.png':
                    self.screenshot()
                    if self.appear(image_template):
                        if over_task:
                            return True
                        if enable:
                            if datetime.now() - self.start_time > self.limit_time:
                                return
                            if self.current_count >= self.limit_count:
                                return

                if self.appear_then_click(image_template, interval=1):
                    if current_file == '御魂溢出确认.png':
                        over_task = True
                        self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())

                    if current_file == '挑战.png' and current_file != last_clicked_file:
                        self.current_count += 1
                        logger.hr("General battle Start", 2)
                        logger.info(f"Current count: {self.current_count} / {self.limit_count}")
                        task_run_time = datetime.now() - self.start_time
                        task_run_time_seconds = timedelta(seconds=int(task_run_time.total_seconds()))
                        logger.info(f"Current times: {task_run_time_seconds} / {self.limit_time}")

                    if current_file == '赢（鼓）.png':
                        while 1:
                            action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                            self.click(action_click, interval=1)
                            self.screenshot()
                            if self.appear(challenge):
                                break

                    # 判断是否连续点击同一图片
                    if current_file == last_clicked_file:
                        click_count += 1
                        if click_count >= click_count_max:
                            over_task = True
                    else:
                        click_count = 0  # 点击不同图片时重置计数

                    last_clicked_file = current_file  # 更新记录
                    if current_file == '挑战.png' or current_file == '准备.png':
                        self.device.stuck_record_add('BATTLE_STATUS_S')

    def _load_image_template(self, image_folder=None):
        image_templates = []
        image_folder = f"./tasks/ActivityCommon/{image_folder}/"
        supported_formats = ('.png', '.jpg', '.jpeg')

        # 遍历图片文件夹
        for filename in os.listdir(image_folder):
            if not filename.lower().endswith(supported_formats):
                continue
            # 构建完整路径
            file_path = os.path.join(image_folder, filename)

            # 创建RuleImage对象并添加到列表
            image_rule = RuleImage(
                roi_front=(0, 0, 1280, 720),  # 保持与原来相同的ROI参数
                roi_back=(0, 0, 1280, 720),
                threshold=0.8,
                method="Template matching",
                file=file_path
            )
            image_templates.append(image_rule)

        logger.info(f"加载图片模板集合: {image_templates}")
        logger.info(f"加载图片模板数量: {len(image_templates)}")
        return image_templates


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('switch')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
