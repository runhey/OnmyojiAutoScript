# This Python file uses the following encoding: utf-8
# @author ohspecial
# github https://github.com/ohspecial
from datetime import datetime ,timedelta
from enum import Enum
import time

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_guild, page_main
from tasks.GuildBanquet.assets import GuildBanquetAssets

WEEKDAYDICT = {
    0: '星期一',
    1: '星期二',
    2: '星期三',
    3: '星期四',
    4: '星期五',
    5: '星期六',
    6: '星期日'
}

class Weekday(str,Enum):
    Monday: str = "星期一"
    Tuesday: str = "星期二" 
    Wednesday: str = "星期三"
    Thursday: str = "星期四"
    Friday: str = "星期五"
    Saturday: str = "星期六"
    Sunday: str = "星期日"
    
class ScriptTask(GameUi, GuildBanquetAssets):

    def run(self):
        self.run_time = self.config.guild_banquet.guild_banquet_time
        # 第一天宴会日期及时间
        self.banquet_day_1 = self.get_key_from_value(WEEKDAYDICT, self.run_time.day_1.value)
        self.banquet_day_1_start_time = self.run_time.run_time_1
        
        # 第二天宴会日期及时间
        self.banquet_day_2 = self.get_key_from_value(WEEKDAYDICT, self.run_time.day_2.value)
        self.banquet_day_2_start_time = self.run_time.run_time_2
        
        
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        
        if self.appear(self.I_FLAG):
            wait_count = 0
            wait_timer = Timer(230)
            wait_timer.start()
            logger.info("Start guild banquet!")
            self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            # 如果没有找到FLAG，并且没超过晚上10点，可能是宴会时间没开始，5分钟后尝试再次查找，超过10点则直接退出
            if self.check_runtime():
                time_now = datetime.now()
                time_later = time_now + timedelta(minutes=5)
                self.set_next_run(task='GuildBanquet',
                              finish=True,
                              target=time_later)
            self.ui_get_current_page()
            self.ui_goto(page_main)
            raise TaskEnd

        last_check_time = 0  # 记录上次实际检测时间
        last_log_time = 0  # 记录上次日志输出时间
        last_flag_status = False  # 记录上次真实检测结果

        while True:
            self.screenshot()
            # 条件1: 强制检测间隔管理
            current_time = time.time()
            if current_time - last_check_time >= 10:
                # 达到间隔要求时执行真实检测
                actual_status = self.appear(self.I_FLAG)
                last_flag_status = actual_status
                last_check_time = current_time
                logger.debug(f"Actual detection at {current_time}, status: {actual_status}")
                
                # 重置日志计时器
                last_log_time = current_time
            else:
                # 未达间隔时沿用上次结果
                logger.debug(f"Using cached status: {last_flag_status}")
                
                
            # 条件2: 状态判断逻辑
            if last_flag_status:
                if current_time - last_log_time >= 10:
                    logger.info("Banquet ongoing, waiting...")
                    last_log_time = current_time
            else:
                logger.info("Guild banquet end")
                break  # 退出循环

            # 条件3: 超时保护
            if wait_timer.reached():
                wait_timer.reset()
                if wait_count >= 3:
                    # 宴会最长15分钟
                    logger.info('Guild banquet timeout')
                    break
                wait_count += 1
                logger.info(f'Banquet ongoing, waiting... (Count: {wait_count})')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.stuck_record_clear()
        self.set_config()
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.plan_next_run()
        raise TaskEnd
    
    def check_runtime(self) -> bool:
        """
        检查时间, 一般寮不会晚上10点再开吧。。。。。
        """

        # 如果当日时间超过22点，说明配置时间可能出错，设置下次失败运行时间
        if datetime.now().hour >= 22:
            self.set_next_run(task="GuildBanquet", success=False)
            logger.error("Guild banquet time config error, set next run fail")
            return False
        return True

    def plan_next_run(self):
        # 安排次日宴会，便于复用
        today = datetime.now().weekday()
        
        if today < self.banquet_day_1:
            logger.info(f"Plan next run: {self.banquet_day_1_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=self.banquet_day_1 - today) 
        elif self.banquet_day_1 <= today < self.banquet_day_2:
            logger.info(f"Plan next run: {self.banquet_day_2_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_2_start_time, time_delta=self.banquet_day_2 - today)
        elif self.banquet_day_2 <= today:
            logger.info(f"Plan next run: {self.banquet_day_1_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=7 - today + self.banquet_day_1) 
    
    def get_key_from_value(self, dict, value):
        return [k for k, v in dict.items() if v == value][0]
    
    def get_weekday_enum(self, value: str) -> Weekday:
        for day in Weekday:
            if day.value == value:
                return day
        
    def set_config(self):
        """
        修改周几配置时会出现警告
        UserWarning: Pydantic serializer warnings:
  Expected `enum` but got `Weekday` with value `<Weekday.Thursday: '星期四'>` - serialized value may not be as expected
        """
        
        try:
            # 当结束宴会时，设置宴会时间的日期及时间，宴会时间设置为运行结束时间提前15分钟(因识图问题，宴会可能被认为提前关闭几秒钟)
            next_time = datetime.now() - timedelta(minutes=14, seconds=55)
            next_time = next_time.replace(second=0, microsecond=0)
            # 计算下次运行时间
            next_time = datetime.time(next_time)
            
            today = datetime.now().weekday()          
            
            # 修改配置文件
            if today == self.banquet_day_1:
                self.run_time.run_time_1 = next_time
            elif today == self.banquet_day_2:
                self.run_time.run_time_2 = next_time
            elif today < self.banquet_day_1:
                self.run_time.day_1 = self.get_weekday_enum(WEEKDAYDICT.get(today))
                self.run_time.run_time_1 = next_time
            elif today > self.banquet_day_2:
                self.run_time.day_2 = self.get_weekday_enum(WEEKDAYDICT.get(today))    
                self.run_time.run_time_2 = next_time
            else:
                # 如果当前时间在两个配置时间之间，则默认把工作日设置第一天，周末设为第二天
                if today <= 4:  # 工作日
                    self.run_time.day_1 = self.get_weekday_enum(WEEKDAYDICT.get(today))
                    self.run_time.run_time_1 = next_time
                else:  # 周末
                    self.run_time.day_2 = self.get_weekday_enum(WEEKDAYDICT.get(today))       
                    self.run_time.run_time_2 = next_time
            logger.info(f"Set next run time: {self.run_time}")
            
            self.config.save()
        except Exception as e:
            logger.error(f"Error setting banquet config: {e}")
            raise TaskEnd


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()

