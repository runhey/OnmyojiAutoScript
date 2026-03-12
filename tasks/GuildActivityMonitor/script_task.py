import re
import time
from datetime import datetime, timedelta
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main


class ScriptTask(GameUi):

    def run(self):
        """ 阴阳寮活动监控主函数

        :return:
        """
        # 构建关键字映射
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

        # 获取初始通知时间
        init_time, _ = self.get_notification_info()

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

            # 处理突发事件
            self.screenshot()

            # 检测新通知
            current_time, notification_text = self.get_notification_info()
            if current_time > init_time and notification_text:
                logger.info(f"检测到新通知: {notification_text}")
                for keyword, task_name in KEYWORD_MAP.items():
                    if keyword in notification_text:
                        logger.info(f"检测到关键字 '{keyword}'，启动任务: {task_name}")
                        self.set_next_run(task=task_name, success=False, finish=False, server=False, target=datetime.now())
                        recheck_interval = monitor_config.recheck_interval
                        self.set_next_run(task='GuildActivityMonitor', success=False, finish=False, server=False, target=datetime.now() + timedelta(minutes=recheck_interval))
                        raise TaskEnd('GuildActivityMonitor')

            time.sleep(interval)

    def get_notification_info(self) -> tuple:
        try:
            output = self.device.adb_shell(['dumpsys', 'notification', '--noredact'])

            # 改进的通知时间提取逻辑 - 只获取最新的通知
            notification_time = 0
            notification_text = ""
            
            # 使用更精确的正则表达式匹配每个通知块
            # 查找所有通知块，每个块包含时间戳和文本
            notification_blocks = re.findall(r'(when=(\d+)[\s\S]*?(?=when=|\Z))', output)
            
            if notification_blocks:
                # 找到最新的通知块
                latest_block_time = 0
                latest_text = ""
                
                for block, time_str in notification_blocks:
                    current_time = float(time_str)
                    if current_time > latest_block_time:
                        latest_block_time = current_time
                        # 在当前块中查找活动类型
                        if re.search(r'宴会[^\w]', block) or '寮宴会' in block:
                            latest_text = '宴会'
                        elif re.search(r'狭间[^\w]', block) or '狭间暗域' in block:
                            latest_text = '狭间'
                        elif re.search(r'退治[^\w]', block) or '首领退治' in block:
                            latest_text = '退治'
                        elif re.search(r'道馆[^\w]', block) or '道馆突破' in block:
                            latest_text = '道馆'
                
                notification_time = latest_block_time
                notification_text = latest_text

            return notification_time, notification_text
        except Exception as e:
            logger.warning(f"获取通知失败: {e}")
            return 0, ""

    '''
    def clear_notifications(self):
        """清理系统通知"""
        try:
            # 清理所有通知
            self.device.adb_shell(['cmd', 'notification', 'remove-all'])
            logger.info("已清理系统通知")
        except Exception as e:
            logger.warning(f"清理通知失败: {e}")
    '''


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()