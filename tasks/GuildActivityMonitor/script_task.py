import time
from datetime import datetime, timedelta
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.GuildActivityMonitor.assets import GuildActivityMonitorAssets


class ScriptTask(GameUi, GuildActivityMonitorAssets):

    def run(self):
        """ 阴阳寮活动监控主函数（截图OCR识别方式）

        :return:
        """
        self.ui_get_current_page()
        self.ui_goto(page_main)
        guild_config = self.config.guild_activity_monitor.guild_activity
        KEYWORD_MAP = {
            '道馆': 'Dokan' if guild_config.Dokan else None,
            '狭间': 'AbyssShadows' if guild_config.AbyssShadows else None,
            '宴会': 'GuildBanquet' if guild_config.GuildBanquet else None,
            '退治': 'DemonRetreat' if guild_config.DemonRetreat else None,
        }
        KEYWORD_MAP = {k: v for k, v in KEYWORD_MAP.items() if v}
        monitored_activities = list(KEYWORD_MAP.keys())
        logger.info(f"监控活动: {monitored_activities}")

        # 初始化监控配置
        monitor_config = self.config.guild_activity_monitor.guild_activity_monitor_combat_time
        duration_minutes = monitor_config.monitor_duration
        interval = monitor_config.detection_interval
        logger.info(f"开始阴阳寮活动监控，持续{duration_minutes}分钟，每{interval}秒检测一次")

        # 初始化定时器
        check_timer = Timer(monitor_config.monitor_duration * 60)
        check_timer.start()
        log_timer = Timer(60)
        log_timer.start()

        # 记录上一次识别到的文本，用于去重
        last_detected_text = ""

        # 主监控循环
        while True:
            if check_timer.reached():
                logger.info("监控时间到，任务结束")
                self.set_next_run(task='GuildActivityMonitor', success=True, finish=True)
                raise TaskEnd('GuildActivityMonitor')

            if log_timer.reached():
                remaining = int(check_timer.remain() // 60)
                logger.info(f"监控中... 剩余时间: {remaining}分钟")
                log_timer.reset()

            # 截图并OCR识别通知区域
            self.screenshot()
            ocr_text = self.detect_notification_by_ocr()

            if ocr_text and ocr_text != last_detected_text:
                logger.info(f"OCR识别到通知区域文字: {ocr_text}")
                last_detected_text = ocr_text

                for keyword, task_name in KEYWORD_MAP.items():
                    if keyword in ocr_text:
                        logger.info(f"检测到关键字 '{keyword}'，启动任务: {task_name}")
                        self.set_next_run(task=task_name, success=False, finish=False, server=False, target=datetime.now())
                        recheck_interval = monitor_config.recheck_interval
                        self.set_next_run(task='GuildActivityMonitor', success=False, finish=False, server=False,
                                          target=datetime.now() + timedelta(minutes=recheck_interval))
                        raise TaskEnd('GuildActivityMonitor')

            # 重置卡死检测计时器，避免纯监控期间误触 GameStuckError
            self.device.stuck_record_clear()
            time.sleep(interval)

    def detect_notification_by_ocr(self) -> str:
        """ 通过截图OCR识别通知区域文字

        ROI区域: x=13, y=213, width=457, height=86
        :return: 识别到的文字内容，无内容返回空字符串
        """
        try:
            boxed_results = self.O_GUILD_ACTIVITY_NOTIFY.detect_and_ocr(self.device.image)
            if not boxed_results:
                return ""
            texts = [result.ocr_text for result in boxed_results if result.ocr_text]
            if texts:
                combined = " ".join(texts)
                logger.debug(f"OCR识别结果: {combined}")
                return combined
            return ""
        except Exception as e:
            logger.warning(f"OCR识别失败: {e}")
            return ""


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()
