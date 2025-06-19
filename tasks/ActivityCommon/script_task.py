# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import os
from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.Restart.assets import RestartAssets

""" 活动通用 """


class ScriptTask(GameUi, SwitchSoul):

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

        # 进入活动
        self.goto_activity()

        # 回到庭院
        self.ui_get_current_page()
        self.ui_goto(page_main)

        self.set_next_run(task='ActivityCommon', success=True, finish=True)
        raise TaskEnd

    def goto_activity(self):

        # 动态加载所有图片
        image_templates = self._load_image_template()

        click_count = 0
        click_count_max = 5
        last_clicked_file = None  # 记录上一次点击的文件名

        while 1:
            self.screenshot()
            # 获得奖励
            if self.ui_reward_appear_click():
                continue
            # 误点聊天频道会自动关闭
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                continue
            for image_template in image_templates:
                new_rule = RuleImage(
                    roi_front=(0, 0, 1280, 720),
                    roi_back=(0, 0, 1280, 720),
                    threshold=image_template.threshold,
                    method=image_template.method,
                    file=image_template.file
                )
                if self.appear_then_click(new_rule, interval=1):
                    current_file = os.path.basename(image_template.file)
                    # logger.info(f"成功点击图片: {current_file}")
                    # 判断是否连续点击同一图片
                    if current_file == last_clicked_file:
                        click_count += 1
                        if click_count >= click_count_max:
                            logger.info(f"连续点击同一图片达到最大次数，退出循环")
                            self.push_notify(content='任务完成')
                            return
                    else:
                        click_count = 0  # 点击不同图片时重置计数

                    last_clicked_file = current_file  # 更新记录

                    self.device.stuck_record_add('BATTLE_STATUS_S')
                    break

    def _load_image_template(self):
        image_templates = []
        image_folder = "./tasks/ActivityCommon/auto/"
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

    c = Config('mi')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
